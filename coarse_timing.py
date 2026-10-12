"""Output policy: qualitative pace only, never dated forecasts."""
import re

def validate_coarse_timing(text):
    patterns=[
        r'\d{4}[-/年]\d{1,2}',r'\d{1,2}\s*月\s*\d{1,2}',
        r'\d{1,2}\s*(?:月|号)',r'[一二三四五六七八九十]+月(?:份|底|初|中旬|下旬|上旬|[一二三四五六七八九十]+日)',
        r'[子丑寅卯辰巳午未申酉戌亥](?:年|月|日|时)(?:必|会|可|能|有望|左右)',
        r'[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥]\s*(?:日|月|年|时)',
        r'(?:明天|明日|后天|后日|下周[一二三四五六日天]|星期[一二三四五六日天]|周[一二三四五六日天])',
        r'(?:\d+|[一二三四五六七八九十两]+)\s*(?:个)?(?:天|日|周|星期|月|年|小时|时辰)\s*(?:后|内|左右|之内)',
        r'\b(?:tomorrow|the day after tomorrow|next (?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday))\b',
        r'\b(?:in|within|after)\s+(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|a|an)\s+(?:days?|weeks?|months?|years?|hours?)\b',
        r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}\b',
        r'\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\b',
        r'\b(?:on|by|this|next)\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b',
        r'(?:应期|归期|到账|成功|恢复|转机)[^。！？\n]{0,12}[子丑寅卯辰巳午未申酉戌亥](?:日|月|年|时)']
    if any(re.search(p,text,re.I) for p in patterns):
        raise ValueError('specific timing is disabled; use qualitative pace only')
    return text
