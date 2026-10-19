#!/usr/bin/env python3
"""Boundary checks for proposal tooling. No daemon or cryptographic proof claim."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import network as n


class Boundaries(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=SCRATCH, prefix='network-check-')
        self.root = Path(self.temporary.name)
        self.p = n.profile()
        self.bootstrap = {
            'schema': 'meownero-vanguard-private-bootstrap/1',
            'primary': {'node_id': 'seed-a', 'operator_id': 'operator-a',
                        'endpoint': '127.0.0.1:48180', 'profile_sha256': n.profile_hash(self.p)},
            'recovery': {'node_id': 'seed-b', 'operator_id': 'operator-b',
                         'endpoint': '127.0.0.1:48280', 'profile_sha256': n.profile_hash(self.p)}}

    def tearDown(self):
        self.temporary.cleanup()

    def save(self, value, name='input.json'):
        path = self.root / name
        path.write_text(json.dumps(value))
        return path

    def invoke(self, *args):
        result = subprocess.run([sys.executable, '-B', str(n.HERE / 'network.py'), *map(str, args)],
                                capture_output=True, text=True, timeout=15)
        CLI_DIAGNOSTICS.append({'arguments': [str(a).replace(str(self.root), '<scratch>') for a in args],
                                'exit': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr})
        return result

    def test_exact_profile_copy_and_key_reordering(self):
        path = self.save(self.p)
        self.assertEqual(n.profile(path), self.p)
        path.write_text(json.dumps(self.p, sort_keys=True))
        self.assertEqual(n.profile_hash(n.profile(path)), n.profile_hash(self.p))
        self.assertFalse(n.profile(path)['launch_ready'])

    def test_foreign_profiles_are_refused_before_preparation(self):
        for selector in ('mainnet', 'stagenet', 'regtest', 'upstream-testnet', 'selected-9-90'):
            with self.subTest(selector=selector):
                other = copy.deepcopy(self.p)
                other['network']['native_selector'] = selector
                out = self.root / selector
                result = self.invoke('--profile', self.save(other), 'prepare', '--out', out,
                                     '--node-id', 'client-a', '--bootstrap', self.save(self.bootstrap, 'peers.json'))
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertFalse(out.exists())

    def test_changed_consensus_identity_and_assurance_are_refused(self):
        mutations = [('launch_ready', True), ('status', 'accepted'), ('valueless', False),
                     ('upstream_commit', '0' * 40), ('unresolved', [])]
        for key, value in mutations:
            other = copy.deepcopy(self.p)
            other[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                n.profile(self.save(other))
        for key, value in [('id_hex', '12' * 16), ('ports', {'p2p': 18080}),
                           ('dns_seeds', ['seeds.moneroseeds.se']), ('daemon_bootstrap_rpc', True)]:
            other = copy.deepcopy(self.p)
            other['network'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                n.profile(self.save(other))
        other = copy.deepcopy(self.p)
        other['consensus_proposal']['reward_atomic'] = 12000000000000
        with self.assertRaises(ValueError):
            n.profile(self.save(other))

    def test_superseded_v17_profile_and_bootstrap_digest_are_refused(self):
        other = copy.deepcopy(self.p)
        other['consensus_proposal']['activation'][1]['version'] = 17
        result = self.invoke('--profile', self.save(other), 'validate')
        self.assertEqual(result.returncode, 2, result.stderr)
        stale = copy.deepcopy(self.bootstrap)
        for role in ('primary', 'recovery'):
            stale[role]['profile_sha256'] = 'd3d9905bd3c1464f4940f49e0872dfa8e7510127ddf83b781d6c6743e0627168'
        out = self.root / 'stale'
        result = self.invoke('prepare', '--bootstrap', self.save(stale, 'peers.json'),
                             '--node-id', 'client-a', '--out', out)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertFalse(out.exists())

    def test_consultation_direction_does_not_accept_genesis_or_launch(self):
        self.assertEqual(self.p['consultation']['comment_id'], '3b6c0197-43f9-4c30-a90c-399f82fc0b57')
        self.assertEqual(self.p['consultation']['exact_genesis_and_candidate'], 'unverified')
        recipe = n.native_recipe(self.p)
        self.assertEqual(recipe['genesis_tx_hex'], self.p['consensus_proposal']['genesis_tx_hex'])
        self.assertEqual(recipe['genesis_block_hash'], self.p['consensus_proposal']['genesis_block_hash'])
        self.assertEqual(recipe['result'], 'PASS_NATIVE_RECIPE_HELPERS_ONLY')
        self.assertEqual(recipe['testnet_admission'], 'NOT_RUN')
        self.assertNotIn('cryptography-genesis-and-v18-activation-ruling', self.p['unresolved'])
        other = copy.deepcopy(self.p)
        other['consultation']['exact_genesis_and_candidate'] = 'accepted'
        with self.assertRaises(ValueError):
            n.profile(self.save(other))
        stale = copy.deepcopy(self.bootstrap)
        stale['primary']['profile_sha256'] = 'b1711b3114e234a4975bcefc6f02fa1175df1d213ed03372bb5c50bc503aef31'
        out = self.root / 'pre-consultation-profile'
        result = self.invoke('prepare', '--bootstrap', self.save(stale), '--node-id', 'client-a', '--out', out)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertFalse(out.exists())

    def test_changed_genesis_and_stale_pre_recipe_profile_are_refused(self):
        for key, value in [('genesis_tx_hex', '00'), ('genesis_block_hash', '0' * 64)]:
            other = copy.deepcopy(self.p)
            other['consensus_proposal'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                n.profile(self.save(other))
            with self.assertRaises(ValueError):
                n.native_recipe(other)
        stale = copy.deepcopy(self.bootstrap)
        stale['primary']['profile_sha256'] = '920825038185340ea4461e3899c0c74e579249fa57735621b7929dec4f3ef7c5'
        out = self.root / 'pre-recipe'
        result = self.invoke('prepare', '--bootstrap', self.save(stale), '--node-id', 'client-a', '--out', out)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertFalse(out.exists())

    def test_malformed_and_oversized_json(self):
        for raw in ('{"schema":1,"schema":2}', '{"x":NaN}', '{broken', ' ' * 65537):
            path = self.root / 'bad.json'
            path.write_text(raw)
            with self.subTest(raw=raw[:30]), self.assertRaises(ValueError):
                n.read_json(path)

    def test_primary_and_recovery_recipes_use_only_selected_peer(self):
        for role in ('primary', 'recovery'):
            out = self.root / role
            receipt = n.prepare(out, 'client-a', self.save(self.bootstrap), role, self.p)
            self.assertEqual(receipt['result'], 'PREPARED_NOT_STARTED')
            self.assertFalse(receipt['launch_ready'])
            self.assertEqual(receipt['profile_sha256'], n.profile_hash(self.p))
            daemon = (out / 'daemon.conf.proposal').read_text().splitlines()
            wallet = (out / 'wallet-rpc.conf.proposal').read_text().splitlines()
            self.assertIn('add-exclusive-node=' + self.bootstrap[role]['endpoint'], daemon)
            self.assertEqual(sum(line.startswith('add-exclusive-node=') for line in daemon), 1)
            self.assertIn('testnet=1', daemon)
            self.assertIn('restricted-rpc=1', daemon)
            self.assertIn('restricted-rpc=1', wallet)
            self.assertIn('rpc-bind-ip=127.0.0.1', wallet)
            self.assertIn('daemon-address=127.0.0.1:48081', wallet)
            self.assertFalse(any(line.startswith(('seed-node=', 'bootstrap-daemon-address=',
                                                  'disable-rpc-login=', 'regtest='))
                                 for line in daemon + wallet))
            database = Path(receipt['native_database'])
            self.assertEqual(database.parts[-2:], ('testnet', 'lmdb'))
            self.assertFalse(database.exists(), 'preparation must not create a native database')
            self.assertEqual(out.stat().st_mode & 0o777, 0o700)
            self.assertTrue(all(path.stat().st_mode & 0o777 == 0o600
                                for path in out.iterdir() if path.is_file()))

    def test_bootstrap_adverse_boundaries(self):
        for key, value in [('endpoint', None), ('endpoint', '198.51.100.2:48180'),
                           ('endpoint', 'seed.invalid:48180'), ('endpoint', '127.0.0.1:18080'),
                           ('endpoint', '127.0.0.1:0'), ('endpoint', '[::]:48180'),
                           ('endpoint', '127.0.0.1:48180\nbootstrap-daemon-address=foreign'),
                           ('profile_sha256', '0' * 64), ('operator_id', None),
                           ('node_id', '../escape')]:
            other = copy.deepcopy(self.bootstrap)
            other['primary'][key] = value
            out = self.root / 'bad-preparation'
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                n.prepare(out, 'client-a', self.save(other), 'primary', self.p)
            self.assertFalse(out.exists())
        for key in ('node_id', 'operator_id', 'endpoint'):
            other = copy.deepcopy(self.bootstrap)
            other['recovery'][key] = other['primary'][key]
            with self.subTest(collision=key), self.assertRaises(ValueError):
                n.topology(self.save(other), self.p)
        other = copy.deepcopy(self.bootstrap)
        other['bootstrap-daemon-address'] = 'http://foreign'
        with self.assertRaises(ValueError):
            n.topology(self.save(other), self.p)

    def test_data_directory_isolation_and_no_overwrite(self):
        a = n.prepare(self.root / 'a', 'client-a', self.save(self.bootstrap), 'primary', self.p)
        b = n.prepare(self.root / 'b', 'client-b', self.save(self.bootstrap), 'primary', self.p)
        self.assertNotEqual(a['native_database'], b['native_database'])
        sentinel = self.root / 'a' / 'sentinel'
        sentinel.write_text('preserve unrelated data')
        with self.assertRaises(ValueError):
            n.prepare(self.root / 'a', 'client-a', self.save(self.bootstrap), 'primary', self.p)
        self.assertEqual(sentinel.read_text(), 'preserve unrelated data')
        (self.root / 'alias').symlink_to(self.root / 'a', target_is_directory=True)
        with self.assertRaises(ValueError):
            n.prepare(self.root / 'alias' / 'new', 'client-a', self.save(self.bootstrap), 'primary', self.p)
        with self.assertRaises(ValueError):
            n.prepare(n.ROOT / 'never-create-network-test', 'client-a', self.save(self.bootstrap), 'primary', self.p)
        checkout = self.root / 'other-checkout'
        checkout.mkdir()
        subprocess.run(['git', 'init', '-q', str(checkout)], check=True, timeout=10)
        with self.assertRaises(ValueError):
            n.prepare(checkout / 'never', 'client-a', self.save(self.bootstrap), 'primary', self.p)
        self.assertFalse((checkout / 'never').exists())

    def test_bootstrap_port_aliases_are_refused_before_writing(self):
        # Core's exact reproduction: these two spellings reach the same socket.
        # Exercise both selected roles; an invalid recovery must fail even when
        # preparing for the primary. Keep the distinct positive control above.
        for alias in ('048180', '00048180', '４８１８０', '٤٨١٨٠', '+48180', '48180 ', '48180\n'):
            peers = copy.deepcopy(self.bootstrap)
            peers['recovery']['endpoint'] = '127.0.0.1:' + alias
            for role in ('primary', 'recovery'):
                out = self.root / 'alias-refused'
                with self.subTest(alias=alias, role=role):
                    result = self.invoke('prepare', '--bootstrap', self.save(peers),
                                         '--node-id', 'client-a', '--role', role, '--out', out)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertIn('canonical ASCII decimal', result.stderr)
                    self.assertFalse(out.exists())

    def test_self_peer_and_rpc_port_are_refused(self):
        for port in (48080, 48081, 48082, 48083):
            other = copy.deepcopy(self.bootstrap)
            other['primary']['endpoint'] = '127.0.0.1:' + str(port)
            with self.subTest(port=port), self.assertRaises(ValueError):
                n.prepare(self.root / 'never', 'client-a', self.save(other), 'primary', self.p)

    def test_readiness_and_launch_cannot_be_enabled(self):
        result = self.invoke('readiness')
        self.assertEqual(result.returncode, 3)
        self.assertEqual(json.loads(result.stdout)['result'], 'BLOCKED_PROTOCOL_AND_NATIVE_GATES')
        self.assertEqual(self.invoke('run').returncode, 2)

    def test_actual_source_overlay_is_scoped_and_reversible(self):
        if not SOURCE:
            self.skipTest('supply --source for the actual pinned-source checks')
        originals = n.checked_source(SOURCE)
        raw = originals['src/cryptonote_config.h']
        changed = n.identity_overlay(raw, self.p)
        before, after = raw.decode(), changed.decode()
        self.assertEqual(before.split('  namespace testnet\n')[0],
                         after.split('  namespace testnet\n')[0])
        self.assertEqual(before.split('  namespace stagenet\n')[1],
                         after.split('  namespace stagenet\n')[1])
        for constant in ('PREFIX = 4240;', 'PREFIX = 4241;', 'PREFIX = 4242;',
                         'P2P_DEFAULT_PORT = 48080;', 'RPC_DEFAULT_PORT = 48081;',
                         'ZMQ_RPC_DEFAULT_PORT = 48082;', 'GENESIS_NONCE = 424001;'):
            self.assertIn(constant, after)
        self.assertEqual([line for line in before.splitlines() if 'GENESIS_TX =' in line],
                         [line for line in after.splitlines() if 'GENESIS_TX =' in line])
        reordered = json.loads(json.dumps(self.p, sort_keys=True))
        self.assertEqual(changed, n.identity_overlay(raw, reordered))
        out = self.root / 'overlay'
        receipt = n.overlay(SOURCE, out, self.p)
        self.assertEqual(receipt['native_network_proof'], 'NOT_RUN')
        tree = self.root / 'disposable-source'
        (tree / 'src').mkdir(parents=True)
        (tree / 'src/cryptonote_config.h').write_bytes(raw)
        patch = out / 'identity-only.patch'
        for reverse, expected in ((False, changed), (True, raw)):
            cmd = ['git', 'apply'] + (['--reverse'] if reverse else []) + [str(patch)]
            result = subprocess.run(cmd, cwd=tree, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((tree / 'src/cryptonote_config.h').read_bytes(), expected)

    def test_foreign_source_tree_is_refused(self):
        if not SOURCE:
            self.skipTest('supply --source for the actual pinned-source checks')
        other = self.root / 'foreign'
        other.mkdir()
        subprocess.run(['git', 'init', '-q', str(other)], check=True, timeout=10)
        with self.assertRaises(subprocess.CalledProcessError):
            n.checked_source(other)

    def test_native_inputs_patch_scope_reversibility_and_no_overwrite(self):
        if not SOURCE:
            self.skipTest('supply --source for actual pinned source')
        originals = n.checked_source(SOURCE)
        changes = n.genesis_admission_changes(originals)
        fork = 'src/hardforks/hardforks.cpp'
        chain = 'src/cryptonote_core/blockchain.cpp'
        self.assertEqual(set(changes), {fork, chain})
        before, after = originals[fork].decode(), changes[fork].decode()
        self.assertEqual(before.split('const hardfork_t testnet_hard_forks[]')[0],
                         after.split('const hardfork_t testnet_hard_forks[]')[0])
        self.assertEqual(before.split('const hardfork_t stagenet_hard_forks[]')[1],
                         after.split('const hardfork_t stagenet_hard_forks[]')[1])
        self.assertIn('{ 18, 1, 0, 1341378001 }', after)
        self.assertIn('testnet_hard_fork_version_1_till = 0;', after)
        # This is a source-scope assertion, not a simulated block-admission test.
        changed = changes[chain].decode()
        start = changed.index('  // Dedicated TESTNET zero-premine genesis.')
        end = changed.index('  if(base_reward + fee < money_in_use)', start)
        self.assertEqual((changed[:start] + changed[end:]).encode(), originals[chain])
        self.assertIn('m_nettype == TESTNET && get_block_height(b) == 0', changed[start:end])
        self.assertNotIn('return true', changed[start:end])
        self.assertNotIn('already_generated_coins ==', changed[start:end])
        self.assertIn('b.miner_tx.vout.size() == 1', changed[start:end])
        output = self.root / 'native-inputs'
        receipt = n.genesis_inputs(SOURCE, output, self.p)
        self.assertEqual(receipt['testnet_admission'], 'NOT_RUN')
        self.assertFalse(receipt['launch_ready'])
        for name, digest in receipt['owned_source_sha256'].items():
            self.assertEqual(n.sha((output / name).read_bytes()), digest)
        tree = self.root / 'native-disposable'
        for name in changes:
            (tree / name).parent.mkdir(parents=True, exist_ok=True)
            (tree / name).write_bytes(originals[name])
        patch = output / 'activation-genesis-admission.patch'
        for reverse, expected in ((False, changes), (True, originals)):
            cmd = ['git', 'apply'] + (['--reverse'] if reverse else []) + [str(patch)]
            result = subprocess.run(cmd, cwd=tree, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            for name in changes:
                self.assertEqual((tree / name).read_bytes(), expected[name])
        original_receipt = (output / 'genesis-inputs.json').read_bytes()
        with self.assertRaises(ValueError):
            n.genesis_inputs(SOURCE, output, self.p)
        self.assertEqual((output / 'genesis-inputs.json').read_bytes(), original_receipt)

    def test_native_derived_admission_patch_scope_reversibility_and_no_overwrite(self):
        if not SOURCE:
            self.skipTest('supply --source for actual pinned source')
        originals = n.checked_source(SOURCE)
        output = self.root / 'admission'
        receipt = n.admission_overlay(SOURCE, output, self.p)
        self.assertEqual(set(receipt['files']), {'src/cryptonote_config.h',
            'src/hardforks/hardforks.cpp', 'src/cryptonote_core/blockchain.cpp'})
        self.assertEqual(receipt['testnet_admission'], 'NOT_RUN')
        self.assertEqual(receipt['selected_policy'], 'NOT_INTEGRATED')
        self.assertFalse(receipt['launch_ready'])
        tree = self.root / 'admission-disposable'
        for name in receipt['files']:
            (tree / name).parent.mkdir(parents=True, exist_ok=True)
            (tree / name).write_bytes(originals[name])
        patch = output / 'testnet-admission-prerequisite.patch'
        subprocess.run(['git', 'apply', str(patch)], cwd=tree, check=True, timeout=10)
        before = originals['src/cryptonote_config.h'].decode()
        after = (tree / 'src/cryptonote_config.h').read_text()
        self.assertEqual(before.split('  namespace testnet\n')[0], after.split('  namespace testnet\n')[0])
        self.assertEqual(before.split('  namespace stagenet\n')[1], after.split('  namespace stagenet\n')[1])
        self.assertIn('GENESIS_TX = "' + self.p['consensus_proposal']['genesis_tx_hex'] + '";', after)
        for name, hashes in receipt['files'].items():
            self.assertEqual(n.sha((tree / name).read_bytes()), hashes['changed_sha256'])
        subprocess.run(['git', 'apply', '--reverse', str(patch)], cwd=tree, check=True, timeout=10)
        for name in receipt['files']:
            self.assertEqual((tree / name).read_bytes(), originals[name])
        with self.assertRaises(ValueError):
            n.admission_overlay(SOURCE, output, self.p)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scratch', type=Path, required=True)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    SCRATCH, SOURCE = args.scratch, args.source
    CLI_DIAGNOSTICS = []
    runner = unittest.TextTestRunner(verbosity=2)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries)
    result = runner.run(suite)
    args.evidence.mkdir(exist_ok=True)
    n.write_json(args.evidence / 'tooling-checks.json', {
        'result': 'PASS_TOOLING_ONLY' if result.wasSuccessful() else 'FAIL_TOOLING',
        'tests': result.testsRun, 'skipped': len(result.skipped),
        'failures': len(result.failures), 'errors': len(result.errors),
        'python': sys.version, 'profile_sha256': n.profile_hash(n.profile()),
        'native_network_proof': 'NOT_RUN', 'cli_diagnostics': CLI_DIAGNOSTICS})
    sys.exit(0 if result.wasSuccessful() else 1)
