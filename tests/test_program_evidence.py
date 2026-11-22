import copy,json
from datetime import datetime
import pytest
import app as site
import simple_reading as engine
from conftest import Model,initial,review,full,submit
from hexagrams import build_cast
from theory_facts import ledger
from reading_contract import resolve_evidence,EvidenceError,ReadingValidationError,REQUIRED
from test_guest_flow import row,paid,post_generate

CAST=build_cast([2]*6)
def selected(value):
 value=copy.deepcopy(value);value['fact_ids']=[x['fact_id'] for x in value.pop('fact_checks')];value.pop('decision_record',None);return value

def test_program_fills_every_available_fact_type():
 kinds=set()
 for words in ([2]*6,[1,2,2,1,3,1],[2,1,2,2,2,3]):
  cast=build_cast(words,datetime(2026,11,22,9,51))
  for fact in ledger(cast)['lines']:
   kind=fact['id'].split('.')[1];kinds.add(kind)
   got=resolve_evidence({'fact_ids':[fact['id']]},cast)[0]
   assert got['claim']=={k:fact[k] for k in REQUIRED[kind]}
 assert kinds==set(REQUIRED)

@pytest.mark.parametrize('ids',[[],['7.state'],['1.changed'],[None],'1.state'])
def test_invalid_selection_has_specific_safe_diagnostic(ids):
 bad=selected(initial(CAST));bad['fact_ids']=ids;m=Model([bad,bad])
 with pytest.raises(ReadingValidationError) as err:engine.generate(m,'能拿到offer吗',CAST,'deepseek-v4-pro')
 assert err.value.reason=='evidence' and err.value.detail.startswith('evidence_') and len(m.calls)==2

def test_duplicates_are_normalized():
 assert len(resolve_evidence({'fact_ids':['1.state','1.state']},CAST))==1

def test_legacy_false_snapshot_is_still_rejected():
 bad=initial(CAST);bad['fact_checks'][0]['claim']['kin']='父母'
 for extra in ({},{'fact_ids':['1.state']}):
  with pytest.raises(EvidenceError):resolve_evidence(dict(bad,**extra),CAST)

def test_conflicting_formats_rejected():
 bad=initial(CAST);bad['fact_ids']=['2.state']
 with pytest.raises(EvidenceError) as err:resolve_evidence(bad,CAST)
 assert err.value.code=='evidence_conflict'

def test_id_only_preview_edit_preserves_evidence():
 bad=selected(initial(CAST));bad['free']['direction']='用神受制，目前推进偏慢。'
 m=Model([bad,{'free':{'direction':'目前推进偏慢，暂时不宜认定过程会一路顺利。'}}])
 result=engine.generate(m,'何时能拿到offer',CAST,'deepseek-v4-pro')['bundle']
 assert result['fact_checks']==resolve_evidence(bad,CAST)
 assert len(m.calls)==2

def test_id_only_paid_flow_saves_and_exports(client,monkeypatch):
 m=Model([selected(initial()),selected(review()),full()]);monkeypatch.setattr(site,'OpenAI',lambda **kw:m)
 assert submit(client).status_code==302
 r=row(client);assert r['free_zh'] and not r['paid_zh'];paid(r)
 assert post_generate(client,r).status_code==302
 r=row(client);assert r['paid_zh'] and len(m.calls)==3
 assert client.get('/r/'+r['access']).status_code==200
 assert client.get('/r/'+r['access']+'/download.pdf').data.startswith(b'%PDF')
 for call in m.calls[:2]:
  task=json.loads(call['messages'][1]['content'])
  assert 'fact_ids' in task['schema'] and 'fact_checks' not in task['schema']
