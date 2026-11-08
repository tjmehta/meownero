#!/usr/bin/env python3
"""Bounded acquisition/cleanup, frozen-context and host-witness fault controls."""
import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
from contextlib import redirect_stdout

import docker_support as support
import host_capacity as host
import build
import run

IMAGE = 'sha256:' + 'b' * 64
CID = 'a' * 64


class Engine:
    def __init__(self, failure=None, mismatched=False):
        self.failure = failure
        self.mismatched = mismatched
        self.item = None
        self.removals = []
        self.inspections = 0
        self.starts = []
        self.public_output = None

    def query(self, *argv, timeout=30):
        operation = argv[0]
        if operation == 'image':
            return json.dumps([{'Id': IMAGE, 'Architecture': 'amd64', 'Os': 'linux'}])
        if operation == 'create':
            name = argv[argv.index('--name') + 1]
            label = argv[argv.index('--label') + 1].split('=', 1)[1]
            mount = argv[argv.index('--mount') + 1]
            self.public_output = Path(mount.removeprefix('type=bind,src=').removesuffix(',dst=/output'))
            self.item = {'Id': CID, 'Name': '/' + name, 'Image': IMAGE,
                         'Config': {'Labels': {'meownero.invocation': label}},
                         'HostConfig': {'NetworkMode': 'none', 'ReadonlyRootfs': True,
                                        'Memory': 2 * host.GIB, 'MemorySwap': 2 * host.GIB,
                                        'NanoCpus': 2_000_000_000, 'PidsLimit': 256,
                                        'CapDrop': ['ALL'], 'SecurityOpt': ['no-new-privileges'],
                                        'Tmpfs': {'/state': 'rw,nosuid,nodev,noexec,size=1g,mode=1777',
                                                  '/tmp': 'rw,nosuid,nodev,noexec,size=64m,mode=1777'}},
                         'State': {'Running': False, 'ExitCode': 0, 'OOMKilled': False}}
            if self.failure == 'create-interrupt':
                raise KeyboardInterrupt()
            if self.failure == 'create-timeout':
                raise subprocess.TimeoutExpired('docker create', 30)
            return CID
        if operation == 'start':
            assert argv == ('start', CID) and self.item['Id'] == CID
            self.starts.append(CID)
            # Protocol fixture only. No wallet, process or container runs here.
            (self.public_output / 'result.json').write_text(json.dumps({'result': 'PASS_NATIVE_JOURNEY', 'fixture': True}) + '\n')
            return CID
        if operation == 'ps':
            if self.failure == 'discover-timeout':
                raise subprocess.TimeoutExpired('docker ps', 30)
            return CID if self.item else ''
        if operation == 'inspect':
            self.inspections += 1
            if self.failure == 'inspect-timeout' or (self.failure == 'inspect-transient' and self.inspections == 1):
                raise subprocess.TimeoutExpired('docker inspect', 30)
            item = json.loads(json.dumps(self.item))
            if self.mismatched:
                item['Image'] = 'sha256:' + 'c' * 64
            return json.dumps([item])
        if operation == 'rm':
            self.removals.append(argv[-1])
            if self.failure == 'remove-timeout':
                raise subprocess.TimeoutExpired('docker rm', 30)
            self.item = None
            return CID
        if operation == 'stop':
            self.item['State']['Running'] = False
            return CID
        raise AssertionError('unexpected fixture query: ' + operation)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    assert args.out.parent.is_dir() and not args.out.exists()
    cases = []
    def passed(name):
        cases.append({'case': name, 'result': 'PASS'})
    with tempfile.TemporaryDirectory(dir=args.out.parent) as temporary:
        root = Path(temporary)
        engine = Engine()
        out = root / 'ordinary-create-start'
        with patch.object(support, 'query', engine.query), patch.object(run, 'query', engine.query), \
             patch.object(run.os, 'getuid', return_value=1000), \
             patch.object(sys, 'argv', ['run.py', '--image', IMAGE, '--out', str(out)]), \
             patch.object(run.shutil, 'disk_usage', return_value=SimpleNamespace(free=10 * host.GIB)), \
             redirect_stdout(io.StringIO()):
            run.main()
        receipt = json.loads((out / 'runtime.json').read_text())
        assert engine.starts == [CID] and engine.removals == [CID] and engine.item is None
        assert receipt['cid'] == CID and receipt['result'] == 'PASS_NATIVE_JOURNEY' and receipt['exit'] == 0
        assert receipt['cleanup']['identity_verified'] and receipt['cleanup']['removed']
        assert receipt['policy']['NetworkMode'] == 'none' and receipt['policy']['ReadonlyRootfs']
        assert receipt['public_result_sha256'] == hashlib.sha256((out / 'result.json').read_bytes()).hexdigest()
        assert {p.name for p in out.iterdir()} == {'runtime.json', 'result.json'}
        passed('ordinary-successful-create-start-result-and-owned-cleanup')
        for failure in ('create-interrupt', 'create-timeout'):
            engine = Engine(failure)
            out = root / failure
            with patch.object(support, 'query', engine.query), patch.object(run, 'query', engine.query), \
                 patch.object(sys, 'argv', ['run.py', '--image', IMAGE, '--out', str(out)]), \
                 patch.object(run.shutil, 'disk_usage', return_value=SimpleNamespace(free=10 * host.GIB)):
                try:
                    run.main()
                except (KeyboardInterrupt, subprocess.TimeoutExpired):
                    pass
                else:
                    raise AssertionError('lost-create response did not propagate')
            receipt = json.loads((out / 'runtime.json').read_text())
            assert receipt['result'] == 'FAILED_RUNTIME_ATTEMPT' and receipt['cleanup']['removed']
            assert engine.removals == [CID] and engine.item is None
            passed(failure + '-registered-by-exact-name-and-finalized')
        engine = Engine('create-interrupt')
        def interrupted_then_failed_inspection(*argv, timeout=30):
            if argv[0] == 'inspect':
                raise subprocess.TimeoutExpired('docker inspect', 30)
            return engine.query(*argv, timeout=timeout)
        out = root / 'runtime-finalization-failure'
        with patch.object(support, 'query', interrupted_then_failed_inspection), patch.object(run, 'query', interrupted_then_failed_inspection), \
             patch.object(sys, 'argv', ['run.py', '--image', IMAGE, '--out', str(out)]), \
             patch.object(run.shutil, 'disk_usage', return_value=SimpleNamespace(free=10 * host.GIB)):
            try:
                run.main()
            except KeyboardInterrupt:
                pass
            else:
                raise AssertionError('interruption swallowed')
        receipt = json.loads((out / 'runtime.json').read_text())
        assert receipt['result'] == 'UNRESOLVED_RUNTIME_CLEANUP' and not receipt['cleanup']['removed']
        assert not engine.removals
        passed('failed-runtime-inspection-still-finalizes-honest-receipt')
        for failure, mismatched, removed in [
            ('inspect-transient', False, True), ('inspect-timeout', False, False),
            ('discover-timeout', False, False), ('remove-timeout', False, False),
            (None, True, False), (None, False, True)]:
            engine = Engine(failure, mismatched)
            engine.item = {'Id': CID, 'Name': '/exact-name', 'Image': IMAGE,
                           'Config': {'Labels': {'meownero.invocation': 'exact-owner'}},
                           'State': {'Running': False, 'ExitCode': 0, 'OOMKilled': False}}
            with patch.object(support, 'query', engine.query):
                receipt = support.cleanup_named('exact-name', IMAGE, 'exact-owner')
            assert receipt['removed'] is removed
            if mismatched or failure in ('inspect-timeout', 'discover-timeout'):
                assert not engine.removals
            passed((failure or ('identity-mismatch' if mismatched else 'owned-cleanup')) + '-honest-bounded-result')
        # The first owned resource's discovery failure must not skip the second.
        ids = ['d' * 64, 'e' * 64]
        with patch.object(support, 'cleanup_named', return_value={'removed': False}), \
             patch.object(support, 'retry_query', return_value='\n'.join(ids)), \
             patch.object(support, 'cleanup_container', side_effect=lambda cid, *a: {'cid': cid, 'removed': cid == ids[1]}) as remove:
            rows = support.cleanup_build('owner', 'name', IMAGE)
        assert len(rows) == 3 and remove.call_count == 2 and rows[-1]['removed']
        passed('cleanup-continues-after-independent-resource-failures')
        context = root / 'context'
        expected = build.freeze(context)
        assert 'docs/vanguard-portable-tester.md' in expected and 'docs/vanguard-docker-tester.md' in expected
        assert any(p.startswith('vanguard/licenses/') for p in expected)
        build.verify_context(context, expected)
        passed('complete-copied-notices-docs-and-input-binding')
        loaded = subprocess.run([sys.executable, '-B', str(context / 'vanguard/package-portable.py'), '--help'],
                                capture_output=True, text=True, timeout=15)
        assert loaded.returncode == 0, loaded.stderr
        passed('frozen-package-command-loads-with-all-dependencies')
        # A changed live recipe has no effect on the independent copied context.
        live = root / 'live-recipe'
        live.write_text('different live bytes')
        with patch.object(build, 'ROOT', live):
            build.verify_context(context, expected)
        passed('verification-independent-of-live-source-root')
        for relative in ('vanguard/docker/Dockerfile', 'vanguard/docker/inputs.json', 'vanguard/licenses/easyloggingpp-9.96.7/LICENSE'):
            path = context / relative
            original = path.read_bytes()
            path.chmod(0o600)
            path.write_bytes(original + b'changed')
            try:
                build.verify_context(context, expected)
            except AssertionError:
                pass
            else:
                raise AssertionError('context mutation admitted')
            path.write_bytes(original)
            passed('changed-frozen-' + Path(relative).name + '-refused')
        values = ['x86_64', 'same-boot', str(6 * host.GIB // 1024), str(20 * host.GIB), '1']
        result = host.check_witness(values, 'same-boot')
        assert result['host_available_bytes'] == 6 * host.GIB
        passed('same-kernel-daemon-host-capacity-witness')
        for label, index, value in [('different-daemon-kernel', 1, 'other-boot'), ('daemon-memory-reserve', 2, str(4 * host.GIB // 1024)),
                                    ('daemon-data-disk-reserve', 3, str(9 * host.GIB)), ('daemon-architecture', 0, 'aarch64')]:
            candidate = values.copy()
            candidate[index] = value
            try:
                host.check_witness(candidate, 'same-boot')
            except AssertionError:
                pass
            else:
                raise AssertionError('unsafe Docker host admitted')
            passed(label + '-refused')
        with patch.dict(os.environ, {'DOCKER_HOST': 'tcp://remote:2376', 'DOCKER_CONTEXT': ''}):
            try:
                host.local_endpoint()
            except AssertionError:
                pass
            else:
                raise AssertionError('remote Docker endpoint admitted')
        passed('remote-context-refused-before-work')
        # Exercise the real outer build finally after a failed admission. No
        # Docker process is run; the lock uses only this test's private inode.
        original_open = os.open
        descriptors = []
        def private_open(path, flags, mode=0o777):
            if str(path) == '/tmp/meownero-swarm-20260912-heavy.lock':
                fd = original_open(root / 'private-heavy.lock', flags, mode)
                descriptors.append(fd)
                return fd
            return original_open(path, flags, mode)
        class Child:
            pid = 0
            def wait(self, timeout): return 0
            def poll(self): return 0
        out = root / 'build-finalization'
        with patch.object(sys, 'argv', ['build.py', '--out', str(out)]), \
             patch.object(build, 'local_endpoint', return_value='fixture'), \
             patch.object(build.os, 'open', side_effect=private_open), \
             patch.object(build.subprocess, 'Popen', return_value=Child()), \
             patch.object(build, 'admit', side_effect=RuntimeError('fixture admission refusal')), \
             patch.object(build, 'cleanup_build', return_value=[{'removed': False, 'failure_type': 'TimeoutExpired'}]):
            try:
                build.main()
            except RuntimeError:
                pass
            else:
                raise AssertionError('failed admission accepted')
        receipt = json.loads((out / 'build.json').read_text())
        assert receipt['lock_closed'] and receipt['result'] == 'UNRESOLVED_BUILD_CLEANUP'
        try:
            os.fstat(descriptors[0])
        except OSError:
            pass
        else:
            raise AssertionError('workload lock remained open')
        passed('failed-cleanup-always-writes-terminal-receipt-and-closes-lock')
    paths = [Path(__file__), *[Path(__file__).with_name(name) for name in ('build.py', 'run.py', 'docker_support.py', 'host_capacity.py', 'Dockerfile', 'inputs.json')]]
    args.out.write_text(json.dumps({'schema': 'meownero-docker-source-hold-fixtures/1', 'result': 'PASS', 'cases': cases,
                                  'source_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
                                  'seams': 'Fake Docker query engine and ordinary-start public protocol result, UID/disk admission, lost-create responses, bounded query failures, private lock inode, fake completed subprocess and temporary copied context; host capacity scalars. Actual run.main/ownership/cleanup/receipt logic executes. No native process, Docker container or image.',
                                  'native_build_or_runtime_acceptance': False}, indent=2) + '\n')
    print('PASS', len(cases), 'source hold controls')


if __name__ == '__main__':
    main()
