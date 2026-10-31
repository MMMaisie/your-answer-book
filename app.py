"""Guest checkout, expiring reading snapshots and shared database protection."""
import hashlib,hmac,json,os,secrets,time
from datetime import datetime,timedelta
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
from flask import Flask,abort,flash,g,jsonify,redirect,render_template,request,session,url_for,Response
from openai import OpenAI
import stripe
from hexagrams import HEXAGRAMS,build_cast
from i18n import t,hx
from locations import TIMEZONE_LABELS
from storage import Store
from protection import Protection,Limited,QuotaUsed,VerificationFailed,BudgetExceeded,bounded_client,capacity,budget_settings
import simple_reading as engine

ROOT=Path(__file__).resolve().parent
app=Flask(__name__)
production=bool(os.getenv('RENDER') or os.getenv('APP_ENV')=='production')
secret=os.getenv('FLASK_SECRET_KEY','')
if not secret:
 if production:raise RuntimeError('Configure FLASK_SECRET_KEY in the server environment.')
 local=ROOT/'.local-secret-v49'
 if not local.exists():local.write_text(secrets.token_hex(32));local.chmod(0o600)
 secret=local.read_text().strip()
app.config.update(SECRET_KEY=secret,MAX_CONTENT_LENGTH=32768,SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Lax',SESSION_COOKIE_SECURE=production,PERMANENT_SESSION_LIFETIME=timedelta(days=30))
app.jinja_env.globals.update(t=t,hx=hx)
PUBLIC_URL=(os.getenv('PUBLIC_BASE_URL') or os.getenv('RENDER_EXTERNAL_URL','')).rstrip('/')
if PUBLIC_URL and urlparse(PUBLIC_URL).scheme not in ('http','https'):raise RuntimeError('Invalid PUBLIC_BASE_URL.')
if production and PUBLIC_URL and urlparse(PUBLIC_URL).scheme!='https':raise RuntimeError('Production URL must use HTTPS.')
DATABASE_URL=os.getenv('DATABASE_URL','')
if production and not DATABASE_URL:raise RuntimeError('Configure Neon DATABASE_URL before deployment. No temporary database fallback in production.')
store=Store(DATABASE_URL,os.getenv('DB_PATH',str(ROOT/'readings-v49.db')));store.init()
protect=Protection(store,secret,PUBLIC_URL)
STRIPE_MODE=os.getenv('STRIPE_MODE','test')
if STRIPE_MODE not in ('test','live'):raise RuntimeError('Invalid STRIPE_MODE.')
PREFIX='STRIPE_TEST_' if STRIPE_MODE=='test' else 'STRIPE_'
STRIPE_KEY=os.getenv(PREFIX+'SECRET_KEY','')
if STRIPE_KEY and not STRIPE_KEY.startswith(('sk_test_','rk_test_') if STRIPE_MODE=='test' else ('sk_live_','rk_live_')):raise RuntimeError('Stripe key and mode do not match.')
stripe_client=stripe.StripeClient(STRIPE_KEY) if STRIPE_KEY else None
AMOUNT=int(os.getenv('READING_PRICE_CENTS','199'))
if AMOUNT<50:raise RuntimeError('READING_PRICE_CENTS must be at least 50.')
SUPPORT_EMAIL=os.getenv('SUPPORT_EMAIL','')
AI_KEY=os.getenv('DEEPSEEK_API_KEY','')
AI_MODEL=os.getenv('DEEPSEEK_MODEL','deepseek-v4-pro').lower().strip()
TRANSLATION_MODEL=os.getenv('DEEPSEEK_NARRATOR_MODEL','deepseek-flash').lower().strip()
VERSION=engine.VERSION+'-'+hashlib.sha256(b''.join((ROOT/n).read_bytes() for n in ('app.py','storage.py','protection.py','external_references.py','pdf_export.py'))).hexdigest()[:8]
RETENTION_DAYS=10
GENERATION_TTL=1200

def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def label(zh,en):return zh if getattr(g,'lang','zh')=='zh' else en

def checkout_ready():
 return bool(store.durable and stripe_client and PUBLIC_URL and SUPPORT_EMAIL and AI_KEY and os.getenv(PREFIX+'WEBHOOK_SECRET') and os.getenv('TURNSTILE_SITE_KEY') and os.getenv('TURNSTILE_SECRET_KEY') and capacity(store))

def delivery_capacity(row,lang):
 # Check a conservative single-attempt delivery allowance before taking a NEW payment.
 # Model repair, rate changes or subsequent traffic can still delay delivery; entitlement persists.
 data=json.loads(row['bundle_json']).get('reference_snapshot')
 if not data:data=engine.context(row['question'],json.loads(row['cast_json']))[0]
 ir,ou,factor,_=budget_settings(AI_MODEL)
 size=len(canonical(data).encode())+6000
 cost=(size*ir+4096*ou)/1000000*factor
 if not row['bundle_json'] or row['bundle_json']=='{}':cost*=2
 if lang=='en':
  ti,to,tf,_=budget_settings(TRANSLATION_MODEL)
  cost+=(6000*ti+2048*to)/1000000*tf
 return capacity(store,cost)

def private_access():
 password=os.getenv('SITE_ACCESS_PASSWORD','')
 if not password or request.endpoint in ('health','stripe_webhook'):return None
 a=request.authorization
 if a and a.type.lower()=='basic' and hmac.compare_digest((a.username or '').encode(),b'tester') and hmac.compare_digest((a.password or '').encode(),password.encode()):return None
 return Response('Private test site.',401,{'WWW-Authenticate':'Basic realm="Private test"','Cache-Control':'no-store'})

@app.before_request
def prepare():
 denied=private_access()
 if denied:return denied
 session.permanent=True
 session.setdefault('owner',secrets.token_urlsafe(24));session.setdefault('csrf',secrets.token_urlsafe(24))
 g.lang=request.args.get('lang',session.get('lang','zh'))
 if g.lang not in ('zh','en'):g.lang='zh'
 session['lang']=g.lang
 if request.method=='POST' and request.endpoint!='stripe_webhook' and not hmac.compare_digest(request.form.get('csrf',''),session['csrf']):abort(400)
 if request.endpoint!='static':store.cleanup()

@app.after_request
def headers(response):
 response.headers['X-Content-Type-Options']='nosniff';response.headers['X-Frame-Options']='DENY';response.headers['Referrer-Policy']='no-referrer'
 response.headers['Content-Security-Policy']="default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self' https://challenges.cloudflare.com; frame-src https://challenges.cloudflare.com; connect-src 'self' https://challenges.cloudflare.com; form-action 'self' https://checkout.stripe.com; frame-ancestors 'none'; base-uri 'self'"
 if request.endpoint!='static':response.headers['Cache-Control']='private, no-store'
 if request.path.startswith(('/r/','/payment','/history')):response.headers['X-Robots-Tag']='noindex, nofollow'
 return response

@app.context_processor
def template_context():
 return {'lang':getattr(g,'lang','zh'),'csrf':session.get('csrf'),'hexagrams':HEXAGRAMS,'timezone_labels':TIMEZONE_LABELS,'support_email':SUPPORT_EMAIL,'stripe_test_mode':STRIPE_MODE=='test','turnstile_site_key':os.getenv('TURNSTILE_SITE_KEY',''),'price_aud':f'{AMOUNT/100:.2f}'}

def fetch_private(access):
 with store.connect() as c:row=c.execute('SELECT * FROM ab49_readings WHERE access=? AND expires>?',(access,time.time())).fetchone()
 if not row:abort(404)
 return row

def read_id(rid):
 with store.connect() as c:return c.execute('SELECT * FROM ab49_readings WHERE id=? AND expires>?',(rid,time.time())).fetchone()

def unlocked(row):return row['paid_mode']==STRIPE_MODE

def provider():
 if not AI_KEY or os.getenv('AI_ENABLED','1')!='1':raise BudgetExceeded()
 return OpenAI(api_key=AI_KEY,base_url='https://api.deepseek.com',timeout=75,max_retries=0)

def notify_failure(error):
 if isinstance(error,(Limited,BudgetExceeded)):
  flash(label('操作过于频繁，请稍后再试。','Too many requests. Please try again later.'),'error')
 elif isinstance(error,VerificationFailed):flash(label('请完成人机验证后重试。','Please complete the verification and try again.'),'error')
 else:
  # Never log API response bodies, connection strings, user questions or credentials.
  app.logger.warning('Reading operation failed: category=%s',type(error).__name__)
  flash(label('本次解读未完成，请稍后重试。已确认的付款仍有效。','The reading could not be completed. Please retry later; confirmed payment remains valid.'),'error')

def initial(question,cast):
 with provider() as client:return engine.generate(bounded_client(client,store),question,cast,AI_MODEL)

class InvalidCast(Exception):pass

def parse_cast_form():
 try:
  question=request.form.get('question','').strip()
  if not 2<=len(question)<=500:raise ValueError()
  dt=datetime.fromisoformat(request.form.get('cast_time',''))
  if dt.tzinfo is not None or dt.second or dt.microsecond or not 1900<=dt.year<=2100:raise ValueError()
  words=[request.form.get('word'+str(i),'') for i in range(1,7)]
  zone=request.form.get('timezone','Asia/Shanghai');ZoneInfo(zone);cast=build_cast(words,dt,zone)
  return question,dt,words,zone,cast
 except (ValueError,KeyError,ZoneInfoNotFoundError):raise InvalidCast() from None

@app.route('/',methods=['GET','POST'])
def home():
 form={}
 if request.method=='POST':
  form=request.form.to_dict();trial=None;lock=None;name=None
  try:
   question,dt,words,zone,cast=parse_cast_form()
   request_key=hashlib.sha256(canonical([question,dt.isoformat(),zone,words]).encode()).hexdigest()
   with store.connect() as c:old=c.execute('SELECT access FROM ab49_readings WHERE request_key=? AND owner=? AND expires>?',(request_key,session['owner'],time.time())).fetchone()
   if old:return redirect(url_for('reading_page',access=old['access'],lang=g.lang))
   protect.rate('new');protect.verify('cast')
   name='new:'+protect.digest(session['owner']);lock=store.acquire(name,GENERATION_TTL)
   if not lock:raise Limited()
   try:trial=protect.reserve_trial()
   except QuotaUsed:pass
   stored=initial(question,cast) if trial else {}
   free=engine.render(stored['bundle'],'free') if trial else ''
   rid=secrets.token_hex(24);access=secrets.token_urlsafe(32);now=time.time()
   with store.connect() as c:c.execute('''INSERT INTO ab49_readings(id,access,owner,request_key,question,cast_json,bundle_json,free_zh,version,created,expires)
     VALUES(?,?,?,?,?,?,?,?,?,?,?)''',(rid,access,session['owner'],request_key,question,canonical(cast),canonical(stored),free,VERSION,now,now+RETENTION_DAYS*86400))
   protect.finish_trial(trial,True);trial=None
   if g.lang=='en' and free:
    try:generate_text(fetch_private(access),'free','en',already_locked=False)
    except Exception as error:notify_failure(error)
   return redirect(url_for('reading_page',access=access,lang=g.lang))
  except InvalidCast:flash(label('请检查问题、六次结果和起卦时间。','Please check the question, six throws and casting time.'),'error')
  except Exception as error:notify_failure(error)
  finally:
   protect.finish_trial(trial,False)
   if name:store.release(name,lock)
 return render_template('home.html',form=form)

@app.get('/r/<access>')
def reading_page(access):
 row=fetch_private(access)
 return render_template('reading.html',reading=row,cast=json.loads(row['cast_json']),free_text=row['free_'+g.lang],full=row['paid_'+g.lang] if unlocked(row) else '',unlocked=unlocked(row),checkout_enabled=checkout_ready(),expiry=datetime.fromtimestamp(row['expires']).strftime('%Y-%m-%d UTC'))

def generate_text(row,tier,lang,already_locked=False):
 field=tier+'_'+lang
 if row[field]:return row[field]
 if tier=='paid' and not unlocked(row):abort(403)
 if tier=='free' and not row['free_zh']:return ''  # No quota means no free model call or translation.
 name='reading:'+row['id'];lock=store.acquire(name,GENERATION_TTL)
 if not lock:raise Limited()
 try:
  row=read_id(row['id'])
  if not row:abort(404)
  if row[field]:return row[field]
  if tier=='paid' and not unlocked(row):abort(403)
  cast=json.loads(row['cast_json']);stored=json.loads(row['bundle_json'])
  # English is a translation of the frozen Chinese text, never an independent reading.
  if lang=='en':
   original=row[tier+'_zh']
   if not original:raise ValueError('Chinese reading not generated')
   parts=stored['bundle'][tier]
   with provider() as client:translated=engine.translate(bounded_client(client,store),parts,tier,cast,TRANSLATION_MODEL)
   text=engine.render(stored['bundle'],tier,'en',translated['parts'])
  else:
   if tier!='paid':return row['free_zh']
   # A quota-exhausted cast gets its decision core only AFTER verified payment.
   if not stored:
    stored=initial(row['question'],cast)
    with store.connect() as c:c.execute('UPDATE ab49_readings SET bundle_json=? WHERE id=?',(canonical(stored),row['id']))
   from external_references import search
   with provider() as client:
    parts=engine.generate_paid(bounded_client(client,store),row['question'],cast,AI_MODEL,stored['bundle'],lambda topics:search(topics,store=store),stored.get('external_reference'),stored.get('reference_snapshot'))
   stored['bundle']['paid']=parts;text=engine.render(stored['bundle'],'paid')
  # Stored output remains valid across future deployments; no UI-file cache invalidation.
  with store.connect() as c:
   latest=c.execute('SELECT paid_mode FROM ab49_readings WHERE id=? AND expires>?',(row['id'],time.time())).fetchone()
   if not latest or (tier=='paid' and latest['paid_mode']!=STRIPE_MODE):raise ValueError('Paid access no longer available')
   c.execute(f'UPDATE ab49_readings SET {field}=?,bundle_json=? WHERE id=?',(text,canonical(stored),row['id']))
  return text
 finally:store.release(name,lock)

@app.post('/r/<access>/generate')
def generate_reading(access):
 row=fetch_private(access);tier='free' if request.form.get('tier')=='free' else 'paid'
 if tier=='paid' and not unlocked(row):abort(403)
 if row[tier+'_'+g.lang]:return redirect(url_for('reading_page',access=access,lang=g.lang))
 try:
  protect.rate('generate');protect.verify('generate')
  if tier=='paid':generate_text(row,'paid','zh');row=fetch_private(access)
  if g.lang=='en':generate_text(row,tier,'en')
 except Exception as error:notify_failure(error)
 return redirect(url_for('reading_page',access=access,lang=g.lang))

@app.get('/history')
def history():
 with store.connect() as c:rows=c.execute('SELECT access,question,created FROM ab49_readings WHERE owner=? AND expires>? ORDER BY created DESC LIMIT 50',(session['owner'],time.time())).fetchall()
 return render_template('history.html',rows=rows)

@app.post('/r/<access>/checkout')
def checkout(access):
 row=fetch_private(access)
 if unlocked(row):return redirect(url_for('reading_page',access=access,lang=g.lang))
 lock=None;name='checkout:'+row['id']
 try:
  protect.rate('checkout');protect.verify('checkout')
  if not checkout_ready() or not delivery_capacity(row,g.lang):raise Limited()
  lock=store.acquire(name,120)
  if not lock:raise Limited()
  with store.connect() as c:order=c.execute('SELECT * FROM ab49_orders WHERE nonce=?',(row['checkout_nonce'],)).fetchone() if row['checkout_nonce'] else None
  if order and order['session_id']:
   existing=stripe_client.v1.checkout.sessions.retrieve(order['session_id']);d=asdict(existing)
   if d.get('status')=='open':return redirect(d['url'],303)
   if d.get('payment_status')=='paid':
    fulfill(d,row['id']);return redirect(url_for('reading_page',access=access,lang=g.lang))
   if d.get('status')!='expired':raise Limited()
   order=None
  if order and not order['session_id'] and order['created']<time.time()-23*3600:raise Limited()
  # Persist nonce BEFORE Stripe: retries after a network timeout reuse its idempotency key.
  if not order:
   nonce=secrets.token_hex(24)
   with store.connect() as c:
    c.execute('INSERT INTO ab49_orders(nonce,reading_id,mode,amount,currency,status,created) VALUES(?,?,?,?,?,?,?)',(nonce,row['id'],STRIPE_MODE,AMOUNT,'aud','pending',time.time()))
    c.execute('UPDATE ab49_readings SET checkout_nonce=? WHERE id=?',(nonce,row['id']))
   order={'nonce':nonce,'reading_id':row['id'],'mode':STRIPE_MODE,'amount':AMOUNT,'currency':'aud'}
  params={'mode':'payment','line_items':[{'price_data':{'currency':'aud','unit_amount':order['amount'],'product_data':{'name':'Your Answer Book - one full reading'}},'quantity':1}],
   'client_reference_id':row['id'],'metadata':{'reading_id':row['id'],'order_nonce':order['nonce']},
   'success_url':PUBLIC_URL+url_for('payment_success',rid=row['id'])+'?session_id={CHECKOUT_SESSION_ID}',
   'cancel_url':PUBLIC_URL+url_for('reading_page',access=access),
   'integration_identifier':'answerbook_'+''.join(chr(97+int(x,16)) for x in order['nonce'][:8])}
  result=asdict(stripe_client.v1.checkout.sessions.create(params,options={'idempotency_key':order['nonce']}))
  if result.get('livemode') is not (STRIPE_MODE=='live') or not str(result.get('id','')).startswith('cs_') or urlparse(result.get('url','')).hostname!='checkout.stripe.com':raise ValueError('Invalid checkout response')
  with store.connect() as c:c.execute('UPDATE ab49_orders SET session_id=? WHERE nonce=?',(result['id'],order['nonce']))
  return redirect(result['url'],303)
 except Exception as error:notify_failure(error)
 finally:store.release(name,lock)
 return redirect(url_for('reading_page',access=access,lang=g.lang))

def asdict(obj):return obj.to_dict() if hasattr(obj,'to_dict') else dict(obj)

def fulfill(d,expected=None):
 meta=d.get('metadata') or {};rid=meta.get('reading_id');nonce=meta.get('order_nonce');sid=d.get('id')
 if d.get('livemode') is not (STRIPE_MODE=='live') or d.get('payment_status')!='paid' or d.get('mode')!='payment' or not rid or not nonce or not sid or (expected and rid!=expected):return False
 now=time.time()
 with store.connect() as c:
  order=c.execute('SELECT * FROM ab49_orders WHERE nonce=?',(nonce,)).fetchone()
  if not order or order['reading_id']!=rid or order['mode']!=STRIPE_MODE or order['amount']!=d.get('amount_total') or order['currency']!=d.get('currency') or (order['session_id'] and order['session_id']!=sid):return False
  if order['status'] in ('refunded','disputed'):return False
  intent=d.get('payment_intent')
  if intent and c.execute('SELECT 1 FROM ab49_reversals WHERE intent=?',(intent,)).fetchone():return False
  first=order['status']!='paid'
  c.execute("UPDATE ab49_orders SET session_id=?,status='paid',payment_intent=? WHERE nonce=?",(sid,intent,nonce))
  if first:c.execute('UPDATE ab49_readings SET paid_mode=?,expires=? WHERE id=?',(STRIPE_MODE,now+RETENTION_DAYS*86400,rid))
 return True

@app.get('/payment/success/<rid>')
def payment_success(rid):
 if not stripe_client:abort(503)
 sid=request.args.get('session_id','')
 if not sid.startswith('cs_') or len(sid)>255:abort(400)
 try:
  # Rate limited to prevent repeated provider lookups; viewing saved results needs no lookup.
  protect.rate('payment-check')
  d=asdict(stripe_client.v1.checkout.sessions.retrieve(sid))
  if not fulfill(d,rid):abort(403)
 except Limited:return render_template('error.html',status=429),429
 except stripe.StripeError:abort(503)
 row=read_id(rid)
 if not row:abort(404)
 flash(label('付款已确认，请点击生成完整解读。','Payment confirmed. Select Generate full reading.'))
 return redirect(url_for('reading_page',access=row['access'],lang=g.lang))

@app.post('/stripe/webhook')
def stripe_webhook():
 secret=os.getenv(PREFIX+'WEBHOOK_SECRET','')
 if not secret:return jsonify(error='not configured'),503
 try:event=asdict(stripe.Webhook.construct_event(request.get_data(),request.headers.get('Stripe-Signature',''),secret))
 except (ValueError,stripe.SignatureVerificationError):return jsonify(error='invalid signature'),400
 if event.get('livemode') is not (STRIPE_MODE=='live'):return jsonify(error='wrong mode'),400
 obj=event.get('data',{}).get('object',{});kind=event.get('type')
 if kind in ('checkout.session.completed','checkout.session.async_payment_succeeded') and obj.get('payment_status')=='paid':
  if not fulfill(obj):
   meta=obj.get('metadata') or {}
   if not meta.get('order_nonce') or not meta.get('reading_id'):return jsonify(received=True,ignored=True)
   with store.connect() as c:
    terminal=c.execute('SELECT status FROM ab49_orders WHERE nonce=?',(meta['order_nonce'],)).fetchone()
    reversed_intent=c.execute('SELECT 1 FROM ab49_reversals WHERE intent=?',(obj.get('payment_intent'),)).fetchone()
   if reversed_intent or (terminal and terminal['status'] in ('refunded','disputed')):return jsonify(received=True,ignored=True)
   return jsonify(error='order not fulfilled'),503
 if kind in ('charge.refunded','charge.dispute.created'):
  intent=obj.get('payment_intent')
  if intent:
   with store.connect() as c:
    c.execute('INSERT INTO ab49_reversals VALUES(?,?) ON CONFLICT(intent) DO NOTHING',(intent,time.time()))
    orders=c.execute('SELECT reading_id FROM ab49_orders WHERE payment_intent=? AND mode=?',(intent,STRIPE_MODE)).fetchall()
    c.execute('UPDATE ab49_orders SET status=? WHERE payment_intent=? AND mode=?',('refunded' if kind=='charge.refunded' else 'disputed',intent,STRIPE_MODE))
    for order in orders:c.execute("UPDATE ab49_readings SET paid_mode='' WHERE id=?",(order['reading_id'],))
 return jsonify(received=True)

@app.get('/r/<access>/download.pdf')
def download(access):
 row=fetch_private(access)
 from pdf_export import reading_pdf
 return Response(reading_pdf(dict(row),g.lang,unlocked(row)),mimetype='application/pdf',headers={'Content-Disposition':'attachment; filename="your-answer-book.pdf"'})

@app.get('/deck')
def deck():return render_template('deck.html')
@app.get('/deck/<int:number>')
def card_page(number):
 if not 1<=number<=64:abort(404)
 return render_template('card.html',card=HEXAGRAMS[number-1])
@app.get('/demo')
def demo():return render_template('demo.html',cast=build_cast(['2','1','2','1','2','1'],datetime(2026,10,4,16,0),'Asia/Shanghai'))
@app.get('/policy')
def policy():return render_template('policy.html')
@app.get('/healthz')
def health():
 with store.connect() as c:c.execute('SELECT 1')
 return jsonify(ok=True,version=VERSION,database='postgresql' if store.durable else 'local_sqlite_development_only',storage_durable=store.durable,reading_retention_days=RETENTION_DAYS,accounts_enabled=False,generation_mode='paid_deferred',payment_mode=STRIPE_MODE,checkout_enabled=checkout_ready(),currency='aud',price_cents=AMOUNT,ai_model=AI_MODEL,case_archive=len(engine.CASES),case_retrieval=sum(bool(c.get('retrieval_eligible')) for c in engine.CASES),rules_available=len(engine.RULES),reading_pipeline='facts_relevant_rules_matched_cases',free_browser_daily=1,free_ip_daily=2,quota_timezone='UTC',turnstile_configured=bool(os.getenv('TURNSTILE_SITE_KEY') and os.getenv('TURNSTILE_SECRET_KEY')),private_test_enabled=bool(os.getenv('SITE_ACCESS_PASSWORD')),free_web_search=False,paid_web_search=os.getenv('WEB_SEARCH_ENABLED','1')=='1',output_limits={'zh_free':50,'zh_paid':300,'en_free':60,'en_paid':350})

for status in (400,403,404,413,429,500,503):
 app.register_error_handler(status,lambda e:(render_template('error.html',status=e.code),e.code))

if os.getenv('TRUST_PROXY','0')=='1':
 from werkzeug.middleware.proxy_fix import ProxyFix
 app.wsgi_app=ProxyFix(app.wsgi_app,x_for=1,x_proto=1)
if __name__=='__main__':app.run(host='0.0.0.0',port=int(os.getenv('PORT','5000')),debug=False)
