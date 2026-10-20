#!/usr/bin/env python3
"""Source/patch separation checks. These do not execute native policy or P2P."""
import argparse
import copy
import contextlib
import fcntl
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import sys
import unittest

import network as n
import policy as p


class PolicyBoundary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.originals = p.checked_source(SOURCE)
        cls.value = n.profile()
        cls.changed = p.changes(cls.originals, cls.value)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=SCRATCH, prefix='policy-test-')
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_patch_applies_and_reverses_every_changed_byte(self):
        out = self.root / 'overlay'
        receipt = p.prepare(SOURCE, out, self.value)
        tree = self.root / 'source'
        for name in self.changed:
            path = tree / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(self.originals[name])
        patch = out / 'selected-9-90.patch'
        for reverse, expected in ((False, self.changed), (True, self.originals)):
            cmd = ['git', 'apply'] + (['--reverse'] if reverse else []) + [str(patch)]
            subprocess.run(cmd, cwd=tree, check=True, capture_output=True, timeout=10)
            for name in self.changed:
                self.assertEqual((tree / name).read_bytes(), expected[name], name)
        self.assertEqual(receipt['overlay_id'], n.sha(patch.read_bytes()))
        self.assertFalse(receipt['launch_ready'])
        self.assertEqual(receipt['native_policy'], 'NOT_RUN')
        with self.assertRaises(ValueError):
            p.prepare(SOURCE, out, self.value)

    def test_patch_is_repeatable_and_never_mutates_inputs(self):
        first = p.prepare(SOURCE, self.root / 'a', self.value)
        second = p.prepare(SOURCE, self.root / 'b', self.value)
        self.assertEqual(first, second)
        self.assertEqual(p.checked_source(SOURCE), self.originals)
        self.assertEqual(first['profile_sha256'], n.profile_hash(self.value))

    def test_exact_allowlist_keeps_crypto_wallet_and_pins_unchanged(self):
        self.assertEqual(set(self.changed), {
            'src/cryptonote_config.h', 'src/hardforks/hardforks.cpp',
            'src/cryptonote_basic/cryptonote_basic_impl.cpp',
            'src/cryptonote_basic/cryptonote_basic_impl.h',
            'src/cryptonote_core/cryptonote_tx_utils.cpp',
            'src/cryptonote_core/cryptonote_tx_utils.h',
            'src/cryptonote_core/blockchain.cpp', 'src/cryptonote_core/blockchain.h',
            'src/cryptonote_core/tx_pool.cpp', 'src/rpc/core_rpc_server.cpp'})
        for name in self.originals.keys() - self.changed.keys():
            self.assertEqual((SOURCE / name).read_bytes(), self.originals[name])

    def test_foreign_identity_fork_tables_and_global_targets_stay_identical(self):
        name = 'src/cryptonote_config.h'
        before, after = self.originals[name].decode(), self.changed[name].decode()
        for marker, index in [('  namespace testnet\n', 0), ('  namespace stagenet\n', 1)]:
            self.assertEqual(before.split(marker)[index], after.split(marker)[index])
        name = 'src/hardforks/hardforks.cpp'
        before, after = self.originals[name].decode(), self.changed[name].decode()
        self.assertEqual(before.split('const hardfork_t testnet_hard_forks[]')[0],
                         after.split('const hardfork_t testnet_hard_forks[]')[0])
        self.assertEqual(before.split('const hardfork_t stagenet_hard_forks[]')[1],
                         after.split('const hardfork_t stagenet_hard_forks[]')[1])

    def test_foreign_emission_branch_and_penalty_are_preserved(self):
        name = 'src/cryptonote_basic/cryptonote_basic_impl.cpp'
        before, after = self.originals[name].decode(), self.changed[name].decode()
        start = before.index('    const int target =')
        end = before.index('\n\n    uint64_t full_reward_zone', start)
        original = before[start:end].replace('uint64_t base_reward =', 'base_reward =')
        expected = '\n'.join('  ' + line if line else '' for line in original.splitlines())
        self.assertIn('else\n    {\n' + expected + '\n    }', after)
        self.assertEqual(after.count('uint64_t base_reward;'), 1)
        self.assertNotIn('uint64_t base_reward =', after)
        self.assertEqual(before.split('    uint64_t full_reward_zone', 1)[1],
                         after.split('    uint64_t full_reward_zone', 1)[1])

    def test_all_production_reward_and_constructor_calls_pass_network(self):
        calls = []
        for name in ('src/cryptonote_core/blockchain.cpp', 'src/cryptonote_core/tx_pool.cpp',
                     'src/cryptonote_core/cryptonote_tx_utils.cpp'):
            for line in self.changed[name].decode().splitlines():
                if 'get_block_reward(' in line or ' = construct_miner_tx(' in line:
                    calls.append(line)
                    self.assertRegex(line, r', (m_nettype|nettype|m_blockchain.get_nettype\(\))\)')
        self.assertEqual(len(calls), 8)
        chain = self.changed['src/cryptonote_core/blockchain.cpp'].decode()
        self.assertNotIn('? DIFFICULTY_TARGET_V1 : DIFFICULTY_TARGET_V2', chain)
        self.assertNotIn('DIFFICULTY_TARGET_V2', chain)

    def test_zero_balance_does_not_select_genesis_and_accounting_is_unchanged(self):
        constructor = self.changed['src/cryptonote_core/cryptonote_tx_utils.cpp'].decode()
        self.assertIn('nettype == TESTNET && height == 0', constructor)
        self.assertIn('fee == 0', constructor)
        self.assertIn('get_config(TESTNET).GENESIS_TX', constructor)
        self.assertNotIn('already_generated_coins == 0', constructor)
        self.assertIn('block_reward += fee;', constructor)
        name = 'src/cryptonote_core/blockchain.cpp'
        before, after = self.originals[name].decode(), self.changed[name].decode()
        for marker in ('  if(base_reward + fee < money_in_use)',
                       'already_generated_coins = base_reward <',
                       'bei.already_generated_coins = (block_reward <'):
            self.assertEqual(before[before.index(marker):].splitlines()[0],
                             after[after.index(marker):].splitlines()[0])
        # Exact coinbase, point checks and all validation below them stay intact.
        self.assertEqual(before.split('  if(base_reward + fee < money_in_use)', 1)[1].split(
            '// get the block weights', 1)[0], after.split('  if(base_reward + fee < money_in_use)', 1)[1].split(
            '// get the block weights', 1)[0])

    def test_fallback_and_unknown_policy_are_refused(self):
        for key, new in [('reward_atomic', 12000000000000), ('target_seconds', 120)]:
            other = copy.deepcopy(self.value)
            other['consensus_proposal'][key] = new
            with self.assertRaisesRegex(ValueError, 'settled selected'):
                p.changes(self.originals, other)

    def test_source_drift_and_ambiguous_anchor_are_refused(self):
        for name in self.changed:
            other = dict(self.originals)
            other[name] = b'changed source'
            with self.subTest(name=name), self.assertRaises((ValueError, KeyError)):
                p.changes(other, self.value)
        with self.assertRaises(ValueError):
            p.replace('anchor anchor', 'anchor', 'new')
        # Exercise the actual binding reader with one changed extra source file.
        from unittest.mock import patch
        with patch.object(p.n, 'checked_source', return_value=self.originals), patch.object(
                p, 'BINDINGS', self.root / 'bad-binding.json'):
            n.write_json(p.BINDINGS, {'upstream_commit': self.value['upstream_commit'],
                                    'files': {'src/cryptonote_core/tx_pool.cpp': '0' * 64}})
            with self.assertRaisesRegex(ValueError, 'changed policy source'):
                p.checked_source(SOURCE)

    def test_consumed_grants_are_refused_before_output_creation(self):
        for grant in ('2d70177d-b7a7-4ef6-8079-242320bdcb1f', '15414082-2a53-4872-8d19-b87f302f0bae'):
            out = self.root / 'never'
            result = subprocess.run([sys.executable, '-B', str(n.HERE / 'run-policy.py'),
                '--out', str(out), '--grant-comment', grant], capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('prior grant is consumed', result.stderr)
            self.assertFalse(out.exists())

    def test_lock_contention_and_wrong_inode_refuse_before_native_admission(self):
        from unittest.mock import patch
        spec = importlib.util.spec_from_file_location('policy_driver', n.HERE / 'run-policy.py')
        driver = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(driver)
        lock_path = self.root / 'fixture.lock'
        lock_path.touch(mode=0o600)
        info = lock_path.stat()
        for case in ('held', 'wrong-inode'):
            with lock_path.open('r+') as holder:
                if case == 'held':
                    fcntl.flock(holder, fcntl.LOCK_EX | fcntl.LOCK_NB)
                identity = (info.st_dev, info.st_ino + (case == 'wrong-inode'))
                out = self.root / case
                with patch.object(driver.g, 'LOCK', lock_path), patch.object(driver.g, 'LOCK_ID', identity), \
                     patch.object(driver.g, 'admission') as admission, \
                     patch.object(driver.policy, 'checked_source', return_value=self.originals), \
                     patch.object(sys, 'argv', ['run-policy.py', '--out', str(out), '--grant-comment',
                                               '00000000-0000-0000-0000-000000000001']), \
                     patch.object(driver.signal, 'signal'), contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(driver.main(), 1)
                    admission.assert_not_called()
                receipt = json.loads((out / 'receipt.json').read_text())
                self.assertEqual(receipt['result'], 'FAILED_BOUNDED_ATTEMPT')
                self.assertNotIn('container_id', receipt)
                self.assertTrue(receipt['lock_fd_closed'])
                self.assertEqual((lock_path.stat().st_dev, lock_path.stat().st_ino), (info.st_dev, info.st_ino))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--scratch', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    SOURCE, SCRATCH = args.source.resolve(), args.scratch.resolve()
    os.umask(0o077)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PolicyBoundary))
    out = n.fresh_directory(args.evidence)
    n.write_json(out / 'checks.json', {'result': 'PASS_SOURCE_POLICY_CHECKS' if result.wasSuccessful() else 'FAIL',
        'tests': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
        'profile_sha256': n.profile_hash(n.profile()), 'native_policy': 'NOT_RUN',
        'native_network_separation': 'NOT_RUN', 'launch_ready': False})
    raise SystemExit(0 if result.wasSuccessful() else 1)
