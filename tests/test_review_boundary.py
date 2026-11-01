import pytest
import simple_reading as engine
from reading_contract import EditorialError,ReadingValidationError,validate_reader_text
from conftest import Model,review
from hexagrams import build_cast

CAST=build_cast([2]*6)
def test_internal_brief_repetition_goes_to_writer_not_rejected():
 r=review()
 r['watch']=r['answer']
 assert engine._check_review(r,CAST,{'focal':{}},'问工作','mixed')['watch']==r['watch']
 with pytest.raises(EditorialError) as e:
  validate_reader_text(r['answer']+'。'+r['watch'],'paid')
 assert e.value.code=='repetition'

def test_internal_brief_density_is_editor_responsibility():
 text='用神、原神、忌神、世爻、应爻'
 assert validate_reader_text(text,'paid',check_style=False)==text
 with pytest.raises(EditorialError) as e:validate_reader_text(text,'paid')
 assert e.value.code=='paid_jargon'

def test_internal_brief_still_rejects_unprovided_personal_inference():
 r=review();r['watch']='你需要先恢复精力。'
 with pytest.raises(EditorialError) as e:
  engine._check_review(r,CAST,{'focal':{}},'问工作','mixed')
 assert e.value.code=='personal_inference'

def test_reviewed_public_preview_stays_strict_and_is_identified():
 r=review();r['revised_free']='需要等待用神出空。'
 with pytest.raises(EditorialError) as e:
  engine._check_review(r,CAST,{'focal':{}},'问工作','mixed')
 assert e.value.code=='review_preview_jargon'

def test_editorial_failure_logs_safe_detail_and_stop():
 m=Model([{},{}])
 def check(_):raise EditorialError('private content','review_preview_jargon')
 with pytest.raises(ReadingValidationError) as e:
  engine._request(m,'deepseek-v4-pro',[],check,stage='review')
 assert e.value.detail=='review_preview_jargon'
 assert e.value.finish_reason=='stop'
 assert 'private content' not in str(e.value)

def test_arbitrary_detail_is_not_logged():
 assert ReadingValidationError('review','editorial','stop','secret').detail=='unspecified'
 assert ReadingValidationError('review','editorial','stop',[]).detail=='unspecified'
