import pytest
import simple_reading as e
from reading_contract import ContentValidationError,ReadingValidationError
from conftest import Model,full
from hexagrams import build_cast
CAST=build_cast([2]*6)

def validate(v):
 if v.get('outlook')!='mixed':raise ContentValidationError('writer_outlook')
 return e.check_parts(v.get('paid'),'paid','zh',CAST,'找工作')

@pytest.mark.parametrize('code,bad',[
 ('prose_fields',{'outlook':'mixed','paid':{}}),
 ('prose_markup',{'outlook':'mixed','paid':{'priorities':'<b>内容</b>','conditions':'理由','actions':'观察'}}),
 ('prose_length',{'outlook':'mixed','paid':{'priorities':'字'*301,'conditions':'理由','actions':'观察'}}),
 ('writer_outlook',full('favorable')),
 ('specific_timing',{'outlook':'mixed','paid':{'priorities':'2026年12月1日会落实。','conditions':'理由','actions':'观察'}}),
 ('json_syntax','broken json')])
def test_targeted_repair_then_valid(code,bad):
 m=Model([bad,full()])
 result=e._request(m,'deepseek-v4-pro',[],validate,stage='writer')
 assert result==full()['paid']
 assert e.REPAIR_HINTS[code] in m.calls[1]['messages'][-1]['content']
 assert len(m.calls)==2

def test_specific_failure_is_logged_and_bounded():
 m=Model([full('favorable'),full('favorable')])
 with pytest.raises(ReadingValidationError) as err:e._request(m,'deepseek-v4-pro',[],validate,stage='writer')
 assert err.value.detail=='writer_outlook'
 assert err.value.finish_reason=='stop'
 assert len(m.calls)==2

@pytest.mark.parametrize('name,code',[
 ('validate_chart_claims','chart_claim'),('validate_explicit_relations','element_relation'),
 ('validate_theory','theory_claim'),('validate_coarse_timing','specific_timing')])
def test_fact_checks_still_fail_closed_with_safe_codes(monkeypatch,name,code):
 def reject(*args):raise ValueError('private content must not enter log')
 monkeypatch.setattr(e,name,reject)
 with pytest.raises(ContentValidationError) as err:e.check_parts(full()['paid'],'paid','zh',CAST)
 assert err.value.code==code
 assert 'private' not in str(err.value)
