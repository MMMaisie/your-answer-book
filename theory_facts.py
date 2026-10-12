"""Deterministic theory facts and checks; interpretation remains conditional.

These checks reject explicit claims. They are not a complete natural-language proof.
"""
import re
from hexagrams import ELEMENTS,GENERATES,CONTROLS

BRANCHES='子丑寅卯辰巳午未申酉戌亥'
PINYIN=('Zi','Chou','Yin','Mao','Chen','Si','Wu','Wei','Shen','You','Xu','Hai')
EN_BRANCH=dict(zip(BRANCHES,PINYIN))
ZH_BRANCH={v.lower():k for k,v in EN_BRANCH.items()}
CLASH=dict(zip(BRANCHES,'午未申酉戌亥子丑寅卯辰巳'))
COMBINE=dict(zip(BRANCHES,'丑子亥戌酉申未午巳辰卯寅'))
EN_ELEMENT=dict(zip('木火土金水',('wood','fire','earth','metal','water')))

def relation(source,target):
    a,b=ELEMENTS[source],ELEMENTS[target]
    if a==b:return 'same_element'
    if GENERATES[a]==b:return 'generates'
    if CONTROLS[a]==b:return 'controls'
    if GENERATES[b]==a:return 'is_generated_by'
    return 'is_controlled_by'

def explicit_focus(text):
    # Extract only an explicitly selected branch, never guess from its mere mention.
    text=re.split(r'【(?:规则依据|Source notes)】',text)[0]
    m=re.search(r'(?:以|取)[^'+BRANCHES+r'。；\n]{0,12}(['+BRANCHES+r'])(?:[木火土金水])?(?:财|官|子孙|兄弟|父母)?为(?:主|用神|主要用神|用)',text)
    if m:return EN_BRANCH[m[1]]
    m=re.search(r'(?:主要用神|主用|用神)(?:为|是|取|：|:)[^'+BRANCHES+r'。；\n]{0,12}(['+BRANCHES+r'])',text)
    if m:return EN_BRANCH[m[1]]
    names='|'.join(ZH_BRANCH)
    patterns=[r'\b(?:take|choose|use|select)\s+(?:the\s+)?(?:void\s+)?('+names+r')\b[^.!?\n]{0,25}?\bas\s+(?:the\s+)?(?:primary|main|focal|focus)',
        r'\b('+names+r')\s+(?:wealth\s+)?(?:line\s+)?is\s+(?:the\s+)?(?:primary|main|focal|focus)\b']
    for pattern in patterns:
        m=re.search(pattern,text,re.I)
        if m:return EN_BRANCH[ZH_BRANCH[m[1].lower()]]
    m=re.search(r'\bprimary line\s+(?:is|:)[^.!?\n]{0,30}?\b('+names+r')\b',text,re.I)
    if m:return EN_BRANCH[ZH_BRANCH[m[1].lower()]]
    return None

def validate_translation_focus(original,translated):
    source=explicit_focus(original)
    if source and explicit_focus(translated)!=source:
        raise ValueError('translation must preserve explicit focal line '+source)
    return translated

def ledger(cast):
    calendar=cast.get('calendar') or {};facts=[]
    for row in cast.get('rows',[]):
        branch=row['branch'];pos=row['position']
        for period in ('day','month'):
            value=calendar.get(period,'')
            if not value or value[-1] not in ELEMENTS:continue
            source=value[-1]
            facts.append({'id':f'{pos}.{period}','source':EN_BRANCH[source],
                'target':EN_BRANCH[branch],'direction':'period acts on line',
                'element_relation':relation(source,branch),'clash':CLASH[source]==branch,
                'combine':COMBINE[source]==branch})
        facts.append({'id':f'{pos}.state','position':pos,'branch':EN_BRANCH[branch],
            'element':EN_ELEMENT[ELEMENTS[branch]],'moving':bool(row.get('moving')),
            'void':branch in calendar['xunkong'] if calendar.get('xunkong') else None,
            'month_broken':CLASH[calendar['month'][-1]]==branch if calendar.get('month') and calendar['month'][-1] in CLASH else None})
    return {'generates':[[EN_ELEMENT[a],EN_ELEMENT[b]] for a,b in GENERATES.items()],
        'controls':[[EN_ELEMENT[a],EN_ELEMENT[b]] for a,b in CONTROLS.items()],
        'lines':facts,'policy':'Facts establish relations and state, not success, failure or effective force. A void, supported or static line needs rule conditions before an outcome is inferred.'}

def fact_phrases(cast,lang):
    """The program writes the literal relation; the model explains its relevance."""
    phrases={}
    for fact in ledger(cast)['lines']:
        if 'source' in fact:
            source=ZH_BRANCH[fact['source'].lower()];target=ZH_BRANCH[fact['target'].lower()]
            period='日辰' if fact['id'].endswith('.day') else '月建'
            a=source+ELEMENTS[source];b=target+ELEMENTS[target]
            se=fact['source']+' '+EN_ELEMENT[ELEMENTS[source]]
            te=fact['target']+' '+EN_ELEMENT[ELEMENTS[target]]
            pe='the day' if fact['id'].endswith('.day') else 'the month'
            rel=fact['element_relation']
            zh={'generates':period+a+'生'+b,'controls':period+a+'克'+b,
                'is_generated_by':b+'生'+period+a,'is_controlled_by':b+'克'+period+a,
                'same_element':b+'与'+period+a+'五行比和'}[rel]
            en={'generates':pe+' '+se+' generates '+te,'controls':pe+' '+se+' controls '+te,
                'is_generated_by':te+' generates '+pe+' '+se,'is_controlled_by':te+' controls '+pe+' '+se,
                'same_element':te+' shares the element of '+pe+' '+se}[rel]
            phrases[fact['id']]=zh if lang=='zh' else en
        else:
            b=ZH_BRANCH[fact['branch'].lower()];zh=b+ELEMENTS[b];en=fact['branch']+' '+fact['element']
            phrases[str(fact['position'])+'.void']=(zh+('的旬空状态待核实' if fact['void'] is None else '旬空' if fact['void'] else '不逢旬空')) if lang=='zh' else (en+(' has unverified void status' if fact['void'] is None else ' is void' if fact['void'] else ' is not void'))
            phrases[str(fact['position'])+'.motion']=(zh+('发动' if fact['moving'] else '为静爻')) if lang=='zh' else (en+(' is moving' if fact['moving'] else ' is static'))
    for row in cast.get('rows',[]):
        changed=row.get('changed')
        if not changed:continue
        a,b=row['branch'],changed['branch'];r=relation(b,a)
        za,zb=a+ELEMENTS[a],b+ELEMENTS[b]
        ea,eb=EN_BRANCH[a]+' '+EN_ELEMENT[ELEMENTS[a]],EN_BRANCH[b]+' '+EN_ELEMENT[ELEMENTS[b]]
        labels={'controls':('变爻'+zb+'克本爻'+za+'，为回头克','Changed '+eb+' controls original '+ea+' (returning control)'),
            'generates':('变爻'+zb+'生本爻'+za+'，为回头生','Changed '+eb+' generates original '+ea+' (returning generation)'),
            'is_controlled_by':('本爻'+za+'克变爻'+zb+'，不是回头克','Original '+ea+' controls changed '+eb+'; this is not returning control'),
            'is_generated_by':('本爻'+za+'生变爻'+zb,'Original '+ea+' generates changed '+eb),
            'same_element':('本爻'+za+'与变爻'+zb+'五行比和','Original '+ea+' and changed '+eb+' share an element')}
        phrases[str(row['position'])+'.changed']=labels[r][0 if lang=='zh' else 1]
    return phrases

def render_fact_slots(text,cast,lang):
    if not isinstance(text,str):return text
    phrases=fact_phrases(cast or {},lang)
    def replace(m):
        if m[1] not in phrases:raise ValueError('unverified fact slot '+m[1])
        return phrases[m[1]]
    result=re.sub(r'\{F:([A-Za-z0-9_.-]+)\}',replace,text)
    if '{F:' in result:raise ValueError('invalid fact slot')
    return result

def validate_theory(text,cast):
    calendar=cast.get('calendar') or {}
    # Changed branch acts back on the original branch, never in the reverse direction.
    chinese=r'(['+BRANCHES+r'])[木火土金水][^'+BRANCHES+r'，。；\n]{0,25}?(?:动)?化(['+BRANCHES+r'])[木火土金水][^'+BRANCHES+r'，。；\n]{0,18}?回头(克|生)'
    for m in re.finditer(chinese,text):
        if re.search(r'若|如果|假如|不是|并非|不为|非回头|不(?:属|属于|构成)回头',text[max(0,m.start()-8):m.end()]):continue
        table=CONTROLS if m[3]=='克' else GENERATES
        if table[ELEMENTS[m[2]]]!=ELEMENTS[m[1]]:
            raise ValueError('returning relation contradicts changed-to-original elemental direction')
    names='|'.join(ZH_BRANCH)
    english=r'\b('+names+r')\s+(?:wood|fire|earth|metal|water)\b[^.!?;\n]{0,65}?transforms?\s+(?:in)?to\s+('+names+r')\s+(?:wood|fire|earth|metal|water)\b[^.!?;\n]{0,60}?(?:turns? back to|turning[- ]back|returning)\s*(?:to\s*)?(control|generate)'
    for m in re.finditer(english,text,re.I):
        if re.search(r'\bif|not\b',text[max(0,m.start()-8):m.start()],re.I) or re.search(r'\bnot\s+(?:a\s+)?(?:turning|returning)',m[0],re.I):continue
        table=CONTROLS if m[3].lower()=='control' else GENERATES
        if table[ELEMENTS[ZH_BRANCH[m[2].lower()]]]!=ELEMENTS[ZH_BRANCH[m[1].lower()]]:
            raise ValueError('returning relation contradicts changed-to-original elemental direction')
    # Compact prose such as "午火得日比月生" was missed by passive-only checks.
    for m in re.finditer(r'(['+BRANCHES+r'])(?:[木火土金水]|财|官|爻)[^'+BRANCHES+r'，。；\n]{0,18}?(日|月)(?:建|辰)?(生|克)',text):
        if re.search(r'若|如果|假如|非|不',text[max(0,m.start()-4):m.end()]):continue
        prefix=re.split(r'[。；\n]',text[:m.start()])[-1]
        if re.search(r'待|未来|届时|若|如果',prefix):continue
        period=calendar.get('day' if m[2]=='日' else 'month','')
        if not period or period[-1] not in ELEMENTS:continue
        table=GENERATES if m[3]=='生' else CONTROLS
        if table[ELEMENTS[period[-1]]]!=ELEMENTS[m[1]]:
            raise ValueError('explicit elemental contradiction (compact calendar relation)')
    for m in re.finditer(r'\b('+names+r')\s+(?:wood|fire|earth|metal|water)(?:\s+line)?[^.!?;\n]{0,24}?combines? with (?:the )?(month|day)\b',text,re.I):
        value=calendar.get(m[2].lower(),'')
        if value and value[-1] in ELEMENTS and COMBINE[ZH_BRANCH[m[1].lower()]]!=value[-1]:
            raise ValueError('calendar combination must not replace elemental affinity')
    for m in re.finditer(r'\b('+names+r')\s+(?:wood|fire|earth|metal|water)(?:\s+line)?\s+matches?\s+(?:the\s+)?(month|day)\b',text,re.I):
        value=calendar.get(m[2].lower(),'')
        if value and value[-1] in ELEMENTS and ZH_BRANCH[m[1].lower()]!=value[-1]:
            raise ValueError('matching period branch must not replace elemental affinity')
    for sentence in re.split(r'[.!?\n]',text):
        if not re.search(r'matches? (?:the )?month and (?:the )?day(?: branches)?',sentence,re.I):continue
        named=set(re.findall(r'\b('+names+r')\b',sentence,re.I))
        if len(named)==1:
            branch=ZH_BRANCH[next(iter(named)).lower()]
            if any(calendar.get(period,'') and calendar[period][-1]!=branch for period in ('day','month')):
                raise ValueError('matching period branches must not replace elemental affinity')
    for m in re.finditer(r'(['+BRANCHES+r'])([木火土金水])',text):
        if ELEMENTS[m[1]]!=m[2]:raise ValueError('branch element contradicts theory')
    names='|'.join(ZH_BRANCH)
    english_elements='|'.join(EN_ELEMENT.values())
    for m in re.finditer(r'\b('+names+r')\s+('+english_elements+r')\b',text,re.I):
        if EN_ELEMENT[ELEMENTS[ZH_BRANCH[m[1].lower()]]]!=m[2].lower():raise ValueError('branch element contradicts theory')
    def check(source,target,verb):
        table=GENERATES if verb in ('生','generates','generated') else CONTROLS
        if table[ELEMENTS[source]]!=ELEMENTS[target]:raise ValueError('explicit elemental contradiction (branch endpoints)')
    for m in re.finditer(r'(['+BRANCHES+r'])(?:[木火土金水]|爻)[^'+BRANCHES+r'，。；\n]{0,12}?(?:被|受)(['+BRANCHES+r'])[木火土金水](生|克)',text):
        if not re.search(r'若|如果|不|非',text[max(0,m.start()-4):m.start()]):check(m[2],m[1],m[3])
    for m in re.finditer(r'\b('+names+r')\s*(?:'+english_elements+r')?\s+(?:line\s+)?(?:is\s+)?(controlled|restrained|generated)\s+by\s+('+names+r')\b',text,re.I):
        if not re.search(r'\b(?:if|not|unless)\b',text[max(0,m.start()-8):m.start()],re.I):check(ZH_BRANCH[m[3].lower()],ZH_BRANCH[m[1].lower()],m[2].lower())
    for m in re.finditer(r'\b('+names+r')\s+(?:'+english_elements+r')\s+(generates|controls|restrains)\s+('+names+r')\b',text,re.I):
        check(ZH_BRANCH[m[1].lower()],ZH_BRANCH[m[3].lower()],m[2].lower())
    # The v12 failure names both endpoints: 未土...受日辰子水克.
    pattern=r'(['+BRANCHES+r'])(?:[木火土金水]|爻)[^'+BRANCHES+r'，。；\n]{0,20}?(?:受|被)(日|月)(?:辰|建)?(['+BRANCHES+r'])(?:[木火土金水])(生|克)'
    for m in re.finditer(pattern,text):
        prefix=text[max(0,m.start()-4):m.start()]
        if re.search(r'若|如果|假如|非|不',prefix):continue
        line,period,source,verb=m.groups()
        actual=calendar.get('day' if period=='日' else 'month','')
        if actual and actual[-1]!=source:raise ValueError('named calendar branch contradicts chart')
        table=GENERATES if verb=='生' else CONTROLS
        if table[ELEMENTS[source]]!=ELEMENTS[line]:raise ValueError('explicit elemental contradiction (named calendar endpoints)')
    # Named line-to-period clashes, without inferring across another named branch.
    passive=r'\b('+names+r')\s+(?:'+english_elements+r')\b([^.!?;\n]{0,55}?)\b(clashed|controlled|restrained|generated)\s+by\s+(?:the\s+)?(day|month)\b'
    for m in re.finditer(passive,text,re.I):
        context=text[max(0,m.start()-12):m.start()]+m[2]
        if re.search(r'\b(?:if|unless|not|cannot|never)\b',context,re.I):continue
        if re.search(r'\b(?:'+names+r')\b',m[2],re.I):continue
        value=calendar.get(m[4].lower(),'')
        if not value or value[-1] not in ELEMENTS:continue
        line=ZH_BRANCH[m[1].lower()];verb=m[3].lower()
        if verb=='clashed':
            if CLASH[value[-1]]!=line:raise ValueError('calendar clash contradicts chart')
        else:check(value[-1],line,verb)
    for m in re.finditer(r'(['+BRANCHES+r'])(?:[木火土金水]|爻)[^'+BRANCHES+r'，。；\n]{0,18}?(?:受|被|逢)(日|月)(?:辰|建)?冲',text):
        if re.search(r'若|如果|不|非',text[max(0,m.start()-4):m.end()]):continue
        value=calendar.get('day' if m[2]=='日' else 'month','')
        if value and CLASH[value[-1]]!=m[1]:raise ValueError('calendar clash contradicts chart')
    for m in re.finditer(r'\b('+names+r')\s+(?:wood|fire|earth|metal|water)?\s*(?:line\s+)?(?:is\s+)?[^.!?\n]{0,30}?\b(day|month)[- ]clashed\b',text,re.I):
        # Restrict to the named branch's own clause.
        between=m[0][len(m[1]):]
        if re.search(r'\b(?:'+names+r')\b',between,re.I) or re.search(r'\b(?:if|not|unless)\b',between,re.I):continue
        value=calendar.get(m[2].lower(),'')
        if value and CLASH[value[-1]]!=ZH_BRANCH[m[1].lower()]:raise ValueError('calendar clash contradicts chart')
    # Basic explicitly stated branch-to-branch clash/combine facts.
    for m in re.finditer(r'(?<!日)(['+BRANCHES+r'])(?:[木火土金水])?(?:与|和)?(['+BRANCHES+r'])(?:[木火土金水])?(?:相)?(冲|合)',text):
        if re.search(r'不|非',text[max(0,m.start()-2):m.start()]):continue
        table=CLASH if m[3]=='冲' else COMBINE
        if table[m[1]]!=m[2]:raise ValueError('branch clash/combine contradiction')
    for m in re.finditer(r'\b('+names+r')\s+(clashes with|combines with)\s+('+names+r')\b',text,re.I):
        table=CLASH if m[2].lower().startswith('clashes') else COMBINE
        if table[ZH_BRANCH[m[1].lower()]]!=ZH_BRANCH[m[3].lower()]:raise ValueError('branch clash/combine contradiction')
    if 'xunkong' in calendar:
        for m in re.finditer(r'(['+BRANCHES+r'])(?:[木火土金水]|爻)(?:为|逢|临|是|属|正)?旬空',text):
            if re.search(r'若|如果|非|不',text[max(0,m.start()-4):m.start()]):continue
            if not calendar.get('xunkong') or m[1] not in calendar['xunkong']:raise ValueError('void claim contradicts calendar or missing status')
        for m in re.finditer(r'\b('+names+r')\s+(?:'+english_elements+r')?\s*(?:line\s+)?(?:is\s+)?void\b',text,re.I):
            if re.search(r'\b(?:if|not|unless)\b',text[max(0,m.start()-8):m.start()],re.I):continue
            if not calendar.get('xunkong') or ZH_BRANCH[m[1].lower()] not in calendar['xunkong']:raise ValueError('void claim contradicts calendar or missing status')
    for sentence in re.split(r'[。！？\n.!?]',text):
        if re.search(r'若|如果|未必|不能仅|不(?:能|可)一概|并非|不等于|\b(?:if|unless|not necessarily|not automatically)\b',sentence,re.I):continue
        if re.search(r'旬空[，, ]?(?:所以|故|便|就|而)?(?:不能|无法|必不|不可能)(?:生财|作用|起作用|生克)',sentence):
            raise ValueError('unconditional void disables line')
        if re.search(r'\bvoid\b[^.!?]{0,20}\b(?:cannot act|cannot generate|can never act)\b',sentence,re.I):
            raise ValueError('unconditional void disables line')
    return text
