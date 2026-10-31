"""Deterministic retrieval chooses references, never a verdict or a forced yongshen."""
import hashlib,json,re
from theory_facts import ledger
CORE={'five_elements','branch_relations','focal','self_other','support','obstruction','one_question','functional_focal','strength_dynamic_joint','hexagram_not_verdict','QA-01','intent_before_cast'}
SIGNALS={'旬空':('void','empty'),'月破':('month_break',),'动爻':('changed','single_move','many_moves'),'伏神':('hidden','flying'),'墓绝':('growth','rescue'),'合冲':('combine','clash'),'取用':('intent','multiple_focal','roles')}

def select_rules(rules,question,cast,topics):
 facts=ledger(cast);tags={'取用','用神','世应','生克'}
 if cast.get('moving'):tags|={'动爻','回头','回头生克','进退','暗动','三合','反吟','伏吟'}
 else:tags|={'静卦','暗动'}
 if any(x.get('void') for x in facts['lines']):tags.add('旬空')
 if any(x.get('month_broken') for x in facts['lines']):tags.add('月破')
 if any(r.get('hidden') for r in cast.get('rows',[])):tags.add('伏神')
 # Grave/growth are conditional concepts; inclusion never asserts the condition holds.
 tags|={'墓绝','合冲'}
 for key,values in SIGNALS.items():
  if key in tags:tags.update(values)
 topic_tags={'求职':{'工作','考试','官鬼','父母'},'求财':{'财运','妻财','子孙'},'婚恋':{'婚姻'}}
 for topic in topics:tags.update(topic_tags.get(topic,set()))
 ranked=[]
 for r in rules:
  if r.get('runtime_eligible') is False:continue
  words=r.get('keywords',[]);matched=any(str(w).casefold() in question.casefold() for w in words)
  rt=set(r.get('tags',[]));score=1000 if r['id'] in CORE else 100 if matched else 5*len(tags&rt)
  if score:ranked.append((score,r['id'],r))
 selected=[r for _,_,r in sorted(ranked,key=lambda x:(-x[0],x[1]))[:40]]
 return selected

def case_rank(case,cast):
 rows=cast.get('rows',[]);old=case.get('lines',[])
 motions={r['position'] for r in rows if r.get('moving')};cm={r['position'] for r in old if r.get('moving')}
 # Theme matching is required by the caller; structural similarity only ranks analogies.
 score=8*(case.get('main')==cast['main']['name'])+3*(motions==cm)
 score+=sum(a.get('kin')==b.get('kin') for a,b in zip(sorted(rows,key=lambda r:r['position']),sorted(old,key=lambda r:r['position'])))
 return score

def snapshot_metadata(rules,cases):
 payload=json.dumps([rules,cases],ensure_ascii=False,sort_keys=True).encode()
 return {'reference_hash':hashlib.sha256(payload).hexdigest()[:16],
 'policy':'Literature is context, not independent evidence or a guaranteed outcome. Compare intent, roles, calendar and moving-line conditions before applying a case.'}
