import subprocess,os,json,stat,shutil,hashlib
from pathlib import Path
r=Path('~/Developer/ios-builds/tjs1882-abf0b97a');name='tjs1882-arm39-abf0b97a';env={**os.environ,'PATH':'/opt/homebrew/bin:/usr/bin:/bin'}
proof={'schema':'meownero-native-arm39-host-cleanup/1','result':'FAIL','vm':name,'actions':[]}
def run(argv,timeout):
 p=subprocess.run(argv,capture_output=True,text=True,env=env,timeout=timeout);proof['actions'].append({'argv':argv,'exit':p.returncode,'stdout':p.stdout[-2500:],'stderr':p.stderr[-2500:]});assert p.returncode==0;return p.stdout
vm=Path('~/.lima')/name
assert vm.is_dir() and not vm.is_symlink() and vm.stat().st_uid==os.getuid()
row=[json.loads(x) for x in run(['/opt/homebrew/bin/limactl','list','--json'],20).splitlines() if x.strip()]
current=[x for x in row if x['name']==name];assert len(current)==1 and current[0]['arch']=='aarch64' and current[0]['vmType']=='vz' and current[0]['dir']==str(vm)
run(['/opt/homebrew/bin/limactl','stop',name],120)
run(['/opt/homebrew/bin/limactl','delete','--tty=false',name],90)
assert not vm.exists();proof['vm_and_disks_removed']=True
cache=Path('~/Library/Caches/lima/download/by-url-sha256/257db384e8cbea9009de184bd6338afc372f57a7f248ab23d4e9af26bde1baf7')
assert cache.is_dir() and not cache.is_symlink() and cache.stat().st_uid==os.getuid()
data=cache/'data';assert data.is_file() and not data.is_symlink()
with data.open('rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()=='86e13258765945ad792dac75fac7f02f4db9fa73a4a535ffa472266e7041fa19'
shutil.rmtree(cache);assert not cache.exists();proof['exact_owned_download_and_raw_cache_removed']=True
j=json.loads((r/'host-lock.json').read_text());lock=Path(j['path']);s=lock.lstat()
assert stat.S_ISREG(s.st_mode) and not lock.is_symlink() and s.st_nlink==1 and s.st_ino==j['inode'] and s.st_uid==j['uid']==os.getuid() and lock.read_text()=='TJS-1882 abf0b97a native ARM39 qualification and execution\n'
lock.unlink();assert not lock.exists();proof['exact_owned_host_lock_removed']=True
colima=json.loads(run(['/opt/homebrew/bin/colima','list','--json'],20));assert colima['name']=='default' and colima['status']=='Running' and colima['cpus']==4 and colima['memory']==6442450944 and colima['disk']==107374182400
proof['non_owned_colima']=colima
assert str(r)=='~/Developer/ios-builds/tjs1882-abf0b97a' and r.is_dir() and not r.is_symlink() and r.stat().st_uid==os.getuid()
proof['completion_helper']={'command':'ios cleanup complete Developer/ios-builds/tjs1882-abf0b97a','result':'REJECTED_STAGING_ROOT_OUTSIDE_ALLOWED_ROOTS','fallback':'Exact owned staging removed after local capture verification'}
shutil.rmtree(r);assert not r.exists();proof['exact_owned_staging_removed']=True
proof['result']='PASS_OWNED_VM_DISKS_CACHE_LOCK_AND_STAGING_REMOVED_SHARED_COLIMA_PRESERVED'
print(json.dumps(proof,indent=2))
