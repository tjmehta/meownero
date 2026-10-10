"""Execute the exact adaptation block with positive and adversarial byte pins."""
import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import subprocess
import tempfile

root = Path(__file__).resolve().parents[3]
helper = root / 'vanguard/portable-cross-build.py'
tree = ast.parse(helper.read_text())
branch = next(n for n in ast.walk(tree) if isinstance(n, ast.If) and
              any(isinstance(a, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'allocator'
                                                   for t in a.targets) for a in n.body))
start = next(i for i, n in enumerate(branch.body) if isinstance(n, ast.Assign) and
             any(isinstance(t, ast.Name) and t.id == 'allocator' for t in n.targets))
end = next(i for i in range(start + 1, len(branch.body)) if isinstance(branch.body[i], ast.Expr) and
           isinstance(branch.body[i].value, ast.Call) and isinstance(branch.body[i].value.func, ast.Name)
           and branch.body[i].value.func.id == 'save')
code = compile(ast.Module(body=branch.body[start:end + 1], type_ignores=[]), str(helper), 'exec')
old = Path('/storage/data/meownero-tjs1882-3175/randomx-arm07-allocator/intrin_portable.original.h').read_bytes()
patch_bytes = (root / 'vanguard/patches/randomx-aaafe713-windows-arm64-aligned-allocator.patch').read_bytes()
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

def require(condition, message):
    if not condition:
        raise RuntimeError(message)

cases = []
for case in ('exact-pins', 'changed-header', 'changed-patch', 'wrong-target', 'wrong-submodule-pin'):
    with tempfile.TemporaryDirectory(prefix='tjs1882-arm07-sourceguard-') as tmp:
        owned = Path(tmp)
        source = owned / 'source'
        header = source / 'external/randomx/src/intrin_portable.h'
        header.parent.mkdir(parents=True)
        header.write_bytes(old + (b'\n// changed\n' if case == 'changed-header' else b''))
        patch = owned / 'patches/randomx-aaafe713-windows-arm64-aligned-allocator.patch'
        patch.parent.mkdir()
        patch.write_bytes(patch_bytes + (b'\n' if case == 'changed-patch' else b''))
        before = header.read_bytes()
        invocations, saves, receipt = [], [], {'patches': []}

        def run(label, argv, cwd):
            invocations.append(label)
            subprocess.run(argv, cwd=cwd, check=True, timeout=5, stdout=subprocess.DEVNULL)

        namespace = dict(source=source, Path=Path, __file__=str(owned / 'portable-cross-build.py'),
            args=SimpleNamespace(target='windows-x86_64' if case == 'wrong-target' else 'windows-aarch64'),
            PIN={'upstream': {'submodules': {'external/randomx': '0' * 40 if case == 'wrong-submodule-pin' else 'aaafe71322df6602c21a5c72937ac284724ae561'}}},
            tester=SimpleNamespace(require=require, sha=sha), run=run, receipt=receipt, save=lambda: saves.append(True))
        refused = False
        try:
            exec(code, namespace)
        except RuntimeError:
            refused = True
        assert refused == (case != 'exact-pins')
        if refused:
            assert header.read_bytes() == before and not invocations and not receipt['patches']
        else:
            assert sha(header) == 'd5abf99da75d0cbaa68d9503d3568079cc1707bc40ede9a949cd2e49dadbd02a'
            assert len(receipt['patches']) == len(invocations) == len(saves) == 1
        cases.append({'case': case, 'refused_before_mutation': refused,
                      'owned_patch_invocations': len(invocations), 'recorded_patch_rows': len(receipt['patches'])})
prior = subprocess.check_output(['git', 'show', 'HEAD:vanguard/portable-cross-build.py'], cwd=root, text=True)
def finalizers(text):
    return [ast.dump(ast.Module(body=n.finalbody, type_ignores=[]), include_attributes=False)
            for n in ast.walk(ast.parse(text)) if isinstance(n, ast.Try) and n.finalbody]
assert finalizers(prior) == finalizers(helper.read_text())
proof = {'schema': 'meownero-arm07-allocator-source-guards/1',
         'result': 'PASS_EXACT_PLATFORM_PATCH_AND_FOUR_PRE_MUTATION_REFUSALS',
         'helper_sha256': sha(helper), 'cases': cases, 'all_existing_finalizers_AST_unchanged': True,
         'patch_sha256': hashlib.sha256(patch_bytes).hexdigest(), 'native_Windows_ARM_execution': 'UNTESTED'}
Path(__file__).with_suffix('.json').write_text(json.dumps(proof, indent=2) + '\n')
print(proof['result'])
