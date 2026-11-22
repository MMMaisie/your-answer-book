"""Validate cited fact snapshots and reader-facing boundaries, never calculate an outcome."""
import re
from theory_facts import ledger,fact_phrases

class EditorialError(ValueError):
 def __init__(self,message,code='unspecified'):
  self.code=code
  super().__init__(message)
EVIDENCE_CODES={
 'fact_checks required':'evidence_missing',
 'invalid evidence shape':'evidence_shape',
 'unknown or duplicate fact':'evidence_reference',
 'fact belongs to another line':'evidence_line',
 'missing or unknown fact attributes':'evidence_attributes',
 'fact snapshot contradicts chart':'evidence_value',
 'decision references missing checked facts':'evidence_decision',
 'reason must cite checked facts':'evidence_reason',
 'reason references missing':'evidence_reason_missing',
 'too many reason references':'evidence_reason_count',
 'reason reference unknown':'evidence_reason_unknown',
 'unverified technical anchor':'evidence_anchor',
 'conflicting evidence formats':'evidence_conflict',
}
class EvidenceError(ValueError):
 def __init__(self,message):
  self.code=EVIDENCE_CODES.get(message,'evidence_shape')
  self.repair={
   'evidence_reason_missing':'每个reasons条目必须有非空fact_ids数组，包含1至4个输入事实表中的真实编号；不得省略或用自然语言代替。',
   'evidence_reason_count':'每个原因条目只选择1至4个最相关的事实编号，不能把全盘编号抄到一条原因中。',
   'evidence_reason_unknown':'原因引用必须原样使用输入事实表中的真实编号。',
   'evidence_reference':'核对顶层、reasons及technical_anchor_ids的全部引用，只用输入事实表存在的编号。',
  }.get(self.code,'')
  super().__init__('evidence rejected: '+self.code)


REPAIR_HINTS={
 'initial_outlook':'初判outlook必须是favorable、mixed、difficult、unclear之一。',
 'initial_analysis':'analysis必须为非空字符串且不超过600字，简记依据，不写全文。',
 'review_outlook':'复核outlook必须是favorable、mixed、difficult、unclear之一。',
 'review_summary':'technical_summary必须为1至600字的字符串，简记核对结果。',
 'review_brief':'answer、watch、limits必须为字符串，各自最多140、180、120字；不用的limits可为空字符串，不能为null。',
 'review_answer':'answer必须直接回应原问题，非空且最多140字。',
 'review_reasons':'reasons必须是包含1至2个对象的数组，每项含explanation和fact_ids。',
 'review_reason':'每条原因的explanation必须为1至160字的字符串。',
 'review_correction':'correction_reason必须为不超过160字的字符串；若复核outlook不同于previous_initial.outlook，必须简述改变判断的依据，不得留空。',
 'unverified_realworld':'不能把象意说成已证实的房屋缺陷、产权债务、疾病或第三者事实；删除断言，改为明确的核实事项。保留已复核的倾向，不编造具体原因。',
 'json_syntax':'返回完整合法JSON对象，不使用JSON之外的文字。',
 'prose_fields':'字段必须符合原请求：free为direction；paid为priorities、conditions、actions，值均为非空字符串。',
 'prose_markup':'只写普通文本，去掉标题括号、代码围栏、HTML和占位符。',
 'prose_length':'总长度超限：按原请求的语言、tier和limit精简；中文按含标点字符数、英文按词数计算，所有字段合计，不截断句子。',
 'language_leakage':'英文内容中不能出现未翻译的中文。',
 'chart_claim':'正文中的爻位、六亲、动静或月建状态与卦盘不一致。不得新编依据；回到已核对摘要，删去不受支持的技术断言，保留判断。',
 'element_relation':'正文的五行关系方向与基础关系不一致。不得新编依据；按已核对摘要用白话解释，不自行添加生克断言。',
 'theory_claim':'正文中的空破、生克、回头生克等技术断言未通过核对。只按已核对摘要表达，不新增技术结论。',
 'specific_timing':'删除具体日期、干支应期和数字时长，只保留有依据的大概节奏。',
 'absolute_outcome':'删除保证或必然成功失败的措辞，保持原有倾向和不确定范围。',
 'writer_outlook':'outlook必须原样复制请求schema中的值，不得改变已复核判断。'
}
class ContentValidationError(ValueError):
 def __init__(self,code):
  self.code=code
  super().__init__('content validation rejected: '+(code if code in REPAIR_HINTS else 'unspecified'))
class ReadingValidationError(ValueError):
 def __init__(self,stage,reason,finish_reason=None,detail=None,attempt=None,max_tokens=None):
  self.stage=stage if stage in {'initial','review','writer','translation'} else 'unknown'
  self.reason=reason if reason in {'evidence','editorial','reference','format_or_fact','incomplete'} else 'unknown'
  self.finish_reason=finish_reason if isinstance(finish_reason,str) and finish_reason in {'stop','length','content_filter','tool_calls','insufficient_system_resource','aborted'} else 'unknown'
  self.detail=detail if isinstance(detail,str) and detail in {'preview_jargon','paid_jargon','repetition','personal_inference','review_preview_jargon','review_preview_repetition','review_preview_personal_inference','review_personal_inference'} | set(REPAIR_HINTS) | set(EVIDENCE_CODES.values()) else 'unspecified'
  self.attempt=attempt if type(attempt) is int and 1<=attempt<=2 else None
  self.max_tokens=max_tokens if type(max_tokens) is int and 1<=max_tokens<=32768 else None
  super().__init__('reading validation rejected')

REQUIRED={
 'state':{'branch','kin','moving'},
 'changed':{'original_branch','changed_branch','original_kin','changed_kin','element_relation'},
 'hidden':{'branch','kin'},
 'day':{'source','target','element_relation'},
 'month':{'source','target','element_relation'},
}

def validate_evidence(items,cast):
 if not isinstance(items,list) or not 1<=len(items)<=12:raise EvidenceError('fact_checks required')
 catalog={f['id']:f for f in ledger(cast)['lines']};result=[];seen=set()
 for item in items:
  if not isinstance(item,dict) or set(item)!={'fact_id','position','claim'}:raise EvidenceError('invalid evidence shape')
  fid=item['fact_id'];position=item['position'];claim=item['claim']
  if not isinstance(fid,str) or fid not in catalog or fid in seen:raise EvidenceError('unknown or duplicate fact')
  match=re.fullmatch(r'([1-6])\.(state|changed|hidden|day|month)',fid)
  if not match or type(position) is not int or position!=int(match[1]):raise EvidenceError('fact belongs to another line')
  fact=catalog[fid]
  if not isinstance(claim,dict) or not REQUIRED[match[2]]<=claim.keys() or not claim.keys()<=fact.keys()-{'id'}:raise EvidenceError('missing or unknown fact attributes')
  for key,value in claim.items():
   expected=fact[key]
   if type(value) is not type(expected) or value!=expected:raise EvidenceError('fact snapshot contradicts chart')
  seen.add(fid);result.append({'fact_id':fid,'position':position,'claim':dict(claim)})
 return result

# These are vocabulary boundaries, not a semantic judgement or a success/failure gate.
JARGON=re.compile(r'用神|原神|忌神|仇神|世爻|应爻|飞神|伏神|出空|出伏|旬空|月破|日克|日泄|月克|月扶|化进|回头生|回头克|泄气|财星|官星|妻财|官鬼|[子丑寅卯辰巳午未申酉戌亥][木火土金水]')
EN_JARGON=re.compile(r'\b(?:significator|flying spirit|hidden spirit|month[- ]broken|returning (?:generation|control))\b',re.I)

def validate_reader_text(text,tier,lang='zh',question='',check_style=True):
 matches=list((JARGON if lang=='zh' else EN_JARGON).finditer(text))
 if check_style and tier=='free' and matches:raise EditorialError('preview must contain no technical reasoning','preview_jargon')
 if check_style and tier=='paid' and len(matches)>4:raise EditorialError('technical notes dominate reader prose','paid_jargon')
 # Do not repeat the same long sentence across the three paragraphs.
 sentences=[s.strip() for s in re.split(r'[。！？.!?\n]',text) if len(s.strip())>=12]
 if check_style and len(sentences)!=len(set(sentences)):raise EditorialError('repeated reader sentence','repetition')
 # Explicit harmful inference seen in production, unless the subject was raised by the user.
 if not re.search(r'吸引|魅力|精力|内耗|心理|焦虑',question):
  if re.search(r'(?:直接影响|导致|说明你|证明你)[^。；\n]{0,16}(?:吸引力|魅力|精力不足|内耗)|自身能量回升|恢复精力|减少内耗',text):
   raise EditorialError('unprovided personal condition','personal_inference')
 return text

def fact_notes(cast,checks):
 phrases=fact_phrases(cast,'zh');notes={}
 for item in checks:
  fid=item['fact_id'];fact=next(f for f in ledger(cast)['lines'] if f['id']==fid)
  if fid in phrases:notes[fid]=phrases[fid]
  elif fid.endswith('.state'):
   row=next(r for r in cast['rows'] if r['position']==item['position'])
   notes[fid]=f"第{row['position']}爻{row['kin']}{row['branch']}{row['element']}，"+('发动' if row['moving'] else '为静爻')
  elif fid.endswith('.hidden'):
   row=next(r for r in cast['rows'] if r['position']==item['position']);h=row['hidden']
   notes[fid]=f"第{row['position']}爻下伏{h['kin']}{h['branch']}{h['element']}"
 return notes


def validate_grounded_copy(text,question=''):
 # Narrow regression guard, not a general semantic proof of groundedness.
 # User questions can mention these risks without proving they exist.
 patterns=[
  r'(?:显示|说明|证明|确定|可见)[^。；\n]{0,30}(?:存在明显隐患|存在严重隐患|存在隐性债务|存在产权纠纷|有结构性损坏)',
  r'(?:房屋|房子|交易条件)[^。；\n]{0,14}(?:有明显问题|存在明显问题|存在严重问题)',
  r'(?:对方|伴侣|他|她)(?:已经|肯定|一定)(?:出轨|有第三者|隐瞒债务)',
  r'(?:你|患者)(?:已经|肯定|一定)(?:患有|得了)[^。；\n]{1,15}',
 ]
 for sentence in re.split(r'[。；\n]',text):
  # Explicitly bounded or conditional checks are not factual assertions.
  if re.search(r'不能(?:证明|确定|判断)|无法(?:证明|确定|判断)|不代表|尚未证实|是否|若|如果',sentence):continue
  if any(re.search(pattern,sentence) for pattern in patterns):
   raise ContentValidationError('unverified_realworld')
 return text


def resolve_evidence(value,cast):
 if 'fact_ids' not in value:return validate_evidence(value.get('fact_checks'),cast)
 ids=value['fact_ids']
 if not isinstance(ids,list) or not 1<=len(ids)<=12:raise EvidenceError('fact_checks required')
 catalog={f['id']:f for f in ledger(cast)['lines']}
 if any(not isinstance(fid,str) or fid not in catalog for fid in ids):
  raise EvidenceError('unknown or duplicate fact')
 result=[]
 for fid in dict.fromkeys(ids):
  match=re.fullmatch(r'([1-6])\.(state|changed|hidden|day|month)',fid)
  if not match:raise EvidenceError('unknown or duplicate fact')
  fact=catalog[fid]
  result.append({'fact_id':fid,'position':int(match[1]),
    'claim':{key:fact[key] for key in sorted(REQUIRED[match[2]])}})
 result=validate_evidence(result,cast)
 if 'fact_checks' in value:
  old=validate_evidence(value['fact_checks'],cast)
  if {x['fact_id'] for x in old}!={x['fact_id'] for x in result}:
   raise EvidenceError('conflicting evidence formats')
 return result
