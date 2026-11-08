import ast
from pathlib import Path
r=Path(__file__).resolve().parents[3]
current=(r/'vanguard/run-portable-linux-ci.py').read_text()
def fn(s,name):
 n=next(n for n in ast.parse(s).body if isinstance(n,ast.FunctionDef) and n.name==name);return '\n'.join(s.splitlines()[n.lineno-1:n.end_lineno])
def replace(s,name,new):
 n=next(n for n in ast.parse(s).body if isinstance(n,ast.FunctionDef) and n.name==name);lines=s.splitlines(keepends=True);return ''.join(lines[:n.lineno-1])+new+'\n\n'+''.join(lines[n.end_lineno:])
for old,new,label,target in [('17','23','','linux-x86_64'),('18','24','arm-','linux-aarch64')]:
 s=(r/f'build/tjs1882-3175-native-linux-{label}ci-payload{old}/vanguard/run-portable-linux-ci.py').read_text()
 for name in ['resources','public_worker_receipt']:s=replace(s,name,fn(current,name))
 needle="'--depends-sources', str(cache / 'depends-sources')],";assert s.count(needle)==1;s=s.replace(needle,"'--depends-sources', str(cache / 'depends-sources'), '--native-ubuntu22-memory-policy'],")
 needle="    assert inputs['schema'] == 'meownero-private-native-linux-build-inputs/1'\n";assert s.count(needle)==1
 guard="    policy = {'scope': 'FRESH_NATIVE_UBUNTU22_ONLY', 'target': '"+target+"', 'container_memory_bytes': 4 * 1024**3, 'container_memory_swap_bytes': 4 * 1024**3, 'host_minimum_available_bytes': 6 * 1024**3}\n    assert inputs['compile_resource_policy'] == policy, 'architecture-bound compile resource policy mismatch'\n"
 s=s.replace(needle,needle+guard)
 s=s.replace('resources(out.parent)',"resources(out.parent, minimum_available=policy['host_minimum_available_bytes'])")
 s=s.replace("resources(out.parent, 5 if name == 'runtime' else 10)","resources(out.parent, 5 if name == 'runtime' else 10, policy['host_minimum_available_bytes'])")
 ast.parse(s);(r/f'build/tjs1882-2493-linux{new}-controller.py').write_text(s)
