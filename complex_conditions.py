"""Book-conditioned interaction records, never forecasts or outcome lookup.

Each member retains its layer and parent. Changed branches can participate in
their own inner/outer combination, not act as independent cross-line agents.
Matched structure and effective application are deliberately separate fields.
"""
from itertools import product
from hexagrams import ELEMENTS, GENERATES, CONTROLS, assemble
from reading_knowledge import branch_relation, CLASH, GROWTH
from returning_conditions import returning_control_requires_review

TRIPLES={'申子辰':'水','巳酉丑':'金','寅午戌':'火','亥卯未':'木'}
ACTIVE=('MOVING','DARK_MOVEMENT_LOCAL')
# Book part 2 PDF p3, printed p41: 卦之反吟 is not 爻之反吟.
FANYIN_PAIRS={frozenset(p) for p in ('乾巽','坎离','艮坤','震兑')}

def member(row, assessment, layer='main'):
    branch=row['branch'] if layer=='main' else row['changed']['branch']
    return {'position':row['position'],'layer':layer,'branch':branch,
            'activation':assessment['activation'] if layer=='main' else 'CHANGED_FROM_MOVING_PARENT',
            'active':assessment['activation'] in ACTIVE if layer=='main' else bool(row['moving']),
            'parent_local_status':assessment['local_status']}

def triple_conditions(rows, assessments, calendar, assess):
    bypos={a['position']:a for a in assessments};nodes=[]
    for row in rows:
        nodes.append(member(row,bypos[row['position']]))
        if row.get('moving') and row.get('changed'):
            nodes.append(member(row,bypos[row['position']],'changed'))
    # Day/month can supply a missing branch; they do not activate other static
    # members. Keep two moving agents as the minimum for these candidates.
    for period in ('day','month'):
        value=calendar.get(period)
        if value and value[-1] in ELEMENTS:
            nodes.append({'position':None,'layer':period,'branch':value[-1],
                          'activation':'CALENDAR_MEMBER','active':False})
    results=[]
    for branches,element in TRIPLES.items():
        pools=[[n for n in nodes if n['branch']==b] for b in branches]
        missing=[b for b,p in zip(branches,pools) if not p]
        if missing:
            available=[n for p in pools for n in p if n['position'] and n['active']]
            if len({n['branch'] for n in available})>=2:
                results.append({'branches':branches,'element':element,'members':available,
                    'positions':sorted({n['position'] for n in available}),
                    'status':'MISSING_MEMBER','missing_branches':missing,
                    'release_conditions':[{'kind':'MISSING_BRANCH','branch':b} for b in missing],
                    'source_ids':['QA-04','triple_missing_static'], 'effective':False})
            continue
        for chosen in product(*pools):
            chart=[n for n in chosen if n['position'] is not None]
            moving_positions={n['position'] for n in chart if n['active']}
            periods=[n for n in chosen if n['position'] is None]
            if len(chart)<2 or (periods and len(moving_positions)<2):continue
            # All-static branch presence is not a combination activation rule.
            if not moving_positions:continue
            gates=[];release=[]
            if len(moving_positions)<2:gates.append('ACTIVATION_PATTERN_REQUIRES_REVIEW')
            if any(n['layer']=='changed' for n in chart) and len({(n['position']-1)//3 for n in chart})>1:
                gates.append('CHANGED_MEMBERS_CROSS_HALVES_REQUIRES_REVIEW')
            for n in chart:
                row=rows[n['position']-1];a=bypos[n['position']]
                if n['layer']=='changed':
                    a=assess({**row,**row['changed'],'changed':None,'moving':False},calendar,'changed')
                    parent=bypos[n['position']]
                    gates.extend(f"parent:{n['position']}:{u}" for u in parent['unresolved']+parent['waiting'])
                    if parent['local_status']=='RETURNING_CONTROL_RESTRICTION':
                        gates.append(f"parent:{n['position']}:RETURNING_CONTROL_RESTRICTION")
                # Changed branches are legitimate local combination members,
                # but that does not grant them cross-line agency.
                unknown=[u for u in a['unresolved'] if u!='CHANGED_LINE_NOT_INDEPENDENT_CROSS_LINE_AGENT']
                gates.extend(f"{n['layer']}:{n['position']}:{u}" for u in unknown+a['waiting'])
                if a['local_status']=='RETURNING_CONTROL_RESTRICTION':
                    gates.append(f"main:{n['position']}:RETURNING_CONTROL_RESTRICTION")
                if not n['active']:
                    release.append({'kind':'STATIC_MEMBER_VALUE_DAY','position':n['position'],'branch':n['branch']})
                if a['void']:release.append({'kind':'VOID_RELEASE','position':n['position'],'layer':n['layer'],'branch':n['branch']})
                if a['month_break']:release.append({'kind':'BREAK_RESCUE_OR_MONTH_CHANGE','position':n['position'],'layer':n['layer'],'branch':n['branch']})
                for period,relation in a['period_relations'].items():
                    if relation['combine']:
                        release.append({'kind':'COMBINATION_RELEASE_REVIEW','position':n['position'],'layer':n['layer'],
                                        'bound_to':relation['source'],'clash_branch':CLASH[relation['source']]})
                    growth=GROWTH[ELEMENTS[n['branch']]]
                    if relation['source']==growth[1]:
                        release.append({'kind':'TOMB_CLASH_REVIEW','position':n['position'],'layer':n['layer'],
                                        'tomb_branch':growth[1],'clash_branch':CLASH[growth[1]],'period':period})
                    if relation['source']==growth[2]:
                        release.append({'kind':'EXTINCTION_SUPPORT_REVIEW','position':n['position'],'layer':n['layer'],
                                        'growth_branch':growth[0],'period':period})
            status='LOCAL_ACTIVATION_MATCHED_REQUIRES_EFFECT_REVIEW'
            if release:status='WAITING_FOR_MEMBER_CONDITIONS'
            elif gates:status='COMBINATION_CONFLICT_REQUIRES_REVIEW'
            results.append({'branches':branches,'element':element,'members':list(chosen),
                'positions':sorted({n['position'] for n in chart}),'status':status,
                'gates':sorted(set(gates)), 'release_conditions':release,
                'source_ids':['QA-04','triple_members','triple_activation','triple_member_block'],
                'effective':False,'scope':'STRUCTURE_AND_RELEASE_CONDITIONS_NOT_AUTOMATIC_TRANSFORMATION'})
    return results

def transfer_conditions(edges, assessments, comparisons):
    bypos={a['position']:a for a in assessments};chains=[]
    for target in comparisons:
        position=target['candidate']['position'];layer=target['assessment']['layer']
        relevant=[e for e in edges if e['target_position']==position and e['target_layer']==layer]
        for o in (e for e in relevant if e['role']=='原神'):
            for k in (e for e in relevant if e['role']=='忌神'):
                origin=bypos[o['source_position']];obstruction=bypos[k['source_position']]
                if GENERATES[ELEMENTS[obstruction['branch']]]!=ELEMENTS[origin['branch']]:continue
                pair=branch_relation(obstruction['branch'],origin['branch'])
                agents=[obstruction,origin];gates=[]
                for a in agents:
                    gates.extend(f"{a['position']}:{g}" for g in a['unresolved']+a['waiting'])
                    if a['local_status']!='ACTIVE_LOCAL':gates.append(f"{a['position']}:{a['local_status']}")
                    # Nominally moving controllers whose own route is restricted
                    # are kept as evidence, not silently promoted to effective.
                    controllers=[s for s in assessments if s['position']!=a['position'] and
                                 s['activation'] in ACTIVE and CONTROLS[ELEMENTS[s['branch']]]==ELEMENTS[a['branch']]]
                    for s in controllers:
                        if s['local_status']!='RETURNING_CONTROL_RESTRICTION':gates.append(f"{a['position']}:CONTROL_FROM_{s['position']}_REVIEW")
                if pair['clash'] or pair['combine']:gates.append('CHAIN_PAIR_CLASH_OR_COMBINATION')
                gates.extend('TARGET_'+g for g in target['assessment']['unresolved']+target['assessment']['waiting'])
                if target['assessment']['local_status'] in ('RETURNING_CONTROL_RESTRICTION','UNKNOWN_CALENDAR'):
                    gates.append('TARGET_'+target['assessment']['local_status'])
                matched=not gates
                chain={'positions':[obstruction['position'],origin['position'],position], 'target_layer':layer,
                    'state':'LOCAL_TRANSFER_RULE_MATCHED' if matched else 'TRANSFER_CONDITIONS_UNRESOLVED',
                    'gates':sorted(set(gates)),'agents_local_status':[a['local_status'] for a in agents],
                    'source_ids':['obstruction_origin_chain','QA-03'],'event_outcome':'NOT_ASSERTED'}
                chains.append(chain)
                if matched:
                    k['state']='DIRECT_CONTROL_REPLACED_BY_LOCAL_TRANSFER';k['transfer_via_positions']=sorted(set(k.get('transfer_via_positions',[])+[origin['position']]))
    return chains

def change_structures(cast, assessments, candidates):
    """Structural 伏吟/爻反吟; no inference from hexagram name alone."""
    findings=[];bypos={a['position']:a for a in assessments}
    changed_rows=assemble(cast['changed']['bits'],cast['palace']['element'])
    for name,positions in [('inner',[1,2,3]),('outer',[4,5,6])]:
        if not any(cast['rows'][p-1]['moving'] for p in positions):continue
        old=[cast['rows'][p-1]['branch'] for p in positions]
        new=[changed_rows[p-1]['branch'] for p in positions]
        trigram='lower' if name=='inner' else 'upper'
        if frozenset((cast['main'][trigram],cast['changed'][trigram])) in FANYIN_PAIRS:
            findings.append({'kind':'TRIGRAM_FANYIN','scope':name,'positions':positions,
                'main_trigram':cast['main'][trigram],'changed_trigram':cast['changed'][trigram],
                'affected_main_candidates':[c['position'] for c in candidates if c['position'] in positions],
                'source_ids':['QA-05','reversal'],'outcome':'NOT_DETERMINED'})
        if old==new:
            findings.append({'kind':'TRIGRAM_FUYIN','scope':name,'positions':positions,
                'affected_main_candidates':[c['position'] for c in candidates if c['position'] in positions],
                'source_ids':['QA-06'],'outcome':'NOT_DETERMINED'})
    for row in cast['rows']:
        if row.get('moving') and row.get('changed'):
            rel=bypos[row['position']]['returning_relation']
            if rel and rel['clash']:
                findings.append({'kind':'LINE_FANYIN','scope':'line','positions':[row['position']],
                    'returning_element_relation':rel['element_relation'],
                    'affects_main_candidate':row['position'] in [c['position'] for c in candidates],
                    'source_ids':['QA-05','reversal'],'outcome':'NOT_DETERMINED'})
    return findings

def punishment_conditions(cast, assessments, comparisons):
    # QA-14 explicitly excludes 六害. No imported "害必凶" rule is added.
    nodes=[{'layer':'main','position':r['position'],'branch':r['branch']} for r in cast['rows']]
    calendar=cast.get('calendar') or {}
    nodes += [{'layer':p,'position':None,'branch':calendar[p][-1]} for p in ('month','day')
              if calendar.get(p) and calendar[p][-1] in ELEMENTS]
    present={n['branch'] for n in nodes};groups=[]
    for group in ('寅巳申','丑未戌','子卯'):
        if set(group)<=present:
            members=[n for n in nodes if n['branch'] in group]
            groups.append({'branches':group,'members':members,'source_ids':['QA-14','punishment_conditional'],
                'candidate_conditions':[{'position':c['candidate']['position'],'layer':c['assessment']['layer'],
                    'monthly_state':c['assessment']['monthly_state'],'calendar_support':c['assessment']['calendar_support'],
                    'calendar_control':c['assessment']['calendar_control']} for c in comparisons],
                'status':'PUNISHMENT_PRESENT_REVIEW_STRENGTH_AND_EFFECTIVE_CONTROL','outcome':'NOT_DETERMINED'})
    return groups

def release_requirements(comparisons, edges, assessments, triples=()):
    """Dependency ledger for timing review; possible dates are not outcomes.

Do not choose the earliest released condition as a predicted success date.
Every restriction retains its own target, evidence and remaining obligations.
"""
    bypos={a['position']:a for a in assessments};result=[]
    for candidate in comparisons:
        a=candidate['assessment'];requirements=[]
        if a['void']:
            requirements.append({'kind':'VOID_RELEASE_REVIEW','branch':a['branch'],
                'alternatives':['出旬','填实','冲实须另核'],'source_ids':['QA-07','void']})
        if a['month_break']:
            requirements.append({'kind':'BREAK_RELEASE_REVIEW','branch':a['branch'],
                'alternatives':['填实','逢合须另核','出月后复核'],'source_ids':['QA-08','month_break']})
        for period,r in a['period_relations'].items():
            if r['combine']:
                requirements.append({'kind':'COMBINATION_RELEASE_REVIEW','bound_to':r['source'],
                    'clash_branch':CLASH[r['source']],'period':period,'source_ids':['QA-11','QA-04']})
            growth=GROWTH[ELEMENTS[a['branch']]]
            if r['source']==growth[1]:requirements.append({'kind':'TOMB_RELEASE_REVIEW','tomb_branch':growth[1],
                'clash_branch':CLASH[growth[1]],'period':period,'source_ids':['QA-12','QA-04']})
            if r['source']==growth[2]:requirements.append({'kind':'EXTINCTION_RESCUE_REVIEW','growth_branch':growth[0],
                'period':period,'source_ids':['QA-12','rescue']})
        if returning_control_requires_review(a):
            requirements.append({'kind':'OWN_RETURNING_CONTROL_REVIEW','source_ids':['QA-02','QA-03']})
        for e in edges:
            if e['target_position']!=a['position'] or e['target_layer']!=a['layer']:continue
            if e['role']=='原神' and e['state']=='RESTRICTED_AT_SOURCE':
                source=bypos[e['source_position']]
                requirements.append({'kind':'RESTRICTED_ORIGIN_ROUTE_REVIEW','source_position':e['source_position'],
                    'restriction_findings':[f['code'] for f in source['findings']],
                    'does_not_remove_calendar_support':True,'source_ids':['QA-03']})
        for triple in triples:
            # A combination acting as the focal/support/obstruction has member
            # dependencies even when a damaged member is not the focal itself.
            for condition in triple['release_conditions']:
                kind=condition['kind']
                if kind=='BREAK_RESCUE_OR_MONTH_CHANGE':kind='BREAK_RELEASE_REVIEW'
                requirements.append({**condition,'kind':kind,'dependency_scope':'COMBINATION_MEMBER',
                    'combination_branches':triple['branches'],'combination_element':triple['element'],
                    'combination_to_candidate':branch_relation(triple['branches'][1],a['branch'])['element_relation'],
                    'application':'IF_RELYING_ON_THIS_COMBINATION_EFFECT_STILL_UNVERIFIED',
                    'source_ids':triple['source_ids']})
        result.append({'candidate':candidate['candidate'],'layer':a['layer'],'requirements':requirements,
            'remaining_unresolved':a['unresolved'],'remaining_waiting':a['waiting'],
            'aggregation':'ALL_RELEVANT_RESTRICTIONS_REQUIRE_REASSESSMENT',
            'any_single_release_sufficient':False,'predicted_date':None,'event_outcome':'NOT_ASSERTED'})
    return result
