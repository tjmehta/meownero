"""Outer failure contracts. Disposable inodes and modeled managers only.

No original heavy lock, resource snapshot, cgroup, mount, daemon or native binary
is touched. OOM/crash/timeout events are injected, never induced on the host.
"""
import copy
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import profile_contract as c
import profile_handoff as h
import profile_outer as outer

GRANT = '11111111-1111-4111-8111-111111111111'
BINDINGS = dict(grant_id=GRANT, grant_sha256='a'*64, candidate_commit='b'*40,
                inputs_sha256='c'*64, artifact_sha256='d'*64, bootstrap_sha256='e'*64)


class ModeledManager:
    def __init__(self):
        self.now = 100
        self.calls = []
        self.keeper = None
        self.failure = None
        self.second_mode = 'normal'
        self.cleanup_failure = False
        self.fail_provision = False
        self.finish_failure = False

    def retain(self, lock_fd, bindings, deadlines, *, deadline):
        self.calls.append('retain')
        self.keeper = os.dup(lock_fd)
        self.deadlines = deadlines
        self.assert_held()

    def assert_held(self):
        h.lock_witness(Path(f'/proc/self/fdinfo/{self.keeper}').read_text(), os.getpid())

    def admit(self, number, *, deadline):
        self.calls.append('admit'+str(number))
        self.now += 1
        return dict(at=self.now, snapshot=dict(available_memory_bytes=5*1024**3,
            free_disk_bytes=20*1024**3, load=[0, 0, 0], native_processes=[], native_containers=[]))

    def provision(self, ledger_fd, *, deadline):
        self.calls.append('provision')
        self.assert_held()
        ledger = json.loads(os.pread(ledger_fd, os.fstat(ledger_fd).st_size, 0))
        assert ledger['state'] == 'CONSUMED'
        assert fcntl.fcntl(ledger_fd, fcntl.F_GETFL) & os.O_ACCMODE == os.O_RDONLY
        if self.fail_provision:
            raise OSError('partial setup')
        self.now += 1
        return dict(enclosure=dict(mechanism=h.MECHANISM, daemon_mode='platform-authorized-rootful-cgroupfs',
                                   cgroup_parent='/modeled', workload_cgroup='/modeled/work'),
                    recovery=dict(owner=c.PLATFORM, implementation_sha256=BINDINGS['bootstrap_sha256'],
                                  kill_scope='/modeled/work'))

    def run_controller(self, context_fd, lock_fd, ledger_fd, second_admission, *, deadlines):
        self.calls.append('controller')
        assert fcntl.fcntl(context_fd, fcntl.F_GET_SEALS) & outer.SEALS == outer.SEALS
        if self.second_mode != 'missing':
            second_admission()
        if self.second_mode == 'repeat':
            second_admission()
        if self.failure:
            raise self.failure
        self.now = deadlines['work'] if self.second_mode != 'late' else deadlines['work']+1
        # A malicious or premature inner PASS cannot finalize cleanup/resources.
        rows = c.empty_rows()
        for row in rows.values():
            for key in row:
                row[key] = dict(status='PASS')
        return dict(exit_code=0, rows=rows)

    def recover(self, *, deadline):
        self.calls.append('recover')
        self.assert_held()
        if self.cleanup_failure:
            raise OSError('busy mount: secret should never be exported')

    def complete_after_exit(self, result, *, deadline):
        self.calls.append('arm_final')
        self.assert_held()
        self.pending = copy.deepcopy(result)
        if self.finish_failure:
            raise OSError('observer unavailable')


class OuterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='meownero-outer-source-test-')
        self.root = Path(self.temp.name)
        self.lock = self.root/'disposable.lock'
        self.lock.touch(mode=0o600)
        info = self.lock.stat()
        self.patch = patch.multiple(c, LOCK=self.lock, LOCK_ID=(info.st_dev, info.st_ino))
        self.patch.start()
        self.manager = ModeledManager()
        self.subject = outer.Outer(self.manager, clock=lambda: self.manager.now)

    def tearDown(self):
        if self.manager.keeper is not None:
            os.close(self.manager.keeper)
        self.patch.stop()
        self.temp.cleanup()

    def run_outer(self):
        return self.subject.run(BINDINGS, self.root)

    def assert_keeper_blocks_new_open(self):
        self.manager.assert_held()
        with self.lock.open('r+') as separate:
            with self.assertRaises(BlockingIOError):
                fcntl.flock(separate, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_contention_refuses_without_manager_admission_or_ledger(self):
        with self.lock.open('r+') as competing:
            fcntl.flock(competing, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                self.run_outer()
        self.assertEqual(self.manager.calls, [])
        self.assertFalse((self.root/(GRANT+'.json')).exists())

    def test_inode_replacement_and_symlink_refuse_before_manager(self):
        self.lock.unlink()
        target = self.root/'other'
        target.touch(mode=0o600)
        self.lock.symlink_to(target)
        with self.assertRaises(OSError):
            self.run_outer()
        self.lock.unlink()
        self.lock.touch(mode=0o644)
        with self.assertRaises(ValueError):
            self.run_outer()
        self.assertEqual(self.manager.calls, [])

    def test_hardlinked_lock_refuses(self):
        os.link(self.lock, self.root/'alias')
        with self.assertRaises(ValueError):
            self.run_outer()
        self.assertEqual(self.manager.calls, [])

    def test_positive_order_is_pending_until_independent_post_exit_observation(self):
        result = self.run_outer()
        self.assertEqual(self.manager.calls,
                         ['retain', 'admit1', 'provision', 'controller', 'admit2', 'recover', 'arm_final'])
        self.assertEqual(result['result'], 'PENDING_MANAGER_COMPLETION')
        self.assertEqual(result['manager_completion'], 'PENDING_INDEPENDENT_POST_EXIT_OBSERVATION')
        self.assertEqual(c.verdict(result['rows']), 'INCOMPLETE')
        self.assertFalse(result['launch_ready'])
        self.assert_keeper_blocks_new_open()

    def test_consumed_grant_never_retries_or_provisions(self):
        self.run_outer()
        os.close(self.manager.keeper)
        self.manager.keeper = None
        self.manager.now = 100
        self.manager.calls.clear()
        result = self.run_outer()
        self.assertEqual(result['result'], 'FAIL')
        self.assertEqual(result['failure_class'], 'FileExistsError')
        self.assertNotIn('provision', self.manager.calls)
        self.assert_keeper_blocks_new_open()

    def test_first_admission_failure_never_consumes_or_provisions(self):
        original = self.manager.admit
        def low(number, **kwargs):
            value = original(number, **kwargs)
            value['snapshot']['available_memory_bytes'] -= 1
            return value
        self.manager.admit = low
        result = self.run_outer()
        self.assertEqual(result['result'], 'REFUSED_BEFORE_ATTEMPT')
        self.assertFalse((self.root/(GRANT+'.json')).exists())
        self.assertNotIn('provision', self.manager.calls)
        self.assert_keeper_blocks_new_open()

    def test_first_admission_staleness_refuses_before_consumption(self):
        original = self.manager.admit
        def stale(number, **kwargs):
            value = original(number, **kwargs)
            self.manager.now += 6
            return value
        self.manager.admit = stale
        self.assertEqual(self.run_outer()['result'], 'REFUSED_BEFORE_ATTEMPT')
        self.assertFalse((self.root/(GRANT+'.json')).exists())

    def test_partial_setup_failure_always_recovers_under_kept_lock(self):
        self.manager.fail_provision = True
        result = self.run_outer()
        self.assertEqual(result['result'], 'FAIL')
        self.assertEqual(self.manager.calls[-2:], ['recover', 'arm_final'])
        self.assertNotIn('controller', self.manager.calls)
        self.assertTrue((self.root/(GRANT+'.json')).exists())
        self.assert_keeper_blocks_new_open()

    def test_workload_oom_controller_crash_timeout_all_recover_without_release(self):
        for failure in (MemoryError('modeled OOM'), ChildProcessError('modeled SIGKILL'),
                        TimeoutError('modeled stalled controller')):
            with self.subTest(failure=type(failure).__name__):
                self.manager.failure = failure
                result = self.run_outer()
                self.assertEqual(result['result'], 'FAIL')
                self.assertEqual(result['failure_class'], type(failure).__name__)
                self.assertEqual(self.manager.calls[-2:], ['recover', 'arm_final'])
                self.assert_keeper_blocks_new_open()
                os.close(self.manager.keeper)
                self.manager.keeper = None
                # A new test-only grant is necessary. The consumed file stays.
                self.temp.cleanup()
                self.patch.stop()
                self.setUp()

    def test_launcher_unwind_also_calls_recovery(self):
        self.manager.failure = KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            self.run_outer()
        self.assertEqual(self.manager.calls[-2:], ['recover', 'arm_final'])
        self.assert_keeper_blocks_new_open()

    def test_second_admission_missing_repeated_or_late_cannot_succeed(self):
        for mode in ('missing', 'repeat', 'late'):
            with self.subTest(mode=mode):
                self.manager.second_mode = mode
                self.assertEqual(self.run_outer()['result'], 'FAIL')
                self.assert_keeper_blocks_new_open()
                os.close(self.manager.keeper)
                self.manager.keeper = None
                self.temp.cleanup()
                self.patch.stop()
                self.setUp()

    def test_second_admission_refusal_is_consumed_and_recovers(self):
        original = self.manager.admit
        def collision(number, **kwargs):
            value = original(number, **kwargs)
            if number == 2:
                value['snapshot']['native_processes'] = ['modeled-collision']
            return value
        self.manager.admit = collision
        result = self.run_outer()
        self.assertEqual(result['result'], 'FAIL')
        self.assertEqual(self.manager.calls.count('admit2'), 1)
        self.assertTrue((self.root/(GRANT+'.json')).exists())
        self.assert_keeper_blocks_new_open()

    def test_cleanup_failure_keeps_custody_and_exports_no_private_error(self):
        self.manager.cleanup_failure = True
        result = self.run_outer()
        self.assertEqual(result['result'], 'FAIL')
        self.assertEqual(result['recovery_failure_class'], 'OSError')
        self.assertNotIn('secret', json.dumps(result))
        self.assert_keeper_blocks_new_open()

    def test_missing_final_observer_cannot_become_success(self):
        self.manager.finish_failure = True
        result = self.run_outer()
        self.assertEqual(result['result'], 'FAIL')
        self.assertEqual(result['manager_completion'], 'NOT_RUN')
        self.assert_keeper_blocks_new_open()

    def test_accidental_unlock_during_cleanup_is_detected(self):
        def bad_recovery(**kwargs):
            fcntl.flock(self.manager.keeper, fcntl.LOCK_UN)
        self.manager.recover = bad_recovery
        result = self.run_outer()
        self.assertEqual(result['result'], 'FAIL')
        self.assertEqual(result['recovery_failure_class'], 'ValueError')

    def test_interrupted_recovery_closes_local_fds_but_keeper_survives(self):
        original = outer.acquire_original
        descriptors = []
        def acquire():
            fd = original()
            descriptors.append(fd)
            return fd
        def interrupt(**kwargs):
            raise KeyboardInterrupt()
        self.manager.recover = interrupt
        with patch.object(outer, 'acquire_original', side_effect=acquire):
            with self.assertRaises(KeyboardInterrupt):
                self.run_outer()
        with self.assertRaises(OSError):
            os.fstat(descriptors[0])
        self.assert_keeper_blocks_new_open()

    def test_cleanup_cannot_extend_total_deadline(self):
        def late_recovery(**kwargs):
            self.manager.now = self.manager.deadlines['end']+1
        self.manager.recover = late_recovery
        result = self.run_outer()
        self.assertEqual(result['result'], 'FAIL')
        self.assertIn('recovery_failure_class', result)
        self.assert_keeper_blocks_new_open()

    def test_ledger_file_then_directory_fsync_and_readonly_descriptor(self):
        calls = []
        real = os.fsync
        def fsync(fd):
            calls.append(os.fstat(fd).st_mode)
            real(fd)
        with patch.object(outer.os, 'fsync', side_effect=fsync):
            fd, value = outer.consume(self.root, BINDINGS, 100, 101)
        try:
            import stat
            self.assertTrue(stat.S_ISREG(calls[0]))
            self.assertTrue(stat.S_ISDIR(calls[1]))
            self.assertEqual(len(calls), 2)
            self.assertEqual(json.loads(os.pread(fd, 10000, 0)), value)
            with self.assertRaises(OSError):
                os.write(fd, b'x')
        finally:
            os.close(fd)

    def test_partial_write_or_fsync_failure_preserves_poisoned_ledger(self):
        for failing in ('write_all', 'file_fsync', 'directory_fsync'):
            with self.subTest(operation=failing):
                real_fsync = os.fsync
                calls = []
                def fail_sync(fd):
                    calls.append(fd)
                    if len(calls) == (1 if failing == 'file_fsync' else 2):
                        raise OSError('injected durability failure')
                    real_fsync(fd)
                target = outer if failing == 'write_all' else outer.os
                operation = 'write_all' if failing == 'write_all' else 'fsync'
                effect = OSError('injected partial write') if failing == 'write_all' else fail_sync
                with patch.object(target, operation, side_effect=effect):
                    result = self.run_outer()
                self.assertEqual(result['result'], 'FAIL')
                self.assertTrue((self.root/(GRANT+'.json')).exists())
                self.assertNotIn('provision', self.manager.calls)
                with self.assertRaises(FileExistsError):
                    outer.consume(self.root, BINDINGS, 100, 101)
                os.close(self.manager.keeper)
                self.manager.keeper = None
                self.temp.cleanup()
                self.patch.stop()
                self.setUp()

    def test_context_is_private_sealed_and_not_inheritable_by_default(self):
        fd = outer.sealed_context(dict(private='test-only'))
        try:
            self.assertFalse(os.get_inheritable(fd))
            self.assertEqual(os.fstat(fd).st_mode & 0o777, 0o600)
            with self.assertRaises(OSError):
                os.write(fd, b'x')
            with self.assertRaises(OSError):
                os.ftruncate(fd, 0)
        finally:
            os.close(fd)

    def test_unbound_and_fabricated_bindings_refuse_before_any_host_call(self):
        capabilities = c.json_file(c.HERE/'integration/outer-capabilities.json')
        self.assertEqual(outer.capability_check(capabilities)['missing'], list(outer.CAPABILITIES))
        for filled in (False, True):
            with self.subTest(filled=filled):
                value = copy.deepcopy(capabilities)
                if filled:
                    value['capabilities'] = {name: {'assertion': True} for name in outer.CAPABILITIES}
                with patch.object(outer, 'acquire_original') as lock:
                    with self.assertRaises(ValueError):
                        outer.require_runtime(dict(platform_bootstrap_sha256='e'*64), value)
                    lock.assert_not_called()
        self.assertEqual(h.QUALIFIED_BOOTSTRAPS, {})

    def test_executable_default_refuses_with_no_lock_or_manager(self):
        spec = importlib.util.spec_from_file_location('outer_entry', c.HERE/'run-outer.py')
        entry = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(entry)
        with patch('sys.argv', ['run-outer.py']), patch('builtins.print'), \
             patch.object(outer, 'acquire_original') as lock:
            self.assertEqual(entry.main(), 3)
            lock.assert_not_called()


if __name__ == '__main__':
    unittest.main()
