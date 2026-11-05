import sys,os,json,unittest,time
from pathlib import Path
root=Path.cwd(); evidence=Path(sys.argv[1]); mode=sys.argv[2]
lock=Path('/tmp/meownero-swarm-20260912-heavy.lock'); before=lock.stat(); blocked=[]
def guard(event,args):
 if event=='open':
  path=args[0]
  if isinstance(path,(str,bytes,os.PathLike)):
   p=Path(os.fsdecode(path))
   try: st=p.stat(); protected=(st.st_dev,st.st_ino)==(66306,657237)
   except (FileNotFoundError,NotADirectoryError,OSError): protected=False
   if p==lock or protected:
    blocked.append('open'); raise RuntimeError('protected original lock refused before open')
   if str(p).startswith('<agent-scratch>'):
    blocked.append('retained-read'); raise RuntimeError('retained native file refused')
 if event=='fcntl.flock':
  st=os.fstat(args[0])
  if (st.st_dev,st.st_ino)==(66306,657237):
   blocked.append('flock'); raise RuntimeError('protected original lock refused before flock')
 if event=='subprocess.Popen':
  executable=os.fsdecode(args[0])
  if Path(executable).name=='docker' or (Path(executable).name in ('monerod','monero-wallet-cli','monero-wallet-rpc') and not Path(executable).is_relative_to('/tmp')):
   blocked.append('native-spawn'); raise RuntimeError('real native/Docker execution refused')
sys.addaudithook(guard)
sys.path.insert(0,str(root/'vanguard/network'))
# These established CLI suites require explicit pinned-source and scratch fixtures.
import tempfile,importlib
scratch=tempfile.TemporaryDirectory(prefix='tjs2504-source-')
for name in ('test_network','test_admission','test_policy'):
 module=importlib.import_module(name)
 module.SCRATCH=Path(scratch.name)
 module.SOURCE=Path('<repo>/build/vanguard-src/monero-fcmp')
 if name=='test_network': module.CLI_DIAGNOSTICS=[]
loader=unittest.TestLoader()
if mode=='full':
 suite=loader.discover(str(root/'vanguard/network'),pattern='test_*.py')
 suite.addTests(loader.loadTestsFromName('integration.test_funded_profile'))
else: suite=loader.loadTestsFromName('integration.test_funded_profile')
started=time.monotonic(); result=unittest.TextTestRunner(verbosity=2).run(suite)
after=lock.stat()
unchanged=all(getattr(before,k)==getattr(after,k) for k in ('st_dev','st_ino','st_uid','st_mode','st_size','st_mtime_ns','st_ctime_ns'))
summary=dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),seconds=time.monotonic()-started,protected_lock_touches=blocked,protected_lock_metadata_unchanged=unchanged,native='NOT_RUN',result='PASS' if result.wasSuccessful() and not blocked and unchanged else 'FAIL')
scratch.cleanup()
evidence.write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
raise SystemExit(0 if summary['result']=='PASS' else 1)
