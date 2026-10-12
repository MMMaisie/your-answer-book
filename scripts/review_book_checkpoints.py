"""Compare independently transcribed intermediate book claims, including gaps."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from hexagrams import build_cast
from judgement_engine import evaluate
from scripts.source_amendments import apply_source_amendments
def subset(value,expected):return all(value.get(k)==v for k,v in expected.items())
def checkpoint_matches(r,claim):
    kind=claim['kind'];actual=None
    if kind=='triple':
        member_set={tuple(m) for m in claim['members']}
        matches=[t for t in r['triple_reviews'] if t['branches']==claim['branches'] and
                 {(m['layer'],m['position']) for m in t['members']}==member_set]
        actual=matches;matched=bool(matches)
        if claim.get('release'):matched=matched and any(subset(c,claim['release']) for t in matches for c in t['release_conditions'])
    elif kind in ('structure','absent_structure'):
        actual=[s for s in r['change_structure_reviews'] if subset(s,claim['match'])]
        matched=bool(actual) if kind=='structure' else not actual
    elif kind=='punishment':
        actual=[p for p in r['punishment_reviews'] if p['branches']==claim['branches']]
        matched=any(c['calendar_support']==claim['support'] for p in actual for c in p['candidate_conditions'])
    elif kind=='activation':
        actual=next(a for a in r['line_assessments'] if a['position']==claim['position'])
        matched=actual['activation']==claim['expected']
    elif kind=='line_finding':
        actual=next(a for a in r['line_assessments'] if a['position']==claim['position'])
        matched=any(f['code']==claim['code'] for f in actual['findings'])
    elif kind=='line_condition':
        actual=next(a for a in r['line_assessments'] if a['position']==claim['position'])
        matched=claim['condition'] in actual['unresolved']+actual['waiting']
    elif kind=='line_field':
        actual=next(a for a in r['line_assessments'] if a['position']==claim['position'])
        matched=subset(actual,claim['expected'])
    elif kind=='primary_position':
        selection=r['selection']
        actual=selection['positions'][0] if selection['status']=='UNIQUE_CANDIDATE' and len(selection['positions'])==1 else None
        matched=actual==claim['expected']
    else:raise ValueError('unknown checkpoint kind')
    return matched,actual

def run(release='v39'):
    fixture=json.loads((ROOT/'research'/('v36_book_checkpoints.json' if release in ('v36','v37','v38','v39') else 'v32_book_checkpoints.json')).read_text())
    if release in ('v33','v34','v35'):
        fixture['cases'].append({'id':'BOOK-P082-L1','source':'第三部分第4页，书页82，左上妻占夫近病',
            'context':{'focal_kin':'官鬼'},'checks':[{'kind':'activation','position':6,'expected':'DARK_MOVEMENT_LOCAL'}]})
    sources={c['inventory_id']:c for c in apply_source_amendments(json.loads((ROOT/'research/all_source_case_records.json').read_text())['cases'])}
    cases=[]
    for case in fixture['cases']:
        s=sources[case['id']];cast=build_cast(s['words']);cast['calendar']=s['calendar']
        r=evaluate(s['question'],cast,case['context']);checks=[]
        for claim in case['checks']:
            matched,actual=checkpoint_matches(r,claim)
            checks.append({'expected_from_book':claim,'actual':actual,'status':'MATCH' if matched else 'NEEDS_RULE_COMPLETION'})
        cases.append({'id':case['id'],'source':case['source'],'source_issue':case.get('source_issue'),
            'status':'SELECTED_CHECKPOINTS_MATCH' if all(c['status']=='MATCH' for c in checks) else 'CHECKPOINT_GAP',
            'full_case_reasoning_certified':False,'historical_outcomes_used':False,'checks':checks})
    report={'scope':fixture['scope'],'cases_reviewed':len(cases),
        'selected_checkpoint_matches':sum(c['status']=='SELECTED_CHECKPOINTS_MATCH' for c in cases),
        'cases_with_checkpoint_gaps':sum(c['status']=='CHECKPOINT_GAP' for c in cases),
        'full_case_passes':'NOT_CERTIFIED','api_calls':0,'release_approved':False,'cases':cases}
    (ROOT/'research'/f'{release}_book_checkpoint_review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='cases'},ensure_ascii=False));return report
if __name__=='__main__':run()
