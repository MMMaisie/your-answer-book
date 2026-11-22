import importlib.util,json
from pathlib import Path
import pytest
from conftest import Model,initial,review,full
from hexagrams import build_cast
from datetime import datetime
spec=importlib.util.spec_from_file_location('live_acceptance_runner',Path(__file__).resolve().parents[1]/'tools/live_acceptance.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)

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
 assert runner.run(arguments(tmp_path,'--execute','--budget-aud','0.000001'),m)==2
 s=summary(tmp_path);assert not m.calls and s['provider_calls']==0 and s['results'][0]['status']=='budget_stopped'

def test_real_runner_pipeline_with_scripted_provider(tmp_path):
 c=build_cast(runner.SCENARIOS['static'],datetime(2026,11,22,11,40))
 en={'priorities':'There is room for progress, though the outcome remains uncertain.','conditions':'Check whether support becomes concrete.','actions':'Check confirmed progress before committing.'}
 m=Model([initial(c),review(cast=c),full(),en])
 assert runner.run(arguments(tmp_path,'--execute','--budget-aud','100','--english','--save-responses'),m)==0
 s=summary(tmp_path);assert s['provider_calls']==4 and s['results'][0]['quality_review']=='pending'
 assert s['results'][0]['status']=='protocol_passed' and s['plan']['queue_tested'] is False
 calls=json.loads(next((tmp_path/'reports').glob('*/calls.json')).read_text())
 assert [x['stage'] for x in calls]==['initial','review','writer','translation']
 assert all(x['completion_tokens']==100 for x in calls)
 assert len(list((tmp_path/'reports').glob('*/response-*.json')))==4

def test_provider_exception_body_not_saved_and_reserve_retained(tmp_path):
 m=Model([RuntimeError('SECRET-DO-NOT-LOG')])
 assert runner.run(arguments(tmp_path,'--execute','--budget-aud','100'),m)==2
 s=summary(tmp_path);assert s['reserved_aud']>0 and s['results'][0]['stage']=='initial'
 for p in (tmp_path/'reports').rglob('*'):
  if p.is_file():assert 'SECRET-DO-NOT-LOG' not in p.read_text()

def test_validation_failure_keeps_specific_diagnostic(tmp_path):
 m=Model([{'outlook':'wrong'},{'outlook':'wrong'}])
 runner.run(arguments(tmp_path,'--execute','--budget-aud','100'),m)
 r=summary(tmp_path)['results'][0]
 assert r['detail']=='initial_outlook' and r['attempt']==2 and r['provider_calls']==2

def test_repeat_runs_create_separate_reports(tmp_path):
 for _ in range(2):runner.run(arguments(tmp_path,'--execute','--budget-aud','0.000001'),Model([]))
 assert len(list((tmp_path/'reports').glob('*/summary.json')))==2

def test_execute_missing_key_creates_no_report(tmp_path,monkeypatch):
 monkeypatch.delenv('DEEPSEEK_API_KEY',raising=False)
 with pytest.raises(ValueError,match='not configured'):runner.run(arguments(tmp_path,'--execute','--budget-aud','2'))
 assert not (tmp_path/'reports').exists()
