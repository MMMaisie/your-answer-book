import base64,time
import pytest
import app as site
import protection
from protection import Protection,Limited,QuotaUsed,BudgetExceeded,bounded_client
from conftest import Model,initial,submit,csrf

def auth(password='private-unit-password'):
 return {'Authorization':'Basic '+base64.b64encode(('tester:'+password).encode()).decode()}

def test_first_fast_repeat_is_short_and_five_violations_escalate(client,monkeypatch):
 clock=[1000.];monkeypatch.setattr(protection.time,'time',lambda:clock[0])
 p=site.protect
 with site.app.test_request_context('/'):
  site.session['owner']='rate-browser';p.rate()
  for n in range(1,6):
   with pytest.raises(Limited):p.rate()
   with site.store.connect() as c:row=c.execute('SELECT * FROM ab49_rates LIMIT 1').fetchone()
   assert row['blocked_until']==(1900 if n==5 else 1030)
  clock[0]=1100
  with pytest.raises(Limited):p.rate()
  with site.store.connect() as c:assert c.execute('SELECT * FROM ab49_rates LIMIT 1').fetchone()['blocked_until']==1900
  clock[0]=1901;p.rate()

def test_one_misclick_does_not_block_after_thirty_seconds(client,monkeypatch):
 clock=[1000.];monkeypatch.setattr(protection.time,'time',lambda:clock[0])
 with site.app.test_request_context('/'):
  site.session['owner']='short-cooldown';site.protect.rate()
  with pytest.raises(Limited):site.protect.rate()
  clock[0]=1031;site.protect.rate()

@pytest.mark.parametrize('password,mode,provided,enabled,expected',[
 ('pw','test','pw','1',True),('pw','test','wrong','1',False),
 ('pw','live','pw','1',False),('','test','','1',False),
 ('pw','test','pw','0',False),
])
def test_private_bypass_requires_all_conditions(client,monkeypatch,password,mode,provided,enabled,expected):
 monkeypatch.setenv('SITE_ACCESS_PASSWORD',password);monkeypatch.setenv('STRIPE_MODE',mode);monkeypatch.setenv('PRIVATE_TEST_UNLIMITED',enabled)
 with site.app.test_request_context('/',headers=auth(provided)):
  site.session['owner']='private';assert site.protect.private_test_unlimited() is expected

def test_private_tester_repeated_casts_get_free_previews_without_changing_public_quota(client,monkeypatch):
 monkeypatch.setenv('SITE_ACCESS_PASSWORD','private-unit-password');monkeypatch.setenv('PRIVATE_TEST_UNLIMITED','1')
 m=Model([initial(),initial(),initial()]);monkeypatch.setattr(site,'OpenAI',lambda **kw:m)
 client.environ_base['HTTP_AUTHORIZATION']=auth()['Authorization']
 for i in range(3):assert submit(client,'找对象'+str(i)).status_code==302
 assert len(m.calls)==3
 with site.store.connect() as c:
  assert c.execute("SELECT COUNT(*) AS n FROM ab49_readings WHERE free_zh<>''").fetchone()['n']==3
  assert c.execute('SELECT COUNT(*) AS n FROM ab49_trials').fetchone()['n']==0
 monkeypatch.setenv('PRIVATE_TEST_UNLIMITED','0')
 # Same visitor now obeys the ordinary daily allowance again.
 with site.app.test_request_context('/',headers=auth()):
  site.session['owner']='private';rid=site.protect.reserve_trial();site.protect.finish_trial(rid,True)
  with pytest.raises(QuotaUsed):site.protect.reserve_trial()

def test_test_switch_does_not_bypass_site_login_or_ai_budget(client,monkeypatch):
 monkeypatch.setenv('SITE_ACCESS_PASSWORD','private-unit-password');monkeypatch.setenv('PRIVATE_TEST_UNLIMITED','1')
 assert client.get('/').status_code==401
 monkeypatch.setenv('AI_ENABLED','0');m=Model([initial()])
 with site.app.test_request_context('/',headers=auth()):
  assert site.protect.private_test_unlimited()
  with pytest.raises(BudgetExceeded):bounded_client(m,site.store).chat.completions.create(model='deepseek-v4-pro',messages=[])
 assert not m.calls

def test_busy_paid_generation_redirects_without_verification_or_spend(client,model,monkeypatch):
 submit(client)
 with site.store.connect() as c:
  r=c.execute('SELECT * FROM ab49_readings').fetchone();c.execute("UPDATE ab49_readings SET paid_mode='test' WHERE id=?",(r['id'],))
 token=site.store.acquire('reading:'+r['id'],1200)
 def forbidden(action):raise AssertionError('busy replay must not verify or call model')
 monkeypatch.setattr(site.protect,'verify',forbidden)
 response=client.post('/r/'+r['access']+'/generate',data={'csrf':csrf(client)})
 assert response.status_code==302 and len(model.calls)==1
 page=client.get(response.location)
 assert '正在生成，请稍候' in page.text and '刷新查看结果' in page.text
 site.store.release('reading:'+r['id'],token)
