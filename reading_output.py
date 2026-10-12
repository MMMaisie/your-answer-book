"""Structured paid output, exact source assembly, and actionable repair diagnostics.

No truncation, canned interpretation, or relaxation of acceptance limits.
"""
import re
from theory_facts import render_fact_slots,explicit_focus,validate_translation_focus
from interpretation_guard import validate_interpretation
from reading_knowledge import PAID_HEADINGS,reference_label,validate_reading
from reading_guard import normalize_headings,validate_explicit_relations,validate_chart_claims,validate_focal

FIELDS=('priorities','conditions','actions')

def validate_selection_context(text,question,cast):
    # Bare topic labels do not supply the case-specific purpose or year horizon.
    kin={'求财':'妻财','升迁':'官鬼','promotion':'官鬼'}.get(question.strip().casefold())
    candidates=[r for r in cast.get('rows',[]) if r.get('kin')==kin] if kin else []
    if len(candidates)<2:return text
    body=text.split('【规则依据】')[0].split('【Source notes】')[0]
    if question.strip()=='升迁' and re.search(r'(?:今年|明年|当年|来年|近期)[^。；，\n]{0,24}(?:看|取|对应|重点)[^。；，\n]{0,12}[子丑寅卯辰巳午未申酉戌亥](?:土|官)|(?:this|next) year[^.!?]{0,45}\b(?:Chen|Chou)\b',body,re.I):
        raise ValueError('unstated year context cannot be mapped to a fixed candidate')
    if explicit_focus(body) and not re.search(r'若|如果|假如|\bif\b',body,re.I):
        raise ValueError('multiple candidates with unstated purpose or horizon: do not invent a unique primary')
    return text

def output_contract(lang,tier='paid'):
    target='Chinese' if lang=='zh' else 'English'
    if tier=='free':
        return f'''FINAL OUTPUT CONTRACT: Never infer absence of support from static alone. Never merge different candidates into one primary. For a bare wealth/promotion question with multiple candidates, keep conditional alternatives; do not name one unconditional primary. Never use wealth-strong/self-weak as a verdict or a branch month as an investment action date. Calendar relations must use provided fact slots or exact supplied direction. Return {{"free":{{"direction":"...","evidence":"..."}}}}.
Write both fields in {target}. No headings: the program adds them. Combined body target 70 Chinese characters, allowed 50-80 excluding whitespace; English target 45 words, allowed 30-65. Give a useful conditional direction and one concrete chart basis in plain language. Identify the one grounded tension or condition that matters to this question; do not manufacture suspense or real-life facts. Do not replace the answer with generic caution or a list of technical terms. Avoid generic advice, promises, invented real-life events, and claiming that void alone prevents action. No Chinese glyphs in English.'''
    budgets='priorities 95-100 characters; conditions 90-95; actions 80-85' if lang=='zh' else 'priorities 60-65 words; conditions 55-60; actions 45-50'
    return f'''FINAL OUTPUT CONTRACT (overrides the earlier string output format):
Return {{"paid":{{"priorities":"...","conditions":"...","actions":"...","sources":[{{"id":"provided rule ID","application":"short explanation"}},{{"id":"another provided rule ID","application":"short explanation"}}]}}}}.
All prose must be {target}. Never infer absence of support from static alone. Never use wealth-strong/self-weak as a verdict or a branch month as an investment action date. If a bare wealth/promotion question has multiple candidates and no purpose or horizon, retain conditional alternatives, no unconditional primary. Distinguish missing context from failed prospects. Use exact fact slots for day/month relationships rather than rewriting their direction. Do not put headings in fields. The application adds exact headings and source labels.
For an explicit original-to-changed relation, use the provided {{F:POSITION.changed}} slot. Do not relabel a transformation yourself as returning control: water controls fire, earth controls water, water never controls earth. Explain applicability after the program-owned fact. Do not omit an existing focal candidate simply to simplify the reading.
Writing budgets: {budgets}. Count all three paragraphs together: Chinese 250-300 characters excluding whitespace, English 150-210 words. Aim for Chinese 275 or English 180. Do not include a fourth body paragraph.
Use exactly two different provided sources with different reference labels. Explain how each applies, without quoting paraphrases as original text or inventing chapter names.
For English use only English prose and pinyin branches: controls, generates, void, month-broken, static, moving; never insert Chinese glyphs such as 生 or 克.
Void and month-broken are distinct conditions; name only the condition established by the chart. A void line is not automatically incapable of acting. Static wealth questions must not import 'wealth strong, self weak, cannot bear wealth' as a complete verdict without an applicable six-line rule. Explain role and applicability, not just a list of relations.
Address the key tension raised in the free reading: explain the obstacle, what would change the judgment, and two specific checks or actions linked to those conditions. Distinguish real-world checks from symbolic chart conditions. Preserve the substantive counter-condition and both practical actions when shortening. Do not pad, truncate, or invent chart facts to meet the count.'''

def assemble(raw,lang,tier,rules,cast=None):
    value=raw.get(tier) if isinstance(raw,dict) else None
    if isinstance(value,str):
        return render_fact_slots(normalize_headings(value,lang,tier),cast,lang)
    if tier=='free':
        if not isinstance(value,dict) or set(value)!={'direction','evidence'}:raise ValueError('free object requires direction and evidence')
        headings=('初判','关键依据') if lang=='zh' else ('Initial reading','Key evidence')
        for field in ('direction','evidence'):
            if not isinstance(value[field],str) or not value[field].strip() or '【' in value[field]:raise ValueError('invalid free paragraph')
        return '\n'.join('【'+h+'】'+render_fact_slots(value[f].strip(),cast,lang) for h,f in zip(headings,('direction','evidence')))
    if not isinstance(value,dict) or set(value)!=set(FIELDS+('sources',)):
        raise ValueError('paid object requires priorities, conditions, actions, sources')
    paragraphs=[]
    for field in FIELDS:
        text=value[field]
        if not isinstance(text,str) or not text.strip() or '【' in text or '\n' in text.strip():
            raise ValueError('invalid paid paragraph: '+field)
        paragraphs.append(render_fact_slots(text.strip(),cast,lang))
    sources=value['sources']
    if not isinstance(sources,list) or len(sources)!=2:raise ValueError('exactly two sources required')
    allowed={r['id']:r for r in rules}
    labels=set();notes=[]
    for source in sources:
        if not isinstance(source,dict) or set(source)!={'id','application'} or not isinstance(source['id'],str) or source['id'] not in allowed:
            raise ValueError('unverified source ID')
        note=source['application']
        if not isinstance(note,str) or not note.strip() or '\n' in note or '【' in note:
            raise ValueError('invalid source application')
        if (lang=='zh' and len(note)>250) or (lang=='en' and (len(note)>1000 or len(re.findall(r"\b[\w]+(?:[-’'][\w]+)*\b",note))>60)):
            raise ValueError('source application exceeds localized limit')
        label=reference_label(allowed[source['id']],lang)
        if label in labels:raise ValueError('sources must have different reference labels')
        labels.add(label);notes.append(label+' — '+render_fact_slots(note.strip(),cast,lang))
    h=PAID_HEADINGS[lang]
    return '\n'.join('【'+title+'】'+paragraph for title,paragraph in zip(h[:3],paragraphs))+'\n【'+h[3]+'】\n'+'\n'.join(notes)

def diagnostics(text,question,cast,lang,tier,free,rules):
    errors=[]
    for check in ((lambda:validate_translation_focus(free,text) if tier=='paid' and explicit_focus(free) else text),lambda:validate_selection_context(text,question,cast),lambda:validate_interpretation(text,question),lambda:validate_explicit_relations(text),lambda:validate_focal(text,question),lambda:validate_chart_claims(text,cast),lambda:validate_reading(text,lang,tier,free,rules)):
        try:check()
        except (ValueError,TypeError) as error:
            if str(error) not in errors:errors.append(str(error))
    if isinstance(text,str):
        body=text.split('【'+PAID_HEADINGS[lang][-1]+'】')[0] if tier=='paid' else text
        body=re.sub(r'【[^】]+】','',body).strip()
        count=len(re.sub(r'\s','',body)) if lang=='zh' else len(body.split())
        lo,hi=(250,300) if lang=='zh' and tier=='paid' else (150,210) if tier=='paid' else (50,80) if lang=='zh' else (30,65)
        if not lo<=count<=hi and not any('length' in e for e in errors):errors.append(tier+' reading length')
        parts=[v.strip() for v in re.split(r'【[^】]+】',text)[1:]]
        fields=FIELDS if tier=='paid' else ('direction','evidence')
        field_counts={field:(len(re.sub(r'\s','',value)) if lang=='zh' else len(value.split())) for field,value in zip(fields,parts)}
        targets=([98,94,83] if lang=='zh' else [60,60,60]) if tier=='paid' else ([30,40] if lang=='zh' else [22,23])
        revision={field:{'current':field_counts.get(field,0),'target':target,'change':target-field_counts.get(field,0)} for field,target in zip(fields,targets)}
        return {'errors':errors,'body_count':count,'unit':'characters excluding whitespace' if lang=='zh' else 'words','allowed':[lo,hi],'field_counts':field_counts,'field_revision':revision}
    return {'errors':errors or ['invalid content']}

def repair_prompt(details,lang,tier):
    language='Chinese' if lang=='zh' else 'English only, no Chinese characters anywhere'
    return f'''Rewrite the complete {tier} JSON response in {language}. The previous response failed acceptance.
This is a fresh compact rewrite, not a request to retain the previous paragraph lengths. Put each distinct fact in one place only. Do not repeat the initial direction in priorities and conditions. Keep the two practical actions, remove internal review commentary. If selection depends on an unstated horizon or purpose, name the missing context rather than inventing a unique primary or dates.
Measured diagnostics: {details!r}
Use field_revision as measured guidance: a positive change means expand that field with relevant reasoning or a concrete verification step; a negative change means compress repetition. Target the midpoint, never just the boundary. Do not repeat conclusions to fill a deficit. Repair ALL listed failures together. A semantic correction must still satisfy length and source requirements. Do not shrink a paid response to free length. Do not return the same response. Count body text before submitting.
Keep the original format contract. Chinese paid field budgets: priorities 95-100 characters, conditions 90-95, actions 80-85, totaling 265-280. English paid: priorities 50-60 words, conditions 55-65, actions 50-60. Check every field and total before submitting. For paid use the paid object with priorities, conditions, actions, sources; target 275 Chinese characters or 180 English words in the first three fields together. Source applications are excluded from the body count.
For free use the free object with direction and evidence; target 70 Chinese characters or 45 English words.
Preserve chart facts, conditional reasoning and substantive actions; remove repeated explanation first. Never cut a sentence mechanically or add unsupported facts. Verify day/month direction and static/moving state; void does not automatically mean powerless. Source IDs must come from the provided rules.'''
