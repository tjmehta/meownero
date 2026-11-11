"""Source checks only; deny original heavy-lock opens and acquisitions."""
import builtins,fcntl,io,json,os,pathlib,runpy,sys,time,types,unittest,subprocess
protected='/tmp/meownero-swarm-20260912-heavy.lock'
identity=(66306,657237)
real_os_open=os.open;real_builtin_open=builtins.open;real_io_open=io.open;real_flock=fcntl.flock
blocked=[]
def refuse_original(path,*,dir_fd=None):
    if isinstance(path,int):
        info=os.fstat(path)
    else:
        if os.fsdecode(path)==protected:
            blocked.append('path');raise AssertionError('original heavy-lock open forbidden')
        try:info=os.stat(path,dir_fd=dir_fd)
        except (FileNotFoundError,NotADirectoryError):return
    if (info.st_dev,info.st_ino)==identity:
        blocked.append('inode');raise AssertionError('original heavy-lock alias/descriptor forbidden')
def guarded_os_open(path,flags,*args,**kwargs):
    refuse_original(path,dir_fd=kwargs.get('dir_fd'))
    return real_os_open(path,flags,*args,**kwargs)
def guarded_builtin_open(path,*args,**kwargs):
    refuse_original(path);return real_builtin_open(path,*args,**kwargs)
def guarded_io_open(path,*args,**kwargs):
    refuse_original(path);return real_io_open(path,*args,**kwargs)
def guarded_flock(fd,operation):
    refuse_original(fd if isinstance(fd,int) else fd.fileno())
    return real_flock(fd,operation)
os.open=guarded_os_open;builtins.open=guarded_builtin_open;io.open=guarded_io_open;fcntl.flock=guarded_flock
root=pathlib.Path.cwd();sys.path.insert(0,str(root/'vanguard/network'))
before=os.stat(protected,follow_symlinks=False)
fields=lambda s:[s.st_dev,s.st_ino,s.st_uid,s.st_mode,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
start=time.monotonic()
def audit(event,args):
    if event=='subprocess.Popen':
        executable=pathlib.Path(os.fsdecode(args[0]))
        if executable.name=='docker' or (executable.name in ('monerod','monero-wallet-cli','monero-wallet-rpc') and
                                        not executable.is_relative_to('/tmp')):
            blocked.append('native-spawn');raise AssertionError('source test attempted native/Docker execution')
sys.addaudithook(audit)
try:
    import warnings
    warnings.simplefilter('error', ResourceWarning)
    if len(sys.argv)>1 and sys.argv[1]=='--mutations':
        runpy.run_path(str(root/'vanguard/network/integration/evidence/security-notes-n1-n6/mutation-checks.py'),run_name='__main__')
    else:
        import importlib, tempfile
        with tempfile.TemporaryDirectory(prefix='TJS-4393-source-') as scratch:
            for name in ('test_network', 'test_policy', 'test_admission'):
                module=importlib.import_module(name)
                module.SCRATCH=pathlib.Path(scratch)
                module.SOURCE=pathlib.Path('<repo>/build/vanguard-src/monero-fcmp')
                if name=='test_network': module.CLI_DIAGNOSTICS=[]
            loader=unittest.TestLoader()
            if len(sys.argv)>1 and sys.argv[1]=='--focus':
                suite=loader.loadTestsFromName('integration.test_operator')
            else:
                suite=loader.discover(str(root/'vanguard/network'),pattern='test_*.py')
                for path in sorted((root/'vanguard/network/integration').glob('test_*.py')):
                    suite.addTests(loader.loadTestsFromName('integration.'+path.stem))
            assert suite.countTestCases()>0, 'empty test discovery'
            result=unittest.TextTestRunner(verbosity=2).run(suite)
            print(json.dumps({'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
                'skipped':len(result.skipped),'seconds':time.monotonic()-start,'native':'NOT_RUN'}))
            raise SystemExit(not result.wasSuccessful() or bool(result.skipped))
finally:
    after=os.stat(protected,follow_symlinks=False)
    print(json.dumps({'protected_lock_metadata_unchanged':fields(before)==fields(after),'protected_lock_metadata':fields(after),
        'blocked_original_lock_touches':blocked,'guard':'builtins/io/os open before call by exact path and device/inode; flock before call',
        'wrapper_seconds':time.monotonic()-start}))
    assert fields(before)==fields(after) and not blocked
