import ast
from pathlib import Path
root=Path(__file__).resolve().parents[3]
current=(root/'vanguard/run-portable-ci.py').read_text()
def replace_function(s,name,new):
 n=next(n for n in ast.parse(s).body if isinstance(n,ast.FunctionDef) and n.name==name)
 lines=s.splitlines(keepends=True); return ''.join(lines[:n.lineno-1])+new+'\n\n'+''.join(lines[n.end_lineno:])
def function(s,name):
 n=next(n for n in ast.parse(s).body if isinstance(n,ast.FunctionDef) and n.name==name);return '\n'.join(s.splitlines()[n.lineno-1:n.end_lineno])
a=(root/'build/tjs1882-3175-native-ci-payload19/vanguard/run-portable-ci.py').read_text()
for name in ('public_check','windows_check'):a=replace_function(a,name,function(current,name))
a=a.replace('import json\n','import json\nimport datetime\nimport math\nimport ntpath\nimport xml.etree.ElementTree as ET\n',1)
extra='\n\n'.join(function(current,n) for n in ('public_cli_event','public_diagnostic','matching_cli_events','native_cli_event'))
a=a.replace('def public_check(value):',extra+'\n\n\ndef public_check(value):',1)
a=a.replace("write(public / name, public_check(value) if name == 'check.json' else value)","write(public / name, public_check(value) if name == 'check.json' else public_diagnostic(value) if name == 'journey-diagnostic.json' else value)")
a=a.replace("write(public / name, public_check(json.loads(path.read_text())) if name == 'check.json' else json.loads(path.read_text()))", "value = json.loads(path.read_text())\n                    write(public / name, public_check(value) if name == 'check.json' else public_diagnostic(value) if name == 'journey-diagnostic.json' else value)")
(root/'build/tjs1882-2493-i68621-supervisor.py').write_text(a)
b=(root/'build/tjs1882-3175-native-ci-payload20/vanguard/run-portable-ci.py').read_text();b=replace_function(b,'mac_check',function(current,'mac_check'));b=b.replace('def mac_check(', function(current,'snapshot_output')+'\n\n\ndef mac_check(',1);(root/'build/tjs1882-2493-intel22-supervisor.py').write_text(b)
for p in ('build/tjs1882-2493-i68621-supervisor.py','build/tjs1882-2493-intel22-supervisor.py'):ast.parse((root/p).read_text())
