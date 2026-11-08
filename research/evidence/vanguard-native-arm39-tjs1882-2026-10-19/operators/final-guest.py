from pathlib import Path
import json,os,stat,re,hashlib,subprocess
r=Path('/var/lib/tjs1882');proof={'schema':'meownero-native-arm39-final-guest-cleanup/1','result':'FAIL'}
pids=set()
for attempt in ('attempt01','attempt02'):
 for p in (r/attempt/'public').glob('*-supervision.json'):
  j=json.loads(p.read_text())
  if attempt=='attempt02':
   assert j['result']=='PASS_WRAPPER_AND_OWNED_CLEANUP' and j['wrapper_reaped']
   pids.add(j['wrapper_pid']);pids.update(x['pid'] for x in j['cleanup'])
   for x in j.get('rejected_observation_cleanup',[]):
    if 'pid' in x:pids.add(x['pid'])
   for x in j.get('snapshot_cost',{}).get('recent',[]):pids.add(x['observer_pid'])
assert pids and all(not Path('/proc/'+str(p)).exists() for p in pids)
proof['attempt02_recorded_host_pids_absent']=sorted(pids)
proof['attempt01_cleanup_before_reboot']=json.loads((r/'attempt01-cleanup.json').read_text())
allids=set(subprocess.check_output(['docker','ps','-aq','--no-trunc'],text=True,timeout=20).splitlines())
containers=[]
for directory in ('attempt01/builder','attempt02/builder','attempt02/build','attempt02/runtime','qualification-hwe','debian12-prep01','debian12-runtime01'):
 for p in (r/directory).glob('*.id'):
  cid=p.read_text().strip();assert re.fullmatch('[0-9a-f]{64}',cid) and cid not in allids
  containers.append({'cidfile':str(p.relative_to(r)),'identity_sha256':hashlib.sha256(cid.encode()).hexdigest(),'absent':True})
assert not allids
proof['recorded_containers']=containers;proof['isolated_vm_container_count']=0
j=json.loads((r/'distro-lock.json').read_text());p=Path(j['path']);s=p.lstat()
assert stat.S_ISREG(s.st_mode) and not p.is_symlink() and s.st_nlink==1 and s.st_ino==j['inode'] and s.st_uid==j['uid'] and p.read_text()==j['content'] and 'abf0b97a' in j['content']
p.unlink();assert not p.exists();proof['owned_supplemental_lock_removed']=True
assert json.loads((r/'attempt02/public/ci-receipt.json').read_text())['owned_ephemeral_lock_removed']
assert json.loads((r/'debian12-runtime01/check-receipt.json').read_text())['result']=='PASS_NATIVE_ARCHIVE_JOURNEY'
proof['result']='PASS_RECORDED_PROCESSES_CONTAINERS_AND_LOCKS_REMOVED_VM_DELETION_PENDING'
(r/'final-guest-cleanup.json').write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps({'result':proof['result'],'host_pids':len(pids),'owned_containers':len(containers)}))
