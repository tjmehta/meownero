#!/usr/bin/env python3
"""Source-bound declaration adaptation fixtures; no compiler or workload launch."""
import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path
import tarfile
import tempfile
from types import SimpleNamespace


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--kit17', type=Path, required=True)
    parser.add_argument('--helper', type=Path, required=True)
    parser.add_argument('--preimage', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    require(sha(args.kit17) == 'd466b93cb9622c7d291e15cf35dbba0e3e44d331d9bc34cea874c2a5e97b070a', 'kit17 binding')
    with tarfile.open(args.kit17) as kit:
        original = kit.extractfile('vanguard/portable-cross-build.py').read()
    require(hashlib.sha256(original).hexdigest() == '161d06bc0d7a6c9a90627061d84a361ab7bf68ee27c86b9b3f8f3e606ee82c47', 'prior helper binding')
    before = ast.parse(original)
    after = ast.parse(args.helper.read_bytes())
    compile(after, str(args.helper), 'exec')
    lists = []
    for node in ast.walk(after):
        for _, value in ast.iter_fields(node):
            if isinstance(value, list) and any(isinstance(s, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'random_source' for t in s.targets) for s in value):
                lists.append(value)
    require(len(lists) == 1, 'unique adaptation block')
    statements = lists[0]
    index = next(i for i, s in enumerate(statements) if isinstance(s, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'random_source' for t in s.targets))
    block = copy.deepcopy(statements[index:index + 6])
    del statements[index:index + 6]
    require(ast.dump(after, include_attributes=False) == ast.dump(before, include_attributes=False), 'every existing helper AST node unchanged')
    adapt = next(n for n in ast.walk(before) if isinstance(n, ast.FunctionDef) and n.name == 'adapt')
    code = compile(ast.Module(body=[copy.deepcopy(adapt), *block], type_ignores=[]), 'exact-arm18-adaptation', 'exec')
    preimage = args.preimage.read_bytes()
    require(hashlib.sha256(preimage).hexdigest() == 'a600a0a54df08eff9be89335daea5299d961fa43dc024c488eceb5a610ec93c6', 'pinned source binding')
    rows = []
    for case in ('exact', 'changed-source', 'wrong-target', 'wrong-pin'):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary)
            source = out / 'source'
            path = source / 'src/crypto/random.c'
            path.parent.mkdir(parents=True)
            data = preimage + (b'\n' if case == 'changed-source' else b'')
            path.write_bytes(data)
            receipt = {'patches': []}
            environment = {'source': source, 'out': out, 'tester': SimpleNamespace(sha=sha, require=require),
                'args': SimpleNamespace(target='windows-i686' if case == 'wrong-target' else 'windows-aarch64'),
                'PIN': {'upstream': {'commit': 'wrong' if case == 'wrong-pin' else 'e151643c5269c83bf24a83b2548e2493876026b2'}},
                'receipt': receipt, 'save': lambda: None, 'difflib': __import__('difflib')}
            refused = False
            try:
                exec(code, environment)
            except AssertionError:
                refused = True
            if case == 'exact':
                require(not refused, 'exact source accepted')
                require(sha(path) == '9574e279b64cc3566c02b6dea77570319482c3056e19c49810442dffdb4ab213', 'exact corrected postimage')
                require(path.read_bytes().replace(b'#include <process.h>\n', b'') == preimage, 'only declaration include changed')
                require(len(receipt['patches']) == 1, 'one attributable patch')
                rows.append({'case': case, 'result': 'PASS', 'patch': receipt['patches'][0]})
            else:
                require(refused and path.read_bytes() == data and not receipt['patches'], 'reject before source modification')
                rows.append({'case': case, 'result': 'PASS', 'source_untouched': True, 'patch_receipt_absent': True})
    result = {'schema': 'meownero-arm18-random-declaration-fixtures/1', 'result': 'PASS',
        'helper_sha256': sha(args.helper), 'kit17_sha256': sha(args.kit17), 'preimage_sha256': sha(args.preimage),
        'postimage_sha256': '9574e279b64cc3566c02b6dea77570319482c3056e19c49810442dffdb4ab213',
        'entire_existing_helper_AST_unchanged_after_removing_six_new_statements': True,
        'existing_finally_blocks_unchanged': sum(isinstance(n, ast.Try) and bool(n.finalbody) for n in ast.walk(before)),
        'cases': rows, 'compiler_or_native_execution': 'NOT_RUN', 'new_full_build_started': False}
    args.receipt.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'result': 'PASS', 'cases': len(rows), 'helper_sha256': result['helper_sha256']}))


if __name__ == '__main__':
    main()
