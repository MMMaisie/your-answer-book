import copy,json
import pytest
import app
from test_app import client,submit,row_for,csrf,mark
from test_simple_reading import sample,Model,CAST
from simple_reading import translate,count

@pytest.fixture
def isolated(tmp_path,monkeypatch):
 app.app.config.update(TESTING=True,DB_PATH=str(tmp_path/'private.db'),SESSION_COOKIE_SECURE=False)
 app.init_db();monkeypatch.setattr(app,'AI_KEY','test-only-no-real-api')


def test_actual_ai_wrapper_uses_single_generation_for_both_tiers_and_survives_new_session(isolated,monkeypatch):
 calls=[]
 def generate(*args):calls.append(args[1]);return {'bundle':sample(),'external_status':'NOT_NEEDED','external_references':[]}
 class Context:
  def __enter__(self):return object()
  def __exit__(self,*args):return False
 monkeypatch.setattr(app,'OpenAI',lambda **kwargs:Context())
 monkeypatch.setattr(app,'simple_generate',generate)
 with app.app.test_request_context('/'):
  app.session['owner']='owner-one'
  free=app.call_ai('我什么时候能拿到offer？',CAST,'zh','free')
  paid=app.call_ai('我什么时候能拿到offer？',CAST,'zh','paid',free)
 with app.app.test_request_context('/'):
  app.session['owner']='owner-two'
  assert app.call_ai('我什么时候能拿到offer？',CAST,'zh','paid',free)==paid
 assert len(calls)==1 and '【规则依据】' in paid and '【规则依据】' not in free


def test_precomputed_paid_bundle_is_never_exposed_before_payment(client,monkeypatch):
 # The real web permission path is used, with a distinctive private cached body.
 response=submit(client);row=row_for(client)
 assert client.post(response.location+'/full',data={'csrf':csrf(client)}).status_code==403
 with app.connect() as db:
  db.execute('UPDATE readings SET paid_text=?,paid_version=? WHERE seed_key=?',('PRIVATE_PRECOMPUTED_BODY',app.PROMPT_VERSION,row['seed_key']))
 assert b'PRIVATE_PRECOMPUTED_BODY' not in client.get(response.location).data
 mark(row)
 assert b'PRIVATE_PRECOMPUTED_BODY' in client.get(response.location).data


def test_translation_preserves_source_order_within_the_same_request():
 value={'direction':'There is room for this job application to progress, although the offer is not yet certain.','evidence':'Key conditions remain unresolved, so present support should be watched carefully rather than treated as proof that the outcome is secure.'}
 model=Model([value]);result=translate(model,sample()['free'],'free',CAST,'mock')
 assert result['parts']==value and 30<=count(' '.join(value.values()),'en')<=65
 assert len(model.calls)==1 and 'Do not reinterpret' in model.calls[0]['messages'][0]['content']


def test_missing_web_key_is_explicit_and_does_not_block_book_reasoning(monkeypatch):
 from external_references import search
 monkeypatch.delenv('BRAVE_SEARCH_API_KEY',raising=False)
 assert search({'求职'})=={'status':'NOT_CONFIGURED','results':[]}
