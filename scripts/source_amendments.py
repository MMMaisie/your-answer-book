"""Current source-page amendments layered over unchanged historical audit inputs."""
import copy,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def apply_source_amendments(records):
    path=ROOT/'research/v31_source_index_amendments.json'
    corrections=json.loads(path.read_text())['replacements'] if path.exists() else []
    byid={c['inventory_id']:copy.deepcopy(c) for c in records}
    for c in corrections:byid[c['inventory_id']]=copy.deepcopy(c)
    return [byid[c['inventory_id']] for c in records]
