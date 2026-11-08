import hashlib,json,subprocess,platform,sys,os,shutil
from pathlib import Path
root=Path('/var/lib/tjs1882')
q=root/'qualification'
def run(argv): return subprocess.check_output(argv,text=True,timeout=20).strip()
def sha(p):
 with Path(p).open('rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()
name='tjs1882-arm39-c517cc7b-b'
host=json.loads((q/'host-evidence.json').read_text())
assert host['architecture']=='arm64' and host['vm']['arch']=='aarch64' and host['vm']['vmType']=='vz'
assert host['image_sha256']=='86e13258765945ad792dac75fac7f02f4db9fa73a4a535ffa472266e7041fa19'
assert host['vm']['config']['vmOpts']['vz']['rosetta']['enabled'] is False
assert not host['vm']['config'].get('mounts')
assert platform.system()=='Linux' and platform.machine()=='aarch64'
assert sys.version_info>=(3,13)
release=dict(x.split('=',1) for x in Path('/etc/os-release').read_text().splitlines() if '=' in x)
assert release['ID'].strip('"')=='ubuntu' and release['VERSION_ID'].strip('"')=='22.04'
assert run(['getconf','GNU_LIBC_VERSION'])=='glibc 2.35'
features=[sorted(set(x.split(':',1)[1].split())) for x in Path('/proc/cpuinfo').read_text().splitlines() if x.startswith('Features')]
assert features and all({'aes','pmull','sha1','sha2'}<=set(x) for x in features)
info=json.loads(run(['docker','info','--format','{{json .}}']))
assert info['OSType']=='linux' and info['Architecture']=='aarch64'
assert info['DockerRootDir']=='/var/lib/docker' and info['Name']=='lima-'+name
assert not run(['docker','ps','-q'])
assert not Path('/.dockerenv').exists() and not Path('/run/.containerenv').exists()
mem=int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))*1024
assert mem>=6*1024**3 and shutil.disk_usage(root).free>=10*1024**3
assert not any(x.startswith(('GITHUB_','RUNNER_')) for x in os.environ)
evidence={'schema':'meownero-owned-native-runner-qualification/1','source_commit':'630f6fbcd84e8475816da823a1c15197226ff4d4','host':host,'guest':{'system':platform.system(),'architecture':platform.machine(),'release':release,'kernel':run(['uname','-r']),'glibc':run(['getconf','GNU_LIBC_VERSION']),'cpu_features':features,'python':sys.version,'python_executable_sha256':sha(sys.executable),'docker':{k:info[k] for k in ('ID','Name','OSType','Architecture','DockerRootDir','ServerVersion','NCPU','MemTotal')},'docker_context':json.loads(run(['docker','context','inspect'])),'machine_id_sha256':sha('/etc/machine-id'),'boot_id_sha256':sha('/proc/sys/kernel/random/boot_id'),'available_memory_bytes':mem,'free_disk_bytes':shutil.disk_usage(root).free,'package_inventory_sha256':sha(q/'packages-after.txt'),'downloaded_debs_manifest_sha256':sha(q/'downloaded-debs.sha256'),'apt_inrelease_manifest_sha256':sha(q/'repository-inrelease.sha256')},'result':'PASS_ACTUAL_NATIVE_ARM_UBUNTU22_RUNNER_QUALIFICATION_MEOWNERO_UNTESTED'}
e=q/'qualification-private.json';e.write_text(json.dumps(evidence,indent=2)+'\n')
p={'schema':'meownero-owned-native-linux-runner/1','issue':'TJS-1882','target':'linux-aarch64','environment':name,'physical_host_architecture':host['architecture'],'machine_id_sha256':evidence['guest']['machine_id_sha256'],'boot_id_sha256':evidence['guest']['boot_id_sha256'],'docker_id':info['ID'],'docker_name':info['Name'],'qualification_evidence_sha256':sha(e)}
(root/'provenance.json').write_text(json.dumps(p,indent=2)+'\n')
public=json.loads(json.dumps(evidence));public['qualification_evidence_sha256']=sha(e)
for k in ('ID','Name'): public['guest']['docker'].pop(k)
public['host']['vm']={k:host['vm'][k] for k in ('vmType','arch','cpus','memory','disk','HostOS','HostArch')}
public['guest']['docker_context']=[{'Name':'default','Host':'unix:///var/run/docker.sock'}]
public['guest']['docker_id_sha256']=hashlib.sha256(info['ID'].encode()).hexdigest()
(q/'qualification-public.json').write_text(json.dumps(public,indent=2)+'\n')
print(public['result']);print('provenance_sha256',sha(root/'provenance.json'));print('qualification_sha256',sha(e))
