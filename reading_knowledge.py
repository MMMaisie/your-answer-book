"""Reviewed book rule retrieval and auditable relationship facts.
No auspiciousness scores, automatic dark movement or unconditional forecasts.
"""
import hashlib,json,re
from pathlib import Path
from hexagrams import ELEMENTS,GENERATES,CONTROLS
from book_cases import CASE_VERSION,retrieve_cases

RULE_PATH=Path(__file__).parent/'knowledge'/'bushi_rules.json'
RULE_BYTES=RULE_PATH.read_bytes()
KNOWLEDGE=json.loads(RULE_BYTES)
CONDITION_BYTES=(RULE_PATH.parent/'bushi_conditions.json').read_bytes()
CONDITIONS=json.loads(CONDITION_BYTES)
SUP_BYTES=(RULE_PATH.parent/'bushi_supplement.json').read_bytes()
TOPIC_BYTES=(RULE_PATH.parent/'bushi_topic_packets.json').read_bytes()
SUPPLEMENTS=json.loads(SUP_BYTES)
TOPIC_PACKETS=json.loads(TOPIC_BYTES)
REFERENCE_RULES=tuple(KNOWLEDGE['rules']+CONDITIONS['rules']+SUPPLEMENTS['rules']+TOPIC_PACKETS['rules'])
KNOWLEDGE_VERSION=KNOWLEDGE['version']+'-'+hashlib.sha256(RULE_BYTES+CONDITION_BYTES+SUP_BYTES+TOPIC_BYTES+CASE_VERSION.encode()).hexdigest()[:10]
CLASH=dict(zip('子丑寅卯辰巳午未申酉戌亥','午未申酉戌亥子丑寅卯辰巳'))
COMBINE=dict(zip('子丑寅卯辰巳午未申酉戌亥','丑子亥戌酉申未午巳辰卯寅'))
ADVANCE={'亥':'子','寅':'卯','巳':'午','申':'酉','丑':'辰','辰':'未','未':'戌','戌':'丑'}
RETREAT={v:k for k,v in ADVANCE.items()}
GROWTH={'木':('亥','未','申'),'火':('寅','戌','亥'),'金':('巳','丑','寅'),'水':('申','辰','巳'),'土':('申','辰','巳')}
TOPICS={
 '工作':('工作','求职','录用','升职','升迁','offer','job','career','promotion','hire'),
 '考试':('考试','学校','学业','exam','study','university'),
 '财运':('钱','收入','生意','财','投资','收益','money','income','business','invest','profit'),
 '关系':('恋','婚','对象','男友','女友','伴侣','丈夫','妻子','关系','partner','relationship','love','marry','husband','wife'),
}

def element_relation(source,target):
 if source==target:return '比和'
 if GENERATES[source]==target:return '生'
 if CONTROLS[source]==target:return '克'
 if GENERATES[target]==source:return '被生（对方生本方）'
 return '被克（对方克本方）'

def branch_relation(source,target):
 result={'source':source,'target':target,'element_relation':element_relation(ELEMENTS[source],ELEMENTS[target])}
 result['clash']=CLASH[source]==target
 result['combine']=COMBINE[source]==target
 result['same_branch']=source==target
 return result

def line_facts(row,calendar):
 branch=row['branch']; element=row['element'];result={'position':row['position'],'branch':branch,'kin':row['kin'],'label':row.get('label',''),'moving':row['moving']}
 for name in ('month','day'):
  value=(calendar or {}).get(name,'')
  if value and value[-1] in ELEMENTS:
   b=value[-1];result[name]=branch_relation(b,branch)
   result[name]['growth_marker']=dict(zip(GROWTH[element],('长生','墓','绝'))).get(b,'')
 if calendar:
  result['void']=branch in (calendar.get('xunkong') or '') if calendar.get('xunkong') else None
  result['month_break']=result.get('month',{}).get('clash',False)
  if not row['moving'] and result.get('day',{}).get('clash'):
   result['day_clash_review']='日冲静爻：须辨旺衰、生扶、旬空等后才能区分暗动、冲起或日破；此处不自动判定。'
 changed=row.get('changed')
 if row['moving'] and changed:
  cb=changed['branch'];result['changed']=branch_relation(cb,branch)
  result['changed']['branch']=cb
  result['changed']['advance']=ADVANCE.get(branch)==cb
  result['changed']['retreat']=RETREAT.get(branch)==cb
  void=(calendar or {}).get('xunkong')
  result['changed']['void']=cb in void if void else None
  month=(calendar or {}).get('month','')
  result['changed']['month_break']=bool(month and month[-1] in CLASH and CLASH[month[-1]]==cb)
  result['changed']['reference_note']='element_relation 的方向是变爻作用于本爻；生/克分别为回头生/回头克。'
 hidden=row.get('hidden')
 if hidden:
  result['hidden']={'branch':hidden['branch'],'kin':hidden['kin'],'flying_to_hidden':branch_relation(branch,hidden['branch'])}
  for name in ('month','day'):
   value=(calendar or {}).get(name,'')
   if value and value[-1] in ELEMENTS:result['hidden'][name]=branch_relation(value[-1],hidden['branch'])
  void=(calendar or {}).get('xunkong')
  result['hidden']['void']=hidden['branch'] in void if void else None
 return result

def chart_facts(cast):
 rows=cast['rows'];cal=cast.get('calendar');facts=[line_facts(r,cal) for r in rows]
 roles=[]
 # For every possible focal line, expose relationships rather than guessing a gender or topic.
 for focal in rows:
  groups={'focal_position':focal['position'],'focal_kin':focal['kin'],'原神':[],'忌神':[],'仇神':[]}
  origin=next(e for e in GENERATES if GENERATES[e]==focal['element'])
  for r in rows:
   if GENERATES[r['element']]==focal['element']:groups['原神'].append(r['position'])
   if CONTROLS[r['element']]==focal['element']:groups['忌神'].append(r['position'])
   if CONTROLS[r['element']]==origin:groups['仇神'].append(r['position'])
  roles.append(groups)
 candidates={}
 for kin in ('父母','兄弟','子孙','妻财','官鬼'):
  main=[{'position':r['position'],'branch':r['branch']} for r in rows if r['kin']==kin]
  changed=[{'position':r['position'],'branch':r['changed']['branch']} for r in rows if r['moving'] and r.get('changed') and r['changed']['kin']==kin]
  hidden=[{'position':r['position'],'branch':r['hidden']['branch']} for r in rows if r.get('hidden') and r['hidden']['kin']==kin]
  candidates[kin]={'main':main,'changed':changed,'hidden':hidden,'search_layer':'main' if main else 'changed' if changed else 'hidden' if hidden else 'absent'}
 shi=next((r for r in rows if r.get('label')=='世'),None)
 ying=next((r for r in rows if r.get('label')=='应'),None)
 return {'lines':facts,'roles_for_each_possible_focal':roles,
  'focal_search_candidates':candidates,
  'focal_search_policy':'先查本卦，再查动爻所化，仍不现才查伏神；本卦已现而空破不能直接改取伏神。候选层级不等于取用裁决。',
  'shi_to_ying':branch_relation(shi['branch'],ying['branch']) if shi and ying else None,
  'limits':'关系事实不等于有效生克或吉凶。未自动计算完整旺衰、暗动、三合成化、刑害、卦级反伏吟与应期；必须说明条件。'}

def source_conditions(question,cast,facts):
 # Select source conditions separately from the capped general-rule search.
 # These are review questions, not computed strength or auspiciousness verdicts.
 ids={'QA-01','QA-03','QA-13','QA-14','QA-18','QA-19'}
 lines=facts['lines']
 changed=[f['changed'] for f in lines if f.get('changed')]
 if changed:ids.add('QA-02')
 if any(f.get('void') or f.get('changed',{}).get('void') or f.get('hidden',{}).get('void') for f in lines):ids.add('QA-07')
 if any(f.get('month_break') or f.get('changed',{}).get('month_break') for f in lines):ids.add('QA-08')
 if any(f.get('hidden') for f in lines):ids.add('QA-09')
 if any(c.get('advance') or c.get('retreat') for c in changed):ids.add('QA-10')
 if any(c.get('clash') for c in changed):ids.add('QA-05')
 if any(c.get('same_branch') for c in changed):ids.add('QA-06')
 if any(f.get(n,{}).get('clash') or f.get(n,{}).get('combine') for f in lines for n in ('day','month','changed')):ids.add('QA-11')
 if any(f.get(n,{}).get('growth_marker') for f in lines for n in ('day','month')):ids.add('QA-12')
 branches={f['branch'] for f in lines}
 if any(len(branches&set(group))>=2 for group in ('申子辰','巳酉丑','寅午戌','亥卯未')):ids.add('QA-04')
 count=sum(f['moving'] for f in lines)
 if count in (1,5):ids.add('QA-15')
 if count in (0,6):ids.add('QA-16')
 kins=[f['kin'] for f in lines]
 if len(kins)!=len(set(kins)):ids.add('QA-17')
 return [r for r in CONDITIONS['rules'] if r['id'] in ids]

def retrieve_rules(question,cast):
 facts=chart_facts(cast);tags={'通用','用神','世应','原神','忌神','六神'}
 q=question.casefold()
 for topic,words in TOPICS.items():
  if any(w in q for w in words):tags.add(topic)
 if cast['moving']:tags.update(('动爻','回头生克','进退'))
 else:tags.add('静卦')
 for f in facts['lines']:
  if f.get('void'):tags.add('旬空')
  if f.get('month_break'):tags.add('月破')
  if f.get('hidden'):tags.add('伏神')
  if f.get('day_clash_review'):tags.add('暗动')
  if any(f.get(n,{}).get('growth_marker') for n in ('month','day')):tags.add('墓绝')
  if f.get('changed',{}).get('combine') or f.get('changed',{}).get('clash'):tags.add('合冲')
 rules=KNOWLEDGE['rules']
 essential={'focal','self_other','support','obstruction','multiple_focal'}
 scored=sorted(rules,key=lambda r:(100 if r['id'] in essential else 0)+sum(3 if tag!='通用' else 1 for tag in r['tags'] if tag in tags),reverse=True)
 # Include triggered constraints ahead of generic optional rules; prompt budget is bounded.
 topic_ids={'job'} if tags & {'工作','考试'} else set()
 if '财运' in tags:topic_ids.add('money')
 priority=[r for r in scored if r['id'] in essential|topic_ids]
 selected=(priority+[r for r in scored if r not in priority])[:14]
 selected+=source_conditions(question,cast,facts)
 supplement_ids={'SUP-13'}
 if '财运' in tags:supplement_ids.add('SUP-16')
 if any(f.get('changed',{}).get('same_branch') for f in facts['lines']):supplement_ids.add('SUP-12')
 if any(f.get('changed',{}).get('combine') for f in facts['lines']):supplement_ids.add('SUP-14')
 if any(f.get(n,{}).get('clash') or f.get(n,{}).get('combine') for f in facts['lines'] for n in ('day','month','changed')):supplement_ids.add('SUP-15')
 selected += [r for r in SUPPLEMENTS['rules'] if r['id'] in supplement_ids]
 topics=[(sum(word.casefold() in q for word in r['keywords']),i,r) for i,r in enumerate(TOPIC_PACKETS['rules'])]
 selected += [r for score,i,r in sorted(topics,key=lambda item:(-item[0],item[1])) if score][:2]
 return {'version':KNOWLEDGE_VERSION,'cases':retrieve_cases(question,cast),'case_version':CASE_VERSION,'rules':selected,'facts':facts,'supplemental':KNOWLEDGE['supplemental'],
  'source_policy':'主体为用户提供书籍的核对释义；书内作者注释与古典正文不得混同。补充资料只限明确列出的来源；没有实时联网，不声称引用最新新闻或研究。'}

def reference_label(rule,lang):
 if rule.get('source_type')=='classical_text_supplement':
  if lang=='en':return f"Bushi Zhengzong, classical supplement {rule['id'].split('-')[-1]} (Shidian Guji)"
  return f"《卜筮正宗》{rule['source_location']}（识典古籍补充正文）"
 if lang=='en':return f"Bushi Zhengzong, part {rule['part']}, PDF p. {rule['pdf_page']}; entry {rule['id']}"
 return f"《卜筮正宗》{rule['chapter']}（第{rule['part']}部分PDF第{rule['pdf_page']}页）〔释义条目 {rule['id']}〕"

PAID_HEADINGS={'zh':('盘面与主次','阻力与可变条件','行动与边界','规则依据'),
 'en':('Chart and priorities','Obstacles and conditions','Actions and boundaries','Source notes')}

def validate_reading(text,lang,tier,free='',rules=()):
 if not isinstance(text,str) or len(text.strip())<30 or len(text)>16000:raise ValueError('invalid content')
 if '<' in text or '```' in text or '{F:' in text:raise ValueError('invalid markup')
 if lang=='en' and re.search(r'[\u3400-\u9fff]',text):raise ValueError('language leakage')
 if tier=='free':
  for heading in (('初判','关键依据') if lang=='zh' else ('Initial reading','Key evidence')):
   if f'【{heading}】' not in text:raise ValueError('missing free section')
  body=re.sub(r'【[^】]+】','',text).strip()
  if lang=='zh' and not 50<=len(re.sub(r'\s','',body))<=80:raise ValueError('free reading length')
  if lang=='en' and not 30<=len(body.split())<=65:raise ValueError('free reading length')
 else:
  for heading in PAID_HEADINGS[lang]:
   if f'【{heading}】' not in text:raise ValueError('missing paid section')
  body=re.sub(r'【[^】]+】','',text.split('【'+PAID_HEADINGS[lang][-1]+'】')[0]).strip()
  if lang=='zh' and not 250<=len(re.sub(r'\s','',body))<=300:raise ValueError('paid reading length')
  if lang=='en' and not 150<=len(body.split())<=210:raise ValueError('paid reading length')
  refs=sum(label in text for label in {reference_label(rule,lang) for rule in rules})
  if refs<2:raise ValueError('missing verified sources')
  # Block substantial verbatim reuse of the free interpretation. Not a semantic quality guarantee.
  body=text.split('【'+PAID_HEADINGS[lang][-1]+'】')[0]
  chunks=[c.strip() for c in re.split(r'[。！？\n.!?]',free) if len(c.strip())>=16]
  if sum(c in body for c in chunks)>=2:raise ValueError('paid repeats free')
 return text.strip()
