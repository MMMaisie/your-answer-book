import os,getpass,secrets
# No .env generation. The key stays in this process's environment only.
os.environ['STRIPE_MODE']='test';os.environ['ALLOW_PRIVATE_TEST_ACCOUNTS']='1';os.environ.setdefault('FLASK_SECRET_KEY',secrets.token_hex(32))
os.environ.setdefault('COOKIE_SECURE','0');os.environ.setdefault('PUBLIC_BASE_URL','http://127.0.0.1:5000')
if not os.getenv('DEEPSEEK_API_KEY'):os.environ['DEEPSEEK_API_KEY']=getpass.getpass('DeepSeek key (hidden; leave empty to inspect UI only): ').strip()
if not os.getenv('SITE_ACCESS_PASSWORD'):os.environ['SITE_ACCESS_PASSWORD']=getpass.getpass('Choose a private-site password (at least 20 characters): ')
if len(os.environ['SITE_ACCESS_PASSWORD'])<20:raise SystemExit('Password too short.')
from app import app
print('Open http://127.0.0.1:5000 — username tester; password is the one you chose.')
app.run(host='127.0.0.1',port=5000,debug=False)
