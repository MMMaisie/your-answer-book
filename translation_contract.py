"""Tier-specific translation contracts with source labels owned by the program."""
import re
from reading_knowledge import PAID_HEADINGS,REFERENCE_RULES,reference_label
from reading_output import assemble

def headings(lang,tier):
    return (('初判','关键依据') if lang=='zh' else ('Initial reading','Key evidence')) if tier=='free' else PAID_HEADINGS[lang]

def sections(text,lang,tier):
    expected=headings(lang,tier)
    found=re.findall(r'【([^】]+)】',text)
    if tuple(found)!=tuple(expected):raise ValueError('section order/count contradicts tier')
    if text.split('【',1)[0].strip():raise ValueError('unexpected section preamble')
    values=re.split(r'【[^】]+】',text)[1:]
    if any(not value.strip() for value in values):raise ValueError('empty section')
    return dict(zip(expected,(value.strip() for value in values)))

def source_pairs(text,lang):
    # Match only citation lines, not every occurrence in a body paragraph.
    notes=re.split(r'【(?:规则依据|Source notes)】',text)[-1]
    pairs=[];seen=set()
    for line in notes.splitlines():
        line=line.strip().lstrip('- ').strip()
        matches=[(reference_label(rule,source_lang),rule) for rule in REFERENCE_RULES for source_lang in ('zh','en') if line.startswith(reference_label(rule,source_lang))]
        if not matches:continue
        label,rule=max(matches,key=lambda pair:len(pair[0]))
        target=reference_label(rule,lang)
        if target in seen:continue
        seen.add(target)
        note=line[len(label):].lstrip(' —–-:：').strip()
        pairs.append({'id':rule['id'],'source_label':label,'target_label':target,'application':note})
    return pairs

def contract(text,lang,tier):
    if lang not in ('zh','en') or tier not in ('free','paid'):raise ValueError('invalid translation mode')
    base={'tier':tier,'headings':headings(lang,tier),'body_count':{'unit':'characters excluding whitespace' if lang=='zh' else 'words','allowed':([50,80] if lang=='zh' else [30,65]) if tier=='free' else ([250,300] if lang=='zh' else [150,210]),'target':(70 if lang=='zh' else 45) if tier=='free' else (275 if lang=='zh' else 180)}}
    if lang=='en':
        base['field_word_budgets']=({'direction':[18,25],'evidence':[20,30]} if tier=='free' else {'priorities':[50,60],'conditions':[55,65],'actions':[50,60]})
        base['compression_policy']='Translate the meaning concisely, not word for word. Merge repeated claims; retain unique evidence, qualifications, focal selection and both actions. Count body words excluding headings and source applications. Do not truncate or pad.'
    if tier=='free':
        base['output_schema']={'text':{'direction':'translated direction','evidence':'translated evidence'}}
        base['instruction']='Translate only the two free paragraphs. Do not add advice, sources, paid sections, or new analysis. No headings in field values; the program adds them.'
    else:
        pairs=source_pairs(text,lang)
        if len(pairs)!=2:raise ValueError('canonical paid reading needs two translatable distinct source labels')
        base['sources']=pairs
        base['source_application_limit']={'unit':'characters' if lang=='zh' else 'words','maximum':250 if lang=='zh' else 60}
        base['output_schema']={'text':{'priorities':'translated paragraph','conditions':'translated paragraph','actions':'translated paragraph','source_applications':['first translated application','second translated application']}}
        base['instruction']='Translate each of the three paid paragraphs and each source application in its original order. Do not change selected lines, interpretations, conditions or sources. No headings or source labels in field values; the program adds them.'
    return base

def render(content,lang,tier,spec,cast):
    if not isinstance(content,dict) or set(content)!={'text'}:raise ValueError('translation requires only text key')
    value=content['text']
    if isinstance(value,str):
        # Compatibility with older responses; still enforce the exact tier structure.
        from reading_guard import normalize_headings
        result=normalize_headings(value,lang,tier)
    elif tier=='free':result=assemble({'free':value},lang,'free',(),cast)
    else:
        if not isinstance(value,dict) or set(value)!={'priorities','conditions','actions','source_applications'}:raise ValueError('invalid paid translation fields')
        notes=value['source_applications']
        if not isinstance(notes,list) or len(notes)!=2:raise ValueError('translation needs two source applications')
        paid={field:value[field] for field in ('priorities','conditions','actions')}
        paid['sources']=[{'id':pair['id'],'application':note} for pair,note in zip(spec['sources'],notes)]
        rules=[next(r for r in REFERENCE_RULES if r['id']==p['id']) for p in spec['sources']]
        result=assemble({'paid':paid},lang,'paid',rules,cast)
    parts=sections(result,lang,tier)
    if tier=='paid':
        actual={p['target_label'] for p in source_pairs(result,lang)}
        expected={p['target_label'] for p in spec['sources']}
        if actual!=expected:raise ValueError('translation changed canonical sources')
        lines=[line.strip().lstrip('- ').strip() for line in parts[PAID_HEADINGS[lang][-1]].splitlines() if line.strip()]
        if len(lines)!=2 or not all(line.startswith(pair['target_label']) for line,pair in zip(lines,spec['sources'])):
            raise ValueError('translation source order/count mismatch')
    return result
