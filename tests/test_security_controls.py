import base64,sqlite3,threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace as NS
import pytest
from flask import Flask
from security_controls import bounded_client,private_access,CallLimitError

def connection(path):
 def connect():return sqlite3.connect(path,timeout=10)
 return connect

def fake_client(fn):return NS(chat=NS(completions=NS(create=fn)))

def test_private_site_rejects_anonymous_and_wrong_password(monkeypatch):
 monkeypatch.setenv('SITE_ACCESS_PASSWORD','private-test-password')
 app=Flask(__name__);app.add_url_rule('/',endpoint='home',view_func=lambda:'ok')
 for headers in ({},{'Authorization':'Basic '+base64.b64encode(b'tester:wrong').decode()}):
  with app.test_request_context('/',headers=headers):assert private_access().status_code==401
 with app.test_request_context('/',headers={'Authorization':'Basic '+base64.b64encode(b'tester:private-test-password').decode()}):assert private_access() is None

@pytest.mark.parametrize('endpoint',['health','stripe_webhook'])
def test_only_health_and_signed_webhook_bypass_private_gate(monkeypatch,endpoint):
 monkeypatch.setenv('SITE_ACCESS_PASSWORD','private-test-password')
 app=Flask(__name__);app.add_url_rule('/allowed',endpoint=endpoint,view_func=lambda:'ok')
 with app.test_request_context('/allowed'):assert private_access() is None

def test_failed_api_attempt_still_consumes_total_quota(tmp_path,monkeypatch):
 monkeypatch.setenv('AI_DAILY_REQUEST_LIMIT','1');db=connection(tmp_path/'calls.db');calls=[]
 def fail(**kwargs):calls.append(1);raise RuntimeError('upstream unavailable')
 proxy=bounded_client(fake_client(fail),db)
 with pytest.raises(RuntimeError):proxy.chat.completions.create(model='deepseek-flash')
 with pytest.raises(CallLimitError):proxy.chat.completions.create(model='deepseek-flash')
 assert len(calls)==1
 with db() as c:assert c.execute('SELECT status FROM provider_calls').fetchone()[0]=='failed'

def test_parallel_api_reservations_cannot_exceed_limit(tmp_path,monkeypatch):
 monkeypatch.setenv('AI_DAILY_REQUEST_LIMIT','2');db=connection(tmp_path/'calls.db')
 proxy=bounded_client(fake_client(lambda **kw:NS(usage=NS(prompt_tokens=123,completion_tokens=45))),db)
 def run(_):
  try:proxy.chat.completions.create(model='deepseek-flash');return 1
  except CallLimitError:return 0
 with ThreadPoolExecutor(max_workers=6) as pool:assert sum(pool.map(run,range(10)))==2
 with db() as c:
  assert c.execute('SELECT COUNT(*) FROM provider_calls').fetchone()[0]==2
  assert c.execute('SELECT SUM(prompt_tokens) FROM provider_calls').fetchone()[0]==246
  assert [r[1] for r in c.execute('PRAGMA table_info(provider_calls)')]==['id','day','model','status','prompt_tokens','completion_tokens','reserved_aud']

def test_daily_budget_blocks_before_provider_call(tmp_path,monkeypatch):
 monkeypatch.setenv('AI_DAILY_BUDGET_AUD','0.000001');calls=[]
 proxy=bounded_client(fake_client(lambda **kw:calls.append(kw)),connection(tmp_path/'calls.db'))
 with pytest.raises(CallLimitError,match='budget'):proxy.chat.completions.create(model='deepseek-v4-pro',messages=[{'role':'user','content':'a question'}],max_tokens=4096)
 assert calls==[]

def test_oversized_payload_is_rejected_before_provider(tmp_path):
 calls=[];proxy=bounded_client(fake_client(lambda **kw:calls.append(kw)),connection(tmp_path/'calls.db'))
 with pytest.raises(CallLimitError,match='input size'):proxy.chat.completions.create(model='deepseek-v4-pro',messages=[{'role':'user','content':'x'*120001}])
 assert calls==[]

def test_unapproved_model_does_not_bypass_price_guard(tmp_path):
 proxy=bounded_client(fake_client(lambda **kw:None),connection(tmp_path/'calls.db'))
 with pytest.raises(CallLimitError,match='model not allowed'):proxy.chat.completions.create(model='unexpected-expensive-model')

def test_exhausted_provider_cap_closes_checkout_capacity(tmp_path,monkeypatch):
 from security_controls import provider_capacity
 monkeypatch.setenv('AI_DAILY_REQUEST_LIMIT','1')
 db=connection(tmp_path/'calls.db')
 assert provider_capacity(db)
 proxy=bounded_client(fake_client(lambda **kw:NS(usage=None)),db)
 proxy.chat.completions.create(model='deepseek-flash',messages=[])
 assert not provider_capacity(db)
