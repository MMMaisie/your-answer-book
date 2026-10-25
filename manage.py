"""Operator-only CLI. No HTTP admin backdoor; run in the trusted server shell."""
import argparse,time,secrets,sqlite3,os
from pathlib import Path
import app
p=argparse.ArgumentParser();p.add_argument('action',choices=['audit','backup','grant','recover']);p.add_argument('--email');p.add_argument('--credits',type=int);p.add_argument('--reason',default='manual adjustment');args=p.parse_args()
if args.action=='audit':
 with app.connect() as c:
  print({'accounts':c.execute('SELECT COUNT(*) FROM accounts').fetchone()[0],'readings':c.execute('SELECT COUNT(*) FROM readings').fetchone()[0],'held_credits':c.execute("SELECT COUNT(*) FROM credit_holds WHERE status='held'").fetchone()[0]})
elif args.action=='backup':
 target=Path(app.app.config['DB_PATH']).with_name('backup-'+str(int(time.time()))+'.sqlite3')
 with app.connect() as source,sqlite3.connect(target) as dest:source.backup(dest)
 target.chmod(0o600);print('Backup created:',target)
elif args.action=='recover':app.members.recover_holds();print('Stale holds checked.')
else:
 if not args.email or not args.credits or args.credits<1 or args.credits>100:raise SystemExit('Specify --email and --credits 1..100. Use only after verifying the adjustment.')
 with app.connect() as c:
  user=c.execute('SELECT id FROM accounts WHERE email=?',(args.email.strip().lower(),)).fetchone()
  if not user:raise SystemExit('Account not found.')
  c.execute('INSERT INTO credit_ledger VALUES(?,?,?,?,?)',('manual:'+secrets.token_hex(16),user[0],args.credits,app.STRIPE_MODE+':manual:'+args.reason[:100],time.time()))
 print('Adjustment recorded. No payment was initiated.')
