import copy,hashlib,hmac,json,time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace as NS
import pytest
import app as site
from conftest import Model,initial,full,submit,csrf
from protection import Protection,Limited,QuotaUsed,BudgetExceeded,bounded_client
from storage import Store

def row(c):
 with site.store.connect() as db:return db.execute('SELECT * FROM ab49_readings ORDER BY created DESC LIMIT 1').fetchone()
def reset_rates():
 with site.store.connect() as db:db.execute('DELETE FROM ab49_rates')
def paid(r,mode='test'):
 with site.store.connect() as db:db.execute('UPDATE ab49_readings SET paid_mode=? WHERE id=?',(mode,r['id']))
def post_generate(c,r,lang='zh',tier='paid'):
 return c.post('/r/'+r['access']+'/generate?lang='+lang,data={'csrf':csrf(c),'tier':tier,'cf-turnstile-response':'token'})

def test_guest_free_no_paid_and_gets_do_not_spend(client,model):
 response=submit(client);assert response.status_code==302;r=row(client)
 assert r['free_zh'] and not r['paid_zh'] and len(model.calls)==1
 for path in [response.location,'/history','/r/'+r['access']+'/download.pdf',response.location+'?lang=en']:
  assert client.get(path).status_code==200
 assert len(model.calls)==1
 assert client.get('/account/login').status_code==404

def test_free_allowance_then_direct_payment_does_not_call_model(client,model):
 submit(client);reset_rates();submit(client,'我跟他能不能结婚？')
 r=row(client);assert r['question']=='我跟他能不能结婚？' and r['free_zh']=='' and r['bundle_json']=='{}'
 assert len(model.calls)==1
 assert '免费额度已用完' in client.get('/r/'+r['access']).text
 assert post_generate(client,r,tier='free').status_code==302
 assert len(model.calls)==1

def test_ip_two_browser_one_across_sessions(client,model,monkeypatch):
 m=Model([initial(),initial()]);monkeypatch.setattr(site,'OpenAI',lambda **kw:m)
 submit(client);reset_rates()
 second=site.app.test_client();submit(second,'找对象');reset_rates()
 third=site.app.test_client();submit(third,'我能找到新工作吗？')
 assert row(third)['free_zh']=='' and len(m.calls)==2

def test_daily_trial_failure_releases_but_does_not_hide_spend(client,monkeypatch):
 monkeypatch.setattr(site,'OpenAI',lambda **kw:Model([RuntimeError('failure')]))
 response=submit(client);assert response.status_code==200
 with site.store.connect() as db:
  assert db.execute('SELECT COUNT(*) AS n FROM ab49_trials').fetchone()['n']==0
  assert db.execute('SELECT COUNT(*) AS n FROM ab49_calls').fetchone()['n']==1
 reset_rates();m=Model([initial()]);monkeypatch.setattr(site,'OpenAI',lambda **kw:m)
 assert submit(client).status_code==302 and len(m.calls)==1

def test_duplicate_submit_returns_original_without_spend(client,model):
 a=submit(client);b=submit(client)
 assert a.location==b.location and len(model.calls)==1

def test_unpaid_cannot_generate_paid_or_access_via_guess(client,model):
 submit(client);r=row(client)
 assert post_generate(client,r).status_code==403 and len(model.calls)==1
 assert client.get('/r/'+'a'*43).status_code==404

def test_paid_delivery_cached_after_version_change(client,model,monkeypatch):
 submit(client);r=row(client);paid(r)
 assert post_generate(client,r).status_code==302
 r=row(client);assert r['paid_zh'] and len(model.calls)==2
 monkeypatch.setattr(site,'VERSION','a-future-version')
 assert post_generate(client,r).status_code==302 and len(model.calls)==2
 assert r['paid_zh'] in client.get('/r/'+r['access']).text
 assert client.get('/r/'+r['access']+'/download.pdf').data.startswith(b'%PDF')

def test_paid_english_failure_preserves_chinese(client,monkeypatch):
 m=Model([initial(),full(),RuntimeError('translation failed')]);monkeypatch.setattr(site,'OpenAI',lambda **kw:m)
 submit(client);r=row(client);paid(r)
 post_generate(client,r,'en');r=row(client)
 assert r['paid_zh'] and not r['paid_en'] and len(m.calls)==3
 reset_rates();m.replies.append({'priorities':'There is room for progress, though the result is not yet settled.','conditions':'The opportunity depends on support continuing and obstacles easing.','actions':'Check confirmed progress and keep other options open.'})
 post_generate(client,r,'en');assert row(client)['paid_en'] and len(m.calls)==4
 task=json.loads(m.calls[-1]['messages'][1]['content']);assert task['parts']==full()['paid']

def test_paid_no_free_quota_only_generates_after_payment(client,monkeypatch):
 m=Model([initial(),initial(),full()]);monkeypatch.setattr(site,'OpenAI',lambda **kw:m)
 submit(client);reset_rates();submit(client,'找对象');r=row(client)
 assert len(m.calls)==1 and not r['free_zh'];paid(r);reset_rates();post_generate(client,r)
 assert row(client)['paid_zh'] and len(m.calls)==3 and row(client)['free_zh']==''

def test_paid_failure_keeps_entitlement_and_unlock_does_not_recharge(client,monkeypatch):
 m=Model([initial(),RuntimeError('provider')]);monkeypatch.setattr(site,'OpenAI',lambda **kw:m)
 submit(client);r=row(client);paid(r);post_generate(client,r)
 assert site.unlocked(row(client)) and not row(client)['paid_zh']
 reset_rates();m.replies.append(full());post_generate(client,r)
 assert row(client)['paid_zh']

def test_ten_day_expiry_and_cleanup_keep_order_only(client,model):
 submit(client);r=row(client)
 with site.store.connect() as db:
  db.execute('UPDATE ab49_readings SET expires=? WHERE id=?',(time.time()-1,r['id']))
  db.execute('INSERT INTO ab49_orders(nonce,reading_id,mode,amount,currency,status,created) VALUES(?,?,?,?,?,?,?)',('retained',r['id'],'test',199,'aud','paid',time.time()))
 assert client.get('/r/'+r['access']).status_code==404
 site.store.cleanup(force=True)
 with site.store.connect() as db:
  assert db.execute('SELECT COUNT(*) AS n FROM ab49_readings').fetchone()['n']==0
  assert db.execute('SELECT COUNT(*) AS n FROM ab49_orders').fetchone()['n']==1

def test_shared_db_new_process_store_retains_reading_and_quota(client,model):
 submit(client);other=Store(path=site.store.path);other.init()
 with other.connect() as db:
  assert db.execute('SELECT free_zh FROM ab49_readings').fetchone()['free_zh']
  assert db.execute("SELECT COUNT(*) AS n FROM ab49_trials WHERE status='used'").fetchone()['n']==2

def order_for(r):
 nonce='unitnonce';sid='cs_test_example'
 with site.store.connect() as db:db.execute('INSERT INTO ab49_orders VALUES(?,?,?,?,?,?,?,?,?)',(nonce,r['id'],sid,'test',199,'aud','pending',None,time.time()))
 return {'id':sid,'metadata':{'reading_id':r['id'],'order_nonce':nonce},'mode':'payment','livemode':False,'payment_status':'paid','amount_total':199,'currency':'aud','payment_intent':'pi_example'}

def test_fulfill_idempotent_and_wrong_fields_rejected(client,model):
 submit(client);r=row(client);d=order_for(r)
 for key,value in [('amount_total',99),('currency','usd'),('livemode',True),('payment_status','unpaid'),('id','cs_bad')]:
  wrong=copy.deepcopy(d);wrong[key]=value;assert not site.fulfill(wrong)
 assert not site.unlocked(row(client))
 assert site.fulfill(d);expiry=row(client)['expires'];assert site.fulfill(d)
 assert row(client)['expires']==expiry and site.unlocked(row(client)) and len(model.calls)==1

def signed_webhook(c,event,secret='whsec_unit'):
 payload=json.dumps(event,separators=(',',':'));stamp=str(int(time.time()));sig=hmac.new(secret.encode(),(stamp+'.'+payload).encode(),hashlib.sha256).hexdigest()
 return c.post('/stripe/webhook',data=payload,headers={'Content-Type':'application/json','Stripe-Signature':f't={stamp},v1={sig}'})

def test_signed_webhook_unlocks_without_browser_return_and_no_model(client,model,monkeypatch):
 monkeypatch.setenv('STRIPE_TEST_WEBHOOK_SECRET','whsec_unit')
 submit(client);r=row(client);d=order_for(r)
 event={'id':'evt_example','object':'event','type':'checkout.session.completed','livemode':False,'data':{'object':d}}
 assert signed_webhook(client,event).status_code==200 and site.unlocked(row(client))
 assert signed_webhook(client,event).status_code==200 and len(model.calls)==1
 event['data']['object']['amount_total']=1
 assert signed_webhook(client,event).status_code==503
 assert client.post('/stripe/webhook',data='{}',headers={'Stripe-Signature':'wrong'}).status_code==400

def test_refund_before_paid_blocks_out_of_order_regrant(client,model,monkeypatch):
 monkeypatch.setenv('STRIPE_TEST_WEBHOOK_SECRET','whsec_unit');submit(client);r=row(client);d=order_for(r)
 event={'id':'evt_refund','object':'event','type':'charge.refunded','livemode':False,'data':{'object':{'payment_intent':'pi_example','amount_refunded':199}}}
 assert signed_webhook(client,event).status_code==200
 assert not site.fulfill(d) and not site.unlocked(row(client))

def test_refund_after_paid_removes_download_access_to_paid_text(client,model,monkeypatch):
 monkeypatch.setenv('STRIPE_TEST_WEBHOOK_SECRET','whsec_unit');submit(client);r=row(client);d=order_for(r);assert site.fulfill(d);post_generate(client,r)
 e={'type':'charge.dispute.created','livemode':False,'data':{'object':{'payment_intent':'pi_example'}}}
 assert signed_webhook(client,e).status_code==200
 assert not site.unlocked(row(client)) and not site.fulfill(d)
 assert full()['paid']['priorities'] not in client.get('/r/'+r['access']).text

def test_checkout_no_registration_idempotency_stable(client,model,monkeypatch):
 submit(client);r=row(client);calls=[]
 class Sessions:
  def create(self,params,options):
   calls.append((params,options))
   if len(calls)==1:raise TimeoutError('ambiguous request')
   return {'id':'cs_test_created','livemode':False,'url':'https://checkout.stripe.com/c/pay/example'}
  def retrieve(self,sid):return {'id':sid,'status':'open','url':'https://checkout.stripe.com/c/pay/example'}
 monkeypatch.setattr(site,'stripe_client',NS(v1=NS(checkout=NS(sessions=Sessions()))));monkeypatch.setattr(site,'checkout_ready',lambda:True)
 data={'csrf':csrf(client),'cf-turnstile-response':'token'}
 first=client.post('/r/'+r['access']+'/checkout',data=data);assert first.status_code==302
 reset_rates();second=client.post('/r/'+r['access']+'/checkout?lang=en',data=data)
 assert second.status_code==303 and second.location.startswith('https://checkout.stripe.com/')
 assert calls[0]==calls[1] and 'payment_method_types' not in calls[0][0]
 assert len(model.calls)==1
 reset_rates();client.post('/r/'+r['access']+'/checkout',data=data);assert len(calls)==2

def test_csrf_required_and_turnstile_not_optional(client,model,monkeypatch):
 assert client.post('/',data={'question':'find work'}).status_code==400
 monkeypatch.setattr(site.protect,'verify',Protection.verify.__get__(site.protect,Protection))
 assert submit(client).status_code==200 and len(model.calls)==0

def test_paid_mode_isolated(client,model):
 submit(client);r=row(client);paid(r,'live');assert post_generate(client,r).status_code==403 and len(model.calls)==1

def test_budget_pauses_before_any_provider_call(client,monkeypatch):
 monkeypatch.setenv('AI_DAILY_BUDGET_AUD','0.000001');m=Model([initial()]);monkeypatch.setattr(site,'OpenAI',lambda **kw:m)
 response=submit(client);assert '操作过于频繁，请稍后再试。' in response.text and len(m.calls)==0

def test_global_concurrency_and_reservations_survive_store_reopen(client,monkeypatch):
 monkeypatch.setenv('AI_MAX_CONCURRENT','1')
 now=time.time();day=time.strftime('%Y-%m-%d',time.gmtime())
 with site.store.connect() as db:db.execute('INSERT INTO ab49_calls(id,day,model,status,reserve,created) VALUES(?,?,?,?,?,?)',('active',day,'deepseek-v4-pro','reserved',0.1,now))
 m=Model([initial()])
 with pytest.raises(BudgetExceeded):bounded_client(m,Store(path=site.store.path)).chat.completions.create(model='deepseek-v4-pro',messages=[],max_tokens=10)
 assert not m.calls

def test_lock_release_requires_owner_token(client):
 a=site.store.acquire('same');assert a and not site.store.acquire('same')
 site.store.release('same','wrong');assert not site.store.acquire('same')
 site.store.release('same',a);assert site.store.acquire('same')

def test_concurrent_daily_browser_claim_only_one(client):
 def claim(_):
  with site.app.test_request_context('/',environ_base={'REMOTE_ADDR':'203.0.113.6'}):
   site.session['owner']='same-browser'
   try:return site.protect.reserve_trial()
   except QuotaUsed:return None
 with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(claim,range(8)))
 assert sum(bool(x) for x in results)==1

def test_rate_cooldown_is_fixed_and_not_extended_by_bot(client,model):
 submit(client);assert '操作过于频繁' in submit(client,'另一个问题').text
 with site.store.connect() as db:before=db.execute('SELECT MAX(blocked_until) AS b FROM ab49_rates').fetchone()['b']
 submit(client,'第三个问题')
 with site.store.connect() as db:after=db.execute('SELECT MAX(blocked_until) AS b FROM ab49_rates').fetchone()['b']
 assert before==after and len(model.calls)==1

def test_no_raw_ip_no_model_key_in_html(client,model):
 submit(client);r=row(client);html=client.get('/r/'+r['access']).text
 assert 'not-a-real-key' not in html and '203.0.113.10' not in html
 with site.store.connect() as db:subjects=[x['subject'] for x in db.execute('SELECT subject FROM ab49_trials').fetchall()]
 assert all('203.0.113.10' not in s for s in subjects)

def test_checkout_does_not_start_when_remaining_budget_cannot_cover_delivery(client,model,monkeypatch):
 submit(client);r=row(client)
 monkeypatch.setattr(site,'checkout_ready',lambda:True);monkeypatch.setenv('AI_DAILY_BUDGET_AUD','0.01')
 class Sessions:
  def create(self,*a,**kw):raise AssertionError('Must not charge when delivery budget is unavailable')
 monkeypatch.setattr(site,'stripe_client',NS(v1=NS(checkout=NS(sessions=Sessions()))))
 response=client.post('/r/'+r['access']+'/checkout',data={'csrf':csrf(client)})
 assert response.status_code==302
 with site.store.connect() as c:assert c.execute('SELECT COUNT(*) AS n FROM ab49_orders').fetchone()['n']==0

def test_replayed_paid_event_after_refund_is_acknowledged_without_regrant(client,model,monkeypatch):
 monkeypatch.setenv('STRIPE_TEST_WEBHOOK_SECRET','whsec_unit');submit(client);r=row(client);d=order_for(r);assert site.fulfill(d)
 signed_webhook(client,{'type':'charge.refunded','livemode':False,'data':{'object':{'payment_intent':'pi_example','amount_refunded':199}}})
 response=signed_webhook(client,{'type':'checkout.session.completed','livemode':False,'data':{'object':d}})
 assert response.status_code==200 and not site.unlocked(row(client))
