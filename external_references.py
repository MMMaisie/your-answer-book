"""Bounded DeepSeek web search. Network pages never become foundation facts."""
import html,json,os,re,time,hashlib,ipaddress
from types import SimpleNamespace as NS
from urllib.request import Request,urlopen
from urllib.parse import urlparse
from security_controls import bounded_client,CallLimitError

ALLOWED_TOPICS={'婚恋','求职','求财','健康','出行','失物','房屋','文书','诉讼','天气','学业','宠物','人际','其他'}

def public_url(value):
 try:
  p=urlparse(value)
  if p.scheme not in ('http','https') or not p.hostname or p.username or p.password or p.port not in (None,80,443):return False
  host=p.hostname.casefold()
  if host=='localhost' or host.endswith(('.local','.internal')) or '.' not in host:return False
  try:return ipaddress.ip_address(host).is_global
  except ValueError:return True
 except (ValueError,TypeError):return False

def search(topics,connect=None,api_key=None):
 if os.getenv('WEB_SEARCH_ENABLED','1')!='1':return {'status':'DISABLED','results':[]}
 key=api_key or os.getenv('DEEPSEEK_API_KEY','')
 if not key or connect is None:return {'status':'NOT_CONFIGURED','results':[]}
 # Only fixed general topics are sent. No question, person name, date or client IP.
 safe=sorted(set(topics or ()) & ALLOWED_TOPICS)
 query='卜筮正宗 六爻 '+(' '.join(safe[:3]) if safe else '非常见问事')+' 用神 条件 判断 案例'
 cache_id=hashlib.sha256(query.encode()).hexdigest();now=time.time()
 with connect() as c:
  c.execute('CREATE TABLE IF NOT EXISTS web_reference_cache(id TEXT PRIMARY KEY,payload TEXT NOT NULL,expires REAL NOT NULL,inflight_until REAL NOT NULL)')
  c.execute('BEGIN IMMEDIATE');old=c.execute('SELECT payload,expires,inflight_until FROM web_reference_cache WHERE id=?',(cache_id,)).fetchone()
  if old and old[1]>now:return json.loads(old[0])
  if old and old[2]>now:return {'status':'BUSY','results':[]}
  c.execute('INSERT INTO web_reference_cache VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET inflight_until=excluded.inflight_until',(cache_id,'{}',0,now+30))
 result={'status':'UNAVAILABLE','results':[]}
 def perform(**_):
  request=Request('https://api.deepseek.com/v1/tools/search',headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},data=json.dumps({'query':query,'count':3,'need_content':True},ensure_ascii=False).encode(),method='POST')
  with urlopen(request,timeout=8) as response:
   raw=response.read(250001)
   if len(raw)>250000:raise ValueError('search response too large')
   data=json.loads(raw)
  return NS(data=data,usage=None)
 try:
  client=NS(chat=NS(completions=NS(create=perform)))
  response=bounded_client(client,connect).chat.completions.create(model='deepseek-search',messages=[],max_tokens=1)
  items=[]
  for row in response.data.get('results',[])[:3]:
   if not isinstance(row,dict) or not public_url(row.get('url','')):continue
   # Relevance scores are provider signals, not evidence of truth.
   if float(row.get('rerank_score',0))<1.5:continue
   summary=row.get('summary') or row.get('snippet') or ''
   content=row.get('content') or ''
   excerpt=re.sub('<[^>]+>','',html.unescape(str(summary)))[:1500]
   excerpt+='\n'+re.sub('<[^>]+>','',html.unescape(str(content)))[:1200]
   items.append({'id':'web-'+str(len(items)+1),'title':str(row.get('title',''))[:160],'url':row['url'][:2048],'excerpt':excerpt,'authority':'UNVERIFIED_WEB_SUPPLEMENT'})
  result={'status':'SEARCHED' if items else 'NO_RESULTS','results':items}
 except CallLimitError:result={'status':'LIMIT_REACHED','results':[]}
 except Exception:pass  # No raw provider errors, keys or query bodies in logs.
 ttl=86400 if result['status'] in ('SEARCHED','NO_RESULTS') else 300
 with connect() as c:c.execute('UPDATE web_reference_cache SET payload=?,expires=?,inflight_until=0 WHERE id=?',(json.dumps(result,ensure_ascii=False),time.time()+ttl,cache_id))
 return result
