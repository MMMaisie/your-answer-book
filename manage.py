"""Local admin commands; never exposed as public HTTP endpoints."""
import argparse
parser=argparse.ArgumentParser();parser.add_argument('command',choices=['cleanup','usage']);args=parser.parse_args()
from app import store
if args.command=='cleanup':store.cleanup(force=True);print('Expired reading content removed.')
else:
 from datetime import datetime,timezone
 day=datetime.now(timezone.utc).strftime('%Y-%m-%d')
 with store.connect() as c:r=c.execute('SELECT COUNT(*) AS calls,COALESCE(SUM(reserve),0) AS reserved_aud,COALESCE(SUM(prompt_tokens),0) AS input_tokens,COALESCE(SUM(completion_tokens),0) AS output_tokens FROM ab49_calls WHERE day=?',(day,)).fetchone()
 print(dict(r))
 print('Reserved AUD is a conservative safety allowance, not the actual invoice.')
