"""Closed decision protocol; completeness of control flow is not rule certification.

Every input terminates at a justified decision or an explicit unresolved gate.
Candidate comparison and timing cannot be supplied by the language model.
"""
def build_decision_flow(reasoning):
    selection=reasoning['selection'];intent=reasoning['intent'];stages=[];missing=[]
    audit=reasoning['calendar_audit']
    duration_conflict=intent.get('illness',{}).get('status') in ('CONFLICTED_DURATION_CONTEXT','INVALID_DURATION_CONTEXT')
    stages.append({'stage':'INPUT','status':'READY' if audit['status']=='VALID' else 'NEEDS_INPUT',
                   'reasons':audit['issues']})
    missing.extend(audit['issues'])
    if not intent['kin']:
        missing.append('ASK_SUBJECT_AND_RELATION_TO_QUESTIONER')
        missing.extend(intent.get('context_questions',[]))
    stages.append({'stage':'SUBJECT','status':'READY' if intent['kin'] and not duration_conflict else 'NEEDS_CONTEXT',
                   'kin':intent['kin'],'method':intent['method'],'illness':intent.get('illness',{})})
    candidates=reasoning['candidate_comparisons']
    options=[]
    for c in candidates:
        a=c['assessment']
        options.append({'position':c['candidate']['position'],'layer':a['layer'],'branch':a['branch'],
            'holds_self':c['holds_self'],'activation':a['activation'],'void':a['void'],
            'month_break':a['month_break'],'calendar_support':a['calendar_support'],
            'calendar_control':a['calendar_control'],'waiting':a['waiting'],'unresolved':a['unresolved']})
    unique=selection['status']=='UNIQUE_CANDIDATE'
    comparison_review=selection.get('comparison_review',{})
    missing.extend(comparison_review.get('required_checks',[]))
    if not candidates and intent['kin']:missing.append('NO_SOURCED_FOCAL_CANDIDATE')
    if len(candidates)>1:
        missing.append('COMPARE_MULTIPLE_CANDIDATES_WITH_SOURCE_CONDITIONS')
        if intent['horizon']=='unspecified':missing.append('ASK_NEAR_OR_FAR_SCOPE')
        if intent['purpose']=='general':missing.append('ASK_OUTCOME_OR_TIMING_OR_SPECIFIC_CONCERN')
    stages.append({'stage':'FOCAL_SELECTION','status':'SELECTED' if unique else 'NEEDS_COMPARISON' if candidates else 'UNRESOLVED',
        'primary_position':selection['positions'][0] if unique else None,'options':options,
        'comparison_review':comparison_review,
        'policy':'NO_UNIVERSAL_MOVING_VOID_STRONGEST_PRIORITY','source_ids':['QA-17','QA-18']})
    restrictions=[]
    for c in candidates:
        a=c['assessment']
        for g in a['waiting']+a['unresolved']:
            restrictions.append({'position':a['position'],'layer':a['layer'],'condition':g})
        if a['local_status'] in ('RETURNING_CONTROL_RESTRICTION','UNKNOWN_CALENDAR'):
            restrictions.append({'position':a['position'],'layer':a['layer'],'condition':a['local_status']})
    unresolved_routes=[{'source_position':e['source_position'],'target_position':e['target_position'],
        'role':e['role'],'state':e['state'],'gates':e['gates']} for e in reasoning['effect_edges']
        if e['role'] in ('原神','忌神') and e['state'] in ('CONDITIONAL_RELATION','RESTRICTED_AT_SOURCE')]
    stages.append({'stage':'EFFECTIVENESS','status':'LOCAL_CONDITIONS_ONLY',
        'focal_restrictions':restrictions,'unresolved_routes':unresolved_routes,
        'complete_chart_certified':False})
    timing={'status':'NOT_REQUESTED','primary_position':None,'requirements':[],
        'unresolved_routes':unresolved_routes,'date':None,'unit':intent.get('time_unit'),
        'single_release_sufficient':False,'event_outcome':'NOT_ASSERTED'}
    if intent['purpose']=='timing':
        if not unique:timing['status']='BLOCKED_BY_FOCAL_SELECTION'
        elif audit['status']!='VALID':timing['status']='BLOCKED_BY_CALENDAR'
        else:
            timing['primary_position']=selection['positions'][0]
            ledgers=[x for x in reasoning['release_requirements'] if x['candidate']['position']==timing['primary_position']
                     and x['layer']==selection['layer']]
            timing['requirements']=[g for x in ledgers for g in x['requirements']]
            timing['status']='CONDITIONAL_WINDOWS_REQUIRE_FULL_REASSESSMENT' if timing['requirements'] else 'NO_VERIFIED_TIMING_RULE'
            timing['remaining_waiting']=[g for x in ledgers for g in x['remaining_waiting']]
            timing['remaining_unresolved']=[g for x in ledgers for g in x['remaining_unresolved']]
            if not timing['unit']:missing.append('ASK_DAY_MONTH_YEAR_OR_HOUR_UNIT')
            missing.append('VERIFY_EVENT_SCOPE_AND_FULL_TIMING_CONDITIONS')
    stages.append({'stage':'TIMING',**timing})
    terminal='NEEDS_INPUT' if audit['status']!='VALID' else 'NEEDS_SUBJECT_CONTEXT' if not intent['kin'] else \
        'NEEDS_FOCAL_COMPARISON' if not unique else 'LOCAL_CONDITIONAL_JUDGEMENT'
    if duration_conflict and audit['status']=='VALID':
        terminal='NEEDS_SUBJECT_CONTEXT'
        timing['status']='BLOCKED_BY_CONFLICTED_ILLNESS_CONTEXT'
        stages[-1]['status']=timing['status']
    return {'protocol':'decision-flow-v1','stages':stages,'terminal_status':terminal,
        'next_required_checks':sorted(set(missing)),'program_direction':reasoning['synthesis']['status'],
        'complete_control_flow':True,'complete_classical_rules_certified':False,
        'model_may_choose_primary':False,'model_may_choose_date':False,'source_ids':['QA-17','QA-18','QA-07','QA-12']}
