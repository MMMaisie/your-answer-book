import json
from datetime import datetime
import pytest
import simple_reading as e
from reading_contract import validate_grounded_copy,ContentValidationError
from hexagrams import build_cast
from conftest import Model,initial,review,full

QUESTIONS=[
 ('房屋','这套房适合买吗？'),('房屋','买这套房能顺利成交吗？'),('房屋','现在买还是再等等？'),
 ('婚恋','我什么时候找到对象？'),('婚恋','我能结婚吗？'),('婚恋','我和他有发展吗？'),('婚恋','女，和她能复合吗？'),
 ('求职','我能拿到offer吗？'),('求职','这次面试有戏吗？'),('求职','什么时候能找到工作？'),
 ('求财','欠款能收回来吗？'),('求财','这笔生意有利润吗？'),('求财','该继续投入还是退出？'),
 ('诉讼','我这个官司能打赢吗？'),('诉讼','纠纷能协商解决吗？'),
 ('健康','身体什么时候能好一点？'),('健康','我是不是得了什么病？'),
 ('失物','钥匙还能找到吗？'),('失物','东西在家里还是外面？'),
 ('宠物','走失的鹦鹉能回来吗？'),('宠物','鸟最近不精神怎么办？'),
 ('文书','签证能批下来吗？'),('文书','合同能签成吗？'),
 ('学业','这次考试能通过吗？'),('学业','申请学校能录取吗？'),
 ('出行','这次旅行能顺利吗？'),('出行','要不要改期出发？'),
 ('人际','合作还能继续吗？'),('人际','朋友会主动联系我吗？'),
 ('选择','留下还是换个城市？'),('模糊','这件事怎么样？'),('模糊','什么时候能成？'),
]
CASTS=[
 build_cast([1,1,2,1,0,0],datetime(2026,11,22,9,51)),
 build_cast([2]*6,datetime(2026,11,22,9,51)),
 build_cast([0,3,2,1,0,3],datetime(2026,11,22,9,51)),
]

@pytest.mark.parametrize('topic,question',QUESTIONS)
@pytest.mark.parametrize('cast',CASTS,ids=['house-regression','static','many-moving'])
def test_multitopic_pipeline_passes_question_and_full_review_focus(topic,question,cast):
 # Scripted provider: verifies wiring/contracts, NOT model judgement quality.
 m=Model([initial(cast),review(cast=cast),full()])
 core=e.generate(m,question,cast,'deepseek-v4-pro')
 plan=e.review_paid(m,question,cast,'deepseek-v4-pro',core['bundle'])
 result=e.generate_paid(m,question,cast,'deepseek-v4-pro',core['bundle'],reviewed_plan=plan)
 assert result==full()['paid']
 prompt=json.loads(m.calls[1]['messages'][1]['content'])
 assert prompt['reference']['question']==question
 assert prompt['reference']['review_focus']['moving_positions']==cast['moving']
 assert prompt['reference']['review_focus']['shi']==cast['palace']['shi']
 assert prompt['reference']['review_focus']['ying']==cast['palace']['ying']
 assert e.ACCURACY in m.calls[0]['messages'][0]['content']
 assert e.ACCURACY in m.calls[1]['messages'][0]['content']
 assert len(m.calls)==3

@pytest.mark.parametrize('text',[
 '显示房屋本身或交易条件存在明显隐患。',
 '房屋状况或交易条件有明显问题，不建议入手。',
 '说明对方存在隐性债务。',
 '他已经出轨。','你肯定患有严重疾病。',
])
def test_unsupported_realworld_assertions_rejected(text):
 with pytest.raises(ContentValidationError,match='unverified_realworld'):validate_grounded_copy(text)

@pytest.mark.parametrize('text',[
 '卦象不能证明房屋存在严重隐患。',
 '应核实房屋是否存在产权纠纷。',
 '若检查发现结构缺陷，应先解决再决定。',
 '父母爻受制，传统解释倾向于谨慎推进。',
 '目前不宜仓促推进，先确认交易条件。',
])
def test_bounded_interpretations_and_checks_allowed(text):assert validate_grounded_copy(text)==text

def test_house_cast_key_facts_are_stable():
 c=CASTS[0]
 assert (c['main']['name'],c['changed']['name'])==('风山渐','地山谦')
 assert c['moving']==[5,6]
 assert c['palace']['shi']==3 and c['palace']['ying']==6
 rows={r['position']:r for r in c['rows']}
 assert (rows[5]['kin'],rows[5]['branch'],rows[5]['changed']['branch'])==('父母','巳','亥')
 assert (rows[6]['kin'],rows[6]['branch'],rows[6]['changed']['branch'])==('官鬼','卯','酉')
 assert rows[2]['branch']=='午'
