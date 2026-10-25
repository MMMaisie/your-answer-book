"""Verified accounts, permanent trial claims and idempotent credit wallet."""
import os,re,secrets,hashlib,hmac,time,smtplib,ssl
from datetime import datetime,timezone
from email.message import EmailMessage
from flask import Blueprint,request,session,g,render_template,redirect,url_for,abort,flash
from werkzeug.security import generate_password_hash,check_password_hash
from storage_checks import mounted_database
from security_controls import provider_capacity

SCHEMA='''
CREATE TABLE IF NOT EXISTS accounts(id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,verified INTEGER NOT NULL DEFAULT 0,session_version INTEGER NOT NULL DEFAULT 0,created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS account_tokens(hash TEXT PRIMARY KEY,account_id TEXT NOT NULL,purpose TEXT NOT NULL,expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS credit_ledger(id TEXT PRIMARY KEY,account_id TEXT NOT NULL,delta INTEGER NOT NULL,reason TEXT NOT NULL,created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS credit_holds(id TEXT PRIMARY KEY,account_id TEXT NOT NULL,seed_key TEXT,status TEXT NOT NULL,created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS credit_entitlements(seed_key TEXT NOT NULL,account_id TEXT NOT NULL,hold_id TEXT UNIQUE NOT NULL,mode TEXT NOT NULL,PRIMARY KEY(seed_key,mode));
CREATE TABLE IF NOT EXISTS trial_claims(subject TEXT PRIMARY KEY,reservation_id TEXT NOT NULL,status TEXT NOT NULL,created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS wallet_orders(session_id TEXT PRIMARY KEY,account_id TEXT NOT NULL,sku TEXT NOT NULL,amount INTEGER NOT NULL,credits INTEGER NOT NULL,mode TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',payment_intent TEXT,revoked INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS wallet_reversals(payment_intent TEXT PRIMARY KEY,amount_refunded INTEGER NOT NULL DEFAULT 0,disputed INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS security_rates(bucket TEXT NOT NULL,window INTEGER NOT NULL,count INTEGER NOT NULL,PRIMARY KEY(bucket,window));
'''
PRODUCTS={'single':(199,1),'five':(599,5),'ten':(999,10)}

class AccessError(Exception):pass

class Membership:
 def __init__(self,site):
  self.s=site
  with site.connect() as c:c.executescript(SCHEMA)
  bp=Blueprint('account',__name__);self.bp=bp;self.routes();site.app.register_blueprint(bp)
 def label(self,zh,en):return zh if getattr(g,'lang','zh')=='zh' else en
 def ip(self):return request.remote_addr or 'unknown'
 def digest(self,text):return hmac.new(self.s.app.secret_key.encode(),text.encode(),hashlib.sha256).hexdigest()
 def rate(self,action,limit=10,seconds=3600):
  bucket=action+':'+self.digest(self.ip());window=int(time.time())//seconds
  with self.s.connect() as c:
   c.execute('BEGIN IMMEDIATE');r=c.execute('SELECT count FROM security_rates WHERE bucket=? AND window=?',(bucket,window)).fetchone()
   if r and r[0]>=limit:raise AccessError(self.label('请求过于频繁，请稍后再试。','Too many attempts. Please try later.'))
   c.execute('INSERT INTO security_rates VALUES(?,?,1) ON CONFLICT(bucket,window) DO UPDATE SET count=count+1',(bucket,window))
 def user(self):
  uid=session.get('account_id')
  if not uid:return None
  with self.s.connect() as c:u=c.execute('SELECT * FROM accounts WHERE id=?',(uid,)).fetchone()
  if not u or session.get('account_version')!=u['session_version']:return None
  return u
 def balance(self,uid):
  with self.s.connect() as c:
   total=c.execute('SELECT COALESCE(SUM(delta),0) FROM credit_ledger WHERE account_id=? AND reason LIKE ?',(uid,self.s.STRIPE_MODE+':%')).fetchone()[0]
   held=c.execute("SELECT COUNT(*) FROM credit_holds WHERE account_id=? AND status='held' AND id LIKE ?",(uid,self.s.STRIPE_MODE+':%')).fetchone()[0]
  return total-held
 def require_user(self):
  u=self.user()
  if not u or not u['verified']:raise AccessError(self.label('请先登录并验证邮箱。','Sign in with a verified email first.'))
  return u
 def captcha(self):
  if os.getenv('SITE_ACCESS_PASSWORD'):return
  secret=os.getenv('TURNSTILE_SECRET_KEY','')
  if not secret:raise AccessError(self.label('公开体验尚未配置人机验证，请联系管理员。','Public access is not configured yet.'))
  import urllib.request,urllib.parse,json
  payload=urllib.parse.urlencode({'secret':secret,'response':request.form.get('cf-turnstile-response',''),'remoteip':self.ip()}).encode()
  try:result=json.loads(urllib.request.urlopen(urllib.request.Request('https://challenges.cloudflare.com/turnstile/v0/siteverify',data=payload),timeout=8).read())
  except Exception:raise AccessError(self.label('人机验证暂不可用。','Verification unavailable.')) from None
  host=request.host.split(':')[0]
  if not result.get('success') or result.get('hostname')!=host:raise AccessError(self.label('请完成人机验证。','Complete the verification.'))
 def reserve_trial(self,verified=False):
  if not verified:self.captcha()
  u=self.user();now=time.time();rid=secrets.token_hex(24)
  device='device:'+session['owner']
  subjects=['account:'+u['id'],device] if u and u['verified'] else ['ip:'+self.digest(self.ip()),device]
  if u and not u['verified']:raise AccessError('请先验证邮箱。 / Verify your email first.')
  with self.s.connect() as c:
   c.execute('BEGIN IMMEDIATE')
   # Release interrupted attempts only; successful claims never expire.
   c.execute("DELETE FROM trial_claims WHERE status='held' AND created<?",(now-1800,))
   for key in subjects:
    if c.execute('SELECT 1 FROM trial_claims WHERE subject=?',(key,)).fetchone():raise AccessError('免费体验已使用，请登录后购买次数。 / Your free trial is used. Sign in to buy credits.')
   for key in subjects:c.execute('INSERT INTO trial_claims VALUES(?,?,?,?)',(key,rid,'held',now))
  return rid
 def finish_trial(self,rid,success):
  if not rid:return
  with self.s.connect() as c:
   if success:c.execute("UPDATE trial_claims SET status='used' WHERE reservation_id=?",(rid,))
   else:c.execute("DELETE FROM trial_claims WHERE reservation_id=? AND status='held'",(rid,))
 def reserve_credit(self,seed=None,verified=False):
  u=self.require_user()
  if not verified:self.captcha()
  rid=self.s.STRIPE_MODE+':'+secrets.token_hex(24)
  with self.s.connect() as c:
   c.execute('BEGIN IMMEDIATE')
   if seed:
    ent=c.execute('SELECT account_id FROM credit_entitlements WHERE seed_key=? AND mode=?',(seed,self.s.STRIPE_MODE)).fetchone()
    if ent:
     if ent[0]!=u['id']:raise AccessError('This reading belongs to another account.')
     return None
   # A hold is not auto-refunded by wall clock: slow requests must not create free delivery.
   total=c.execute('SELECT COALESCE(SUM(delta),0) FROM credit_ledger WHERE account_id=? AND reason LIKE ?',(u['id'],self.s.STRIPE_MODE+':%')).fetchone()[0]
   held=c.execute("SELECT COUNT(*) FROM credit_holds WHERE account_id=? AND status='held' AND id LIKE ?",(u['id'],self.s.STRIPE_MODE+':%')).fetchone()[0]
   if total-held<1:raise AccessError('次数余额不足，请购买次数包。 / Not enough credits. Purchase a pack first.')
   if seed and c.execute("SELECT 1 FROM credit_holds WHERE seed_key=? AND status='held'",(seed,)).fetchone():raise AccessError('完整解读正在生成。 / A reading is already being generated.')
   c.execute('INSERT INTO credit_holds VALUES(?,?,?,?,?)',(rid,u['id'],seed,'held',time.time()))
  return rid
 def bind_hold(self,rid,seed):
  with self.s.connect() as c:c.execute('UPDATE credit_holds SET seed_key=? WHERE id=? AND status=?',(seed,rid,'held'))
 def finish_credit(self,rid,success):
  if not rid:return
  with self.s.connect() as c:
   c.execute('BEGIN IMMEDIATE');h=c.execute('SELECT * FROM credit_holds WHERE id=?',(rid,)).fetchone()
   if not h or h['status']!='held':return
   if success:
    if not h['seed_key']:raise ValueError('credit hold has no reading')
    c.execute('INSERT INTO credit_entitlements VALUES(?,?,?,?)',(h['seed_key'],h['account_id'],rid,self.s.STRIPE_MODE))
    c.execute('INSERT INTO credit_ledger VALUES(?,?,?,?,?)',('debit:'+rid,h['account_id'],-1,self.s.STRIPE_MODE+':reading',time.time()))
   c.execute('UPDATE credit_holds SET status=? WHERE id=?',('spent' if success else 'released',rid))
 def held(self,seed):
  u=self.user()
  if not u:return False
  with self.s.connect() as c:return c.execute("SELECT 1 FROM credit_holds WHERE seed_key=? AND account_id=? AND status='held'",(seed,u['id'])).fetchone() is not None
 def entitled(self,seed):
  u=self.user()
  with self.s.connect() as c:r=c.execute('SELECT account_id FROM credit_entitlements WHERE seed_key=? AND mode=?',(seed,self.s.STRIPE_MODE)).fetchone()
  return bool(r and u and r[0]==u['id'])
 def token(self,uid,purpose):
  raw=secrets.token_urlsafe(32);digest=hashlib.sha256(raw.encode()).hexdigest()
  with self.s.connect() as c:
   c.execute('DELETE FROM account_tokens WHERE account_id=? AND purpose=?',(uid,purpose))
   c.execute('INSERT INTO account_tokens VALUES(?,?,?,?)',(digest,uid,purpose,time.time()+(3600 if purpose=='reset' else 86400)))
  return raw
 def mail(self,email,token,purpose):
  host=os.getenv('SMTP_HOST','');sender=os.getenv('MAIL_FROM','');base=self.s.PUBLIC_URL
  if not host or not sender or not base:raise AccessError('邮件服务尚未配置。 / Email service is not configured.')
  message=EmailMessage();message['From']=sender;message['To']=email;message['Subject']='Your Answer Book — '+('Verify your email' if purpose=='verify' else 'Reset password')
  message.set_content(base+url_for('account.token_page',purpose=purpose)+'#token='+token+'\n\nIgnore this email if you did not request it.')
  port=int(os.getenv('SMTP_PORT','587'));ctx=ssl.create_default_context()
  try:
   if port==465:s=smtplib.SMTP_SSL(host,port,timeout=10,context=ctx)
   else:s=smtplib.SMTP(host,port,timeout=10);s.starttls(context=ctx)
   with s:
    if os.getenv('SMTP_USERNAME'):s.login(os.environ['SMTP_USERNAME'],os.environ.get('SMTP_PASSWORD',''))
    s.send_message(message)
  except Exception:raise AccessError('邮件发送失败，请稍后重新发送。 / Email delivery failed. Try again later.') from None
 def login(self,u):
  owner=session.get('owner');csrf=session.get('csrf');lang=session.get('lang','zh');session.clear();session.update(account_id=u['id'],account_version=u['session_version'],owner='acct:'+u['id'],csrf=secrets.token_urlsafe(24),lang=lang)
  if owner and not owner.startswith('acct:'):
   with self.s.connect() as c:
    c.execute('UPDATE readings SET owner_id=? WHERE owner_id=?',('acct:'+u['id'],owner))
    used=c.execute("SELECT 1 FROM trial_claims WHERE subject=? AND status='used'",('device:'+owner,)).fetchone()
    if used:c.execute('INSERT OR IGNORE INTO trial_claims VALUES(?,?,?,?)',('account:'+u['id'],'inherited','used',time.time()))
 def routes(self):
  bp=self.bp
  @bp.route('/account/register',methods=['GET','POST'])
  def register():
   if request.method=='POST':
    try:
     self.rate('register',3,86400);self.captcha();email=request.form.get('email','').strip().lower();password=request.form.get('password','')
     if not re.fullmatch(r'[^\s@]{1,64}@[^\s@.]+(?:\.[^\s@.]+)+',email) or len(email)>254 or not 12<=len(password)<=256:raise AccessError('请输入有效邮箱，密码12–256字符。 / Use a valid email and a 12–256 character password.')
     with self.s.connect() as c:
      existing=c.execute('SELECT * FROM accounts WHERE email=?',(email,)).fetchone()
      if not existing:
       uid=secrets.token_hex(24);c.execute('INSERT INTO accounts VALUES(?,?,?,0,0,?)',(uid,email,generate_password_hash(password),time.time()))
      else:uid=existing['id']
     if os.getenv('ALLOW_PRIVATE_TEST_ACCOUNTS')=='1' and os.getenv('SITE_ACCESS_PASSWORD') and self.s.STRIPE_TEST_MODE:
      with self.s.connect() as c:c.execute('UPDATE accounts SET verified=1 WHERE id=?',(uid,))
      flash('私密测试账号已建立，请登录。 / Private test account created. Sign in.')
      return redirect(url_for('account.signin'))
     if not existing or not existing['verified']:self.mail(email,self.token(uid,'verify'),'verify')
     flash('请查收验证邮件；已有账号请登录。 / Check your verification email, or sign in if already registered.')
     return redirect(url_for('account.signin'))
    except AccessError as e:flash(str(e),'error')
   return render_template('account.html',mode='register')
  @bp.route('/account/login',methods=['GET','POST'])
  def signin():
   if request.method=='POST':
    try:
     self.rate('login',10,900);self.captcha();email=request.form.get('email','').strip().lower();password=request.form.get('password','')
     with self.s.connect() as c:u=c.execute('SELECT * FROM accounts WHERE email=?',(email,)).fetchone()
     if len(password)>256 or not u or not check_password_hash(u['password_hash'],password):raise AccessError('邮箱或密码不正确。 / Invalid email or password.')
     if not u['verified']:raise AccessError('请先验证邮箱，可使用“重新发送”。 / Verify your email first; use resend if needed.')
     self.login(u);return redirect(url_for('account.wallet'))
    except AccessError as e:flash(str(e),'error')
   return render_template('account.html',mode='login')
  @bp.post('/account/logout')
  def logout():session.clear();return redirect(url_for('home'))
  @bp.route('/account/help',methods=['GET','POST'])
  def help_email():
   if request.method=='POST':
    try:
     self.rate('email',3,3600);self.captcha();email=request.form.get('email','').strip().lower();purpose='reset' if request.form.get('purpose')=='reset' else 'verify'
     with self.s.connect() as c:u=c.execute('SELECT * FROM accounts WHERE email=?',(email,)).fetchone()
     if u and (purpose=='reset' or not u['verified']):self.mail(email,self.token(u['id'],purpose),purpose)
     flash('如果账号适用，邮件已发送。 / If eligible, an email has been sent.')
    except AccessError as e:flash(str(e),'error')
   return render_template('account.html',mode='help')
  @bp.route('/account/token/<purpose>',methods=['GET','POST'])
  def token_page(purpose):
   if purpose not in ('verify','reset'):abort(404)
   if request.method=='POST':
    try:
     self.rate('token',10,3600);raw=request.form.get('token','');digest=hashlib.sha256(raw.encode()).hexdigest()
     with self.s.connect() as c:
      c.execute('BEGIN IMMEDIATE');t=c.execute('SELECT * FROM account_tokens WHERE hash=? AND purpose=? AND expires>?',(digest,purpose,time.time())).fetchone()
      if not t:raise AccessError('链接无效或已过期。 / Link invalid or expired.')
      if purpose=='reset':
       password=request.form.get('password','')
       if not 12<=len(password)<=256:raise AccessError('密码12–256字符。 / Password must be 12–256 characters.')
       c.execute('UPDATE accounts SET password_hash=?,session_version=session_version+1 WHERE id=?',(generate_password_hash(password),t['account_id']))
      else:c.execute('UPDATE accounts SET verified=1 WHERE id=?',(t['account_id'],))
      c.execute('DELETE FROM account_tokens WHERE hash=?',(digest,))
     flash('已完成，请登录。 / Done. Please sign in.');return redirect(url_for('account.signin'))
    except AccessError as e:flash(str(e),'error')
   return render_template('account.html',mode='token',purpose=purpose)
  @bp.get('/account/wallet')
  def wallet():
   self.recover_holds()
   u=self.user()
   if not u:return redirect(url_for('account.signin'))
   with self.s.connect() as c:history=c.execute('SELECT delta,reason,created FROM credit_ledger WHERE account_id=? ORDER BY created DESC LIMIT 30',(u['id'],)).fetchall()
   return render_template('wallet.html',balance=self.balance(u['id']),products=PRODUCTS,ledger=history,wallet_ready=self.ready())
  @bp.post('/account/buy/<sku>')
  def buy(sku):
   try:
    u=self.require_user();self.rate('checkout',10,3600)
    if sku not in PRODUCTS:abort(404)
    if not self.ready():raise AccessError('支付暂未开放。 / Checkout is unavailable.')
    if not self.s.STRIPE_TEST_MODE:self.check_provider_balance()
    amount,credits=PRODUCTS[sku];nonce=secrets.token_hex(16)
    params={'mode':'payment','line_items':[{'price_data':{'currency':'aud','unit_amount':amount,'product_data':{'name':f'Your Answer Book — {credits} reading credit(s)'}},'quantity':1}], 'metadata':{'wallet_account_id':u['id'],'sku':sku,'order_nonce':nonce},'success_url':self.s.PUBLIC_URL+url_for('account.return_payment')+'?session_id={CHECKOUT_SESSION_ID}','cancel_url':self.s.PUBLIC_URL+url_for('account.wallet'),'integration_identifier':'answerbook_'+''.join(secrets.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(8))}
    checkout=self.s.stripe_client.v1.checkout.sessions.create(params,options={'idempotency_key':nonce})
    if checkout.livemode is not (not self.s.STRIPE_TEST_MODE):raise AccessError('Payment mode mismatch.')
    with self.s.connect() as c:c.execute('INSERT INTO wallet_orders(session_id,account_id,sku,amount,credits,mode,status) VALUES(?,?,?,?,?,?,?)',(checkout.id,u['id'],sku,amount,credits,self.s.STRIPE_MODE,'pending'))
    return redirect(checkout.url,code=303)
   except AccessError as e:flash(str(e),'error')
   except Exception:self.s.app.logger.warning('Wallet checkout failed');flash('暂未发起付款，请稍后重试。 / Checkout failed. Please try later.','error')
   return redirect(url_for('account.wallet'))
  @bp.get('/account/payment-return')
  def return_payment():
   u=self.user()
   if not u:return redirect(url_for('account.signin'))
   sid=request.args.get('session_id','')
   if not sid.startswith('cs_'):abort(400)
   try:
    obj=self.s.stripe_client.v1.checkout.sessions.retrieve(sid);d=obj.to_dict() if hasattr(obj,'to_dict') else dict(obj)
    if (d.get('metadata') or {}).get('wallet_account_id')!=u['id']:abort(403)
    if not self.fulfill(d):raise AccessError('付款尚未确认。稍后从余额页核对。 / Payment not confirmed yet. Check your balance later.')
    flash('付款已确认，次数已到账。 / Payment confirmed. Credits added.')
   except AccessError as e:flash(str(e),'error')
   except self.s.stripe.StripeError:flash('暂时无法核对付款，请稍后重试。 / Could not check payment yet.','error')
   return redirect(url_for('account.wallet'))
 def ready(self):
  return bool(self.s.AI_KEY and provider_capacity(self.s.connect) and self.s.stripe_client and self.s.PUBLIC_URL and self.s.SUPPORT_EMAIL and os.getenv(self.s.STRIPE_ENV_PREFIX+'WEBHOOK_SECRET') and (self.s.STRIPE_TEST_MODE or (self.s.STORAGE_DURABLE and mounted_database(self.s.app.config['DB_PATH']))))
 def fulfill(self,d):
  if d.get('livemode') is not (not self.s.STRIPE_TEST_MODE) or (not self.s.STRIPE_TEST_MODE and not (self.s.STORAGE_DURABLE and mounted_database(self.s.app.config['DB_PATH']))):return False
  if d.get('payment_status')!='paid' or d.get('mode')!='payment' or d.get('currency')!='aud':return False
  sid=d.get('id');meta=d.get('metadata') or {}
  with self.s.connect() as c:
   c.execute('BEGIN IMMEDIATE');order=c.execute('SELECT * FROM wallet_orders WHERE session_id=?',(sid,)).fetchone()
   if not order or order['mode']!=self.s.STRIPE_MODE or order['account_id']!=meta.get('wallet_account_id') or order['sku']!=meta.get('sku') or order['amount']!=d.get('amount_total'):return False
   c.execute('INSERT OR IGNORE INTO credit_ledger VALUES(?,?,?,?,?)',('stripe:'+sid,order['account_id'],order['credits'],self.s.STRIPE_MODE+':purchase',time.time()))
   intent=d.get('payment_intent')
   c.execute("UPDATE wallet_orders SET status='paid',payment_intent=? WHERE session_id=?",(intent,sid))
   reversal=c.execute('SELECT * FROM wallet_reversals WHERE payment_intent=?',(intent,)).fetchone()
   if reversal:self._reverse_in_transaction(c,order,reversal['amount_refunded'],bool(reversal['disputed']))
  return True

 def check_provider_balance(self):
  import urllib.request,json
  try:
   request_obj=urllib.request.Request('https://api.deepseek.com/user/balance',headers={'Authorization':'Bearer '+self.s.AI_KEY})
   result=json.loads(urllib.request.urlopen(request_obj,timeout=8).read())
  except Exception:raise AccessError('暂时无法确认AI服务状态，未发起付款。 / Cannot verify AI availability; checkout was not started.') from None
  if result.get('is_available') is not True:raise AccessError('AI服务余额不足，暂停新增付款。 / AI balance is insufficient; new purchases are paused.')
 def _reverse_in_transaction(self,c,o,refunded,dispute):
  import math
  amount=o['amount'] if dispute else min(o['amount'],max(0,int(refunded)))
  units=min(o['credits'],math.ceil(o['credits']*amount/o['amount']))
  difference=units-o['revoked']
  if difference>0:
   c.execute('INSERT OR IGNORE INTO credit_ledger VALUES(?,?,?,?,?)',('reversal:'+o['session_id']+':'+str(units),o['account_id'],-difference,self.s.STRIPE_MODE+':reversal',time.time()))
   c.execute('UPDATE wallet_orders SET revoked=? WHERE session_id=?',(units,o['session_id']))
 def reverse_payment(self,obj,dispute=False):
  intent=obj.get('payment_intent')
  if not intent:return False
  amount=max(0,int(obj.get('amount_refunded',0)))
  with self.s.connect() as c:
   c.execute('BEGIN IMMEDIATE')
   c.execute('INSERT INTO wallet_reversals VALUES(?,?,?) ON CONFLICT(payment_intent) DO UPDATE SET amount_refunded=MAX(amount_refunded,excluded.amount_refunded),disputed=MAX(disputed,excluded.disputed)',(intent,amount,int(dispute)))
   o=c.execute('SELECT * FROM wallet_orders WHERE payment_intent=? AND mode=?',(intent,self.s.STRIPE_MODE)).fetchone()
   if o:self._reverse_in_transaction(c,o,amount,dispute)
  return True
 def recover_holds(self):
  # Run on startup/wallet visits. Never recover a lock that may still be active.
  with self.s.connect() as c:holds=c.execute("SELECT * FROM credit_holds WHERE status='held' AND created<?",(time.time()-max(1800,self.s.GENERATION_LOCK_TTL*2),)).fetchall()
  for h in holds:
   with self.s.connect() as c:
    active=c.execute('SELECT 1 FROM generation_locks WHERE seed_key IN (?,?) AND started_at>?',((h['seed_key'] or '')+':paid',(h['seed_key'] or '')+':free',time.time()-self.s.GENERATION_LOCK_TTL)).fetchone()
    r=c.execute('SELECT paid_text,paid_version FROM readings WHERE seed_key=?',(h['seed_key'],)).fetchone()
   if not active:
    # Historical mode remains bound to its reservation; never recover test credits as live.
    if h['id'].startswith(self.s.STRIPE_MODE+':'):self.finish_credit(h['id'],bool(r and r['paid_text'] and r['paid_version']==self.s.PROMPT_VERSION))
