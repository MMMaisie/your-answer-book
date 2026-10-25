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
from simple_reading import VERSION as SIMPLE_VERSION, generate as simple_generate, generate_paid as simple_generate_paid, render as simple_render, reference_label as simple_reference_label, REFERENCES as SIMPLE_REFERENCES
from external_references import search as web_search
from coarse_timing import validate_coarse_timing
from security_controls import private_access,bounded_client,CallLimitError
from membership import Membership,AccessError
from storage_checks import mounted_database

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
             os.getenv(STRIPE_ENV_PREFIX+'WEBHOOK_SECRET') and ((STORAGE_DURABLE and mounted_database(app.config['DB_PATH'])) or STRIPE_TEST_MODE))
PUBLIC_URL=(os.getenv('PUBLIC_BASE_URL') or os.getenv('RENDER_EXTERNAL_URL','')).rstrip('/')
AI_KEY=os.getenv('DEEPSEEK_API_KEY','')
AI_MODEL=os.getenv('DEEPSEEK_MODEL','deepseek-v4-pro').strip().lower()
NARRATOR_MODEL=os.getenv('DEEPSEEK_NARRATOR_MODEL','deepseek-flash').strip().lower()
PAID_MODEL=os.getenv('DEEPSEEK_PAID_MODEL',AI_MODEL).strip().lower()
PROMPT_VERSION=SIMPLE_VERSION+'-'+hashlib.sha256(Path(__file__).read_bytes()+b''.join((ROOT/n).read_bytes() for n in ('membership.py','security_controls.py','storage_checks.py','external_references.py'))).hexdigest()[:10]
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
 blocked=private_access()
 if blocked is not None:return blocked
 session.permanent=True
 if 'owner' not in session:session['owner']=secrets.token_urlsafe(24)
 if 'csrf' not in session:session['csrf']=secrets.token_urlsafe(24)
 g.account=members.user()
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
 r.headers['Content-Security-Policy']="default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self' https://challenges.cloudflare.com; frame-src https://challenges.cloudflare.com; connect-src 'self' https://challenges.cloudflare.com; form-action 'self' https://checkout.stripe.com; frame-ancestors 'none'; base-uri 'self'"
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

SAFE_VALIDATION_MESSAGES = frozenset(['English language leakage', 'absolute outcome', 'branch clash/combine contradiction', 'branch element contradicts theory', 'calendar clash contradicts chart', 'calendar combination must not replace elemental affinity', 'combined void/broken claim adds unsupported month-broken status', 'duplicate references', 'explicit elemental contradiction', 'explicit elemental contradiction (branch endpoints)', 'explicit elemental contradiction (compact calendar relation)', 'explicit elemental contradiction (named calendar endpoints)', 'focal contradicts explicit child question', 'free and paid contradict the shared direction', 'incomplete prose repair', 'incomplete reading', 'incomplete translation', 'invalid analysis', 'invalid fact slot', 'invalid prose', 'invalid reading bundle', 'invalid reference', 'matching period branch must not replace elemental affinity', 'matching period branches must not replace elemental affinity', 'month-broken claim contradicts calendar', 'month-building identity contradicts calendar; same element is not same branch', 'moving claim contradicts static chart', 'named calendar branch contradicts chart', 'one to three sources required', 'returning relation contradicts changed-to-original elemental direction', 'source application translation changed', 'specific timing is disabled; use qualitative pace only', 'unconditional void disables line', 'void claim contradicts calendar or missing status'])

def safe_failure_details(error):
 import traceback
 underlying=error
 while underlying.__cause__ is not None and isinstance(underlying.__cause__,(ValueError,TypeError,KeyError)):underlying=underlying.__cause__
 message=str(underlying)
 reason=message if message in SAFE_VALIDATION_MESSAGES else "unclassified"
 frames=traceback.extract_tb(error.__traceback__)
 allowed={"simple_reading.py","reading_guard.py","theory_facts.py","coarse_timing.py","app.py"}
 locations=[f"{os.path.basename(f.filename)}:{f.lineno}:{f.name}" for f in frames if os.path.basename(f.filename) in allowed]
 return reason," > ".join(locations[-6:]) or "no_application_frame"

def call_ai(question,cast,lang,tier,free=''):
 if not AI_KEY:raise ReadingError('AI服务尚未配置。 / AI service is not configured.')
 if os.getenv('AI_ENABLED','1')!='1':raise ReadingError('AI服务暂时暂停。 / AI generation is paused.')
 key=bundle_key(question,cast)
 try:
  with connect() as c:row=c.execute('SELECT bundle_json FROM simple_reading_bundles WHERE cache_key=?',(key,)).fetchone()
  stored=json.loads(row['bundle_json']) if row else None
  if tier=='paid':
   # Payment/credit authorisation is checked again at the actual provider boundary.
   with connect() as c:r=c.execute('SELECT * FROM readings WHERE cache_key IS NOT NULL AND question=? AND words=? ORDER BY created_at DESC',(question,','.join(map(str,cast['words'])))).fetchall()
   authorized=any(bundle_key(question,cast_from_row(x))==key and (paid(x['seed_key']) or members.held(x['seed_key'])) for x in r)
   if not authorized:raise ReadingError('请先付款或使用一次余额。 / Payment or a reading credit is required.')
   if not stored:raise ReadingError('请先生成初判。 / Generate the initial reading first.')
   if 'paid' not in stored['bundle']:
    with OpenAI(api_key=AI_KEY,base_url='https://api.deepseek.com',timeout=AI_TIMEOUT,max_retries=0) as client:
     parts=simple_generate_paid(bounded_client(client,connect),question,cast,AI_MODEL,stored['bundle'],lambda topics:web_search(topics,connect=connect),stored.get('external_reference'))
    stored['bundle']['paid']=parts
    with connect() as c:c.execute('UPDATE simple_reading_bundles SET bundle_json=? WHERE cache_key=?',(canonical(stored),key))
  elif not stored:
   with OpenAI(api_key=AI_KEY,base_url='https://api.deepseek.com',timeout=AI_TIMEOUT,max_retries=0) as client:
    stored=simple_generate(bounded_client(client,connect),question,cast,AI_MODEL,lambda topics:web_search(topics,connect=connect))
   with connect() as c:c.execute('INSERT OR IGNORE INTO simple_reading_bundles VALUES(?,?)',(key,canonical(stored)))
  text=simple_render(stored['bundle'],tier)
  return call_translation(text,'en',tier,cast,question) if lang=='en' else text
 except ReadingError:raise
 except Exception as error:
  reason,location=safe_failure_details(error)
  app.logger.warning('Reading diagnostic: category=%s reason=%s location=%s status=%s',failure_category(error),reason,location,getattr(error,'status_code',None))
  if isinstance(error,CallLimitError):raise ReadingError('服务调用额度已达上限，请稍后再试。 / Service usage limit reached.') from None
  if getattr(error,'status_code',None)==402:raise ReadingError('AI服务余额不足，请联系网站管理员。 / AI service balance is insufficient.') from None
  raise ReadingError('本次解读未能完成，未扣取解读次数。 / Generation failed; no reading credit was charged.') from None

def paid(seed):
 if members.entitled(seed):return True
 with connect() as c:return c.execute("SELECT 1 FROM payments WHERE seed_key=? AND status=?",(seed,PAYMENT_STATUS)).fetchone() is not None

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
 if not AI_KEY or os.getenv('AI_ENABLED','1')!='1':raise ReadingError('英文解读暂未开启。 / Translation is unavailable.')
 try:
  from simple_reading import HEADINGS,FIELDS,translate
  body=text.split('【规则依据】')[0]
  values=re.split(r'【[^】]+】',body)[1:]
  if len(values)!=len(FIELDS[tier]):raise ValueError('invalid source sections')
  parts=dict(zip(FIELDS[tier],[v.strip() for v in values]))
  with OpenAI(api_key=AI_KEY,base_url='https://api.deepseek.com',timeout=AI_TIMEOUT,max_retries=0) as client:
   translated=translate(bounded_client(client,connect),parts,tier,cast or {},NARRATOR_MODEL)
  result='\n'.join('【'+h+'】'+translated['parts'][f] for h,f in zip(HEADINGS['en'][tier],FIELDS[tier]))
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
  trial=None;hold=None;request_lock=None
  try:
   members.rate('generation',6,3600)
   question=request.form.get('question','').strip()
   if not 2<=len(question)<=500:raise ValueError('问题请写2—500个字。')
   words=[request.form.get(f'word{i}','') for i in range(1,7)]
   dt=datetime.fromisoformat(request.form.get('cast_time',''))
   if dt.tzinfo is not None or dt.second or dt.microsecond or not 1900<=dt.year<=2100:raise ValueError('请使用1900—2100年之间的有效起卦时间。')
   tz=request.form.get('timezone','Asia/Shanghai');ZoneInfo(tz)
   cast=build_cast(words,dt,tz)
   normalized=' '.join(question.split())
   cache_key=hashlib.sha256(json.dumps([PROMPT_VERSION,normalized,dt.isoformat(),tz,words],ensure_ascii=False).encode()).hexdigest()
   with connect() as c:
    cached=c.execute('SELECT access_key FROM readings WHERE cache_key=? AND owner_id=?',(cache_key,session['owner'])).fetchone()
   if cached:return redirect(url_for('reading_page',access=cached['access_key']))
   pending_key='initial:'+hashlib.sha256((session['owner']+cache_key).encode()).hexdigest()
   with connect() as c:
    c.execute('DELETE FROM generation_locks WHERE started_at<?',(time.time()-GENERATION_LOCK_TTL,))
    try:c.execute('INSERT INTO generation_locks VALUES(?,?)',(pending_key,time.time()))
    except sqlite3.IntegrityError:raise ReadingError('这个问题正在生成，请稍后查看历史记录。 / This reading is already being generated.')
   request_lock=pending_key
   members.captcha()
   try:trial=members.reserve_trial(verified=True)
   except AccessError:
    hold=members.reserve_credit(verified=True)
   text=call_ai(question,cast,'zh','free')
   translated=None
   key=secrets.token_urlsafe(24);seed=secrets.token_hex(24)
   with connect() as c:
    c.execute('''INSERT INTO readings(seed_key,lang,question,cast_time,words,free_text,paid_text,created_at,
      access_key,owner_id,timezone,prompt_version,cache_key) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
      (seed,'zh',question,dt.strftime('%Y-%m-%d %H:%M'),','.join(words),text,'',datetime.now().isoformat(),key,session['owner'],tz,PROMPT_VERSION,cache_key))
    if translated:c.execute('INSERT INTO reading_translations VALUES(?,?,?,?,?)',(seed,'en','free',translated,PROMPT_VERSION))
   if hold:
    members.bind_hold(hold,seed)
    with connect() as c:new_reading=c.execute('SELECT * FROM readings WHERE seed_key=?',(seed,)).fetchone()
    generate_text(new_reading,'paid','zh')
    members.finish_credit(hold,True);hold=None
   members.finish_trial(trial,True);trial=None
   if g.lang=='en':
    try:
     with connect() as c:new_reading=c.execute('SELECT * FROM readings WHERE seed_key=?',(seed,)).fetchone()
     generate_text(new_reading,'free','en')
     if paid(seed):generate_text(new_reading,'paid','en')
    except ReadingError as error:flash(str(error),'error')
   return redirect(url_for('reading_page',access=key))
  except (ValueError,ZoneInfoNotFoundError):flash('请检查问题、六次结果和起卦时间。','error')
  except (ReadingError,AccessError) as e:
   flash(str(e),'error')
   if '今日解读次数已用完' in str(e):form['quota_exhausted']=True
  finally:
   members.finish_trial(trial,False);members.finish_credit(hold,False)
   if request_lock:
    with connect() as c:c.execute('DELETE FROM generation_locks WHERE seed_key=?',(request_lock,))
 return render_template('home.html',form=form,free_limit='1')

@app.route('/r/<access>')
def reading_page(access):
 r=fetch_private(access)
 unlocked=paid(r['seed_key'])
 # No paid generation on GET: refreshes, previews and crawlers must not trigger model spend.
 full=cached_text(r,'paid',g.lang) if unlocked else ''
 return render_template('reading.html',reading=r,cast=cast_from_row(r),unlocked=unlocked,full=full,free_text=cached_text(r,'free',g.lang),
   checkout_enabled=checkout_ready(),wallet_enabled=members.ready(),share=False)

@app.post('/r/<access>/full')
def full_reading(access):
 r=fetch_private(access);hold=None
 try:
  members.rate('full',6,3600)
  if not paid(r['seed_key']):
   hold=members.reserve_credit(r['seed_key'])
  generate_text(r,'paid','zh')
  members.finish_credit(hold,True);hold=None
  if g.lang=='en':generate_text(r,'paid','en')
 except (ReadingError,AccessError) as e:flash(str(e),'error')
 finally:members.finish_credit(hold,False)
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

@app.context_processor
def account_context():
 u=members.user()
 return {'account_user':({k:u[k] for k in ('id','email','verified')} if u else None),'account_balance':members.balance(u['id']) if u else 0,'turnstile_site_key':os.getenv('TURNSTILE_SITE_KEY','') if not os.getenv('SITE_ACCESS_PASSWORD') else ''}

@app.get('/healthz')
def health():
 with connect() as c:c.execute('SELECT 1')
 return jsonify(ok=True,private_test_enabled=bool(os.getenv("SITE_ACCESS_PASSWORD")),version=PROMPT_VERSION,ai_model=AI_MODEL,case_archive=133,case_retrieval=112,reading_pipeline="book_reference_model_reasoning",web_search_enabled=bool(AI_KEY) and os.getenv("WEB_SEARCH_ENABLED","1")=="1",languages=['zh','en'],payment_mode=STRIPE_MODE,checkout_enabled=members.ready(),generation_mode='paid_deferred',currency='aud',output_limits={'zh_free':50,'zh_paid':300,'en_free':60,'en_paid':350},mounted_storage=mounted_database(app.config['DB_PATH']))

def fulfill(session_data,expected_seed=None):
 if session_data.get('livemode') is not (not STRIPE_TEST_MODE):return False
 if not STRIPE_TEST_MODE and not (STORAGE_DURABLE and mounted_database(app.config['DB_PATH'])):return False
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
 fetch_private(access)
 return redirect(url_for('account.wallet'))

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
  obj=e['data']['object']
  if (obj.get('metadata') or {}).get('wallet_account_id'):
   if obj.get('payment_status')=='paid' and not members.fulfill(obj):return jsonify(error='order not ready'),503
  else:fulfill(obj)
 if e['type']=='charge.refunded':members.reverse_payment(e['data']['object'])
 if e['type']=='charge.dispute.created':members.reverse_payment(e['data']['object'],True)
 return jsonify(received=True)

@app.errorhandler(400)
@app.errorhandler(403)
@app.errorhandler(404)
@app.errorhandler(413)
@app.errorhandler(500)
@app.errorhandler(503)
def error_page(e):return render_template('error.html',status=e.code),e.code

import sys
members=Membership(sys.modules[__name__])

if os.getenv('TRUST_PROXY','0')=='1':
 from werkzeug.middleware.proxy_fix import ProxyFix
 app.wsgi_app=ProxyFix(app.wsgi_app,x_for=1,x_proto=1)

if __name__=='__main__':app.run(host='0.0.0.0',port=int(os.getenv('PORT','5000')),debug=False)
