import copy,itertools,json
from datetime import datetime
import pytest
import simple_reading as e
from conftest import Model,initial,review,full
from reading_contract import resolve_evidence,ReadingValidationError
from hexagrams import build_cast
from theory_facts import ledger
from test_completion_retry import Completion

# These are synthetic protocol tests, not model interpretation acceptance.
QUESTIONS=['他是适合结婚的对象吗','她适合结婚吗','女，和她能复合吗','什么时候能脱单','买房合适吗','卖房能成交吗','租房能租到吗','装修顺利吗','能拿到offer吗','要不要换工作','考试能过吗','签证会批吗','欠款能收回吗','生意有利润吗','官司能赢吗','合作能继续吗','钥匙能找回吗','鹦鹉能回来吗','出行顺利吗','生产能顺利吗','这批产品生产能顺利吗','会下雨吗','这件事怎么样','Is he a suitable marriage partner?']
PATTERNS=[[1]*6,[2]*6,[0]*6,[3]*6,[0,1,2,3,1,2],[1,1,2,1,0,0],[1,2,2,1,3,1],[2,1,2,2,2,3]]

def ids_only(v):
 v=copy.deepcopy(v);v['fact_ids']=[c['fact_id'] for c in v.pop('fact_checks')];v.pop('decision_record',None);return v

@pytest.mark.parametrize('words',PATTERNS)
@pytest.mark.parametrize('question',QUESTIONS)
def test_varied_questions_all_stages_with_id_only_contract(words,question):
 cast=build_cast(words,datetime(2026,11,22,11,40))
 m=Model([ids_only(initial(cast)),ids_only(review(cast=cast)),full(),{'priorities':'There is room for progress, though the outcome remains uncertain.','conditions':'The support needs to become concrete before drawing a conclusion.','actions':'Check confirmed progress before deciding how much to commit.'}])
 core=e.generate(m,question,cast,'deepseek-v4-pro')
 plan=e.review_paid(m,question,cast,'deepseek-v4-pro',core['bundle'])
 result=e.generate_paid(m,question,cast,'deepseek-v4-pro',core['bundle'],reviewed_plan=plan)
 translated=e.translate(m,result,'paid',cast,'deepseek-v4-pro')
 assert translated['parts'] and len(m.calls)==4
 assert json.loads(m.calls[1]['messages'][1]['content'])['reference']['question']==question

@pytest.mark.parametrize('bits',list(itertools.product((1,2),repeat=6)))
def test_all_hexagrams_all_moving_counts_reference_roundtrip(bits):
 for count in range(7):
  words=[(3 if b==2 else 0) if i<count else b for i,b in enumerate(bits)]
  cast=build_cast(words,datetime(2026,11,22,11,40))
  for fact in ledger(cast)['lines']:
   got=resolve_evidence({'fact_ids':[fact['id']]},cast)
   assert resolve_evidence({'fact_checks':got},cast)==got

@pytest.mark.parametrize('field,value,code',[
 ('outlook','unknown','review_outlook'),('technical_summary',None,'review_summary'),
 ('answer','','review_answer'),('watch',None,'review_brief'),('limits',None,'review_brief'),
 ('reasons',[],'review_reasons'),('correction_reason',None,'review_correction')])
def test_malformed_review_is_repaired_with_specific_hint(field,value,code):
 bad=review();bad[field]=value;m=Model([bad,review()])
 result=e._request(m,'deepseek-v4-pro',[],lambda v:e._check_review(v,build_cast([2]*6),{'focal':{}},'婚恋','mixed'),16384,'review')
 assert result['answer'] and e.REPAIR_HINTS[code] in m.calls[1]['messages'][-1]['content']

@pytest.mark.parametrize('stage,budget',[('initial',4096),('review',16384),('writer',4096),('translation',2048)])
def test_every_stage_length_retry_discards_partial(stage,budget):
 m=Completion([('length','partial'),('stop','{"ok":true}')])
 assert e._request(m,'deepseek-v4-pro',[],lambda v:v,budget,stage)=={'ok':True}
 assert [c['max_tokens'] for c in m.calls]==[budget,min(32768 if stage=='review' else 8192,budget*2)]

@pytest.mark.parametrize('question',QUESTIONS)
def test_http_paid_save_translation_pdf_and_cached_retry(client,monkeypatch,question):
 import app as site
 from conftest import submit
 from test_guest_flow import row,paid,post_generate
 en={'priorities':'There is room for progress, though the outcome remains uncertain.','conditions':'The support needs to become concrete before drawing a conclusion.','actions':'Check confirmed progress before deciding how much to commit.'}
 m=Model([ids_only(initial()),ids_only(review()),full(),en]);monkeypatch.setattr(site,'OpenAI',lambda **kw:m)
 response=submit(client,question=question);assert response.status_code==302
 r=row(client);assert r['free_zh'] and not r['paid_zh'];paid(r)
 assert post_generate(client,r,'en').status_code==302
 r=row(client);assert r['paid_zh'] and r['paid_en'] and len(m.calls)==4
 for lang in ['zh','en']:
  assert client.get('/r/'+r['access']+'?lang='+lang).status_code==200
  pdf=client.get('/r/'+r['access']+'/download.pdf?lang='+lang)
  assert pdf.data.startswith(b'%PDF')
 post_generate(client,r,'en');assert len(m.calls)==4
