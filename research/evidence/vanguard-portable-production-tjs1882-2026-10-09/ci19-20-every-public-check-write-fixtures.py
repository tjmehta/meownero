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
sources = {'original16': root / 'build/tjs1882-3175-native-ci-payload16/vanguard/run-portable-ci.py',
           'corrected19': root / 'build/tjs1882-3175-i68619-supervisor.py',
           'corrected20': root / 'build/tjs1882-3175-intel20-supervisor.py'}
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
        receipt = {'schema': 'meownero-native-windows-ci-check/1', 'result': 'PASS_NATIVE_ARCHIVE_JOURNEY',
                   'private_extra': 'PRIVATE_WALLET_KEY_SENTINEL',
                   'phases': [{'name': 'journey', 'pid': 1234, 'reaped': True, 'exit': 0,
                               'argv': ['C:\\PRIVATE_WALLET_KEY_SENTINEL\\tester.py', '--out', 'PRIVATE_OUTPUT'],
                               'stderr': 'PRIVATE_WALLET_KEY_SENTINEL'}],
                   'owned_job': {'active_processes': 0, 'total_processes': 15,
                                 'private_extra': 'PRIVATE_WALLET_KEY_SENTINEL',
                                 'children': [{'pid': 1234, 'exit': 0, 'argv': ['PRIVATE_WALLET_KEY_SENTINEL']}]}}
        ci.write(private / 'check-receipt.json', receipt)
        success = next(n for n in ast.walk(main) if isinstance(n, ast.For) and isinstance(n.iter, ast.List) and n.iter.elts and isinstance(n.iter.elts[0], ast.Tuple) and isinstance(n.iter.elts[0].elts[0], ast.Constant) and n.iter.elts[0].elts[0].value == 'journey.json')
        public_writes = []
        def write(path, value):
            if path.name == 'check.json':
                public_writes.append('PRIVATE_WALLET_KEY_SENTINEL' in json.dumps(value))
            ci.write(path, value)
        namespace = dict(os=os, signal=signal, json=json, check_root=private, public=public,
                         proof={'result': 'PASS_NATIVE_ARCHIVE_JOURNEY_AND_TEN_CONTROLS'}, journey={'result':'PASS_NATIVE_JOURNEY'}, controls={'result':'PASS'}, check=receipt, write=write, public_check=getattr(ci, 'public_check', None))
        exec(compile(ast.Module(body=[success], type_ignores=[]), str(source), 'exec'), namespace)
        exec(compile(ast.Module(body=body, type_ignores=[]), str(source), 'exec'), namespace)
        exported = (public / 'check.json').read_text()
        leaked = 'PRIVATE_WALLET_KEY_SENTINEL' in exported
        assert not leaked
        assert len(public_writes) == 2 and any(public_writes) == (name == 'original16')
        if not leaked:
            safe = json.loads(exported)
            assert safe['phases'] == [{'pid': 1234, 'exit': 0, 'reaped': True, 'name': 'journey'}]
            assert safe['owned_job']['active_processes'] == 0 and safe['owned_job']['children'] == [{'pid': 1234, 'exit': 0}]
            assert 'argv' not in exported and 'stderr' not in exported and 'PRIVATE_OUTPUT' not in exported
        cases.append({'case': name, 'actual_finalizer_executed': True, 'private_sentinel_exported': leaked, 'all_public_check_writes': public_writes, 'actual_success_export_region_executed': True,
                      'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                      'original_private_execution_receipt_preserved': json.loads((private / 'check-receipt.json').read_text()) == receipt})
result = {'schema': 'meownero-ci19-20-all-public-check-write-fixtures/1',
          'result': 'PASS_OLD_SUCCESS_WRITE_LEAK_REPRODUCED_EVERY_NEW_WRITE_PROJECTED',
          'cases': cases, 'native_execution': 'UNTESTED_BY_FIXTURES'}
Path(__file__).with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n')
print(result['result'])
