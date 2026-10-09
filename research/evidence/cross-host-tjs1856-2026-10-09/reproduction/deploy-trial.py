from pathlib import Path
from datetime import datetime,timezone,timedelta
import importlib.util,json,os,secrets,subprocess,time,urllib.request,urllib.error
ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('controls',ROOT/'deploy-controls.py');c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
TOKEN=secrets.token_hex(32);c.SECRETS.append(TOKEN)
URL=None;proxy=None;domain=None;started=time.monotonic()
record={'result':'INCOMPLETE','started_utc':datetime.now(timezone.utc).isoformat(),'operator_cleanup_deadline_utc':(datetime.now(timezone.utc)+timedelta(seconds=2400)).isoformat(),'project':c.PROJECT,'environment':c.ENVIRONMENT,'service':c.SERVICE,'free_credit':{'usd':5.0,'provenance':'parent browser handoff 2026-10-09T05:00:18Z; supported project token usage query lacked billing access'},'cleanup':{}}
def save():
 (c.PUBLIC/'execution.json').write_text(json.dumps(record,indent=2)+'\n')
def objects(value):
 if isinstance(value,dict):
  yield value
  for item in value.values():yield from objects(item)
 elif isinstance(value,list):
  for item in value:yield from objects(item)
def remote(route,body=None,auth=True):
 req=urllib.request.Request(URL+'/'+route,json.dumps(body or {}).encode(),{'Content-Type':'application/json',**({'Authorization':'Bearer '+TOKEN} if auth else {})})
 deadline=time.monotonic()+30
 while True:
  try:
   with urllib.request.urlopen(req,timeout=40) as r:return json.load(r)
  except urllib.error.HTTPError as err:
   if err.code not in (404,502,503) or not (route in ('state','rpc') or not auth) or time.monotonic()>=deadline:raise
   record.setdefault('edge_read_retries',[]).append({'route':route,'authenticated':auth,'status':err.code,'body':err.read(2048).decode(errors='replace')})
   time.sleep(1)
save()
try:
 c.cli('set-control-secret',['variable','set','MEOWNERO_CONTROL_TOKEN','--stdin','--skip-deploys',*c.SCOPE,'--json'],input=TOKEN,public=False)
 record['control_secret_set']=True;save()
 p=json.loads(c.cli('tcp-create',['tcp-proxy','create','--port','19080',*c.SCOPE,'--json']))
 for row in objects(p):
  if row.get('domain') and row.get('proxyPort'):
   proxy=row;break
 assert proxy,'native proxy endpoint unavailable'
 record['proxy']=proxy;save()
 d=json.loads(c.cli('domain-create',['domain','--port','8080',*c.SCOPE,'--json']))
 for row in objects(d):
  if isinstance(row.get('domain'),str):domain=row;break
 assert domain,'HTTPS endpoint unavailable'
 URL='https://'+domain['domain'].removeprefix('https://').rstrip('/')
 record['domain']=domain;save()
 output=c.cli('source-upload',['up',str(ROOT/'upload'),'--path-as-root','--detach','--json',*c.SCOPE],timeout=180)
 record['upload_started']=True;save()
 uploaded=json.loads(c.cli('uploaded-deployment-list',['deployment','list',*c.SCOPE,'--json']))
 record['deployment_id']=uploaded[0]['id'];save()
 print('Railway private source uploaded; waiting for bounded preflight',flush=True)
 until=time.monotonic()+300
 while True:
  try:
   state=remote('state');break
  except OSError:
   assert time.monotonic()<until,'provider startup deadline'
   query='query($id:String!){deployment(id:$id){id status deploymentStopped}}'
   observed=json.loads(c.cli('startup-liveness',['api',query,'--variables',json.dumps({'id':record['deployment_id']}),'--compact']))
   status=observed['data']['deployment']['status']
   assert not (status in ('SUCCESS','FAILED','CRASHED','REMOVED') and observed['data']['deployment']['deploymentStopped']),'native provider deployment stopped during startup'
   time.sleep(2)
 assert state['architecture'] in ('x86_64','AMD64')
 expected='a1c98d4fcf69402e4850467984bb39a5c76bb244fe23ed7766110f7f20c386b0'
 assert state['process']['exe_sha256']==expected
 limit=int(state['memory.max']);assert limit>0 and int(state['memory.peak'])<limit
 events=dict(line.split() for line in state['memory.events'].splitlines());assert int(events['oom'])==int(events['oom_kill'])==0
 record['runtime_preflight']=state
 record['upload_manifest']=json.loads((ROOT/'upload-manifest.json').read_text())
 record['local_package_image']=json.loads((ROOT/'package-image.json').read_text())
 versions=remote('rpc',{'path':'json_rpc','body':{'jsonrpc':'2.0','id':'0','method':'get_info'}})
 record['runtime_info']=versions
 meta_deadline=time.monotonic()+90
 while True:
  deployments=json.loads(c.cli('deployment-list',['deployment','list',*c.SCOPE,'--json']))
  exact=[row for row in deployments if row['id']==record['deployment_id']]
  if exact and exact[0]['status']=='SUCCESS' and exact[0]['meta'].get('imageDigest','').startswith('sha256:'):
   break
  assert time.monotonic()<meta_deadline,'deployed image metadata deadline'
  time.sleep(2)
 record['deployment_metadata']=deployments
 assert exact[0]['meta']['serviceManifest']['deploy']['restartPolicyType']=='NEVER','provider restart policy differs'
 record['anonymous_refusals']=[]
 for route in ['state','restart','stop','rpc']:
  try:remote(route,auth=False)
  except urllib.error.HTTPError as err:
   assert err.code in (401,403,404),'anonymous control was not denied'
   record['anonymous_refusals'].append({'route':route,'status':err.code,'body':err.read(2048).decode(errors='replace')})
  else:raise AssertionError('anonymous control accepted')
 record['forbidden_refusals']=[]
 for payload in [{'path':'json_rpc','body':{'method':'generateblocks'}},{'path':'send_raw_transaction','body':{}}]:
  try:remote('rpc',payload)
  except urllib.error.HTTPError as err:
   assert err.code in (401,403,404),'forbidden remote RPC was not denied'
   record['forbidden_refusals'].append({'payload':payload,'status':err.code,'body':err.read(2048).decode(errors='replace')})
  else:raise AssertionError('remote mining/submission permitted')
 assert remote('state')['process']['exe_sha256']==expected,'authorized peer unavailable after refusal checks'
 healthy=remote('rpc',{'path':'json_rpc','body':{'jsonrpc':'2.0','id':'0','method':'get_info'}})
 assert healthy['result']['status']=='OK','authorized read RPC unavailable after refusal checks'
 record['post_refusal_authorized_info']=healthy
 record['control_refusals']='PASS';save()
 # Freeze all actual provider metadata before local wallets/funding start.
 config=json.loads((ROOT/'native-inputs.json').read_text())
 config['provider_preflight']=record.copy()
 config['environment'].update({'MEOWNERO_REMOTE_CONTROL_URL':URL,'MEOWNERO_CONTROL_TOKEN':TOKEN,
 'MEOWNERO_PEER_HOST':proxy['domain'],'MEOWNERO_PEER_PORT':str(proxy['proxyPort']),
 'MEOWNERO_REMOTE_DAEMON_SHA256':expected,'MEOWNERO_REMOTE_MEMORY_LIMIT_BYTES':str(limit)})
 print('Native Railway preflight PASS; starting four-payment ARM witness',flush=True)
 ssh=['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=10','build-mac','python3 ~/Developer/tjs1856-d779915e/run-cross-host-build-mac.py']
 with (c.PUBLIC/'native-run.stdout').open('w') as stdout,(c.PUBLIC/'native-run.stderr').open('w') as stderr:
  proc=subprocess.run(ssh,input=json.dumps(config),text=True,stdout=stdout,stderr=stderr,timeout=1660)
 record['native_host_exit']=proc.returncode;assert proc.returncode==0,'native host witness failed'
 record['result']='NATIVE_HOST_COMPLETED_REQUIRES_RAW_VERDICT'
except BaseException as err:
 record['result']='FAIL';record['failure']=type(err).__name__+': '+c.scrub(str(err));raise
finally:
 if URL:
  try:record['cleanup']['control_stop']=remote('stop')
  except OSError:record['cleanup']['control_stop']='already stopped or unreachable; provider removal required'
 try:record['cleanup']['control-variable-delete']=c.cli('control-variable-delete',['variable','delete','MEOWNERO_CONTROL_TOKEN',*c.SCOPE,'--json'],public=False)
 except Exception as err:record['cleanup']['control-variable-delete']=type(err).__name__+': '+c.scrub(str(err))
 for label,args in [('deployment-down',['down',*c.SCOPE,'--yes']),('tcp-delete',['tcp-proxy','delete','19080',*c.SCOPE,'--yes','--json'])]:
  try:record['cleanup'][label]=c.cli(label,args)
  except Exception as err:record['cleanup'][label]=type(err).__name__+': '+c.scrub(str(err))
 if domain:
  try:record['cleanup']['domain-delete']=c.cli('domain-delete',['domain','delete',domain['domain'],*c.SCOPE,'--yes','--json'])
  except Exception as err:record['cleanup']['domain-delete']=type(err).__name__+': '+c.scrub(str(err))
 record['cleanup']['status']=json.loads(c.cli('cleanup-status',['status','--json']))
 record['wall_seconds']=time.monotonic()-started;record['finished_utc']=datetime.now(timezone.utc).isoformat();save()
 print('Finite deployment attempt finished; cleanup evidence saved',flush=True)
