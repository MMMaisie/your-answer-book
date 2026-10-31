"""Small PostgreSQL/SQLite store. No network calls while a transaction is open."""
import os,sqlite3,time
from contextlib import contextmanager
from pathlib import Path

SCHEMA='''
CREATE TABLE IF NOT EXISTS ab49_readings (
 id TEXT PRIMARY KEY, access TEXT UNIQUE NOT NULL, owner TEXT NOT NULL,
 request_key TEXT NOT NULL, question TEXT NOT NULL, cast_json TEXT NOT NULL,
 bundle_json TEXT NOT NULL, free_zh TEXT NOT NULL DEFAULT '', free_en TEXT NOT NULL DEFAULT '',
 paid_zh TEXT NOT NULL DEFAULT '', paid_en TEXT NOT NULL DEFAULT '', version TEXT NOT NULL,
 created DOUBLE PRECISION NOT NULL, expires DOUBLE PRECISION NOT NULL,
 paid_mode TEXT NOT NULL DEFAULT '', checkout_nonce TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ab49_owner ON ab49_readings(owner,created);
CREATE INDEX IF NOT EXISTS ab49_expiry ON ab49_readings(expires);
CREATE TABLE IF NOT EXISTS ab49_orders (
 nonce TEXT PRIMARY KEY, reading_id TEXT NOT NULL, session_id TEXT UNIQUE,
 mode TEXT NOT NULL, amount INTEGER NOT NULL, currency TEXT NOT NULL,
 status TEXT NOT NULL, payment_intent TEXT, created DOUBLE PRECISION NOT NULL
);
CREATE INDEX IF NOT EXISTS ab49_intent ON ab49_orders(payment_intent);
CREATE TABLE IF NOT EXISTS ab49_reversals(intent TEXT PRIMARY KEY, created DOUBLE PRECISION NOT NULL);
CREATE TABLE IF NOT EXISTS ab49_trials (
 subject TEXT NOT NULL, day TEXT NOT NULL, reservation TEXT NOT NULL,
 status TEXT NOT NULL, created DOUBLE PRECISION NOT NULL,
 PRIMARY KEY(subject,day,reservation)
);
CREATE TABLE IF NOT EXISTS ab49_rates(subject TEXT PRIMARY KEY, next_at DOUBLE PRECISION NOT NULL, blocked_until DOUBLE PRECISION NOT NULL, expires DOUBLE PRECISION NOT NULL);
CREATE TABLE IF NOT EXISTS ab49_tokens(digest TEXT PRIMARY KEY, expires DOUBLE PRECISION NOT NULL);
CREATE TABLE IF NOT EXISTS ab49_locks(name TEXT PRIMARY KEY, token TEXT NOT NULL, expires DOUBLE PRECISION NOT NULL);
CREATE TABLE IF NOT EXISTS ab49_calls(id TEXT PRIMARY KEY, day TEXT NOT NULL, model TEXT NOT NULL, status TEXT NOT NULL, reserve DOUBLE PRECISION NOT NULL, prompt_tokens INTEGER NOT NULL DEFAULT 0, completion_tokens INTEGER NOT NULL DEFAULT 0, created DOUBLE PRECISION NOT NULL);
CREATE TABLE IF NOT EXISTS ab49_meta(name TEXT PRIMARY KEY, value DOUBLE PRECISION NOT NULL);
CREATE TABLE IF NOT EXISTS ab49_search(id TEXT PRIMARY KEY,payload TEXT NOT NULL,expires DOUBLE PRECISION NOT NULL);
'''
class Connection:
 def __init__(self,raw,pg):self.raw,self.pg=raw,pg
 def execute(self,sql,args=()):return self.raw.execute(sql.replace('?','%s') if self.pg else sql,args)
class Store:
 def __init__(self,url='',path='readings-v49.db'):
  if url and not url.startswith(('postgresql://','postgres://')):raise RuntimeError('DATABASE_URL must be a PostgreSQL URL.')
  self.url,self.path=url,path
 @property
 def durable(self):return bool(self.url)
 @contextmanager
 def connect(self):
  if self.url:
   import psycopg
   from psycopg.rows import dict_row
   # Explicit TLS; connection URI is never written to logs or client responses.
   try:raw=psycopg.connect(self.url,connect_timeout=15,sslmode='require',row_factory=dict_row,autocommit=True)
   except Exception:raise RuntimeError('Database connection failed. Check DATABASE_URL in the server environment.') from None
   raw.execute('BEGIN')
   raw.execute('SET LOCAL statement_timeout = 15000')
   # Transaction-level lock works with Neon transaction pooling; low-volume writes are serialized.
   raw.execute('SELECT pg_advisory_xact_lock(794901239)')
  else:
   Path(self.path).parent.mkdir(parents=True,exist_ok=True)
   raw=sqlite3.connect(self.path,timeout=15);raw.row_factory=sqlite3.Row;raw.execute('BEGIN IMMEDIATE')
  try:
   yield Connection(raw,bool(self.url));raw.execute('COMMIT')
  except BaseException:
   raw.execute('ROLLBACK');raise
  finally:raw.close()
 def init(self):
  with self.connect() as c:
   for sql in SCHEMA.split(';'):
    if sql.strip():c.execute(sql)
 def cleanup(self,force=False):
  now=time.time()
  with self.connect() as c:
   old=c.execute("SELECT value FROM ab49_meta WHERE name='cleanup'").fetchone()
   if not force and old and old['value']>now-3600:return
   # Orders keep only payment identifiers, never original questions or prose.
   c.execute('DELETE FROM ab49_readings WHERE expires<?',(now,))
   c.execute('DELETE FROM ab49_trials WHERE created<?',(now-3*86400,))
   for table in ('ab49_rates','ab49_tokens','ab49_locks','ab49_search'):
    c.execute(f'DELETE FROM {table} WHERE expires<?',(now,))
   c.execute('DELETE FROM ab49_calls WHERE created<?',(now-30*86400,))
   c.execute("INSERT INTO ab49_meta VALUES('cleanup',?) ON CONFLICT(name) DO UPDATE SET value=excluded.value",(now,))
 def acquire(self,name,ttl=900):
  import secrets
  token=secrets.token_hex(16);now=time.time()
  with self.connect() as c:
   c.execute('DELETE FROM ab49_locks WHERE name=? AND expires<?',(name,now))
   cursor=c.execute('INSERT INTO ab49_locks VALUES(?,?,?) ON CONFLICT(name) DO NOTHING',(name,token,now+ttl))
   return token if cursor.rowcount==1 else None
 def release(self,name,token):
  if token:
   with self.connect() as c:c.execute('DELETE FROM ab49_locks WHERE name=? AND token=?',(name,token))
