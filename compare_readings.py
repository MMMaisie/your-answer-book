"""Explicit opt-in A/B comparison. No provider requests without --execute."""
import argparse,json,os,time
from pathlib import Path
QUESTIONS=['我什么时候能拿到offer？','找对象','我跟他能不能结婚？','这笔欠款能收回来吗？']

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--execute',action='store_true',help='Actually call the paid API using server-side environment credentials')
 parser.add_argument('--max-cases',type=int,choices=range(1,5),default=2)
 parser.add_argument('--tier',choices=['free','both'],default='free')
 parser.add_argument('--budget-aud',type=float,default=1.)
 parser.add_argument('--output',default='comparison-result.json')
 args=parser.parse_args()
 if not 0<args.budget_aud<=10:parser.error('Budget must be greater than zero and at most AUD 10.')
 if not args.execute:
  print(json.dumps({'executed':False,'questions':QUESTIONS[:args.max_cases],'tier':args.tier,'budget_aud':args.budget_aud,'instructions':'Set DEEPSEEK_API_KEY in your own environment, then explicitly add --execute. Never paste keys into chat or commit them. Output checks do not establish prediction accuracy.'},ensure_ascii=False,indent=2));return
 if not os.getenv('DEEPSEEK_API_KEY'):parser.error('Set DEEPSEEK_API_KEY in your local environment; do not put it in the command line.')
 # A/B has its own smaller ceiling, and also honors the deployment's lower daily ceiling.
 os.environ['AI_DAILY_BUDGET_AUD']=str(min(args.budget_aud,float(os.getenv('AI_DAILY_BUDGET_AUD','2'))))
 from storage import Store
 from protection import bounded_client,BudgetExceeded
 from hexagrams import build_cast
 from datetime import datetime
 from openai import OpenAI
 import simple_reading as current
 import baseline_v48 as baseline
 st=Store(os.getenv('DATABASE_URL',''),os.getenv('DB_PATH',str(Path(__file__).parent/'comparison-budget.db')));st.init()
 model=os.getenv('DEEPSEEK_MODEL','deepseek-v4-pro');report={'model':model,'budget_aud':args.budget_aud,'executed':True,'results':[],'accuracy_certified':False}
 for i,question in enumerate(QUESTIONS[:args.max_cases]):
  words=[str((i+j)%4) for j in range(6)];cast=build_cast(words,datetime(2026,10,31,12,i),'Australia/Adelaide')
  for name,module in [('v48.2',baseline),('v49',current)]:
   started=time.monotonic();result={'question':question,'variant':name,'words':words}
   try:
    with OpenAI(api_key=os.environ['DEEPSEEK_API_KEY'],base_url='https://api.deepseek.com',timeout=75,max_retries=0) as client:
     wrapped=bounded_client(client,st);stored=module.generate(wrapped,question,cast,model)
     result['free']=stored['bundle']['free'];result['outlook']=stored['bundle']['outlook'];result['references']=stored['reference_ids']
     if args.tier=='both':
      extra={'reference_snapshot':stored.get('reference_snapshot')} if name=='v49' else {}
      result['paid']=module.generate_paid(wrapped,question,cast,model,stored['bundle'],**extra)
    result['status']='STRUCTURE_AND_FOUNDATION_CHECKS_PASSED'
   except Exception as error:result['status']=type(error).__name__
   result['seconds']=round(time.monotonic()-started,2);report['results'].append(result)
   with st.connect() as c:stats=c.execute('SELECT COUNT(*) AS requests,COALESCE(SUM(reserve),0) AS reserved_aud,COALESCE(SUM(prompt_tokens),0) AS prompt_tokens,COALESCE(SUM(completion_tokens),0) AS completion_tokens FROM ab49_calls WHERE day=?',(datetime.utcnow().strftime('%Y-%m-%d'),)).fetchone()
   report['daily_usage_including_other_calls']=dict(stats);Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2))
   if result['status']=='BudgetExceeded':print('Stopped at the budget safety ceiling. Partial results saved.');return
 print('Comparison saved. Review relevance, book application, consistency and actual provider billing; this is not a predictive-accuracy certificate.')
if __name__=='__main__':main()
