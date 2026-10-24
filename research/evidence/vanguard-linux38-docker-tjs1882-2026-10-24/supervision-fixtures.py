#!/usr/bin/env python3
"""Small real process tests of the unchanged source-bound supervisor, no Docker."""
import argparse,importlib.util,json,os,signal,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(); p.add_argument('--kit',type=Path,required=True); p.add_argument('--out',type=Path,required=True); a=p.parse_args()
assert not a.out.exists(); a.out.mkdir(mode=0o700)
spec=importlib.util.spec_from_file_location('checked_supervisor',a.kit/'vanguard/run-portable-ci.py'); supervisor=importlib.util.module_from_spec(spec); spec.loader.exec_module(supervisor)
wrapper=a.out/'wrapper.py'
wrapper.write_text('''import signal,subprocess,sys,time
child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])
def stop(n,f):
    child.terminate()
    child.wait(timeout=5)
    sys.exit(0)
signal.signal(signal.SIGTERM,stop)
if sys.argv[1]=='normal':
    time.sleep(.6)
    stop(None,None)
else:
    child.wait(timeout=20)
''')
unrelated=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])
rows=[]
try:
 for mode,timeout,expected in [('normal',5,None),('deadline',.5,'TimeoutExpired'),('cancellation',5,'RuntimeError')]:
  private=a.out/mode; private.mkdir(); public=private/'public'; public.mkdir()
  sender=None
  if mode=='cancellation':
   sender=subprocess.Popen([sys.executable,'-c','import os,signal,time; time.sleep(1); os.kill('+str(os.getpid())+',signal.SIGTERM)'])
  error=None
  try: supervisor.mac_check([sys.executable,'-B',wrapper,mode],private,public,timeout=timeout,cleanup_seconds=30)
  except BaseException as e: error=type(e).__name__
  finally:
   if sender: sender.wait(timeout=5)
  receipt=json.loads((public/'supervision.json').read_text())
  assert error==expected,(mode,error,receipt)
  assert receipt['wrapper_reaped'] and all(r['removed'] for r in receipt['cleanup'])
  assert unrelated.poll() is None
  rows.append({'case':mode,'expected_exception':expected,'observed_exception':error,'wrapper_reaped':True,'owned_children_removed':True,'unrelated_preserved':True,'result':'PASS'})
finally:
 unrelated.terminate(); unrelated.wait(timeout=5)
(a.out/'result.json').write_text(json.dumps({'result':'PASS','cases':rows,'unrelated_fixture_reaped':True,'docker_execution':'NONE','native_meownero_journey':'UNTESTED'},indent=2)+'\n')
print('PASS_NORMAL_DEADLINE_CANCELLATION_UNRELATED_PRESERVATION')
