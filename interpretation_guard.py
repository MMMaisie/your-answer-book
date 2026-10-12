"""Reject a small set of explicit, unsupported rule shortcuts.

This is not a complete rule engine or proof of natural-language correctness.
"""
import re

def validate_interpretation(text,question=''):
    if not isinstance(text,str):raise ValueError('invalid interpretation')
    errors=[]
    # Reject an explicit symbolic-to-real-world causal shortcut, not every discussion of tomb.
    if re.search(r'(?:其|竞争方|合伙方)受月墓制约(?:则|所以|故)?阻力小',text):
        errors.append('month tomb cannot establish real-world competitor constraint')
    if re.search(r'兄弟[^。；\n]{0,25}(?:入月墓|月墓)[^。；\n]{0,8}(?:暂不为大忌|阻力小)',text):
        errors.append('tomb status needs effectiveness and exception review before minimizing obstruction')
    body=text.split('【规则依据】')[0].split('【Source notes】')[0]
    if re.search(r'免费初判|与初判一致|对应阻力与变化条件|方向对但|the free initial reading|matching the initial judgment|these correspond to obstacles',body,re.I):
        errors.append('internal review commentary is not a customer reading')
    if re.search(r'(?:孩子|儿子|女儿)(?:暂时|现在|目前)?(?:还)?(?:回不来|不能回|必定|一定)|\b(?:the child|your son|your daughter)\s+(?:cannot|will definitely|will certainly)\b',body,re.I):
        errors.append('unqualified real-world outcome; state the conditional chart indication')
    if re.search(r'(?:无动爻|静卦|没有动爻)[^。；\n]{0,12}(?:不能|无法|不可能)定(?:具体)?(?:日期|应期)|no moving lines[^.!?]{0,35}(?:no specific date|cannot.*tim)',body,re.I):
        errors.append('static state alone does not rule out timing analysis')
    if re.search(r'(?:主要阻力是|本盘|当前)(?:原神|子孙)[^。；\n]{0,8}空破',body):
        errors.append('ambiguous combined status: name the line and distinguish void from month-broken')
    if re.search(r'用神[^。；\n]{0,12}(?:被|受)空破|primary line[^.!?]{0,25}void and broken',body,re.I):
        errors.append('different candidate lines must not be merged into one void-and-broken primary')
    if re.search(r'现实(?:中的)?(?:竞品|合伙分利)[^。；\n]{0,5}正强',body):
        errors.append('symbolic role cannot establish actual competition or profit-sharing facts')

    if re.search(r'旬空(?:当前|暂时|现在)?(?:无力|无用|失效)|\bvoid\s+(?:and\s+)?(?:currently\s+)?(?:powerless|ineffective)\b',body,re.I):
        errors.append('void status alone does not establish powerlessness; review support and effectiveness')
    if re.search(r'化进[^。；\n]{0,12}(?:归意|想回|愿回)|\b(?:advanc\w*|progression)\b[^.!?\n]{0,35}return intent',body,re.I):
        errors.append('advancing change cannot establish actual intention to return')
    if re.search(r'\bback[- ]clash\b',body,re.I):
        errors.append('returning control must not be translated as clash')

    # A narrow explicit shortcut check; not a general adjudication of static lines.
    for sentence in re.split(r'[。！？\n.!?]',text):
        if re.search(r'不(?:能|可|应)(?:仅|只)|不能一概|并非|not solely|cannot conclude',sentence,re.I):continue
        conditional_static=bool(re.search(r'休囚(?:且)?不动|\b(?:weak|debilitated|exhausted)\s+and\s+static\b',sentence,re.I))
        if not conditional_static and (re.search(r'兄弟[^。；\n]{0,12}(?:安静|静爻|静而不动|静而未动|静而未发动)[^。；\n]{0,8}(?:暂)?不(?:会)?劫财',sentence) or re.search(r'\b(?:sibling|brother)[^.!?]{0,25}\bstatic\b[^.!?]{0,20}\b(?:cannot|does not)\b[^.!?]{0,12}\b(?:wealth|money)\b',sentence,re.I)):
            errors.append('static state alone cannot rule out wealth restriction')
        if not conditional_static and (re.search(r'(?:静而不动|安静未动|原神[^，。；\n]{0,10}未动)[^。；\n]{0,30}(?:不能|难)(?:有效|直接)?生(?:用|扶|财)',sentence) or re.search(r'\bstatic\b[^.!?\n]{0,45}(?:cannot|unable to)\s+(?:directly |effectively )?generate',sentence,re.I)):
            errors.append('static state alone cannot establish absence of effective support')
        if not conditional_static and (re.search(r'静(?:爻|无动|未动|而不动)?[^。；\n]{0,18}(?:不成实际克力|没有(?:任何)?生克作用|无生克作用|不能生克)',sentence) or re.search(r'\bstatic\b[^.!?]{0,65}(?:do not form actual controlling force|cannot (?:generate|control)|no (?:generating|controlling) (?:force|effect))',sentence,re.I)):
            errors.append('static state alone cannot establish absence of effective interaction')
        if re.search(r'待申酉(?:金)?日[^。；\n]{0,12}(?:再扩大投入|后再扩大投入)',sentence) or re.search(r'wait until Shen/You[^.!?]{0,45}before expanding investment',sentence,re.I):
            errors.append('branch day alone cannot justify expanding investment')

    for sentence in re.split(r'[。！？\n.!?]',text):
        if re.search(r'不(?:是|代表|等于|保证|能仅)|并非|\b(?:not|never guarantees)\b',sentence,re.I):continue
        if re.search(r'出空(?:就|便|即可|必定|必然)(?:能)?(?:得财|成功|获利)|\b(?:void\s+(?:ends|fills)|out of void)\b.{0,25}\b(?:guarantees|ensures)\b',sentence,re.I):
            errors.append('void ending cannot guarantee outcome')
        if re.search(r'出空方得',sentence) and not re.search(r'还需|仍需|尚需|须再|生扶有效|受制解除',text):
            errors.append('unqualified void timing needs effective support conditions')
        wealth=bool(re.search(r'财|收入|生意|投资|\b(?:wealth|money|income|business|invest)',question,re.I))
        if wealth and (re.search(r'克世[^。；\n]{0,8}(?:不取|舍弃|弃用)',sentence) or re.search(r'controls\s+(?:the\s+)?self[^.!?]{0,35}(?:reject|exclude|discard)',sentence,re.I)):
            errors.append('wealth candidate cannot be excluded solely for controlling self')
    if errors:raise ValueError('; '.join(dict.fromkeys(errors)))
    return text
