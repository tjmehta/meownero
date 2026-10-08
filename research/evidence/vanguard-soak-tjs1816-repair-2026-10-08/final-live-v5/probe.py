import subprocess,json,hashlib,shutil
from pathlib import Path
root=Path('~/Developer/tjs1816-5a24c6b6')
candidate=root/'candidate-run-v5'
argvs=[['hostname'],['uname','-srm'],['sw_vers'],['sysctl','-n','hw.memsize','hw.ncpu'],['docker','--context','colima','version'],['docker','--context','colima','info','--format','{{json .}}'],['docker','--context','colima','ps','-a','--format','{{json .}}'],['docker','--context','colima','image','inspect','sha256:345b4ccbee39f1231271234eddcc38e9e7c492114744ca21796b517913ee544b'],['colima','ssh','--','cat','/proc/meminfo'],['git','-C',str(candidate),'rev-parse','HEAD'],['git','-C',str(candidate),'status','--porcelain'],['git','-C','<repo>','status','--short']]
for argv in argvs:
 r=subprocess.run(argv,capture_output=True,text=True,timeout=30);print(json.dumps({'argv':argv,'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr}))
print(json.dumps({'disk_free_bytes':shutil.disk_usage(root).free,'profile_sha256':hashlib.sha256(Path('~/.colima/default/colima.yaml').read_bytes()).hexdigest()}))
for name in ['monerod','monero-wallet-rpc']:
 p=root/'build01/monero-fcmp/build/vanguard/bin'/name
 with p.open('rb') as f: header=f.read(20)
 print(json.dumps({'binary':name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size,'elf_magic':header[:4].hex(),'elf_machine':int.from_bytes(header[18:20],'little')}))
r=subprocess.run(['ps','-p','75180,10739','-o','pid,ppid,lstart,command'],capture_output=True,text=True);print(json.dumps({'argv':['ps','-p','75180,10739','-o','pid,ppid,lstart,command'],'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr}))

import fcntl
lock=Path('/tmp/meownero-swarm-20260912-heavy.lock')
with lock.open('a+') as f:
 try:
  fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
  print(json.dumps({'heavy_lock_available':True,'path':str(lock)}))
  fcntl.flock(f,fcntl.LOCK_UN)
 except BlockingIOError:
  print(json.dumps({'heavy_lock_available':False,'path':str(lock)}))
