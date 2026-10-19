import subprocess,json,os,hashlib
from pathlib import Path
r=Path('~/Developer/ios-builds/tjs1882-abf0b97a');name='tjs1882-arm39-abf0b97a'
env={**os.environ,'PATH':'/opt/homebrew/bin:/usr/bin:/bin'}
base=['/opt/homebrew/bin/limactl','shell',name,'--']
assert json.loads((r/'qualification-public.json').read_text())['result']=='PASS_ACTUAL_NATIVE_ARM_UBUNTU22_RUNNER_QUALIFICATION_MEOWNERO_UNTESTED'
command=base+['sudo','systemd-run','--unit=tjs1882-arm39-abf0b97a-02','--wait','--collect','-p','RuntimeMaxSec=7200','-p','TimeoutStopSec=240','-p','KillMode=mixed','/opt/tjs1882-python/bin/python3.13','-B','/var/lib/tjs1882/source/vanguard/run-portable-linux-ci.py','--inputs','/var/lib/tjs1882/source/input/local39.json','--inputs-sha256','7716e56dcd82f254172a1fb1d867b0a414131121daaeba91beb15024a6e5fd52','--local-provenance','/var/lib/tjs1882/provenance.json','--local-provenance-sha256','365d1bab0e64996ca0d6f3a5650d49e95eba12bc96c367b1942ddf4ee1aec387','--out','/var/lib/tjs1882/attempt02']
(r/'full-controller02-command.json').write_text(json.dumps(command,indent=2)+'\n')
with (r/'full-controller02.log').open('xb') as log: result=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=7500)
(r/'full-controller02-exit.json').write_text(json.dumps({'exit':result.returncode})+'\n')
print('Full ARM39 controller exit',result.returncode,flush=True)
raise SystemExit(result.returncode)
