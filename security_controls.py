"""Server-only test access and bounded provider calls. Never logs credentials or prompts."""
import hmac,os,secrets,json,math,sqlite3
from datetime import datetime,timezone
from types import SimpleNamespace
from flask import request,Response

class CallLimitError(ValueError):pass

def private_access():
 password=os.getenv('SITE_ACCESS_PASSWORD','')
 if not password or request.endpoint in ('health','stripe_webhook'):return None
 auth=request.authorization
 if auth and auth.type.lower()=='basic' and hmac.compare_digest((auth.username or '').encode(),b'tester') and hmac.compare_digest((auth.password or '').encode(),password.encode()):return None
 return Response('Private test site. Authentication required.',401,{'WWW-Authenticate':'Basic realm="Private test", charset="UTF-8"','Cache-Control':'no-store'})

def bounded_client(client,connect):
 def create(**kwargs):
  if os.getenv('AI_ENABLED','1')!='1':raise CallLimitError('provider calls paused')
  limit=max(1,min(200,int(os.getenv('AI_DAILY_REQUEST_LIMIT','20'))))
  size=len(json.dumps(kwargs.get('messages',[]),ensure_ascii=False).encode('utf-8'))
  if size>120000:raise CallLimitError('provider input size limit reached')
  rates={'deepseek-v4-pro':(1.32,3.96),'deepseek-flash':(0.30,1.20),'deepseek-search':(0,0)}
  if kwargs.get('model') not in rates:raise CallLimitError('provider model not allowed')
  input_rate,output_rate=rates[kwargs['model']]
  max_tokens=min(8192,max(1,int(kwargs.get('max_tokens',4096))));kwargs['max_tokens']=max_tokens
  factor=float(os.getenv('BUDGET_AUD_PER_USD','2.0'));budget=float(os.getenv('AI_DAILY_BUDGET_AUD','2.0'))
  if not math.isfinite(factor) or factor<1 or not math.isfinite(budget) or budget<=0:raise CallLimitError('invalid budget configuration')
  # Conservative byte-based input allowance, peak rates, no cache discounts.
  reserved_cost=(0.00075*factor if kwargs['model']=='deepseek-search' else ((size+4096)*input_rate+max_tokens*output_rate)/1000000*factor)
  now=datetime.now(timezone.utc);day=now.strftime('%Y-%m-%d');call_id=secrets.token_hex(12)
  with connect() as c:
   c.execute('CREATE TABLE IF NOT EXISTS provider_calls(id TEXT PRIMARY KEY,day TEXT NOT NULL,model TEXT NOT NULL,status TEXT NOT NULL,prompt_tokens INTEGER DEFAULT 0,completion_tokens INTEGER DEFAULT 0)')
   columns={r[1] for r in c.execute('PRAGMA table_info(provider_calls)')}
   if 'reserved_aud' not in columns:
    try:c.execute('ALTER TABLE provider_calls ADD COLUMN reserved_aud REAL NOT NULL DEFAULT 0')
    except sqlite3.OperationalError:
     if 'reserved_aud' not in {r[1] for r in c.execute('PRAGMA table_info(provider_calls)')}:raise
   c.execute('BEGIN IMMEDIATE')
   n=c.execute('SELECT COUNT(*) FROM provider_calls WHERE day=?',(day,)).fetchone()[0]
   if n>=limit:raise CallLimitError('provider daily request limit reached')
   if kwargs['model']=='deepseek-search':
    search_limit=max(0,min(20,int(os.getenv('WEB_SEARCH_DAILY_LIMIT','5'))))
    search_count=c.execute("SELECT COUNT(*) FROM provider_calls WHERE day=? AND model='deepseek-search'",(day,)).fetchone()[0]
    if search_count>=search_limit:raise CallLimitError('web search daily request limit reached')
   used=c.execute('SELECT COALESCE(SUM(reserved_aud),0) FROM provider_calls WHERE day=?',(day,)).fetchone()[0]
   if used+reserved_cost>budget:raise CallLimitError('provider daily budget limit reached')
   c.execute('INSERT INTO provider_calls(id,day,model,status,reserved_aud) VALUES(?,?,?,?,?)',(call_id,day,str(kwargs.get('model','unknown')),'reserved',reserved_cost))
  try:
   response=client.chat.completions.create(**kwargs)
  except Exception:
   with connect() as c:c.execute('UPDATE provider_calls SET status=? WHERE id=?',('failed',call_id))
   raise
  usage=getattr(response,'usage',None)
  with connect() as c:c.execute('UPDATE provider_calls SET status=?,prompt_tokens=?,completion_tokens=? WHERE id=?',('completed',getattr(usage,'prompt_tokens',0) or 0,getattr(usage,'completion_tokens',0) or 0,call_id))
  return response
 return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

def provider_capacity(connect):
 if os.getenv('AI_ENABLED','1')!='1':return False
 try:
  limit=max(1,min(200,int(os.getenv('AI_DAILY_REQUEST_LIMIT','20'))));budget=float(os.getenv('AI_DAILY_BUDGET_AUD','2'))
  if not math.isfinite(budget) or budget<=0:return False
  day=datetime.now(timezone.utc).strftime('%Y-%m-%d')
  with connect() as c:
   if not c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='provider_calls'").fetchone():return True
   n=c.execute('SELECT COUNT(*) FROM provider_calls WHERE day=?',(day,)).fetchone()[0]
   cols={r[1] for r in c.execute('PRAGMA table_info(provider_calls)')}
   used=c.execute('SELECT COALESCE(SUM(reserved_aud),0) FROM provider_calls WHERE day=?',(day,)).fetchone()[0] if 'reserved_aud' in cols else 0
  return n<limit and used<budget
 except (ValueError,sqlite3.Error):return False
