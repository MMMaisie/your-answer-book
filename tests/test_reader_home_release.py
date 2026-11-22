import json
import pytest
import simple_reading as e
from intent_reference import intent_hints
from hexagrams import build_cast
from conftest import initial,review,full,Model
CAST=build_cast([2]*6)

@pytest.mark.parametrize('lang,expected',[('zh','心有所问，可以从这里开始'),('en','A place to begin your question')])
def test_home_topic_copy(client,lang,expected):
 text=client.get('/?lang='+lang).text
 assert expected in text
 assert text.count('<li>')>=9
 assert '这两类还没有完成真实模型验收' not in text
 assert 'Health & childbirth' not in text

@pytest.mark.parametrize('q,key',[
 ('这套房现在适合买入吗','home_suitability'),('这套房能成交吗','home_transaction'),
 ('现在卖房好吗','home_transaction'),('租房能租到吗','home_rent'),('修造能顺利吗','home_build'),
 ('生产能顺利吗','health_birth'),('这批产品生产能顺利吗','health_birth'),
 ('考试能通过吗','study'),('丢失钥匙还能找回吗','lost')])
def test_scope_hints_describe_question_without_forced_verdict(q,key):
 hints=intent_hints(q);assert key in {x['id'] for x in hints}
 assert all('outlook' not in x and 'yongshen' not in x for x in hints)

def test_free_key_point_and_plain_paid_request_contract():
 m=Model([initial(),review(),full()])
 result=e.generate(m,'这套房适合买入吗',CAST,'deepseek-v4-pro')
 plan=e.review_paid(m,'这套房适合买入吗',CAST,'deepseek-v4-pro',result['bundle'])
 e.generate_paid(m,'这套房适合买入吗',CAST,'deepseek-v4-pro',result['bundle'],reviewed_plan=plan)
 initial_task=json.loads(m.calls[0]['messages'][1]['content'])
 assert '判断＋一个关键点' in initial_task['schema']['free']['direction']
 assert initial_task['reference']['question_scope_hints']
 assert '通常只用一处专业依据' in m.calls[2]['messages'][0]['content']
 assert '初判只给' not in m.calls[0]['messages'][0]['content']
