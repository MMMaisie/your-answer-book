import json
from types import SimpleNamespace as NS
import pytest
from simple_reading import _request
from reading_contract import ReadingValidationError

class Completion:
 def __init__(self,replies):
  self.replies=iter(replies);self.calls=[]
  self.chat=NS(completions=NS(create=self.create))
 def create(self,**kwargs):
  self.calls.append(kwargs)
  reason,content=next(self.replies)
  return NS(choices=[NS(finish_reason=reason,message=NS(content=content))])

def test_length_retry_discards_partial_and_keeps_bounds():
 m=Completion([('length','SECRET_PARTIAL'),('stop','{"ok":true}')])
 assert _request(m,'deepseek-v4-pro',[{'role':'user','content':'original'}],lambda x:x)=={'ok':True}
 assert [c['max_tokens'] for c in m.calls]==[4096,8192]
 assert 'SECRET_PARTIAL' not in json.dumps(m.calls[1]['messages'])
 assert m.calls[1]['messages'][0]['content']=='original'

@pytest.mark.parametrize('reason',['length','content_filter','tool_calls','insufficient_system_resource','aborted',None,'secret\nvalue'])
def test_safe_reason_and_bounded_failure(reason):
 replies=[('length','partial'),(reason,'partial')] if reason=='length' else [(reason,'partial')]
 m=Completion(replies)
 with pytest.raises(ReadingValidationError) as e:
  _request(m,'deepseek-v4-pro',[],lambda x:x,stage='initial')
 assert e.value.stage=='initial'
 assert e.value.reason=='incomplete'
 assert e.value.finish_reason==(reason if reason in {'length','content_filter','tool_calls','insufficient_system_resource','aborted'} else 'unknown')
 assert len(m.calls)==(2 if reason=='length' else 1)

def test_format_repair_then_length_never_third_call():
 m=Completion([('stop','not json'),('length','partial')])
 with pytest.raises(ReadingValidationError) as e:_request(m,'deepseek-v4-pro',[],lambda x:x)
 assert e.value.finish_reason=='length'
 assert len(m.calls)==2

def test_budget_exception_on_retry_is_preserved():
 m=Completion([('length','partial')])
 original=m.create
 def guarded(**kwargs):
  if m.calls:raise RuntimeError('budget blocked')
  return original(**kwargs)
 m.chat.completions.create=guarded
 with pytest.raises(RuntimeError,match='budget blocked'):
  _request(m,'deepseek-v4-pro',[],lambda x:x)
 assert len(m.calls)==1
