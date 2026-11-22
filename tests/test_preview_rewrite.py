import copy,json
import pytest
import app as site
import simple_reading as e
from conftest import Model,initial,submit
from hexagrams import build_cast
from reading_contract import ReadingValidationError
CAST=build_cast([2]*6)

@pytest.mark.parametrize('question',['生产能顺利吗','生孩子会顺利吗','我什么时候找到对象','我能拿到offer吗','这套房适合买吗'])
def test_only_preview_is_rewritten_and_internal_judgement_preserved(question):
 original=initial(CAST);original['free']['direction']='用神受制，目前推进偏慢。'
 m=Model([copy.deepcopy(original),{'free':{'direction':'目前推进偏慢，暂时不宜认定过程会一路顺利。'}}])
 result=e.generate(m,question,CAST,'deepseek-v4-pro')['bundle']
 for k in ['analysis','outlook','fact_checks','decision_record']:assert result[k]==original[k]
 prompt=json.loads(m.calls[1]['messages'][1]['content'])
 assert prompt['question']==question
 assert set(prompt)=={'question','outlook','original_preview'}
 assert 'reference' not in prompt and len(m.calls)==2
 assert 'paid' not in result

def test_incorrect_facts_are_not_salvaged_by_preview_edit():
 bad=initial(CAST);bad['free']['direction']='用神受制。';bad['fact_checks'][0]['claim']['kin']='父母'
 m=Model([bad,bad])
 with pytest.raises(ReadingValidationError) as err:e.generate(m,'生产能顺利吗',CAST,'deepseek-v4-pro')
 assert err.value.reason=='evidence'
 assert 'reference' in json.loads(m.calls[1]['messages'][1]['content'])

def test_rewrite_cannot_change_outlook_or_return_full_reinterpretation():
 bad=initial(CAST);bad['free']['direction']='用神受制。'
 m=Model([bad,{'outlook':'favorable','free':{'direction':'一定成功。'}}])
 with pytest.raises(ReadingValidationError) as err:e.generate(m,'生产能顺利吗',CAST,'deepseek-v4-pro')
 assert err.value.detail=='prose_fields' and len(m.calls)==2

def test_second_jargon_failure_does_not_trigger_unbounded_calls():
 bad=initial(CAST);bad['free']['direction']='用神受制。'
 m=Model([bad,{'free':{'direction':'需要等出空。'}}])
 with pytest.raises(ReadingValidationError) as err:e.generate(m,'生产能顺利吗',CAST,'deepseek-v4-pro')
 assert err.value.detail=='preview_jargon' and len(m.calls)==2

def test_initial_failure_does_not_claim_payment_confirmation(client,monkeypatch):
 m=Model([RuntimeError('provider unavailable')]);monkeypatch.setattr(site,'OpenAI',lambda **kw:m)
 response=submit(client,question='生产能顺利吗')
 assert '本次解读未完成' in response.text
 assert '已确认的付款仍有效' not in response.text
