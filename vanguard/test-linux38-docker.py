#!/usr/bin/env python3
"""Exercise the Docker successor without contacting a daemon or launching workers."""
import copy
import fcntl
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

import linux38_docker as provider

ROOT = Path(__file__).resolve().parent.parent
KIT = Path(os.environ['LINUX38_TEST_KIT']).absolute()
spec = importlib.util.spec_from_file_location('docker_controller', KIT / 'vanguard/run-portable-linux-docker.py')
controller = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controller)


class Admission(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT / 'build')
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / 'provenance.json'
        self.value = {'schema': 'meownero-linux38-native-docker/1', 'issue': 'TJS-1882',
                      'target': 'linux-x86_64', 'machine_id_sha256': '1' * 64,
                      'boot_id_sha256': '2' * 64, 'kernel': 'fixture-kernel', 'docker_id': 'private-daemon',
                      'docker_name': 'shared-host', 'docker_root': '/var/lib/docker', 'docker_version': '29.5.3',
                      'qualification_evidence_sha256': '3' * 64}
        self.info = {'ID': 'private-daemon', 'Name': 'shared-host', 'DockerRootDir': '/var/lib/docker',
                     'ServerVersion': '29.5.3', 'KernelVersion': 'fixture-kernel',
                     'Architecture': 'x86_64', 'OSType': 'linux', 'CgroupVersion': '2',
                     'MemoryLimit': True, 'SwapLimit': True, 'PidsLimit': True, 'CpuCfsQuota': True}
        self.context = [{'Name': 'default', 'Endpoints': {'docker': {'Host': 'unix:///var/run/docker.sock'}}}]
        self.release = 'ID=ubuntu\nVERSION_ID="24.04"\n'
        actual_read = Path.read_text
        actual_sha = provider.sha

        def read(path, *a, **k):
            return self.release if str(path) == '/etc/os-release' else actual_read(path, *a, **k)

        def sha(path):
            return {'/etc/machine-id': '1' * 64, '/proc/sys/kernel/random/boot_id': '2' * 64}.get(str(path)) or actual_sha(path)

        def query(*args):
            if args == ('context', 'inspect'):
                return json.dumps(self.context)
            if args == ('info', '--format', '{{json .}}'):
                return json.dumps(self.info)
            raise AssertionError('unexpected Docker command: ' + str(args))

        for context in (patch.dict(os.environ, {}, clear=True), patch.object(provider.platform, 'system', return_value='Linux'),
                        patch.object(provider.platform, 'machine', return_value='x86_64'),
                        patch.object(provider.platform, 'release', return_value='fixture-kernel'),
                        patch.object(provider.sys, 'version_info', (3, 14)), patch.object(Path, 'read_text', read),
                        patch.object(provider, 'sha', side_effect=sha), patch.object(provider, 'query', side_effect=query),
                        patch.object(provider.subprocess, 'check_output', return_value='glibc 2.39\n'),
                        patch.object(provider.stat, 'S_ISSOCK', return_value=True)):
            context.start()
            self.addCleanup(context.stop)
        provider._binding = None

    def admit(self, value=None, target='linux-x86_64'):
        self.path.write_text(json.dumps(value or self.value))
        return provider.admit(self.path, hashlib.sha256(self.path.read_bytes()).hexdigest(), target)

    def test_shared_daemon_and_container_marker_do_not_imply_refusal(self):
        with patch.object(Path, 'exists', return_value=True):
            proof = self.admit()
        self.assertEqual(proof['execution_provider'], provider.SCOPE)
        self.assertEqual(proof['worker_glibc'], '2.35')
        self.assertEqual(proof['controller_glibc'], '2.39')
        self.assertNotIn('private-daemon', json.dumps(proof))
        self.assertNotIn('shared-host', json.dumps(proof))

    def test_wrong_provenance_and_target_refused(self):
        for key, value in [('schema', 'other'), ('issue', 'other'), ('target', 'linux-aarch64'),
                           ('machine_id_sha256', '4' * 64), ('boot_id_sha256', '4' * 64),
                           ('kernel', 'other'), ('qualification_evidence_sha256', ''), ('extra', 'private')]:
            with self.subTest(key=key), self.assertRaises(AssertionError):
                self.admit({**self.value, key: value})
        self.admit()
        with self.assertRaises(AssertionError):
            provider.admit(self.path, '0' * 64, 'linux-x86_64')
        with self.assertRaises(AssertionError):
            self.admit(target='linux-aarch64')

    def test_wrong_daemon_and_reduced_capability_refused(self):
        baseline = copy.deepcopy(self.info)
        for key, value in [('ID', 'other'), ('Name', 'other'), ('ServerVersion', 'other'),
                           ('DockerRootDir', '/other'), ('KernelVersion', 'other'), ('Architecture', 'aarch64'),
                           ('OSType', 'windows'), ('CgroupVersion', '1'), ('MemoryLimit', False),
                           ('SwapLimit', False), ('PidsLimit', False), ('CpuCfsQuota', False)]:
            self.info = {**baseline, key: value}
            with self.subTest(key=key), self.assertRaises(AssertionError):
                self.admit()
        self.info = baseline
        self.context[0]['Endpoints']['docker']['Host'] = 'tcp://remote:2375'
        with self.assertRaises(AssertionError):
            self.admit()

    def test_hosted_environment_and_redirects_refused(self):
        for key in ('GITHUB_ACTIONS', 'RUNNER_ARCH', 'DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH'):
            with self.subTest(key=key), patch.dict(os.environ, {key: 'fixture'}), self.assertRaises(AssertionError):
                self.admit()

    def test_wrong_host_python_libc_refused(self):
        self.release = 'ID=ubuntu\nVERSION_ID="22.04"\n'
        with self.assertRaises(AssertionError):
            self.admit()
        self.release = 'ID=ubuntu\nVERSION_ID="24.04"\n'
        for context in (patch.object(provider.platform, 'machine', return_value='aarch64'),
                        patch.object(provider.platform, 'system', return_value='Darwin'),
                        patch.object(provider.sys, 'version_info', (3, 12)),
                        patch.object(provider.subprocess, 'check_output', return_value='glibc 2.35')):
            with context, self.assertRaises(AssertionError):
                self.admit()


class Controls(unittest.TestCase):
    def test_failed_probe_and_lost_create_response_still_clean_owned_name(self):
        sys.path.insert(0, str(ROOT / 'vanguard/docker'))
        import docker_support
        for failure in ('create', 'start', 'witness'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory(dir=ROOT / 'build') as directory:
                root = Path(directory)
                binding = root / 'binding.json'
                binding.write_text('{}')
                state = (binding, 'a' * 64, {'kernel': 'kernel', 'boot_id_sha256': 'b' * 64})
                calls = []

                def query(*args):
                    calls.append(args)
                    if args[:2] == ('image', 'inspect'):
                        return json.dumps([{'Id': 'sha256:' + 'c' * 64, 'Os': 'linux', 'Architecture': 'amd64'}])
                    if args[0] == failure:
                        raise subprocess.TimeoutExpired(['docker', args[0]], 30)
                    if args[0] == 'create':
                        return 'd' * 64
                    if args[0] == 'start':
                        return 'invalid witness'
                    raise AssertionError('unexpected command')

                with patch.object(provider, '_binding', state), patch.object(provider, 'admit'), \
                     patch.object(provider, 'query', side_effect=query), patch.object(provider, 'unrelated', return_value={'unrelated'}), \
                     patch.object(provider, 'preserved') as preserve, patch.object(docker_support, 'proof'), \
                     patch.object(docker_support, 'cleanup_named', return_value={'removed': True}) as cleanup:
                    with self.assertRaises((subprocess.TimeoutExpired, AssertionError)):
                        provider.resources(root)
                self.assertEqual(cleanup.call_count, 1)
                self.assertEqual(preserve.call_args.args[0], {'unrelated'})
                receipt = json.loads(next(root.glob('linux38-admission-*.json')).read_text())
                self.assertEqual(receipt['result'], 'FAIL')
                self.assertTrue(receipt['cleanup']['removed'])
                create = next(args for args in calls if args[0] == 'create')
                self.assertIn('--network=none', create)
                self.assertIn('--read-only', create)
                self.assertIn('--cap-drop=ALL', create)
                self.assertNotIn('--privileged', create)

    def test_witness_binding_and_resource_refusals(self):
        value = {'kernel': 'test-kernel', 'boot_id_sha256': hashlib.sha256(b'boot\n').hexdigest()}
        lines = ['x86_64', 'test-kernel', 'boot', 'a' * 64 + '  /binding', '22.04', 'glibc 2.35',
                 str(6 * 1024**2), str(11 * provider.GIB) + ' 1', str(11 * provider.GIB) + ' 1',
                 '67108864 0 16', '100000 100000']
        result = provider.check_witness(lines, value, 'a' * 64)
        self.assertEqual(result['available_memory_bytes'], 6 * provider.GIB)
        for index, bad in [(0, 'aarch64'), (1, 'other'), (2, 'other'), (3, 'b' * 64 + '  /binding'),
                           (4, '24.04'), (5, 'glibc 2.39'), (6, '100'), (7, '1 1'), (8, '1 1'),
                           (9, 'max max max'), (10, 'max 100000')]:
            altered = list(lines)
            altered[index] = bad
            with self.subTest(index=index), self.assertRaises(AssertionError):
                provider.check_witness(altered, value, 'a' * 64)

    def test_real_busy_shared_lock_and_inode_preservation(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'build') as directory:
            lock = Path(directory) / 'heavy.lock'
            lock.touch(mode=0o600)
            inode = lock.stat().st_ino
            with patch.object(provider, 'LOCK', lock):
                with lock.open('rb') as held:
                    fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    with self.assertRaises(BlockingIOError), provider.shared_lock():
                        self.fail('busy lock admitted')
                with provider.shared_lock() as actual:
                    self.assertEqual(actual, inode)
            self.assertEqual(lock.stat().st_ino, inode)

    def test_unrelated_container_disappearance_refuses(self):
        with patch.object(provider, 'unrelated', return_value={'unrelated'}):
            provider.preserved({'unrelated'})
            with self.assertRaises(AssertionError):
                provider.preserved({'unrelated', 'missing'})

    def test_actual_source_export_and_validation_without_daemon(self):
        output = ROOT / 'build' / ('linux38-validation-' + os.urandom(5).hex())
        self.addCleanup(__import__('shutil').rmtree, output, True)
        argv = [sys.executable, '-B', str(KIT / 'vanguard/run-portable-linux-docker.py'), '--inputs', str(KIT / 'inputs.json'),
                '--inputs-sha256', hashlib.sha256((KIT / 'inputs.json').read_bytes()).hexdigest(), '--out', str(output)]
        result = subprocess.run(argv + ['--validate-only'], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        proof = json.loads((output / 'public/ci-receipt.json').read_text())
        self.assertEqual(proof['result'], 'PASS_ALLOWLIST_ONLY_RUNNER_BUILD_NATIVE_JOURNEY_UNTESTED')
        other = output.parent / (output.name + '-no-provenance')
        result = subprocess.run(argv[:-1] + [str(other)], capture_output=True, text=True, timeout=20)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Docker provenance is required', result.stderr)
        self.assertFalse(other.exists())

    def test_controller_supervision_binding_and_failed_phase_cleanup(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'build') as directory:
            root = Path(directory)
            lock = root / 'heavy.lock'
            lock.touch(mode=0o600)
            provenance = root / 'binding.json'
            provenance.write_text('{}')
            digest = hashlib.sha256(provenance.read_bytes()).hexdigest()
            calls = []

            def supervise(argv, private, public, **kwargs):
                calls.append(argv)
                self.assertEqual(argv[-4:], ['--docker-provenance', str(provenance), '--docker-provenance-sha256', digest])
                phase = argv[argv.index('--phase') + 1]
                self.assertLessEqual(kwargs['timeout'], {'fetch': 900, 'prepare': 1200, 'build': 3600, 'package': 180, 'runtime': 1500}[phase])
                self.assertEqual(kwargs['cleanup_seconds'], 180)
                (public / 'supervision.json').write_text(json.dumps({'wrapper_reaped': True, 'cleanup': [{'removed': True}]}))
                if phase == 'build':
                    (root / 'out/build').mkdir()
                    (root / 'out/build/build-receipt.json').write_text(json.dumps({'compiler_execution_substrate': 'NATIVE', 'patches': [], 'cleanup': {'removed': True}}))
                if phase == 'package':
                    release = root / 'out/package/meownero-vanguard-x86_64'
                    release.mkdir(parents=True)
                    (release / 'release.json').write_text(json.dumps({'minimum_glibc': '2.35'}))
                if phase == 'runtime':
                    raise RuntimeError('fixture stops at runtime before any workload')

            def resources(parent, reserve=10, minimum_available=6 * provider.GIB):
                self.assertEqual(reserve, 10)
                self.assertEqual(minimum_available, 6 * provider.GIB)
                return {'available_memory_bytes': 6 * provider.GIB}

            argv = ['controller', '--inputs', str(KIT / 'inputs.json'), '--inputs-sha256',
                    hashlib.sha256((KIT / 'inputs.json').read_bytes()).hexdigest(), '--out', str(root / 'out'),
                    '--docker-provenance', str(provenance), '--docker-provenance-sha256', digest]
            # Controller uses its private-kit provider; patch that module, not the test module's copy.
            with patch.object(controller.sys, 'argv', argv), patch.object(controller, 'local_runner', return_value={'execution_provider': provider.SCOPE}), \
                 patch.object(controller.provider, 'LOCK', lock), patch.object(controller.provider, 'unrelated', return_value={'unrelated'}), \
                 patch.object(controller.provider, 'preserved'), patch.object(controller, 'resources', side_effect=resources), \
                 patch.object(controller, 'load', return_value=SimpleNamespace(mac_check=supervise)), \
                 patch.object(controller.subprocess, 'check_output', side_effect=lambda argv, **k: 'glibc 2.39' if argv[0] == 'getconf' else 'linux x86_64'), \
                 patch.object(controller.sys, 'stdout', new_callable=io.StringIO):
                with self.assertRaisesRegex(RuntimeError, 'fixture stops at runtime'):
                    controller.main()
            proof = json.loads((root / 'out/public/ci-receipt.json').read_text())
            self.assertEqual(len(calls), 5)
            self.assertNotIn('github_sha', proof)
            self.assertTrue(proof['canonical_shared_lock_preserved'])
            self.assertEqual(proof['result'], 'FAIL')
            self.assertFalse((root / 'out/cache').exists())
            self.assertTrue(lock.is_file())


if __name__ == '__main__':
    unittest.main(verbosity=2)
