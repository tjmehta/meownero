import subprocess,json,uuid
from pathlib import Path
root=Path('/var/lib/tjs1882');name='tjs1882-abf0b97a-cgroup';owner=uuid.uuid4().hex
assert subprocess.check_output(['uname','-r'],text=True).strip()=='6.8.0-138-generic'
assert not subprocess.check_output(['docker','ps','-q'],text=True).strip()
image='sha256:30dfd7fe96f97c5f5ddf388ce8d098aa509644ad68fdef67244fb71b8169ffcb'
cidfile=root/'qualification-hwe/cgroup.container.id';proof={'schema':'meownero-native-cgroup-counter-qualification/1','result':'FAIL','kernel':'6.8.0-138-generic'}
try:
 r=subprocess.run(['docker','run','--pull=never','--name',name,'--cidfile',str(cidfile),'--label','meownero.invocation='+owner,'--network=none','--read-only','--cap-drop=ALL','--security-opt=no-new-privileges','--cpus=1','--memory=64m','--memory-swap=64m','--pids-limit=32',image,'/bin/sh','-ec','cat /sys/fs/cgroup/memory.max; cat /sys/fs/cgroup/memory.peak; cat /sys/fs/cgroup/memory.events'],capture_output=True,text=True,timeout=30)
 proof.update(exit=r.returncode,output=r.stdout,stderr=r.stderr);assert r.returncode==0
 lines=r.stdout.splitlines();assert int(lines[0])==64*1024**2 and 0<int(lines[1])<=int(lines[0])
 events=dict(line.split() for line in lines[2:]);assert events['oom']=='0' and events['oom_kill']=='0'
 proof['counters_validated']=True
finally:
 if cidfile.exists():
  cid=cidfile.read_text().strip();p=json.loads(subprocess.check_output(['docker','inspect',cid],text=True,timeout=15))[0]
  assert p['Id']==cid and p['Name']=='/'+name and p['Image']==image and p['Config']['Labels']['meownero.invocation']==owner
  subprocess.run(['docker','rm',cid],capture_output=True,check=True,timeout=15)
  assert cid not in subprocess.check_output(['docker','ps','-aq','--no-trunc'],text=True,timeout=15).splitlines()
  proof['owned_container_removed']=True
 if proof.get('counters_validated') and proof.get('owned_container_removed'):proof['result']='PASS_NATIVE_CGROUP_MEMORY_COUNTERS_AND_OWNED_CLEANUP'
 (root/'cgroup-diagnostic.json').write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps(proof,indent=2))
