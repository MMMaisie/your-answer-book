"""Traceable conditional reasoning; symbolic findings are not event predictions.

No scalar fortune score, historical-result lookup, or invented missing calendar.
An ACTIVE edge means an uncontested local rule application, not a guarantee
that the complete chart has been adjudicated. Unresolved interactions persist.
"""
import re
from hexagrams import ELEMENTS, GENERATES, CONTROLS
from reading_knowledge import branch_relation, chart_facts, CLASH, COMBINE, GROWTH
from complex_conditions import triple_conditions, transfer_conditions, change_structures, punishment_conditions, release_requirements
from dynamic_rescue import qualify_dynamic_rescue, revalidate_rescue_sources
from effect_routes import audit_generating_routes
from focal_comparison import illness_context, compare_focal_candidates, explicit_relation_subject
from returning_conditions import review_returning_control, returning_control_requires_review

STEMS='甲乙丙丁戊己庚辛壬癸'
BRANCHES='子丑寅卯辰巳午未申酉戌亥'
CYCLE=[STEMS[i%10]+BRANCHES[i%12] for i in range(60)]
VOID_PAIRS=['戌亥','申酉','午未','辰巳','寅卯','子丑']
KIN=('父母','兄弟','子孙','妻财','官鬼')

def void_for(day):
    if day not in CYCLE: raise ValueError('invalid sexagenary day')
    return VOID_PAIRS[CYCLE.index(day)//10]

def infer_days(branch, void=None):
    return [d for d in CYCLE if d[-1]==branch and (not void or void_for(d)==void)]

def requested_time_unit(question,context):
    supplied=context.get('time_unit')
    if supplied:return supplied if supplied in ('day','month','year','hour') else None
    units=[unit for unit,pattern in [('day',r'何日|哪天|几号|what date'),
        ('month',r'何月|哪个月|which month'),('year',r'何年|哪年|which year'),
        ('hour',r'几点|哪个时辰|what hour')] if re.search(pattern,question,re.I)]
    return units[0] if len(units)==1 else None

def subject_context_questions(question):
    checks=[
        (r'姑病', 'CLARIFY_OWN_AUNT_OR_SPOUSES_SISTER'),
        (r'为女择婿|为子择媳', 'CLARIFY_PROPOSED_SPOUSE_OR_CHILD_AS_SUBJECT'),
        (r'借银|借贷', 'CLARIFY_BORROW_REPAY_AND_COUNTERPARTY_RELATION'),
        (r'婚', 'CLARIFY_QUESTIONER_AND_PARTNER_RELATION'),
        (r'生产', 'CLARIFY_MOTHER_CHILD_OR_BOTH'),
        (r'风水|坟|造葬|家宅|买宅|穴地', 'CLARIFY_PROPERTY_OWNERSHIP_AND_BENEFICIARY'),
        (r'讼|闹殴|被参|禁劾|拿问', 'CLARIFY_OWN_CASE_OR_CASE_FOR_RELATIVE'),
        (r'自去寻父', 'CLARIFY_OWN_JOURNEY_OR_FATHERS_RETURN')]
    result=[label for pattern,label in checks if re.search(pattern,question)]
    return result or ['CLARIFY_SINGLE_SUBJECT_AND_RELATION']

def classify_question(question, context=None):
    """Explicit objects only. Ambiguous relationship/intent never guessed."""
    context=context or {}; found=[]
    if context.get('focal_kin') in KIN or context.get('focal_kin') in ('世','应'):
        purpose=context.get('purpose') or ('timing' if re.search(r'何日|何时|什么时候|几时|何年|何月|归期|哪天|几号|几点|哪年|哪个月|哪个时辰|when|what date|what hour|which month|which year',question,re.I) else 'general')
        return {'kin':context['focal_kin'],'method':'EXPLICIT_CONTEXT','purpose':purpose,
                'horizon':context.get('horizon','unspecified'),'time_unit':requested_time_unit(question,context),'context_questions':[],
                'illness':illness_context(question,context),'source_ids':['focal','QA-18']}
    patterns=(
      ('子孙',r'^(?:子|女)(?:近|久|急|远)?病|^子何日脱难|^子在.{0,10}何日回|^子.{0,12}(?:出|归)|儿子|女儿|孩子|子女|问子|占子|子嗣|求子|侄|孙儿|孙女|求晴|天晴|雨止|\b(?:son|daughter|my child|children|nephew|niece|clear weather)\b'),
      ('妻财',r'何日得财|开店|卖货|脱货|索房价|出外贸易|失银物|往买卖|赌钱|桑叶贵贱|仆(?:何日回|近出|逃)|逃仆|嫂嫂|弟妇|妾(?:近|久)?病|求财|收款|收入|生意|投资|收益|妻子|妻(?:病|在|去)|\b(?:wealth|money|income|business|investment|profit|my wife)\b'),
      ('官鬼',r'升选|图谋补缺|乡试|会试|升迁|升职|录用|求职|功名|丈夫|老公|占夫|夫(?:急|近|远)?病|\b(?:promotion|job offer|hired|my husband)\b'),
      ('父母',r'^父(?:何日归|近出|远出|在任|在乱军|官事)|师(?:近|久)?病|何日有大雨|文书|合同|证书|父亲|母亲|爸爸|妈妈|问父|问母|父(?:急|近|远)?病|母(?:急|近|远)?病|何日雨(?!止)|何日有雨|下雨|\b(?:document|contract|certificate|my father|my mother|rainfall)\b'),
      ('兄弟',r'^兄(?:近|久)?病|^妹临产|兄弟|姐妹|姊妹|哥哥|弟弟|姐姐|妹妹|弟(?:病|被)|兄(?:病|被)|\b(?:my brother|my sister|sibling)\b'),
      ('世',r'自占(?:近|久)?病|自陈|自己(?:疾病|处境|出行|终身)|本人(?:处境|出行)|一人自病|\b(?:my own situation|my own journey)\b'),
      ('应',r'交疏之人|交疏的人|不熟悉的人|\b(?:unrelated visitor|the counterparty)\b'))
    for kin, pattern in patterns:
        if re.search(pattern,question,re.I): found.append(kin)
    relation_kin=explicit_relation_subject(question)
    relation_ambiguous=relation_kin=='RELATION_SUBJECTS_NEED_CLARIFICATION'
    if relation_ambiguous:found=[];relation_kin=None
    elif relation_kin:found=[relation_kin]
    purpose=context.get('purpose') or ('timing' if re.search(r'何日|何时|什么时候|几时|何年|何月|归期|哪天|几号|几点|哪年|哪个月|哪个时辰|when|what date|what hour|which month|which year',question,re.I) else 'general')
    horizon=context.get('horizon') or ('near' if re.search(r'近期|近事|这几天|soon|near term',question,re.I) else 'far' if re.search(r'远期|长远|long term',question,re.I) else 'unspecified')
    return {'kin':found[0] if len(found)==1 else None,'method':'EXPLICIT_RELATION' if relation_kin else 'EXPLICIT_WORDS' if len(found)==1 else 'NEEDS_CONTEXT',
            'matched_kins':found,'purpose':purpose,'horizon':horizon,'time_unit':requested_time_unit(question,context),
            'context_questions':[] if len(found)==1 else ['CLARIFY_SINGLE_SUBJECT_OR_SEPARATE_QUESTIONS'] if relation_ambiguous else subject_context_questions(question),
            'illness':illness_context(question,context),'source_ids':['focal','QA-18']}

def calendar_audit(calendar):
    c=calendar or {}; issues=[]
    for name in ('month','day'):
        v=c.get(name)
        if not isinstance(v,str) or not v or v[-1] not in ELEMENTS: issues.append('MISSING_'+name.upper())
    day=c.get('day'); void=c.get('xunkong')
    if day and (len(day)!=2 or day not in CYCLE): issues.append('INVALID_DAY')
    if not void: issues.append('MISSING_VOID')
    elif day in CYCLE and void!=void_for(day): issues.append('DAY_VOID_CONFLICT')
    return {'status':'VALID' if not issues else 'INCOMPLETE_OR_CONFLICTED','issues':issues}

def season_state(month_element, element):
    """Monthly five-element state only; never the full strength verdict."""
    if month_element==element:return '旺'
    if GENERATES[month_element]==element:return '相'
    if GENERATES[element]==month_element:return '休'
    if CONTROLS[element]==month_element:return '囚'
    return '死'

def assess_line(row,calendar,layer='main',horizon='unspecified'):
    pos=row['position']; branch=row['branch']; element=ELEMENTS[branch]
    rel={name:branch_relation(calendar[name][-1],branch) for name in ('month','day') if calendar.get(name) and calendar[name][-1] in ELEMENTS}
    missing=calendar_audit(calendar)['issues']; void=branch in (calendar.get('xunkong') or '') if calendar.get('xunkong') else None
    month=rel.get('month',{}); day=rel.get('day',{}); change=row.get('changed') if layer=='main' and row.get('moving') else None
    ret=branch_relation(change['branch'],branch) if change else None
    monthly=season_state(ELEMENTS[calendar['month'][-1]],element) if 'month' in rel else None
    supports=[name for name,r in rel.items() if r['element_relation'] in ('生','比和')]
    controls=[name for name,r in rel.items() if r['element_relation']=='克']
    reasons=[]; waiting=[]; unknown=[]
    def reason(code,refs): reasons.append({'code':code,'source_ids':refs})
    if missing: unknown.extend(missing)
    if month.get('clash'):reason('MONTH_BREAK',['QA-08','month_break']);waiting.append('REVIEW_FILL_OR_COMBINATION_OR_MONTH_CHANGE')
    if void:reason('VOID',['QA-07','void']);waiting.append('REVIEW_VOID_RELEASE_AND_REMAINING_OBSTACLES')
    if supports:reason('CALENDAR_SUPPORT',['QA-01'])
    if controls:reason('CALENDAR_CONTROL',['QA-01'])
    if supports and controls:reason('CALENDAR_MIXED_NO_CANCELLING_SCORE',['QA-01'])
    for name,r in rel.items():
        if r['combine']:unknown.append(name.upper()+'_COMBINATION_EFFECT')
        growth=dict(zip(GROWTH[element],('长生','墓','绝'))).get(r['source'])
        if growth in ('墓','绝'):unknown.append(name.upper()+'_GROWTH_'+growth)
    activation='MOVING' if row.get('moving') and layer=='main' else 'STATIC'
    if activation=='MOVING' and day.get('clash'):unknown.append('DYNAMIC_DAY_CLASH_EFFECT')
    if layer=='changed':activation='CHANGED_OWN_PARENT_ONLY';unknown.append('CHANGED_LINE_NOT_INDEPENDENT_CROSS_LINE_AGENT')
    if layer=='hidden':activation='HIDDEN';unknown.append('HIDDEN_EMERGENCE_CONDITIONS')
    if activation=='STATIC' and day.get('clash'):
        if not missing and monthly in ('旺','相') and not void and not month.get('clash'):
            activation='DARK_MOVEMENT_LOCAL';reason('STRONG_STATIC_DAY_CLASH',['strength_dynamic_joint','static_day_clash'])
        elif not missing and day.get('element_relation')=='比和' and not void and not month.get('clash'):
            # Earth clashes can coexist with same-element day support. Reviewed
            # p82/p83 examples do not use the monthly-only label as a veto.
            # Tomb and other force conditions remain unresolved below.
            activation='DARK_MOVEMENT_LOCAL';reason('STATIC_DAY_CLASH_WITH_SAME_ELEMENT_DAY_SUPPORT',['QA-03','QA-04','strength_dynamic_joint'])
        elif void and not missing and not month.get('clash') and not controls and (
                day.get('element_relation')=='比和' or monthly in ('旺','相')):
            # Supported 冲空 supplies a local activation qualification, not
            # removal of 空 or 墓. All waiting/effect gates remain in place.
            activation='DARK_MOVEMENT_LOCAL'
            reason('SUPPORTED_VOID_DAY_CLASH_LOCAL_ACTIVATION',['QA-03','QA-07','strength_dynamic_joint'])
            unknown.append('VOID_CLASH_EFFECT_REQUIRES_REVIEW')
        elif void:
            activation='VOID_CLASH_REVIEW';unknown.append('VOID_CLASH_NOT_AUTOMATIC_DARK_MOVEMENT')
        elif monthly in ('休','囚','死'):
            activation='WEAK_DAY_CLASH_REVIEW';unknown.append('DAY_CLASH_NEEDS_DYNAMIC_RESCUE_REVIEW')
        else:unknown.append('DAY_CLASH_ACTIVATION_UNRESOLVED')
    if ret:
        if ret['element_relation']=='克':reason('RETURNING_CONTROL',['QA-02','QA-03'])
        if ret['element_relation']=='生':reason('RETURNING_SUPPORT',['QA-02'])
        if ret['clash'] or ret['combine']:unknown.append('CHANGED_CLASH_OR_COMBINATION_EFFECT')
        cb=change['branch']
        if cb in (calendar.get('xunkong') or ''):waiting.append('CHANGED_VOID_RELEASE');unknown.append('CHANGED_VOID_EFFECT_ON_PARENT')
        if calendar.get('month') and calendar['month'][-1] in CLASH and CLASH[calendar['month'][-1]]==cb:waiting.append('CHANGED_MONTH_BREAK_REVIEW');unknown.append('CHANGED_BREAK_EFFECT_ON_PARENT')
        from reading_knowledge import ADVANCE,RETREAT
        if ADVANCE.get(branch)==cb:
            reason('ADVANCE',['QA-10'])
            if monthly in ('旺','相') and not void and not month.get('clash') and not unknown and not waiting:
                reason('ADVANCE_LOCAL_CONDITIONS_MET',['QA-10'])
            else:waiting.append('ADVANCE_NEEDS_VALID_PARENT_AND_CHANGE')
        if RETREAT.get(branch)==cb:
            reason('RETREAT',['QA-10']);unknown.append('RETREAT_HORIZON_'+horizon.upper())
        if cb==GROWTH[element][1]:
            reason('CHANGED_TOMB_STRUCTURE',['QA-12'])
            opened=bool(not missing and not void and not month.get('clash') and day.get('source')==CLASH[cb] and
                day.get('element_relation') in ('生','比和') and cb not in (calendar.get('xunkong') or '') and
                not (calendar.get('month') and CLASH.get(calendar['month'][-1])==cb) and ret['element_relation']!='克')
            if opened:
                reason('CHANGED_TOMB_DAY_CLASH_WITH_PARENT_SUPPORT',['QA-12','rescue'])
            else:unknown.append('CHANGED_TOMB_OR_EXTINCTION')
        if cb==GROWTH[element][2]:
            # QA-12 says earth meeting Si must also consider fire generating
            # earth. The 十二运 marker does not reverse that basic relation.
            earth_rescue=bool(element=='土' and ret['element_relation']=='生' and not missing and supports and
                not void and not month.get('clash') and cb not in (calendar.get('xunkong') or '') and
                not (calendar.get('month') and CLASH.get(calendar['month'][-1])==cb))
            if earth_rescue:reason('EARTH_CHANGED_SI_WITH_RETURNING_SUPPORT',['QA-12','rescue'])
            else:unknown.append('CHANGED_TOMB_OR_EXTINCTION')
    returning_review=review_returning_control(branch,change['branch'] if change else None,ret,monthly,rel,
        missing,void,bool(month.get('clash')),
        bool(change and change['branch'] in (calendar.get('xunkong') or '')),
        bool(change and calendar.get('month') and CLASH.get(calendar['month'][-1])==change['branch']))
    if returning_review and 'SUP-14' in returning_review['source_ids']:
        reason('COMBINED_RETURNING_CONTROL_CONDITIONAL_REVIEW',['SUP-14'])
    hard_return=bool(returning_review and returning_review['treat_as_pure_control'])
    if missing: local='UNKNOWN_CALENDAR'
    elif hard_return and not any(x.startswith('CHANGED_') for x in unknown): local='RETURNING_CONTROL_RESTRICTION'
    elif unknown: local='CONDITIONS_REQUIRE_REVIEW'
    elif void or month.get('clash'):local='WAITING_FOR_RELEASE'
    elif activation in ('MOVING','DARK_MOVEMENT_LOCAL'):local='ACTIVE_LOCAL'
    else:local='STATIC_NOT_AN_ACTIVE_CROSS_LINE_AGENT'
    return {'position':pos,'layer':layer,'branch':branch,'kin':row['kin'],'monthly_state':monthly,
            'monthly_state_scope':'MONTHLY_ONLY_NOT_FULL_STRENGTH','period_relations':rel,
            'calendar_support':supports,'calendar_control':controls,'activation':activation,
            'local_status':local,'void':void,'month_break':bool(month.get('clash')),
            'returning_relation':ret,'returning_control_review':returning_review,'findings':reasons,'waiting':sorted(set(waiting)),
            'unresolved':sorted(set(unknown)),'rule_scope':'LOCAL_CONDITIONAL_APPLICATION_NOT_EVENT_VERDICT'}

def evaluate(question,cast,context=None):
    context=context or {};cal=cast.get('calendar') or {}; intent=classify_question(question,context)
    assessments=[assess_line(r,cal,horizon=intent['horizon']) for r in cast['rows']]
    dynamic_rescue_reviews=qualify_dynamic_rescue(assessments)
    triple_reviews=triple_conditions(cast['rows'],assessments,cal,assess_line)
    # Calculate member conditions first, then gate ordinary cross-line effects:
    # a possible combination must not be counted again as free direct 生克.
    for review in triple_reviews:
        if review['status']=='MISSING_MEMBER':continue
        for a in assessments:
            if a['position'] in review['positions']:
                a['unresolved'].append('TRIPLE_MEMBERS_EFFECTIVENESS_REVIEW')
                if a['local_status']=='ACTIVE_LOCAL':a['local_status']='CONDITIONS_REQUIRE_REVIEW'
    revalidate_rescue_sources(assessments,dynamic_rescue_reviews)
    bypos={a['position']:a for a in assessments};kin=intent['kin']; facts=chart_facts(cast)
    if kin in ('世','应'):
        layer='main';pool={};candidates=[{'position':r['position'],'branch':r['branch']} for r in cast['rows'] if r['label']==kin]
    else:
        pool=facts['focal_search_candidates'].get(kin,{})
        layer=pool.get('search_layer','unresolved');candidates=pool.get(layer,[]) if layer in ('main','changed','hidden') else []
    comparisons=[]
    for c in candidates:
        base=cast['rows'][c['position']-1]
        if layer=='main':a=bypos[c['position']]
        else:a=assess_line({**base,**base[layer], 'changed':None,'moving':False},cal,layer,intent['horizon'])
        emergence=None
        if layer=='hidden':
            flying=bypos[c['position']];r=branch_relation(base['branch'],c['branch']); release=[];obstacles=[]
            if a['calendar_support']:release.append('DAY_OR_MONTH_SUPPORTS_HIDDEN')
            if r['element_relation']=='生':release.append('FLYING_GENERATES_HIDDEN')
            if flying['void'] or flying['month_break']:release.append('FLYING_VOID_OR_BREAK_REVIEW')
            if r['element_relation']=='克' and flying['calendar_support']:obstacles.append('SUPPORTED_FLYING_CONTROLS_HIDDEN')
            obstacles+=a['unresolved']+a['waiting']
            emergence={'flying_to_hidden':r,'release_conditions':release,'obstacles':sorted(set(obstacles)),
                       'status':'CONDITIONAL_EMERGENCE_NOT_ESTABLISHED','source_ids':['QA-09']}
        comparisons.append({'candidate':c,'assessment':a,'hidden_emergence':emergence,'holds_self':base.get('label')=='世' and layer=='main',
            'role':'FOCAL_CANDIDATE','source_ids':['QA-17','QA-18']})
    selection_status='UNIQUE_CANDIDATE' if len(candidates)==1 else 'COMPARISON_UNRESOLVED' if candidates else 'OBJECT_UNRESOLVED'
    preferred=None;method=None
    # 病处 is a comparison criterion, not a universal automatic ranking.
    # A sole void candidate in an explicitly asked timing problem can be marked
    # as the timing checkpoint, without erasing other candidates or declaring it
    # the sole primary for outcome/health questions.
    if len(candidates)>1 and intent['purpose']=='timing':
        checkpoints=[c for c in comparisons if c['assessment']['void']]
        if len(checkpoints)==1: preferred=checkpoints[0]['candidate'];method='UNIQUE_VOID_TIMING_CHECKPOINT_NOT_PRIMARY'
    edges=[]
    for focal in comparisons:
        target=focal['candidate'];te=ELEMENTS[target['branch']];origin=next(e for e in GENERATES if GENERATES[e]==te)
        for src in assessments:
            if layer=='main' and src['position']==target['position']:continue
            se=ELEMENTS[src['branch']]
            role='原神' if GENERATES[se]==te else '忌神' if CONTROLS[se]==te else '仇神' if CONTROLS[se]==origin else None
            if not role:continue
            rel=branch_relation(src['branch'],target['branch']); gates=list(src['unresolved'])+list(src['waiting'])
            nominal_controllers=[s for s in assessments if s['position']!=src['position'] and s['activation'] in ('MOVING','DARK_MOVEMENT_LOCAL') and CONTROLS[ELEMENTS[s['branch']]]==se]
            incoming=[s['position'] for s in nominal_controllers if s['local_status']!='RETURNING_CONTROL_RESTRICTION']
            if incoming:gates.append('OTHER_ACTIVE_CONTROL_REVIEW')
            if rel['clash'] or rel['combine']:gates.append('SOURCE_TARGET_CLASH_OR_COMBINATION_REVIEW')
            # A source may be locally available while the target remains void,
            # broken or hidden. Keep these as separate gates.
            gates+=['TARGET_'+g for g in focal['assessment']['unresolved']+focal['assessment']['waiting']]
            if focal['assessment']['local_status'] in ('RETURNING_CONTROL_RESTRICTION','UNKNOWN_CALENDAR'):
                gates.append('TARGET_'+focal['assessment']['local_status'])
            if src['local_status']=='RETURNING_CONTROL_RESTRICTION':state='RESTRICTED_AT_SOURCE'
            elif src['local_status']=='STATIC_NOT_AN_ACTIVE_CROSS_LINE_AGENT':state='STATIC_RELATION_ONLY'
            elif src['local_status']=='ACTIVE_LOCAL' and not gates:state='ACTIVE_LOCAL_RELATION'
            else:state='CONDITIONAL_RELATION'
            edges.append({'id':f"{layer}:{target['position']}<-main:{src['position']}",'source_position':src['position'],
                          'target_position':target['position'],'target_layer':layer,'role':role,
                          'element_relation':rel['element_relation'],'state':state,'gates':sorted(set(gates)),
                          'incoming_control_positions':incoming,
                          'restricted_controller_positions':[s['position'] for s in nominal_controllers if s['local_status']=='RETURNING_CONTROL_RESTRICTION'],
                          'source_ids':['QA-03','support','obstruction']})
    chains=transfer_conditions(edges,assessments,comparisons)
    generating_routes=audit_generating_routes(assessments,comparisons)
    structures=change_structures(cast,assessments,candidates if layer=='main' else [])
    punishments=punishment_conditions(cast,assessments,comparisons)
    if selection_status!='UNIQUE_CANDIDATE':summary='SELECTION_UNRESOLVED'
    else:
        a=comparisons[0]['assessment'];roles=[e for e in edges if e['role'] in ('原神','忌神')]
        constraints=a['calendar_control'] or a['month_break'] or returning_control_requires_review(a) or any(e['role']=='忌神' and e['state']=='ACTIVE_LOCAL_RELATION' for e in roles)
        support=a['calendar_support'] or any(e['role']=='原神' and e['state']=='ACTIVE_LOCAL_RELATION' for e in roles)
        if calendar_audit(cal)['issues']:summary='INPUT_UNRESOLVED'
        elif constraints and support:summary='MIXED_SUPPORT_AND_RESTRICTION'
        elif constraints:summary='RESTRICTIONS_NEED_RESOLUTION'
        elif a['waiting'] or a['unresolved']:summary='WAITING_CONDITIONS'
        elif support:summary='SUPPORT_PRESENT_OUTCOME_CONDITIONAL'
        else:summary='NO_SUFFICIENT_EFFECTIVE_BASIS'
    return {'intent':intent,'calendar_audit':calendar_audit(cal),
            'selection':{'kin':kin,'layer':layer,'candidates':candidates,'positions':sorted(c['position'] for c in candidates),
                         'secondary_layers':{name:pool.get(name,[]) for name in ('main','changed','hidden') if name!=layer},
                         'status':selection_status,'timing_checkpoint':preferred,'checkpoint_method':method,
                         'comparison_review':compare_focal_candidates(comparisons,intent,cal),
                         'policy':'逐项比较病处与问意；不以最旺或某爻位置强行选主用。'},
            'line_assessments':assessments,'candidate_comparisons':comparisons,'effect_edges':edges,'transfer_chains':chains,'triple_reviews':triple_reviews,
            'change_structure_reviews':structures,'punishment_reviews':punishments,
            'dynamic_rescue_reviews':dynamic_rescue_reviews,
            'generating_route_reviews':generating_routes,
            'release_requirements':release_requirements(comparisons,edges,assessments,triple_reviews),
            'synthesis':{'status':summary,'event_success':'NOT_ASSERTED','timing':'NOT_DETERMINED',
                         'complete_chart_certified':False,'source_ids':['QA-01','QA-03','QA-17','QA-18']},
            'remaining_scope':['三合成员有效性与成局','卦级反伏吟完整联动','刑与扶抑联动','精确应期','复杂多现与代占问意'],
            'source_outcomes_used':False}
