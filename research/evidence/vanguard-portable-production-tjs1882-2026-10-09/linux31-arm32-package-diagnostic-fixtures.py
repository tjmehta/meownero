"""Exercise exact controller workers, primary errors and fixed public diagnostics."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

root = Path(__file__).resolve().parents[3]
evidence = Path(__file__).parent
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
cases = []
for number, payload, input_name in [
    (31, 'build/tjs1882-d67e-native-linux-ci-payload27', 'linux-build-inputs.json'),
    (32, 'build/tjs1882-d67e-native-linux-arm-ci-payload28', 'linux-arm-build-inputs.json'),
]:
    source = evidence / f'linux{number}-package-controller.source.py'
    frozen = root / payload
    old = frozen / 'vanguard/run-portable-linux-ci.py'
    inputs = json.loads((frozen / 'ci/tjs1882' / input_name).read_text())
    current_ast, old_ast = ast.parse(source.read_text()), ast.parse(old.read_text())
    functions = lambda tree: {n.name: ast.dump(n) for n in tree.body if isinstance(n, ast.FunctionDef)}
    current, original = functions(current_ast), functions(old_ast)
    assert set(current) - set(original) == {'package_failure'}
    assert [name for name in original if current[name] != original[name]] == ['worker']
    assert current['main'] == original['main']
    spec = importlib.util.spec_from_file_location(f'controller{number}', source)
    ci = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ci)
    ci.ROOT = frozen
    saved_argv = sys.argv
    with tempfile.TemporaryDirectory() as directory, patch.object(sys, 'path', [str(frozen / 'vanguard'), *sys.path]):
        out = Path(directory)
        (out / 'public').mkdir()
        (out / 'build').mkdir()
        (out / 'build/build-receipt.json').write_text(json.dumps({'source_lock': 'PRIVATE_SEED_SENTINEL'}))
        try:
            ci.worker('package', inputs, out)
        except AssertionError as error:
            assert str(error) == 'source lock mismatch'
        else:
            raise AssertionError('actual preserved package guard did not reject')
        public = out / 'public/package-diagnostic.json'
        value = json.loads(public.read_text())
        assert value['source_module'] == 'package-portable.py' and value['source_line'] == 35
        assert value['source_sha256'] == sha(frozen / 'vanguard/package-portable.py')
        assert value['failure_type'] == 'AssertionError'
        assert 'PRIVATE_SEED_SENTINEL' not in public.read_text()
        assert not (out / 'package').exists()
        cases.append({'controller': number, 'case': 'exact-preserved-package-source-pin-refusal',
                      'source_line': 35, 'primary_error_preserved': True, 'package_not_created': True,
                      'bound_public_source_context': True, 'scope': 'ACTUAL_PRESERVED_PACKAGE_MAIN'})
        public.unlink()

        # Synthetic exception seams verify privacy and primary-error retention,
        # including a secondary diagnostic write failure. They are not a claim
        # about the inner failure in the actual native Linux27/ARM28 runs.
        for name, error, frame_name, phase, export_failure in [
            ('license-assertion', AssertionError('PRIVATE_SEED_SENTINEL'), 'portable_licenses.py', 'package', False),
            ('process-error', ci.subprocess.CalledProcessError(1, ['PRIVATE_SEED_SENTINEL']), 'package-portable.py', 'package', False),
            ('OS-error', OSError('PRIVATE_SEED_SENTINEL'), 'package-portable.py', 'package', False),
            ('cancel', KeyboardInterrupt('PRIVATE_SEED_SENTINEL'), 'package-portable.py', 'package', False),
            ('unknown-private-frame', RuntimeError('PRIVATE_SEED_SENTINEL'), 'PRIVATE_SEED_SENTINEL.py', 'package', False),
            ('secondary-export-failure', AssertionError('PRIVATE_SEED_SENTINEL'), 'package-portable.py', 'package', True),
            ('unrelated-prepare-error', AssertionError('PRIVATE_SEED_SENTINEL'), 'package-portable.py', 'prepare', False),
        ]:
            scope = {'error': error}
            function = compile('def main():\n    raise error\n', str(frozen / 'vanguard' / frame_name), 'exec')
            exec(function, scope)
            writes = []
            def write(path, value):
                assert path == public
                assert 'PRIVATE_SEED_SENTINEL' not in json.dumps(value)
                writes.append(value)
                if export_failure:
                    raise OSError('PRIVATE_SECONDARY_SENTINEL')
                ci_write(path, value)
            ci_write = ci.write
            with patch.object(ci, 'load', return_value=SimpleNamespace(main=scope['main'])), patch.object(ci, 'write', write):
                try:
                    ci.worker(phase, inputs, out)
                except BaseException as observed:
                    assert observed is error
                else:
                    raise AssertionError('primary error lost')
            assert len(writes) == (0 if phase != 'package' else 1)
            if phase == 'package':
                value = writes[0]
                assert set(value) == {'schema', 'phase', 'failure_type', 'source_module', 'source_line', 'source_sha256'}
                assert value['phase'] == 'PACKAGE'
                if frame_name.startswith('PRIVATE_'):
                    assert value['source_module'] == 'UNKNOWN' and value['source_line'] is None and value['source_sha256'] is None
                else:
                    assert value['source_module'] == frame_name and value['source_line'] == 2
                    assert value['source_sha256'] == inputs['source_files']['vanguard/' + frame_name]
                if export_failure:
                    assert error.__notes__ == ['PACKAGE_DIAGNOSTIC_EXPORT_FAILED']
                    assert not public.exists()
                else:
                    assert 'PRIVATE_SEED_SENTINEL' not in public.read_text()
                    public.unlink()
            cases.append({'controller': number, 'case': name, 'primary_error_identity_retained': True,
                          'public_diagnostic_writes': len(writes), 'private_exception_argv_path_exported': False,
                          'scope': 'EXACT_WORKER_WITH_SYNTHETIC_EXCEPTION_SEAM'})
        with patch.object(ci, 'load', return_value=SimpleNamespace(main=lambda: None)):
            ci.worker('package', inputs, out)
        assert not public.exists()
        cases.append({'controller': number, 'case': 'success', 'diagnostic_created': False})
    sys.argv = saved_argv

value = {'schema': 'meownero-linux31-arm32-package-diagnostic-fixtures/1', 'result': 'PASS',
         'source_sha256': {str(n): sha(evidence / f'linux{n}-package-controller.source.py') for n in (31, 32)},
         'fixture_source_sha256': sha(Path(__file__)), 'cases': cases,
         'all_other_functions_including_controller_main_finalizers': 'AST_UNCHANGED',
         'actual_native_package_failure_cause': 'UNKNOWN', 'native_build_or_retry_started': False}
Path(__file__).with_suffix('.json').write_text(json.dumps(value, indent=2) + '\n')
print('PASS', len(cases), 'exact-controller diagnostic cases')
