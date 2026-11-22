import copy
import pytest
import simple_reading as e
from hexagrams import build_cast
from conftest import review,Model
from reading_contract import EvidenceError,ReadingValidationError
CAST=build_cast([2]*6)
def value():
 v=review();v.pop('fact_checks');v['fact_ids']=['1.state'];return v

def test_valid_reason_id_added_to_canonical_evidence():
 v=value();v['reasons'][0]['fact_ids']=['2.state']
 got=e._check_review(v,CAST,{'focal':{}},'结婚','mixed')
 assert {x['fact_id'] for x in got['fact_checks']}=={'1.state','2.state'}
 assert v['fact_ids']==['1.state']

@pytest.mark.parametrize('ids,code',[([], 'evidence_reason_missing'),(None,'evidence_reason_missing'),(['7.state'],'evidence_reference'),(['1.state']*5,'evidence_reason_count')])
def test_bad_refs_still_rejected_with_precise_code(ids,code):
 v=value();v['reasons'][0]['fact_ids']=ids
 with pytest.raises(EvidenceError) as err:e._check_review(v,CAST,{'focal':{}},'结婚','mixed')
 assert err.value.code==code

def test_missing_reason_retry_explains_actual_problem():
 bad=value();bad['reasons'][0].pop('fact_ids');good=value();m=Model([bad,good])
 check=lambda v:e._check_review(v,CAST,{'focal':{}},'结婚','mixed')
 assert e._request(m,'deepseek-v4-pro',[],check,16384,'review')['fact_checks']
 assert '每个reasons条目' in m.calls[1]['messages'][-1]['content']

def test_legacy_snapshot_does_not_gain_unchecked_refs():
 v=review();v['reasons'][0]['fact_ids']=['2.state']
 with pytest.raises(EvidenceError):e._check_review(v,CAST,{'focal':{}},'结婚','mixed')
