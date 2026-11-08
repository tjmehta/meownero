"""Execute the exact assembler-adaptation AST with actual zero-fuzz patching."""
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace

root = Path(__file__).resolve().parents[3]
os.chdir(root)
p = Path('vanguard/portable-cross-build.py').resolve()
m = ast.parse(p.read_text())
nodes = next(n.body for n in ast.walk(m) if isinstance(n, ast.If) and any(isinstance(s, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'assembly' for t in s.targets) for s in n.body))
a = next(i for i, n in enumerate(nodes) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'assembly' for t in n.targets))
z = next(i for i, n in enumerate(nodes[a:], a) if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name) and n.value.func.id == 'save')
code = compile(ast.fix_missing_locations(ast.Module(body=nodes[a:z], type_ignores=[])), str(p), 'exec')
original = Path('build/tjs1882-linux64-attempt02/monero-fcmp/external/randomx/src/jit_compiler_a64_static.S')
cases = []
for case in ['exact', 'wrong_target', 'wrong_pin', 'changed_source', 'changed_patch']:
    with tempfile.TemporaryDirectory() as directory:
        src = Path(directory) / 'source'
        dest = src / 'external/randomx/src'
        dest.mkdir(parents=True)
        shutil.copy2(original, dest / original.name)
        copied = Path(directory) / 'driver.py'
        copied.write_bytes(p.read_bytes())
        (copied.parent / 'patches').mkdir()
        patch = copied.parent / 'patches/randomx-aaafe713-windows-arm64-hidden.patch'
        shutil.copy2(p.with_name('patches') / patch.name, patch)
        if case == 'changed_source':
            (dest / original.name).write_bytes(original.read_bytes() + b'\n')
        if case == 'changed_patch':
            patch.write_bytes(patch.read_bytes() + b'\n')
        calls = []
        def require(ok, message):
            if not ok:
                raise RuntimeError(message)
        def run(label, args, cwd):
            calls.append(label)
            subprocess.run(args, cwd=cwd, check=True, capture_output=True)
        receipt = {'patches': []}
        env = {'__file__': str(copied), 'Path': Path, 'source': src,
               'args': SimpleNamespace(target='windows-i686' if case == 'wrong_target' else 'windows-aarch64'),
               'PIN': {'upstream': {'submodules': {'external/randomx': 'WRONG' if case == 'wrong_pin' else 'aaafe71322df6602c21a5c72937ac284724ae561'}}},
               'tester': SimpleNamespace(require=require, sha=lambda f: hashlib.sha256(Path(f).read_bytes()).hexdigest()),
               'run': run, 'receipt': receipt}
        try:
            exec(code, env)
            result = 'APPLIED'
        except RuntimeError:
            result = 'REFUSED'
        assert (result == 'APPLIED') == (case == 'exact')
        assert calls == (['randomx-arm64-hidden'] if case == 'exact' else [])
        cases.append({'case': case, 'result': result, 'patch_invocations': len(calls)})
result = {'schema': 'meownero-arm08-source-bound-assembler-gates/1', 'result': 'PASS_EXACT_ONLY_FOUR_NEGATIVES_BEFORE_PATCH', 'helper_sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'cases': cases}
Path(__file__).with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n')
print(result['result'])
