"""Inventory the supplied corpus and build structural scenarios; never assert full-book coverage."""
import csv,json,sys
from pathlib import Path
from datetime import datetime
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from hexagrams import build_cast
from theory_facts import ledger
from intent_reference import INTENTS
out=ROOT/'review';out.mkdir(exist_ok=True)
entries=[]
for path in sorted((ROOT/'knowledge').glob('*.json')):
 data=json.loads(path.read_text())
 for row in data.get('rules',[]):
  entries.append({'kind':'rule','file':path.name,'id':row['id'],'chapter':row.get('chapter',''),'part':row.get('part'),'pdf_page':row.get('pdf_page'),'runtime_eligible':row.get('runtime_eligible',True),'verification':'现有条目记录，非本次重新核对原书','live_test':'未执行'})
 for row in data.get('cases',[]):
  src=row.get('source',{})
  entries.append({'kind':'case','file':path.name,'id':row['id'],'chapter':row.get('question',''),'part':src.get('part'),'pdf_page':src.get('pdf_page'),'runtime_eligible':row.get('retrieval_eligible',False),'verification':'现有案例记录，非本次重新核对原书','live_test':'未执行'})
with (out/'reference_inventory.csv').open('w',encoding='utf-8-sig',newline='') as f:
 writer=csv.DictWriter(f,fieldnames=list(entries[0]));writer.writeheader();writer.writerows(entries)
with (out/'question_intents.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.writer(f);w.writerow(['id','topic','example','scope','live_test'])
 for i,t,kw,examples,scope in INTENTS:
  for q in examples:w.writerow([i,t,q,scope,'未执行'])
scenarios=[];coverage={}
for bits in range(64):
 for mask in [0,1,2,21,63]:
  words=[(0 if (bits>>i)&1 else 3) if (mask>>i)&1 else (2 if (bits>>i)&1 else 1) for i in range(6)]
  c=build_cast(words,datetime(2026,11,22,9,51));facts=ledger(c)['lines']
  states=[f for f in facts if f['id'].endswith('.state')]
  tags=[]
  if not mask:tags.append('静卦')
  if mask:tags.append('动爻')
  if mask==63:tags.append('六爻全动')
  if any(f['id'].endswith('.hidden') for f in facts):tags.append('伏藏')
  if any(f['void'] for f in states):tags.append('旬空')
  if any(f['month_broken'] for f in states):tags.append('月破')
  if any(sum(x['kin']==f['kin'] for x in states)>1 for f in states):tags.append('同六亲多现')
  for relation in ['generates','controls','is_generated_by','is_controlled_by','same_element']:
   if any(f.get('element_relation')==relation for f in facts):tags.append(relation)
  for tag in tags:coverage[tag]=coverage.get(tag,0)+1
  scenarios.append({'id':f'bits-{bits}-moves-{mask}','words':words,'main':c['main']['name'],'changed':c['changed']['name'],'tags':tags,'expected':'核对盘面事实和作用方向，不预设吉凶','model_verdict_tested':False})
(out/'structural_scenarios.json').write_text(json.dumps(scenarios,ensure_ascii=False,indent=2))
(out/'coverage_status.json').write_text(json.dumps({'scope':'仅当前已收录语料；未取得全书逐篇目录对照，不能声明全书覆盖','rules':sum(x['kind']=='rule' for x in entries),'cases':sum(x['kind']=='case' for x in entries),'retrieval_eligible_cases':sum(x['kind']=='case' and x['runtime_eligible'] for x in entries),'structural_scenarios':len(scenarios),'structural_tags':coverage,'true_model_runs':0,'not_completed':['全书目录逐篇对照与缺篇补充','真实DeepSeek抽样验收','真实Stripe付款及Neon端到端验收']},ensure_ascii=False,indent=2))
print('Inventory and 320 structural scenarios saved; real model runs: 0')
