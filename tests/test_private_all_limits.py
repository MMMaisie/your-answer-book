import base64,time
from datetime import datetime,timezone
import pytest
import app as site
from protection import bounded_client,capacity,BudgetExceeded
from conftest import Model,initial

def auth(password='private-unit-password'):
 return {'Authorization':'Basic '+base64.b64encode(('tester:'+password).encode()).decode()}

@pytest.mark.parametrize('model',['deepseek-v4-pro','deepseek-search'])
def test_authenticated_test_ignores_every_usage_limit(client,monkeypatch,model):
 for key,value in {'SITE_ACCESS_PASSWORD':'private-unit-password','PRIVATE_TEST_UNLIMITED':'1','AI_DAILY_BUDGET_CNY':'0.000001','AI_DAILY_REQUEST_LIMIT':'0','AI_MAX_CONCURRENT':'0','WEB_SEARCH_DAILY_LIMIT':'0'}.items():monkeypatch.setenv(key,value)
 day=datetime.now(timezone.utc).strftime('%Y-%m-%d')
 with site.store.connect() as c:c.execute('INSERT INTO ab49_calls(id,day,model,status,reserve,created) VALUES(?,?,?,?,?,?)',('active',day,model,'reserved',999,time.time()))
 m=Model([initial(),initial()])
 with site.app.test_request_context('/',headers=auth()):
  site.session['owner']='test'
  assert capacity(site.store,999999)
  assert site.delivery_capacity({},'en')
  for _ in range(2):
   site.protect.rate('new');assert site.protect.reserve_trial()=='private-test-unlimited'
   bounded_client(m,site.store).chat.completions.create(model=model,messages=[],max_tokens=10)
 assert len(m.calls)==2
 with site.store.connect() as c:
  rows=c.execute("SELECT * FROM ab49_calls WHERE id!='active'").fetchall()
 assert len(rows)==2 and all(x['status']=='completed' and x['reserve']==0 for x in rows)

@pytest.mark.parametrize('mode,password,flag',[('live','private-unit-password','1'),('test','wrong','1'),('test','private-unit-password','0')])
def test_public_live_wrong_password_and_disabled_flag_keep_limits(client,monkeypatch,mode,password,flag):
 monkeypatch.setenv('SITE_ACCESS_PASSWORD','private-unit-password');monkeypatch.setenv('PRIVATE_TEST_UNLIMITED',flag);monkeypatch.setenv('STRIPE_MODE',mode);monkeypatch.setenv('AI_DAILY_REQUEST_LIMIT','0')
 m=Model([initial()])
 with site.app.test_request_context('/',headers=auth(password)):
  assert not capacity(site.store)
  with pytest.raises(BudgetExceeded):bounded_client(m,site.store).chat.completions.create(model='deepseek-v4-pro',messages=[])
 assert not m.calls

def test_no_request_context_never_bypasses(client,monkeypatch):
 monkeypatch.setenv('PRIVATE_TEST_UNLIMITED','1');monkeypatch.setenv('SITE_ACCESS_PASSWORD','private-unit-password');monkeypatch.setenv('AI_DAILY_REQUEST_LIMIT','0')
 assert not capacity(site.store)

@pytest.fixture(autouse=True)
def explicit_legacy_development_mode(monkeypatch):
 monkeypatch.setenv("SAFETY_LIMITS_ENFORCED","0")
