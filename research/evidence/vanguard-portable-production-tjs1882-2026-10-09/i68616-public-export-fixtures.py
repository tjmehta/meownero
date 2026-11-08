"""Execute old/new public finalizers with hostile private argv/extra fields."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import tempfile

root = Path(__file__).resolve().parents[3]
sources = {'original12': root / 'build/tjs1882-3175-native-ci-payload12/vanguard/run-portable-ci.py',
           'corrected16': root / 'build/tjs1882-3175-i68616-supervisor.py'}
cases = []
with tempfile.TemporaryDirectory(prefix='tjs1882-i68616-public-') as tmp:
    for name, source in sources.items():
        spec = importlib.util.spec_from_file_location(name, source)
        ci = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ci)
        main = next(n for n in ast.parse(source.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'main')
        body = next(n.finalbody for n in main.body if isinstance(n, ast.Try) and n.finalbody)
        out = Path(tmp) / name
        out.mkdir(mode=0o700)
        private, public = out / 'private', out / 'public'
        private.mkdir(mode=0o700)
        public.mkdir(mode=0o700)
        receipt = {'schema': 'meownero-native-windows-ci-check/1', 'result': 'FAIL',
                   'private_extra': 'PRIVATE_WALLET_KEY_SENTINEL',
                   'phases': [{'name': 'journey', 'pid': 1234, 'reaped': True, 'exit': 1,
                               'argv': ['C:\\PRIVATE_WALLET_KEY_SENTINEL\\tester.py', '--out', 'PRIVATE_OUTPUT'],
                               'stderr': 'PRIVATE_WALLET_KEY_SENTINEL'}],
                   'owned_job': {'active_processes': 0, 'total_processes': 15,
                                 'private_extra': 'PRIVATE_WALLET_KEY_SENTINEL',
                                 'children': [{'pid': 1234, 'exit': 1, 'argv': ['PRIVATE_WALLET_KEY_SENTINEL']}]}}
        ci.write(private / 'check-receipt.json', receipt)
        namespace = dict(os=os, signal=signal, json=json, check_root=private, public=public,
                         proof={'result': 'FAIL'}, write=ci.write, public_check=getattr(ci, 'public_check', None))
        exec(compile(ast.Module(body=body, type_ignores=[]), str(source), 'exec'), namespace)
        exported = (public / 'check.json').read_text()
        leaked = 'PRIVATE_WALLET_KEY_SENTINEL' in exported
        assert leaked == (name == 'original12')
        if not leaked:
            safe = json.loads(exported)
            assert safe['phases'] == [{'pid': 1234, 'exit': 1, 'reaped': True, 'name': 'journey'}]
            assert safe['owned_job']['active_processes'] == 0 and safe['owned_job']['children'] == [{'pid': 1234, 'exit': 1}]
            assert 'argv' not in exported and 'stderr' not in exported and 'PRIVATE_OUTPUT' not in exported
        cases.append({'case': name, 'actual_finalizer_executed': True, 'private_sentinel_exported': leaked,
                      'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                      'original_private_execution_receipt_preserved': json.loads((private / 'check-receipt.json').read_text()) == receipt})
result = {'schema': 'meownero-i68616-public-projection-negative-fixtures/1',
          'result': 'PASS_OLD_PRIVATE_ARGV_LEAK_REPRODUCED_NEW_ALLOWLIST_NO_PRIVATE_TEXT',
          'cases': cases, 'native_execution': 'UNTESTED_BY_FIXTURES'}
Path(__file__).with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n')
print(result['result'])
