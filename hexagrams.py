"""King Wen sequence; bits and line positions always run bottom to top."""
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from lunar_python import Solar

TRIGRAMS = {
 '乾': ('111','金','天'), '坤': ('000','土','地'), '震': ('100','木','雷'),
 '巽': ('011','木','风'), '坎': ('010','水','水'), '离': ('101','火','火'),
 '艮': ('001','土','山'), '兑': ('110','金','泽'),
}
# number|name|upper|lower|theme|interpretive limit|painting brief
DATA = '''1|乾为天|乾|乾|刚健·创造|有担当才有进展，刚强过度则失衡|金龙穿云而上，天光开阔
2|坤为地|坤|坤|承载·顺势|适宜承接与落实，顺势不等于失去主见|广阔田野，厚土托起万物
3|水雷屯|坎|震|初生·艰难|起步有阻，先建秩序再求扩张|雷雨岩隙中长出的嫩芽
4|山水蒙|艮|坎|启蒙·求教|信息未明，先求证，忌自以为懂|山脚少年提灯问路
5|水天需|坎|乾|等待·准备|有能力而条件未齐，等待须有准备|河岸行者候云雨
6|天水讼|乾|坎|争执·分歧|立场相背，厘清边界，忌争胜到底|两岸相对的士人
7|地水师|坤|坎|纪律·统筹|成事靠组织与规则，不靠个人逞强|旌旗有序，行军越原野
8|水地比|坎|坤|亲比·结盟|选择可靠同伴，结合需要诚意和边界|水畔乡人相聚
9|风天小畜|巽|乾|积蓄·小制|积累尚小，能约束而未能大举推进|梯田上风聚薄云，雨尚未落
10|天泽履|乾|兑|谨慎·分寸|接近强势条件时，守礼守界而行|旅人谨慎行于虎侧
11|地天泰|坤|乾|交通·和合|上下能交流，顺境仍需维护秩序|天地相交，桥通两岸
12|天地否|乾|坤|隔绝·闭塞|上下不交，渠道闭塞，先守边界|崖壁阻路，远天高悬
13|天火同人|乾|离|同道·共识|合作靠公开共同目标，不是小圈子|旷野中同道相会
14|火天大有|离|乾|丰盛·统领|资源充足，更考验分配和克制|日光下铜器盛满收获
15|地山谦|坤|艮|谦逊·有实|有实力而不张扬，进退留余地|低矮山脉藏于厚土平原
16|雷地豫|震|坤|振奋·动员|顺势动员可行，忌兴奋替代准备|春雷下乡人鼓乐
17|泽雷随|兑|震|顺随·选择|随势须辨方向，不是盲从|沿河循灯而行的旅队
18|山风蛊|艮|巽|整治·更新|积弊需要清理，修复须追根源|匠人修复古老祠堂
19|地泽临|坤|兑|临近·照应|机会接近，要落实责任，也防盛势转退|泽畔来访的长者
20|风地观|巽|坤|观察·审视|先观察整体与自身位置，忌急于定论|高台观照田野
21|火雷噬嗑|离|震|破障·明断|处理真实障碍，判断与执行缺一不可|雷光下铜刃断结
22|山火贲|艮|离|文饰·质地|外观可润色，不能替代内在实力|山下精雅亭阁映火光
23|山地剥|艮|坤|剥落·守根|外层支持消退，宜护根本而非强进|古屋外墙剥落，老人加固基脚
24|地雷复|坤|震|回转·复始|微小转机初生，恢复需要节奏|冬尽一芽，归途初现
25|天雷无妄|乾|震|真实·自然|按事实行事，忌侥幸和额外妄求|旷野白鹤立于晴雷之下
26|山天大畜|艮|乾|蓄势·涵养|能力须积蓄和约束，准备好再出山|山门内骏马蓄力，书卷积学
27|山雷颐|艮|震|养正·取舍|辨别输入与供养，言语和资源都需节制|山下双手捧粮
28|泽风大过|兑|巽|重压·失衡|负荷超过结构承受，应先减压或加固|湖上屋梁承重弯曲
29|坎为水|坎|坎|险中·守信|风险反复，守住可控步骤，不以冒进破险|层层深峡与急流
30|离为火|离|离|明辨·依附|光明依托合适基础，辨清所依之物|双灯照亮案上书卷
31|泽山咸|兑|艮|感应·相悦|有相互感应，但感应不等于稳定承诺|湖中山影，双鹤相近
32|雷风恒|震|巽|恒久·守常|长久靠可持续节奏，不是固执不变|风雷中的老松
33|天山遁|乾|艮|退守·避锋|适时退出保留余地，不与不利形势硬碰|高山远路，行者隐退
34|雷天大壮|震|乾|强势·守正|力量增长，更需守界，忌蛮力越线|雷下公羊停在篱前
35|火地晋|离|坤|进展·显明|有显现和被看见的条件，宜稳步推进|日出照亮通往亭阁的阶梯
36|地火明夷|坤|离|藏明·自护|环境不利表达，先护核心，勿逞明|暗谷中衣袖护灯
37|风火家人|巽|离|内治·分工|关系和组织先理清内部责任与规则|暖院一家围炉各司其事
38|火泽睽|离|兑|相异·求同|方向不同，宜找小共识，不能假装一致|两人各望不同远方
39|水山蹇|坎|艮|阻途·求援|前路受阻，换路线或求助比硬走有效|行者面对山间洪水
40|雷水解|震|坎|松绑·释放|障碍出现松动，及时处理余结|雨霁云开，绳结渐松
41|山泽损|艮|兑|减省·取舍|减去非必要负担，取舍须看代价|湖畔放下多余器物
42|风雷益|巽|震|增益·施行|资源流向能成事之处，增长需要行动|清水滋养新林与田畦
43|泽天夬|兑|乾|决断·公开|需要清楚决断，同时防急躁与孤立|明河决开旧堤
44|天风姤|乾|巽|相遇·警觉|突然而来的影响，先辨性质再接纳|风中树下不期而遇
45|泽地萃|兑|坤|聚集·中心|人和资源汇聚，须有共同中心与秩序|舟船会于水畔古庙
46|地风升|坤|巽|向上·累进|借基础和扶持逐步上升，不主一步登顶|新树破土，石阶渐高
47|泽水困|兑|坎|受困·守志|可用资源不足，先保基本行动能力|枯井旁旅人歇于疏苇
48|水风井|坎|巽|根源·供养|关注可持续的资源系统，井好也须能取水|古井汲清水供乡人
49|泽火革|兑|离|变革·时机|改变需条件和信任成熟，不能只换表面|秋光下褪旧袍换新衣
50|火风鼎|离|巽|承新·成器|资源经组织转化才成价值，重在承载结构|青铜鼎中火稳气升
51|震为雷|震|震|惊动·觉醒|突发变化先稳住，再回应，不把惊吓当结论|雷起林摇，行者回神
52|艮为山|艮|艮|止息·边界|知道何时停止，停在该停的位置|双山之间静坐之人
53|风山渐|巽|艮|渐进·循序|进展需要阶段和秩序，不能跳过过程|鸿雁循岸渐登山坡
54|雷泽归妹|震|兑|位置·不正|关系或安排不对等，先认清位置和自主权|偏门外停着待行婚轿
55|雷火丰|震|离|盛大·转折|盛时要处理关键事务，也须意识到难久持|灯节粮仓，日中有食
56|火山旅|离|艮|暂居·适应|处于客位，守分寸、留退路、谨慎结交|山驿中的轻装旅人
57|巽为风|巽|巽|入微·柔进|靠持续渗透和清楚表达，不靠一击强压|风入竹林与窗扉
58|兑为泽|兑|兑|交流·悦纳|交流促进相合，忌为讨好牺牲原则|双湖畔友人共茶
59|风水涣|巽|坎|疏散·重聚|散开阻滞后需重建连接与中心|风散河雾，舟重新出行
60|水泽节|坎|兑|尺度·约束|明确限制能保长久，过度限制反成阻碍|竹间石渠分水有度
61|风泽中孚|巽|兑|诚信·内实|信任依赖内外一致与可验证行动|静湖双鹤，倒影清晰
62|雷山小过|震|艮|小行·谨慎|适合小步修正，不宜放大目标冒进|小鸟低飞于山云之下
63|水火既济|坎|离|已成·维护|阶段完成后更需维护，防松懈生乱|舟已渡岸，炉火有节
64|火水未济|离|坎|未成·续行|接近完成仍缺关键一步，忌提前当作定局|小狐湿尾立于河岸，彼岸尚远'''
HEXAGRAMS=[]
IMAGE_SYMBOLS=['天行健', '地势坤', '云雷', '山下出泉', '云上于天', '天与水违行', '地中有水', '地上有水', '风行天上', '上天下泽', '天地交', '天地不交', '天与火', '火在天上', '地中有山', '雷出地奋', '泽中有雷', '山下有风', '泽上有地', '风行地上', '雷电', '山下有火', '山附于地', '雷在地中', '天下雷行', '天在山中', '山下有雷', '泽灭木', '水洊至', '明两作', '山上有泽', '雷风', '天下有山', '雷在天上', '明出地上', '明入地中', '风自火出', '上火下泽', '山上有水', '雷雨作', '山下有泽', '风雷', '泽上于天', '天下有风', '泽上于地', '地中生木', '泽无水', '木上有水', '泽中有火', '木上有火', '洊雷', '兼山', '山上有木', '泽上有雷', '雷电皆至', '山上有火', '随风', '丽泽', '风行水上', '泽上有水', '泽上有风', '山上有雷', '水在火上', '火在水上']
IMAGE_NOTES={15: '取“地中有山”：把山的力量藏在厚土之中，表示有实而不自高，不是软弱退缩。', 17: '原典取“泽中有雷”。暮色归行借喻顺时休息；随是择善而从，不是盲从领头人。', 19: '原典取“泽上有地”。泽畔照应借喻临近与承担教养责任，不表示高位者天然正确，也不保证机会长留。', 23: '取“山附于地”与厚下安宅。墙皮剥落、加固基脚表示支持渐弱而护本，不表示一定遭遇灾难。', 24: '原典取“雷在地中”。冬尽萌芽是生机初回的借喻，不表示某个人一定回头。', 26: '取“天在山中”：骏马蓄力、书卷积学表示涵养与自制。畜读 xù，是蓄养，不能读成牲畜的 chù。', 30: '取“明两作”。双灯表示光明相继，也须有所依附；不是财富或喜庆的预告。', 43: '决开的水口借喻决断与疏通。应清楚公开地处理问题，不能把夬读成暴力摧毁。', 54: '婚轿借喻角色与安排的不对等，不能凭此判断婚姻失败或给女性定性。', 63: '舟渡岸、火煮水借喻阶段完成且仍须防患，不是所有事情永远顺利。', 64: '小狐尚在渡水借喻关键一步未完，不是注定失败。'}
BY_BITS={}
for row in DATA.splitlines():
 n,name,upper,lower,theme,meaning,motif=row.split('|')
 n=int(n); bits=TRIGRAMS[lower][0]+TRIGRAMS[upper][0]
 h=dict(number=n,name=name,upper=upper,lower=lower,bits=bits,theme=theme,meaning=meaning,motif=motif,
        symbol=chr(0x4dc0+n-1),atlas=(n-1)//16,cell=(n-1)%16)
 HEXAGRAMS.append(h); BY_BITS[bits]=h
assert len(BY_BITS)==64

for h in HEXAGRAMS:
 h['classical_image']=IMAGE_SYMBOLS[h['number']-1]
 h['art_note']=IMAGE_NOTES.get(h['number'],'画面借助人物与景物表达卦义；这是现代叙事取象，并非每件画中物都对应原典。')

from english_hexagrams import attach
attach(HEXAGRAMS)

NAJIA={
 '乾':('甲','壬','子寅辰午申戌'),'坤':('乙','癸','未巳卯丑亥酉'),
 '震':('庚','庚','子寅辰午申戌'),'巽':('辛','辛','丑亥酉未巳卯'),
 '坎':('戊','戊','寅辰午申戌子'),'离':('己','己','卯丑亥酉未巳'),
 '艮':('丙','丙','辰午申戌子寅'),'兑':('丁','丁','巳卯丑亥酉未')}
ELEMENTS=dict(zip('子丑寅卯辰巳午未申酉戌亥','水土木木土火火土金金土水'))
GENERATES={'木':'火','火':'土','土':'金','金':'水','水':'木'}
CONTROLS={'木':'土','土':'水','水':'火','火':'金','金':'木'}
PALACES={}
for palace,(trigram,element,_) in TRIGRAMS.items():
 base=trigram*2
 for i,mask in enumerate((0,1,3,7,15,31,23,16)):
  bits=''.join(str(int(b)^((mask>>j)&1)) for j,b in enumerate(base))
  shi=(6,1,2,3,4,5,4,3)[i]
  PALACES[bits]={'name':palace,'element':element,'shi':shi,'ying':((shi+2)%6)+1,
    'stage':('本宫','一世','二世','三世','四世','五世','游魂','归魂')[i]}
assert len(PALACES)==64

def kin(element,palace):
 if element==palace:return '兄弟'
 if GENERATES[palace]==element:return '子孙'
 if GENERATES[element]==palace:return '父母'
 if CONTROLS[palace]==element:return '妻财'
 return '官鬼'

def assemble(bits,palace_element):
 h=BY_BITS[bits]; rows=[]
 for i,b in enumerate(bits):
  trig=h['lower'] if i<3 else h['upper']; inner,outer,branches=NAJIA[trig]
  branch=branches[i]; element=ELEMENTS[branch]
  rows.append(dict(position=i+1,yang=int(b),stem=inner if i<3 else outer,branch=branch,
    element=element,kin=kin(element,palace_element)))
 return rows

def build_cast(words,local_dt=None,tz='Asia/Shanghai'):
 if len(words)!=6 or any(str(w) not in ('0','1','2','3') for w in words):raise ValueError('必须提供六次有效硬币结果。')
 # Convention matches original site: counted number face has value 2, reverse has value 3.
 values=[9-int(w) for w in words]
 bits=''.join(str(v%2) for v in values)
 changed_bits=''.join(str(1-int(b)) if v in (6,9) else b for b,v in zip(bits,values))
 main=BY_BITS[bits]; changed=BY_BITS[changed_bits]; palace=PALACES[bits]
 moving=[i+1 for i,v in enumerate(values) if v in (6,9)]
 rows=assemble(bits,palace['element']); changed_rows=assemble(changed_bits,palace['element'])
 base_rows=assemble(TRIGRAMS[palace['name']][0]*2,palace['element'])
 missing=set(r['kin'] for r in base_rows)-set(r['kin'] for r in rows)
 calendar=None
 if local_dt:
  z=ZoneInfo(tz)
  zoned=local_dt.replace(tzinfo=z)
  if zoned.astimezone(timezone.utc).astimezone(z).replace(tzinfo=None)!=local_dt:
   raise ValueError('该当地时间处于夏令时跳时区间，请选择有效时间。')
  if zoned.utcoffset()!=local_dt.replace(tzinfo=z,fold=1).utcoffset():
   raise ValueError('该当地时间存在夏令时歧义，请避开重复时段。')
  dt=zoned.astimezone(ZoneInfo('Asia/Shanghai'))
  l=Solar.fromYmdHms(dt.year,dt.month,dt.day,dt.hour,dt.minute,0).getLunar()
  calendar={'month':l.getMonthInGanZhiExact(),'day':l.getDayInGanZhiExact2(),
    'xunkong':l.getDayXunKongExact2(),'beijing_time':dt.strftime('%Y-%m-%d %H:%M'),
    'convention':'北京时间、节气定月、零点换日；不校正真太阳时'}
  start={'甲':0,'乙':0,'丙':1,'丁':1,'戊':2,'己':3,'庚':4,'辛':4,'壬':5,'癸':5}[calendar['day'][0]]
  gods=('青龙','朱雀','勾陈','螣蛇','白虎','玄武')
 for i,row in enumerate(rows):
  row.update(value=values[i],moving=i+1 in moving,
    label='世' if i+1==palace['shi'] else ('应' if i+1==palace['ying'] else ''),
    changed=changed_rows[i] if i+1 in moving else None,
    hidden=base_rows[i] if base_rows[i]['kin'] in missing else None,
    god=gods[(start+i)%6] if calendar else '',
    empty=row['branch'] in calendar['xunkong'] if calendar else False)
 return dict(main=main,changed=changed,moving=moving,rows=rows,palace=palace,calendar=calendar,words=list(map(str,words)),values=values)
