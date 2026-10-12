"""Bounded retrieval of source-gated lessons, without importing historical outcomes."""
import hashlib,json,re
from pathlib import Path
CASE_BYTES=(Path(__file__).parent/'knowledge/bushi_cases.json').read_bytes()
CASE_BOOK=json.loads(CASE_BYTES)
CASE_VERSION=CASE_BOOK['version']+'-'+hashlib.sha256(CASE_BYTES).hexdigest()[:12]
TOPICS={
 'money':('收入','投资','盈利','收益','财','银','卖','买卖','贸易','生意','赌','价','煤','income','money','profit','business','investment','wealth'),
 'career':('工作','求职','录用','升职','官','任','功名','升迁','补缺','升选','会试','乡试','考试','job','career','offer','promotion','exam'),
 'return':('归','回','来','出','仆','寻父','return','come back','arrival','missing','son','daughter'),
 'relationship':('婚','夫','妻','婿','媳','妾','marry','marriage','relationship','partner','husband','wife'),
 'health':('病','生产','生子','子嗣','生育','health','ill','sick','pregnan','fertility','birth'),
 'home':('宅','坟','穴','风水','葬','home','house','property','feng shui'),
 'weather':('雨','旱','麦','晴','rain','weather','drought'),
 'document':('文书','信','寄','document','letter','certificate'),
 'legal':('讼','参','拿问','刑','劾','官事','殴','legal','lawsuit','court'),
}
def topics(question):
 q=question.casefold()
 return {topic for topic,words in TOPICS.items() if any(w in q for w in words)}
def traits(cast):
 cal=cast.get('calendar') or {};rows=cast.get('rows',[])
 return dict(moving=sum(bool(r.get('moving')) for r in rows),void=sum(r.get('branch','?') in cal['xunkong'] for r in rows) if cal.get('xunkong') else None,hidden=any(r.get('hidden') for r in rows))
def retrieve_cases(question,cast,limit=3):
 if not 0<=limit<=3:raise ValueError('case retrieval limit must be 0..3')
 wanted=topics(question)
 if not wanted or not limit:return []
 current=traits(cast);ranked=[]
 for case in CASE_BOOK['cases']:
  if not case['retrieval_eligible']:continue
  related=topics(case['question'])
  # Weather, illness and law examples may not silently migrate into other domains.
  if (related & {'health','weather','legal'})-wanted:continue
  overlap=wanted & related
  if not overlap:continue
  bits=case['words'];moving=sum(str(b) in ('0','3') for b in bits)
  score=10*len(overlap)+2*(moving==current['moving'])
  if case['question'].strip().casefold()==question.strip().casefold():score+=3
  if case.get('main')==(cast.get('main') or {}).get('name'):score+=4
  if list(map(str,case['words']))==list(map(str,cast.get('words',[]))):score+=8
  if case.get('calendar')==(cast.get('calendar') or {}):score+=2
  if current['void'] is not None and any(r['branch'] in case['calendar']['xunkong'] for r in case['lines'])==bool(current['void']):score+=1
  ranked.append((score,case['id'],case))
 result=[]
 for score,ident,c in sorted(ranked,key=lambda item:(-item[0],item[1]))[:limit]:
  src=c['source'];result.append(dict(id=ident,source=src,question=c['question'],main=c['main'],changed=c.get('changed'),calendar=c['calendar'],lines=c['lines'],lessons=c['lessons'],reference=f"《卜筮正宗》第{src['part']}部分PDF第{src['pdf_page']}页，印刷页{src['printed_page']}，位置{src['slot']}",reasoning_validation='NOT_CERTIFIED',use_policy='Historical source analogy only. Verify target-chart applicability. Do not copy the source question, dates, outcome, focal selection or forecasts into the user reading. Not a prediction gold label.'))
 return result
