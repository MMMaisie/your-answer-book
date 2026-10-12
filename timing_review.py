"""Counterfactual day review; fixed month assumption, not an event date."""
from copy import deepcopy

def review_day_scenarios(question,cast,reasoning,limit=12):
    if type(limit) is not int or not 1<=limit<=12:raise ValueError('day review limit must be 1..12')
    intent=reasoning['intent']
    result={'scope':'HYPOTHETICAL_DAY_REASSESSMENT_NOT_EVENT_TIMING','status':'NOT_REQUESTED',
        'assumptions':['MONTH_BRANCH_HELD_FIXED_NOT_A_FUTURE_CALENDAR'],
        'calendar_dates':None,'event_date':None,'unit':'day','windows':[],
        'complete_effect_certified':False,'all_releases_sufficient':False,'api_calls':0}
    if intent['purpose']!='timing':return result
    if intent.get('time_unit') not in (None,'day'):
        result['status']='REQUESTED_UNIT_NEEDS_SEPARATE_RULES';return result
    if reasoning['calendar_audit']['status']!='VALID':
        result['status']='BLOCKED_BY_CALENDAR';return result
    if reasoning['selection']['status']!='UNIQUE_CANDIDATE':
        result['status']='BLOCKED_BY_FOCAL_COMPARISON';return result
    from judgement_engine import evaluate,CYCLE,void_for
    current=cast['calendar'];start=CYCLE.index(current['day'])
    focal=reasoning['candidate_comparisons'][0]['assessment']
    def focal_gates(a):
        gates=set(a['waiting']+a['unresolved'])
        from returning_conditions import returning_control_requires_review
        if returning_control_requires_review(a):gates.add('OWN_RETURNING_CONTROL')
        gates.update(period.upper()+'_CONTROLS_FOCAL' for period in a['calendar_control'])
        return gates
    original=focal_gates(focal)
    for offset in range(1,limit+1):
        future=deepcopy(cast);day=CYCLE[(start+offset)%60]
        # No copied absolute timestamps may imply a real calendar prediction.
        future['calendar']={'month':current['month'],'day':day,'xunkong':void_for(day)}
        r=evaluate(question,future,{'focal_kin':intent['kin'],'purpose':'timing',
                                  'horizon':intent['horizon'],'time_unit':'day'})
        target=next((c['assessment'] for c in r['candidate_comparisons'] if
                     c['assessment']['layer']==focal['layer'] and c['assessment']['position']==focal['position']),None)
        if target is None:continue
        remaining=focal_gates(target)
        origin_edges=[e for e in r['effect_edges'] if e['role']=='原神' and
                      e['target_position']==focal['position'] and e['target_layer']==focal['layer']]
        route_gates=sorted({g for e in origin_edges for g in e['gates']} |
                          {e['state'] for e in origin_edges if e['state']!='ACTIVE_LOCAL_RELATION'})
        no_longer=sorted(original-remaining)
        # No score, best-day choice, or event-outcome assertion.
        if no_longer or remaining!=original:
            result['windows'].append({'cycle_offset':offset,'hypothetical_day':day,
                'hypothetical_void':future['calendar']['xunkong'],
                'conditions_not_triggered_in_this_scenario':no_longer,
                'remaining_focal_conditions':sorted(remaining),'origin_route_gates':route_gates,
                'new_conditions':sorted(remaining-original),'complete_effect_certified':False,
                'event_outcome':'NOT_ASSERTED'})
    result['status']='SCENARIOS_RECOMPUTED_NOT_CERTIFIED_WINDOWS'
    result['scenarios_checked']=limit
    return result
