import json,copy
from pathlib import Path
import pytest
import simple_reading as engine
from hexagrams import build_cast
from conftest import Model,initial,full
CAST=build_cast([2]*6)
MATRIX=json.loads(Path(__file__).with_name('colloquial_cases.json').read_text())
QUESTIONS=[q for g in MATRIX.values() for q in g['questions']]
@pytest.mark.parametrize('question',QUESTIONS)
def test_questions_reach_reference_context_without_keyword_gate(question):
 data,refs=engine.context(question,CAST)
 assert data['question']==question and len(data['book_rules'])==141
 assert not any(k in data for k in ('allowed_primary_positions','forced_direction','selection','focal_kin'))
 assert all(c['id'] in refs for c in data['book_cases'])

def test_initial_does_not_generate_or_store_paid_content():
 raw=initial();raw['paid']=full()['paid']
 m=Model([raw]);r=engine.generate(m,'找工作',CAST,'deepseek-v4-pro')
 assert 'paid' not in r['bundle'] and len(m.calls)==1
 assert '禁止生成付费全文' in m.calls[0]['messages'][1]['content']

def test_paid_is_another_provider_call_using_frozen_initial():
 m=Model([initial(),full()]);core=engine.generate(m,'找工作',CAST,'deepseek-v4-pro')['bundle']
 result=engine.generate_paid(m,'找工作',CAST,'deepseek-v4-pro',core)
 assert len(m.calls)==2 and result==full()['paid']
 assert json.loads(m.calls[1]['messages'][1]['content'])['canonical']==core

@pytest.mark.parametrize('tier,lang,maximum',[('free','zh',50),('paid','zh',300),('free','en',60),('paid','en',350)])
def test_exact_maximum_accepted_and_one_over_rejected(tier,lang,maximum):
 keys=engine.FIELDS[tier]
 values={k:('好' if lang=='zh' else 'okay') for k in keys}
 first=maximum-(len(keys)-1)
 values[keys[0]]=('好'*first if lang=='zh' else ' '.join(['okay']*first))
 assert engine.check_parts(values,tier,lang,CAST)
 values[keys[0]]+=('好' if lang=='zh' else ' okay')
 with pytest.raises(ValueError,match='length'):engine.check_parts(values,tier,lang,CAST)

@pytest.mark.parametrize('claim',['水克土','金生火','火生水','辰土生子水'])
def test_basic_element_errors_fail_instead_of_leaking_to_user(claim):
 v=initial();v['free']['direction']=claim
 with pytest.raises(ValueError):engine.generate(Model([v,v]),'找工作',CAST,'deepseek-v4-pro')

def test_repair_is_bounded_and_never_truncates_text():
 bad=initial();bad['free']['direction']='好'*51
 m=Model([bad,initial()]);assert engine.generate(m,'求职',CAST,'deepseek-v4-pro')['bundle']['free']==initial()['free'];assert len(m.calls)==2
 with pytest.raises(ValueError):engine.generate(Model([bad,bad]),'求职',CAST,'deepseek-v4-pro')

def test_paid_opposite_outlook_rejected():
 with pytest.raises(ValueError):engine.generate_paid(Model([full('difficult'),full('difficult')]),'求职',CAST,'deepseek-v4-pro',initial())

def test_unknown_sources_rejected():
 v=initial();v['sources']=[{'id':'invented'}]
 with pytest.raises(ValueError):engine.generate(Model([v,v]),'求职',CAST,'deepseek-v4-pro')

def test_english_translation_limits_and_no_new_interpretation():
 v={'direction':'There is room to progress, but the outcome remains uncertain.'};m=Model([v])
 assert engine.translate(m,initial()['free'],'free',CAST,'deepseek-flash')['parts']==v
 assert 'Do not reinterpret' in m.calls[0]['messages'][0]['content']

def test_optional_search_failure_does_not_block_book_based_initial():
 def forbidden(*args):raise AssertionError('Search must not run')
 r=engine.generate(Model([initial()]),'冷门问题',CAST,'deepseek-v4-pro',forbidden)
 assert r['external_status']=='UNAVAILABLE'

def test_quarantined_book_cases_are_not_retrieved():
 excluded={c['id'] for c in engine.CASES if not c.get('retrieval_eligible')}
 for q in QUESTIONS:assert not excluded & {c['id'] for c in engine.reference_cases(q,CAST)}

def test_canonical_five_element_tables_are_exact():
 from hexagrams import GENERATES,CONTROLS
 assert GENERATES=={'木':'火','火':'土','土':'金','金':'水','水':'木'}
 assert CONTROLS=={'木':'土','土':'水','水':'火','火':'金','金':'木'}

@pytest.mark.parametrize('source',['木','火','土','金','水'])
@pytest.mark.parametrize('target',['木','火','土','金','水'])
def test_all_explicit_elemental_edges_match_canonical_theory(source,target):
 from hexagrams import GENERATES,CONTROLS
 from reading_guard import validate_explicit_relations
 for name,table in [('生',GENERATES),('克',CONTROLS)]:
  text=source+name+target
  if table[source]==target:validate_explicit_relations(text)
  else:
   with pytest.raises(ValueError):validate_explicit_relations(text)
