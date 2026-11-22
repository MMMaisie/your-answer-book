import importlib.util,json
from pathlib import Path
import pytest
from conftest import Model,initial,review,full
from hexagrams import build_cast
from datetime import datetime
spec=importlib.util.spec_from_file_location('live_acceptance_runner',Path(__file__).resolve().parents[1]/'tools/live_acceptance.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)

@pytest.fixture(autouse=True)
def private_daily_ledger(tmp_path,monkeypatch):
 original=runner.DailyLedger
 monkeypatch.setattr(runner,'DailyLedger',lambda _:original(tmp_path/'daily.sqlite3'))

def arguments(tmp_path,*extra):return runner.parser().parse_args(['--out',str(tmp_path/'reports'),*extra])
def summary(tmp_path):return json.loads(next((tmp_path/'reports').glob('*/summary.json')).read_text())

def test_dry_run_never_calls_or_requires_key(tmp_path,monkeypatch,capsys):
 monkeypatch.delenv('DEEPSEEK_API_KEY',raising=False)
 m=Model([]);assert runner.run(arguments(tmp_path,'--limit','3'),m)==0
 assert not m.calls and not (tmp_path/'reports').exists()
 assert len(json.loads(capsys.readouterr().out)['cases'])==3

def test_execution_requires_explicit_budget(tmp_path):
 with pytest.raises(ValueError,match='budget'):runner.run(arguments(tmp_path,'--execute'),Model([]))

def test_budget_exhaustion_stops_before_provider_call(tmp_path):
 m=Model([])
 assert runner.run(arguments(tmp_path,'--execute','--budget-cny','0.000001'),m)==2
 s=summary(tmp_path);assert not m.calls and s['provider_calls']==0 and s['results'][0]['status']=='budget_stopped'

def test_real_runner_pipeline_with_scripted_provider(tmp_path):
 c=build_cast(runner.SCENARIOS['static'],datetime(2026,11,22,11,40))
 en={'priorities':'There is room for progress, though the outcome remains uncertain.','conditions':'Check whether support becomes concrete.','actions':'Check confirmed progress before committing.'}
 m=Model([initial(c),review(cast=c),full(),en])
 assert runner.run(arguments(tmp_path,'--execute','--budget-cny','100','--english','--save-responses'),m)==0
 s=summary(tmp_path);assert s['provider_calls']==4 and s['results'][0]['quality_review']=='pending'
 assert s['results'][0]['status']=='protocol_passed' and s['plan']['queue_tested'] is False
 calls=json.loads(next((tmp_path/'reports').glob('*/calls.json')).read_text())
 assert [x['stage'] for x in calls]==['initial','review','writer','translation']
 assert all(x['completion_tokens']==100 for x in calls)
 assert len(list((tmp_path/'reports').glob('*/response-*.json')))==4

def test_provider_exception_body_not_saved_and_reserve_retained(tmp_path):
 m=Model([RuntimeError('SECRET-DO-NOT-LOG')])
 assert runner.run(arguments(tmp_path,'--execute','--budget-cny','100'),m)==2
 s=summary(tmp_path);assert s['reserved_cny']>0 and s['results'][0]['stage']=='initial'
 for p in (tmp_path/'reports').rglob('*'):
  if p.is_file():assert 'SECRET-DO-NOT-LOG' not in p.read_text()

def test_validation_failure_keeps_specific_diagnostic(tmp_path):
 m=Model([{'outlook':'wrong'},{'outlook':'wrong'}])
 runner.run(arguments(tmp_path,'--execute','--budget-cny','100'),m)
 r=summary(tmp_path)['results'][0]
 assert r['detail']=='initial_outlook' and r['attempt']==2 and r['provider_calls']==2

def test_repeat_runs_create_separate_reports(tmp_path):
 for _ in range(2):runner.run(arguments(tmp_path,'--execute','--budget-cny','0.000001'),Model([]))
 assert len(list((tmp_path/'reports').glob('*/summary.json')))==2

def test_execute_missing_key_creates_no_report(tmp_path,monkeypatch):
 monkeypatch.delenv('DEEPSEEK_API_KEY',raising=False)
 with pytest.raises(ValueError,match='not configured'):runner.run(arguments(tmp_path,'--execute','--budget-cny','2'))
 assert not (tmp_path/'reports').exists()

def test_resume_reuses_initial_without_calling_again(tmp_path):
 c=build_cast(runner.SCENARIOS['static'],datetime(2026,11,22,11,40))
 # Generate only initial, then stop because the next reservation cannot fit.
 first=Model([initial(c)])
 assert runner.run(arguments(tmp_path,'--execute','--budget-cny','0.7'),first)==2
 old=next((tmp_path/'reports').glob('*/summary.json')).parent
 assert json.loads((old/'summary.json').read_text())['results'][0]['stage']=='review'
 second=Model([review(cast=c),full()])
 assert runner.run(arguments(tmp_path,'--execute','--budget-cny','10','--resume',str(old)),second)==0
 assert len(second.calls)==2
 assert json.loads((old/'summary.json').read_text())['results'][0]['status']=='budget_stopped'

def test_daily_budget_survives_separate_runs(tmp_path,monkeypatch):
 monkeypatch.setenv('AI_DAILY_BUDGET_CNY','0.7')
 c=build_cast(runner.SCENARIOS['static'],datetime(2026,11,22,11,40))
 first=Model([initial(c)])
 runner.run(arguments(tmp_path,'--execute','--budget-cny','10'),first)
 assert len(first.calls)==1
 second=Model([])
 runner.run(arguments(tmp_path,'--execute','--budget-cny','10'),second)
 assert not second.calls

def test_old_aud_environment_does_not_change_cny_budget(tmp_path,monkeypatch,capsys):
 monkeypatch.setenv('AI_DAILY_BUDGET_AUD','9999');monkeypatch.setenv('BUDGET_AUD_PER_USD','9999')
 runner.run(arguments(tmp_path),Model([]))
 p=json.loads(capsys.readouterr().out)
 assert p['daily_budget_cny']==10 and p['currency']=='CNY'

def test_resume_old_aud_report_counts_prior_usage_once(tmp_path):
 c=build_cast(runner.SCENARIOS['static'],datetime(2026,11,22,11,40))
 runner.run(arguments(tmp_path,'--execute','--budget-cny','0.7'),Model([initial(c)]))
 old=next((tmp_path/'reports').glob('*/summary.json')).parent
 p=json.loads((old/'plan.json').read_text());p['pipeline_version']='v49.8.1-old';runner.write_json(old/'plan.json',p)
 calls=json.loads((old/'calls.json').read_text());calls[0].pop('ledger_id');calls[0].pop('reserved_cny');calls[0]['reserved_aud']=1.11758
 runner.write_json(old/'calls.json',calls)
 from acceptance_budget import DailyLedger
 ledger=DailyLedger(tmp_path/'import-test.sqlite3')
 rates={'deepseek-v4-pro':(10,30)}
 ledger.import_report(old,rates);first=ledger.total();ledger.import_report(old,rates)
 assert first>0 and ledger.total()==first
 m=Model([review(cast=c),full()])
 assert runner.run(arguments(tmp_path,'--execute','--budget-cny','10','--resume',str(old)),m)==0
 assert len(m.calls)==2

def test_daily_ledger_concurrent_reservations_are_atomic(tmp_path):
 from acceptance_budget import DailyLedger,DailyBudgetStop
 from concurrent.futures import ThreadPoolExecutor
 ledger=DailyLedger(tmp_path/'concurrent.sqlite3')
 def reserve(i):
  try:ledger.reserve(str(i),3,10);return True
  except DailyBudgetStop:return False
 with ThreadPoolExecutor(max_workers=8) as pool:assert sum(pool.map(reserve,range(8)))==3
 assert ledger.total()==9
