import json,time
from datetime import datetime,timezone
from types import SimpleNamespace as NS
import pytest
import app as site
import protection
from protection import Protection,VerificationFailed,QuotaUsed,BudgetExceeded,bounded_client
from conftest import Model,initial

class Result:
 def __init__(self,obj):self.obj=obj
 def read(self,n):return json.dumps(self.obj).encode()
 def __enter__(self):return self
 def __exit__(self,*a):pass

def test_turnstile_requires_hostname_action_freshness_and_single_use(client,monkeypatch):
 monkeypatch.setenv('TURNSTILE_SECRET_KEY','not-real');p=Protection(site.store,'secret','https://example.test')
 value={'success':True,'hostname':'example.test','action':'cast','challenge_ts':datetime.now(timezone.utc).isoformat()}
 monkeypatch.setattr(protection,'urlopen',lambda *a,**kw:Result(value))
 def verify(token='token'):
  with site.app.test_request_context('/',method='POST',data={'cf-turnstile-response':token}):p.verify('cast')
 for change in [{'hostname':'attacker.test'},{'action':'checkout'},{'challenge_ts':'2000-01-01T00:00:00+00:00'},{'success':False}]:
  old=value.copy();value.update(change)
  with pytest.raises(VerificationFailed):verify()
  value.clear();value.update(old)
 verify()
 with pytest.raises(VerificationFailed):verify()
 with pytest.raises(VerificationFailed):verify('')

def test_trial_resets_on_utc_day_and_old_claims_cleanup(client):
 p=Protection(site.store,'secret','https://example.test')
 with site.app.test_request_context('/'):
  site.session['owner']='daily-browser'
  rid=p.reserve_trial();p.finish_trial(rid,True)
  with pytest.raises(QuotaUsed):p.reserve_trial()
  with site.store.connect() as c:c.execute("UPDATE ab49_trials SET day='2000-01-01',created=?",(time.time()-4*86400,))
  assert p.reserve_trial()
 site.store.cleanup(force=True)
 with site.store.connect() as c:assert c.execute('SELECT COUNT(*) AS n FROM ab49_trials').fetchone()['n']==2

def test_provider_failures_and_missing_usage_keep_reservation(client):
 m=Model([RuntimeError('secret vendor response')]);wrapped=bounded_client(m,site.store)
 with pytest.raises(RuntimeError):wrapped.chat.completions.create(model='deepseek-v4-pro',messages=[],max_tokens=100)
 with site.store.connect() as c:r=c.execute('SELECT * FROM ab49_calls').fetchone()
 assert r['status']=='failed' and r['reserve']>0

def test_provider_unknown_models_and_oversized_payload_never_sent(client):
 m=Model([initial()]);wrapped=bounded_client(m,site.store)
 for kwargs in [dict(model='other-model',messages=[]),dict(model='deepseek-v4-pro',messages=[{'role':'user','content':'x'*100000}])]:
  with pytest.raises(BudgetExceeded):wrapped.chat.completions.create(**kwargs)
 assert not m.calls

def test_transaction_rollback_and_no_stale_trial_leak(client):
 with pytest.raises(RuntimeError):
  with site.store.connect() as c:
   c.execute('INSERT INTO ab49_meta VALUES(?,?)',('rollback',1));raise RuntimeError()
 with site.store.connect() as c:assert not c.execute("SELECT * FROM ab49_meta WHERE name='rollback'").fetchone()

def test_optional_source_format_does_not_spend_extra_call_but_unknown_is_rejected(client):
 import simple_reading as e
 cast=site.build_cast(['2']*6)
 for sources in [None,[]]:
  value=initial();value['sources']=sources;m=Model([value]);assert e.generate(m,'找对象',cast,'deepseek-v4-pro')['bundle']['sources']==[];assert len(m.calls)==1

def test_decision_record_unknown_facts_not_allowed(client):
 import simple_reading as e
 cast=site.build_cast(['2']*6);value=initial();value['decision_record']['fact_ids']=['invented']
 with pytest.raises(ValueError):e.generate(Model([value,value]),'找对象',cast,'deepseek-v4-pro')

def test_internal_foundation_errors_rejected_even_when_free_prose_is_valid(client):
 import simple_reading as e
 value=initial();value['analysis']='水克土，所以有利。'
 with pytest.raises(ValueError):e.generate(Model([value,value]),'找对象',site.build_cast(['2']*6),'deepseek-v4-pro')

def test_rule_context_keeps_core_and_excludes_irrelevant_topics(client):
 import simple_reading as e
 d,refs=e.context('找对象',site.build_cast(['2']*6))
 assert {'five_elements','focal','self_other','QA-01'}<=set(refs)
 assert 'TOP-REL' in refs and 'TOP-HEALTH' not in refs
 assert len(d['book_rules'])<=40
 assert d['reference_metadata']['reference_hash']

def test_paid_uses_saved_reference_snapshot_across_rule_updates(client,monkeypatch):
 import simple_reading as e
 from conftest import full
 cast=site.build_cast(['2']*6);m=Model([initial(),full()]);stored=e.generate(m,'找对象',cast,'deepseek-v4-pro')
 snapshot=stored['reference_snapshot']
 monkeypatch.setattr(e,'RULES',[])
 e.generate_paid(m,'找对象',cast,'deepseek-v4-pro',stored['bundle'],reference_snapshot=snapshot)
 task=json.loads(m.calls[-1]['messages'][1]['content'])
 assert task['reference']['book_rules']==snapshot['book_rules']

def test_free_search_never_executes_even_when_requested(client):
 import simple_reading as e
 value=initial();value['needs_web']=True;calls=[]
 e.generate(Model([value]),'冷门的问题',site.build_cast(['2']*6),'deepseek-v4-pro',lambda *a:calls.append(a))
 assert not calls
