import itertools,json,sqlite3,sys
from datetime import datetime
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app as site
from hexagrams import build_cast,BY_BITS,PALACES,HEXAGRAMS

@pytest.fixture
def client(tmp_path,monkeypatch):
 site.app.config.update(TESTING=True,DB_PATH=str(tmp_path/'readings.db'),SESSION_COOKIE_SECURE=False)
 site.init_db()
 monkeypatch.setattr(site,'call_ai',lambda q,c,l,t,free='': '【初判】'+('免费证据测试。'*12) if t=='free' else '【盘面】PRIVATE_FULL_SENTINEL <script>alert(1)</script>')
 return site.app.test_client()

def csrf(c):
 c.get('/')
 with c.session_transaction() as s:return s['csrf']

def submit(c,question='未来三个月换工作是否合适？',words=None):
 values=words or ['2','1','2','1','2','1']
 return c.post('/',data=dict(csrf=csrf(c),question=question,cast_time='2026-10-04T16:00',timezone='Asia/Shanghai',**{f'word{i+1}':w for i,w in enumerate(values)}))

def row_for(c):
 with site.connect() as db:return db.execute('SELECT * FROM readings').fetchone()

def mark(r):
 with site.connect() as db:db.execute("INSERT INTO payments(seed_key,status) VALUES(?,'paid')",(r['seed_key'],))

@pytest.mark.parametrize('url',['/','/deck','/deck/1','/deck/64','/demo','/history','/policy','/healthz'])
def test_public_pages(client,url):assert client.get(url).status_code==200

def test_all_4096_casts():
 seen=set()
 for w in itertools.product(range(4),repeat=6):
  c=build_cast(w);bits=''.join(str((9-x)%2) for x in w);seen.add(c['main']['number'])
  assert c['main']['bits']==bits
  assert len(c['rows'])==6
  assert c['palace']['shi']!=c['palace']['ying']
  for i,r in enumerate(c['rows']):assert r['moving']==(w[i] in (0,3))
  assert c['changed']['bits']==''.join(str(1-int(b)) if x in (0,3) else b for b,x in zip(bits,w))
 assert seen==set(range(1,65))

def test_known_qian_palace():
 qian=['111111','011111','001111','000111','000011','000001','000101','111101']
 expected=[1,44,33,12,20,23,35,14]
 assert [BY_BITS[x]['number'] for x in qian]==expected
 assert [PALACES[x]['shi'] for x in qian]==[6,1,2,3,4,5,4,3]
 c=build_cast([2]*6,datetime(2026,10,4,16));assert c['calendar']['day']=='辛亥'
 assert [r['stem']+r['branch'] for r in c['rows']]==['甲子','甲寅','甲辰','壬午','壬申','壬戌']
 assert [r['god'] for r in c['rows']]==['白虎','玄武','青龙','朱雀','勾陈','螣蛇']
 assert c['moving']==[]

@pytest.mark.parametrize('w',[[],[4]*6,['x']*6,[1]*5])
def test_reject_bad_cast(w):
 with pytest.raises(ValueError):build_cast(w)

def test_timezones_and_boundary():
 # Adelaide starts daylight saving on this date: local 18:30 equals Beijing 16:00.
 a=build_cast([2]*6,datetime(2026,10,4,18,30),'Australia/Adelaide')
 b=build_cast([2]*6,datetime(2026,10,4,16,0),'Asia/Shanghai')
 assert a['calendar']==b['calendar']
 before=build_cast([2]*6,datetime(2026,10,4,23,30))
 after=build_cast([2]*6,datetime(2026,10,5,0,30))
 assert before['calendar']['day']!=after['calendar']['day']
 with pytest.raises(ValueError):build_cast([2]*6,datetime(2026,10,4,2,30),'Australia/Adelaide')


def test_free_only_and_cached(client,monkeypatch):
 calls=[]
 def ai(*args):calls.append(args[3]);return '免费有据初判。'*15
 monkeypatch.setattr(site,'call_ai',ai)
 response=submit(client);assert response.status_code==302
 r=row_for(client);assert r['paid_text']=='';assert calls==['free']
 assert client.get(response.location).status_code==200
 second=submit(client);assert second.location==response.location;assert calls==['free']
 with site.connect() as db:assert db.execute("SELECT count FROM usage WHERE bucket='global'").fetchone()['count']==1


def test_paid_not_in_unpaid_html(client):
 response=submit(client);r=row_for(client)
 with site.connect() as db:db.execute('UPDATE readings SET paid_text=?,paid_version=? WHERE seed_key=?',('PRIVATE_FULL_SENTINEL',site.PROMPT_VERSION,r['seed_key']))
 html=client.get(response.location).data;assert b'PRIVATE_FULL_SENTINEL' not in html
 assert client.post(response.location+'/full',data={'csrf':csrf(client)}).status_code==403
 mark(r);assert b'PRIVATE_FULL_SENTINEL' in client.get(response.location).data


def test_paid_generated_once_and_escaped(client,monkeypatch):
 response=submit(client);r=row_for(client);mark(r)
 calls=[]
 def ai(*args):calls.append(args[3]);return 'PRIVATE_FULL_SENTINEL <script>alert(1)</script>'
 monkeypatch.setattr(site,'call_ai',ai)
 assert b'PRIVATE_FULL_SENTINEL' not in client.get(response.location).data;assert calls==[]
 for _ in range(2):assert client.post(response.location+'/full',data={'csrf':csrf(client)}).status_code==302
 assert calls==['paid']
 html=client.get(response.location).data
 assert b'&lt;script&gt;alert(1)&lt;/script&gt;' in html
 assert b'<script>alert(1)</script>' not in html


def test_private_random_links_and_public_share(client):
 response=submit(client,question='MY_PRIVATE_QUESTION_123');r=row_for(client)
 assert client.get('/reading/'+r['seed_key']).status_code==302 # own browser
 other=site.app.test_client();assert other.get('/reading/'+r['seed_key']).status_code==404
 assert other.get('/r/not-real').status_code==404
 shared=client.post(response.location+'/share',data={'csrf':csrf(client)})
 html=other.get(shared.location).data
 assert b'MY_PRIVATE_QUESTION_123' not in html
 assert r['access_key'].encode() not in html
 assert b'PRIVATE_FULL_SENTINEL' not in html
 client.post(response.location+'/unshare',data={'csrf':csrf(client)})
 assert other.get(shared.location).status_code==404
 assert client.get(response.location).headers['Cache-Control']=='private, no-store'


def test_csrf(client):assert client.post('/',data={'question':'test'}).status_code==400

def test_validation_before_ai(client,monkeypatch):
 def no_ai(*a):raise AssertionError('Invalid input called AI')
 monkeypatch.setattr(site,'call_ai',no_ai)
 assert submit(client,words=['4']*6).status_code==200
 with site.connect() as db:assert db.execute('SELECT count(*) FROM usage').fetchone()[0]==0


def test_quota(client,monkeypatch):
 monkeypatch.setenv('FREE_DAILY_LIMIT','1')
 assert submit(client,'第一个不同问题，是否适合？').status_code==302
 result=submit(client,'第二个不同问题，是否适合？');assert result.status_code==200
 assert '今日解读次数已用完'.encode() in result.data


def test_ai_failure_is_not_template(client,monkeypatch):
 def fail(*a):raise site.ReadingError('本次解读未能完成，未生成模板答案。')
 monkeypatch.setattr(site,'call_ai',fail)
 response=submit(client);assert response.status_code==200
 assert '未生成模板答案'.encode() in response.data
 with site.connect() as db:assert db.execute('SELECT count(*) FROM readings').fetchone()[0]==0


def test_fulfillment_paid_binding_and_replay(client,monkeypatch):
 submit(client);r=row_for(client);monkeypatch.setattr(site,'PRICE_ID','price_test')
 with site.connect() as db:db.execute('INSERT INTO orders VALUES(?,?,?,?)',('cs_test_valid',r['seed_key'],'price_test','now'))
 d={'id':'cs_test_valid','metadata':{'seed_key':r['seed_key']},'payment_status':'unpaid','amount_total':199,'currency':'aud'}
 assert not site.fulfill(d);assert not site.paid(r['seed_key'])
 d['payment_status']='paid';assert not site.fulfill(d,'wrong-seed')
 assert site.fulfill(d);assert site.fulfill(d)
 with site.connect() as db:assert db.execute('SELECT count(*) FROM payments').fetchone()[0]==1
 d['id']='cs_foreign';assert not site.fulfill(d)


def test_webhook_async_and_bad_signature(client,monkeypatch):
 submit(client);r=row_for(client);monkeypatch.setenv('STRIPE_WEBHOOK_SECRET','whsec_test');monkeypatch.setattr(site,'PRICE_ID','price_test')
 with site.connect() as db:db.execute('INSERT INTO orders VALUES(?,?,?,?)',('cs_test_async',r['seed_key'],'price_test','now'))
 def event(*args):return {'type':'checkout.session.async_payment_succeeded','data':{'object':{'id':'cs_test_async','metadata':{'seed_key':r['seed_key']},'payment_status':'paid'}}}
 monkeypatch.setattr(site.stripe.Webhook,'construct_event',event)
 assert client.post('/stripe/webhook',data=b'{}').status_code==200;assert site.paid(r['seed_key'])
 def bad(*a):raise ValueError('invalid signature')
 monkeypatch.setattr(site.stripe.Webhook,'construct_event',bad)
 assert client.post('/stripe/webhook',data=b'{}').status_code==400


def test_prompt_quality(client):
 c=build_cast([2]*6,datetime(2026,10,4,16))
 p=site.reading_prompt('三个月内有offer吗',c,'zh','free')
 assert '至少引用两条' in p and '不能保证' in p and '不留故意的悬念' in p
 assert '乾为天' in p and '世' in p and '辛亥' in p
 assert 'Emotion level:' not in p


def test_migration_keeps_existing_data(client,tmp_path):
 old=tmp_path/'old.db'
 with sqlite3.connect(old) as db:
  db.execute('CREATE TABLE readings(seed_key TEXT PRIMARY KEY,lang TEXT,question TEXT,cast_time TEXT,words TEXT,topic TEXT,emotion_level TEXT,free_text TEXT,paid_text TEXT,created_at TEXT)')
  db.execute("INSERT INTO readings VALUES('legacy','zh','旧问题','2026/10/04 16:00','2,1,2,1,2,1','','','旧初判','旧完整','now')")
 site.app.config['DB_PATH']=str(old);site.init_db()
 with site.connect() as db:r=db.execute('SELECT * FROM readings').fetchone()
 assert r['question']=='旧问题' and r['paid_text']=='旧完整' and len(r['access_key'])>=30
 assert r['paid_version'] is None

def test_moving_lines_in_one_expandable_plate(client):
 response=submit(client,words=['0','1','2','3','2','1'])
 html=client.get(response.location).data.decode()
 assert '六爻卦盘 · 看动处' in html
 assert html.count('<table>')==1
 assert 'data-plate-toggle' in html
 assert '第 1、4 爻发动' in html
 assert '阳 → 阴' in html and '阴 → 阳' in html
 assert html.count('moving-row is-moving')==2
 cast=build_cast([0,1,2,3,2,1])
 assert cast['rows'][0]['changed']['yang']==0
 assert cast['rows'][3]['changed']['yang']==1

def test_deck_art_data_matches_server(client):
 data=json.loads(client.get('/static/deck.json').data)
 assert data==HEXAGRAMS
 assert all(h['classical_image'] and h['art_note'] for h in data)
 assert 'I CHING' not in client.get('/').data.decode()
 assert 'id="card-dialog"' in client.get('/deck').data.decode()


def test_location_labels_and_chart_conversion(client):
 html=client.get('/').data.decode()
 assert '澳大利亚 · 阿德莱德' in html and '澳大利亚 · 悉尼' in html
 assert '当地起卦时间' in html and 'UTC+8' in html
 # Winter and summer offsets come from IANA rules, not fixed city offsets.
 winter=build_cast([2]*6,datetime(2026,7,1,18,30),'Australia/Adelaide')
 summer=build_cast([2]*6,datetime(2026,12,1,18,30),'Australia/Adelaide')
 assert winter['calendar']['beijing_time']=='2026-07-01 17:00'
 assert summer['calendar']['beijing_time']=='2026-12-01 16:00'
 sydney=build_cast([2]*6,datetime(2026,12,1,18,30),'Australia/Sydney')
 assert sydney['calendar']['beijing_time']=='2026-12-01 15:30'

@pytest.mark.parametrize('route',['/','/deck','/deck/1','/deck/15','/deck/26','/deck/64','/demo','/history','/policy','/no-such-page'])
def test_english_ui_has_no_untranslated_text(client,route):
 from html.parser import HTMLParser
 import re
 class Visible(HTMLParser):
  def __init__(self):super().__init__();self.chinese=[]
  def handle_data(self,text):
   if re.search('[\u4e00-\u9fff]',text) and text.strip() not in ('易','中文'):self.chinese.append(text.strip())
 parser=Visible();parser.feed(client.get(route+'?lang=en').data.decode())
 assert parser.chinese==[]

def test_language_switch_translates_without_new_cast_or_charge(client,monkeypatch):
 response=submit(client);r=row_for(client);calls=[]
 def translate(text,lang,tier):calls.append((lang,tier));return '【Initial reading】English translation with preserved evidence. '*5
 monkeypatch.setattr(site,'call_translation',translate)
 page=client.get(response.location+'?lang=en')
 assert b'Translate initial reading to English' in page.data and calls==[]
 for _ in range(2):assert client.post(response.location+'/language?lang=en',data={'csrf':csrf(client)}).status_code==302
 assert calls==[('en','free')]
 assert b'English translation' in client.get(response.location+'?lang=en').data
 with site.connect() as db:assert db.execute('SELECT COUNT(*) FROM readings').fetchone()[0]==1
 assert row_for(client)['free_text']==r['free_text']
 assert client.post(response.location+'/full?lang=en',data={'csrf':csrf(client)}).status_code==403

def test_paid_language_cache_and_original_are_preserved(client,monkeypatch):
 response=submit(client);r=row_for(client);mark(r)
 client.post(response.location+'/full',data={'csrf':csrf(client)})
 original=row_for(client)['paid_text'];calls=[]
 def translate(text,lang,tier):calls.append((text,lang,tier));return '【Chart and priorities】Translated full reading. '*5
 monkeypatch.setattr(site,'call_translation',translate)
 for _ in range(2):assert client.post(response.location+'/full?lang=en',data={'csrf':csrf(client)}).status_code==302
 assert len(calls)==1 and calls[0]==(original,'en','paid')
 assert row_for(client)['paid_text']==original
 assert b'Translated full reading' in client.get(response.location+'?lang=en').data
 with site.connect() as db:assert db.execute('SELECT COUNT(*) FROM payments').fetchone()[0]==1

def test_english_ai_prompt_uses_english_section_headings(client):
 from hexagrams import build_cast
 free=site.reading_prompt('Should I change jobs?',build_cast([0,1,2,3,2,1]),'en','free')
 full=site.reading_prompt('Should I change jobs?',build_cast([0,1,2,3,2,1]),'en','paid')
 assert '【Initial reading】' in free and '【初判】' not in free
 assert '【Chart and priorities】' in full and '【盘面与主次】' not in full
