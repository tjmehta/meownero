"""Review-only source/process counterexample; no Docker or source mutations."""
from pathlib import Path
import fcntl,hashlib,importlib.util,json,sys
from unittest.mock import patch
r=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('review_provider',r/'kit/vanguard/linux38_docker.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
sys.path.insert(0,str(r/'kit/vanguard/docker'))
import docker_support
# These disjoint inodes model private /tmp versus daemon-host /tmp at the same
# pathname. Real flock behavior is exercised; only Docker observations are mocked.
local=r/'controller-namespace';host=r/'daemon-namespace'
local.mkdir();host.mkdir()
local_lock=local/'heavy.lock';host_lock=host/'heavy.lock'
local_lock.touch(mode=0o600);host_lock.touch(mode=0o600)
binding=r/'binding.fixture.json';binding.write_text('{}')
digest=hashlib.sha256(binding.read_bytes()).hexdigest()
value={'kernel':'same-native-kernel','boot_id_sha256':hashlib.sha256(b'same-boot\n').hexdigest()}
# /output is represented solely by free blocks, not file/mount identity.
lines=['x86_64',value['kernel'],'same-boot',digest+'  /binding','22.04','glibc 2.35',str(7*1024**2),'20000000 4096','20000000 4096','67108864 0 16','100000 100000']
commands=[]
def query(*args):
 commands.append(args)
 if args[:2]==('image','inspect'):return json.dumps([{'Id':'sha256:'+'c'*64,'Os':'linux','Architecture':'amd64'}])
 if args[0]=='create':return 'd'*64
 if args[0]=='start':return '\n'.join(lines)
 raise AssertionError(args)
with host_lock.open('rb') as held:
 fcntl.flock(held,fcntl.LOCK_EX|fcntl.LOCK_NB)
 with host_lock.open('rb') as check:
  try:fcntl.flock(check,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:host_busy_proven=True
  else:raise AssertionError('positive busy-lock control failed')
 with patch.object(p,'LOCK',local_lock):
  with p.shared_lock():local_lock_admitted=True
 with patch.object(p,'_binding',(binding,digest,value)),patch.object(p,'admit'),patch.object(p,'query',side_effect=query),patch.object(p,'unrelated',return_value={'unrelated'}),patch.object(p,'preserved'),patch.object(docker_support,'proof'),patch.object(docker_support,'cleanup_named',return_value={'removed':True}):
  result=p.resources(local)
 create=next(c for c in commands if c[0]=='create')
 mounts=[create[i+1] for i,a in enumerate(create) if a=='--mount']
 assert not any('heavy.lock' in m for m in mounts)
 assert result['owned_probe_removed']
receipt={'schema':'meownero-linux38-review-topology-counterexample/1','candidate':'53112f4b1a0a799c498b25b8376201af2bc39e27','result':'REPRODUCED_SOURCE_GAP','real_host_fixture_lock_busy':host_busy_proven,'distinct_controller_fixture_lock_admitted':local_lock_admitted,'same_boot_binding_witness_accepted':True,'lock_mounted_by_probe':False,'output_identity_in_witness':False,'docker_operations':'MOCKED_ONLY','native_topology_qualification':'NOT_ATTEMPTED','interpretation':'A correct provenance-file bind and kernel boot do not prove that a container controller shares the host heavy lock or output/source mounts. No actual host interference is claimed.'}
(r/'topology-counterexample.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
