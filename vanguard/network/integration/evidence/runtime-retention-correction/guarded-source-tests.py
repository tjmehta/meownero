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
try:
    if len(sys.argv)>1 and sys.argv[1]=='--known-bad':
        import test_direct_profile as test
        old=subprocess.check_output(['git','show','6671d176de7a88114086cee845be9bb9d62a49e5:vanguard/network/run-profile.py'])
        baseline=types.ModuleType('baseline_direct_retention');baseline.__file__=str(root/'vanguard/network/run-profile.py')
        exec(compile(old,baseline.__file__,'exec'),baseline.__dict__)
        test.r=baseline
        suite=unittest.TestSuite([test.Direct('test_zero_exit_runtime_evidence_failures_retain_private_staging_full_and_reuse')])
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        assert len(result.failures)==12 and not result.errors and not result.skipped, 'known-bad must fail all 12 adverse retention cases'
        print(json.dumps({'known_bad':'DETECTED','candidate':'6671d176','adverse_subcases_failed':12,'native_effects':'substituted'}))
    else:
        runpy.run_path(str(root/'vanguard/network/integration/evidence/runtime-diagnostics-reuse/run-source-tests.py'),run_name='__main__')
finally:
    after=os.stat(protected,follow_symlinks=False)
    print(json.dumps({'protected_lock_metadata_unchanged':fields(before)==fields(after),'protected_lock_metadata':fields(after),
        'blocked_original_lock_touches':blocked,'guard':'builtins/io/os open before call by exact path and device/inode; flock before call',
        'wrapper_seconds':time.monotonic()-start}))
    assert fields(before)==fields(after) and not blocked
