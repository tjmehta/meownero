"""Connected F1 source checks; native effects are explicitly substituted."""
import contextlib
import ast
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

import profile_contract as c
from integration import funded_contract as f
from integration import funded_driver as driver

spec = importlib.util.spec_from_file_location('funded_controller_tests', c.HERE/'run-profile.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


class NativeFixture:
    """One synthetic ledger behind the actual Journey orchestration and requests."""
    def __init__(self, root, adverse=None):
        self.root, self.adverse = root, adverse
        self.count = 1
        self.b_count = 1
        self.mining = False
        self.b_alive = False
        self.pending = []
        self.txs = {}
        self.events = []
        self.pid = 100000
        self.coinbase = '1'*64
        self.coinbase_key = '2'*64
        self.received_key = '3'*64
        self.restored = False
        self.live = {}
        self.cli_count = 0

    def tick(self, seconds):
        if self.mining:
            self.count += 1
            for txid in self.pending:
                self.txs[txid]['block'] = self.count-1
            self.pending.clear()
        if self.b_alive:
            self.b_count = self.count

    def launch(self, name, argv, cwd, env=None, **kwargs):
        if '--wallet-dir' in argv and '--password-file' in argv:
            raise ValueError('pinned wallet-dir/password-file incompatibility')
        self.events.append(('launch', name, list(argv), dict(env or {})))
        self.pid += 1
        process = types.SimpleNamespace(pid=self.pid, returncode=None)
        process.poll = lambda: process.returncode
        self.live[name] = process
        driver.d.PROCS[name] = (process, [process.pid, str(self.pid)])
        if name == 'node0':
            self.mining = '--start-mining' in argv
        elif name == 'node1':
            self.b_alive = True
            self.b_count = self.count
            if self.count > 3:
                self.events.append(('B_restart_while_A_mining', self.mining))
        else:
            port = int(argv[argv.index('--rpc-bind-port')+1])
            login = cwd/f'monero-wallet-rpc.{port}.login'
            login.write_text('fixture:PRIVATE_LOGIN')
            login.chmod(0o600)
        return process

    def stop(self, name, graceful=True):
        self.events.append(('stop', name, graceful))
        self.live[name].returncode = 0
        if name == 'node0': self.mining = False
        if name == 'node1': self.b_alive = False
        return driver.d.PROCS[name][1]

    def seal(self, root, kind, binaries):
        driver.d.SAVED[str(root)] = {'kind': kind}
        return driver.d.SAVED[str(root)]

    def cli(self, root, port, create=False):
        self.cli_count += 1
        self.events.append(('cli', port, create))
        (root/'wallet').write_text('synthetic wallet')
        self.seal(root, 'wallet', {})

    def rpc(self, port, login):
        fixture = self
        class RPC:
            def __init__(self): self.port, self.login = port, login
            def healthy(self, wallet=False): return self.call('get_balance' if wallet else 'get_info')
            def auth_controls(self, wallet=False): fixture.events.append(('auth', port, wallet))
            def call(self, method, params=None, path='json_rpc', login='current', raw=False):
                return fixture.call(port, method, params or {}, path, raw)
        return RPC()

    def output(self, txid, amount, key, block):
        spent = any(key in x['spent_key_images']['key_images'] for x in self.txs.values())
        return dict(amount=amount, tx_hash=txid, key_image=key, pubkey='4'*64,
            global_index=1, block_height=block, spent=spent,
            unlocked=self.count >= (61 if block == 1 else block+10))

    def call(self, port, method, params, path, raw):
        self.events.append(('rpc', port, method, copy.deepcopy(params), path, raw))
        if port in (48081, 48181):
            count = self.count if port == 48081 else self.b_count
            if method == 'get_info':
                tip = c.GENESIS if count == 1 and self.adverse != 'wrong_genesis' else f'{count:064x}'
                return dict(status='OK', height=count, top_block_hash=tip,
                    wide_cumulative_difficulty=str(count))
            if path == 'get_transaction_pool_hashes': return dict(tx_hashes=list(self.pending))
            if method == 'get_block':
                height = params['height']
                unlock = 62 if height == 1 and self.adverse == 'wrong_coinbase_unlock' else height+60
                data = dict(miner_tx=dict(unlock_time=unlock, vout=[dict(amount=9*f.ATOMIC)]),
                    tx_hashes=[k for k, tx in self.txs.items() if tx.get('block') == height])
                return dict(json=json.dumps(data), miner_tx_hash=self.coinbase,
                    block_header=dict(height=height, hash=f'{height+100:064x}', orphan_status=False))
            if path == 'get_transactions':
                if self.adverse == 'missing_confirmation': return dict(status='OK', txs=[])
                txid, = params['txs_hashes']
                tx = self.txs[txid]
                decoded = dict(rct_signatures=dict(type=7, txnFee=tx['fee']), unlock_time=0,
                    vout=[dict(target=dict(carrot_v1={}))],
                    vin=[dict(key=dict(key_offsets=[], k_image=tx['spent_key_images']['key_images'][0]))])
                if self.adverse == 'legacy_transaction': decoded['rct_signatures']['type'] = 6
                return dict(status='OK', txs=[dict(tx_hash=txid, in_pool=False,
                    block_height=tx['block'], confirmations=count-tx['block'], as_json=json.dumps(decoded))])
        else:
            is_a = port == 48083
            if method == 'get_version': return dict(version=1)
            if method in ('store', 'refresh'): return {}
            if method == 'get_balance':
                balance, unlocked = f.ATOMIC, 0 if is_a and self.count == 60 else f.ATOMIC
                if is_a and self.count == 60:
                    if self.adverse == 'zero_balance': balance = 0
                    if self.adverse == 'boolean_balance': balance = True
                    if self.adverse == 'early_unlocked_balance': unlocked = 1
                    if self.adverse == 'boolean_unlocked_balance': unlocked = False
                return dict(balance=balance, unlocked_balance=unlocked)
            if method == 'get_address': return dict(address='A_ADDRESS' if is_a else 'B_ADDRESS')
            if method == 'query_key': return dict(key=' '.join(['synthetic']*25))
            if method == 'restore_deterministic_wallet':
                self.restored = True
                return dict(address='B_ADDRESS', seed='PRIVATE_RECOVERY_SEED')
            if method == 'incoming_transfers':
                if is_a:
                    value = self.output(self.coinbase, 9*f.ATOMIC, self.coinbase_key, 1)
                    if self.count == 61 and self.adverse == 'eligible_lineage': value['pubkey'] = 'f'*64
                    return dict(transfers=[value])
                found = [(k, tx) for k, tx in self.txs.items() if tx['amount'] == f.ATOMIC and 'block' in tx]
                key = 'f'*64 if self.restored and self.adverse == 'restored_lineage' else self.received_key
                return dict(transfers=[self.output(k, f.ATOMIC, key, tx['block']) for k, tx in found])
            if method == 'transfer':
                address = params['destinations'][0]['address']
                refusal = -2 if address == driver.d.FOREIGN else -4 if self.count == 60 else None
                if refusal and self.adverse != ('wrong_network_accepted' if refusal == -2 else 'early_spend_accepted'):
                    if refusal == -4:
                        if self.adverse in ('early_wrong_code', 'baseline_legacy_refusal'): refusal = -37
                        if self.adverse == 'early_pool_change': self.pending.append('f'*64)
                        if self.adverse == 'early_chain_change': self.count += 1; self.b_count += 1
                        if self.adverse == 'early_error_with_result':
                            return 200, dict(error=dict(code=-4), result={})
                    return 200, dict(error=dict(code=refusal, message='PRIVATE_NATIVE_ERROR'))
                txid = str(len(self.txs)+5)*64
                key = self.coinbase_key if is_a else self.received_key
                if is_a and self.adverse == 'wrong_coinbase_input': key = 'f'*64
                if not is_a and self.adverse == 'wrong_spent_input': key = 'f'*64
                tx = dict(tx_hash=txid, amount=params['destinations'][0]['amount'], fee=1000,
                    spent_key_images=dict(key_images=[key]))
                if params['do_not_relay']:
                    return 200, dict(result=tx)
                self.txs[txid] = tx
                self.pending.append(txid)
                return 200, dict(result=tx)
        raise AssertionError((port, method, path))

    @contextlib.contextmanager
    def installed(self):
        private, binary = self.root/'private', self.root/'bin'
        private.mkdir(mode=0o700)
        binary.mkdir(mode=0o700)
        for name in ('monerod', 'monero-wallet-cli', 'monero-wallet-rpc'):
            (binary/name).write_text('substituted native executable')
        d = driver.d
        with contextlib.ExitStack() as stack:
            replacements = dict(PRIVATE=private, BIN=binary, PROCS={}, SAVED={},
                DEADLINE=time.monotonic()+120, HARD_END=time.monotonic()+150,
                launch=self.launch, stop=self.stop, seal=self.seal, cli=self.cli, RPC=self.rpc,
                released=lambda root: None, absent=lambda port: None, census=lambda: 4,
                creation=lambda kind, binaries: dict(kind=kind))
            for key, value in replacements.items(): stack.enter_context(patch.object(d, key, value))
            stack.enter_context(patch.object(c, 'root_manifest', lambda root, expected: root))
            stack.enter_context(patch.object(time, 'sleep', self.tick))
            yield


class FundedDriver(unittest.TestCase):
    def test_actual_journey_connected_positive_native_substitution(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = NativeFixture(Path(temp))
            with fixture.installed():
                journey = driver.Journey()
                journey.run()
            states = [journey.rows[file][key]['status'] for file, keys in f.REQUIRED.items()
                      if file not in ('build.json', 'resources.json', 'cleanup.json') for key in keys]
            self.assertEqual(set(states), {'PASS'})
            self.assertEqual(fixture.count, 73)
            self.assertEqual(len(fixture.txs), 2)
            self.assertIn(('B_restart_while_A_mining', True), fixture.events)
            self.assertEqual(fixture.cli_count, 5)
            for event in fixture.events:
                if event[0] == 'launch':
                    argv, env = event[2:]
                    self.assertNotIn('--disable-rpc-login', argv)
                    self.assertNotIn('--fixed-difficulty', argv)
                    self.assertNotIn('--regtest', argv)
                    if event[1].startswith('node'):
                        self.assertEqual(env['MONERO_RANDOMX_UMASK'], '4')
                    if not event[1].startswith('node'):
                        self.assertNotIn('--restricted-rpc', argv)
                        self.assertNotIn('RPC_LOGIN', env)
                        if '--wallet-dir' in argv: self.assertNotIn('--password-file', argv)
            encoded = json.dumps(journey.rows)
            for secret in ('A_ADDRESS', 'B_ADDRESS', 'PRIVATE_', fixture.coinbase_key, fixture.received_key):
                self.assertNotIn(secret, encoded)
            for file, keys in f.REQUIRED.items():
                if file in ('build.json', 'resources.json', 'cleanup.json'): continue
                for key in keys:
                    witness = {k:v for k,v in journey.rows[file][key].items() if k != 'status'}
                    self.assertIsNone(r.witness_failure(witness, f.shapes()[key], key, complete=True))
            requests = [e[3] for e in fixture.events if e[:3] == ('rpc', 48083, 'transfer')
                        and e[3]['destinations'][0]['address'] == 'B_ADDRESS']
            self.assertEqual(requests[0], requests[1])
            self.assertEqual(len(journey.daemon_light_modes),
                sum(e[0] == 'launch' and e[1].startswith('node') for e in fixture.events))

    def test_actual_journey_refuses_adverse_native_effects(self):
        for adverse in ('early_spend_accepted', 'wrong_network_accepted', 'missing_confirmation',
                        'restored_lineage', 'wrong_spent_input', 'legacy_transaction', 'wrong_genesis',
                        'zero_balance', 'boolean_balance', 'early_unlocked_balance',
                        'boolean_unlocked_balance', 'wrong_coinbase_unlock', 'eligible_lineage',
                        'early_wrong_code', 'early_error_with_result', 'early_pool_change',
                        'early_chain_change', 'wrong_coinbase_input'):
            with self.subTest(adverse=adverse), tempfile.TemporaryDirectory() as temp:
                fixture = NativeFixture(Path(temp), adverse)
                with fixture.installed():
                    journey = driver.Journey()
                    with self.assertRaises(ValueError): journey.run()
                    self.assertNotEqual(f.verdict(journey.rows), 'PASS_FUNDED_TWO_PEER_JOURNEY_ONLY')

    def test_missing_or_ineffective_mask_refuses_before_each_daemon_start(self):
        for index in (0, 1):
            for mask in (None, '0', '2', 4, '4extra'):
                with self.subTest(index=index, mask=mask), tempfile.TemporaryDirectory() as temp:
                    fixture = NativeFixture(Path(temp))
                    with fixture.installed():
                        journey = driver.Journey()
                        original = journey.launch_daemon
                        def altered(name, argv, root, env):
                            if mask is None: env.pop('MONERO_RANDOMX_UMASK')
                            else: env['MONERO_RANDOMX_UMASK'] = mask
                            return original(name, argv, root, env)
                        with patch.object(journey, 'launch_daemon', altered):
                            with self.assertRaisesRegex(ValueError, 'light mode required'):
                                journey.node(index)
                        self.assertFalse(any(e[0] == 'launch' for e in fixture.events))

    def test_light_mode_witness_requires_complete_launch_history(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = NativeFixture(Path(temp))
            with fixture.installed():
                journey = driver.Journey()
                original = journey.launch_daemon
                def corrupted(*args):
                    original(*args)
                    journey.daemon_light_modes[-1] = False
                with patch.object(journey, 'launch_daemon', corrupted):
                    with self.assertRaisesRegex(ValueError, 'light-mode history'): journey.run()
                self.assertEqual(journey.rows['isolation.json']['native_mining_bounds']['status'], 'NOT_RUN')

    def test_b_restart_missing_mask_never_starts_second_process(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = NativeFixture(Path(temp))
            with fixture.installed():
                journey = driver.Journey()
                journey.node(1)
                journey.stop_node(1)
                original = journey.launch_daemon
                def altered(name, argv, root, env):
                    env.pop('MONERO_RANDOMX_UMASK')
                    return original(name, argv, root, env)
                with patch.object(journey, 'launch_daemon', altered):
                    with self.assertRaisesRegex(ValueError, 'light mode required'): journey.node(1)
            self.assertEqual(sum(e[:2] == ('launch', 'node1') for e in fixture.events), 1)

    def baseline_journey(self):
        raw = subprocess.check_output(['git', '-C', str(c.HERE.parents[1]), 'show',
            '68963718f5b96b0e1b3cba668f748ee7ac24b4a4:vanguard/network/integration/funded_driver.py'])
        cls = next(x for x in ast.parse(raw).body if isinstance(x, ast.ClassDef) and x.name == 'Journey')
        namespace = dict(vars(driver))
        exec(compile(ast.Module(body=[cls], type_ignores=[]), '<exact-68963718-Journey>', 'exec'), namespace)
        return namespace['Journey']

    def test_known_bad_68963718_rejects_active_carrot_refusal(self):
        baseline = self.baseline_journey()
        with tempfile.TemporaryDirectory() as temp:
            fixture = NativeFixture(Path(temp))
            with fixture.installed():
                with self.assertRaisesRegex(ValueError, 'expected native transfer refusal'):
                    baseline().run()
            self.assertEqual(fixture.count, 60)
            self.assertEqual(fixture.txs, {})

    def test_known_bad_68963718_claims_light_mode_without_mask(self):
        baseline = self.baseline_journey()
        with tempfile.TemporaryDirectory() as temp:
            fixture = NativeFixture(Path(temp), 'baseline_legacy_refusal')
            with fixture.installed():
                journey = baseline()
                journey.run()
            self.assertTrue(journey.rows['isolation.json']['native_mining_bounds']['light_mode'])
            launches = [e for e in fixture.events if e[0] == 'launch' and e[1].startswith('node')]
            self.assertGreater(len(launches), 2)
            self.assertTrue(all('MONERO_RANDOMX_UMASK' not in e[3] for e in launches))

    def test_ceiling_deadline_and_overshoot_abort(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = NativeFixture(Path(temp))
            with fixture.installed():
                journey = driver.Journey()
                journey.node(0)
                fixture.count = 80
                with self.assertRaisesRegex(ValueError, 'ceiling'): journey.state(0)
                fixture.count = 81
                with self.assertRaisesRegex(ValueError, 'count bound'): journey.state(0)
                fixture.count = 1
                with patch.object(driver.d, 'DEADLINE', time.monotonic()-1):
                    with self.assertRaises(ValueError): journey.wait(lambda: False)
                def skip(seconds):
                    fixture.count += 3
                    fixture.b_count = fixture.count
                journey.node(1)
                with patch.object(time, 'sleep', skip):
                    with self.assertRaisesRegex(ValueError, 'overshot'): journey.mine_to(3, 'A_ADDRESS')

    def test_pinned_restore_option_negative_and_private_rpc_password(self):
        with tempfile.TemporaryDirectory() as temp:
            fixture = NativeFixture(Path(temp))
            with self.assertRaisesRegex(ValueError, 'incompatibility'):
                fixture.launch('restore', ['--wallet-dir', temp, '--password-file', '/private/password'], Path(temp))
            with fixture.installed():
                journey = driver.Journey()
                journey.run()
            restores = [event for event in fixture.events if event[:3] == ('rpc', 48183, 'restore_deterministic_wallet')]
            self.assertEqual(len(restores), 1)
            self.assertEqual(restores[0][3]['restore_height'], 0)
            self.assertTrue(restores[0][3]['password'])
            for event in fixture.events:
                if event[0] == 'launch': self.assertNotIn(restores[0][3]['password'], event[2])


class FundedContract(unittest.TestCase):
    def test_funded_native_source_bindings_match_exact_git_objects(self):
        value = c.json_file(c.HERE/'integration/funded-native-bindings.json')
        self.assertEqual(value['upstream'], 'e151643c5269c83bf24a83b2548e2493876026b2')
        for name, binding in value['files'].items():
            raw = (r.g.BASE/'monero-fcmp'/name).read_bytes()
            self.assertEqual(len(raw), binding['bytes'])
            self.assertEqual(c.digest(raw), binding['sha256'])
            self.assertEqual(raw, subprocess.check_output(['git', '-C', str(r.g.BASE/'monero-fcmp'),
                'show', value['upstream']+':'+name], timeout=10))
        for name, submodule in value['submodules'].items():
            source = r.g.BASE/'monero-fcmp'
            entry = subprocess.check_output(['git', '-C', str(source), 'ls-tree', value['upstream'], name], text=True)
            self.assertEqual(entry.split()[2], submodule['commit'])
            for path, binding in submodule['files'].items():
                raw = (source/name/path).read_bytes()
                self.assertEqual(len(raw), binding['bytes'])
                self.assertEqual(c.digest(raw), binding['sha256'])
                self.assertEqual(raw, subprocess.check_output(['git', '-C', str(source/name),
                    'show', submodule['commit']+':'+path], timeout=10))

    def grant(self, root):
        return dict(schema='meownero-direct-profile-grant/1', authorized=True,
            candidate_commit='a'*40, inputs_sha256='b'*64, artifact_sha256='c'*64,
            runner_sha256='d'*64, output_root=str(root), attempts=1, retry=False,
            wall_seconds=15000, build_seconds=0, runtime_seconds=14700, cleanup_seconds=300,
            container_flags=r.CONTAINER_FLAGS, workload=f.WORKLOAD, non_genesis_blocks=79,
            transactions=10, mode='runtime-only', reuse_build_root=f.RETAINED_ROOT,
            retained_build_sha256=f.RETAINED_SHA256, valid_from_unix=0,
            valid_until_unix=200000, artifact_attachment_id='22222222-2222-4222-8222-222222222222',
            load_rule=dict(metric='host-load-1-5-15', maximum=[9,9,9]),
            host_overhead_allowance=dict(mode='measured-controller-and-descendants-not-kernel-enforced',
                peak_rss_bytes=1024**3, cpu_seconds=4000, peak_pids=32), detached_session=True,
            no_other_heavy_lock_workload_scheduled=True, coordination_window_seconds=15000,
            main_chain_count_max=80, retained_build_authority_comment=f.AUTHORITY_COMMENT)

    def parse(self, value, **kwargs):
        comment = dict(issueId=c.ISSUE, authorAgentId=c.PLATFORM, authorUserId=None,
            body='```meownero-direct-profile-grant\n'+json.dumps(value)+'\n```')
        return r.grant_payload(comment, commit='a'*40, inputs_hash='b'*64, artifact_hash='c'*64,
            runner_hash='d'*64, output=Path('/owned/attempt'), now=1000,
            reuse=dict(root=Path(f.RETAINED_ROOT), manifest_sha256=f.RETAINED_SHA256), **kwargs)

    def test_grant_bound_workload_caps_retained_authority_window_and_no_schedule(self):
        value = self.grant(Path('/owned/attempt'))
        self.assertEqual(self.parse(value, workload=f.WORKLOAD), value)
        for key, wrong in dict(workload=r.GENESIS_WORKLOAD, runtime_seconds=600,
                wall_seconds=900, non_genesis_blocks=80, transactions=11,
                detached_session=False, no_other_heavy_lock_workload_scheduled=False,
                main_chain_count_max=81, retained_build_authority_comment='wrong',
                retained_build_sha256='f'*64, coordination_window_seconds=900,
                valid_until_unix=50000).items():
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.parse(dict(value, **{key: wrong}), workload=f.WORKLOAD)
        with self.assertRaises(ValueError): self.parse(value)

    def test_controller_funded_deadlines_entry_and_complete_rows(self):
        value = self.grant(Path('/owned/attempt'))
        control = r.Controller(Path('/owned/attempt'), value, 100)
        self.assertEqual((control.build_end, control.work_end, control.end), (14800, 14800, 15100))
        cmd = r.container_command(Path('/owned/attempt'), 'owned', 'image', f.WORKLOAD)
        self.assertEqual(cmd[-1], '/out/harness/integration/funded-runtime.sh')
        self.assertNotIn('build.sh', cmd)
        rows = f.empty_rows()
        self.assertEqual(f.verdict(rows), 'INCOMPLETE')
        for file in rows:
            for key in rows[file]: rows[file][key]['status'] = 'PASS'
        self.assertEqual(f.verdict(rows), 'PASS_FUNDED_TWO_PEER_JOURNEY_ONLY')
        rows['wallet.json']['received_output_spend']['status'] = 'FAIL'
        self.assertEqual(f.verdict(rows), 'FAIL')

    def test_closed_funded_exports_reject_secrets_types_and_missing_witnesses(self):
        witness = dict(status='PASS', code=-2, unchanged_pool=True)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root/'auth.json'
            path.write_text(json.dumps(dict(wrong_network_payment_refusal=witness)))
            self.assertEqual(r.read_public_rows(path, r.public_shapes(f.WORKLOAD), f.REQUIRED)
                ['wrong_network_payment_refusal'], witness)
            for altered in (dict(witness, code=True), dict(witness, seed='PRIVATE_SECRET'),
                            dict(status='PASS', code=-2)):
                path.write_text(json.dumps(dict(wrong_network_payment_refusal=altered)))
                with self.assertRaises(r.PublicWitnessError):
                    r.read_public_rows(path, r.public_shapes(f.WORKLOAD), f.REQUIRED)
            (root/'public').mkdir()
            (root/'public/auth.json').write_text(json.dumps(dict(wrong_network_payment_refusal=witness)))
            (root/'public/seed.private').write_text('PRIVATE_SECRET')
            rows = f.empty_rows()
            rejected = r.collect_public(root, rows, workload=f.WORKLOAD)
            self.assertEqual(rejected, ['unexpected-public-entry'])
            self.assertEqual(list((root/'public').iterdir()), [])
            self.assertNotIn('PRIVATE_SECRET', json.dumps(rows))

    def test_actual_controller_main_funded_pass_and_partial_failure_retention(self):
        for incomplete in (False, True):
            with self.subTest(incomplete=incomplete), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                fixture_root = root/'native-fixture'
                fixture_root.mkdir()
                fixture = NativeFixture(fixture_root)
                with fixture.installed():
                    journey = driver.Journey()
                    journey.run()
                output = root/'attempt'
                inputs = root/'inputs.json'
                inputs.write_text('{}')
                lock = root/'disposable.lock'
                lock.touch(mode=0o600)
                lock_info = lock.stat()
                grant = self.grant(output)
                grant.update(inputs_sha256=c.digest(inputs.read_bytes()),
                    runner_sha256=c.digest((c.HERE/'run-profile.py').read_bytes()),
                    valid_until_unix=time.time()+200000)
                comment = dict(id='11111111-1111-4111-8111-111111111111', issueId=c.ISSUE,
                    authorAgentId=c.PLATFORM, authorUserId=None,
                    body='```meownero-direct-profile-grant\n'+json.dumps(grant)+'\n```')
                build_rows = dict(
                    three_production_binaries=dict(status='PASS', binaries={name:dict(sha256='e'*64, needed=[])
                        for name in r.BINARIES}), rpc_translation_unit=dict(status='PASS', object_sha256='f'*64))
                reuse = dict(root=Path(f.RETAINED_ROOT), manifest_sha256=f.RETAINED_SHA256,
                    rows=build_rows, binaries={name:'e'*64 for name in r.BINARIES})
                state, events = dict(active=False), []
                def api(path):
                    return b'packet' if '/attachments/' in path else json.dumps(comment).encode()
                grant['artifact_sha256'] = c.digest(b'packet')
                comment['body'] = '```meownero-direct-profile-grant\n'+json.dumps(grant)+'\n```'
                def stage(control, inputs, manifest, reuse):
                    events.append('stage')
                    (control.root/'staging').mkdir(mode=0o700)
                def admission(*args):
                    events.append('admit')
                    return dict(fixture=True)
                def run(control, argv, deadline, **kwargs):
                    if 'image' in argv and 'inspect' in argv:
                        events.append('image')
                        return subprocess.CompletedProcess(argv, 0, json.dumps([dict(Id='image')]).encode(), b'')
                    if 'create' in argv:
                        events.append('create')
                        self.assertEqual(argv[-1], '/out/harness/integration/funded-runtime.sh')
                        state['active'] = True
                    elif 'start' in argv:
                        events.append('start')
                        rows = copy.deepcopy(journey.rows)
                        if incomplete: rows['wallet.json']['received_output_spend'] = dict(status='NOT_RUN')
                        for file in f.REQUIRED:
                            if file not in ('build.json', 'resources.json', 'cleanup.json'):
                                (control.root/'public'/file).write_text(json.dumps(rows[file]))
                        (control.root/'staging/resources-runtime.json').write_text(json.dumps(dict(oom=0, oom_kill=0)))
                    elif 'rm' in argv:
                        events.append('rm')
                        state['active'] = False
                    else: raise AssertionError(argv)
                    return subprocess.CompletedProcess(argv, 0, b'', b'PRIVATE_CHILD_OUTPUT')
                def inspect(*args):
                    return dict(Id='a'*64, State=dict(Running=False, ExitCode=0, OOMKilled=False)) if state['active'] else None
                def sample(control, force=False): control.samples += 1
                argv = ['run-profile.py', '--inputs', str(inputs), '--grant-comment', comment['id'],
                    '--artifact-sha256', c.digest(b'packet'), '--out', str(output),
                    '--reuse-build', f.RETAINED_ROOT, '--workload', f.WORKLOAD]
                with contextlib.ExitStack() as stack:
                    for target, name, value in [
                        (sys, 'argv', argv), (r, 'api', api),
                        (r, 'check_inputs', lambda path: dict(builder_image='image')),
                        (r, 'reuse_build', lambda root, manifest: reuse),
                        (r, 'acquire_lock', lambda: (os.open(lock, os.O_RDONLY),
                            dict(device=lock_info.st_dev, inode=lock_info.st_ino))),
                        (r, 'admit', admission), (r, 'stage_reuse', stage),
                        (r, 'inspect_owned', inspect), (r, 'verify_limits', lambda value: None),
                        (r.Controller, 'run', run), (r.Controller, 'sample', sample),
                        (r.g, 'LOCK', lock), (r.os, 'getsid', lambda pid: os.getpid()),
                        (r.subprocess, 'check_output', lambda argv, **kwargs: 'a'*40+'\n' if 'rev-parse' in argv else '')]:
                        stack.enter_context(patch.object(target, name, value))
                    result = r.main()
                receipt = json.loads((output/'evidence/receipt.json').read_text())
                self.assertEqual(result, 1 if incomplete else 0)
                self.assertEqual(receipt['result'], 'FAIL' if incomplete else 'PASS_FUNDED_TWO_PEER_JOURNEY_ONLY')
                self.assertEqual(events, ['admit', 'stage', 'image', 'admit', 'create', 'start', 'rm'])
                self.assertEqual(receipt['rows']['resources.json']['deadlines']['wall_seconds'], 15000)
                self.assertEqual(receipt['rows']['resources.json']['deadlines']['runtime_seconds'], 14700)
                self.assertEqual((output/'staging').exists(), incomplete)
                self.assertEqual(set(p.name for p in (output/'evidence').iterdir()), set(f.REQUIRED)|{'receipt.json'})
                self.assertFalse(receipt['launch_ready'])
                self.assertFalse(receipt['public_launch'])
                self.assertNotIn('PRIVATE_', json.dumps(receipt))

    def test_funded_main_requires_detached_reuse_before_api_or_lock(self):
        argv = ['run-profile.py', '--grant-comment', 'unused', '--artifact-sha256', 'unused',
                '--out', '/unused', '--workload', f.WORKLOAD]
        for reuse in ([], ['--reuse-build', f.RETAINED_ROOT]):
            with patch.object(sys, 'argv', argv+reuse), patch.object(r.os, 'getsid', return_value=os.getpid()+1), \
                    patch.object(r, 'api') as api, patch.object(r, 'acquire_lock') as acquire:
                with self.assertRaisesRegex(ValueError, 'detached session'): r.main()
                api.assert_not_called()
                acquire.assert_not_called()


if __name__ == '__main__':
    unittest.main()
