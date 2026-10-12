"""Bounded dynamic rescue qualification, not full strength or an event verdict.

The initial assessment is frozen. Only independently available 明动 can
qualify a weak static day-clashed line; rescued 暗动 never proves itself or
another rescue. Changed/hidden branches are not independent agents.
"""
from hexagrams import ELEMENTS,GENERATES,CONTROLS
from reading_knowledge import branch_relation

def qualify_dynamic_rescue(assessments):
    available=[a for a in assessments if a['activation']=='MOVING' and a['local_status']=='ACTIVE_LOCAL']
    nominal=[a for a in assessments if a['activation']=='MOVING']
    reviews=[]
    for target in assessments:
        if target['activation']!='WEAK_DAY_CLASH_REVIEW':continue
        candidates=[];eligible=[]
        for source in assessments:
            if source['position']==target['position'] or GENERATES[ELEMENTS[source['branch']]]!=ELEMENTS[target['branch']]:continue
            gates=list(source['waiting'])+list(source['unresolved'])
            if source['local_status']!='ACTIVE_LOCAL' or source['activation']!='MOVING':gates.append('SOURCE_NOT_INDEPENDENTLY_AVAILABLE_BRIGHT_MOVEMENT')
            controllers=[a for a in nominal if a['position']!=source['position'] and
                CONTROLS[ELEMENTS[a['branch']]]==ELEMENTS[source['branch']] and a['local_status']!='RETURNING_CONTROL_RESTRICTION']
            if controllers:gates.append('SOURCE_HAS_OTHER_MOVING_CONTROL_REVIEW')
            relation=branch_relation(source['branch'],target['branch'])
            if relation['combine'] or relation['clash']:gates.append('SOURCE_TARGET_COMBINATION_OR_CLASH_REVIEW')
            candidate={'source_position':source['position'],'source_branch':source['branch'],
                'local_status':source['local_status'],'gates':sorted(set(gates)),
                'state':'AVAILABLE_LOCAL_GENERATING_ROUTE' if not gates else 'RESTRICTED_OR_UNRESOLVED_ROUTE'}
            candidates.append(candidate)
            if not gates and source in available:eligible.append(source)
        blockers=list(target['waiting'])+[u for u in target['unresolved'] if u!='DAY_CLASH_NEEDS_DYNAMIC_RESCUE_REVIEW']
        if target['period_relations']['day']['element_relation']=='克':blockers.append('DAY_CONTROLS_TARGET_REQUIRES_FULL_RESCUE_REVIEW')
        if any(a['position']!=target['position'] and CONTROLS[ELEMENTS[a['branch']]]==ELEMENTS[target['branch']] and
               a['local_status']!='RETURNING_CONTROL_RESTRICTION' for a in nominal):
            blockers.append('TARGET_HAS_OTHER_MOVING_CONTROL_REVIEW')
        matched=bool(eligible) and not blockers
        review={'target_position':target['position'],'target_branch':target['branch'],'routes':candidates,
            'status':'LOCAL_DYNAMIC_RESCUE_QUALIFICATION_MATCHED' if matched else 'DYNAMIC_RESCUE_CONDITIONS_UNRESOLVED',
            'target_gates':sorted(set(blockers)),'source_ids':['QA-01','QA-03','rescue','strength_dynamic_joint'],
            'scope':'LOCAL_DARK_QUALIFICATION_NOT_COMPLETE_STRENGTH_OR_FORECAST',
            'full_effect_certified':False,'circular_or_rescued_agents_used':False}
        reviews.append(review)
        if matched:
            target['activation']='DARK_MOVEMENT_LOCAL'
            target['unresolved'].remove('DAY_CLASH_NEEDS_DYNAMIC_RESCUE_REVIEW')
            target['findings'].append({'code':'STATIC_DAY_CLASH_WITH_LOCAL_DYNAMIC_RESCUE','source_ids':review['source_ids'],
                'support_positions':[a['position'] for a in eligible]})
            target['local_status']='ACTIVE_LOCAL'
        target['dynamic_rescue_review']=review
    return reviews

def revalidate_rescue_sources(assessments, reviews):
    """Combination review may restrict a source after initial qualification.

    Preserve activation provenance, but never retain effective availability
    from a source whose final assessment now requires review.
    """
    bypos={a['position']:a for a in assessments}
    for review in reviews:
        if review['status']!='LOCAL_DYNAMIC_RESCUE_QUALIFICATION_MATCHED':continue
        eligible=[r for r in review['routes'] if r['state']=='AVAILABLE_LOCAL_GENERATING_ROUTE']
        available=[r for r in eligible if bypos[r['source_position']]['local_status']=='ACTIVE_LOCAL'
                   and not bypos[r['source_position']]['waiting'] and not bypos[r['source_position']]['unresolved']]
        review['final_available_source_positions']=[r['source_position'] for r in available]
        if available:continue
        target=bypos[review['target_position']]
        review['status']='RESCUE_SOURCE_RESTRICTED_AFTER_INTERACTION_REVIEW'
        review['target_gates'].append('RESCUE_SOURCE_FINAL_EFFECT_UNRESOLVED')
        target['unresolved'].append('RESCUE_SOURCE_FINAL_EFFECT_UNRESOLVED')
        if target['local_status']=='ACTIVE_LOCAL':target['local_status']='CONDITIONS_REQUIRE_REVIEW'
