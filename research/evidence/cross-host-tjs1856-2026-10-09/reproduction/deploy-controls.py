import json,os,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
CLI=Path('~/.local/share/meownero-tests/tjs1856-private/railway')
PROJECT='f46a08ef-dcba-431b-8fb0-a3b2c0dd721e'
ENVIRONMENT='4e5d9d89-594e-464c-a9de-b854ec33e30a'
SERVICE='884ba31d-a288-4f69-9dbb-9e1332501d87'
SCOPE=['--project',PROJECT,'--environment',ENVIRONMENT,'--service',SERVICE]
ENV={**os.environ,'RAILWAY_TOKEN':(CLI.parent/'railway-project.token').read_text().strip()}
ENV.pop('RAILWAY_API_TOKEN',None)
SECRETS=[ENV['RAILWAY_TOKEN']]
def scrub(value):
 for secret in SECRETS:
  value=value.replace(secret,'[redacted]')
 return value
PUBLIC=ROOT/'provider';PUBLIC.mkdir(exist_ok=True)

def cli(label,args,input=None,timeout=60,public=True):
 started=time.monotonic()
 r=subprocess.run([str(CLI),*args],env=ENV,cwd=ROOT,input=input,capture_output=True,text=True,timeout=timeout)
 if public and input is None:
  # Never use public logging for commands whose responses could contain secrets.
  (PUBLIC/(label+'.stdout')).write_text(scrub(r.stdout))
  (PUBLIC/(label+'.stderr')).write_text(scrub(r.stderr))
  (PUBLIC/(label+'.command.json')).write_text(json.dumps({'args':args,'exit':r.returncode,'wall_seconds':time.monotonic()-started},indent=2)+'\n')
 assert r.returncode==0,label+' exit '+str(r.returncode)
 return scrub(r.stdout)
