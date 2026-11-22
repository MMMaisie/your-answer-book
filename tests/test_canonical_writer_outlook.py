import json
import pytest
import simple_reading as e
from conftest import Model,initial,review,full
from hexagrams import build_cast

@pytest.mark.parametrize('label',[None,'favorable','difficult','unclear','other'])
def test_writer_label_does_not_replace_reviewed_outlook(label):
 v=full();v.pop('outlook')
 if label is not None:v['outlook']=label
 m=Model([v]);cast=build_cast([2]*6);plan=review()
 result=e.generate_paid(m,'他适合结婚吗',cast,'deepseek-v4-pro',initial(),reviewed_plan=plan)
 assert result==v['paid'] and plan['outlook']=='mixed' and len(m.calls)==1
 task=json.loads(m.calls[0]['messages'][1]['content'])
 assert 'outlook' not in task['schema']

def test_writer_invalid_prose_still_rejected():
 from reading_contract import ReadingValidationError
 m=Model([{'paid':{}},{'paid':{}}]);cast=build_cast([2]*6)
 with pytest.raises(ReadingValidationError):e.generate_paid(m,'他适合结婚吗',cast,'deepseek-v4-pro',initial(),reviewed_plan=review())
 assert len(m.calls)==2
