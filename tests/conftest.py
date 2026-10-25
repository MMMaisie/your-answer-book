import os,sys,base64,json,secrets,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
from types import SimpleNamespace as NS
import app as site
from membership import SCHEMA
from werkzeug.security import generate_password_hash

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

def initial():return {'outlook':'mixed','analysis':'以求职或问事对象为中心比较支持与限制，不把倾向当作已经发生。','free':{'direction':'目前有推进的机会，但结果还未明朗，暂时不能认定已经稳妥。'},'sources':[{'id':'focal'}]}
def full(outlook='mixed'):return {'outlook':outlook,'paid':{'priorities':'这件事有推进的空间，仍需区分眼前的支持和已经落实的结果。判断要围绕所问的目标，结合自身处境与外部条件比较。','conditions':'主要限制仍有待解除，不能只凭一时顺利就认定结局。若支持继续发挥、原有限制减轻，原来的机会才更有实际意义。','actions':'先核对已经确认的进展与尚未落实的环节，再决定投入多少精力；同时保留其他选择，避免把所有安排建立在一个未经确认的结果上。'}}

def csrf(c):
 c.get('/')
 with c.session_transaction() as s:return s['csrf']
def submit(c,question='我什么时候能拿到offer？',time_value='2026-10-24T20:00'):
 return c.post('/',data={'csrf':csrf(c),'question':question,'cast_time':time_value,'timezone':'Australia/Adelaide',**{f'word{i}':'2' for i in range(1,7)}})
def add_user(c,email='test@example.org',credits=0,verified=True):
 uid=secrets.token_hex(12)
 with site.connect() as db:
  db.execute('INSERT INTO accounts VALUES(?,?,?, ?,0,?)',(uid,email,generate_password_hash('a-long-test-password'),int(verified),time.time()))
  if credits:db.execute('INSERT INTO credit_ledger VALUES(?,?,?,?,?)',('grant:'+uid,uid,credits,site.STRIPE_MODE+':test-grant',time.time()))
 with c.session_transaction() as s:s['account_id']=uid;s['account_version']=0;s['owner']='acct:'+uid
 return uid

@pytest.fixture
def client(tmp_path,monkeypatch):
 monkeypatch.setenv('SITE_ACCESS_PASSWORD','only-for-unit-tests');monkeypatch.setenv('AI_DAILY_REQUEST_LIMIT','100');monkeypatch.setenv('AI_DAILY_BUDGET_AUD','100')
 site.app.config.update(TESTING=True,DB_PATH=str(tmp_path/'readings.db'),SESSION_COOKIE_SECURE=False)
 site.init_db()
 with site.connect() as db:db.executescript(SCHEMA)
 monkeypatch.setattr(site,'AI_KEY','unit-only-not-a-key');monkeypatch.setattr(site,'STRIPE_MODE','test');monkeypatch.setattr(site,'STRIPE_TEST_MODE',True);monkeypatch.setattr(site,'STRIPE_ENV_PREFIX','STRIPE_TEST_');monkeypatch.setattr(site,'PAYMENT_STATUS','test_paid')
 c=site.app.test_client();c.environ_base['HTTP_AUTHORIZATION']='Basic '+base64.b64encode(b'tester:only-for-unit-tests').decode()
 return c

@pytest.fixture
def model(monkeypatch):
 m=Model([initial(),full()]);monkeypatch.setattr(site,'OpenAI',lambda **kw:m)
 return m
