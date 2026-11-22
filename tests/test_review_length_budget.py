import json
from types import SimpleNamespace as NS
import pytest
import simple_reading as e
import app as site
from hexagrams import build_cast
from protection import bounded_client
from reading_contract import ReadingValidationError
from conftest import review,initial,Model
from test_completion_retry import Completion
CAST=build_cast([2]*6)

def test_paid_review_length_retry_has_real_higher_cap(client,monkeypatch):
 replies=[('length','partial-secret'),('stop',json.dumps(review(),ensure_ascii=False))]
 m=Completion(replies)
 plan=e.review_paid(bounded_client(m,site.store,max_output_tokens=32768),'这套房值得买吗',CAST,'deepseek-v4-pro',initial())
 assert plan['outlook']=='mixed'
 assert [x['max_tokens'] for x in m.calls]==[16384,32768]
 assert all(x['extra_body']['thinking']['type']=='enabled' for x in m.calls)
 assert 'partial-secret' not in json.dumps(m.calls[1]['messages'])

def test_paid_review_twice_length_stops_and_records_actual_budget(client):
 m=Completion([('length','partial'),('length','partial')])
 with pytest.raises(ReadingValidationError) as err:
  e.review_paid(bounded_client(m,site.store,max_output_tokens=32768),'买房',CAST,'deepseek-v4-pro',initial())
 assert err.value.stage=='review' and err.value.finish_reason=='length'
 assert (err.value.attempt,err.value.max_tokens)==(2,32768)
 assert len(m.calls)==2

def test_ordinary_stages_still_have_old_cap(client):
 m=Model([{}])
 bounded_client(m,site.store).chat.completions.create(model='deepseek-v4-pro',messages=[],max_tokens=32768)
 assert m.calls[0]['max_tokens']==8192

def test_review_prompt_does_not_replay_old_technical_record():
 core=initial();core['analysis']='old-only-analysis';core['fact_checks'][0]['claim']['test_marker']='must-not-replay'
 m=Model([review()])
 e.review_paid(m,'买房',CAST,'deepseek-v4-pro',core)
 payload=json.loads(m.calls[0]['messages'][1]['content'])
 assert set(payload['previous_initial'])=={'outlook','free'}
 assert 'test_marker' not in json.dumps(payload)
 assert e.VOICE not in m.calls[0]['messages'][0]['content']

def test_topic_grid_is_borderless_and_three_columns(client):
 from pathlib import Path
 html=client.get('/').text
 assert html.count('<li>')==9
 css=(Path(e.__file__).parent/'static/site.css').read_text()
 final=css.split('/* Three rows of three labels;')[1]
 assert 'repeat(3,minmax(0,1fr))' in final and 'border:0' in final
 assert 'content:"·"' in final and 'font:inherit' in final
