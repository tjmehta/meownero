"""Exercise native policy guards before lock/build and unchanged finalizers."""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / 'vanguard'))
def load(name):
    spec = importlib.util.spec_from_file_location(name, root / 'vanguard' / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
worker, controller = load('portable-build.py'), load('run-portable-linux-ci.py')
cases = []
original_read = Path.read_text
with tempfile.TemporaryDirectory(prefix='tjs1882-policy-') as tmp:
    base = Path(tmp)
    for target, arch in [('linux-x86_64', 'x86_64'), ('linux-aarch64', 'aarch64')]:
        preparation = {'result': 'PREPARED_OLDER_BUILDER', 'cleanup': {'removed': True},
            'distribution': 'Ubuntu 22.04', 'target': target, 'compiler_execution_substrate': 'NATIVE', 'builder_image': 'fixture'}
        prep = base / (arch + '.json')
        prep.write_text(json.dumps(preparation))
        for memory in (6 * 1024**3 - 1024, 6 * 1024**3):
            def read(path, *args, **kwargs):
                if str(path) == '/proc/meminfo': return 'MemAvailable: ' + str(memory // 1024) + ' kB\n'
                if str(path) == '/etc/os-release': return 'ID=ubuntu\nVERSION_ID="22.04"\n'
                return original_read(path, *args, **kwargs)
            with patch.object(Path, 'read_text', read), patch.object(worker.platform, 'system', return_value='Linux'), patch.object(worker.platform, 'machine', return_value=arch):
                if memory < 6 * 1024**3:
                    lock_calls, command_calls = [], []
                    def bad_lock():
                        lock_calls.append(True)
                        raise AssertionError('policy refusal must precede lock')
                    argv = ['build', '--cache', str(base), '--rust', str(base), '--out', str(base / ('refuse-' + arch)),
                        '--target', target, '--older-builder-receipt', str(prep), '--native-ubuntu22-memory-policy']
                    with patch.object(sys, 'argv', argv), patch.object(worker.tester, 'heavy_lock', bad_lock), patch.object(worker.tester, 'command', side_effect=lambda *a, **kw: command_calls.append(a)):
                        try: worker.main()
                        except RuntimeError as error: assert str(error).startswith('requires 6 GiB')
                        else: raise AssertionError('below6GiB accepted')
                    assert not lock_calls and not command_calls
                    cases.append({'case': target + '-below6GiB', 'lock_acquired': False, 'Docker_or_build_started': False})
                else:
                    policy = worker.native_compile_resources(target, preparation)
                    assert policy['container_memory_bytes'] == policy['container_memory_swap_bytes'] == 4 * 1024**3
                    assert policy['host_minimum_available_bytes'] == policy['measured_available_bytes'] == 6 * 1024**3
                    safe = controller.public_worker_receipt({'native_compile_resources': {**policy, 'argv': ['PRIVATE_MEMORY_SENTINEL']}})
                    assert safe['native_compile_resources'] == policy and 'PRIVATE_' not in json.dumps(safe)
                    cases.append({'case': target + '-exact6GiB', 'numeric_public_policy': policy})
        for platform_name, machine, substrate in [('Darwin', 'arm64', 'NATIVE'), ('Linux', 'x86_64' if arch == 'aarch64' else 'aarch64', 'NATIVE'), ('Linux', arch, 'PREEXISTING_QEMU_AMD64_ON_COLIMA_ARM64')]:
            with patch.object(worker.platform, 'system', return_value=platform_name), patch.object(worker.platform, 'machine', return_value=machine):
                try: worker.native_compile_resources(target, {**preparation, 'compiler_execution_substrate': substrate})
                except RuntimeError: pass
                else: raise AssertionError('policy escaped native scope')
        with patch.object(Path, 'read_text', lambda path, *a, **k: 'MemAvailable: 6291456 kB\n'), patch.object(controller.shutil, 'disk_usage', return_value=SimpleNamespace(free=10 * 1024**3)):
            assert controller.resources(base, minimum_available=6 * 1024**3)['available_memory_bytes'] == 6 * 1024**3
    main = next(n for n in ast.parse((root / 'vanguard/run-portable-linux-ci.py').read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    finalizer = next(n.finalbody for n in main.body if isinstance(n, ast.Try) and n.finalbody)
    private = base / 'exports'
    private.mkdir()
    (private / 'build').mkdir()
    public = private / 'public'
    public.mkdir()
    value = {'schema': 'meownero-portable-build/1', 'result': 'FAILED_ATTEMPT',
        'failure': 'PRIVATE_MEMORY_SENTINEL', 'native_compile_resources': {**policy, 'argv': ['PRIVATE_MEMORY_SENTINEL']},
        'commands': [{'label': 'build', 'exit': 2, 'argv': ['PRIVATE_MEMORY_SENTINEL']}]}
    controller.write(private / 'build/build-receipt.json', value)
    writes = []
    def write(path, receipt):
        assert 'PRIVATE_MEMORY_SENTINEL' not in json.dumps(receipt)
        writes.append(path.name)
        controller.write(path, receipt)
    namespace = dict(controller.__dict__, out=private, public=public, arch='x86_64', lock_identity=None,
                     proof={'result': 'FAIL'}, began=time.monotonic(), write=write)
    exec(compile(ast.Module(body=finalizer, type_ignores=[]), 'bound-linux-public-finalizer', 'exec'), namespace)
    assert writes == ['build.json', 'ci-receipt.json']
    assert json.loads((private / 'build/build-receipt.json').read_text()) == value
    cases.append({'case': 'actual-public-finalizer-cap-host-private-sentinel', 'all_public_writes_inspected': writes, 'private_receipt_unchanged': True})

# Existing protected finalizers must remain structurally identical.
old = ast.parse((root / 'build/tjs1882-3175-native-linux-ci-payload17/vanguard/portable-build.py').read_text())
new = ast.parse((root / 'vanguard/portable-build.py').read_text())
finalizers = lambda tree: [ast.dump(ast.Module(body=n.finalbody, type_ignores=[]), include_attributes=False) for n in ast.walk(tree) if isinstance(n, ast.Try) and n.finalbody]
assert finalizers(old) == finalizers(new)
text = (root / 'vanguard/portable-build.py').read_text()
assert "container_memory = '4g' if compile_resources else '3g'" in text
assert "'--memory=' + container_memory, '--memory-swap=' + container_memory" in text
assert text.count('native_compile_resources(args.target, preparation)') == 2
assert 'timeout 3500 make -j1' in text and "'CARGO_BUILD_JOBS=1'" in text and "'--cpus=2'" in text and "'--pids-limit=256'" in text
result = {'schema': 'meownero-native-linux23-arm24-resource-fixtures/1', 'result': 'PASS', 'cases': cases,
    'worker_finalizers_AST_unchanged': True, 'prior_default_3GiB_preserved': True,
    'actual_native_build': 'UNTESTED_BY_FIXTURES', 'four_GiB_sufficiency': 'UNPROVEN',
    'source_sha256': {p: hashlib.sha256((root / 'vanguard' / p).read_bytes()).hexdigest() for p in ('portable-build.py', 'run-portable-linux-ci.py')}}
Path(__file__).with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n')
print('PASS_NATIVE_SCOPE_BEFORE_LOCK_RESERVE_CAP_PROJECTION_UNCHANGED_FINALIZERS')
