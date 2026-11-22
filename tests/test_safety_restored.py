import base64
import pytest
import app as site
from protection import private_test_unlimited,Limited,QuotaUsed,BudgetExceeded,bounded_client
from conftest import Model,initial

@pytest.mark.parametrize('setting',[None,'1','true','invalid'])
def test_old_test_flag_cannot_disable_restored_limits(client,monkeypatch,setting):
 if setting is None:monkeypatch.delenv('SAFETY_LIMITS_ENFORCED',raising=False)
 else:monkeypatch.setenv('SAFETY_LIMITS_ENFORCED',setting)
 monkeypatch.setenv('PRIVATE_TEST_UNLIMITED','1');monkeypatch.setenv('SITE_ACCESS_PASSWORD','pw');monkeypatch.setenv('STRIPE_MODE','test')
 headers={'Authorization':'Basic '+base64.b64encode(b'tester:pw').decode()}
 m=Model([initial()])
 with site.app.test_request_context('/',headers=headers):
  site.session['owner']='restored'
  assert not private_test_unlimited()
  site.protect.rate()
  with pytest.raises(Limited):site.protect.rate()
  rid=site.protect.reserve_trial();site.protect.finish_trial(rid,True)
  with pytest.raises(QuotaUsed):site.protect.reserve_trial()
  monkeypatch.setenv('AI_DAILY_REQUEST_LIMIT','0')
  with pytest.raises(BudgetExceeded):bounded_client(m,site.store).chat.completions.create(model='deepseek-v4-pro',messages=[])
 assert not m.calls
 health=client.get('/healthz').get_json()
 assert health['safety_limits_enforced'] and not health['private_test_unlimited']
