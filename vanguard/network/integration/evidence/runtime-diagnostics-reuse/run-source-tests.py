import os,fcntl,sys,unittest,time,json,pathlib
root=pathlib.Path.cwd();sys.path.insert(0,str(root/'vanguard/network'))
original_open=os.open;original_flock=fcntl.flock
protected='/tmp/meownero-swarm-20260912-heavy.lock'
def guarded_open(path,flags,*args,**kwargs):
 if not isinstance(path,int) and os.fsdecode(path)==protected:raise AssertionError('source test attempted original lock open')
 return original_open(path,flags,*args,**kwargs)
def guarded_flock(fd,operation):
 st=os.fstat(fd if isinstance(fd,int) else fd.fileno())
 if (st.st_dev,st.st_ino)==(66306,657237):raise AssertionError('source test attempted original lock flock')
 return original_flock(fd,operation)
os.open=guarded_open;fcntl.flock=guarded_flock
start=time.monotonic()
import importlib,tempfile
scratch=tempfile.TemporaryDirectory(prefix='TJS-2504-source-checks-')
for name in ('test_network','test_policy','test_admission'):
 module=importlib.import_module(name)
 module.SCRATCH=pathlib.Path(scratch.name)
 if name!='test_admission':module.SOURCE=pathlib.Path('<repo>/build/vanguard-src/monero-fcmp')
 if name=='test_network':module.CLI_DIAGNOSTICS=[]
suite=unittest.defaultTestLoader.discover('vanguard/network',pattern=sys.argv[1] if len(sys.argv)>1 else 'test_*.py')
result=unittest.TextTestRunner(verbosity=2).run(suite)
print(json.dumps({'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),'wall_seconds':time.monotonic()-start,'original_lock_guard':'path before open; device/inode before flock','native_effects':'substituted'}))
scratch.cleanup()
raise SystemExit(not result.wasSuccessful())
