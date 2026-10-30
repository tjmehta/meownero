import ast,json,subprocess,sys
from pathlib import Path
sys.path.insert(0,'vanguard/network')
import profile_executor as e,profile_dispatch as d,profile_handoff as h,profile_packet as p,profile_contract as c
root=Path.cwd();base='e9cb885fbf9513801fca216fe033df7fad38f58a'
index=c.json_file(c.HERE/'integration/inputs.json')
old=json.loads(subprocess.check_output(['git','show',base+':vanguard/network/integration/inputs.json']))
changed=[k for k in set(old)|set(index) if old.get(k)!=index.get(k)]
assert set(changed)=={'candidate_files','installed_ingress_authorization_document'}
for name in ['source-plan.json','lifecycle-packet.json','unit-manifest.json','completion.schema.json']:
 path='vanguard/network/integration/'+name
 assert (root/path).read_bytes()==subprocess.check_output(['git','show',base+':'+path])
assert len(p.render(p.source_plan())['records'])==55 and len(p.units(p.source_plan()))==8
assert e.QUALIFIED_ROOT==d.QUALIFIED_OS==h.QUALIFIED_BOOTSTRAPS=={}
assert index['platform_bootstrap_sha256'] is None
cap=c.json_file(c.HERE/'integration/outer-capabilities.json')
assert all(v is None for v in cap['capabilities'].values())
for path in c.HERE.glob('*.py'):ast.parse(path.read_text())
for name,sha in {**index['reference']['repository_files'],**index['candidate_files']}.items():
 assert c.digest((root/name).read_bytes())==sha,name
manifest=c.json_file(c.HERE/'integration/manager-source-manifest.json')
for name,sha in manifest['source_sha256'].items():assert c.digest((root/name).read_bytes())==sha,name
print(json.dumps(dict(result='PASS_SOURCE_ONLY',changed_input_sections=sorted(changed),packet_records=55,unit_calls=8,
 manager_bindings=len(manifest['source_sha256']),registries_empty=True,capabilities_null=True,native_execution='NOT_RUN'),indent=2))
