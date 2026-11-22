import json
import pytest
import simple_reading as e
from test_completion_retry import Completion
from conftest import initial,review,full,Model
from hexagrams import build_cast

@pytest.mark.parametrize('stage',['writer','translation'])
def test_copy_stages_disable_thinking(stage):
 m=Completion([('stop','bad json'),('stop','{"ok":true}')])
 assert e._request(m,'deepseek-v4-pro',[],lambda v:v,4096,stage)=={'ok':True}
 assert [c['max_tokens'] for c in m.calls]==[4096,8192]
 for c in m.calls:
  assert c['extra_body']['thinking']['type']=='disabled'
  assert 'reasoning_effort' not in c

@pytest.mark.parametrize('stage',['initial','review'])
def test_analysis_stays_thinking(stage):
 m=Completion([('stop','{"ok":true}')]);e._request(m,'deepseek-v4-pro',[],lambda v:v,4096,stage)
 assert m.calls[0]['extra_body']['thinking']['type']=='enabled'

def test_actual_writer_uses_copy_mode():
 cast=build_cast([2]*6);m=Model([full()])
 e.generate_paid(m,'他是适合结婚的对象吗',cast,'deepseek-v4-pro',initial(),reviewed_plan=review())
 assert m.calls[0]['max_tokens']==4096
 assert m.calls[0]['extra_body']['thinking']['type']=='disabled'
 assert '具体对象' in e.ACCURACY
