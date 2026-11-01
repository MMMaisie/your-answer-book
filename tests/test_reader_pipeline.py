import copy,json
from datetime import datetime
import pytest
import app as site
import simple_reading as engine
from reading_contract import validate_evidence,validate_reader_text,EvidenceError,EditorialError
from theory_facts import ledger
from hexagrams import build_cast
from conftest import Model,initial,full,review,checks,submit,csrf
from test_guest_flow import row,paid,post_generate
CAST=build_cast([1,1,2,2,1,0],datetime(2026,11,1,19,23))

@pytest.mark.parametrize('field,value', [('branch','Hai'),('kin','父母'),('moving',True),('moving',0)])
def test_evidence_values_and_types_must_match_own_line(field,value):
 items=checks(CAST);items[0]['claim'][field]=value
 with pytest.raises(EvidenceError):validate_evidence(items,CAST)

def test_correct_fact_cannot_be_attached_to_another_line():
 items=checks(CAST);items[0]['position']=3
 with pytest.raises(EvidenceError):validate_evidence(items,CAST)

def test_changed_and_hidden_facts_are_distinct_from_original():
 facts={f['id']:f for f in ledger(CAST)['lines']}
 records=[]
 for fid in ['1.state','3.hidden','6.changed']:
  records.append({'fact_id':fid,'position':int(fid[0]),'claim':{k:v for k,v in facts[fid].items() if k!='id'}})
 assert len(validate_evidence(records,CAST))==3
 records[1]['claim']['kin']='妻财'
 with pytest.raises(EvidenceError):validate_evidence(records,CAST)

def test_nonmoving_line_cannot_supply_a_change_record():
 items=checks(CAST);items[0]['fact_id']='1.changed'
 with pytest.raises(EvidenceError):validate_evidence(items,CAST)

def test_unknown_and_missing_fact_attributes_are_rejected():
 for change in [{'bad':True},{}]:
  items=checks(CAST);items[0]['claim']=change
  with pytest.raises(EvidenceError):validate_evidence(items,CAST)

@pytest.mark.parametrize('text',[
 '近期不易快速有结果，整体偏慢；需等待用神状态改善，留意出空、出伏等时机。',
 '近期出伏后更有希望。',
])
def test_real_preview_technical_leak_requests_one_bounded_rewrite(text):
 bad=initial(CAST);bad['free']['direction']=text
 good=initial(CAST);good['free']['direction']='眼下进展偏慢，近期不宜期待迅速确定关系。'
 m=Model([bad,good]);value=engine.generate(m,'什么时候能找到对象？',CAST,'deepseek-v4-pro')
 assert value['bundle']['free']==good['free'] and len(m.calls)==2
 assert '免费不出现术语' in m.calls[-1]['messages'][-1]['content']

@pytest.mark.parametrize('text',[
 '男看妻财，申酉空且世爻月破日克；女看官鬼亥水，月克日泄，伏神无力。',
 '世爻受制直接影响吸引力和行动力，应恢复精力，减少内耗。',
])
def test_real_publication_faults_do_not_pass_editor(text):
 with pytest.raises(EditorialError):validate_reader_text(text,'paid','zh','什么时候能找到对象？')

def test_reason_must_reference_a_checked_fact():
 r=review(cast=CAST);r['reasons'][0]['fact_ids']=['6.changed']
 with pytest.raises(EvidenceError):engine._check_review(r,CAST,{'focal':{}},'找对象','mixed')

def test_writer_has_no_raw_chart_or_internal_notes():
 r=review(cast=CAST);r['technical_summary']='初爻子孙辰土持世，上爻兄弟巳火化子孙戌土。'
 r['technical_anchor_ids']=['1.state']
 m=Model([full()]);engine.generate_paid(m,'找对象',CAST,'deepseek-v4-pro',initial(CAST),reviewed_plan=r)
 task=json.loads(m.calls[0]['messages'][1]['content'])
 assert 'reference' not in task and 'previous_initial' not in task
 assert 'technical_summary' not in task['reviewed_brief'] and 'fact_checks' not in task['reviewed_brief']
 assert task['reviewed_brief']['checked_fact_notes']==['第1爻子孙辰土，为静爻']

def test_review_can_correct_initial_but_writer_cannot_change_review():
 r=review('difficult',CAST);value=full('difficult')
 m=Model([r,value]);assert engine.generate_paid(m,'找对象',CAST,'deepseek-v4-pro',initial(CAST))==value['paid']
 bad=full('favorable')
 with pytest.raises(ValueError):engine.generate_paid(Model([bad,bad]),'找对象',CAST,'deepseek-v4-pro',initial(CAST),reviewed_plan=r)
 r['correction_reason']=''
 with pytest.raises(ValueError):engine._check_review(r,CAST,{'focal':{}},'找对象','mixed')

def test_writer_retry_reuses_persisted_review_without_repeating_analysis(client,monkeypatch):
 m=Model([initial(),review(),RuntimeError('writer unavailable')]);monkeypatch.setattr(site,'OpenAI',lambda **kw:m)
 submit(client);r=row(client);paid(r);post_generate(client,r)
 stored=json.loads(row(client)['bundle_json'])
 assert stored.get('paid_review') and not row(client)['paid_zh'] and len(m.calls)==3
 m.replies.append(full());post_generate(client,row(client))
 assert row(client)['paid_zh'] and len(m.calls)==4
 assert 'reviewed_brief' in json.loads(m.calls[-1]['messages'][1]['content'])

def test_corrected_preview_and_notice_are_saved_without_regranting_free_quota(client,monkeypatch):
 m=Model([initial(),review('difficult'),full('difficult')]);monkeypatch.setattr(site,'OpenAI',lambda **kw:m)
 response=submit(client);r=row(client);paid(r)
 with site.store.connect() as c:
  c.execute("UPDATE ab49_readings SET free_en='old English preview' WHERE id=?",(r['id'],))
 post_generate(client,r);r=row(client);stored=json.loads(r['bundle_json'])
 assert r['free_zh']==review('difficult')['revised_free'] and not r['free_en']
 assert stored['previous_initial']['outlook']=='mixed' and stored['bundle']['outlook']=='difficult'
 assert '初判已作调整' in client.get(response.location).text
 with site.store.connect() as c:assert c.execute('SELECT COUNT(*) AS n FROM ab49_trials').fetchone()['n']==2

def test_old_legacy_core_is_reviewed_instead_of_rejected(client,monkeypatch):
 m=Model([initial(),review(),full()]);monkeypatch.setattr(site,'OpenAI',lambda **kw:m)
 submit(client);r=row(client);stored=json.loads(r['bundle_json']);stored['bundle'].pop('fact_checks')
 with site.store.connect() as c:c.execute('UPDATE ab49_readings SET bundle_json=? WHERE id=?',(json.dumps(stored),r['id']))
 paid(r);post_generate(client,r);assert row(client)['paid_zh'] and len(m.calls)==3

def test_incorrect_focal_citation_cannot_hide_behind_another_checked_fact():
 value=initial(CAST);value['decision_record']['fact_ids']=['6.changed']
 with pytest.raises(ValueError):engine.generate(Model([value,value]),'找对象',CAST,'deepseek-v4-pro')
