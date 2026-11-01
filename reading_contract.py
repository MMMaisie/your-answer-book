"""Validate cited fact snapshots and reader-facing boundaries, never calculate an outcome."""
import re
from theory_facts import ledger,fact_phrases

class EditorialError(ValueError):pass
class EvidenceError(ValueError):pass
class ReadingValidationError(ValueError):
 def __init__(self,stage,reason,finish_reason=None):
  self.stage=stage if stage in {'initial','review','writer','translation'} else 'unknown'
  self.reason=reason if reason in {'evidence','editorial','reference','format_or_fact','incomplete'} else 'unknown'
  self.finish_reason=finish_reason if isinstance(finish_reason,str) and finish_reason in {'stop','length','content_filter','tool_calls','insufficient_system_resource','aborted'} else 'unknown'
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

def validate_reader_text(text,tier,lang='zh',question=''):
 matches=list((JARGON if lang=='zh' else EN_JARGON).finditer(text))
 if tier=='free' and matches:raise EditorialError('preview must contain no technical reasoning')
 if tier=='paid' and len(matches)>4:raise EditorialError('technical notes dominate reader prose')
 # Do not repeat the same long sentence across the three paragraphs.
 sentences=[s.strip() for s in re.split(r'[。！？.!?\n]',text) if len(s.strip())>=12]
 if len(sentences)!=len(set(sentences)):raise EditorialError('repeated reader sentence')
 # Explicit harmful inference seen in production, unless the subject was raised by the user.
 if not re.search(r'吸引|魅力|精力|内耗|心理|焦虑',question):
  if re.search(r'(?:直接影响|导致|说明你|证明你)[^。；\n]{0,16}(?:吸引力|魅力|精力不足|内耗)|自身能量回升|恢复精力|减少内耗',text):
   raise EditorialError('unprovided personal condition')
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
