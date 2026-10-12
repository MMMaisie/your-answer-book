"""Immutable, program-owned evidence record shared by all reading views.

This compiler includes traceable local condition applications, not certified
complete-chart effectiveness or forecasts.
Unknown conditions stay unresolved. A receipt validates declared provenance;
it is not a proof that arbitrary natural language faithfully expresses it.
"""
import copy,hashlib,json,re
from pathlib import Path
from hexagrams import ELEMENTS,GENERATES,CONTROLS
from reading_knowledge import KNOWLEDGE_VERSION,retrieve_rules,chart_facts,REFERENCE_RULES
from theory_facts import fact_phrases,explicit_focus,EN_BRANCH
from judgement_engine import evaluate,classify_question
from book_evidence import retrieve_book_evidence, VERSION as BOOK_EVIDENCE_VERSION
from decision_flow import build_decision_flow
from coarse_timing import validate_coarse_timing

ENGINE_FILES=('judgement_record.py','judgement_engine.py','hybrid_judgement.py','coarse_timing.py','focal_comparison.py','returning_conditions.py','complex_conditions.py','dynamic_rescue.py','effect_routes.py','book_evidence.py','decision_flow.py','scripts/review_book_checkpoints.py','theory_facts.py','reading_knowledge.py','book_cases.py','hexagrams.py','reading_guard.py','interpretation_guard.py')
VERSION='judgement-v2-'+hashlib.sha256(b''.join((Path(__file__).parent/name).read_bytes() for name in ENGINE_FILES)+BOOK_EVIDENCE_VERSION.encode()).hexdigest()[:12]

def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))

def subject(question):
    return classify_question(question)['kin']

def compile_record(question,cast):
    question=' '.join(question.split())
    knowledge=retrieve_rules(question,cast);facts=chart_facts(cast)
    reasoning=evaluate(question,cast)
    selection=reasoning['selection'];candidates=selection['candidates']
    phrases={lang:fact_phrases(cast,lang) for lang in ('zh','en')}
    evidence={key:{'id':key,'zh':phrases['zh'][key],'en':phrases['en'][key]} for key in phrases['zh']}
    rule_ids={r['id'] for r in knowledge['rules']}
    # Complex findings carry references even when generic retrieval's ranking
    # omitted their rules. Never give an unresolvable reference to the narrator.
    def referenced(value):
        if isinstance(value,dict):
            for key,item in value.items():
                if key=='source_ids':rule_ids.update(item)
                else:referenced(item)
        elif isinstance(value,list):
            for item in value:referenced(item)
    referenced(reasoning)
    rule_ids.intersection_update(r['id'] for r in REFERENCE_RULES)
    relations={}
    conditions=[]
    def add(pos,kind,value,refs,statement):
        conditions.append({'id':f'{pos}.{kind}','position':pos,'structural_value':value,
            'status':'STRUCTURE_VERIFIED_EFFECTIVENESS_UNRESOLVED','source_ids':[r for r in refs if r in rule_ids],
            'statement':statement,'outcome_inference':'NOT_AUTHORIZED'})
    for line in facts['lines']:
        pos=line['position']
        if line.get('void'):add(pos,'void',True,['QA-07'],'该爻旬空成立；不能据此单断无力或成功日期。')
        if line.get('month_break'):add(pos,'month_break',True,['QA-08'],'月支冲该爻成立；有效作用须另查日扶、动变及例外。')
        for period in ('month','day'):
            relation=line.get(period)
            if relation:
                relations[f'{pos}.{period}']=relation
                if relation['clash']:add(pos,period+'_clash',True,['QA-11'],'冲的结构关系成立；不自动判为冲散、暗动或解除受制。')
                if relation['combine']:add(pos,period+'_combine',True,['QA-11'],'合的结构关系成立；不自动判为合住或解除受制。')
        changed=line.get('changed')
        if changed:
            if changed['element_relation']=='克':add(pos,'returning_control',True,['QA-03','origin_blocked','SUP-14'],
                '变爻克本爻的五行关系成立；是否有效受制须另查合中带克、生扶和冲合，不能据此直接认定原神无力，也不能抹去日月扶持。')
            if changed.get('advance'):add(pos,'advance',True,['QA-10'],'化进的结构成立；不证明现实人物意愿、成功或确定归期。')
            if changed.get('retreat'):add(pos,'retreat',True,['QA-10'],'化退的结构成立；是否能退及作用效力尚需条件复核。')
    roles=[]
    for candidate in candidates:
        element=ELEMENTS[candidate['branch']]
        origin=next(e for e in GENERATES if GENERATES[e]==element)
        roles.append({'candidate':candidate,'origin_positions':[r['position'] for r in cast['rows'] if GENERATES[r['element']]==element],
            'obstruction_positions':[r['position'] for r in cast['rows'] if CONTROLS[r['element']]==element],
            'enemy_positions':[r['position'] for r in cast['rows'] if CONTROLS[r['element']]==origin],
            'policy':'角色按五行关系核对，不代表已经有效生克。'})
    direction_text={
        'OBJECT_UNRESOLVED':{'zh':'先明确问事对象，再核对条件，暂不定成败。','en':'Clarify the subject first; the outcome remains unresolved.'},
        'COMPARISON_UNRESOLVED':{'zh':'多个候选尚待比较，暂不指定唯一主用或确定成败。','en':'Multiple candidates still need comparison; no unique primary or outcome is determined.'},
        'UNIQUE_CANDIDATE':{'zh':'候选明确，仍需核对有效扶持和制约，暂不定结果。','en':'The candidate is clear; effective support and restrictions still need review before an outcome.'}}[selection['status']]
    if selection['status']=='UNIQUE_CANDIDATE':
        direction_text={
          'INPUT_UNRESOLVED':{'zh':'日月信息待核实，暂不定结果。','en':'Verify the calendar before drawing an outcome.'},
          'MIXED_SUPPORT_AND_RESTRICTION':{'zh':'有扶持也有制约，需看障碍能否解除。','en':'Support and restrictions coexist; progress depends on resolving the obstacles.'},
          'RESTRICTIONS_NEED_RESOLUTION':{'zh':'当前制约较明确，先看解除条件再论推进。','en':'Restrictions are present; review their release conditions before expecting progress.'},
          'WAITING_CONDITIONS':{'zh':'仍有待满足的条件，暂不把转机当作结果。','en':'Conditions remain pending; a possible opening is not yet an outcome.'},
          'SUPPORT_PRESENT_OUTCOME_CONDITIONAL':{'zh':'有扶持依据，能否落实仍看其余条件。','en':'Support is present; realization still depends on the remaining conditions.'},
          'NO_SUFFICIENT_EFFECTIVE_BASIS':{'zh':'有效推动依据不足，需补查支持和阻碍。','en':'The effective basis is insufficient; review support and obstacles.'}
        }[reasoning['synthesis']['status']]
    record={'version':VERSION,'knowledge_version':KNOWLEDGE_VERSION,'question':question,
        'calendar':cast.get('calendar') or {},'chart':copy.deepcopy(cast.get('rows',[])),'selection':selection,'reasoning':reasoning,'decision_flow':build_decision_flow(reasoning),'book_evidence':retrieve_book_evidence(question,cast),'roles':roles,'facts':evidence,'relations':relations,'conditions':conditions,
        'condition_texts':{c['id']:{'zh':'第'+str(c['position'])+'爻：'+c['statement'],'en':'Line '+str(c['position'])+': '+CONDITION_EN[c['id'].split('.',1)[1]]} for c in conditions},
        'source_ids':sorted(rule_ids),'direction':'CONDITIONAL_ONLY','direction_text':direction_text,'timing':'UNRESOLVED',
        'unresolved':reasoning['remaining_scope'],'timing_policy':'QUALITATIVE_PACE_ONLY_NO_DATES_OR_NUMERIC_DURATIONS',
        'views':{'free':{'minimum_fact_count':1,'minimum_condition_count':min(1,len(conditions)),'body_zh':[50,80],'body_en':[30,65]},
                 'paid':{'minimum_fact_count':2,'minimum_condition_count':min(2,len(conditions)),'required_expansions':['selection_reason','obstacle','counter_evidence','change_condition','action_1','action_2'],'body_zh':[250,300],'body_en':[150,210]}}}
    record['id']=hashlib.sha256(canonical(record).encode()).hexdigest()
    return record

def validate_identity(record):
    content={k:v for k,v in record.items() if k!='id'}
    if hashlib.sha256(canonical(content).encode()).hexdigest()!=record.get('id'):
        raise ValueError('judgement record integrity mismatch')

def receipt_contract(record,tier,source_receipt=None):
    policy=record['views'][tier]
    return {'judgement_id':record['id'],'direction':record['direction'],'focus_positions':record['selection']['positions'],
        'fact_ids':'list of at least '+str(policy['minimum_fact_count'])+' unique provided fact IDs used in body',
        'condition_ids':'list of at least '+str(policy['minimum_condition_count'])+' unique provided condition IDs whose limitations are retained',
        'expansions':policy.get('required_expansions',[]),
        'source_receipt':source_receipt,
        'instruction':'Return this provenance as the top-level judgement object, beside free/paid/text. Do not include it in prose. IDs describe facts actually explained, not merely listed. Do not introduce new judgments. Translation MUST copy the source receipt exactly.'}

def validate_receipt(raw,record,tier,source_receipt=None):
    validate_identity(record)
    receipt=raw.get('judgement') if isinstance(raw,dict) else None
    keys={'judgement_id','direction','focus_positions','fact_ids','condition_ids','expansions'}
    if not isinstance(receipt,dict) or set(receipt)!=keys:raise ValueError('missing or invalid program judgement receipt')
    if receipt['judgement_id']!=record['id'] or receipt['direction']!=record['direction']:
        raise ValueError('judgement identity or direction changed')
    if not isinstance(receipt['focus_positions'],list) or any(type(v) is not int for v in receipt['focus_positions']) or receipt['focus_positions']!=record['selection']['positions']:raise ValueError('candidate set changed')
    for field,allowed,minimum in (('fact_ids',set(record['facts']),record['views'][tier]['minimum_fact_count']),
                                 ('condition_ids',{c['id'] for c in record['conditions']},record['views'][tier]['minimum_condition_count'])):
        values=receipt[field]
        if not isinstance(values,list) or any(not isinstance(v,str) for v in values) or len(values)!=len(set(values)):
            raise ValueError('invalid '+field)
        if len(values)<minimum or not set(values)<=allowed:raise ValueError('missing or unverified '+field)
    if receipt['expansions']!=record['views'][tier].get('required_expansions',[]):raise ValueError('tier expansion contract changed')
    receipt={**receipt,'fact_ids':sorted(receipt['fact_ids']),'condition_ids':sorted(receipt['condition_ids'])}
    if source_receipt is not None and receipt!=source_receipt:raise ValueError('translation changed source judgement receipt')
    return receipt

def validate_narrative(text,record):
    body=text.split('【规则依据】')[0].split('【Source notes】')[0]
    from reading_guard import validate_chart_claims,validate_explicit_relations
    validate_chart_claims(body,{'calendar':record.get('calendar',{}),'rows':record.get('chart',[])})
    validate_explicit_relations(body)
    reasoning=record.get('reasoning',{})
    routes=reasoning.get('generating_route_reviews',[])
    if routes and not any(r.get('full_effect_certified') for r in routes):
        pattern=r'(?:已|已经|确已)(?:解除空墓|冲开日墓|冲开墓库|有效连续生扶|得救)|\b(?:has|have) (?:already )?(?:been rescued|released the day tomb|resolved the void and tomb)\b'
        for match in re.finditer(pattern,body,re.I):
            prefix=re.split(r'[，,。.!?！？;；\n]',body[:match.start()])[-1][-30:]
            if not re.search(r'不能(?:直接|就|据此)?(?:说|认为|断)|不(?:代表|等于|意味着)|不可(?:认定|断)|cannot (?:say|claim)|does not mean',prefix,re.I):
                raise ValueError('unverified generating route cannot certify rescue or tomb release')
    if not any(t.get('effective') for t in reasoning.get('triple_reviews',[])):
        pattern=r'(?<!未)(?<!不)(?:已经|确定|必然|已然|确已|已)(?:三合)?(?:成局|合化|成化)|\b(?:has|have) (?:already )?(?:formed an effective (?:triple|three.harmony) combination|transformed into a (?:wood|fire|earth|metal|water) combination)\b'
        for match in re.finditer(pattern,body,re.I):
            prefix=re.split(r'[，,。.!?！？;；\n]',body[:match.start()])[-1][-30:]
            if not re.search(r'不能(?:直接|就|据此)?(?:说|认为|断)|不(?:代表|等于|意味着)|不可(?:认定|断)|cannot (?:say|claim)|does not mean',prefix,re.I):
                raise ValueError('unverified effective triple cannot be asserted')
    if re.search(r'(?:三刑|刑|反吟|伏吟)(?:必凶|必败|必然失败)|\b(?:punishment|fanyin|fuyin) guarantees (?:failure|harm)\b',body,re.I):
        raise ValueError('structural sign cannot guarantee an adverse outcome')
    if re.search(r'judgement_id|fact_ids|condition_ids|统一判断记录|程序尚未|程序未实现|本程序不能',body,re.I):
        raise ValueError('internal implementation details must not appear in the reading')
    for sentence in re.split(r'[。！？.!?\n]',body):
        if re.search(r'暗动|三合成化|冲散|hidden movement|three[- ]harmony transformation',sentence,re.I):
            if not re.search(r'不能|不自动|未定|需|须|待|若|if|cannot|not automatically|needs|review',sentence,re.I):
                raise ValueError('unresolved advanced condition cannot be asserted by the narrator')
    if re.search(r'(?:归期|应期|到账日)(?:确定为|就是|为|在|是)[子丑寅卯辰巳午未申酉戌亥0-9]|\b(?:will|must) (?:return|arrive|be paid|succeed) on\b',body,re.I):
        raise ValueError('unresolved timing cannot be decided by the narrator')
    validate_coarse_timing(body)
    selection=record['selection'];focus=explicit_focus(text)
    status=record.get('reasoning',{}).get('synthesis',{}).get('status')
    if status=='MIXED_SUPPORT_AND_RESTRICTION':
        if re.search(r'没有任何(?:生扶|扶持|制约)|完全没有(?:生扶|扶持|制约)|毫无(?:扶持|制约)|\b(?:no support at all|no restrictions at all)\b',body,re.I):
            raise ValueError('narrative erases a checked support or restriction')
    interpretation=record.get('interpretation')
    chosen=interpretation['primary_positions'] if interpretation else selection['positions'] if selection['status']=='UNIQUE_CANDIDATE' else []
    allowed={EN_BRANCH[c['branch']] for c in selection['candidates'] if c['position'] in chosen}
    if focus and focus not in allowed:
        raise ValueError('narrative selects a primary not decided by the program')
    elements={ELEMENTS[c['branch']] for c in selection['candidates']}
    if len(elements)==1:
        target=next(iter(elements));origin=next(e for e in GENERATES if GENERATES[e]==target)
        checks={'原神':lambda e:GENERATES[e]==target,'忌神':lambda e:CONTROLS[e]==target,'仇神':lambda e:CONTROLS[e]==origin}
        for m in re.finditer(r'([子丑寅卯辰巳午未申酉戌亥])[木火土金水](?:(?:为|是|属|作|作为)(?:本盘|此卦)?的?|这个|之|的)?(原神|忌神|仇神)',text):
            if re.search(r'不是|并非|不为',text[max(0,m.start()-5):m.end()]):continue
            if not checks[m[2]](ELEMENTS[m[1]]):raise ValueError('named role contradicts program elemental relation')
        for m in re.finditer(r'(原神|忌神|仇神)(?:是|为|指|取|子孙|兄弟|父母|官鬼|妻财)?([子丑寅卯辰巳午未申酉戌亥])[木火土金水]',text):
            if not checks[m[1]](ELEMENTS[m[2]]):raise ValueError('named role contradicts program elemental relation')
        names='|'.join(EN_BRANCH.values());reverse={v.lower():k for k,v in EN_BRANCH.items()}
        aliases={'supporting':'原神','obstructing':'忌神','enemy':'仇神'}
        for m in re.finditer(r'\b('+names+r')\s+(?:wood|fire|earth|metal|water)\s+(?:(?:is|as)\s+(?:the\s+)?)?(supporting|obstructing|enemy) line\b',text,re.I):
            if re.search(r'\bnot\b',text[max(0,m.start()-5):m.end()],re.I):continue
            if not checks[aliases[m[2].lower()]](ELEMENTS[reverse[m[1].lower()]]):raise ValueError('named role contradicts program elemental relation')
    return text

def validate_paid_increment(free_receipt,paid_receipt):
    if free_receipt:
        for field in ('judgement_id','direction','focus_positions'):
            if free_receipt[field]!=paid_receipt[field]:raise ValueError('paid changed free judgement')
        for field in ('fact_ids','condition_ids'):
            if not set(free_receipt[field])<=set(paid_receipt[field]):raise ValueError('paid omitted free '+field)
        if set(free_receipt['fact_ids'])==set(paid_receipt['fact_ids']) and set(free_receipt['condition_ids'])==set(paid_receipt['condition_ids']):
            raise ValueError('paid must add checked evidence or conditions')

CONDITION_EN={
 'void':'Void is established; that alone does not mean powerless or give a successful date.',
 'month_break':'The month clashes with this line; its effectiveness still needs support, changes and exceptions checked.',
 'month_clash':'A month clash exists; that does not automatically establish scattering, hidden movement or release from control.',
 'day_clash':'A day clash exists; that does not automatically establish scattering, hidden movement or release from control.',
 'month_combine':'A month combination exists; that does not automatically establish binding or release from control.',
 'day_combine':'A day combination exists; that does not automatically establish binding or release from control.',
 'returning_control':'The changed line element controls the original line element. Effective restriction still needs review of combination, support and clashes; this alone does not establish a powerless supporting line or erase calendar support.',
 'advance':'An advancing change exists; that does not establish someone’s intention, success or a definite return date.',
 'retreat':'A retreating change exists; whether it can take effect still needs its conditions checked.'}

FREE_CONDITIONS={
 'void':('旬空不等于无力，仍须核对生扶与动变。','Void alone does not mean powerless; support and changes still matter.'),
 'month_break':('月破形成限制，实际作用仍看生扶与动变。','The month clashes with this line; its effect still depends on support and changes.'),
 'month_clash':('有月冲，不能直接断作冲散或解除克制。','A month clash alone does not establish scattering or release from control.'),
 'day_clash':('有日冲，不能直接断作暗动或冲散。','A day clash alone does not establish hidden movement or scattering.'),
 'month_combine':('有月合，不能直接断作合绊或解除克制。','A month combination alone does not establish binding or release from control.'),
 'day_combine':('有日合，不能直接断作合绊或解除克制。','A day combination alone does not establish binding or release from control.'),
 'returning_control':('有回头克，能否形成有效克制仍须核对。','Returning control exists; whether it takes effect still needs checking.'),
 'advance':('有进神之象，实际能否推进仍看条件。','An advancing change alone does not establish intention or success.'),
 'retreat':('有退神之象，实际能否退却仍看条件。','A retreating change still depends on its conditions.')}

def condition_prose(record,key,lang,tier):
    if tier=='free' and key.split('.',1)[1] in FREE_CONDITIONS:
        position=key.split('.',1)[0]
        return ('第'+position+'爻：' if lang=='zh' else 'Line '+position+': ')+FREE_CONDITIONS[key.split('.',1)[1]][0 if lang=='zh' else 1]
    return record['condition_texts'][key][lang]

def expand_verified_slots(raw,receipt,record,lang,tier,translation=False):
    """Bind declared evidence to literal program-owned prose in the actual body."""
    import copy
    result=copy.deepcopy(raw)
    name='text' if translation else tier
    value=result.get(name)
    fields=('direction','evidence') if tier=='free' else tuple(record['views']['paid']['required_expansions'])
    if not isinstance(value,dict):raise ValueError('shared judgement requires structured paragraphs')
    if tier=='paid':
        suffix='source_applications' if translation else 'sources'
        if set(value)!=set(fields+(suffix,)) or any(not isinstance(value[field],str) or not value[field].strip() for field in fields):
            raise ValueError('paid requires distinct selection, obstacle, counter-evidence, condition and two actions')
        if value['action_1'].strip().casefold()==value['action_2'].strip().casefold():raise ValueError('paid actions must be distinct')
    direction_field='direction' if tier=='free' else 'selection_reason'
    if value.get(direction_field,'').count('{D:direction}')!=1 or sum(v.count('{D:direction}') for k,v in value.items() if k in fields and isinstance(v,str))!=1:
        raise ValueError('shared program direction must appear once in its designated field')
    body='\n'.join(value.get(field,'') for field in fields if isinstance(value.get(field),str))
    found_facts=re.findall(r'\{F:([A-Za-z0-9_.-]+)\}',body)
    found_conditions=re.findall(r'\{C:([A-Za-z0-9_.-]+)\}',body)
    if set(found_facts)!=set(receipt['fact_ids']) or set(found_conditions)!=set(receipt['condition_ids']):
        raise ValueError('declared evidence must match actual body slots')
    if any('zh' not in record['facts'].get(key,{}) for key in found_facts):
        raise ValueError('fact is not an approved prose slot')
    conditions={c['id']:c for c in record['conditions']}
    def replace(m):
        condition=conditions.get(m[1])
        if not condition:raise ValueError('unverified condition slot')
        return condition_prose(record,condition['id'],lang,tier)
    for field in fields:
        if isinstance(value.get(field),str):value[field]=re.sub(r'\{C:([A-Za-z0-9_.-]+)\}',replace,value[field]).replace('{D:direction}',record['direction_text'][lang])
    if re.search(r'\{[CD]:',canonical(value)):raise ValueError('invalid condition slot')
    if tier=='paid':
        mapped={'priorities':value['selection_reason'],'conditions':' '.join(value[f] for f in ('obstacle','counter_evidence','change_condition')),'actions':' '.join(value[f] for f in ('action_1','action_2'))}
        key='source_applications' if translation else 'sources'
        mapped[key]=value[key];result[name]=mapped
    result.pop('judgement',None)
    return result


def validate_translation_bindings(source,target,tier):
    fields=('direction','evidence') if tier=='free' else ('selection_reason','obstacle','counter_evidence','change_condition','action_1','action_2')
    if not isinstance(source,dict) or not isinstance(target,dict):raise ValueError('translation needs canonical structured parts')
    for field in fields:
        a=source.get(field);b=target.get(field)
        if not isinstance(a,str) or not isinstance(b,str):raise ValueError('missing translated semantic field '+field)
        slots=lambda value:sorted(re.findall(r'\{([FCD]:[A-Za-z0-9_.-]+)\}',value))
        if slots(a)!=slots(b):raise ValueError('translation changed evidence/condition field '+field)
