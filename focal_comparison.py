"""Source criteria, competing claims and missing context for multiple focal lines.

QA-17 supplies comparison criteria, not a universal priority ordering. Keep
their competing claims visible. No case IDs or historical outcomes enter here.
"""

def explicit_relation_subject(question):
    """Resolve a single explicitly stated relation before keyword matching.

    Own aunt and husband's sister differ in the book. Do not infer the
    speaker of bare 姑病, or collapse a sentence naming several subjects.
    """
    import re
    if re.search(r'和|以及|同时|、|\band\b',question,re.I):
        if re.search(r'姑姑|姑妈|姨妈|姨母|伯父|叔父|婶婶|婶母|叔母|(?:丈夫|老公|夫君)的|嫂子|弟媳|husband.s|paternal aunt|maternal aunt|my uncle',question,re.I):
            return 'RELATION_SUBJECTS_NEED_CLARIFICATION'
        return None
    predicates=r'(?:近病|久病|急病|病|身体|健康|平安|何日|何时|什么时候|回来|归|回|能否|是否|会不会|情况|怎样|如何|吉凶|出行|在外)'
    patterns=[
        ('父母',r'^(?:占|问)?(?:我的|我|自己(?:的)?)?(?:伯父|叔父|婶婶|婶母|叔母)'+predicates),
        ('父母',r'^(?:占|问)?(?:我的|我|自己的)(?:姑姑|姑妈|姨妈|姨母)'+predicates),
        ('官鬼',r'^(?:占|问)?(?:我的|我)?(?:丈夫|老公|夫君)的(?:哥哥|弟弟|姐姐|妹妹|兄弟|姐妹)'+predicates),
        ('妻财',r'^(?:占|问)?(?:我的|我)?(?:嫂子|嫂嫂|弟媳|弟妇)'+predicates),
        ('官鬼',r"^my husband's (?:brother|sister)\s+(?:is|has|will|when|returns|returning)\b"),
        ('父母',r'^my (?:paternal aunt|maternal aunt|uncle)\s+(?:is|has|will|when|returns|returning)\b')]
    matches=[kin for kin,pattern in patterns if re.search(pattern,question,re.I)]
    return matches[0] if len(set(matches))==1 else None

def illness_context(question, context):
    import re
    topic = bool(re.search(r'病|疾|illness|sick|disease', question, re.I))
    supplied = context.get('illness_duration')
    recent = bool(re.search(r'近病|急病|新病|recent illness|acute illness', question, re.I))
    chronic = bool(re.search(r'久病|慢性病|chronic illness|longstanding illness', question, re.I))
    mentions = [value for value, present in [('recent', recent), ('chronic', chronic)] if present]
    if supplied is not None:
        if supplied not in ('recent', 'chronic'):
            return {'is_illness':topic, 'duration':None, 'status':'INVALID_DURATION_CONTEXT'}
        if mentions and any(value != supplied for value in mentions):
            return {'is_illness':True, 'duration':None, 'status':'CONFLICTED_DURATION_CONTEXT'}
        return {'is_illness':True, 'duration':supplied, 'status':'EXPLICIT_DURATION'}
    return {'is_illness':topic, 'duration':mentions[0] if len(mentions)==1 else None,
        'status':'CONFLICTED_DURATION_CONTEXT' if len(mentions)>1 else
                 'EXPLICIT_DURATION' if mentions else 'DURATION_UNSPECIFIED' if topic else 'NOT_ILLNESS'}

def compare_focal_candidates(comparisons, intent, calendar):
    from reading_knowledge import branch_relation
    claims=[]
    for candidate in comparisons:
        a=candidate['assessment']; criteria=[]
        if candidate['holds_self']:criteria.append('HOLDS_SELF')
        if a['activation'] in ('MOVING','DARK_MOVEMENT_LOCAL'):criteria.append('ACTIVATED')
        if a['void']:criteria.append('VOID_PROBLEM_SITE')
        if a['month_break']:criteria.append('MONTH_BREAK_PROBLEM_SITE')
        # Calendar equality is narrower than monthly 旺 or calendar support.
        for period in ('month','day'):
            value=calendar.get(period)
            if value and value[-1]==a['branch']:criteria.append(period.upper()+'_VALUE')
        claims.append({'position':a['position'],'layer':a['layer'],'branch':a['branch'],
            'criteria':criteria,'effect_restrictions':sorted(set(a['unresolved']+a['waiting']+
                ([a['local_status']] if a['local_status'] in ('RETURNING_CONTROL_RESTRICTION','UNKNOWN_CALENDAR') else []))),
            'source_ids':['QA-17'], 'criteria_are_not_priority_scores':True})
    grouped={criterion:sorted({c['position'] for c in claims if criterion in c['criteria']})
        for criterion in ('HOLDS_SELF','ACTIVATED','VOID_PROBLEM_SITE','MONTH_BREAK_PROBLEM_SITE','MONTH_VALUE','DAY_VALUE')}
    proposals=[{'criterion':key,'position':positions[0]} for key,positions in grouped.items() if len(positions)==1]
    conflict=len({p['position'] for p in proposals})>1
    links=[]
    for source in comparisons:
        for target in comparisons:
            sa=source['assessment'];ta=target['assessment']
            if sa['layer']!='main' or ta['layer']!='main' or sa['position']==ta['position']:continue
            relation=branch_relation(sa['branch'],ta['branch'])
            if not relation['clash'] and not relation['combine']:continue
            active=sa['activation'] in ('MOVING','DARK_MOVEMENT_LOCAL')
            day_bound=bool(ta['period_relations'].get('day',{}).get('combine'))
            links.append({'source_position':sa['position'],'target_position':ta['position'],
                'relation':relation,'source_activation':sa['activation'],
                'source_local_status':sa['local_status'],
                'target_day_combined':day_bound,
                'review_kind':'ACTIVE_CLASH_TO_DAY_COMBINED_CANDIDATE' if active and relation['clash'] and day_bound else 'CANDIDATE_STRUCTURAL_RELATION',
                'does_not_establish_release':True,'does_not_choose_primary':True,
                'source_ids':['QA-11','QA-17']})
    requirements=[]
    health=intent.get('illness',{})
    if health.get('is_illness') and health.get('duration') is None:
        requirements.append('CLARIFY_ILLNESS_DURATION')
    if health.get('status') in ('CONFLICTED_DURATION_CONTEXT','INVALID_DURATION_CONTEXT'):
        requirements.append('RESOLVE_ILLNESS_DURATION_CONTEXT')
    if len(claims)>1:
        requirements.append('VERIFY_QUESTION_SPECIFIC_SELECTION_RULE')
        if conflict:requirements.append('RESOLVE_COMPETING_SOURCE_CRITERIA')
        # Agreement of superficial criteria does not establish full applicability.
        requirements.append('VERIFY_PROBLEM_SITE_AND_REMEDY_RELEVANCE')
    return {'status':'COMPETING_CRITERIA_REQUIRE_ADJUDICATION' if conflict else
        'MULTIPLE_CANDIDATES_REQUIRE_APPLICABILITY_REVIEW' if len(claims)>1 else
        'SINGLE_CANDIDATE' if claims else 'NO_CANDIDATE',
        'candidates':claims,'criterion_positions':grouped,'unique_criterion_proposals':proposals,
        'candidate_interactions':links,
        'criteria_conflict':conflict,'required_checks':requirements,
        'automatic_primary':None,'weighted_score_used':False,'historical_outcome_used':False,
        'source_ids':['QA-17','QA-18','QA-13']}
