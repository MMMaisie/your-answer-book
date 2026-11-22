"""Local, transactional CNY daily reservation ledger. Not a provider-account cap."""
import hashlib,json,sqlite3
from contextlib import contextmanager
from datetime import datetime,timezone
from pathlib import Path

class DailyBudgetStop(Exception):pass

def utc_day():return datetime.now(timezone.utc).strftime('%Y-%m-%d')

class DailyLedger:
 def __init__(self,path):
  self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
  with self.connect() as c:
   c.execute('CREATE TABLE IF NOT EXISTS spend(id TEXT PRIMARY KEY,day TEXT NOT NULL,reserve REAL NOT NULL)')
  self.path.chmod(0o600)
 @contextmanager
 def connect(self):
  c=sqlite3.connect(self.path,timeout=15,isolation_level='IMMEDIATE')
  try:
   with c:yield c
  finally:c.close()
 def total(self):
  with self.connect() as c:return c.execute('SELECT COALESCE(SUM(reserve),0) FROM spend WHERE day=?',(utc_day(),)).fetchone()[0]
 def reserve(self,identity,amount,limit):
  with self.connect() as c:
   c.execute('BEGIN IMMEDIATE')
   total=c.execute('SELECT COALESCE(SUM(reserve),0) FROM spend WHERE day=?',(utc_day(),)).fetchone()[0]
   if total+amount>limit+1e-12:raise DailyBudgetStop()
   c.execute('INSERT INTO spend VALUES(?,?,?)',(identity,utc_day(),amount))
 def import_report(self,directory,rates):
  """Count prior API calls on resume once, even if a report is copied elsewhere."""
  path=Path(directory)/'calls.json'
  if not path.exists():return
  # Reports have UTC timestamps. Old-day expenses must not consume today's cap.
  try:day=datetime.strptime(Path(directory).name[:8],'%Y%m%d').strftime('%Y-%m-%d')
  except ValueError:raise ValueError('resume report needs its original timestamped folder name') from None
  raw=json.loads(path.read_text(encoding='utf-8'))
  for item in raw:
   identity=item.get('ledger_id')
   identity=identity or 'import-'+hashlib.sha256(json.dumps([Path(directory).name,item],sort_keys=True).encode()).hexdigest()
   if 'reserved_cny' in item:amount=float(item['reserved_cny'])
   elif isinstance(item.get('prompt_tokens'),int) and isinstance(item.get('completion_tokens'),int):
    inp,out=rates[item['model']];amount=(item['prompt_tokens']*inp+item['completion_tokens']*out)/1e6
   else:amount=float(item.get('reserved_aud',0))*5
   if amount<0:raise ValueError('invalid report expense')
   with self.connect() as c:c.execute('INSERT OR IGNORE INTO spend VALUES(?,?,?)',(identity,day,amount))
