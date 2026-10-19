#!/usr/bin/env python3
"""Exercise owned-runner admission; these fixtures prove no native build/journey."""
import copy
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
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('local_linux_controller', Path(__file__).with_name('run-portable-linux-ci.py'))
controller = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controller)


class Admission(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(dir=os.environ['PAPERCLIP_RUN_SCRATCH_DIR'])
        self.addCleanup(self.scratch.cleanup)
        self.path = Path(self.scratch.name) / 'provenance.json'
        self.value = {'schema': 'meownero-owned-native-linux-runner/1', 'issue': 'TJS-1882',
                      'target': 'linux-aarch64', 'environment': 'tjs1882-arm39-fixture',
                      'physical_host_architecture': 'arm64', 'machine_id_sha256': '1' * 64,
                      'boot_id_sha256': '2' * 64, 'qualification_evidence_sha256': '3' * 64,
                      'docker_id': 'fixture-daemon', 'docker_name': 'tjs1882-arm39-fixture'}
        self.release = 'ID=ubuntu\nVERSION_ID="22.04"\n'
        self.glibc = 'glibc 2.35\n'
        self.context = [{'Name': 'default', 'Endpoints': {'docker': {'Host': 'unix:///var/run/docker.sock'}}}]
        self.info = {'ID': 'fixture-daemon', 'Name': self.value['environment'], 'OSType': 'linux',
                     'Architecture': 'aarch64', 'DockerRootDir': '/var/lib/docker'}
        self.running = ''
        self.markers = False
        original_sha, original_read, original_exists = controller.sha, Path.read_text, Path.exists

        def digest(path):
            return {'/etc/machine-id': '1' * 64, '/proc/sys/kernel/random/boot_id': '2' * 64}.get(str(path)) or original_sha(path)

        def read(path, *args, **kwargs):
            if str(path) == '/proc/cpuinfo':
                return 'Features: aes pmull sha1 sha2\n'
            return self.release if str(path) == '/etc/os-release' else original_read(path, *args, **kwargs)

        def exists(path):
            return self.markers if str(path) in ('/.dockerenv', '/run/.containerenv') else original_exists(path)

        def command(argv, **kwargs):
            self.assertGreater(kwargs['timeout'], 0)
            if argv == ['getconf', 'GNU_LIBC_VERSION']:
                return self.glibc
            if argv == ['docker', 'context', 'inspect']:
                return json.dumps(self.context)
            if argv == ['docker', 'info', '--format', '{{json .}}']:
                return json.dumps(self.info)
            if argv == ['docker', 'info', '--format', '{{.OSType}} {{.Architecture}}']:
                return 'linux aarch64'
            self.assertEqual(argv, ['docker', 'ps', '-q'])
            return self.running

        for context in (patch.dict(os.environ, {}, clear=True), patch.object(controller.platform, 'system', return_value='Linux'),
                        patch.object(controller.platform, 'machine', return_value='aarch64'),
                        patch.object(controller, 'sha', side_effect=digest), patch.object(Path, 'read_text', read),
                        patch.object(Path, 'exists', exists), patch.object(controller.subprocess, 'check_output', side_effect=command)):
            context.start()
            self.addCleanup(context.stop)

    def admit(self, value=None, digest=None, target='linux-aarch64'):
        self.path.write_text(json.dumps(self.value if value is None else value))
        return controller.local_runner(self.path, digest or hashlib.sha256(self.path.read_bytes()).hexdigest(), target)

    def test_native_arm_and_x64_admitted_with_private_ids_excluded(self):
        proof = self.admit()
        self.assertEqual(proof['execution_provider'], 'OWNED_NATIVE_UBUNTU22_VM')
        self.assertNotIn('fixture-daemon', json.dumps(proof))
        self.assertNotIn('tjs1882-arm39-fixture', json.dumps(proof))
        self.value['docker_name'] = self.info['Name'] = 'lima-' + self.value['environment']
        self.admit()
        self.value.update(target='linux-x86_64', physical_host_architecture='x86_64')
        self.info['Architecture'] = 'x86_64'
        with patch.object(controller.platform, 'machine', return_value='x86_64'):
            self.admit(target='linux-x86_64')

    def test_binding_changes_refused(self):
        for key, value in [('schema', 'other'), ('issue', 'TJS-1'), ('target', 'linux-x86_64'),
                           ('environment', 'shared'), ('physical_host_architecture', 'x86_64'),
                           ('machine_id_sha256', '4' * 64), ('boot_id_sha256', '5' * 64),
                           ('qualification_evidence_sha256', ''), ('docker_id', 'other'), ('docker_name', 'other')]:
            with self.subTest(key=key):
                candidate = copy.deepcopy(self.value)
                candidate[key] = value
                with self.assertRaises(AssertionError):
                    self.admit(candidate)
        with self.assertRaises(AssertionError):
            self.admit(digest='0' * 64)
        with self.assertRaises(AssertionError):
            self.admit({**self.value, 'unlisted': 'private'})

    def test_hosted_identity_and_docker_redirects_refused(self):
        for key in ('GITHUB_ACTIONS', 'GITHUB_SHA', 'RUNNER_ARCH', 'RUNNER_OS', 'DOCKER_HOST',
                    'DOCKER_CONTEXT', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH'):
            with self.subTest(key=key), patch.dict(os.environ, {key: 'fixture'}):
                with self.assertRaises(AssertionError):
                    self.admit()

    def test_wrong_os_libc_arch_python_and_container_refused(self):
        self.release = 'ID=ubuntu\nVERSION_ID="24.04"\n'
        with self.assertRaises(AssertionError):
            self.admit()
        self.release = 'ID=ubuntu\nVERSION_ID="22.04"\n'
        self.glibc = 'glibc 2.39\n'
        with self.assertRaises(AssertionError):
            self.admit()
        self.glibc = 'glibc 2.35\n'
        for context in (patch.object(controller.platform, 'machine', return_value='x86_64'),
                        patch.object(controller.sys, 'version_info', (3, 12)), patch.object(self, 'markers', True)):
            with context, self.assertRaises(AssertionError):
                self.admit()

    def test_shared_or_redirected_daemon_refused(self):
        baseline = copy.deepcopy(self.info)
        for key, value in [('ID', 'other'), ('Name', 'shared'), ('OSType', 'windows'),
                           ('Architecture', 'x86_64'), ('DockerRootDir', '/other')]:
            with self.subTest(key=key):
                self.info = {**baseline, key: value}
                with self.assertRaises(AssertionError):
                    self.admit()
        self.info = baseline
        self.context[0]['Endpoints']['docker']['Host'] = 'tcp://remote:2375'
        with self.assertRaises(AssertionError):
            self.admit()
        self.context[0]['Endpoints']['docker']['Host'] = 'unix:///var/run/docker.sock'
        self.running = 'unrelated-container\n'
        with self.assertRaises(AssertionError):
            self.admit()

    def test_full_local_controller_uses_supervisor_and_truthful_receipt(self):
        self.admit()
        root = self.path.parent
        inputs = json.loads((controller.ROOT / 'research/evidence/vanguard-local-runner-tjs1882-2026-10-19/local-39-inputs.json').read_text())
        input_file = root / 'inputs.json'
        input_file.write_text(json.dumps(inputs))
        digest = hashlib.sha256(self.path.read_bytes()).hexdigest()
        local_lock = root / 'fixture.lock'
        calls = []

        def supervise(argv, *args, **kwargs):
            calls.append(argv)
            self.assertEqual(argv[-4:], ['--local-provenance', str(self.path), '--local-provenance-sha256', digest])
            self.assertEqual(kwargs['cleanup_seconds'], 180)
            self.assertEqual(kwargs['timeout'], 900)
            raise RuntimeError('fixture stops inside supervisor before any fetch or build')

        def path(value):
            return local_lock if str(value) == '/tmp/meownero-swarm-20260912-heavy.lock' else Path(value)

        argv = ['controller', '--inputs', str(input_file), '--inputs-sha256', hashlib.sha256(input_file.read_bytes()).hexdigest(),
                '--out', str(root / 'out'), '--local-provenance', str(self.path), '--local-provenance-sha256', digest]
        with patch.object(controller, 'Path', side_effect=path), patch.object(controller.sys, 'argv', argv), \
             patch.object(controller, 'resources', return_value={'available_memory_bytes': 6 * 1024**3}), \
             patch.object(controller, 'load', return_value=SimpleNamespace(mac_check=supervise)), \
             patch.object(controller.sys, 'stdout', new_callable=io.StringIO):
            with self.assertRaisesRegex(RuntimeError, 'fixture stops inside supervisor'):
                controller.main()
        proof = json.loads((root / 'out/public/ci-receipt.json').read_text())
        self.assertEqual(len(calls), 1)
        self.assertEqual(proof['schema'], 'meownero-owned-native-ubuntu22-build-and-journey/1')
        self.assertNotIn('github_sha', proof)
        self.assertNotIn('github_run_id', proof)
        self.assertEqual(proof['local_runner']['execution_provider'], 'OWNED_NATIVE_UBUNTU22_VM')
        self.assertEqual(proof['result'], 'FAIL')
        self.assertTrue(proof['owned_ephemeral_lock_removed'])
        self.assertFalse(local_lock.exists())
        self.assertFalse((root / 'out/cache').exists())


class LocalCli(unittest.TestCase):
    def test_real_host_refuses_before_output_or_worker_start(self):
        # This actual Ubuntu24 developer host is deliberately not a qualified VM.
        if 'VERSION_ID="24.04"' not in Path('/etc/os-release').read_text():
            self.skipTest('actual Ubuntu24 refusal fixture')
        with tempfile.TemporaryDirectory(dir=os.environ['PAPERCLIP_RUN_SCRATCH_DIR']) as directory:
            root = Path(directory)
            inputs = json.loads((controller.ROOT / 'research/evidence/vanguard-portable-production-tjs1882-2026-10-09/linux38-inputs.source.json').read_text())
            inputs['source_files']['vanguard/run-portable-linux-ci.py'] = controller.sha(Path(controller.__file__))
            input_file = root / 'inputs.json'
            input_file.write_text(json.dumps(inputs))
            value = {'schema': 'meownero-owned-native-linux-runner/1', 'issue': 'TJS-1882',
                     'target': 'linux-x86_64', 'environment': 'tjs1882-x64-fixture',
                     'physical_host_architecture': 'x86_64', 'machine_id_sha256': '1' * 64,
                     'boot_id_sha256': '2' * 64, 'qualification_evidence_sha256': '3' * 64,
                     'docker_id': 'fixture', 'docker_name': 'tjs1882-x64-fixture'}
            provenance = root / 'provenance.json'
            provenance.write_text(json.dumps(value))
            command = [sys.executable, '-B', controller.__file__, '--inputs', str(input_file),
                       '--inputs-sha256', controller.sha(input_file), '--out', str(root / 'out')]
            env = {k: v for k, v in os.environ.items() if not k.startswith(('GITHUB_', 'RUNNER_'))}
            for phase in ([], ['--phase', 'fetch']):
                result = subprocess.run(command + ['--local-provenance', str(provenance),
                    '--local-provenance-sha256', controller.sha(provenance)] + phase, capture_output=True, text=True, env=env, timeout=20)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('owned Ubuntu22 VM required', result.stderr)
                self.assertFalse((root / 'out').exists())
            result = subprocess.run(command + ['--local-provenance', str(provenance)], capture_output=True, text=True, timeout=20)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('local provenance requires path and checksum', result.stderr)
            self.assertFalse((root / 'out').exists())


if __name__ == '__main__':
    unittest.main()
