#!/usr/bin/env python3
"""Real flock/stat/shell fixtures; Docker observations remain explicitly mocked."""
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import linux38_docker as provider

ROOT = Path(__file__).resolve().parent.parent
KIT = Path(os.environ['LINUX38_TEST_KIT']).absolute()
sys.path.insert(0, str(ROOT / 'vanguard/docker'))
import docker_support
REAL_RUN = subprocess.run


def execute_witness(command, remap, marker):
    """Model daemon namespaces with disjoint real files, not invented stat output."""
    mounts = {}
    for index, flag in enumerate(command):
        if flag == '--mount':
            fields = dict(part.split('=', 1) for part in command[index + 1].split(',') if '=' in part)
            mounts[fields['dst']] = Path(fields['src'])
    mounts.update(remap)
    script = command[-1].split('# end mount witness\n')[0]
    pattern = '|'.join(re.escape(path) for path in sorted(mounts, key=len, reverse=True))
    script = re.sub(pattern, lambda match: shlex.quote(str(mounts[match.group()])), script)
    script += '\ntouch ' + shlex.quote(str(marker))
    return REAL_RUN(['/bin/sh', '-ec', script], capture_output=True, text=True, timeout=5)


class Topology(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT / 'build')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.lock = self.root / 'controller.lock'
        self.lock.touch(mode=0o600)
        self.host_lock = self.root / 'daemon.lock'
        self.host_lock.touch(mode=0o600)
        self.wrong = self.root / 'wrong-mount'
        self.wrong.mkdir()
        self.binding = self.root / 'binding.json'
        self.binding.write_text('{}')
        self.marker = self.root / 'payload-started'
        context = patch.object(provider, 'LOCK', self.lock)
        context.start()
        self.addCleanup(context.stop)
        self.assertIsNone(getattr(provider, '_lock_stream', None))

    def resources(self, remap):
        digest = hashlib.sha256(self.binding.read_bytes()).hexdigest()
        value = {'kernel': 'same-kernel', 'boot_id_sha256': hashlib.sha256(b'same-boot\n').hexdigest()}
        transcript = ['x86_64', 'same-kernel', 'same-boot', digest + '  /binding', '22.04', 'glibc 2.35',
                      str(7 * 1024**2), '20000000 4096', '20000000 4096', '67108864 0 16', '100000 100000']
        created = []

        def query(*args):
            if args[:2] == ('image', 'inspect'):
                return json.dumps([{'Id': 'sha256:' + 'c' * 64, 'Os': 'linux', 'Architecture': 'amd64'}])
            if args[0] == 'create':
                created.append(args)
                return 'd' * 64
            if args[0] == 'start':
                if '# end mount witness\n' in created[0][-1]:
                    result = execute_witness(created[0], remap, self.marker)
                    if result.returncode:
                        raise subprocess.CalledProcessError(result.returncode, 'fixture witness', result.stdout, result.stderr)
                return '\n'.join(transcript)
            raise AssertionError('unexpected Docker operation')

        def cleanup(*args):
            with self.lock.open('rb') as check:
                try:
                    fcntl.flock(check, fcntl.LOCK_SH | fcntl.LOCK_NB)
                except BlockingIOError:
                    self.cleanup_lock_busy = True
                else:
                    self.cleanup_lock_busy = False
            return {'removed': True}

        with patch.object(provider, '_binding', (self.binding, digest, value)), patch.object(provider, 'admit'), \
             patch.object(provider, 'query', side_effect=query), patch.object(provider, 'unrelated', return_value={'unrelated'}), \
             patch.object(docker_support, 'proof'), patch.object(docker_support, 'cleanup_named', side_effect=cleanup):
            try:
                return provider.resources(self.root)
            finally:
                receipts = list(self.root.glob('linux38-admission-*.json'))
                self.assertTrue(receipts)
                receipt = json.loads(receipts[-1].read_text())
                self.assertTrue(receipt['cleanup']['removed'])
                self.assertTrue(receipt['unrelated_containers_preserved'])

    def test_same_namespace_positive_control_and_lock_release(self):
        inode = self.lock.stat().st_ino
        result = self.resources({})
        self.assertTrue(self.marker.exists(), 'real lock/stat witness did not reach payload')
        self.assertTrue(result['owned_probe_removed'])
        self.assertTrue(self.cleanup_lock_busy, 'canonical lock released before probe cleanup')
        self.assertEqual(self.lock.stat().st_ino, inode)
        with self.lock.open('rb') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_same_boot_shared_provenance_private_lock_refused_even_when_host_busy(self):
        with self.host_lock.open('rb') as held:
            fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.host_lock.open('rb') as control:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(control, fcntl.LOCK_SH | fcntl.LOCK_NB)
            with self.assertRaises(subprocess.CalledProcessError):
                self.resources({'/canonical-heavy-lock': self.host_lock})
            self.assertFalse(self.marker.exists())
            with self.host_lock.open('rb') as control:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(control, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_wrong_absent_and_stale_source_output_mounts_refused(self):
        for destination in ('/source', '/output'):
            for kind in ('wrong', 'absent', 'stale'):
                with self.subTest(destination=destination, kind=kind):
                    stale = self.root / ('old-' + destination[1:])
                    stale.mkdir(exist_ok=True)
                    mapped = {'wrong': self.wrong, 'absent': self.root / 'absent', 'stale': stale}[kind]
                    with self.assertRaises(subprocess.CalledProcessError):
                        self.resources({destination: mapped})
                    self.assertFalse(self.marker.exists())
                    self.assertFalse((self.root / 'absent').exists(), 'absent bind source was created')

    def test_unheld_lock_symlinks_and_changed_inode_refused(self):
        with self.assertRaisesRegex(AssertionError, 'must remain held'):
            provider.mount_witness([(self.root, '/out', False)])
        alias = self.root / 'alias'
        alias.symlink_to(self.wrong, target_is_directory=True)
        with provider.shared_lock():
            with self.assertRaisesRegex(AssertionError, 'symlink'):
                provider.mount_witness([(alias, '/out', False)])
            with provider.shared_lock():
                with self.lock.open('rb') as check:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(check, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with self.assertRaisesRegex(AssertionError, 'identity changed'):
            with provider.shared_lock():
                self.lock.rename(self.root / 'old-lock')
                self.lock.touch(mode=0o600)
        self.assertIsNone(provider._lock_stream)
        with (self.root / 'old-lock').open('rb') as check:
            fcntl.flock(check, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_worker_lock_contention_is_required_even_with_matching_inode(self):
        # Build the real prelude while held, then intentionally release before
        # executing it. Identical stat output alone must not permit the payload.
        with provider.shared_lock():
            flags, witness = provider.mount_witness([(self.root, '/out', False)])
        result = execute_witness([*flags, witness], {}, self.marker)
        self.assertEqual(result.returncode, 76)
        self.assertFalse(self.marker.exists())

    def test_actual_runtime_command_checks_exact_archive_output_and_harness(self):
        spec = importlib.util.spec_from_file_location('runtime_fixture', KIT / 'vanguard/run-portable-check.py')
        runtime = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runtime)
        archive = self.root / 'archive.tar.gz'
        archive.write_bytes(b'fixture, no native artifact or journey')
        for mismatch in (False, True):
            with self.subTest(mismatch=mismatch):
                self.marker.unlink(missing_ok=True)
                out = self.root / ('runtime-' + str(mismatch))
                calls = []

                def run(command, **kwargs):
                    calls.append(command)
                    result = execute_witness(command, {'/out': self.wrong} if mismatch else {}, self.marker)
                    self.assertEqual(result.returncode == 0, not mismatch, result.stderr)
                    # Stop before archive extraction or any native program.
                    return type('Result', (), {'returncode': 1})()

                argv = ['runtime', '--archive', str(archive), '--sha256', hashlib.sha256(archive.read_bytes()).hexdigest(),
                        '--target', 'linux-x86_64', '--runtime-image', 'sha256:' + 'c' * 64, '--out', str(out)]
                with patch.object(sys, 'argv', argv), patch.object(runtime.tester, 'command', return_value='amd64 linux'), \
                     patch.object(runtime.subprocess, 'run', side_effect=run), \
                     patch.object(runtime.provider, 'cleanup_owned', return_value={'removed': True}):
                    with self.assertRaisesRegex(RuntimeError, 'native archive journey failed'):
                        runtime.main()
                self.assertEqual(self.marker.exists(), not mismatch)
                self.assertNotIn('-v', calls[0])
                self.assertIn('dst=/artifact.tar.gz,readonly', ' '.join(calls[0]))
                self.assertIn('dst=/harness,readonly', ' '.join(calls[0]))
                self.assertTrue(json.loads((out / 'check-receipt.json').read_text())['cleanup']['removed'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
