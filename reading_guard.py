"""Reject explicit elemental contradictions. This is not a complete semantic judge."""
import re
from hexagrams import ELEMENTS,CONTROLS,GENERATES
ELEMENT_EN={'wood':'木','fire':'火','earth':'土','metal':'金','water':'水'}
BRANCH_EN=dict(zip(('zi','chou','yin','mao','chen','si','wu','wei','shen','you','xu','hai'),'子丑寅卯辰巳午未申酉戌亥'))

def check_relation(source,verb,target,negated=False):
 if verb in ('生','generates'):valid=GENERATES[source]==target
 elif verb=='supports':valid=source==target or GENERATES[source]==target
 elif verb in ('克','回头克','controls','restrains'):valid=CONTROLS[source]==target
 else:return
 if bool(valid)==bool(negated):raise ValueError('explicit elemental contradiction')

def validate_explicit_relations(text):
 # Resolve only clearly anchored line subjects, rather than guessing pronouns across prose.
 for sentence in re.split(r'[。！？\n]',text):
  focus=re.search(r'(?:第?\d+爻)[^，。；]{0,8}?([子丑寅卯辰巳午未申酉戌亥])([木火土金水])',sentence)
  if focus:
   for m in re.finditer(r'(?:月建|日建|日辰)[^，。；]{0,3}?([子丑寅卯辰巳午未申酉戌亥])([木火土金水])(生|克)之',sentence):
    check_relation(m[2],m[3],focus[2])
 # Explicit branch plus pronoun: 辰财…子水克之 means water acts on earth.
 for sentence in re.split(r'[。！？\n]',text):
  for m in re.finditer(r'([子丑寅卯辰巳午未申酉戌亥])(?:财|土|木|水|火|金|爻)[^。！？\n]{0,18}?([子丑寅卯辰巳午未申酉戌亥])([木火土金水])(生|克)之',sentence):
   check_relation(m[3],m[4],ELEMENTS[m[1]])
 # Narrow, positive assertions only; unsupported phrasing is not counted as verified.
 for m in re.finditer(r'([子丑寅卯辰巳午未申酉戌亥]?[木火土金水])(?:直接)?(回头克|生|克)([子丑寅卯辰巳午未申酉戌亥]?[木火土金水])',text):
  prefix=text[max(0,m.start()-8):m.start()]
  negated=bool(re.search(r'(?:并非|不是|并不是|不意味着)$',prefix))
  check_relation(m[1][-1],m[2],m[3][-1],negated)
 for m in re.finditer(r'([子丑寅卯辰巳午未申酉戌亥]?[木火土金水])(?:不|并不)(生|克)([子丑寅卯辰巳午未申酉戌亥]?[木火土金水])',text):
  check_relation(m[1][-1],m[2],m[3][-1],True)
 for m in re.finditer(r'\b(wood|fire|earth|metal|water)\s+(generates|controls|restrains)\s+(wood|fire|earth|metal|water)\b',text,re.I):
  check_relation(ELEMENT_EN[m[1].lower()],m[2].lower(),ELEMENT_EN[m[3].lower()])
 for m in re.finditer(r'\b(zi|chou|yin|mao|chen|si|wu|wei|shen|you|xu|hai)\s+(generates|controls|restrains)\s+(zi|chou|yin|mao|chen|si|wu|wei|shen|you|xu|hai)\b',text,re.I):
  check_relation(ELEMENTS[BRANCH_EN[m[1].lower()]],m[2].lower(),ELEMENTS[BRANCH_EN[m[3].lower()]])
 return text


def focal_contract(question):
 q=question.casefold()
 if re.search(r'^子[^。？！]{0,12}(?:出|归)|儿子|女儿|孩子|子女|问子|占子|\b(?:son|daughter|my child|children)\b',q):
  return {'kin':'子孙','reason':'明确询问子女，不能以父母为主要用神'}
 return {}

def validate_focal(text,question):
 if focal_contract(question).get('kin')=='子孙':
  if re.search(r'(?:以|取|用神[为是])父母|(?:focal|focus|significator)[^.!?\n]{0,65}\bparent',text,re.I):
   raise ValueError('focal contradicts explicit child question')
 return text


def chart_assertions(cast):
 """Small, deterministic facts; these do not decide auspiciousness."""
 rows=cast.get('rows',cast.get('lines',[]))
 if not rows:
  rows=cast.get('yao',[])
 result=[]
 for row in rows:
  b=row.get('branch')
  if b not in ELEMENTS:continue
  e=ELEMENTS[b]
  for name,label in (('day','日'),('month','月')):
   value=(cast.get('calendar') or {}).get(name,'')
   if not value or value[-1] not in ELEMENTS:continue
   source=ELEMENTS[value[-1]]
   if CONTROLS[source]==e:description=f'{label}克{b}；{b}受{label}克'
   elif CONTROLS[e]==source:description=f'{b}克{label}；不是{b}受{label}克'
   elif GENERATES[source]==e:description=f'{label}生{b}；{b}受{label}生'
   elif GENERATES[e]==source:description=f'{b}生{label}；不是{b}受{label}生'
   else:description=f'{b}与{label}五行比和'
   result.append({'position':row.get('position'),'branch':b,'period':name,'fact':description})
 return result


def validate_symbolic_targets(text,cast):
 # Resolve role abbreviations only when their target element is unambiguous.
 rows=cast.get('rows',[])
 targets={}
 for alias,kin in [('财','妻财'),('官','官鬼'),('兄弟','兄弟'),('子孙','子孙'),('父母','父母'),('wealth','妻财'),('officer','官鬼'),('sibling','兄弟'),('child','子孙'),('parent','父母')]:
  targets[alias]={ELEMENTS[r['branch']] for r in rows if r.get('kin')==kin and r.get('branch') in ELEMENTS}
 for alias,label in [('世','世'),('应','应'),('self','世'),('responding','应')]:
  targets[alias]={ELEMENTS[r['branch']] for r in rows if r.get('label')==label and r.get('branch') in ELEMENTS}
 def verify(source,verb,role):
  elements=targets.get(role,set())
  if len(elements)==1:
   try:check_relation(source,verb,next(iter(elements)))
   except ValueError:raise ValueError('symbolic target role elemental contradiction: '+role) from None
 for m in re.finditer(r'([子丑寅卯辰巳午未申酉戌亥])([木火土金水])([^子丑寅卯辰巳午未申酉戌亥，。；\n]{0,40})',text):
  tail=m[3]
  for relation in re.finditer(r'(生|克)(世|应|财|官|兄弟|子孙|父母)(?:爻)?',tail):
   if re.search(r'不|未|难|若|如果|不能',tail[max(0,relation.start()-6):relation.start()]):continue
   verify(m[2],relation[1],relation[2])
 names='|'.join(BRANCH_EN)
 for m in re.finditer(r'\b('+names+r')\s+(wood|fire|earth|metal|water)\b([^.!?;\n]{0,140})',text,re.I):
  tail=m[3]
  for relation in re.finditer(r'\b(generates|controls|restrains)\s+(?:the\s+)?(self|responding|wealth|officer|sibling|child|parent)(?:\s+line)?\b',tail,re.I):
   prefix=tail[:relation.start()]
   if re.search(r'\b(?:not|cannot|unable|if|unless)\b',prefix,re.I):continue
   # A later explicit named subject invalidates the earlier anchor.
   if re.search(r'\b(?:'+names+r')\s+(?:wood|fire|earth|metal|water)\b',prefix,re.I):continue
   verify(ELEMENT_EN[m[2].lower()],relation[1].lower(),relation[2].lower())
 return text

def validate_chart_claims(text,cast):
 """Reject unambiguous named-branch calendar claims and static/moving contradictions.
 Unmatched prose still requires independent review; no comprehensive semantic guarantee.
 """
 from theory_facts import validate_theory
 validate_theory(text,cast)
 validate_symbolic_targets(text,cast)
 branches='子丑寅卯辰巳午未申酉戌亥'
 for sentence in re.split(r'[。！？\n.!?]',text):
  for m in re.finditer(r'(['+branches+r'])(?:[木火土金水]|财|爻)[^'+branches+r'，。；\n]{0,15}?(?:受|被)(日|月)(?:建|辰)?(克|生)',sentence):
   if re.search(r'若|如果|假如|未必|不(?:是|能|受|被)',sentence[:m.start()]):continue
   value=(cast.get('calendar') or {}).get('day' if m[2]=='日' else 'month','')
   if value and value[-1] in ELEMENTS:check_relation(ELEMENTS[value[-1]],m[3],ELEMENTS[m[1]])
  for m in re.finditer(r'\b(zi|chou|yin|mao|chen|si|wu|wei|shen|you|xu|hai)\s+(?:wood|fire|earth|metal|water)?\s*(?:line\s+)?(?:is\s+)?(?:controlled|restrained|generated|supported)\s+by\s+(?:the\s+)?(day|month)\b',sentence,re.I):
   if re.search(r'\b(?:if|unless|not)\b',sentence[:m.start()],re.I):continue
   value=(cast.get('calendar') or {}).get(m[2].lower(),'')
   if value and value[-1] in ELEMENTS:
    verb='supports' if re.search(r'supported',m[0],re.I) else '生' if re.search(r'generated',m[0],re.I) else '克'
    check_relation(ELEMENTS[value[-1]],verb,ELEMENTS[BRANCH_EN[m[1].lower()]])
 # Resolve each explicitly named single/multiple-branch subject inside its own clause.
 # Do not let 寅卯得日生但受月克 bypass the single-branch/element spelling checks.
 for clause in re.split(r'[。！？\n，,；;]',text):
  for m in re.finditer(r'(['+branches+r']{1,2})[木火土金水]?(?:财爻|财|爻)?[^'+branches+r']{0,20}?(?:受|被)(日|月)(?:建|辰)?(生|克)',clause):
   if re.search(r'若|如果|假如|未必',clause[:m.start()]):continue
   value=(cast.get('calendar') or {}).get('day' if m[2]=='日' else 'month','')
   if value and value[-1] in ELEMENTS:
    negated=bool(re.search(r'(?:不|并非|不是|未)(?:受|被)(?:日|月)',m[0]))
    for branch in m[1]:check_relation(ELEMENTS[value[-1]],m[3],ELEMENTS[branch],negated)
 # Explicit multiple-branch subject, e.g. 寅卯木受未月克.
 for m in re.finditer(r'([子丑寅卯辰巳午未申酉戌亥]{1,2})[木火土金水]?(?:爻)?(?:受|被)([子丑寅卯辰巳午未申酉戌亥])[木火土金水]?(?:月|日)(生|克)(?:制)?',text):
  prefix=text[max(0,m.start()-6):m.start()]
  if re.search(r'若|如果|并非|不是',prefix):continue
  for branch in m[1]:check_relation(ELEMENTS[m[2]],m[3],ELEMENTS[branch])
 month_value=(cast.get('calendar') or {}).get('month','')
 if month_value:
  for m in re.finditer(r'([子丑寅卯辰巳午未申酉戌亥])[木火土金水]?(?:财爻|财|爻)?(?:值|临)月建',text):
   if m[1]!=month_value[-1]:raise ValueError('month-building identity contradicts calendar; same element is not same branch')
 rows=cast.get('rows',cast.get('lines',cast.get('yao',[])))
 month=(cast.get('calendar') or {}).get('month','')
 if month and month[-1] in ELEMENTS:
  from reading_knowledge import CLASH
  for m in re.finditer(r'([子丑寅卯辰巳午未申酉戌亥])(?:[木火土金水]|爻)?(?:为|逢|临|属|是|已|正|现|\s){0,3}月破',text):
   if not re.search(r'若|如果|非|未|不',text[max(0,m.start()-3):m.start()]) and CLASH[month[-1]]!=m[1]:
    raise ValueError('month-broken claim contradicts calendar')
  for m in re.finditer(r'\b(zi|chou|yin|mao|chen|si|wu|wei|shen|you|xu|hai)\s+(?:line\s+)?is\s+month[- ]broken\b',text,re.I):
   if CLASH[month[-1]]!=BRANCH_EN[m[1].lower()]:raise ValueError('month-broken claim contradicts calendar')
 if month and month[-1] in ELEMENTS:
  from reading_knowledge import CLASH
  for m in re.finditer(r'([子丑寅卯辰巳午未申酉戌亥])[木火土金水]?(?:爻)?(?:旬)?空(?:且|而|又)?(?:月)?破',text):
   prefix=text[max(0,m.start()-8):m.start()]
   if not re.search(r'若|如果|不|并非',prefix) and CLASH[month[-1]]!=m[1]:
    raise ValueError('combined void/broken claim adds unsupported month-broken status')
 if rows and not any(r.get('moving') for r in rows):
  for sentence in re.split(r'[。！？\n.!?]',text):
   for match in re.finditer(r'(?:兄弟|妻财|官鬼|父母|子孙)(?:爻)?(?:旺动|发动|明动|动而|动化|动克)',sentence):
    # Scope negation to this claim, so a denied first clause cannot hide a later positive claim.
    prefix=re.split(r'[，,；;]',sentence[:match.start()])[-1]
    if re.search(r'若|如果|假如|未必|不(?:是|能|会)|(?:无|没有|未见|并无|未)(?:任何|明显)?$',prefix):continue
    raise ValueError('moving claim contradicts static chart')
   if re.search(r'\b(?:wei|chen|zi|chou|yin|mao|si|wu|shen|you|xu|hai)\s+(?:line\s+)?is\s+(?:moving|active)\b',sentence,re.I) and not re.search(r'\b(?:if|not)\b',sentence,re.I):
    raise ValueError('moving claim contradicts static chart')
 return text


def normalize_headings(text,lang,tier):
 """Normalize exact heading punctuation only; never shorten or rewrite content."""
 if not isinstance(text,str):return text
 from reading_knowledge import PAID_HEADINGS
 headings=(('初判','关键依据') if lang=='zh' else ('Initial reading','Key evidence')) if tier=='free' else PAID_HEADINGS[lang]
 for heading in headings:
  text=re.sub(r'(?m)^\s*'+re.escape(heading)+r'\s*[:：]\s*',lambda m:'【'+heading+'】',text)
 return text
