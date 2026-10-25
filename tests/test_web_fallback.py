import json,sqlite3
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
import app
import simple_reading as engine
import external_references as web
from conftest import Model,initial,full,client,add_user,csrf,submit
from hexagrams import build_cast
CAST=build_cast([2]*6)

def result():return {'status':'SEARCHED','results':[{'id':'web-1','title':'六爻参考','url':'https://example.org/case','excerpt':'区分条件，不照搬结果。','authority':'UNVERIFIED_WEB_SUPPLEMENT'}]}

def test_no_matching_book_case_uses_web_before_first_generation():
 seen=[];m=Model([initial()])
 r=engine.generate(m,'一个超出原案例的新问题',CAST,'deepseek-v4-pro',lambda t:seen.append(t) or result())
 assert len(seen)==1 and len(m.calls)==1 and r['external_status']=='SEARCHED'
 task=json.loads(m.calls[0]['messages'][1]['content'])
 assert task['reference']['external_reference']['results'][0]['id']=='web-1'
 assert task['reference']['five_elements']['generates']['木']=='火'
 assert task['reference']['foundation_facts']

def test_model_can_request_web_even_when_topic_matches_book_cases():
 value=initial();value['needs_web']=True;value['search_topics']=['求职']
 seen=[];m=Model([value,initial()])
 r=engine.generate(m,'我什么时候能拿到offer？',CAST,'deepseek-v4-pro',lambda t:seen.append(t) or result())
 assert len(seen)==1 and len(m.calls)==2
 assert r['bundle']['free']==initial()['free'] and 'paid' not in r['bundle']
 assert '基础卦盘和五行仍以程序为准' in m.calls[1]['messages'][-1]['content']

def test_web_failure_never_fakes_a_search_or_blocks_valid_initial():
 value=initial();value['needs_web']=True;m=Model([value])
 r=engine.generate(m,'我什么时候能拿到offer？',CAST,'deepseek-v4-pro',lambda t:{'status':'UNAVAILABLE','results':[]})
 assert len(m.calls)==1 and r['external_status']=='UNAVAILABLE'

def test_web_refinement_failure_keeps_validated_initial_instead_of_erroring():
 value=initial();value['needs_web']=True;m=Model([value,RuntimeError('outage')])
 r=engine.generate(m,'我什么时候能拿到offer？',CAST,'deepseek-v4-pro',lambda t:result())
 assert r['bundle']['free']==initial()['free']
 assert r['external_reference']['application']=='NOT_APPLIED_TO_INITIAL'

def test_network_cannot_override_element_tables_or_paid_direction():
 value=initial();value['needs_web']=True
 wrong=initial();wrong['free']['direction']='水克土，所以能成。'
 m=Model([value,wrong,wrong])
 r=engine.generate(m,'我什么时候能拿到offer？',CAST,'deepseek-v4-pro',lambda t:result())
 assert r['bundle']['free']==initial()['free']
 with pytest.raises(ValueError):engine.generate_paid(Model([full('difficult'),full('difficult')]),'求职',CAST,'deepseek-v4-pro',r['bundle'],None,r['external_reference'])

def test_search_uses_same_key_generic_topics_cache_and_shared_request_budget(tmp_path,monkeypatch):
 monkeypatch.setenv('DEEPSEEK_API_KEY','unit-only-no-real-key');monkeypatch.setenv('AI_DAILY_REQUEST_LIMIT','20');monkeypatch.setenv('AI_DAILY_BUDGET_AUD','2')
 called=[]
 class Response:
  def __enter__(self):return self
  def __exit__(self,*a):pass
  def read(self,n):return json.dumps({'results':[{'title':'理论','url':'https://example.org/case','summary':'条件比较','content':'未经核实的案例','rerank_score':2}]}).encode()
 def fake(req,timeout):called.append(req);return Response()
 monkeypatch.setattr(web,'urlopen',fake)
 def connect():return sqlite3.connect(tmp_path/'usage.db')
 for _ in range(2):assert web.search({'求职','张三','test@example.org'},connect)['status']=='SEARCHED'
 assert len(called)==1
 payload=json.loads(called[0].data)
 assert '张三' not in payload['query'] and 'test@example.org' not in payload['query']
 assert 'ori_question' not in payload and 'localization' not in payload
 with connect() as c:
  assert c.execute("SELECT COUNT(*) FROM provider_calls WHERE model='deepseek-search'").fetchone()[0]==1
  assert c.execute('SELECT reserved_aud FROM provider_calls').fetchone()[0]>0

@pytest.mark.parametrize('url',['http://127.0.0.1/a','http://169.254.169.254/latest','file:///etc/passwd','https://localhost/','https://name:password@example.org/'])
def test_search_references_reject_local_and_credential_urls(url):assert not web.public_url(url)

def test_search_daily_cap_is_distinct_and_does_not_retry(tmp_path,monkeypatch):
 monkeypatch.setenv('DEEPSEEK_API_KEY','unit-only-no-real-key');monkeypatch.setenv('WEB_SEARCH_DAILY_LIMIT','0')
 monkeypatch.setattr(web,'urlopen',lambda *a,**k:(_ for _ in ()).throw(AssertionError('must not call')))
 assert web.search({'求职'},lambda:sqlite3.connect(tmp_path/'calls.db'))['status']=='LIMIT_REACHED'

def test_removed_legacy_limits_have_no_runtime_code_or_effect():
 source=Path(app.__file__).read_text()
 for word in ('FREE_DAILY_LIMIT','IP_DAILY_LIMIT','PAID_DAILY_LIMIT','GLOBAL_DAILY_LIMIT','consume_quota','paid-retry:'):
  assert word not in source

def test_purchased_account_can_submit_more_than_three_distinct_questions_same_day(client,monkeypatch):
 uid=add_user(client,credits=5)
 # First question is trial, next three use purchased credits, under hourly/global safeguards.
 model=Model([initial(),initial(),full(),initial(),full(),initial(),full()]);monkeypatch.setattr(app,'OpenAI',lambda **kw:model)
 for i in range(4):assert submit(client,question='第'+str(i)+'个问题：我什么时候能拿到offer？').status_code==302
 assert app.members.balance(uid)==2 and len(model.calls)==7
