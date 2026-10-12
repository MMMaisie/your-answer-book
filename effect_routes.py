"""Audit generating routes without converting a possible chain into a verdict.

This is dependency bookkeeping, not an additional classical rescue rule.
Every hop keeps its own gates; upstream support cannot erase downstream
void, tomb, returning control, combination, or calendar uncertainty.
"""
from hexagrams import ELEMENTS, GENERATES, CONTROLS
from reading_knowledge import branch_relation

ACTIVE=('MOVING','DARK_MOVEMENT_LOCAL')

def audit_generating_routes(assessments, comparisons):
    nodes={a['position']:a for a in assessments}
    reviews=[]
    def hop(source,target):
        gates=[{'position':source['position'],'side':'source','condition':g}
               for g in source['waiting']+source['unresolved']]
        if source['local_status']!='ACTIVE_LOCAL':
            gates.append({'position':source['position'],'side':'source','condition':source['local_status']})
        gates.extend({'position':target['position'],'side':'target','condition':g}
                     for g in target['waiting']+target['unresolved'])
        if target['local_status'] in ('RETURNING_CONTROL_RESTRICTION','UNKNOWN_CALENDAR'):
            gates.append({'position':target['position'],'side':'target','condition':target['local_status']})
        pair=branch_relation(source['branch'],target['branch'])
        if pair['clash'] or pair['combine']:
            gates.append({'position':target['position'],'side':'pair','condition':'PAIR_CLASH_OR_COMBINATION_REVIEW'})
        for other in assessments:
            if other['position']==source['position'] or other['activation'] not in ACTIVE:continue
            if CONTROLS[ELEMENTS[other['branch']]]==ELEMENTS[source['branch']] and other['local_status']!='RETURNING_CONTROL_RESTRICTION':
                gates.append({'position':source['position'],'side':'source','condition':'INCOMING_CONTROL_REQUIRES_REVIEW',
                              'controller_position':other['position'],'controller_local_status':other['local_status']})
        return {'source_position':source['position'],'target_position':target['position'],
                'source_branch':source['branch'],'target_branch':target['branch'],
                'relation':'生','gates':gates,'locally_available':not gates}
    for focal in comparisons:
        # Changed and hidden focal lines retain their separate emergence gates;
        # they must not be confused with a main line at the same position.
        if focal['assessment']['layer']!='main':continue
        target=nodes[focal['candidate']['position']]
        def visit(path):
            downstream=nodes[path[0]]
            for source in assessments:
                pos=source['position']
                if pos in path or source['activation'] not in ACTIVE:continue
                if GENERATES[ELEMENTS[source['branch']]]!=ELEMENTS[downstream['branch']]:continue
                route=[pos]+path
                if len(route)>=3:
                    hops=[hop(nodes[a],nodes[b]) for a,b in zip(route,route[1:])]
                    reviews.append({'positions':route,'target_layer':'main','hops':hops,
                        'status':'ALL_HOPS_LOCALLY_AVAILABLE_NOT_COMPLETE_RESCUE' if all(h['locally_available'] for h in hops)
                                 else 'BLOCKED_OR_UNRESOLVED_GENERATING_ROUTE',
                        'source_ids':['QA-03','rescue'],'scope':'DEPENDENCY_AUDIT_NOT_RULE_FOR_ERASING_RESTRICTIONS',
                        'full_effect_certified':False,'historical_outcomes_used':False})
                visit(route)
        visit([target['position']])
    return reviews
