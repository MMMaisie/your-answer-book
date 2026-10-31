import os,sys,json
from pathlib import Path
os.environ.setdefault('FLASK_SECRET_KEY','local-unit-tests-only-never-deploy-this-secret')
os.environ.setdefault('STRIPE_MODE','test')
os.environ.setdefault('DB_PATH','/tmp/answerbook-import-v49.sqlite3')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
from types import SimpleNamespace as NS
import app as site
from storage import Store
from protection import Protection
class Model:
 def __init__(self,replies):self.replies=list(replies);self.calls=[];self.chat=NS(completions=NS(create=self.create))
 def create(self,**kwargs):
  self.calls.append(kwargs)
  if not self.replies:raise AssertionError('unexpected provider call')
  r=self.replies.pop(0)
  if isinstance(r,Exception):raise r
  return NS(choices=[NS(finish_reason='stop',message=NS(content=r if isinstance(r,str) else json.dumps(r,ensure_ascii=False)))],usage=NS(prompt_tokens=1000,completion_tokens=100))
 def __enter__(self):return self
 def __exit__(self,*args):return False

def initial():return {'outlook':'mixed','analysis':'围绕所问比较支持与限制，不把倾向当作已发生的事实。','free':{'direction':'目前有推进的机会，结果仍有变数，尚不能认定稳妥。'},'sources':[{'id':'focal'}],'decision_record':{'focal_positions':[1],'fact_ids':['1.state'],'uncertainties':['问意未说明的关系身份不作猜测']}}
def full(outlook='mixed'):return {'outlook':outlook,'paid':{'priorities':'这件事有推进空间，仍需区分眼前支持和已经落实的结果。','conditions':'若支持持续、限制减轻，机会才更有实际意义；不能只凭一时顺利认定结局。','actions':'先核对已经确认的进展，再决定投入多少精力，同时保留其他选择。'}}
def csrf(c):
 c.get('/')
 with c.session_transaction() as s:return s['csrf']
def submit(c,question='我什么时候能拿到offer？',time_value='2026-10-31T12:00',ip='203.0.113.10'):
 return c.post('/',data={'csrf':csrf(c),'question':question,'cast_time':time_value,'timezone':'Australia/Adelaide','cf-turnstile-response':'test-token',**{f'word{i}':'2' for i in range(1,7)}},environ_overrides={'REMOTE_ADDR':ip})
@pytest.fixture
def client(tmp_path,monkeypatch):
 st=Store(path=str(tmp_path/'test.db'));st.init();monkeypatch.setattr(site,'store',st);monkeypatch.setattr(site,'protect',Protection(st,'test-secret','https://example.test'))
 site.app.config.update(TESTING=True,SESSION_COOKIE_SECURE=False)
 monkeypatch.setattr(site,'AI_KEY','not-a-real-key');monkeypatch.setattr(site,'PUBLIC_URL','https://example.test');monkeypatch.setattr(site,'STRIPE_MODE','test')
 monkeypatch.setenv('AI_DAILY_BUDGET_AUD','100');monkeypatch.setenv('AI_DAILY_REQUEST_LIMIT','100');monkeypatch.delenv('SITE_ACCESS_PASSWORD',raising=False)
 monkeypatch.setattr(site.protect,'verify',lambda action:None)
 return site.app.test_client()
@pytest.fixture
def model(monkeypatch):
 m=Model([initial(),full()]);monkeypatch.setattr(site,'OpenAI',lambda **kw:m);return m
