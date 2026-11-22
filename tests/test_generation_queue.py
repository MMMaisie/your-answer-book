import time,json
from concurrent.futures import ThreadPoolExecutor
import pytest
import app as site
import generation_queue as q
from protection import InProgress,BudgetExceeded
from conftest import Model,initial,review,full,submit,csrf
from test_guest_flow import row,paid,post_generate

@pytest.fixture
def queue_mode(client,monkeypatch):
 monkeypatch.setenv('GENERATION_QUEUE_ENABLED','1')
 return client

def test_preview_and_paid_queue_complete_and_cache(queue_mode,monkeypatch):
 c=queue_mode;m=Model([initial(),review(),full()]);monkeypatch.setattr(site,'OpenAI',lambda **kw:m)
 response=submit(c);r=row(c)
 assert response.status_code==302 and not r['free_zh'] and not m.calls
 assert '初判已排队' in c.get(response.location).text
 assert q.run_one(site) and row(c)['free_zh'] and len(m.calls)==1
 r=row(c);paid(r);post_generate(c,r)
 assert not row(c)['paid_zh'] and len(m.calls)==1
 assert 'data-job-pending' in c.get(response.location).text
 # Repeated submit returns the pending task before verification/model invocation.
 monkeypatch.setattr(site.protect,'verify',lambda *_:(_ for _ in ()).throw(AssertionError('duplicate verification')))
 post_generate(c,r);assert len(m.calls)==1
 assert q.run_one(site) and row(c)['paid_zh'] and len(m.calls)==3
 post_generate(c,row(c));assert len(m.calls)==3 and not q.run_one(site)
 assert c.get('/r/'+r['access']+'/download.pdf').data.startswith(b'%PDF')

def test_failed_preview_releases_quota_and_can_retry(queue_mode,monkeypatch):
 c=queue_mode;m=Model([RuntimeError('fail'),initial()]);monkeypatch.setattr(site,'OpenAI',lambda **kw:m)
 submit(c);r=row(c);q.run_one(site)
 assert q.status(site.store,r['id'],'zh','free')['status']=='failed'
 with site.store.connect() as db:assert db.execute('SELECT COUNT(*) AS n FROM ab49_trials').fetchone()['n']==0
 assert '重试初判' in c.get('/r/'+r['access']).text
 post_generate(c,r,tier='free');q.run_one(site)
 assert row(c)['free_zh'] and len(m.calls)==2

def test_queue_failed_writer_keeps_payment_and_review(queue_mode,monkeypatch):
 c=queue_mode;m=Model([initial(),review(),RuntimeError('fail'),full()]);monkeypatch.setattr(site,'OpenAI',lambda **kw:m)
 submit(c);q.run_one(site);r=row(c);paid(r);post_generate(c,r);q.run_one(site)
 r=row(c);assert r['paid_mode']=='test' and not r['paid_zh'] and json.loads(r['bundle_json'])['paid_review']
 post_generate(c,r);q.run_one(site)
 assert row(c)['paid_zh'] and len(m.calls)==4

def test_claim_serialized_and_stale_token_cannot_finish(client):
 for i in range(6):q.enqueue(site.store,str(i),'zh')
 with ThreadPoolExecutor(max_workers=6) as p:jobs=list(p.map(lambda _:q.claim(site.store),range(6)))
 assert len({j['id'] for j in jobs})==6
 j=jobs[0]
 with site.store.connect() as db:db.execute('UPDATE ab49_jobs SET lease=0 WHERE id=?',(j['id'],))
 new=q.claim(site.store);assert new['id']==j['id'] and new['token']!=j['token']
 q.finish(site.store,j,'done');assert q.status(site.store,j['reading_id'],'zh')['status']=='running'
 q.finish(site.store,new,'done');assert q.status(site.store,j['reading_id'],'zh')['status']=='done'

def test_full_queue_and_wait_timeout(client):
 for i in range(100):q.enqueue(site.store,str(i),'zh')
 with pytest.raises(q.QueueFull):q.enqueue(site.store,'extra','zh')
 assert q.enqueue(site.store,'0','zh')
 with site.store.connect() as db:db.execute("UPDATE ab49_jobs SET created=? WHERE id=?",(time.time()-901,q.key('0','zh')))
 assert q.status(site.store,'0','zh')['error']=='wait_expired'

def test_worker_requeues_busy_but_does_not_loop_budget_failure(client,monkeypatch):
 # Paid job must have paid entitlement; no real provider used.
 m=Model([initial()]);monkeypatch.setattr(site,'OpenAI',lambda **kw:m)
 submit(client);r=row(client);paid(r);q.enqueue(site.store,r['id'],'zh')
 monkeypatch.setattr(site,'generate_text',lambda *_:(_ for _ in ()).throw(InProgress()))
 q.run_one(site);assert q.status(site.store,r['id'],'zh')['status']=='queued'
 with site.store.connect() as db:db.execute('UPDATE ab49_jobs SET lease=0')
 monkeypatch.setattr(site,'generate_text',lambda *_:(_ for _ in ()).throw(BudgetExceeded()))
 q.run_one(site);assert q.status(site.store,r['id'],'zh')['status']=='failed'
 assert not q.run_one(site)

def test_unpaid_queue_endpoint_does_not_allow_paid_work(queue_mode,monkeypatch):
 c=queue_mode;m=Model([initial()]);monkeypatch.setattr(site,'OpenAI',lambda **kw:m)
 submit(c);q.run_one(site);r=row(c)
 assert post_generate(c,r).status_code==403 and not q.pending(site.store,r['id'],'zh')

def test_actual_worker_process_reads_same_database(queue_mode,monkeypatch):
 import os,subprocess,sys
 from pathlib import Path
 c=queue_mode;submit(c);r=row(c);paid(r);post_generate(c,r)
 env=dict(os.environ);env['DB_PATH']=site.store.path
 root=Path(__file__).resolve().parents[1]
 env['PYTHONPATH']=str(root)+':'+str(root/'tests')+':'+os.environ.get('PYTHONPATH','')
 for key in ('DATABASE_URL','RENDER','SITE_ACCESS_PASSWORD'):env.pop(key,None)
 code="""import app as site
from conftest import Model,initial,review,full
from generation_queue import run_one,heartbeat
m=Model([initial(),review(),full()]);site.provider=lambda:m
heartbeat(site.store)
assert run_one(site)
assert run_one(site)
assert not run_one(site)
assert len(m.calls)==3
"""
 result=subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True,timeout=30)
 assert result.returncode==0,result.stderr
 assert row(c)['free_zh'] and row(c)['paid_zh']
 assert c.get('/healthz').get_json()['queue_worker_recent']

def test_expired_queued_preview_releases_held_quota(queue_mode):
 submit(queue_mode);r=row(queue_mode)
 with site.store.connect() as db:db.execute('UPDATE ab49_jobs SET created=?',(time.time()-901,))
 assert q.status(site.store,r['id'],'zh','free')['status']=='failed'
 with site.store.connect() as db:assert db.execute('SELECT COUNT(*) AS n FROM ab49_trials').fetchone()['n']==0

def test_lease_recovery_has_finite_limit(client):
 q.enqueue(site.store,'test','zh');job=q.claim(site.store)
 for _ in range(2):
  with site.store.connect() as db:db.execute('UPDATE ab49_jobs SET lease=0')
  job=q.claim(site.store);assert job
 with site.store.connect() as db:db.execute('UPDATE ab49_jobs SET lease=0')
 assert not q.claim(site.store)
 assert q.status(site.store,'test','zh')['status']=='failed'

def test_english_preview_and_paid_delivery(queue_mode,monkeypatch):
 c=queue_mode
 en={'priorities':'There is room for progress, though the outcome remains uncertain.','conditions':'Check whether the support becomes concrete.','actions':'Check confirmed progress before committing further.'}
 m=Model([initial(),{'direction':'There is room for progress, though the outcome remains uncertain.'},review(),full(),en]);monkeypatch.setattr(site,'OpenAI',lambda **kw:m)
 c.get('/?lang=en');submit(c);q.run_one(site)
 r=row(c);assert r['free_zh'] and r['free_en'];paid(r)
 post_generate(c,r,'en');q.run_one(site);r=row(c)
 assert r['paid_zh'] and r['paid_en'] and len(m.calls)==5
 assert c.get('/r/'+r['access']+'/download.pdf?lang=en').data.startswith(b'%PDF')

def test_five_model_calls_admitted_and_sixth_waits(client,monkeypatch):
 import threading
 from types import SimpleNamespace as NS
 from protection import bounded_client
 monkeypatch.setenv('AI_MAX_CONCURRENT','5')
 entered=threading.Event();release=threading.Event();lock=threading.Lock();count=[0]
 def create(**kwargs):
  with lock:
   count[0]+=1
   if count[0]==5:entered.set()
  assert release.wait(10)
  return NS(usage=None)
 model=NS(chat=NS(completions=NS(create=create)))
 call=lambda:bounded_client(model,site.store).chat.completions.create(model='deepseek-v4-pro',messages=[],max_tokens=10)
 with ThreadPoolExecutor(max_workers=5) as pool:
  futures=[pool.submit(call) for _ in range(5)]
  try:
   assert entered.wait(10)
   with pytest.raises(InProgress):call()
   assert count[0]==5
  finally:release.set()
  for f in futures:f.result()
 call() # released capacity is reusable

def test_worker_readiness_and_full_queue_disable_new_payments(client):
 assert not q.accepting_payments(site.store)
 q.heartbeat(site.store);assert q.accepting_payments(site.store)
 for i in range(100):q.enqueue(site.store,str(i),'zh')
 assert not q.accepting_payments(site.store)

def test_background_worker_entrypoint_process(queue_mode,monkeypatch):
 import os,subprocess,sys
 from pathlib import Path
 c=queue_mode;submit(c);r=row(c)
 env=dict(os.environ);env['DB_PATH']=site.store.path
 root=Path(__file__).resolve().parents[1]
 env['PYTHONPATH']=str(root)+':'+str(root/'tests')+':'+os.environ.get('PYTHONPATH','')
 for key in ('DATABASE_URL','RENDER','SITE_ACCESS_PASSWORD'):env.pop(key,None)
 code="import app as site;from conftest import Model,initial;import runpy;m=Model([initial()]);site.provider=lambda:m;runpy.run_module('queue_worker',run_name='__main__')"
 process=subprocess.Popen([sys.executable,'-c',code],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 try:
  deadline=time.time()+15
  while time.time()<deadline:
   if row(c)['free_zh']:break
   assert process.poll() is None
   time.sleep(.1)
  assert row(c)['free_zh'] and q.worker_recent(site.store)
 finally:
  process.terminate()
  try:process.communicate(timeout=10)
  except subprocess.TimeoutExpired:process.kill();process.communicate();raise
 assert process.returncode==0
