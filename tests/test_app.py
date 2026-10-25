import itertools,json,sqlite3
from datetime import datetime
from pathlib import Path
import pytest
import app as site
from hexagrams import build_cast,BY_BITS,PALACES,HEXAGRAMS


def test_all_4096_casts():
    seen = set()
    for w in itertools.product(range(4), repeat=6):
        c = build_cast(w)
        bits = ''.join((str((9 - x) % 2) for x in w))
        seen.add(c['main']['number'])
        assert c['main']['bits'] == bits
        assert len(c['rows']) == 6
        assert c['palace']['shi'] != c['palace']['ying']
        for i, r in enumerate(c['rows']):
            assert r['moving'] == (w[i] in (0, 3))
        assert c['changed']['bits'] == ''.join((str(1 - int(b)) if x in (0, 3) else b for b, x in zip(bits, w)))
    assert seen == set(range(1, 65))

def test_known_qian_palace():
    qian = ['111111', '011111', '001111', '000111', '000011', '000001', '000101', '111101']
    expected = [1, 44, 33, 12, 20, 23, 35, 14]
    assert [BY_BITS[x]['number'] for x in qian] == expected
    assert [PALACES[x]['shi'] for x in qian] == [6, 1, 2, 3, 4, 5, 4, 3]
    c = build_cast([2] * 6, datetime(2026, 10, 4, 16))
    assert c['calendar']['day'] == '辛亥'
    assert [r['stem'] + r['branch'] for r in c['rows']] == ['甲子', '甲寅', '甲辰', '壬午', '壬申', '壬戌']
    assert [r['god'] for r in c['rows']] == ['白虎', '玄武', '青龙', '朱雀', '勾陈', '螣蛇']
    assert c['moving'] == []

@pytest.mark.parametrize('w', [[], [4] * 6, ['x'] * 6, [1] * 5])
def test_reject_bad_cast(w):
    with pytest.raises(ValueError):
        build_cast(w)

def test_timezones_and_boundary():
    a = build_cast([2] * 6, datetime(2026, 10, 4, 18, 30), 'Australia/Adelaide')
    b = build_cast([2] * 6, datetime(2026, 10, 4, 16, 0), 'Asia/Shanghai')
    assert a['calendar'] == b['calendar']
    before = build_cast([2] * 6, datetime(2026, 10, 4, 23, 30))
    after = build_cast([2] * 6, datetime(2026, 10, 5, 0, 30))
    assert before['calendar']['day'] != after['calendar']['day']
    with pytest.raises(ValueError):
        build_cast([2] * 6, datetime(2026, 10, 4, 2, 30), 'Australia/Adelaide')

def test_deck_art_data_matches_server(client):
    data = json.loads(client.get('/static/deck.json').data)
    assert data == HEXAGRAMS
    assert all((h['classical_image'] and h['art_note'] for h in data))
    assert 'I CHING' not in client.get('/').data.decode()
    assert 'id="card-dialog"' in client.get('/deck').data.decode()

def test_location_labels_and_chart_conversion(client):
    html = client.get('/').data.decode()
    assert '澳大利亚 · 阿德莱德' in html and '澳大利亚 · 悉尼' in html
    assert '当地起卦时间' in html and 'UTC+8' in html
    winter = build_cast([2] * 6, datetime(2026, 7, 1, 18, 30), 'Australia/Adelaide')
    summer = build_cast([2] * 6, datetime(2026, 12, 1, 18, 30), 'Australia/Adelaide')
    assert winter['calendar']['beijing_time'] == '2026-07-01 17:00'
    assert summer['calendar']['beijing_time'] == '2026-12-01 16:00'
    sydney = build_cast([2] * 6, datetime(2026, 12, 1, 18, 30), 'Australia/Sydney')
    assert sydney['calendar']['beijing_time'] == '2026-12-01 15:30'

def test_chart_line_labels_follow_language_inside_macro(client):
    assert '6爻'.encode() in client.get('/demo?lang=zh').data
    assert b'Line 6' in client.get('/demo?lang=en').data