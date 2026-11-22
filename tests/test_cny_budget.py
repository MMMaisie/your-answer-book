import sqlite3,time
from datetime import datetime,timezone
import pytest
from storage import Store
from protection import capacity,bounded_client,BudgetExceeded,budget_settings
from conftest import Model,initial

def test_existing_aud_rows_survive_idempotent_migration(tmp_path,monkeypatch):
 path=tmp_path/'legacy.db'
 with sqlite3.connect(path) as c:
  c.execute('CREATE TABLE ab49_calls(id TEXT PRIMARY KEY,day TEXT,model TEXT,status TEXT,reserve REAL,prompt_tokens INTEGER DEFAULT 0,completion_tokens INTEGER DEFAULT 0,created REAL)')
  c.execute('INSERT INTO ab49_calls(id,day,model,status,reserve,created) VALUES(?,?,?,?,?,?)',('old',datetime.now(timezone.utc).strftime('%Y-%m-%d'),'deepseek-v4-pro','completed',1,time.time()))
 store=Store(path=str(path));store.init();store.init()
 with store.connect() as c:r=c.execute('SELECT * FROM ab49_calls').fetchone()
 assert r['reserve']==1 and r['currency']=='AUD'
 monkeypatch.setenv('AI_DAILY_BUDGET_CNY','5')
 assert not capacity(store)
 monkeypatch.setenv('AI_DAILY_BUDGET_CNY','10')
 assert capacity(store)
 model=Model([initial()]);bounded_client(model,store).chat.completions.create(model='deepseek-v4-pro',messages=[],max_tokens=100)
 with store.connect() as c:
  row=c.execute("SELECT * FROM ab49_calls WHERE id!='old'").fetchone()
 assert row['currency']=='CNY' and 0<row['reserve']<1

def test_cny_default_and_legacy_env_not_reinterpreted(monkeypatch):
 monkeypatch.delenv('AI_DAILY_BUDGET_CNY',raising=False)
 monkeypatch.setenv('AI_DAILY_BUDGET_AUD','5000');monkeypatch.setenv('AI_PRO_OUTPUT_USD_PER_M','999')
 assert budget_settings('deepseek-v4-pro')==[10,30,1,10]
