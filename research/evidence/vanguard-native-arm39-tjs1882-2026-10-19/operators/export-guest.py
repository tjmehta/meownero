import json,tarfile,hashlib,io,subprocess
from pathlib import Path
root=Path('/var/lib/tjs1882');members={}
for directory in ('qualification','qualification-hwe'):
 for name in ('packages-before.txt','packages-after.txt','downloaded-debs.sha256','python-executable.sha256','repository-inrelease.sha256','boot-files.sha256','candidate.txt','qualification-public.json'):
  p=root/directory/name
  if p.is_file() and not p.is_symlink():members[directory+'/'+name]=p
for attempt in ('attempt01','attempt02'):
 public=root/attempt/'public'
 if public.is_dir():
  for p in public.glob('*.json'):
   assert p.is_file() and not p.is_symlink();json.loads(p.read_text());members[attempt+'/public/'+p.name]=p
for name in ('cgroup-diagnostic.json','attempt01-cleanup.json','final-guest-cleanup.json','live-build-resources.json'):
 p=root/name
 if p.is_file() and not p.is_symlink():members[name]=p
for directory,names in {
 'attempt02/builder':('preparation.memory','preparation.memory-events'),
 'attempt02/build':('build.memory','build.memory-events'),
 'attempt02/runtime':('runtime.memory','runtime.memory-events','environment.txt'),
 'debian12-prep01':('preparation.json','downloaded-debs.sha256','packages.txt','apt-inrelease.sha256','environment.txt','preparation.memory','preparation.memory-events','prepare-container.sh','manifest.log'),
 'debian12-runtime01':('runtime.memory','runtime.memory-events','environment.txt'),
 'debian12-runtime01/journey':('result.json',),
 'debian12-runtime01/controls':('controls.json',),
}.items():
 for name in names:
  p=root/directory/name;assert p.is_file() and not p.is_symlink();members[directory+'/'+name]=p
p=root/'debian12-runtime01/check-receipt.json';check=json.loads(p.read_text());check.pop('argv');check['cleanup']={'removed':check['cleanup']['removed']};check['execution_scope']='Native ARM64 Debian12 container userland, on Ubuntu22 HWE6.8 guest; not a Debian kernel or bare-metal host'
p=root/'debian12-runtime01/check-public.json';p.write_text(json.dumps(check,indent=2)+'\n');members['debian12-runtime01/check-public.json']=p
out=root/'public-evidence.tar.gz'
with tarfile.open(out,'w:gz') as stream:
 manifest={}
 for name,p in members.items():
  assert p.stat().st_size<5*1024**2
  stream.add(p,arcname=name);manifest[name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
 p=root/'attempt01/builder/prepare.log'
 if p.is_file():
  tail='\n'.join(p.read_text(errors='replace').splitlines()[-8:])+'\n';name='attempt01/prepare-tail.txt';data=tail.encode();info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o600;stream.addfile(info,io.BytesIO(data));manifest[name]={'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
 data=(json.dumps(manifest,indent=2)+'\n').encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(data);info.mode=0o600;stream.addfile(info,io.BytesIO(data))
print('Public evidence',len(members),'files',out.stat().st_size,'bytes',hashlib.sha256(out.read_bytes()).hexdigest())
