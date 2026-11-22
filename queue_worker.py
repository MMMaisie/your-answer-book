"""Run as a separate Render background worker: python queue_worker.py."""
import os,signal,threading,logging
from concurrent.futures import ThreadPoolExecutor
import app as site
from generation_queue import run_one,heartbeat
stop=threading.Event()
def loop():
 while not stop.is_set():
  try:
   heartbeat(site.store);worked=run_one(site)
  except Exception as error:
   site.app.logger.warning('Queue polling failed: category=%s',type(error).__name__);worked=False
  stop.wait(.25 if worked else 2)
def main():
 for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stop.set())
 workers=max(1,min(20,int(os.getenv('AI_MAX_CONCURRENT','5'))))
 with ThreadPoolExecutor(max_workers=workers) as pool:
  futures=[pool.submit(loop) for _ in range(workers)]
  try:
   while not stop.wait(5):
    try:heartbeat(site.store)
    except Exception as error:site.app.logger.warning('Queue heartbeat failed: category=%s',type(error).__name__)
  finally:
   stop.set()
   for future in futures:future.result()
if __name__=='__main__':main()
