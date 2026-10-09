import fcntl,subprocess,json,time,shutil,hashlib
from pathlib import Path
root=Path('~/Developer/tjs1856-d779915e');out=root/'smoke-arm01';out.mkdir()
up=Path('~/Developer/tjs1816-5a24c6b6/build01/monero-fcmp')
pin=json.loads((root/'source-lock.json').read_text())
assert subprocess.check_output(['git','-C',str(up),'rev-parse','HEAD'],text=True).strip()==pin['upstream']['commit']
assert not subprocess.check_output(['git','-C',str(up),'status','--porcelain','--untracked-files=no'],text=True).strip()
for path,rev in pin['upstream']['submodules'].items():
 assert subprocess.check_output(['git','-C',str(up/path),'rev-parse','HEAD'],text=True).strip()==rev
assert hashlib.sha256((up/pin['rust']['cargo_lock_path']).read_bytes()).hexdigest()==pin['rust']['cargo_lock_sha256']
with open('/tmp/meownero-swarm-20260912-heavy.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 mem=subprocess.check_output(['colima','ssh','--','cat','/proc/meminfo'],text=True)
 assert int(next(x.split()[1] for x in mem.splitlines() if x.startswith('MemAvailable:')))>=5*1024**2
 assert shutil.disk_usage(root).free>=5*1024**3
 argv=['docker','--context','colima','run','--rm','--name','tjs1856-smoke-arm01','--pull=never','--network=none','--cap-drop=ALL','--security-opt=no-new-privileges','--cpus=2','--memory=512m','--memory-swap=512m','--pids-limit=64','--ulimit','core=0','-u','501:20','-v',str(root)+':/harness:ro','-v',str(up)+':/src:ro','-v',str(out)+':/out','sha256:345b4ccbee39f1231271234eddcc38e9e7c492114744ca21796b517913ee544b','bash','-euc',"trap 'cat /sys/fs/cgroup/memory.peak > /out/final.memory; cat /sys/fs/cgroup/memory.events > /out/final.memory-events' EXIT; timeout 150 python3 -B /harness/check-railway-peer.py"]
 began=time.monotonic()
 try:
  with (out/'stdout.log').open('wb') as stream:r=subprocess.run(argv,stdout=stream,stderr=subprocess.STDOUT,timeout=170)
 finally:
  subprocess.run(['docker','--context','colima','rm','-f','tjs1856-smoke-arm01'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 absent='tjs1856-smoke-arm01' not in subprocess.check_output(['docker','--context','colima','ps','-a','--format','{{.Names}}'],text=True).splitlines()
 receipt={'argv':argv,'exit':r.returncode,'wall_seconds':time.monotonic()-began,'container_absent':absent,'source_pins':pin,'meminfo':mem,'disk_free':shutil.disk_usage(root).free}
 (out/'host-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 print('native offline capacity check',r.returncode,absent)
 print((out/'stdout.log').read_text()[-2000:])
