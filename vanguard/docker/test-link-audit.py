#!/usr/bin/env python3
"""Prove early origin refusal, safe receipts and export before owned cleanup."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import portable_licenses as licenses
import build

spec = importlib.util.spec_from_file_location('compiler', Path(__file__).with_name('compile.py'))
compiler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compiler)
ROOT = Path(__file__).resolve().parents[2]
NAMES = ('libboost_filesystem.a', 'libssl.a', 'libcrypto.a', 'libsodium.a', 'libunbound.a', 'libzmq.a')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    assert args.out.parent.is_dir() and not args.out.exists()
    cases = []
    with tempfile.TemporaryDirectory(prefix='PRIVATE_PATH_SENTINEL ', dir=args.out.parent) as directory:
        temporary = Path(directory)
        source = temporary / 'build/monero-fcmp'
        binary_build = source / 'build/vanguard'
        depends = source / 'contrib/depends/x86_64-unknown-linux-gnu'
        recipe = temporary / 'recipe'
        for relative in ('vanguard/source-lock.json', 'vanguard/portable_licenses.py', 'vanguard/docker/compile.py'):
            destination = recipe / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, destination)
        source.parent.mkdir(parents=True)
        (source.parent / 'inputs.json').write_text(json.dumps({'base': 'fixture'}))
        toolchain = depends / 'share/toolchain.cmake'
        toolchain.parent.mkdir(parents=True)
        links = []
        for target, folder in (('daemon', 'daemon'), ('simplewallet', 'simplewallet'), ('wallet_rpc_server', 'wallet')):
            link = binary_build / 'src' / folder / 'CMakeFiles' / (target + '.dir/link.txt')
            link.parent.mkdir(parents=True)
            links.append(link)
        def configure(bad=None):
            toolchain.write_text('SET(STATIC ON)\n')
            for link in links:
                tokens = [str(depends / 'lib' / name) for name in NAMES]
                tokens += ['../cryptonote_core/libcryptonote_core.a', '../cryptonote_basic/libcryptonote_basic.a']
                if bad is not None:
                    tokens.insert(0, str(bad))
                link.write_text(shlex.join(['c++', *tokens]))
        original_read = Path.read_text
        cgroup = {'memory.max': str(3 * 1024**3), 'memory.swap.max': '0', 'pids.max': '256'}
        def read(path, *args, **kwargs):
            if path.parent == Path('/sys/fs/cgroup') and path.name in cgroup:
                return cgroup[path.name]
            return original_read(path, *args, **kwargs)
        class ReachedCompile(Exception):
            pass
        for label, bad in [('valid-project-and-pinned', None),
                           ('project-disguised-openssl', binary_build / 'src/libcrypto.a'),
                           ('wrong-host-openssl', source / 'contrib/depends/wrong-host/lib/libcrypto.a'),
                           ('private-source-openssl', source / 'contrib/PRIVATE_LIBRARY_SENTINEL/libcrypto.a'),
                           ('private-foreign-openssl', temporary / 'PRIVATE_LIBRARY_SENTINEL/libcrypto.a')]:
            configure(bad)
            calls = []
            def command(argv, cwd=source, timeout=3500):
                calls.append(argv)
                if argv[:2] == ['make', '-j1']:
                    raise ReachedCompile()
            with patch.object(compiler, 'BUILD', source.parent), patch.object(compiler, 'SOURCE', source), \
                 patch.object(compiler, 'RECIPE', recipe), patch.object(compiler, 'run', command), \
                 patch.object(Path, 'read_text', read), \
                 patch.object(Path, 'iterdir', return_value=iter([Path('/sys/class/net/lo')])), patch.dict(os.environ):
                try:
                    compiler.main()
                except ReachedCompile:
                    assert bad is None
                except AssertionError:
                    assert bad is not None
                else:
                    raise AssertionError('compiler fixture did not stop')
            receipt = json.loads((source.parent / 'link-origin-audit.json').read_text())
            assert 'PRIVATE_' not in json.dumps(receipt)
            assert bool(any(argv[:2] == ['make', '-j1'] for argv in calls)) == (bad is None)
            assert receipt['scope'] == 'GENERATED_COMMANDS_ONLY_NO_RUNTIME_EVIDENCE'
            assert receipt['result'] == ('PASS_LINK_ORIGINS' if bad is None else 'REFUSED_LINK_ORIGIN')
            assert receipt['source_sha256'] == {p: licenses.sha(recipe / p) for p in
                ('vanguard/source-lock.json', 'vanguard/portable_licenses.py', 'vanguard/docker/compile.py')}
            if bad is not None:
                assert receipt['component'] == 'openssl' and receipt['basename'] == 'libcrypto.a'
                assert len(receipt['link_commands']) == 1
            cases.append({'case': label + '-actual-main-order-and-safe-receipt', 'result': 'PASS'})

        for label, original, replacement, component, expected in (
            ('missing-sodium', 'libsodium.a', '', 'sodium', 'depends component absent from linker inventory'),
            ('shared-openssl', 'libssl.a', 'libssl.so.3', 'openssl', 'older baseline requires the pinned static dependency closure')):
            configure()
            for link in links:
                text = link.read_text()
                token = shlex.quote(str(depends / 'lib' / original))
                link.write_text(text.replace(token, shlex.quote(str(depends / 'lib' / replacement)) if replacement else ''))
            with patch.object(compiler, 'BUILD', source.parent), patch.object(compiler, 'SOURCE', source), \
                 patch.object(compiler, 'RECIPE', recipe):
                try:
                    compiler.audit_links(binary_build, depends)
                except AssertionError as error:
                    assert str(error) == expected
                else:
                    raise AssertionError('incomplete/static closure admitted')
            receipt = json.loads((source.parent / 'link-origin-audit.json').read_text())
            assert receipt['component'] == component and receipt['result'] == 'REFUSED_LINK_ORIGIN'
            assert 'token' not in receipt and 'normalized_path' not in receipt
            cases.append({'case': label + '-early-closure-refusal', 'result': 'PASS'})

        # A secondary receipt-write failure preserves the origin assertion.
        configure(binary_build / 'src/libcrypto.a')
        with patch.object(compiler, 'BUILD', source.parent), patch.object(compiler, 'SOURCE', source), \
             patch.object(compiler, 'RECIPE', recipe), patch.object(Path, 'write_text', side_effect=OSError('PRIVATE_WRITE_SENTINEL')):
            try:
                compiler.audit_links(binary_build, depends)
            except AssertionError as error:
                assert str(error) == 'pinned depends library has non-pinned origin'
            else:
                raise AssertionError('primary origin error lost')
        cases.append({'case': 'secondary-diagnostic-write-does-not-mask-origin-refusal', 'result': 'PASS'})

        for label in ('valid', 'wrong-identity', 'copy-failure'):
            out = temporary / label
            out.mkdir()
            events = []
            cid = 'a' * 64
            def proof(*args, **kwargs):
                events.append('proof')
                if label == 'wrong-identity':
                    raise AssertionError('foreign image')
            def query(*argv, timeout=30):
                events.append(argv[0])
                if argv[0] == 'ps':
                    return cid
                assert argv == ('cp', cid + ':/build/link-origin-audit.json', str(out / 'link-origin-audit.json'))
                if label == 'copy-failure':
                    raise subprocess.CalledProcessError(1, 'docker cp')
                (out / 'link-origin-audit.json').write_text('{"scope":"GENERATED_COMMANDS_ONLY"}\n')
                return ''
            with patch.object(build, 'query', query), patch.object(build, 'proof', proof):
                value = build.retain_link_audit(out, 'owned', 'exact-name', 'exact-image')
            assert value['retained'] == (label == 'valid')
            assert events == (['ps', 'proof'] if label == 'wrong-identity' else ['ps', 'proof', 'cp'])
            if label == 'valid':
                assert value['sha256'] == licenses.sha(out / 'link-origin-audit.json')
            cases.append({'case': label + '-identity-verified-receipt-copy', 'result': 'PASS'})

        # Exercise the real outer failed-compile finalizer with a private lock.
        # Diagnostic export must precede cleanup, including when copying fails.
        original_open = os.open
        def private_open(path, flags, mode=0o777):
            if str(path) == '/tmp/meownero-swarm-20260912-heavy.lock':
                return original_open(temporary / 'private-heavy.lock', flags, mode)
            return original_open(path, flags, mode)
        class Child:
            pid = 0
            def __init__(self, exit_code): self.exit_code = exit_code
            def wait(self, timeout): return self.exit_code
            def poll(self): return self.exit_code
        for retained in (True, False):
            out = temporary / ('outer-' + str(retained))
            order = []
            exits = iter([0, 0, 1])
            def export(*args):
                order.append('export')
                return {'retained': retained}
            def cleanup(*args):
                assert order == ['export']
                order.append('cleanup')
                return [{'removed': True}]
            with patch.object(sys, 'argv', ['build.py', '--out', str(out)]), \
                 patch.object(build, 'local_endpoint', return_value='fixture'), \
                 patch.object(build.os, 'open', side_effect=private_open), \
                 patch.object(build.subprocess, 'Popen', side_effect=lambda *a, **kw: Child(next(exits))), \
                 patch.object(build, 'query', return_value='sha256:' + 'b' * 64), \
                 patch.object(build, 'admit'), patch.object(build, 'retain_link_audit', side_effect=export), \
                 patch.object(build, 'cleanup_build', side_effect=cleanup):
                try:
                    build.main()
                except AssertionError as error:
                    assert str(error) == 'compile failed; exact log retained'
                else:
                    raise AssertionError('failed compilation accepted')
            receipt = json.loads((out / 'build.json').read_text())
            assert order == ['export', 'cleanup']
            assert receipt['result'] == 'FAILED_BUILD_ATTEMPT' and receipt['lock_closed']
            assert receipt['link_origin_audit']['retained'] == retained and receipt['cleanup'][0]['removed']
            cases.append({'case': 'failed-compile-export-' + str(retained) + '-before-cleanup-and-lock-release', 'result': 'PASS'})

    args.out.write_text(json.dumps({'result': 'PASS', 'cases': cases,
        'source_sha256': {str(p.relative_to(ROOT)): licenses.sha(p) for p in
            (Path(__file__).resolve(), ROOT / 'vanguard/portable_licenses.py',
             ROOT / 'vanguard/docker/compile.py', ROOT / 'vanguard/docker/build.py')},
        'seams': 'Generated link fixtures, fake depends/CMake command runner, cgroup/network scalars, fake Docker queries. Actual compile.main audit ordering and ownership-checked receipt copy execute.',
        'program_compile_image_or_runtime_acceptance': False}, indent=2) + '\n')
    print('PASS', len(cases), 'early link audit controls')


if __name__ == '__main__':
    main()
