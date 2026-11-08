import ast,copy,hashlib,json,os,signal,subprocess,sys,time
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime,timezone
root=Path(__file__).resolve().parents[3]
base=Path('/tmp')/('tjs1882-linux23-cleanup-fixtures-'+str(os.getpid()))
names=['portable-prepare-old-linux.py','portable-build.py','run-portable-check.py','run-portable-linux-ci.py']
if len(sys.argv)>1:
 source=Path(sys.argv[1]);out=Path(sys.argv[2]);bad=len(sys.argv)>3;out.mkdir(mode=0o700);public=out/'public';public.mkdir(mode=0o700)
 cid='a'*64;name='owned-fixture';image='sha256:'+'b'*64;invocation=owner='owned-invocation';docker=['docker'];cidfile=out/'container.id';cidfile.write_text(cid);container=out/'owned-container-state';container.write_text('owned');lock=out/'owned-fixture.lock';lock.touch(mode=0o600);lock_identity=lock.stat().st_ino;began=time.monotonic();arch='aarch64'
 receipt={'result':'FAILED_ATTEMPT','base_image':image,'cleanup':{'id':cid,'removed':False}};proof={'result':'FAIL'};work=out
 def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
 def save():write(out/'receipt.json',receipt)
 def build_diagnostics(work):return {'phase':'COMPILE','reason':'BUILD_FAILURE_UNCLASSIFIED'}
 def public_worker_receipt(value):return value
 def require(ok,reason):
  if not ok:raise AssertionError(reason)
 def command(argv,*a,**kw):
  if 'inspect' in argv:
   (out/'cleanup-ready').touch();time.sleep(.5)
   return json.dumps([{'Id':cid,'Name':'/'+('wrong-owner' if bad else name),'Image':image,'Config':{'Labels':{'meownero.invocation':invocation}},'State':{'OOMKilled':False,'ExitCode':2,'Running':False}}])
  if 'rm' in argv:
   require(argv[-1]==cid,'wrong owned fixture');container.unlink();time.sleep(.2);return cid
  if 'ps' in argv:return cid if container.exists() else ''
  raise AssertionError('unexpected mocked Docker command')
 def run(label,argv,*a,**kw):return command(argv)
 tester=SimpleNamespace(command=command,require=require,write=write);real_subprocess=subprocess
 subprocess=SimpleNamespace(check_output=lambda argv,**kw:command(argv))
 active=True
 def cancelled(n,f):
  if active:raise RuntimeError('OWNED_FIXTURE_CANCELLED')
 signal.signal(signal.SIGTERM,cancelled);signal.signal(signal.SIGINT,cancelled);original_mask=signal.pthread_sigmask(signal.SIG_BLOCK,set());original_handlers={s:signal.getsignal(s) for s in (signal.SIGTERM,signal.SIGINT)}
 if source.name=='run-portable-linux-ci.py':
  directory=out/'builder';directory.mkdir();(directory/'container.id').write_text(cid);container.unlink();write(directory/'preparation.json',{'cleanup':{'removed':not bad}})
  actual_write=write
  def write(path,value):
   if path.name=='builder.json':(out/'cleanup-ready').touch();time.sleep(.5)
   actual_write(path,value)
 tree=ast.parse(source.read_text());main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main');tries=[n for n in ast.walk(main) if isinstance(n,ast.Try) and n.finalbody];selected=sorted(tries,key=lambda n:(-n.end_lineno,n.lineno))[0]
 body=ast.parse("(out/'body-ready').touch(); time.sleep(20)").body;wrapped=ast.Try(body=body,handlers=[],orelse=[],finalbody=copy.deepcopy(selected.finalbody));fn=ast.FunctionDef(name='exercise_actual_finalizer',args=ast.arguments(posonlyargs=[],args=[],kwonlyargs=[],kw_defaults=[],defaults=[]),body=[wrapped],decorator_list=[]);module=ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[]));exec(compile(module,str(source),'exec'),globals())
 error=None
 try:exercise_actual_finalizer()
 except BaseException as e:error=type(e).__name__
 active=False
 state={'error_type':error,'mask_restored':signal.pthread_sigmask(signal.SIG_BLOCK,set())==original_mask,'handlers_restored':all(signal.getsignal(s)==h for s,h in original_handlers.items()),'container_removed':not container.exists(),'lock_removed':not lock.exists(),'receipt_written':(public/'ci-receipt.json').exists() if source.name=='run-portable-linux-ci.py' else (out/'check-receipt.json').exists() if source.name=='run-portable-check.py' else (out/'receipt.json').exists()}
 write(out/'fixture-state.json',state);sys.exit(0)
assert not base.exists();base.mkdir(mode=0o700);rows=[]
for version in ('old06','corrected17'):
 for name in names:
  for bad in ([False,True] if version=='corrected17' and name in ('portable-build.py','run-portable-linux-ci.py') else [False]):
   source=root/('build/tjs1882-3175-native-linux-ci-payload06/vanguard' if version=='old06' else 'vanguard')/name;out=base/(version+'-'+name+('-bad-owner' if bad else ''));p=subprocess.Popen([sys.executable,'-B',__file__,str(source),str(out),*(['bad'] if bad else [])],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
   def wait(path):
    end=time.monotonic()+5
    while not path.exists() and p.poll() is None and time.monotonic()<end:time.sleep(.01)
    assert path.exists(),(version,name,'missing fixture boundary',p.communicate()[1])
   wait(out/'body-ready');p.send_signal(signal.SIGTERM);wait(out/'cleanup-ready');p.send_signal(signal.SIGTERM);p.send_signal(signal.SIGINT);p.send_signal(signal.SIGTERM);_,stderr=p.communicate(timeout=6);assert p.returncode==0,(version,name,stderr)
   state=json.loads((out/'fixture-state.json').read_text());assert state['mask_restored'] and state['handlers_restored'],(version,name,state)
   if version=='corrected17':
    assert state['receipt_written'],(name,state)
    assert state['lock_removed']==(name=='run-portable-linux-ci.py' and not bad),(name,state)
    if name!='run-portable-linux-ci.py':assert state['container_removed']!=bad,(name,state)
   else:assert not (state['lock_removed'] if name=='run-portable-linux-ci.py' else state['container_removed']),(name,state)
   rows.append({'version':version,'source':name,'ownership_failure_injected':bad,'actual_signal_sequence':['SIGTERM','SIGTERM','SIGINT','SIGTERM'],'actual_finalizer_ast_executed':True,'bounded_Docker_operations':'MOCKED_NO_CONTAINER_OR_BUILD','worker_reaped':True,**state})
proof={'schema':'meownero-linux23-repeated-cancel-cleanup-fixtures/1','result':'PASS_OLD_INTERRUPTED_NEW_CLEANUP_PROTECTED_AND_FAIL_CLOSED','source_sha256':{name:hashlib.sha256((root/'vanguard'/name).read_bytes()).hexdigest() for name in names},'cases':rows,'native_build_and_journey':'UNTESTED'}
(root/'research/evidence/vanguard-portable-production-tjs1882-2026-10-09/linux23-repeated-cancel-fixtures.json').write_text(json.dumps(proof,indent=2)+'\n');print(proof['result'],len(rows))
