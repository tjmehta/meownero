"""Execute the real pre-copy host-compiler guard with adverse ELF headers."""
import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile

root = Path(__file__).resolve().parents[3]
source = root / 'vanguard/portable-cross-build.py'
main = next(n for n in ast.parse(source.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'main')
node = next(n for n in main.body if isinstance(n, ast.For) and isinstance(n.target, ast.Name) and n.target.id == 'program')
code = compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec')
cases = []
for label, machine, klass, endian in [('amd64', 62, 2, 1), ('arm64', 183, 2, 1),
                                    ('i686', 3, 1, 1), ('wrong-endian', 62, 2, 2), ('not-ELF', 62, 0, 1)]:
    with tempfile.TemporaryDirectory(prefix='tjs1882-rust-host-') as tmp:
        owned = Path(tmp)
        (owned / 'bin').mkdir()
        header = bytearray(20)
        header[:6] = b'\x7fELF' + bytes([klass, endian])
        header[18:20] = machine.to_bytes(2, 'little')
        for name in ('rustc', 'cargo'):
            (owned / 'bin' / name).write_bytes(header)
        def require(condition, message):
            if not condition:
                raise RuntimeError(message)
        namespace = {'args': SimpleNamespace(rust=owned),
                     'tester': SimpleNamespace(regular=lambda p: p, require=require)}
        passed = True
        try:
            exec(code, namespace)
        except RuntimeError:
            passed = False
        assert passed == (label == 'amd64')
        cases.append({'case': label, 'accepted_header': passed, 'no_workload_or_output_created': True})
proof = {'schema': 'meownero-arm08-Rust-host-ELF-guards/1',
         'result': 'PASS_AMD64_ROLE_AND_FOUR_EARLY_REFUSALS',
         'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'cases': cases,
         'qualification': 'Injected header guard fixture only; actual compiler source separately byte-bound to06; not complete executable validation or native target proof'}
Path(__file__).with_suffix('.json').write_text(json.dumps(proof, indent=2) + '\n')
print(proof['result'])
