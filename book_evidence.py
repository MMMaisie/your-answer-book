"""Retrieve independently selected book checkpoints with honest scope.

Raw OCR and field-matched case lessons are not complete judgement gold.
Only source-specific intermediate claims which the current engine matches
can accompany its immutable record; nothing here grants an outcome verdict.
"""
import hashlib,json
from pathlib import Path
from book_cases import retrieve_cases, CASE_BOOK

PATH=Path(__file__).parent/'research'/'v36_book_checkpoints.json'
DATA=PATH.read_bytes()
VERSION=hashlib.sha256(DATA).hexdigest()[:12]

def retrieve_book_evidence(question,cast):
    # Use the source-authored expected claims, never last-run PASS reports.
    fixture=json.loads(DATA)
    independent={case['id']:case for case in fixture['cases']}
    result=[]
    for case in retrieve_cases(question,cast):
        expected=independent.get(case['id'])
        if not expected:continue
        # This gate validates only the independently authored claims. General
        # lessons, dates and historical outcomes are deliberately not returned.
        from scripts.review_book_checkpoints import checkpoint_matches
        from judgement_engine import evaluate
        from hexagrams import build_cast
        original=build_cast(list(map(int,next(c['words'] for c in CASE_BOOK['cases'] if c['id']==case['id']))))
        original['calendar']=case['calendar']
        reasoning=evaluate(case['question'],original,expected.get('context'))
        checks=[claim for claim in expected['checks'] if checkpoint_matches(reasoning,claim)[0]]
        if len(checks)!=len(expected['checks']):continue
        result.append({'id':case['id'],'source':case['source'],'checks':checks,
            'validation':'SELECTED_INTERMEDIATE_CHECKPOINTS_ONLY',
            'full_case_certified':False,'target_chart_applicability':'MUST_USE_CURRENT_PROGRAM_RECORD',
            'historical_outcome_included':False})
    return {'version':VERSION,'cases':result,'scope':'SOURCE_CHECKPOINT_CONTEXT_NOT_NEW_JUDGEMENT_AUTHORITY',
            'raw_ocr_used':False,'complete_book_certified':False}
