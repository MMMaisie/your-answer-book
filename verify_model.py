"""Optional real-provider acceptance. Never stores credentials. Not a Stripe test."""
import os,json,getpass,tempfile,sqlite3
from pathlib import Path
from datetime import datetime

def main():
 print('Real DeepSeek test: up to 8 API attempts for one chart / four views. This spends your provider balance.')
 print('Conservative local budget allowance A$2; this is not a provider-side currency guarantee. No Stripe payment is made.')
 if input('Type TEST to continue: ').strip()!='TEST':return
 key=os.getenv('DEEPSEEK_API_KEY') or getpass.getpass('DeepSeek key (hidden, never saved): ').strip()
 if not key:raise SystemExit('No key supplied.')
 from openai import OpenAI
 from simple_reading import generate,generate_paid,translate,count,LIMITS
 from security_controls import bounded_client
 from hexagrams import build_cast
 from external_references import search as web_search
 os.environ['AI_DAILY_REQUEST_LIMIT']='8';os.environ['AI_DAILY_BUDGET_AUD']='2'
 report={'real_provider':True,'stripe_tested':False,'passed':False,'views':{}}
 with tempfile.TemporaryDirectory() as temp:
  def connect():return sqlite3.connect(str(Path(temp)/'usage.db'),timeout=10)
  cast=build_cast([2,1,2,1,0,2],datetime(2026,10,24,20,0),'Australia/Adelaide');question='我什么时候能拿到offer？'
  try:
   with OpenAI(api_key=key,base_url='https://api.deepseek.com',timeout=90,max_retries=0) as raw:
    client=bounded_client(raw,connect);record=generate(client,question,cast,'deepseek-v4-pro',lambda topics:web_search(topics,connect,api_key=key));core=record['bundle']
    paid=generate_paid(client,question,cast,'deepseek-v4-pro',core,lambda topics:web_search(topics,connect,api_key=key),record.get('external_reference'))
    for tier,parts in [('free',core['free']),('paid',paid)]:
     english=translate(client,parts,tier,cast,'deepseek-flash')['parts']
     for lang,body in [('zh',parts),('en',english)]:
      size=count(' '.join(body.values()),lang)
      report['views'][tier+'_'+lang]={'body':body,'count':size,'maximum':LIMITS[lang][tier]}
    report['passed']=True
  except Exception as error:
   report['failure_type']=type(error).__name__;report['http_status']=getattr(error,'status_code',None)
   print('Test stopped. No raw response, question credentials or provider error body was logged.')
  finally:
   with connect() as c:
    try:report['provider_calls']=c.execute('SELECT COUNT(*) FROM provider_calls').fetchone()[0]
    except sqlite3.OperationalError:report['provider_calls']=0
 Path('acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 print('PASS' if report['passed'] else 'NOT PASSED','— acceptance.json')
if __name__=='__main__':main()
