"""Regressions from the actual paid result, plus valid neighboring claims."""
from datetime import datetime
import pytest
from hexagrams import build_cast,GENERATES,CONTROLS,ELEMENTS
from theory_facts import ledger,validate_theory
from reading_guard import validate_chart_claims
from simple_reading import check_parts,render
CAST=build_cast([0,3,2,3,2,2],datetime(2026,10,31,17,38))

def test_live_cast_fixture_is_the_same_chart():
 assert CAST['main']['number']==37 and CAST['changed']['number']==44
 assert CAST['moving']==[1,2,4]

@pytest.mark.parametrize('text',[
 '世爻丑土月扶日克，化亥水回头生。',
 '原神子孙安静，化午火，支持有限。',
 '五爻子孙巳火化午火。',
 '二爻丑土化午火。',
])
def test_reported_errors_are_not_delivered(text):
 with pytest.raises(ValueError):check_parts({'priorities':text,'conditions':'进展仍有不确定性。','actions':'观察后续变化。'},'paid','zh',CAST)

@pytest.mark.parametrize('text',[
 '四爻未土化午火回头生。',
 '二爻丑土化亥水，本爻克变爻。',
 '五爻子孙巳火安静；四爻未土化午火。',
])
def test_valid_changes_and_separate_static_subject_are_not_blocked(text):
 validate_chart_claims(text,CAST)

@pytest.mark.parametrize('source','子丑寅卯辰巳午未申酉戌亥')
@pytest.mark.parametrize('changed','子丑寅卯辰巳午未申酉戌亥')
def test_returning_relation_direction_with_comma(source,changed):
 for verb,table in [('生',GENERATES),('克',CONTROLS)]:
  text=f'{source}{ELEMENTS[source]}，化{changed}{ELEMENTS[changed]}回头{verb}。'
  if table[ELEMENTS[changed]]==ELEMENTS[source]:validate_theory(text,{})
  else:
   with pytest.raises(ValueError):validate_theory(text,{})

def test_changed_facts_are_scoped_to_their_own_moving_line():
 facts={f['id']:f for f in ledger(CAST)['lines']}
 assert facts['2.changed']['element_relation']=='is_controlled_by'
 assert facts['4.changed']['element_relation']=='generates'
 assert '5.changed' not in facts

def test_free_render_has_single_heading_at_template_level():
 assert render({'free':{'direction':'感情进展偏慢。'}},'free')=='感情进展偏慢。'
