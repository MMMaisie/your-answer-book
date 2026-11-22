import time,json
from datetime import datetime,timezone
import app as site
import generation_queue as q
from conftest import Model,initial,review,full,submit,csrf
from test_guest_flow import row,paid,post_generate
from protection import capacity,capacity_reason

def queued_preview(client,monkeypatch):
 monkeypatch.setenv('GENERATION_QUEUE_ENABLED','1')
 response=submit(client);r=row(client)
 assert not r['free_zh'] and q.pending(site.store,r['id'],'zh','free')
 monkeypatch.setenv('GENERATION_QUEUE_ENABLED','0')
 return r,response.location

def test_switch_to_sync_releases_unused_hold_and_old_reading_retries(client,monkeypatch):
 m=Model([initial()]);monkeypatch.setattr(site,'OpenAI',lambda **kw:m)
 r,url=queued_preview(client,monkeypatch)
 page=client.get(url).text
 assert '重试初判' in page and '初判已排队' not in page
 with site.store.connect() as c:assert c.execute('SELECT COUNT(*) AS n FROM ab49_trials').fetchone()['n']==0
 post_generate(client,r,tier='free')
 assert row(client)['free_zh'] and len(m.calls)==1
 with site.store.connect() as c:assert c.execute("SELECT COUNT(*) AS n FROM ab49_trials WHERE status='used'").fetchone()['n']==2
 # Refreshes / repeated submissions never spend another request.
 client.get(url);post_generate(client,row(client),tier='free');assert len(m.calls)==1
 assert q.status(site.store,r['id'],'zh','free')['status']=='done'

def test_switch_to_sync_allows_fresh_cast_without_extra_quota(client,monkeypatch):
 m=Model([initial()]);monkeypatch.setattr(site,'OpenAI',lambda **kw:m)
 queued_preview(client,monkeypatch)
 with site.store.connect() as c:c.execute('DELETE FROM ab49_rates')
 submit(client,question='这次面试顺利吗？')
 with site.store.connect() as c:assert c.execute("SELECT COUNT(*) AS n FROM ab49_readings WHERE free_zh!=''").fetchone()['n']==1
 assert len(m.calls)==1

def test_release_preserves_used_quota_live_leases_and_payment(client,monkeypatch):
 m=Model([initial()]);monkeypatch.setattr(site,'OpenAI',lambda **kw:m)
 submit(client);r=row(client);paid(r)
 q.enqueue(site.store,r['id'],'zh','paid')
 with site.store.connect() as c:
  c.execute("INSERT INTO ab49_trials VALUES('someone','today','live','held',?)",(time.time(),))
  c.execute("INSERT INTO ab49_trials VALUES('someone','today','expired','held',?)",(time.time(),))
  c.execute("INSERT INTO ab49_jobs(id,reading_id,lang,tier,trial,status,created,updated,lease) VALUES('livejob',?,'zh','free','live','running',?,?,?)",(r['id'],time.time(),time.time(),time.time()+1200))
  c.execute("INSERT INTO ab49_jobs(id,reading_id,lang,tier,trial,status,created,updated,lease) VALUES('expiredjob',?,'zh','free','expired','running',?,?,0)",(r['id'],time.time(),time.time()))
 q.suspend_unclaimed(site.store)
 with site.store.connect() as c:
  assert c.execute("SELECT COUNT(*) AS n FROM ab49_trials WHERE status='used'").fetchone()['n']==2
  assert c.execute("SELECT COUNT(*) AS n FROM ab49_trials WHERE reservation='live'").fetchone()['n']==1
  assert c.execute("SELECT COUNT(*) AS n FROM ab49_trials WHERE reservation='expired'").fetchone()['n']==0
 assert row(client)['paid_mode']=='test'

def test_sync_retry_failure_releases_only_its_new_hold(client,monkeypatch):
 m=Model([RuntimeError('provider error')]);monkeypatch.setattr(site,'OpenAI',lambda **kw:m)
 r,url=queued_preview(client,monkeypatch);client.get(url)
 post_generate(client,r,tier='free')
 with site.store.connect() as c:assert c.execute('SELECT COUNT(*) AS n FROM ab49_trials').fetchone()['n']==0
 assert '重试初判' in client.get(url).text

def test_old_aud_completed_calls_count_known_tokens_not_old_huge_reserve(client,monkeypatch):
 day=datetime.now(timezone.utc).strftime('%Y-%m-%d');monkeypatch.setenv('AI_DAILY_BUDGET_CNY','10')
 with site.store.connect() as c:
  c.execute('INSERT INTO ab49_calls(id,day,model,status,reserve,prompt_tokens,completion_tokens,created) VALUES(?,?,?,?,?,?,?,?)',('old',day,'deepseek-v4-pro','completed',50,8359,2056,time.time()))
 assert capacity(site.store)
 with site.store.connect() as c:c.execute("UPDATE ab49_calls SET status='failed'")
 assert capacity_reason(site.store)=='ai_daily_budget_unavailable'

def test_health_blockers_show_missing_config_without_secrets(client,monkeypatch):
 monkeypatch.setattr(site,'stripe_client',None);monkeypatch.setattr(site,'SUPPORT_EMAIL','')
 monkeypatch.setenv('AI_ENABLED','0')
 data=client.get('/healthz').get_json()
 assert {'missing_stripe_key','missing_support_email','ai_disabled'}<=set(data['checkout_blockers'])
 assert not data['generation_queue_enabled'] and data['ai_budget_currency']=='CNY'
 assert 'not-a-real-key' not in json.dumps(data)

def test_sync_paid_still_runs_without_worker_and_reuses_saved_review(client,monkeypatch):
 m=Model([initial(),review(),RuntimeError('writer fails'),full()]);monkeypatch.setattr(site,'OpenAI',lambda **kw:m)
 submit(client);r=row(client);paid(r);post_generate(client,r)
 r=row(client);assert not r['paid_zh'] and json.loads(r['bundle_json'])['paid_review']
 monkeypatch.setattr(site.protect,'rate',lambda *a:None)
 post_generate(client,r);assert row(client)['paid_zh'] and len(m.calls)==4

def test_checkout_is_enabled_without_worker_when_config_and_budget_ready(client,monkeypatch):
 from storage import Store
 from types import SimpleNamespace
 monkeypatch.setattr(Store,'durable',property(lambda self:True))
 monkeypatch.setattr(site,'stripe_client',SimpleNamespace())
 monkeypatch.setattr(site,'SUPPORT_EMAIL','support@example.test')
 for key in ('STRIPE_TEST_WEBHOOK_SECRET','TURNSTILE_SITE_KEY','TURNSTILE_SECRET_KEY'):monkeypatch.setenv(key,'local-test-only')
 monkeypatch.setenv('AI_DAILY_BUDGET_CNY','10')
 data=client.get('/healthz').get_json()
 assert data['checkout_enabled'] and data['checkout_blockers']==[]
 assert not data['queue_worker_recent'] and not data['generation_queue_enabled']
