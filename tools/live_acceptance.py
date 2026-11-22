#!/usr/bin/env python3
"""Opt-in real-provider protocol acceptance. Never imports the web app or touches its DB."""
import argparse,csv,json,math,os,secrets,sys,time
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parent))
import simple_reading as engine
from hexagrams import build_cast
from acceptance_budget import DailyLedger,DailyBudgetStop

QUESTIONS=[('marriage','他是适合结婚的对象吗？'),('offer','这次面试能拿到offer吗？'),('house','这套房现在适合买入吗？'),('debt','这笔欠款能收回来吗？'),('exam','这次考试能通过吗？'),('lost','丢失的钥匙还能找回来吗？'),('rent','这套房适合租住吗？'),('business','这笔生意有利润吗？'),('legal','这场官司能打赢吗？'),('travel','这次出行能顺利吗？'),('pet','走失的鹦鹉还能找回来吗？'),('cooperation','这次合作能继续吗？')]
SCENARIOS={'static':[2,1,2,2,1,2],'moving':[1,1,2,1,0,0],'multiple':[0,3,2,1,0,3]}
class BudgetStop(Exception):pass

def positive(value):
 try:number=float(value)
 except (ValueError,TypeError):raise argparse.ArgumentTypeError('must be finite and greater than zero') from None
 if not math.isfinite(number) or number<=0:raise argparse.ArgumentTypeError('must be finite and greater than zero')
 return number

def write_json(path,value):
 path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');path.chmod(0o600)

class Meter:
 def __init__(self,provider,budget,rates,factor,report_dir,save_responses=False):
  self.provider,self.budget,self.rates,self.factor,self.report_dir,self.save_responses=provider,budget,rates,factor,report_dir,save_responses
  self.ledger=None;self.daily_limit=10.;self.run_id=secrets.token_hex(16);self.blocked=None
  self.reserved=0.;self.calls=[];self.stage='';self.case=''
  self.chat=SimpleNamespace(completions=SimpleNamespace(create=self.create))
 def create(self,**kwargs):
  model=kwargs['model'];input_rate,output_rate=self.rates[model]
  # UTF-8 bytes overestimate text tokens; extra allowance covers message framing.
  size=len(json.dumps(kwargs.get('messages',[]),ensure_ascii=False).encode('utf-8'))+8192
  reserve=(size*input_rate+kwargs['max_tokens']*output_rate)/1e6*self.factor
  if self.reserved+reserve>self.budget+1e-12:
   self.blocked={'scope':'run','next_stage':self.stage,'next_reservation_cny':reserve,'remaining_cny':max(0,self.budget-self.reserved)};raise BudgetStop()
  identity=self.run_id+'-'+str(len(self.calls)+1)
  if self.ledger:
   try:self.ledger.reserve(identity,reserve,self.daily_limit)
   except DailyBudgetStop:
    self.blocked={'scope':'day','next_stage':self.stage,'next_reservation_cny':reserve,'remaining_cny':max(0,self.daily_limit-self.ledger.total())};raise BudgetStop() from None
  self.reserved+=reserve
  item={'number':len(self.calls)+1,'case':self.case,'stage':self.stage,'model':model,'max_tokens':kwargs['max_tokens'],'reserved_cny':reserve,'ledger_id':identity,'status':'started'}
  self.calls.append(item);write_json(self.report_dir/'calls.json',self.calls)
  started=time.monotonic()
  try:
   result=self.provider.chat.completions.create(**kwargs)
   item['status']='returned'
   choices=getattr(result,'choices',[]) or []
   item['finish_reason']=getattr(choices[0],'finish_reason',None) if choices else None
   usage=getattr(result,'usage',None)
   for field in ('prompt_tokens','completion_tokens','total_tokens'):
    item[field]=getattr(usage,field,None)
   if self.save_responses and choices:
    content=getattr(choices[0].message,'content',None)
    # Only final content, never SDK errors, HTTP headers, credentials, or hidden reasoning.
    write_json(self.report_dir/('response-%03d.json'%item['number']),{'content':content})
   return result
  except Exception as error:
   item['status']='error';item['error_category']=type(error).__name__
   raise
  finally:
   item['seconds']=round(time.monotonic()-started,3);write_json(self.report_dir/'calls.json',self.calls)


def parser():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--execute',action='store_true',help='Actually call DeepSeek; absent means dry run')
 p.add_argument('--budget-cny',type=positive,help='Required with --execute; CNY reservation ceiling for this run, daily cap still applies')
 p.add_argument('--resume',help='Existing timestamped report directory; reuse completed stages')
 p.add_argument('--limit',type=int,default=1,help='Number of question/chart combinations, default 1')
 p.add_argument('--topic',choices=[q[0] for q in QUESTIONS],action='append')
 p.add_argument('--scenario',choices=list(SCENARIOS),action='append')
 p.add_argument('--english',action='store_true',help='Also translate the saved Chinese paid text')
 p.add_argument('--save-responses',action='store_true',help='Save final JSON content for diagnosing validation failures')
 p.add_argument('--out',default='acceptance-reports',help='Parent directory; a NEW private run directory is always created')
 return p


def run(args,provider=None):
 if args.limit<1:raise ValueError('limit must be positive')
 if args.execute and args.budget_cny is None:raise ValueError('--execute requires --budget-cny')
 resume=Path(args.resume).resolve() if args.resume else None
 previous=json.loads((resume/'plan.json').read_text(encoding='utf-8')) if resume else None
 topics=args.topic or [q[0] for q in QUESTIONS];scenarios=args.scenario or list(SCENARIOS)
 # Cycle topics before chart variants, so a small limit covers different questions.
 cases=[{'id':topic+'-'+scenario,'question':question,'scenario':scenario,'words':SCENARIOS[scenario]} for scenario in scenarios for topic,question in QUESTIONS if topic in topics][:args.limit]
 if previous:
  if args.topic or args.scenario:raise ValueError('resume cannot be combined with topic/scenario filters')
  cases=previous['cases'][:args.limit]
 settings={'model':os.getenv('DEEPSEEK_MODEL','deepseek-v4-pro').strip().lower()}
 settings['writer_model']=os.getenv('DEEPSEEK_WRITER_MODEL',settings['model']).strip().lower()
 settings['translation_model']=os.getenv('DEEPSEEK_NARRATOR_MODEL','deepseek-flash').strip().lower()
 rates={}
 for model in set(settings.values()):
  if model not in ('deepseek-v4-pro','deepseek-flash'):raise ValueError('unsupported model configuration')
  prefix='AI_PRO' if model=='deepseek-v4-pro' else 'AI_FLASH';defaults=(10,30) if model=='deepseek-v4-pro' else (2.5,10)
  rates[model]=[positive(os.getenv(prefix+'_INPUT_CNY_PER_M',str(defaults[0]))),positive(os.getenv(prefix+'_OUTPUT_CNY_PER_M',str(defaults[1])))]
 factor=1.
 daily_limit=positive(os.getenv('AI_DAILY_BUDGET_CNY','10'))
 plan={'pipeline_version':engine.VERSION,'mode':'execute' if args.execute else 'dry_run','cases':cases,'models':settings,'rate_allowances_cny_per_million':rates,'currency':'CNY','budget_cny':args.budget_cny,'daily_budget_cny':daily_limit,'resume_from':str(resume) if resume else None,'english':args.english,'payment_tested':False,'queue_tested':False,'external_search_tested':False,'interpretation_quality':'requires_manual_review'}
 if not args.execute:
  print(json.dumps(plan,ensure_ascii=False,indent=2));return 0
 if provider is None:
  key=os.getenv('DEEPSEEK_API_KEY','').strip()
  if not key:raise ValueError('DEEPSEEK_API_KEY is not configured; no calls made')
  from openai import OpenAI
  provider=OpenAI(api_key=key,base_url='https://api.deepseek.com',timeout=75,max_retries=0)
 parent=Path(args.out).resolve();parent.mkdir(parents=True,exist_ok=True)
 directory=parent/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+secrets.token_hex(4));directory.mkdir(mode=0o700)
 write_json(directory/'plan.json',plan)
 meter=Meter(provider,args.budget_cny,rates,factor,directory,args.save_responses)
 meter.ledger=DailyLedger(Path(__file__).resolve().parents[1]/'acceptance-reports'/'daily-budget-cny.sqlite3')
 meter.daily_limit=daily_limit
 if resume:meter.ledger.import_report(resume,rates)
 results=[];stop=False
 # Fixed dates make cases reproducible, not forecasts. Conditions are recorded for each chart.
 for case in cases:
  meter.case=case['id'];started=time.monotonic();first=len(meter.calls)
  result={**case,'status':'running','quality_review':'pending'}
  cast=build_cast(case['words'],datetime(2026,11,22,11,40),'Asia/Shanghai')
  write_json(directory/(case['id']+'-chart.json'),cast)
  output={}
  if resume and (resume/(case['id']+'-output.json')).exists():
   output=json.loads((resume/(case['id']+'-output.json')).read_text(encoding='utf-8'))
   saved_cast=json.loads((resume/(case['id']+'-chart.json')).read_text(encoding='utf-8'))
   if saved_cast!=cast:raise ValueError('resume chart does not match selected case')
   output.pop('result',None)
   if previous.get('pipeline_version')!=engine.VERSION or previous.get('models')!=settings:
    # Preserve costly initial evidence; rerun changed paid review/writing logic.
    for key in ('review','paid_zh','paid_en'):output.pop(key,None)
  try:
   meter.stage='initial'
   if 'initial' not in output:output['initial']=engine.generate(meter,case['question'],cast,settings['model'])
   core=output['initial']
   if core['reference_snapshot']['cast']!=engine.context(case['question'],cast)[0]['cast'] or core['reference_snapshot']['question']!=case['question']:raise ValueError('saved initial does not match chart')
   write_json(directory/(case['id']+'-output.json'),output)
   meter.stage='review'
   if 'review' not in output:output['review']=engine.review_paid(meter,case['question'],cast,settings['model'],core['bundle'],reference_snapshot=core['reference_snapshot'])
   review=output['review']
   write_json(directory/(case['id']+'-output.json'),output)
   meter.stage='writer'
   if 'paid_zh' not in output:output['paid_zh']=engine.generate_paid(meter,case['question'],cast,settings['model'],core['bundle'],reference_snapshot=core['reference_snapshot'],reviewed_plan=review,writer_model=settings['writer_model'])
   parts=output['paid_zh']
   write_json(directory/(case['id']+'-output.json'),output)
   if args.english and 'paid_en' not in output:
    meter.stage='translation';output['paid_en']=engine.translate(meter,parts,'paid',cast,settings['translation_model'])['parts']
   result['status']='protocol_passed'
  except BudgetStop:result['status']='budget_stopped';result['budget_block']=meter.blocked;result['stage']=meter.stage;stop=True
  except Exception as error:
   result['status']='failed';result['error_category']=type(error).__name__;result['stage']=meter.stage
   for field in ('reason','detail','finish_reason','attempt','max_tokens'):
    if hasattr(error,field):result[field]=getattr(error,field)
  finally:
   result['seconds']=round(time.monotonic()-started,3);result['provider_calls']=len(meter.calls)-first
   output['result']=result;write_json(directory/(case['id']+'-output.json'),output);results.append(result)
   write_json(directory/'summary.json',{'plan':plan,'results':results,'reserved_cny':meter.reserved,'daily_reserved_cny':meter.ledger.total(),'provider_calls':len(meter.calls),'unrun_cases':len(cases)-len(results),'note':'Protocol pass is not content-quality approval. Reserved cost is a conservative estimate, not a vendor bill.'})
  if stop:break
 fields=['id','question','scenario','status','stage','reason','detail','seconds','provider_calls','quality_review']
 with (directory/'summary.csv').open('w',encoding='utf-8-sig',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(results)
 (directory/'summary.csv').chmod(0o600)
 print('Report: '+str(directory));print('Provider calls: '+str(len(meter.calls)));print('Reserved CNY this run: %.4f'%meter.reserved);print('Reserved CNY today: %.4f'%meter.ledger.total())
 for result in results:print(result['id']+': '+result['status']+(' (stage='+result['stage']+')' if result.get('stage') else ''))
 return 0 if len(results)==len(cases) and all(r['status']=='protocol_passed' for r in results) else 2

def main():
 args=parser().parse_args()
 try:return run(args)
 except (ValueError,argparse.ArgumentTypeError) as error:
  # Only our own configuration errors; never print provider exception messages.
  print('Configuration error: '+str(error),file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())
