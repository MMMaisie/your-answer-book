"""Optional web supplementation, only when no suitable book case was retrieved."""
import html,json,os,re
from urllib.request import Request,urlopen
from urllib.parse import urlencode,urlparse

def search(topics):
 key=os.getenv('BRAVE_SEARCH_API_KEY','')
 if not key:return {'status':'NOT_CONFIGURED','results':[]}
 # Send general theory terms, never the user's verbatim private question.
 query='卜筮正宗 六爻 '+(' '.join(sorted(topics)) if topics else '用神取用')+' 理论 案例'
 url='https://api.search.brave.com/res/v1/web/search?'+urlencode({'q':query,'count':3})
 try:
  req=Request(url,headers={'X-Subscription-Token':key,'Accept':'application/json'})
  with urlopen(req,timeout=8) as response:data=json.load(response)
  items=[]
  for row in data.get('web',{}).get('results',[])[:3]:
   target=row.get('url','')
   if urlparse(target).scheme not in ('https','http'):continue
   items.append({'title':row.get('title','')[:160],'url':target,'excerpt':re.sub('<[^>]+>','',html.unescape(row.get('description','')))[:1200],'authority':'UNVERIFIED_WEB_SUPPLEMENT'})
  return {'status':'SEARCHED' if items else 'NO_RESULTS','results':items}
 except Exception:return {'status':'UNAVAILABLE','results':[]}
