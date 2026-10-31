"""Fail-closed human verification, daily trial claims and conservative spend reservations."""
import hashlib,hmac,ipaddress,json,math,os,secrets,time
from datetime import datetime,timezone
from types import SimpleNamespace
from urllib.parse import urlencode,urlparse
from urllib.request import Request,urlopen
from flask import request,session

class Limited(Exception):pass
class QuotaUsed(Exception):pass
class VerificationFailed(Exception):pass

class Protection:
 def __init__(self,store,secret,public_url):self.store,self.secret,self.public_url=store,secret,public_url
 def digest(self,value):return hmac.new(self.secret.encode(),value.encode(),hashlib.sha256).hexdigest()
 def subjects(self):
  ip=request.remote_addr or 'unknown'
  try:ip=str(ipaddress.ip_address(ip))
  except ValueError:ip='unknown'
  return ['browser:'+self.digest(session['owner']),'ip:'+self.digest(ip)]
 def rate(self,operation='new'):
  now=time.time();keys=[operation+':'+s for s in self.subjects()]
  blocked=False
  with self.store.connect() as c:
   rows=[c.execute('SELECT * FROM ab49_rates WHERE subject=?',(s,)).fetchone() for s in keys]
   if any(r and r['blocked_until']>now for r in rows):blocked=True
   elif any(r and r['next_at']>now for r in rows):
    blocked=True
    for s in keys:c.execute('INSERT INTO ab49_rates VALUES(?,?,?,?) ON CONFLICT(subject) DO UPDATE SET blocked_until=excluded.blocked_until,expires=excluded.expires',(s,now+60,now+900,now+86400))
   else:
    for s in keys:c.execute('INSERT INTO ab49_rates VALUES(?,?,0,?) ON CONFLICT(subject) DO UPDATE SET next_at=excluded.next_at,blocked_until=0,expires=excluded.expires',(s,now+60,now+86400))
  if blocked:raise Limited()
 def verify(self,action):
  token=request.form.get('cf-turnstile-response','')
  secret=os.getenv('TURNSTILE_SECRET_KEY','')
  if not token or len(token)>2048 or not secret:raise VerificationFailed()
  payload=urlencode({'secret':secret,'response':token,'remoteip':request.remote_addr or ''}).encode()
  try:
   with urlopen(Request('https://challenges.cloudflare.com/turnstile/v0/siteverify',data=payload),timeout=8) as r:result=json.loads(r.read(20000))
  except Exception:raise VerificationFailed() from None
  if result.get('success') is not True or result.get('hostname')!=urlparse(self.public_url).hostname or result.get('action')!=action:raise VerificationFailed()
  try:
   challenge=datetime.fromisoformat(result['challenge_ts'].replace('Z','+00:00')).timestamp()
   if not -30<=time.time()-challenge<=300:raise ValueError()
  except (ValueError,KeyError,TypeError):raise VerificationFailed() from None
  digest=self.digest(token)
  with self.store.connect() as c:
   inserted=c.execute('INSERT INTO ab49_tokens VALUES(?,?) ON CONFLICT(digest) DO NOTHING',(digest,time.time()+600)).rowcount
  if inserted!=1:raise VerificationFailed()
 def reserve_trial(self):
  now=time.time();day=datetime.now(timezone.utc).strftime('%Y-%m-%d');rid=secrets.token_hex(16)
  subjects=self.subjects()
  with self.store.connect() as c:
   c.execute("DELETE FROM ab49_trials WHERE status='held' AND created<?",(now-1800,))
   for subject,maximum in zip(subjects,(1,2)):
    count=c.execute('SELECT COUNT(*) AS n FROM ab49_trials WHERE subject=? AND day=?',(subject,day)).fetchone()['n']
    if count>=maximum:raise QuotaUsed()
   for s in subjects:c.execute('INSERT INTO ab49_trials VALUES(?,?,?,?,?)',(s,day,rid,'held',now))
  return rid
 def finish_trial(self,rid,success):
  if not rid:return
  with self.store.connect() as c:
   if success:c.execute("UPDATE ab49_trials SET status='used' WHERE reservation=?",(rid,))
   else:c.execute("DELETE FROM ab49_trials WHERE reservation=? AND status='held'",(rid,))

# Configurable upper-bound rates, USD per million tokens; over-reservation is intentional.
# These are safety allowances, NOT a vendor price quotation. Raising provider prices requires updating them.
DEFAULT_RATES={'deepseek-v4-pro':(10.,40.),'deepseek-flash':(2.,8.),'deepseek-search':(1.,1.)}
class BudgetExceeded(Exception):pass

def budget_settings(model):
 rates=DEFAULT_RATES.get(model)
 if rates is None:raise BudgetExceeded()
 prefix='AI_PRO' if model=='deepseek-v4-pro' else 'AI_FLASH'
 values=[float(os.getenv(prefix+'_INPUT_USD_PER_M',str(rates[0]))),float(os.getenv(prefix+'_OUTPUT_USD_PER_M',str(rates[1]))),float(os.getenv('BUDGET_AUD_PER_USD','2')),float(os.getenv('AI_DAILY_BUDGET_AUD','2'))]
 if any(not math.isfinite(x) or x<=0 for x in values) or values[2]<1:raise BudgetExceeded()
 return values

def capacity(store,reserve_needed=0):
 try:
  if os.getenv('AI_ENABLED','1')!='1':return False
  *_,budget=budget_settings('deepseek-v4-pro');day=datetime.now(timezone.utc).strftime('%Y-%m-%d')
  with store.connect() as c:r=c.execute('SELECT COUNT(*) AS n, COALESCE(SUM(reserve),0) AS cost FROM ab49_calls WHERE day=?',(day,)).fetchone()
  return r['n']<int(os.getenv('AI_DAILY_REQUEST_LIMIT','40')) and r['cost']+reserve_needed<budget
 except (ValueError,BudgetExceeded):return False

def bounded_client(client,store):
 def create(**kwargs):
  if not capacity(store):raise BudgetExceeded()
  input_rate,output_rate,factor,budget=budget_settings(kwargs.get('model'))
  size=len(json.dumps(kwargs.get('messages',[]),ensure_ascii=False).encode())
  if size>90000:raise BudgetExceeded()
  maximum=min(8192,max(1,int(kwargs.get('max_tokens',4096))));kwargs['max_tokens']=maximum
  reserve=float(os.getenv('WEB_SEARCH_RESERVE_AUD','0.10')) if kwargs['model']=='deepseek-search' else ((size+2048)*input_rate+maximum*output_rate)/1000000*factor
  if not math.isfinite(reserve) or reserve<=0:raise BudgetExceeded()
  day=datetime.now(timezone.utc).strftime('%Y-%m-%d');now=time.time();cid=secrets.token_hex(16)
  with store.connect() as c:
   row=c.execute('SELECT COUNT(*) AS n,COALESCE(SUM(reserve),0) AS cost FROM ab49_calls WHERE day=?',(day,)).fetchone()
   if kwargs['model']=='deepseek-search':
    searches=c.execute("SELECT COUNT(*) AS n FROM ab49_calls WHERE day=? AND model='deepseek-search'",(day,)).fetchone()['n']
    if searches>=int(os.getenv('WEB_SEARCH_DAILY_LIMIT','3')):raise BudgetExceeded()
   active=c.execute("SELECT COUNT(*) AS n FROM ab49_calls WHERE status='reserved' AND created>?",(now-900,)).fetchone()['n']
   if row['n']>=int(os.getenv('AI_DAILY_REQUEST_LIMIT','40')) or row['cost']+reserve>budget or active>=int(os.getenv('AI_MAX_CONCURRENT','2')):raise BudgetExceeded()
   c.execute('INSERT INTO ab49_calls(id,day,model,status,reserve,created) VALUES(?,?,?,?,?,?)',(cid,day,kwargs['model'],'reserved',reserve,now))
  try:response=client.chat.completions.create(**kwargs)
  except Exception:
   with store.connect() as c:c.execute("UPDATE ab49_calls SET status='failed' WHERE id=?",(cid,))
   raise
  usage=getattr(response,'usage',None)
  with store.connect() as c:c.execute("UPDATE ab49_calls SET status='completed',prompt_tokens=?,completion_tokens=? WHERE id=?",(getattr(usage,'prompt_tokens',0) or 0,getattr(usage,'completion_tokens',0) or 0,cid))
  # Keep the reservation even when cache discounts apply or usage is missing.
  return response
 return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
