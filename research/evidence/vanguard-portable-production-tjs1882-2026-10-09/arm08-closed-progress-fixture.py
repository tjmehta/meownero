"""Real closed progress pipe must preserve the failed build and cleanup metadata."""
import ast
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

root = Path(__file__).resolve().parents[3]
new = (root / 'vanguard/portable-cross-build.py').read_text()
old = subprocess.run(['git', 'show', '556850503ed69223acee2f4dc1b381386dc7b4a1:vanguard/portable-cross-build.py'], cwd=root, capture_output=True, text=True, check=True).stdout

def node(source, name):
    found = [n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef) and n.name == name]
    assert len(found) == 1
    return found[0]

assert ast.dump(node(old, 'contained'), include_attributes=False) == ast.dump(node(new, 'contained'), include_attributes=False)
cases = []
for label, source in [('old', old), ('corrected', new)]:
    with tempfile.TemporaryDirectory() as directory:
        receipt = {'commands': []}
        removed = False
        def require(condition, message):
            if not condition:
                raise RuntimeError(message)
        env = dict(os=os, signal=signal, subprocess=subprocess, time=time, out=Path(directory), receipt=receipt, save=lambda: None, tester=SimpleNamespace(require=require))
        module = ast.Module(body=[node(source, 'run')], type_ignores=[])
        exec(compile(ast.fix_missing_locations(module), label, 'exec'), env)
        before_mask = signal.pthread_sigmask(signal.SIG_BLOCK, set())
        before_handlers = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGINT)}
        read, write = os.pipe()
        os.close(read)
        broken = io.TextIOWrapper(os.fdopen(write, 'wb'), write_through=True)
        stdout = sys.stdout
        try:
            sys.stdout = broken
            try:
                try:
                    env['run']('build', [sys.executable, '-c', 'raise SystemExit(2)'])
                finally:
                    env['run']('build-cleanup', [sys.executable, '-c', 'pass'])
                    removed = True
            except BaseException as error:
                error_type = type(error).__name__
                primary_preserved = isinstance(error, RuntimeError) and str(error) == 'build failed; diagnostics preserved'
        finally:
            sys.stdout = stdout
            try:
                broken.close()
            except BrokenPipeError:
                pass
        assert all(row['reaped'] for row in receipt['commands'])
        assert [row['exit'] for row in receipt['commands']] == [2, 0]
        assert signal.pthread_sigmask(signal.SIG_BLOCK, set()) == before_mask
        assert {s: signal.getsignal(s) for s in before_handlers} == before_handlers
        if label == 'old':
            assert error_type == 'BrokenPipeError' and not primary_preserved and not removed
        else:
            assert error_type == 'RuntimeError' and primary_preserved and removed
        cases.append({'source': label, 'source_sha256': hashlib.sha256(source.encode()).hexdigest(), 'error_type': error_type, 'primary_build_failure_preserved': primary_preserved, 'cleanup_completed_metadata': removed, 'actual_children_reaped': True, 'signal_handlers_and_mask_restored': True})
result = {'schema': 'meownero-arm08-closed-progress-fixture/1', 'result': 'PASS_OLD_MASKING_REPRODUCED_CORRECTED_PRIMARY_PRESERVED', 'contained_finalizer_ast_unchanged': True, 'cases': cases}
Path(__file__).with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n')
print(result['result'])
