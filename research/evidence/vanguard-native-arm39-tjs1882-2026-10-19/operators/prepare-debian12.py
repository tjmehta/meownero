import importlib.util,json,os,subprocess,shutil,re,hashlib,uuid,time
from pathlib import Path
root=Path('/var/lib/tjs1882');out=root/'debian12-prep01'
spec=importlib.util.spec_from_file_location('tester',root/'source/vanguard/tester.py');tester=importlib.util.module_from_spec(spec);spec.loader.exec_module(tester)
assert json.loads((root/'attempt02/public/ci-receipt.json').read_text())['result']=='PASS_NATIVE_UBUNTU22_BUILD_ARCHIVE_JOURNEY_TEN_CONTROLS_PENDING_REVIEW'
with tester.heavy_lock():
 assert not out.exists() and shutil.disk_usage(root).free>10*1024**3
 assert not subprocess.check_output(['docker','ps','-q'],text=True).strip()
 out.mkdir(mode=0o700);client=out/'anonymous-client';client.mkdir(mode=0o700)
 (client/'config.json').write_text('{"auths":{"https://index.docker.io/v1/":{}},"credHelpers":{"https://index.docker.io/v1/":""}}\n')
 docker=['docker','--config',str(client),'--host','unix:///var/run/docker.sock'];proof={'schema':'meownero-owned-debian12-runtime-preparation/1','result':'FAIL','commands':[]}
 def run(label,argv,timeout):
  began=time.monotonic()
  with (out/(label+'.log')).open('wb') as f:r=subprocess.run(argv,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
  proof['commands'].append({'label':label,'exit':r.returncode,'wall_seconds':round(time.monotonic()-began,3)});assert r.returncode==0,label
  return (out/(label+'.log')).read_text()
 owner=uuid.uuid4().hex;name='tjs1882-abf0b97a-debian12-'+owner;cidfile=out/'container.id';base=None
 try:
  manifest=run('manifest',docker+['manifest','inspect','docker.io/library/debian:12-slim'],90);index=json.loads(manifest)
  rows=[r for r in index['manifests'] if r.get('platform',{}).get('architecture')=='arm64' and r.get('platform',{}).get('os')=='linux']
  assert len(rows)==1 and re.fullmatch('sha256:[0-9a-f]{64}',rows[0]['digest'])
  ref='debian@'+rows[0]['digest'];proof.update(base_manifest=ref,manifest_inspection_sha256=hashlib.sha256(manifest.encode()).hexdigest())
  run('pull',docker+['pull','--platform=linux/arm64',ref],180)
  base=subprocess.check_output(['docker','image','inspect',ref,'--format','{{.Id}}'],text=True).strip()
  assert subprocess.check_output(['docker','image','inspect',base,'--format','{{.Architecture}} {{.Os}}'],text=True).strip()=='arm64 linux'
  script="""set -e
trap 'cat /sys/fs/cgroup/memory.peak > /out/preparation.memory; cat /sys/fs/cgroup/memory.events > /out/preparation.memory-events' EXIT
test "$(. /etc/os-release; echo "$ID:$VERSION_ID")" = debian:12
apt-get -o Acquire::Retries=1 -o Acquire::http::Timeout=30 update
apt-get -o Acquire::Retries=1 -o Acquire::http::Timeout=30 -o APT::Keep-Downloaded-Packages=true --download-only install -y --no-install-recommends python3 ca-certificates
sha256sum /var/cache/apt/archives/*.deb > /out/downloaded-debs.sha256
DEBIAN_FRONTEND=noninteractive apt-get --no-download install -y --no-install-recommends python3 ca-certificates
dpkg-query -W -f='${binary:Package}=${Version}\\n' | sort > /out/packages.txt
sha256sum /var/lib/apt/lists/*InRelease > /out/apt-inrelease.sha256
cat /etc/os-release > /out/environment.txt
getconf GNU_LIBC_VERSION >> /out/environment.txt
python3 --version >> /out/environment.txt
command -v bash tar python3
"""
  (out/'prepare-container.sh').write_text(script)
  run('prepare',docker+['run','--pull=never','--name',name,'--cidfile',str(cidfile),'--label','meownero.invocation='+owner,'--cpus=2','--memory=512m','--memory-swap=512m','--pids-limit=128','--security-opt=no-new-privileges','--ulimit','core=0','-v',str(out)+':/out',base,'/bin/bash','-ec',script],600)
  events=dict(row.split() for row in (out/'preparation.memory-events').read_text().splitlines());peak=int((out/'preparation.memory').read_text())
  assert events['oom']=='0' and events['oom_kill']=='0' and 0<peak<=512*1024**2
  cid=cidfile.read_text().strip();image=run('commit',docker+['commit',cid],120).strip();assert re.fullmatch('sha256:[0-9a-f]{64}',image)
  proof.update(runtime_image=image,base_image=base,environment=(out/'environment.txt').read_text(),peak_memory_bytes=peak,memory_events=events,result='PASS_PREPARED_NATIVE_DEBIAN12_RUNTIME_JOURNEY_UNTESTED')
 finally:
  if cidfile.exists():
   cid=cidfile.read_text().strip();p=json.loads(subprocess.check_output(['docker','inspect',cid],text=True,timeout=15))[0]
   assert p['Id']==cid and p['Name']=='/'+name and p['Image']==base and p['Config']['Labels']['meownero.invocation']==owner
   subprocess.run(['docker','rm','-f',cid],check=True,timeout=20,capture_output=True)
   assert cid not in subprocess.check_output(['docker','ps','-aq','--no-trunc'],text=True,timeout=15).splitlines();proof['owned_container_removed']=True
  (out/'preparation.json').write_text(json.dumps(proof,indent=2)+'\n')
 print(json.dumps(proof,indent=2))
