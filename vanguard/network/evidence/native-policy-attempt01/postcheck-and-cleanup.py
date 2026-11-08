import datetime, fcntl, hashlib, importlib.util, json, os, pathlib, re, shutil, stat, subprocess, sys, tarfile
RUN=pathlib.Path(__file__).resolve().parent
OUT=RUN/'native-policy-attempt01'
E=RUN/'evidence'
sys.path.insert(0,str(pathlib.Path('vanguard/network').resolve()))
import network as n, policy
spec=importlib.util.spec_from_file_location('genesis_cleanup',n.HERE/'run-genesis.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
def sha(p):
    with p.open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
r={'schema':'meownero-tjs2504-native-postcheck-cleanup/1','observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'launch_ready':False}
# Never touch active staging. Require persisted normal supervision completion.
exit_record=json.loads((E/'native-invocation-exit.json').read_text())
receipt=json.loads((OUT/'receipt.json').read_text())
n.require(receipt['result']!='RUNNING' and receipt.get('lock_fd_closed'),'driver did not finish cleanup')
n.require(receipt['grant_comment']=='0ae5446a-0da7-4f75-9604-50b4e7b090c8','foreign grant')
r['driver_exit']=exit_record;r['native_result']=receipt['result']
cid=receipt.get('container_id')
if cid:
    n.require(re.fullmatch('[0-9a-f]{64}',cid),'invalid container ID')
    probe=subprocess.run(g.DOCKER+['inspect',cid],capture_output=True,text=True,timeout=10)
    n.require(probe.returncode!=0 and 'no such' in probe.stderr.lower(),'exact container still exists; do not delete mounted staging')
    r['exact_container_id']=cid;r['container_absent']=True
fd=None
try:
    fd=os.open(g.LOCK,os.O_RDWR|os.O_NOFOLLOW);s=os.fstat(fd)
    n.require(stat.S_ISREG(s.st_mode) and (s.st_dev,s.st_ino)==g.LOCK_ID and s.st_uid==os.getuid() and stat.S_IMODE(s.st_mode)==0o600,'original lock changed')
    fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    r['lock_reacquired_nonblocking']={'device':s.st_dev,'inode':s.st_ino,'uid':s.st_uid,'mode':oct(stat.S_IMODE(s.st_mode))}
finally:
    if fd is not None: os.close(fd);r['postcheck_lock_released']=True
r['candidate_commit']=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
n.require(r['candidate_commit']=='a1558795663e5999785a5586bf6c755c7826071a','candidate changed during attempt')
n.require(not subprocess.check_output(['git','status','--porcelain'],text=True).strip(),'candidate dirty after attempt')
r['upstream_source_recheck_count']=len(policy.checked_source(g.BASE/'monero-fcmp'))
r['applied_overlay_recheck']={}
for name,binding in receipt.get('overlay',{}).get('files',{}).items():
    digest=sha(OUT/'source'/name)
    n.require(digest==binding['changed_sha256'],'post-build source changed: '+name)
    r['applied_overlay_recheck'][name]=digest
binary_path=OUT/'source/build/network/tests/vanguard-policy/vanguard_network_policy'
if binary_path.exists() and (OUT/'binary.sha256').exists():
    r['binary_sha256']=sha(binary_path)
    n.require(r['binary_sha256']==(OUT/'binary.sha256').read_text().split()[0],'native binary digest differs')
if receipt['result'].startswith('PASS_'):
    first,second=[json.loads((OUT/x).read_text()) for x in ('policy01.json','policy02.json')]
    n.require(first==second and (OUT/'policy01.json').read_bytes()==(OUT/'policy02.json').read_bytes(),'native outputs differ')
    n.require(first['result']=='PASS_NATIVE_POLICY_HELPERS_AND_TEMPLATE_ONLY' and first['reward_vectors']==13608 and first['address_vectors']==39 and first['constructions']==24 and first['positive_reset'] is True and first['admitted_non_genesis_blocks']==0 and first['two_peer_network']=='NOT_RUN' and first['mature_root']=='NOT_RUN' and first['launch_ready'] is False,'unexpected native summary')
    events=dict(line.split() for line in (OUT/'memory.events').read_text().splitlines())
    n.require(int(events['oom'])==int(events['oom_kill'])==0,'OOM observed')
    r['native_summary']=first;r['native_outputs_byte_identical']=True
    r['native_json_sha256']=sha(OUT/'policy01.json')
# Save exact public code and small diagnostics, excluding caches and full exported upstream.
retained=E/'native-policy-attempt01';retained.mkdir(mode=0o700)
for p in sorted(OUT.iterdir()):
    if p.is_file() and not (p.name.startswith('source-') and p.suffix=='.tar'):
        shutil.copy2(p,retained/p.name)
if (OUT/'overlay').exists(): shutil.copytree(OUT/'overlay',retained/'overlay')
executed=retained/'executed';executed.mkdir()
for name in n.read_json(n.HERE/'evidence/projection-correction/candidate-inputs.json')['files']:
    target=executed/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(n.ROOT/name,target)
binary=OUT/'source/build/network/tests/vanguard-policy/vanguard_network_policy'
archive_members=[p for p in [binary,OUT/'db-policy01',OUT/'db-policy02'] if p.exists()]
if archive_members:
    archive=E/'stopped-native-state.tar.gz'
    with tarfile.open(archive,'w:gz') as tar:
        for p in archive_members: tar.add(p,arcname=str(p.relative_to(OUT)),recursive=True)
    r['stopped_state_archive']={'path':archive.name,'sha256':sha(archive),'members':[str(p.relative_to(OUT)) for p in archive_members]}
# Exact owned staging only, with native driver receipt retained above.
removed=[]
for p in [OUT/'source',OUT/'cargo-home',OUT/'db-policy01',OUT/'db-policy02',*sorted(OUT.glob('source-*.tar'))]:
    if p.exists():
        n.require(p.parent==OUT and not p.is_symlink(),'unsafe cleanup boundary')
        if p.is_dir(): shutil.rmtree(p)
        else:p.unlink()
        removed.append(str(p.relative_to(RUN)))
r['removed_exact_owned_paths']=removed
r['remaining_staging_entries']=[p.name for p in OUT.iterdir() if p.is_dir() and p.name!='overlay']
n.require(not r['remaining_staging_entries'],'unexpected remaining native staging')
r['result']='PASS_POSTCHECK_AND_OWNED_CLEANUP'
(E/'cleanup-verification.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r,indent=2))
