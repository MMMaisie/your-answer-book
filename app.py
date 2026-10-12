"""Your Answer Book v4 — private casts, evidence-based readings and illustrated hexagrams."""
import re
import hashlib,hmac,json,os,secrets,sqlite3,time
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
from flask import has_app_context,Flask,abort,flash as flask_flash,g,redirect,render_template,request,session,url_for,jsonify
from openai import OpenAI
import stripe
from reading_guard import validate_chart_claims
from hexagrams import HEXAGRAMS,build_cast
from i18n import t,hx
from simple_reading import VERSION as SIMPLE_VERSION, generate as simple_generate, render as simple_render, reference_label as simple_reference_label, REFERENCES as SIMPLE_REFERENCES
from external_references import search as web_search
from coarse_timing import validate_coarse_timing

TIMEZONE_LABELS={'Asia/Shanghai':('中国 · 北京','China · Beijing'),'Asia/Hong_Kong':('中国 · 香港','China · Hong Kong'),'Asia/Singapore':('新加坡','Singapore'),'Australia/Adelaide':('澳大利亚 · 阿德莱德','Australia · Adelaide'),'Australia/Sydney':('澳大利亚 · 悉尼','Australia · Sydney'),'Australia/Brisbane':('澳大利亚 · 布里斯班','Australia · Brisbane'),'Australia/Perth':('澳大利亚 · 珀斯','Australia · Perth'),'America/Los_Angeles':('美国 · 洛杉矶','United States · Los Angeles'),'America/New_York':('美国 · 纽约','United States · New York'),'Europe/London':('英国 · 伦敦','United Kingdom · London'),'UTC':('协调世界时 · UTC','Coordinated Universal Time · UTC')}
ROOT=Path(__file__).resolve().parent
SUPPORT_EMAIL=os.getenv('SUPPORT_EMAIL','')
STORAGE_DURABLE=os.getenv('STORAGE_DURABLE','0')=='1'
app=Flask(__name__)
app.jinja_env.globals.update(t=t,hx=hx)
secret=os.getenv('FLASK_SECRET_KEY','')
if not secret:
 if os.getenv('RENDER') or os.getenv('APP_ENV')=='production':
  raise RuntimeError('Set a persistent FLASK_SECRET_KEY before production deployment.')
 keyfile=ROOT/'.local-secret'
 if not keyfile.exists():keyfile.write_text(secrets.token_hex(32));keyfile.chmod(0o600)
 secret=keyfile.read_text().strip()
app.config.update(SECRET_KEY=secret,MAX_CONTENT_LENGTH=32768,SESSION_COOKIE_HTTPONLY=True,
 SESSION_COOKIE_SAMESITE='Lax',SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE','1' if os.getenv('RENDER') or os.getenv('APP_ENV')=='production' else '0')=='1',
 PERMANENT_SESSION_LIFETIME=timedelta(days=30),DB_PATH=os.getenv('DB_PATH',str(ROOT/'readings.db')))
STRIPE_MODE=os.getenv('STRIPE_MODE','live')
if STRIPE_MODE not in ('test','live'):raise RuntimeError('STRIPE_MODE must be test or live.')
STRIPE_TEST_MODE=STRIPE_MODE=='test'
STRIPE_ENV_PREFIX='STRIPE_TEST_' if STRIPE_TEST_MODE else 'STRIPE_'
STRIPE_KEY=os.getenv(STRIPE_ENV_PREFIX+'SECRET_KEY','')
if STRIPE_KEY and not STRIPE_KEY.startswith(('sk_test_','rk_test_') if STRIPE_TEST_MODE else ('sk_live_','rk_live_')):
 raise RuntimeError('Stripe key does not match STRIPE_MODE.')
stripe_client=stripe.StripeClient(STRIPE_KEY) if STRIPE_KEY else None
PRICE_ID=os.getenv(STRIPE_ENV_PREFIX+'PRICE_ID','')
PAYMENT_STATUS='test_paid' if STRIPE_TEST_MODE else 'paid'
def checkout_ready():
 return bool(stripe_client and PRICE_ID and PUBLIC_URL and SUPPORT_EMAIL and
             os.getenv(STRIPE_ENV_PREFIX+'WEBHOOK_SECRET') and (STORAGE_DURABLE or STRIPE_TEST_MODE))
PUBLIC_URL=(os.getenv('PUBLIC_BASE_URL') or os.getenv('RENDER_EXTERNAL_URL','')).rstrip('/')
AI_KEY=os.getenv('DEEPSEEK_API_KEY','')
AI_MODEL=os.getenv('DEEPSEEK_MODEL','deepseek-v4-pro').strip().lower()
NARRATOR_MODEL=os.getenv('DEEPSEEK_NARRATOR_MODEL','deepseek-flash').strip().lower()
PAID_MODEL=os.getenv('DEEPSEEK_PAID_MODEL',AI_MODEL).strip().lower()
PROMPT_VERSION=SIMPLE_VERSION+'-'+hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:10]
AI_TIMEOUT=90
GENERATION_LOCK_TTL=max(600,AI_TIMEOUT*6+60)

SCHEMA='''
CREATE TABLE IF NOT EXISTS readings(seed_key TEXT PRIMARY KEY,lang TEXT,question TEXT,cast_time TEXT,
 words TEXT,topic TEXT,emotion_level TEXT,free_text TEXT,paid_text TEXT,created_at TEXT);
CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY AUTOINCREMENT,seed_key TEXT NOT NULL,
 stripe_session_id TEXT,status TEXT NOT NULL DEFAULT 'paid',amount_total INTEGER,currency TEXT,created_at TEXT,paid_at TEXT);
CREATE TABLE IF NOT EXISTS usage(bucket TEXT,day TEXT,count INTEGER NOT NULL,PRIMARY KEY(bucket,day));
CREATE TABLE IF NOT EXISTS orders(session_id TEXT PRIMARY KEY,seed_key TEXT NOT NULL,price_id TEXT NOT NULL,created_at TEXT);
CREATE TABLE IF NOT EXISTS reading_translations(seed_key TEXT,lang TEXT,tier TEXT,text TEXT,prompt_version TEXT,PRIMARY KEY(seed_key,lang,tier));
CREATE TABLE IF NOT EXISTS generation_locks(seed_key TEXT PRIMARY KEY,started_at REAL);
CREATE TABLE IF NOT EXISTS simple_reading_bundles(cache_key TEXT PRIMARY KEY,bundle_json TEXT NOT NULL);
'''
class ClosingConnection(sqlite3.Connection):
 def __exit__(self,*args):
  try:return super().__exit__(*args)
  finally:self.close()

def connect():
 c=sqlite3.connect(app.config['DB_PATH'],timeout=15,factory=ClosingConnection);c.row_factory=sqlite3.Row
 c.execute('PRAGMA busy_timeout=15000');return c

def init_db():
 Path(app.config['DB_PATH']).parent.mkdir(parents=True,exist_ok=True)
 with connect() as c:
  if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='readings'").fetchone():
   existing={r['name'] for r in c.execute('PRAGMA table_info(readings)')}
   required={'access_key','owner_id','timezone','prompt_version','share_key','paid_version','cache_key'}
   if not required<=existing:
    backup=Path(app.config['DB_PATH']).with_name(Path(app.config['DB_PATH']).name+'.before-v8.sqlite3')
    if not backup.exists():
     temporary=backup.with_name(backup.name+'.'+secrets.token_hex(6)+'.tmp')
     try:
      with sqlite3.connect(temporary,factory=ClosingConnection) as destination:c.backup(destination)
      temporary.chmod(0o600);temporary.replace(backup)
     finally:
      if temporary.exists():temporary.unlink()
  c.execute('PRAGMA journal_mode=WAL');c.executescript(SCHEMA)
  columns={r['name'] for r in c.execute('PRAGMA table_info(readings)')}
  for name,kind in {'access_key':'TEXT','owner_id':'TEXT','timezone':'TEXT','prompt_version':'TEXT',
     'share_key':'TEXT','paid_version':'TEXT','cache_key':'TEXT'}.items():
   if name not in columns:c.execute(f'ALTER TABLE readings ADD COLUMN {name} {kind}')
  columns={r['name'] for r in c.execute('PRAGMA table_info(payments)')}
  for name,kind in {'stripe_session_id':'TEXT','status':"TEXT DEFAULT 'paid'",'amount_total':'INTEGER',
     'currency':'TEXT','created_at':'TEXT','paid_at':'TEXT'}.items():
   if name not in columns:c.execute(f'ALTER TABLE payments ADD COLUMN {name} {kind}')
  for r in c.execute('SELECT seed_key FROM readings WHERE access_key IS NULL').fetchall():
   c.execute('UPDATE readings SET access_key=?,timezone=COALESCE(timezone,?) WHERE seed_key=?',
      (secrets.token_urlsafe(24),'Asia/Shanghai',r['seed_key']))
  c.execute('CREATE UNIQUE INDEX IF NOT EXISTS reading_access ON readings(access_key)')
  c.execute('CREATE UNIQUE INDEX IF NOT EXISTS reading_share ON readings(share_key)')
  c.execute('CREATE INDEX IF NOT EXISTS payment_reading ON payments(seed_key,status)')
  c.execute('CREATE UNIQUE INDEX IF NOT EXISTS payment_session_v4 ON payments(stripe_session_id)')
init_db()

@app.before_request
def prepare():
 session.permanent=True
 if 'owner' not in session:session['owner']=secrets.token_urlsafe(24)
 if 'csrf' not in session:session['csrf']=secrets.token_urlsafe(24)
 g.lang=request.args.get('lang') or session.get('lang','zh')
 if g.lang not in ('zh','en'):g.lang='zh'
 session['lang']=g.lang
 if request.method=='POST' and request.endpoint!='stripe_webhook':
  supplied=request.form.get('csrf','')
  if not hmac.compare_digest(supplied,session['csrf']):abort(400,description='页面已过期，请刷新后重试。')

@app.after_request
def headers(r):
 r.headers['X-Content-Type-Options']='nosniff';r.headers['X-Frame-Options']='DENY'
 r.headers['Referrer-Policy']='no-referrer'
 r.headers['Content-Security-Policy']="default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; form-action 'self' https://checkout.stripe.com; frame-ancestors 'none'; base-uri 'self'"
 if request.path.startswith(('/r/','/reading/','/payment','/history')):
  r.headers['Cache-Control']='private, no-store';r.headers['X-Robots-Tag']='noindex, nofollow'
 return r

@app.context_processor
def context():return {'lang':getattr(g,'lang','zh'),'csrf':session.get('csrf'),'hexagrams':HEXAGRAMS,'support_email':SUPPORT_EMAIL,'timezone_labels':TIMEZONE_LABELS,'stripe_test_mode':STRIPE_TEST_MODE}

def flash(message,category='message'):
 return flask_flash(t(message),category)

class ReadingError(Exception):
 def __init__(self,message):super().__init__(t(message) if has_app_context() else message)

def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))

def bundle_key(question,cast):
 return hashlib.sha256(canonical([PROMPT_VERSION,question,cast]).encode()).hexdigest()

def failure_category(error):
 message=str(error).lower()
 for token,kind in [('length','LENGTH'),('reference','REFERENCE'),('source','REFERENCE'),('contradict','CONTRADICTION'),('element','FOUNDATION'),('json','JSON'),('fields','FORMAT'),('prose','FORMAT'),('incomplete','INCOMPLETE')]:
  if token in message:return kind
 return type(error).__name__

def call_ai(question,cast,lang,tier,free=''):
 if not AI_KEY:raise ReadingError('解读服务暂未开启。卦盘仍可浏览，请稍后再试。')
 key=bundle_key(question,cast)
 try:
  with connect() as c:row=c.execute('SELECT bundle_json FROM simple_reading_bundles WHERE cache_key=?',(key,)).fetchone()
  if row:stored=json.loads(row['bundle_json'])
  else:
   if tier=='paid':raise ReadingError('请先生成本卦初判，再查看完整解读。')
   with OpenAI(api_key=AI_KEY,base_url='https://api.deepseek.com',timeout=AI_TIMEOUT,max_retries=0) as client:
    stored=simple_generate(client,question,cast,AI_MODEL,web_search)
   with connect() as c:c.execute('INSERT OR IGNORE INTO simple_reading_bundles VALUES(?,?)',(key,canonical(stored)))
  bundle=stored['bundle'];text=simple_render(bundle,tier)
  if tier=='paid' and stored.get('external_references'):text+='\n网络补充（检索摘要，不是书中卦例）：\n'+'\n'.join(r['url'] for r in stored['external_references'])
  if lang=='en':return call_translation(text,'en',tier,cast,question)
  return text
 except ReadingError:raise
 except Exception as error:
  app.logger.warning('Simple reading failed: category=%s status=%s',failure_category(error),getattr(error,'status_code',None))
  length_detail=re.search(r'(free|paid) length (\d+); allowed (\d+)-(\d+)',str(error))
  if length_detail:app.logger.warning('Reading length rejected: tier=%s count=%s min=%s max=%s',*length_detail.groups())
  raise ReadingError('本次解读未能完成，请稍后重试。') from None

def paid(seed):
 with connect() as c:return c.execute("SELECT 1 FROM payments WHERE seed_key=? AND status=?",(seed,PAYMENT_STATUS)).fetchone() is not None

def consume_quota(kind='free'):
 day=datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y-%m-%d')
 # Only trust the direct peer. With a known reverse proxy, set TRUST_PROXY=1 and use exactly one trusted hop.
 ip=request.remote_addr or 'unknown'
 digest=hmac.new(app.secret_key.encode(),ip.encode(),hashlib.sha256).hexdigest()
 owner=session['owner']
 if kind=='free':buckets=[('owner-success-v45:'+owner,int(os.getenv('FREE_DAILY_LIMIT','3'))),('ip:'+digest,int(os.getenv('IP_DAILY_LIMIT','12'))),('global',int(os.getenv('GLOBAL_DAILY_LIMIT','100')))]
 elif kind=='free-operation':buckets=[('ip:'+digest,int(os.getenv('IP_DAILY_LIMIT','12'))),('global',int(os.getenv('GLOBAL_DAILY_LIMIT','100')))]
 else:buckets=[('paid-retry:'+owner,5),('paid-global',int(os.getenv('PAID_DAILY_LIMIT','100')))]
 with connect() as c:
  c.execute('BEGIN IMMEDIATE')
  for bucket,limit in buckets:
   r=c.execute('SELECT count FROM usage WHERE bucket=? AND day=?',(bucket,day)).fetchone()
   if r and r['count']>=limit:
    if bucket.startswith('owner-success-'):raise ReadingError('今日解读次数已用完。可以查看已有卦，解锁完整解读；新的免费初判请明天再来。')
    raise ReadingError('服务今日请求额度已达上限，请稍后或明天再试。')
  for bucket,_ in buckets:c.execute('INSERT INTO usage VALUES(?,?,1) ON CONFLICT(bucket,day) DO UPDATE SET count=count+1',(bucket,day))
  c.execute('DELETE FROM usage WHERE day<?',((datetime.now()-timedelta(days=7)).strftime('%Y-%m-%d'),))
 return {'bucket':'owner-success-v45:'+owner,'day':day} if kind=='free' else None

def refund_failed_free(reservation):
 if not reservation:return
 with connect() as c:
  c.execute('UPDATE usage SET count=MAX(0,count-1) WHERE bucket=? AND day=?',(reservation['bucket'],reservation['day']))

def cast_from_row(r):
 try:
  dt=datetime.strptime(r['cast_time'],'%Y-%m-%d %H:%M')
 except ValueError:
  dt=datetime.strptime(r['cast_time'],'%Y/%m/%d %H:%M')
 return build_cast(r['words'].split(','),dt,r['timezone'] or 'Asia/Shanghai')

def fetch_private(access):
 with connect() as c:r=c.execute('SELECT * FROM readings WHERE access_key=?',(access,)).fetchone()
 if not r:abort(404)
 return r

def cached_text(r,tier,lang):
 original=(r['free_text'] if r['prompt_version']==PROMPT_VERSION else '') if tier=='free' else (r['paid_text'] if r['paid_version']==PROMPT_VERSION else '')
 if lang==r['lang']:return original
 with connect() as c:
  row=c.execute('SELECT text FROM reading_translations WHERE seed_key=? AND lang=? AND tier=? AND prompt_version=?',(r['seed_key'],lang,tier,PROMPT_VERSION)).fetchone()
 return row['text'] if row else ''

def call_translation(text,lang,tier,cast=None,question=''):
 if lang!='en':return text
 if not AI_KEY:raise ReadingError('英文解读暂未开启。')
 try:
  from simple_reading import HEADINGS,FIELDS,translate
  body=text.split('【规则依据】')[0]
  values=re.split(r'【[^】]+】',body)[1:]
  if len(values)!=len(FIELDS[tier]):raise ValueError('invalid source sections')
  parts=dict(zip(FIELDS[tier],[v.strip() for v in values]))
  bundle=None;external=[]
  if tier=='paid':
   key=bundle_key(question,cast)
   with connect() as c:row=c.execute('SELECT bundle_json FROM simple_reading_bundles WHERE cache_key=?',(key,)).fetchone()
   if not row:raise ValueError('canonical source record missing')
   stored=json.loads(row['bundle_json']);bundle=stored['bundle'];external=stored.get('external_references',[])
  with OpenAI(api_key=AI_KEY,base_url='https://api.deepseek.com',timeout=AI_TIMEOUT,max_retries=0) as client:
   translated=translate(client,parts,tier,cast or {},NARRATOR_MODEL,bundle['sources'] if bundle else ())
  result='\n'.join('【'+h+'】'+translated['parts'][f] for h,f in zip(HEADINGS['en'][tier],FIELDS[tier]))
  if bundle:
   result+='\n【Source notes】\n'+'\n'.join(simple_reference_label(SIMPLE_REFERENCES[s['id']],'en')+' — '+note for s,note in zip(bundle['sources'],translated['source_applications']))
   if external:result+='\nWeb supplements (search excerpts; not book cases):\n'+'\n'.join(r['url'] for r in external)
  return result
 except Exception as error:
  app.logger.warning('Simple translation failed: category=%s status=%s',failure_category(error),getattr(error,'status_code',None))
  raise ReadingError('本次翻译未能完成，中文解读仍可查看，请稍后重试。') from None

def generate_text(r,tier,lang):
 cached=cached_text(r,tier,lang)
 if cached:return cached
 # Produce the canonical Chinese view before taking the translation lock.
 # This also covers English-first paid requests without recursive lock conflicts.
 if lang=='en':generate_text(r,tier,'zh')
 lock_key=r['seed_key']+':'+tier
 with connect() as c:
  c.execute('DELETE FROM generation_locks WHERE started_at<?',(time.time()-GENERATION_LOCK_TTL,))
  try:c.execute('INSERT INTO generation_locks VALUES(?,?)',(lock_key,time.time()))
  except sqlite3.IntegrityError:raise ReadingError('完整解读正在生成，请稍后刷新。')
 try:
  # A second request may have completed between the initial cache read and lock acquisition.
  with connect() as c:
   refreshed=c.execute('SELECT * FROM readings WHERE seed_key=?',(r['seed_key'],)).fetchone()
  if refreshed is None:abort(404)
  r=refreshed
  cached=cached_text(r,tier,lang)
  if cached:return cached
  consume_quota('paid' if tier=='paid' else 'free-operation')
  original=cached_text(r,tier,'zh') if lang=='en' else ''
  if original:text=call_translation(original,'en',tier,cast_from_row(r),r['question'])
  else:
   free=cached_text(r,'free',lang)
   if tier=='paid' and not free:free=generate_text(r,'free',lang)
   text=call_ai(r['question'],cast_from_row(r),lang,tier,free)
  try:
   validate_chart_claims(text,cast_from_row(r))
  except ValueError:
   raise ReadingError('本次解读未通过卦盘一致性检查，请稍后重试。') from None
  with connect() as c:
   if lang==r['lang'] and tier=='free':c.execute('UPDATE readings SET free_text=?,prompt_version=? WHERE seed_key=?',(text,PROMPT_VERSION,r['seed_key']))
   elif lang==r['lang'] and tier=='paid':c.execute('UPDATE readings SET paid_text=?,paid_version=? WHERE seed_key=?',(text,PROMPT_VERSION,r['seed_key']))
   else:c.execute('INSERT OR REPLACE INTO reading_translations VALUES(?,?,?,?,?)',(r['seed_key'],lang,tier,text,PROMPT_VERSION))
  return text
 finally:
  with connect() as c:c.execute('DELETE FROM generation_locks WHERE seed_key=?',(lock_key,))

def generate_paid(r):return generate_text(r,'paid',g.lang)

@app.post('/r/<access>/language')
def reading_language(access):
 r=fetch_private(access)
 try:generate_text(r,'free',g.lang)
 except ReadingError as e:flash(str(e),'error')
 return redirect(url_for('reading_page',access=access,lang=g.lang))

@app.route('/',methods=['GET','POST'])
def home():
 form={}
 if request.method=='POST':
  form=request.form.to_dict()
  reservation=None
  try:
   question=request.form.get('question','').strip()
   if not 4<=len(question)<=600:raise ValueError('问题请写4—600个字，并尽量说明目标与时限。')
   words=[request.form.get(f'word{i}','') for i in range(1,7)]
   dt=datetime.fromisoformat(request.form.get('cast_time',''))
   if dt.tzinfo is not None or not 1900<=dt.year<=2100:raise ValueError('请使用1900—2100年之间的有效起卦时间。')
   tz=request.form.get('timezone','Asia/Shanghai');ZoneInfo(tz)
   cast=build_cast(words,dt,tz)
   normalized=' '.join(question.split())
   cache_key=hashlib.sha256(json.dumps([PROMPT_VERSION,g.lang,normalized,dt.isoformat(),tz,words],ensure_ascii=False).encode()).hexdigest()
   with connect() as c:
    cached=c.execute('SELECT access_key FROM readings WHERE cache_key=? AND owner_id=?',(cache_key,session['owner'])).fetchone()
   if cached:return redirect(url_for('reading_page',access=cached['access_key']))
   reservation=consume_quota()
   text=call_ai(question,cast,'zh','free')
   translated=call_translation(text,'en','free',cast,question) if g.lang=='en' else None
   key=secrets.token_urlsafe(24);seed=secrets.token_hex(24)
   with connect() as c:
    c.execute('''INSERT INTO readings(seed_key,lang,question,cast_time,words,free_text,paid_text,created_at,
      access_key,owner_id,timezone,prompt_version,cache_key) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
      (seed,'zh',question,dt.strftime('%Y-%m-%d %H:%M'),','.join(words),text,'',datetime.now().isoformat(),key,session['owner'],tz,PROMPT_VERSION,cache_key))
    if translated:c.execute('INSERT INTO reading_translations VALUES(?,?,?,?,?)',(seed,'en','free',translated,PROMPT_VERSION))
   reservation=None
   return redirect(url_for('reading_page',access=key))
  except (ValueError,ZoneInfoNotFoundError):flash('请检查问题、六次结果和起卦时间。','error')
  except ReadingError as e:
   flash(str(e),'error')
   if '今日解读次数已用完' in str(e):form['quota_exhausted']=True
  finally:refund_failed_free(reservation)
 return render_template('home.html',form=form,free_limit=os.getenv('FREE_DAILY_LIMIT','3'))

@app.route('/r/<access>')
def reading_page(access):
 r=fetch_private(access)
 unlocked=paid(r['seed_key'])
 # No paid generation on GET: refreshes, previews and crawlers must not trigger model spend.
 full=cached_text(r,'paid',g.lang) if unlocked else ''
 return render_template('reading.html',reading=r,cast=cast_from_row(r),unlocked=unlocked,full=full,free_text=cached_text(r,'free',g.lang),
   checkout_enabled=checkout_ready(),share=False)

@app.post('/r/<access>/full')
def full_reading(access):
 r=fetch_private(access)
 if not paid(r['seed_key']):abort(403)
 try:generate_paid(r)
 except ReadingError as e:flash(str(e),'error')
 return redirect(url_for('reading_page',access=access))

@app.get('/reading/<seed_key>')
def legacy_reading(seed_key):
 # Old predictable/cache links can no longer expose question or paid content.
 with connect() as c:r=c.execute('SELECT access_key FROM readings WHERE seed_key=? AND owner_id=?',(seed_key,session['owner'])).fetchone()
 if not r:abort(404)
 return redirect(url_for('reading_page',access=r['access_key']))

@app.post('/r/<access>/share')
def create_share(access):
 r=fetch_private(access);share_key=r['share_key'] or secrets.token_urlsafe(24)
 with connect() as c:c.execute('UPDATE readings SET share_key=? WHERE access_key=?',(share_key,access))
 return redirect(url_for('share_page',key=share_key))

@app.post('/r/<access>/unshare')
def revoke_share(access):
 fetch_private(access)
 with connect() as c:c.execute('UPDATE readings SET share_key=NULL WHERE access_key=?',(access,))
 flash('分享链接已关闭。');return redirect(url_for('reading_page',access=access))

@app.get('/share/<key>')
def share_page(key):
 with connect() as c:r=c.execute('SELECT * FROM readings WHERE share_key=?',(key,)).fetchone()
 if not r:abort(404)
 # Public card never contains the original question, reading text, access key, or checkout link.
 return render_template('share.html',cast=cast_from_row(r))

@app.get('/history')
def history():
 with connect() as c:rows=c.execute('SELECT access_key,question,cast_time FROM readings WHERE owner_id=? ORDER BY created_at DESC LIMIT 30',(session['owner'],)).fetchall()
 return render_template('history.html',rows=rows)

@app.get('/deck')
def deck():return render_template('deck.html')

@app.get('/deck/<int:number>')
def card_page(number):
 if not 1<=number<=64:abort(404)
 return render_template('card.html',card=HEXAGRAMS[number-1])

@app.get('/demo')
def demo():
 cast=build_cast(['2','1','2','1','2','1'],datetime(2026,10,4,16,0),'Asia/Shanghai')
 return render_template('demo.html',cast=cast)

@app.get('/policy')
def policy():return render_template('policy.html')

@app.get('/healthz')
def health():
 with connect() as c:c.execute('SELECT 1')
 return jsonify(ok=True,version=PROMPT_VERSION,ai_model=AI_MODEL,case_archive=133,case_retrieval=112,reading_pipeline="book_reference_model_reasoning",web_search_enabled=bool(os.getenv("BRAVE_SEARCH_API_KEY")),languages=['zh','en'],payment_mode=STRIPE_MODE,checkout_enabled=checkout_ready())

def fulfill(session_data,expected_seed=None):
 if session_data.get('livemode') is not (not STRIPE_TEST_MODE):return False
 if not STRIPE_TEST_MODE and not STORAGE_DURABLE:return False
 sid=session_data.get('id');seed=(session_data.get('metadata') or {}).get('seed_key')
 if session_data.get('payment_status')!='paid' or not sid or not seed:return False
 if expected_seed and seed!=expected_seed:return False
 with connect() as c:
  order=c.execute('SELECT * FROM orders WHERE session_id=?',(sid,)).fetchone()
  if not order or order['seed_key']!=seed or order['price_id']!=PRICE_ID:return False
  if c.execute('SELECT 1 FROM payments WHERE stripe_session_id=?',(sid,)).fetchone():return True
  c.execute("INSERT OR IGNORE INTO payments(seed_key,stripe_session_id,status,amount_total,currency,created_at,paid_at) VALUES(?,?,?,?,?,?,?)",
    (seed,sid,PAYMENT_STATUS,session_data.get('amount_total'),session_data.get('currency'),datetime.now().isoformat(),datetime.now().isoformat()))
 return True

@app.post('/r/<access>/checkout')
def checkout(access):
 r=fetch_private(access)
 if paid(r['seed_key']):return redirect(url_for('reading_page',access=access))
 if not checkout_ready():flash('付款服务暂未开启。','error');return redirect(url_for('reading_page',access=access))
 try:
  price=stripe_client.v1.prices.retrieve(PRICE_ID)
  if price.livemode is not (not STRIPE_TEST_MODE) or not price.active or price.type!='one_time':raise ValueError('Invalid price')
  params=dict(mode='payment',line_items=[{'price':PRICE_ID,'quantity':1}],
    integration_identifier='answerbook_'+''.join(secrets.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(8)),
    metadata={'seed_key':r['seed_key']},
    success_url=PUBLIC_URL+url_for('payment_success',seed_key=r['seed_key'])+'?session_id={CHECKOUT_SESSION_ID}',
    cancel_url=PUBLIC_URL+url_for('reading_page',access=access))
  s=stripe_client.v1.checkout.sessions.create(params)
  if s.livemode is not (not STRIPE_TEST_MODE):raise ValueError('Invalid session mode')
  with connect() as c:c.execute('INSERT OR IGNORE INTO orders VALUES(?,?,?,?)',(s.id,r['seed_key'],PRICE_ID,datetime.now().isoformat()))
  return redirect(s.url,code=303)
 except Exception:
  app.logger.warning('Checkout creation failed.');flash('付款暂未发起，请稍后再试。','error')
  return redirect(url_for('reading_page',access=access))

@app.get('/payment/success/<seed_key>')
def payment_success(seed_key):
 if not stripe_client:abort(503)
 sid=request.args.get('session_id','')
 if not sid.startswith('cs_'):abort(400)
 try:
  s=stripe_client.v1.checkout.sessions.retrieve(sid)
  d=s.to_dict() if hasattr(s,'to_dict') else dict(s)
  if not fulfill(d,seed_key):abort(403)
 except (stripe.StripeError,ValueError):abort(400)
 with connect() as c:r=c.execute('SELECT access_key FROM readings WHERE seed_key=?',(seed_key,)).fetchone()
 if not r:abort(404)
 # Recovery link is issued only after checking this server's verified paid order.
 flash('付款已确认，点击“生成完整解读”即可继续。')
 return redirect(url_for('reading_page',access=r['access_key']))

@app.post('/stripe/webhook')
def stripe_webhook():
 secret=os.getenv(STRIPE_ENV_PREFIX+'WEBHOOK_SECRET','')
 if not secret:return jsonify(error='not configured'),503
 try:
  event=stripe.Webhook.construct_event(request.get_data(),request.headers.get('Stripe-Signature',''),secret)
  e=event.to_dict() if hasattr(event,'to_dict') else dict(event)
 except (ValueError,stripe.SignatureVerificationError):return jsonify(error='invalid signature'),400
 if e.get('livemode') is not (not STRIPE_TEST_MODE):return jsonify(error='wrong mode'),400
 if e['type'] in ('checkout.session.completed','checkout.session.async_payment_succeeded'):
  fulfill(e['data']['object'])
 return jsonify(received=True)

@app.errorhandler(400)
@app.errorhandler(403)
@app.errorhandler(404)
@app.errorhandler(413)
@app.errorhandler(500)
@app.errorhandler(503)
def error_page(e):return render_template('error.html',status=e.code),e.code

if os.getenv('TRUST_PROXY','0')=='1':
 from werkzeug.middleware.proxy_fix import ProxyFix
 app.wsgi_app=ProxyFix(app.wsgi_app,x_for=1,x_proto=1)

if __name__=='__main__':app.run(host='0.0.0.0',port=int(os.getenv('PORT','5000')),debug=False)
