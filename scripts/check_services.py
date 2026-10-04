"""Run from the project directory: python scripts/check_services.py [--ai].
Stripe checks are read-only. --ai makes two real model calls using synthetic questions.
Never prints credentials. Does not create charges, customers or checkout sessions.
"""
import argparse,json,sys
from pathlib import Path
from datetime import datetime
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app as site
from hexagrams import build_cast
parser=argparse.ArgumentParser();parser.add_argument('--ai',action='store_true');args=parser.parse_args()
report={'version':site.PROMPT_VERSION,'live_ai':'not_run','checkout_payment':'not_run','stripe_readonly':'not_run','configured':{'ai':bool(site.AI_KEY),'stripe':bool(site.stripe.api_key),'price':bool(site.PRICE_ID),'public_url':bool(site.PUBLIC_URL),'support':bool(site.SUPPORT_EMAIL),'durable_storage':site.STORAGE_DURABLE}}
if site.stripe.api_key and site.PRICE_ID:
 try:
  price=site.stripe.Price.retrieve(site.PRICE_ID)
  report['stripe_readonly']={'active':price.active,'livemode':price.livemode,'currency':price.currency,'unit_amount':price.unit_amount,'type':price.type}
 except Exception:report['stripe_readonly']='failed; check credentials and price in the dashboard'
if args.ai:
 if not site.AI_KEY:report['live_ai']='blocked: DEEPSEEK_API_KEY is missing'
 else:
  results=[]
  for lang,question,words in [('zh','未来三个月是否适合主动寻找新工作？',[0,1,2,3,2,1]),('en','Should I actively look for a new job over the next three months?',[2,1,2,1,2,1])]:
   cast=build_cast(words,datetime(2026,10,4,18,30),'Australia/Adelaide')
   with site.app.test_request_context('/'):
    site.g.lang=lang
    try:
     text=site.call_ai(question,cast,lang,'free')
     results.append({'language':lang,'status':'returned','chart':{'primary':cast['main']['name'],'transformed':cast['changed']['name'],'moving':cast['moving'],'rows':cast['rows'],'calendar':cast['calendar']},'reading':text,'review_required':'Compare every quoted line, relation and conclusion with this chart. This is not a test of predictive accuracy.'})
    except site.ReadingError:results.append({'language':lang,'status':'generation_failed'})
  report['live_ai']=results
print(json.dumps(report,ensure_ascii=False,indent=2))
