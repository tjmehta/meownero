from pathlib import Path
import subprocess,json,fcntl,hashlib,time,shutil
r=Path('~/Developer/tjs1856-d779915e');o=r/'amd64';log=o/'preparation'
prior=json.loads((log/'receipt.json').read_text());assert prior['commands'][-1]['exit']==124
up=o/'monero-fcmp';pin=prior['source_pins']
receipt={'scope':'bounded incremental daemon-only x86 preparation emulated on build-mac; first timeout preserved','result':'INCOMPLETE','prior_receipt_sha256':hashlib.sha256((log/'receipt.json').read_bytes()).hexdigest(),'source_pins':pin,'rootfs':prior['rootfs'],'image_id':prior['image_id']}
with open('/tmp/meownero-swarm-20260912-heavy.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 mem=subprocess.check_output(['colima','ssh','--','cat','/proc/meminfo'],text=True);assert int(next(x.split()[1] for x in mem.splitlines() if x.startswith('MemAvailable:')))>=5*1024**2
 assert shutil.disk_usage(r).free>=5*1024**3
 assert subprocess.check_output(['git','-C',str(up),'rev-parse','HEAD'],text=True).strip()==pin['upstream']['commit']
 assert not subprocess.check_output(['git','-C',str(up),'status','--porcelain','--untracked-files=no'],text=True).strip()
 for path,rev in pin['upstream']['submodules'].items():assert subprocess.check_output(['git','-C',str(up/path),'rev-parse','HEAD'],text=True).strip()==rev
 assert hashlib.sha256((up/pin['rust']['cargo_lock_path']).read_bytes()).hexdigest()==pin['rust']['cargo_lock_sha256']
 args=['docker','--context','colima','run','--rm','--platform=linux/amd64','--name','tjs1856-amd64-resume','--pull=never','--network=none','--cap-drop=ALL','--security-opt=no-new-privileges','--cpus=2','--memory=4g','--memory-swap=4g','--pids-limit=256','--ulimit','core=0','-v',str(up)+':/src','-v',str(o)+':/work','-e','CARGO_HOME=/work/cargo-home','-e','CARGO_NET_OFFLINE=true','-e','PATH=/work/rust-x86/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin','-w','/src/build/vanguard',prior['image_id'],'bash','-euc',"trap 'cat /sys/fs/cgroup/memory.peak > /work/preparation/resume.memory; cat /sys/fs/cgroup/memory.events > /work/preparation/resume.memory-events' EXIT; rustc -V; uname -m; timeout 600 make -j1 daemon"]
 receipt['argv']=args;began=time.monotonic()
 try:
  with (log/'daemon-resume.log').open('wb') as f:result=subprocess.run(args,stdout=f,stderr=subprocess.STDOUT,timeout=720)
  receipt['exit']=result.returncode;receipt['wall_seconds']=time.monotonic()-began
  assert result.returncode==0
  binary=up/'build/vanguard/bin/monerod';data=binary.read_bytes();assert data[:4]==b'\x7fELF' and int.from_bytes(data[18:20],'little')==62
  receipt['binary']={'monerod':{'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}};receipt['result']='PASS_EMULATED_DAEMON_BUILD'
 finally:
  subprocess.run(['docker','--context','colima','rm','-f','tjs1856-amd64-resume'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  receipt['owned_container_absent']='tjs1856-amd64-resume' not in subprocess.check_output(['docker','--context','colima','ps','-a','--format','{{.Names}}'],text=True).splitlines()
  (log/'daemon-resume.json').write_text(json.dumps(receipt,indent=2)+'\n')
 print(receipt['result'],flush=True)
