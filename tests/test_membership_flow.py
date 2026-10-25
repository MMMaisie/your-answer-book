import json,time,secrets,base64,hashlib
from types import SimpleNamespace as NS
import pytest
import app as site
from membership import AccessError
from conftest import submit,csrf,add_user,initial,full,Model
from hexagrams import build_cast

def reading():
 with site.connect() as c:return c.execute('SELECT * FROM readings ORDER BY created_at DESC').fetchone()

def test_initial_generation_succeeds_without_paid_call_or_paid_text(client,model):
 r=submit(client);assert r.status_code==302
 row=reading();assert row['paid_text']=='' and len(model.calls)==1
 with site.connect() as c:
  core=json.loads(c.execute('SELECT bundle_json FROM simple_reading_bundles').fetchone()[0])
 assert 'paid' not in core['bundle']
 assert client.get(r.location).status_code==200
 assert len(model.calls)==1
 assert client.post(r.location+'/full',data={'csrf':csrf(client)}).status_code==302
 assert len(model.calls)==1

def test_guest_ip_lifetime_limit_survives_cookie_reset(client,model):
 assert submit(client).status_code==302
 # A new browser on the same IP cannot claim another permanent guest trial.
 other=site.app.test_client();other.environ_base.update(client.environ_base)
 r=submit(other,question='我什么时候换工作？')
 assert r.status_code==200 and len(model.calls)==1
 with site.connect() as c:assert c.execute('SELECT COUNT(*) FROM readings').fetchone()[0]==1

def test_generation_failure_returns_trial_and_does_not_fake_success(client,monkeypatch):
 m=Model([RuntimeError('offline')]);monkeypatch.setattr(site,'OpenAI',lambda **kw:m)
 assert submit(client).status_code==200
 with site.connect() as c:assert c.execute('SELECT COUNT(*) FROM trial_claims').fetchone()[0]==0

def test_account_trial_upgrade_consumes_one_credit_once_and_caches(client,model):
 uid=add_user(client,credits=2);r=submit(client);assert len(model.calls)==1
 assert site.members.balance(uid)==2
 response=client.post(r.location+'/full',data={'csrf':csrf(client)})
 assert response.status_code==302 and len(model.calls)==2
 assert site.members.balance(uid)==1
 assert client.get(r.location).status_code==200
 client.post(r.location+'/full',data={'csrf':csrf(client)})
 assert len(model.calls)==2 and site.members.balance(uid)==1
 with site.connect() as c:assert c.execute('SELECT COUNT(*) FROM credit_entitlements').fetchone()[0]==1

def test_full_generation_failure_releases_credit_without_unlock(client,monkeypatch):
 uid=add_user(client,credits=1);m=Model([initial(),RuntimeError('offline')]);monkeypatch.setattr(site,'OpenAI',lambda **kw:m)
 r=submit(client);client.post(r.location+'/full',data={'csrf':csrf(client)})
 assert site.members.balance(uid)==1
 with site.connect() as c:
  assert c.execute('SELECT COUNT(*) FROM credit_entitlements').fetchone()[0]==0
  assert c.execute('SELECT paid_text FROM readings').fetchone()[0]==''

def test_second_account_question_requires_balance_and_generates_full_after_authorization(client,monkeypatch):
 uid=add_user(client,credits=1);m=Model([initial(),initial(),full()]);monkeypatch.setattr(site,'OpenAI',lambda **kw:m)
 assert submit(client).status_code==302
 r=submit(client,question='我跟他能结婚吗？');assert r.status_code==302
 assert len(m.calls)==3 and site.members.balance(uid)==0
 assert 'paid' in json.loads(m.calls[-1]['messages'][1]['content'])['schema']

def test_paid_endpoint_checks_authorization_at_provider_boundary(client,model):
 r=submit(client);row=reading()
 with site.app.test_request_context('/'):
  with pytest.raises(site.ReadingError,match='Payment'):
   site.call_ai(row['question'],site.cast_from_row(row),'zh','paid')
 assert len(model.calls)==1

def test_wallet_fulfillment_validates_amount_currency_mode_and_is_idempotent(client,monkeypatch):
 uid=add_user(client);sid='cs_test_wallet'
 with site.connect() as c:c.execute('INSERT INTO wallet_orders(session_id,account_id,sku,amount,credits,mode,status) VALUES(?,?,?,?,?,?,?)',(sid,uid,'five',599,5,'test','pending'))
 obj={'id':sid,'mode':'payment','payment_status':'paid','livemode':False,'amount_total':599,'currency':'aud','metadata':{'wallet_account_id':uid,'sku':'five'}}
 for field,value in [('amount_total',1),('currency','usd'),('livemode',True),('payment_status','unpaid')]:
  bad=dict(obj);bad[field]=value;assert not site.members.fulfill(bad)
 assert site.members.fulfill(obj) and site.members.fulfill(obj)
 assert site.members.balance(uid)==5
 monkeypatch.setattr(site,'STRIPE_MODE','live');monkeypatch.setattr(site,'STRIPE_TEST_MODE',False)
 assert site.members.balance(uid)==0

def test_unverified_account_cannot_spend_or_receive_free_trial(client):
 add_user(client,credits=5,verified=False)
 with client.session_transaction() as s:state=dict(s)
 with site.app.test_request_context('/'):
  site.session.update(state)
  with pytest.raises(AccessError):site.members.reserve_credit()
  with pytest.raises(AccessError):site.members.reserve_trial()

def test_login_password_and_csrf_logout(client):
 uid=add_user(client)
 client.post('/account/logout',data={'csrf':csrf(client)})
 r=client.post('/account/login',data={'csrf':csrf(client),'email':'test@example.org','password':'a-long-test-password'})
 assert r.status_code==302
 with client.session_transaction() as s:assert s['account_id']==uid
 assert client.post('/account/logout').status_code==400

def test_email_token_single_use_and_reset_invalidates_old_sessions(client):
 uid=add_user(client);raw=site.members.token(uid,'reset')
 old=site.app.test_client();old.environ_base.update(client.environ_base)
 with old.session_transaction() as s:s.update(account_id=uid,account_version=0,owner='acct:'+uid)
 response=client.post('/account/token/reset',data={'csrf':csrf(client),'token':raw,'password':'new-long-safe-password'})
 assert response.status_code==302
 with site.connect() as c:
  assert c.execute('SELECT session_version FROM accounts WHERE id=?',(uid,)).fetchone()[0]==1
  assert c.execute('SELECT COUNT(*) FROM account_tokens').fetchone()[0]==0
 assert old.get('/account/wallet').status_code==302
 assert client.post('/account/token/reset',data={'csrf':csrf(client),'token':raw,'password':'another-long-password'}).status_code==200

def test_public_mode_fails_closed_without_captcha_config(client,monkeypatch,model):
 monkeypatch.delenv('SITE_ACCESS_PASSWORD');monkeypatch.delenv('TURNSTILE_SECRET_KEY',raising=False)
 assert submit(client).status_code==200 and len(model.calls)==0

def test_no_key_in_public_pages_or_health_or_static_source(client,monkeypatch):
 secret='SENTINEL_SECRET_ONLY_IN_SERVER';monkeypatch.setattr(site,'AI_KEY',secret)
 for path in ('/','/healthz','/deck','/account/login','/static/site.js'):
  r=client.get(path);assert r.status_code==200 and secret.encode() not in r.data

def test_credit_reservation_prevents_overspend_and_double_finalization(client):
 uid=add_user(client,credits=1)
 with client.session_transaction() as s:state=dict(s)
 with site.app.test_request_context('/'):
  site.session.update(state)
  h=site.members.reserve_credit('example-reading')
  with pytest.raises(AccessError):site.members.reserve_credit('other-reading')
  site.members.finish_credit(h,True);site.members.finish_credit(h,True)
 assert site.members.balance(uid)==0

def test_unpaid_private_link_does_not_expose_paid_cache(client,model):
 r=submit(client);row=reading()
 with site.connect() as c:c.execute('UPDATE readings SET paid_text=?,paid_version=? WHERE seed_key=?',('PRIVATE_FULL_SENTINEL',site.PROMPT_VERSION,row['seed_key']))
 assert b'PRIVATE_FULL_SENTINEL' not in client.get(r.location).data

def test_page_refresh_does_not_trigger_model(client,model):
 r=submit(client)
 for _ in range(4):assert client.get(r.location).status_code==200
 assert len(model.calls)==1

def test_refunds_reverse_credits_idempotently_and_can_leave_debt(client):
 uid=add_user(client);sid='cs_test_refund';intent='pi_unit'
 with site.connect() as c:c.execute('INSERT INTO wallet_orders(session_id,account_id,sku,amount,credits,mode,status) VALUES(?,?,?,?,?,?,?)',(sid,uid,'five',599,5,'test','pending'))
 obj={'id':sid,'payment_intent':intent,'mode':'payment','payment_status':'paid','livemode':False,'amount_total':599,'currency':'aud','metadata':{'wallet_account_id':uid,'sku':'five'}}
 assert site.members.fulfill(obj) and site.members.balance(uid)==5
 refund={'payment_intent':intent,'amount_refunded':599}
 assert site.members.reverse_payment(refund) and site.members.reverse_payment(refund)
 assert site.members.balance(uid)==0

def test_real_sdk_signature_webhook_and_replay(client,monkeypatch):
 import hmac
 secret='whsec_unit_signature';monkeypatch.setenv('STRIPE_TEST_WEBHOOK_SECRET',secret)
 uid=add_user(client);sid='cs_test_signed'
 with site.connect() as c:c.execute('INSERT INTO wallet_orders(session_id,account_id,sku,amount,credits,mode,status) VALUES(?,?,?,?,?,?,?)',(sid,uid,'single',199,1,'test','pending'))
 obj={'id':sid,'object':'checkout.session','mode':'payment','payment_status':'paid','livemode':False,'amount_total':199,'currency':'aud','metadata':{'wallet_account_id':uid,'sku':'single'}}
 event={'id':'evt_unit','object':'event','type':'checkout.session.completed','livemode':False,'data':{'object':obj}}
 raw=json.dumps(event);stamp=str(int(time.time()));signature=hmac.new(secret.encode(),(stamp+'.'+raw).encode(),hashlib.sha256).hexdigest()
 for _ in range(2):assert client.post('/stripe/webhook',data=raw,headers={'Stripe-Signature':f't={stamp},v1={signature}'},content_type='application/json').status_code==200
 assert site.members.balance(uid)==1
 assert client.post('/stripe/webhook',data=raw,headers={'Stripe-Signature':'invalid'}).status_code==400

def test_stale_interrupted_hold_recovers_without_charging_failed_reading(client):
 uid=add_user(client,credits=1)
 with client.session_transaction() as s:state=dict(s)
 with site.app.test_request_context('/'):
  site.session.update(state);h=site.members.reserve_credit('missing-reading')
  with site.connect() as c:c.execute('UPDATE credit_holds SET created=? WHERE id=?',(time.time()-7200,h))
  site.members.recover_holds()
 assert site.members.balance(uid)==1

def test_refund_arriving_before_payment_event_does_not_regrant_credits(client):
 uid=add_user(client);sid='cs_test_early_refund';intent='pi_early'
 with site.connect() as c:c.execute('INSERT INTO wallet_orders(session_id,account_id,sku,amount,credits,mode,status) VALUES(?,?,?,?,?,?,?)',(sid,uid,'five',599,5,'test','pending'))
 site.members.reverse_payment({'payment_intent':intent,'amount_refunded':599})
 obj={'id':sid,'payment_intent':intent,'mode':'payment','payment_status':'paid','livemode':False,'amount_total':599,'currency':'aud','metadata':{'wallet_account_id':uid,'sku':'five'}}
 assert site.members.fulfill(obj) and site.members.balance(uid)==0
 assert site.members.fulfill(obj) and site.members.balance(uid)==0

def test_same_cast_reposted_in_other_ui_language_does_not_spend_again(client,model):
 first=submit(client)
 with client.session_transaction() as s:s['lang']='en'
 second=submit(client)
 assert first.location==second.location and len(model.calls)==1

def test_private_test_registration_does_not_send_email_and_is_never_public(client,monkeypatch):
 monkeypatch.setenv('ALLOW_PRIVATE_TEST_ACCOUNTS','1')
 def forbidden(*args):raise AssertionError('Test registration must not send mail')
 monkeypatch.setattr(site.members,'mail',forbidden)
 r=client.post('/account/register',data={'csrf':csrf(client),'email':'private@example.org','password':'a-private-test-password'})
 assert r.status_code==302
 with site.connect() as c:assert c.execute('SELECT verified FROM accounts WHERE email=?',('private@example.org',)).fetchone()[0]==1

def test_guest_trial_is_not_granted_again_after_verified_login(client,model):
 assert submit(client).status_code==302
 uid=add_user(client)
 client.post('/account/logout',data={'csrf':csrf(client)})
 # New browser grant after discarding cookies is bounded by IP for guests, verified accounts by account id.
 # Explicit inheritance check uses the guest owner still present in the same browser.
 with site.connect() as c:
  subject=c.execute("SELECT subject FROM trial_claims WHERE subject LIKE 'device:%'").fetchone()[0]
  u=c.execute('SELECT * FROM accounts WHERE id=?',(uid,)).fetchone()
 with site.app.test_request_context('/'):
  site.session['owner']=subject.removeprefix('device:');site.members.login(u)
  with pytest.raises(AccessError):site.members.reserve_trial(verified=True)

def test_checkout_amount_is_server_selected_and_not_browser_controlled(client,monkeypatch):
 uid=add_user(client);seen=[]
 def create(params,options=None):seen.append((params,options));return NS(id='cs_test_create',url='https://checkout.stripe.com/test',livemode=False)
 fake=NS(v1=NS(checkout=NS(sessions=NS(create=create))))
 monkeypatch.setattr(site,'stripe_client',fake);monkeypatch.setattr(site,'PUBLIC_URL','https://example.org');monkeypatch.setattr(site,'SUPPORT_EMAIL','support@example.org');monkeypatch.setenv('STRIPE_TEST_WEBHOOK_SECRET','whsec_unit')
 r=client.post('/account/buy/five',data={'csrf':csrf(client),'amount':1,'credits':1000})
 assert r.status_code==303
 line=seen[0][0]['line_items'][0]
 assert line['price_data']['unit_amount']==599 and line['price_data']['currency']=='aud' and line['quantity']==1
 assert 'payment_method_types' not in seen[0][0]
 assert seen[0][1]['idempotency_key']
 with site.connect() as c:
  o=c.execute('SELECT * FROM wallet_orders').fetchone();assert o['credits']==5 and o['amount']==599 and o['account_id']==uid

def test_email_verification_can_be_completed_once_without_leaking_token_in_url(client,monkeypatch):
 uid=add_user(client,verified=False);token=site.members.token(uid,'verify')
 page=client.get('/account/token/verify');assert page.status_code==200
 assert token.encode() not in page.data
 r=client.post('/account/token/verify',data={'csrf':csrf(client),'token':token})
 assert r.status_code==302
 with site.connect() as c:assert c.execute('SELECT verified FROM accounts WHERE id=?',(uid,)).fetchone()[0]==1
 assert client.post('/account/token/verify',data={'csrf':csrf(client),'token':token}).status_code==200

def test_storage_flag_alone_does_not_allow_live_checkout(client,monkeypatch):
 uid=add_user(client);monkeypatch.setattr(site,'STRIPE_MODE','live');monkeypatch.setattr(site,'STRIPE_TEST_MODE',False);monkeypatch.setattr(site,'STORAGE_DURABLE',True);monkeypatch.setattr(site,'stripe_client',object());monkeypatch.setattr(site,'PUBLIC_URL','https://example.org');monkeypatch.setattr(site,'SUPPORT_EMAIL','support@example.org');monkeypatch.setenv('STRIPE_TEST_WEBHOOK_SECRET','whsec_unit')
 assert not site.members.ready()
