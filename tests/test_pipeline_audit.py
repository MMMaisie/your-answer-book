from datetime import datetime
import pytest
import app as site
import simple_reading as e
from hexagrams import build_cast
from conftest import Model,initial,review,full,submit
from test_guest_flow import row,paid,post_generate

CAST=build_cast([2]*6,datetime(2026,11,22,11,40))
def test_calendar_note_is_not_mistaken_for_forecast():
 day=CAST['calendar']['day'];month=CAST['calendar']['month']
 assert e.validate_internal_timing(day+'日，'+month+'月，比较盘面条件。',CAST)
 with pytest.raises(ValueError):e.validate_internal_timing('三个月内会结婚',CAST)
 with pytest.raises(ValueError):e.validate_internal_timing('2027年1月会结婚',CAST)

def test_reader_cannot_leak_calendar_notes():
 with pytest.raises(ValueError):e.check_parts({'direction':CAST['calendar']['day']+'日会结婚。'},'free','zh',CAST)

def test_preview_edit_uses_non_thinking_mode():
 bad=initial();bad['free']['direction']='用神受制，进展较慢。'
 m=Model([bad,{'free':{'direction':'目前推进偏慢，尚不适合急于确定结果。'}}])
 e.generate(m,'何时有对象',build_cast([2]*6),'deepseek-v4-pro')
 assert m.calls[0]['extra_body']['thinking']['type']=='enabled'
 assert m.calls[1]['extra_body']['thinking']['type']=='disabled'

def test_review_updates_preview_even_when_outlook_unchanged(client,monkeypatch):
 plan=review();plan['revised_free']='目前宜放慢推进，落实条件仍有变数。'
 m=Model([initial(),plan,full()]);monkeypatch.setattr(site,'OpenAI',lambda **kw:m)
 submit(client);r=row(client);paid(r)
 with site.store.connect() as db:db.execute("UPDATE ab49_readings SET free_en='stale translation' WHERE id=?",(r['id'],))
 post_generate(client,r);r=row(client)
 assert r['free_zh']==plan['revised_free'] and r['free_en']=='' and r['paid_zh']
 import json
 assert json.loads(r['bundle_json'])['bundle']['free']['direction']==r['free_zh']
