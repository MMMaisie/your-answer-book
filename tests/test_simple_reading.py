import copy,json
from types import SimpleNamespace as NS
from pathlib import Path
import pytest
import simple_reading as engine
from hexagrams import build_cast

CAST=build_cast([2,2,2,2,0,2])

def sample():
 return {
  'analysis':'按求职问题综合职位与文书因素，取用由模型比较。支持与限制应分别核对，不能把卦象等同已经录用。',
  'free':{'direction':'这次求职有继续推进的机会，但录用结果还不能当作已经确定。','evidence':'眼下仍有尚未落实的条件，现有支持需要继续观察，不能只凭一时顺利就认定已经稳了。'},
  'paid':{
   'priorities':'这次求职有继续推进的机会，但录用结果仍有条件。判断应围绕职位机会、申请材料与自身状态分别展开，不能把其中一项有利直接当作已经录用。若问题涉及多家公司，要保留各自条件，避免把不同机会合成一个确定结果。',
   'conditions':'主要风险是支持因素尚未落实，现阶段仍需比较有利与受限条件；已有支持值得保留，也不能忽略后续阻力。转折要看原有支持能否继续发挥、关键限制是否减轻，大致节奏只能作条件性判断，不能给出确定日期。',
   'actions':'先确认招聘方已经完成哪些环节、还缺哪些材料，区分正式答复与口头表达。再核对后续安排，保留其他申请机会；以实际进展确认条件是否改善，收到明确通知后再决定下一步。'},
  'sources':[{'id':'focal','application':'职位与文书依据问意分别审查，不机械指定唯一用神。'},{'id':'QA-18','application':'按当前问意综合判断，不把历史案例结局复制过来。'}]}

class Model:
 def __init__(self,replies):self.replies=list(replies);self.calls=[];self.chat=NS(completions=NS(create=self.create))
 def create(self,**kw):
  self.calls.append(kw)
  return NS(choices=[NS(finish_reason='stop',message=NS(content=json.dumps(self.replies.pop(0),ensure_ascii=False)))])

MATRIX=json.loads((Path(__file__).with_name('colloquial_cases.json')).read_text())
QUESTIONS=[q for group in MATRIX.values() for q in group['questions']]

@pytest.mark.parametrize('question',QUESTIONS)
def test_every_question_reaches_model_with_book_theory_and_chart_without_classification_gate(question):
 data,refs=engine.context(question,CAST)
 assert data['question']==question
 assert len(data['book_rules'])>=104
 assert data['foundation_facts'] and data['cast']['rows']==CAST['rows']
 assert not any(k in data for k in ('allowed_primary_positions','forced_direction','selection','focal_kin'))
 assert all(c['id'] in refs for c in data['book_cases'])


def test_one_generation_contains_both_tiers_from_same_analysis():
 value=sample();model=Model([value]);result=engine.generate(model,'我什么时候能拿到offer？',CAST,'mock')
 assert len(model.calls)==1 and result['bundle']==value
 assert 50<=engine.count(''.join(value['free'].values()),'zh')<=80
 assert 250<=engine.count(''.join(value['paid'].values()),'zh')<=300

@pytest.mark.parametrize('claim',['水克土','金生火','辰土生子水','火生水'])
def test_basic_element_errors_are_rejected_without_forcing_complex_judgement(claim):
 value=sample();value['analysis']=claim
 _,refs=engine.context('求职',CAST)
 with pytest.raises(ValueError):engine.check_bundle(value,CAST,refs)


def test_program_does_not_impose_a_primary_choice_on_the_model():
 value=sample();value['analysis']='按问意比较官鬼职位与父母文书，并结合世应、日月与动变分析；不机械取第一个候选。'
 _,refs=engine.context('我跟他能不能结婚？',CAST)
 assert engine.check_bundle(value,CAST,refs)==value


def test_no_case_triggers_optional_search_and_never_fakes_search_success():
 calls=[]
 data,_=engine.context('冷门问题没有对应案例',CAST,lambda topics:calls.append(topics) or {'status':'NOT_CONFIGURED','results':[]})
 assert len(calls)==1 and data['external_reference']['status']=='NOT_CONFIGURED'


def test_conflicting_free_paid_outlooks_are_rejected():
 value=sample();value['free']['direction']='整体偏有利。'+value['free']['direction'][6:]
 value['paid']['priorities']='整体偏不利。'+value['paid']['priorities'][6:]
 _,refs=engine.context('求职',CAST)
 with pytest.raises(ValueError,match='contradict'):engine.check_bundle(value,CAST,refs)


def test_invalid_source_is_not_accepted_as_book_reference():
 value=sample();value['sources'][0]['id']='MADE_UP'
 _,refs=engine.context('求职',CAST)
 with pytest.raises(ValueError,match='reference'):engine.check_bundle(value,CAST,refs)


def test_bad_length_has_only_one_bounded_correction():
 bad=sample();bad['free']['direction']='太短';bad['free']['evidence']='太短'
 model=Model([bad,sample()]);engine.generate(model,'求职',CAST,'mock')
 assert len(model.calls)==2
 model=Model([bad,bad])
 with pytest.raises(ValueError):engine.generate(model,'求职',CAST,'mock')
 assert len(model.calls)==2


def test_quarantined_cases_are_never_retrieved():
 excluded={c['id'] for c in engine.CASES if not c.get('retrieval_eligible')}
 for q in QUESTIONS:assert not excluded & {c['id'] for c in engine.reference_cases(q,CAST)}


def test_artwork_meanings_are_not_used_as_chart_evidence():
 data,_=engine.context('我能拿到offer吗',CAST)
 assert 'meaning' not in data['cast']['main'] and 'motif' not in data['cast']['main']
 assert data['cast']['main']['name']==CAST['main']['name']


def test_free_outlook_contract_and_paid_detail_boundary():
 assert '免费不得透露具体障碍' in engine.SYSTEM
 assert '详细依据、关键障碍、条件和建议全部放在付费' in engine.SYSTEM
 assert engine.HEADINGS['zh']['free'] == ('初判', '整体倾向')
 assert engine.HEADINGS['en']['free'] == ('Initial reading', 'Overall outlook')
 free = engine.render(sample(), 'free')
 assert '规则依据' not in free
 assert sample()['paid']['conditions'] not in free
 assert '关键依据' not in free


def test_length_repair_preserves_original_analysis_and_paid_text():
 bad=sample();bad['free']['direction']='太短';bad['free']['evidence']='太短'
 corrected={'free':sample()['free']}
 model=Model([bad,corrected])
 result=engine.generate(model,'求职',CAST,'mock')['bundle']
 assert result['analysis']==bad['analysis']
 assert result['paid']==bad['paid']
 assert result['sources']==bad['sources']
 assert len(model.calls)==2
 assert '只做正文编辑' in model.calls[1]['messages'][0]['content']
