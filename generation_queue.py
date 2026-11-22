"""Durable, deduplicated paid jobs. All claims use Store's serialized transactions."""
import secrets,time

class QueueFull(Exception):pass

def key(reading_id,lang,tier='paid'):
 if lang not in ('zh','en'):raise ValueError('unsupported language')
 if tier not in ('free','paid'):raise ValueError('unsupported tier')
 return reading_id+':'+lang+':'+tier

def enqueue(store,reading_id,lang,tier='paid',trial=''):
 now=time.time();jid=key(reading_id,lang,tier)
 with store.connect() as c:
  old=c.execute('SELECT * FROM ab49_jobs WHERE id=?',(jid,)).fetchone()
  if old and old['status'] in ('queued','running'):return jid
  total=c.execute("SELECT COUNT(*) AS n FROM ab49_jobs WHERE status IN ('queued','running')").fetchone()['n']
  if total>=100:raise QueueFull()
  c.execute("INSERT INTO ab49_jobs(id,reading_id,lang,tier,trial,status,created,updated,lease,token,error) VALUES(?,?,?,?,?,'queued',?,?,0,'','') ON CONFLICT(id) DO UPDATE SET status='queued',recoveries=0,trial=excluded.trial,created=excluded.created,updated=excluded.updated,lease=0,token='',error=''",(jid,reading_id,lang,tier,trial,now,now))
 return jid

def recover(c,now):
 # Finite recovery of interrupted workers; do not revive a stale lease forever.
 c.execute("DELETE FROM ab49_trials WHERE status='held' AND reservation IN (SELECT trial FROM ab49_jobs WHERE status='running' AND lease<? AND recoveries>=2)",(now,))
 c.execute("UPDATE ab49_jobs SET status='failed',error='worker_interrupted',updated=? WHERE status='running' AND lease<? AND recoveries>=2",(now,now))
 c.execute("UPDATE ab49_jobs SET status='queued',token='',lease=0,created=?,updated=?,recoveries=recoveries+1 WHERE status='running' AND lease<?",(now,now,now))

def heartbeat(store):
 with store.connect() as c:c.execute("INSERT INTO ab49_meta(name,value) VALUES('queue-heartbeat',?) ON CONFLICT(name) DO UPDATE SET value=excluded.value",(time.time(),))

def accepting_payments(store):
 if not worker_recent(store):return False
 with store.connect() as c:row=c.execute("SELECT COUNT(*) AS n FROM ab49_jobs WHERE status IN ('queued','running')").fetchone()
 return row['n']<100


def worker_recent(store):
 with store.connect() as c:row=c.execute("SELECT value FROM ab49_meta WHERE name='queue-heartbeat'").fetchone()
 return bool(row and row['value']>time.time()-30)


def status(store,reading_id,lang,tier='paid'):
 now=time.time()
 with store.connect() as c:
  c.execute("DELETE FROM ab49_trials WHERE status='held' AND reservation IN (SELECT trial FROM ab49_jobs WHERE status='queued' AND created<?)",(now-900,))
  recover(c,now)
  # A missing worker cannot leave the page polling forever.
  c.execute("UPDATE ab49_jobs SET status='failed',error='wait_expired',updated=? WHERE status='queued' AND created<?",(now,now-900))
  row=c.execute('SELECT status,error FROM ab49_jobs WHERE id=?',(key(reading_id,lang,tier),)).fetchone()
 return dict(row) if row else {}

def pending(store,reading_id,lang,tier='paid'):return status(store,reading_id,lang,tier).get('status') in ('queued','running')

def claim(store):
 now=time.time();token=secrets.token_hex(24)
 with store.connect() as c:
  c.execute("DELETE FROM ab49_trials WHERE status='held' AND reservation IN (SELECT trial FROM ab49_jobs WHERE status='queued' AND created<?)",(now-900,))
  recover(c,now)
  c.execute("UPDATE ab49_jobs SET status='failed',error='wait_expired',updated=? WHERE status='queued' AND created<?",(now,now-900))
  row=c.execute("SELECT * FROM ab49_jobs WHERE status='queued' AND lease<=? ORDER BY created,id LIMIT 1",(now,)).fetchone()
  if not row:return None
  c.execute("UPDATE ab49_jobs SET status='running',token=?,lease=?,updated=? WHERE id=?",(token,now+1200,now,row['id']))
 return dict(row,token=token)

def finish(store,job,state,error=''):
 if state not in ('done','failed','queued'):raise ValueError('invalid job state')
 now=time.time()
 with store.connect() as c:
  c.execute('UPDATE ab49_jobs SET status=?,error=?,updated=?,lease=?,token=? WHERE id=? AND token=? AND status=\'running\'',(state,error,now,now+2 if state=='queued' else 0,'',job['id'],job['token']))

def run_one(site):
 from protection import InProgress,BudgetExceeded
 job=claim(site.store)
 if not job:return False
 try:
  with site.app.test_request_context('/'):
   site.g.lang=job['lang']
   row=site.read_id(job['reading_id'])
   if not row:raise ValueError('reading expired')
   if job['tier']=='paid':
    if not site.unlocked(row):raise ValueError('entitlement unavailable')
    site.generate_text(row,'paid','zh')
    if job['lang']=='en':
     row=site.read_id(job['reading_id']);site.generate_text(row,'paid','en')
   else:
    site.generate_preview_job(row,job['trial'])
    if job['lang']=='en':
     row=site.read_id(job['reading_id']);site.generate_text(row,'free','en')
  finish(site.store,job,'done')
 except InProgress:finish(site.store,job,'queued')
 except BudgetExceeded:
  site.protect.finish_trial(job['trial'],False)
  finish(site.store,job,'failed','service_capacity')
 except Exception as error:
  # Reuse safe diagnostic categories, never log model bodies, questions or keys.
  from reading_contract import ReadingValidationError
  if isinstance(error,ReadingValidationError):site.app.logger.warning('Queued generation failed: stage=%s reason=%s detail=%s finish_reason=%s',error.stage,error.reason,error.detail,error.finish_reason)
  else:site.app.logger.warning('Queued generation failed: category=%s',type(error).__name__)
  site.protect.finish_trial(job['trial'],False)
  finish(site.store,job,'failed','generation_failed')
 return True


def suspend_unclaimed(store):
 """Release unused free holds when switching to synchronous mode; never cancel a live lease."""
 now=time.time()
 with store.connect() as c:
  jobs=c.execute("SELECT id,trial FROM ab49_jobs WHERE status='queued' OR (status='running' AND lease<=?)",(now,)).fetchall()
  for job in jobs:
   if job['trial']:
    c.execute("DELETE FROM ab49_trials WHERE reservation=? AND status='held'",(job['trial'],))
   c.execute("UPDATE ab49_jobs SET status='failed',error='queue_disabled',updated=?,lease=0,token='' WHERE id=?",(now,job['id']))
 return len(jobs)
