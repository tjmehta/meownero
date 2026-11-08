"""Reproduce the real ARM13 inventory gap and exercise Windows .lib origin guards."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('--original', type=Path, required=True)
parser.add_argument('--patched', type=Path, required=True)
parser.add_argument('--build', type=Path, required=True)
parser.add_argument('--scratch', type=Path, required=True)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

old, new = load('original', args.original), load('candidate', args.patched)
source = args.build.resolve() / 'monero-fcmp'
binary = source / 'build/portable'
depends = source / 'contrib/depends/aarch64-w64-mingw32'
before = old.link_inventory(source, binary, depends, (Path('/out/monero-fcmp'),), True)
after = new.link_inventory(source, binary, depends, (Path('/out/monero-fcmp'),), True)
assert before[0] == after[0], 'the exact original linker/response hashes must remain unchanged'
assert not any(old.depends_component(n) == 'boost' for n in before[1])
boost = {n for n in after[1] if new.depends_component(n) == 'boost'}
assert boost and all(n.endswith('.lib') for n in boost)
assert after[1] - before[1] == boost and before[1] - after[1] == set()
assert after[3] - before[3] == {(n, 'pinned_depends') for n in boost}
archives = []
for name in sorted(boost):
    path = depends / 'lib' / name
    raw = path.read_bytes()
    assert raw.startswith(b'!<arch>\n')
    headers = subprocess.check_output([str(args.build.resolve() / 'llvm/bin/llvm-readobj'),
                                      '--file-headers', str(path)], text=True, timeout=30)
    machines = [line.strip() for line in headers.splitlines() if 'Machine:' in line]
    assert machines and all('IMAGE_FILE_MACHINE_ARM64 (0xAA64)' in line for line in machines)
    assert 'Format: COFF-import-file' not in headers
    archives.append({'name': name, 'sha256': hashlib.sha256(raw).hexdigest(),
                     'arm64_object_members': len(machines), 'bytes': len(raw)})
cases = [{'case': 'original-real-links-miss-boost', 'result': 'REPRODUCED'},
         {'case': 'patched-real-links-cover-exact-boost-archives', 'result': 'PASS'}]
with tempfile.TemporaryDirectory(prefix='arm13-lib-', dir=args.scratch) as work:
    src = Path(work) / 'source'
    build = src / 'build/portable'
    dep = src / 'contrib/depends/aarch64-w64-mingw32'
    links = []
    for target in ('daemon', 'simplewallet', 'wallet_rpc_server'):
        link = build / 'src' / target / 'CMakeFiles' / (target + '.dir/link.txt')
        link.parent.mkdir(parents=True)
        links.append(link)
    valid = dep / 'lib/libboost_filesystem.lib'
    for style in ('absolute', 'relative', 'container', 'response'):
        for link in links:
            cwd = link.parent.parent.parent
            token = str(valid)
            if style == 'relative': token = os.path.relpath(valid, cwd)
            if style == 'container': token = str(Path('/out/monero-fcmp') / valid.relative_to(src))
            if style == 'response':
                response = link.with_name('libs.rsp')
                response.write_text(shlex.quote(token))
                token = '@' + str(response.relative_to(cwd))
            link.write_text(shlex.join(['c++', token]))
        result = new.link_inventory(src, build, dep, (Path('/out/monero-fcmp'),), True)
        assert result[1] == {valid.name} and result[3] == {(valid.name, 'pinned_depends')}
        assert new.link_inventory(src, build, dep, (Path('/out/monero-fcmp'),), False)[1] == set()
        cases.append({'case': style + '-windows-only-lib-inventory', 'result': 'PASS'})
    for label, token in [
        ('wrong-target', src / 'contrib/depends/wrong/lib/libboost_filesystem.lib'),
        ('wrong-directory', dep / 'lib-other/libboost_filesystem.lib'),
        ('project-imposter', build / 'src/libboost_filesystem.lib'),
        ('system-imposter', Path(work) / 'system/libboost_filesystem.lib'),
        ('unmapped-contrib', src / 'contrib/private/unknown.lib'),
    ]:
        for link in links: link.write_text(shlex.join(['c++', str(token)]))
        try:
            new.link_inventory(src, build, dep, (Path('/out/monero-fcmp'),), True)
        except AssertionError:
            cases.append({'case': label, 'result': 'PASS_REFUSAL'})
        else:
            raise AssertionError('untrusted .lib origin accepted: ' + label)
result = {'result': 'PASS_WINDOWS_LIB_INVENTORY', 'cases': cases, 'count': len(cases),
          'actual_boost_archives': archives, 'actual_link_bindings': after[0],
          'original_module_sha256': hashlib.sha256(args.original.read_bytes()).hexdigest(),
          'candidate_module_sha256': hashlib.sha256(args.patched.read_bytes()).hexdigest(),
          'scope': 'LICENSE_INVENTORY_AND_CROSS_OBJECTS_ONLY_NO_NATIVE_WINDOWS_EXECUTION'}
args.out.write_text(json.dumps(result, indent=2) + '\n')
print(result['result'], result['count'])
