"""TJS-3920 topology source checks; native effects are explicitly substituted.

The fixture models the upstream behaviours the driver depends on: --start-mining
begins only after a connection synchronizes (miner.cpp:493-498,
cryptonote_protocol_handler.inl:211,2689-2732), so an --offline daemon never
mines; --in-peers 0 refuses inbound peers (net_node.inl:319-323); the heavier
connected chain wins and the node that reorganizes keeps the old tip as an
alternative block. Chain state lives in each root's data.mdb so seals, cold
backups, corruption, restore and the container cycle use real files.
"""
import contextlib
import copy
import importlib.util
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest import mock

import profile_contract as c
from integration import topology_contract as t
from integration import topology_driver as driver

spec = importlib.util.spec_from_file_location('topology_manager_tests', c.HERE/'run-topology.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
d = driver.d
INPUTS = json.loads((c.HERE/'integration/inputs.json').read_text())


class Clock:
    def __init__(self, ledger):
        self.now, self.mono, self.ledger = 1_800_000_000.0, 1000.0, ledger

    def time(self):
        return self.now

    def monotonic(self):
        return self.mono

    def sleep(self, seconds):
        self.now += seconds
        self.mono += seconds
        self.ledger.tick(seconds)


class Ledger:
    """Three-node chain model behind the real driver's process/RPC calls."""
    def __init__(self, root, adverse=None):
        self.root, self.adverse = root, adverse
        self.nodes = {}
        self.pid = 200000
        self.events = []
        self.elapsed = 0.0
        self.block = 0

    # chain persistence --------------------------------------------------------
    def lmdb(self, root):
        return root/'testnet'/'lmdb'

    def load(self, root):
        path = self.lmdb(root)/'data.mdb'
        if not path.exists():
            return [c.GENESIS], set()
        value = json.loads(path.read_text())
        return value['chain'], set(value['alt'])

    def store(self, node):
        path = self.lmdb(node['root'])
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        (path/'data.mdb').write_text(json.dumps(dict(chain=node['chain'], alt=sorted(node['alt']))))
        (path/'lock.mdb').write_bytes(b'\0'*64)

    # processes ----------------------------------------------------------------
    def launch(self, name, argv, cwd, env=None, **kwargs):
        self.events.append(('launch', name, list(argv), dict(env or {})))
        self.pid += 1
        process = types.SimpleNamespace(pid=self.pid, returncode=None)
        process.poll = lambda: process.returncode
        def signal_(sig, process=process, name=name):
            process.returncode = -9
            self.nodes.pop(name, None)
        process.send_signal = signal_
        process.wait = lambda timeout=None: process.returncode
        d.PROCS[name] = (process, [process.pid, str(self.pid)])
        if name.startswith('node'):
            options = dict(t.options(argv))
            flags = [k for k, _ in t.options(argv)]
            peers = [v for k, v in t.options(argv) if k == '--add-exclusive-node']
            root = Path(options['--data-dir'])
            chain, alt = self.load(root)
            for log in ('console.log', 'native.log'):
                with (root/log).open('a') as stream:
                    stream.write('fixture\n')
            self.nodes[name] = dict(root=root, chain=chain, alt=alt, offline='--offline' in flags,
                mining='--start-mining' in flags, sync=False, process=process,
                peers=[int(x.split(':')[1]) for x in peers], in_peers=int(options.get('--in-peers', -1)),
                port=int(options['--p2p-bind-port']), rpc=int(options['--rpc-bind-port']))
            if self.nodes[name]['offline']:
                self.nodes[name]['sync'] = True  # m_synchronized(offline); miner never notified.
            self.store(self.nodes[name])
        elif name == 'miner-wallet':
            port = int(dict(t.options(argv))['--rpc-bind-port'])
            login = cwd/f'monero-wallet-rpc.{port}.login'
            login.write_text('fixture:PRIVATE_LOGIN')
            login.chmod(0o600)
        return process

    def stop(self, name, graceful=True):
        self.events.append(('stop', name, graceful))
        process, owned = d.PROCS[name]
        c.require(process.poll() is None, 'unexpected native exit')
        node = self.nodes.pop(name, None)
        if node:
            self.store(node)
        process.returncode = 0
        return owned

    def identity(self, pid):
        for process, owned in d.PROCS.values():
            if process.pid == pid:
                return owned
        raise FileNotFoundError(pid)

    # network model ------------------------------------------------------------
    def graph(self):
        online = {n: x for n, x in self.nodes.items() if not x['offline']}
        by_port = {x['port']: n for n, x in online.items()}
        edges = set()
        for name, node in online.items():
            for port in node['peers']:
                peer = by_port.get(port)
                if peer and peer != name and online[peer]['in_peers'] != 0:
                    edges.add(frozenset((name[4:], peer[4:])))
        return edges

    def tick(self, seconds):
        self.elapsed += seconds
        while self.elapsed >= 90:
            self.elapsed -= 90
            for name, node in sorted(self.nodes.items()):
                if node['mining'] and node['sync'] and not node['offline'] and self.adverse != 'stall':
                    self.block += 1
                    node['chain'].append(f'{self.block:064x}')
        self.gossip()

    def gossip(self):
        edges = self.graph()
        for edge in edges:
            for name in edge:
                self.nodes['node'+name]['sync'] = True
        changed = True
        while changed:
            changed = False
            for edge in edges:
                a, b = (self.nodes['node'+x] for x in sorted(edge))
                for src, dst in ((a, b), (b, a)):
                    if len(src['chain']) > len(dst['chain']):
                        common = 0
                        while common < len(dst['chain']) and dst['chain'][common] == src['chain'][common]:
                            common += 1
                        dst['alt'] |= set(dst['chain'][common:])
                        dst['chain'] = list(src['chain'])
                        changed = True

    def edges(self):
        return self.graph(), 0

    # RPC ----------------------------------------------------------------------
    def rpc(self, port, login):
        ledger = self
        class RPC:
            def __init__(self): self.port, self.login = port, login
            def healthy(self, wallet=False): return self.call('get_info')
            def auth_controls(self, wallet=False): ledger.events.append(('auth', port))
            def call(self, method, params=None, path='json_rpc', login='current', raw=False):
                return ledger.call(port, method, params or {}, raw)
        return RPC()

    def call(self, port, method, params, raw):
        self.events.append(('rpc', port, method))
        if port == t.WALLET_PORT:
            return dict(get_version={'version': 1}, create_wallet={}, close_wallet={},
                        get_address={'address': '9'*95}).get(method, {})
        node = next((x for x in self.nodes.values() if x['rpc'] == port), None)
        if node is None:
            raise ConnectionRefusedError(port)
        if method == 'get_info':
            tip = node['chain'][-1]
            if self.adverse == 'wrong_genesis' and len(node['chain']) == 1:
                tip = 'f'*64
            return dict(status='OK', height=len(node['chain']), top_block_hash=tip,
                        wide_cumulative_difficulty=hex(len(node['chain'])*1000))
        if method == 'get_block_header_by_hash':
            known = params['hash'] in node['chain'] or params['hash'] in node['alt']
            value = dict(result=dict(block_header=dict(orphan_status=params['hash'] in node['alt']))) if known \
                else dict(error=dict(code=-5, message='not found'))
            return (200, value) if raw else value
        raise AssertionError('unexpected RPC '+method)


@contextlib.contextmanager
def substituted(ledger, *, uptime=3000, sample=300):
    clock = Clock(ledger)
    patches = [
        mock.patch.object(d, 'PRIVATE', ledger.root/'private'),
        mock.patch.object(d, 'PUBLIC', ledger.root/'public'),
        mock.patch.object(d, 'BIN', ledger.root/'bin'),
        mock.patch.object(d, 'launch', ledger.launch),
        mock.patch.object(d, 'stop', ledger.stop),
        mock.patch.object(d, 'identity', ledger.identity),
        mock.patch.object(d, 'RPC', ledger.rpc),
        mock.patch.object(d, 'census', lambda: 4),
        mock.patch.object(d, 'absent', lambda port: None),
        mock.patch.object(d, 'released', lambda root: None),
        mock.patch.object(d, 'wait', lambda check, seconds=30: check()),
        mock.patch.object(d, 'creation', lambda kind, binaries: dict(kind=kind, profile='p', overlay='o',
                                                                     binaries=binaries, stopped_saved=True)),
        mock.patch.object(d, 'DEADLINE', time.monotonic()+10**9),
        mock.patch.object(driver, 'time', clock),
        mock.patch.object(driver.Topology, 'edges', lambda self: ledger.edges()),
        mock.patch.object(t, 'UPTIME_SECONDS', uptime),
        mock.patch.object(t, 'SAMPLE_SECONDS', sample),
        mock.patch.dict(d.PROCS, clear=True),
        mock.patch.dict(d.SAVED, clear=True),
    ]
    for p in patches:
        p.start()
    try:
        yield clock
    finally:
        for p in reversed(patches):
            p.stop()


def prepare(base):
    for sub in ('private', 'public', 'bin'):
        (base/sub).mkdir(mode=0o700)
    for name in ('monerod', 'monero-wallet-cli', 'monero-wallet-rpc'):
        (base/'bin'/name).write_bytes(name.encode())
    return Ledger(base)


class Driver(unittest.TestCase):
    def journey(self, base, adverse=None, steady_shape=False):
        ledger = prepare(base)
        ledger.adverse = adverse
        with substituted(ledger, uptime=t.UPTIME_SECONDS if steady_shape else 3000):
            first = driver.Topology()
            self.assertEqual(first.run(), 'cycle')
            first.publish('cycle')
            beat = json.loads((base/'public/heartbeat.json').read_text())
            self.assertEqual(beat['phase'], 'cycle')
            # Container stop/start: a new driver process with an empty process table.
            d.PROCS.clear()
            d.SAVED.clear()
            second = driver.Topology()
            self.assertEqual(second.state['generation'], 2)
            self.assertEqual(second.run(), 'complete')
            second.publish('complete')
        return ledger, second

    def test_connected_journey_passes_every_driver_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger, top = self.journey(Path(tmp), steady_shape=True)
            rows = top.state['rows']
            for file in t.DRIVER_FILES:
                for key, row in rows[file].items():
                    self.assertEqual(row['status'], 'PASS', file+'.'+key)
            self.assertEqual(rows['persistence.json']['full_cycle']['status'], 'PASS')
            shapes = t.shapes()
            for file in t.DRIVER_FILES+('persistence.json',):
                value = m.r.read_public_rows(Path(tmp)/'public'/file, shapes, t.REQUIRED)
                for key, row in value.items():
                    self.assertEqual(row['status'], 'PASS')
            # L2/L5/RandomX: every daemon launch is restricted, loopback, light mode.
            daemons = [e for e in ledger.events if e[0] == 'launch' and e[1].startswith('node')]
            self.assertGreater(len(daemons), 20)
            for _, _, argv, env in daemons:
                self.assertIn('--restricted-rpc', argv)
                self.assertEqual(env['MONERO_RANDOMX_UMASK'], '4')
                self.assertEqual(argv[argv.index('--rpc-bind-ip')+1], '127.0.0.1')
                self.assertNotIn('0.0.0.0', ' '.join(argv))
            logins = [env['RPC_LOGIN'] for *_, env in daemons]
            self.assertEqual(len(set(logins)), len(logins))  # Fresh login per launch.
            wallet = [e for e in ledger.events if e[0] == 'launch' and e[1] == 'miner-wallet']
            self.assertEqual(len(wallet), 1)
            self.assertNotIn('--password-file', wallet[0][2])
            self.assertNotIn('RPC_LOGIN', wallet[0][3])
            self.assertFalse((Path(tmp)/'private/wallets/miner-cli.conf').exists())
            for _, _, argv, env in daemons:
                self.assertNotIn(env['RPC_LOGIN'], ' '.join(argv))  # Login never in argv.
            # L3: no raw tip in public rows or state rows; only salted digests.
            public = ''.join((Path(tmp)/'public'/f).read_text() for f in t.DRIVER_FILES)
            for node in ('A', 'B', 'C'):
                chain = json.loads((Path(tmp)/'private/nodes'/node/'testnet/lmdb/data.mdb').read_text())['chain']
                for block in chain:
                    self.assertNotIn(block, public)
            # Backups are never opened by a writer; the lost root is quarantined, not erased.
            self.assertTrue((Path(tmp)/'private/quarantine/A-lost-1').is_dir())
            self.assertTrue((Path(tmp)/'private/backups/A-1/creation.json').exists())
            self.assertFalse(any(str(Path(tmp)/'private/backups') in ' '.join(e[2]) for e in daemons))
            reorg = rows['reorg.json']['partition_reorg']
            self.assertGreaterEqual(reorg['depth'], 2)
            self.assertFalse((Path(tmp)/'private/adverse').exists())
            mode = stat.S_IMODE((Path(tmp)/'private/salt').stat().st_mode)
            self.assertEqual(mode, 0o600)

    def test_offline_mining_never_produces_blocks(self):
        # Known-bad design control: an isolated --offline --start-mining side stalls.
        with tempfile.TemporaryDirectory() as tmp:
            ledger = prepare(Path(tmp))
            with substituted(ledger):
                top = driver.Topology()
                (top.private/'nodes').mkdir(mode=0o700)
                top.state['address'] = '9'*95
                with self.assertRaises(t.PolicyRefusal):
                    t.check_argv('monerod', top.daemon_argv('A', top.root('A'), peers=('B',), offline=True))
                argv = top.daemon_argv('A', top.root('A'), peers=(), mining=True, offline=True)
                t.check_argv('monerod', argv, mining=True, offline=True)
                (top.root('A')).mkdir(mode=0o700)
                ledger.launch('nodeA', argv, top.root('A'), {})
                for _ in range(20):
                    driver.time.sleep(90)
                self.assertEqual(len(ledger.nodes['nodeA']['chain']), 1)

    def test_unplanned_restart_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = prepare(Path(tmp))
            with substituted(ledger):
                top = driver.Topology()
                top.state['phase'] = 'rows'
                top.save()
                again = driver.Topology()
                with self.assertRaisesRegex(ValueError, 'unplanned restart'):
                    again.run()

    def test_state_binary_binding_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = prepare(Path(tmp))
            with substituted(ledger):
                driver.Topology()
                (Path(tmp)/'bin/monerod').write_bytes(b'other')
                with self.assertRaisesRegex(ValueError, 'binary binding'):
                    driver.Topology()

    def test_adverse_argv_refused_before_any_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = prepare(Path(tmp))
            with substituted(ledger):
                top = driver.Topology()
                (top.private/'nodes').mkdir(mode=0o700)
                original = top.daemon_argv
                for mutate in (lambda a: a+['--rpc-bind-ip', '0.0.0.0'],
                               lambda a: [x for x in a if x != '--restricted-rpc'],
                               lambda a: a+['--confirm-external-bind'],
                               lambda a: a+['--p2p-bind-ip=10.1.1.1']):
                    with mock.patch.object(top, 'daemon_argv', lambda *x, **k: mutate(original(*x, **k))):
                        with self.assertRaises(t.PolicyRefusal):
                            top.start('B', fresh=not top.root('B').exists())
                self.assertFalse([e for e in ledger.events if e[0] == 'launch'])

    def test_corrupt_backup_or_crashed_root_never_starts(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = prepare(Path(tmp))
            with substituted(ledger):
                top = driver.Topology()
                (top.private/'nodes').mkdir(mode=0o700)
                top.state['address'] = '9'*95
                top.start('A', fresh=True)
                top.start('B', fresh=True)
                top.stop('A')
                backup = top.private/'backups'
                backup.mkdir(mode=0o700)
                d.copy_stopped(top.root('A'), backup/'A-1')
                launches = len([e for e in ledger.events if e[0] == 'launch'])
                top.backup_controls(backup/'A-1')
                self.assertEqual(len([e for e in ledger.events if e[0] == 'launch']), launches)
                row = top.state['rows']['backup.json']['corrupt_incomplete_refusal']
                self.assertEqual(row['refused'], row['cases'])
                # Crashed writer: SIGKILL leaves the root unsealed; the last seal refuses it.
                top.start('A')
                top.lose('A')
                with self.assertRaises(ValueError):
                    c.root_manifest(top.root('A'), top.state['last_sealed'][str(top.root('A'))])
                with self.assertRaises(KeyError):
                    top.start('A')

    def test_backup_controls_detect_a_disabled_check(self):
        # Known-bad control: a launcher that skips the manifest would accept corruption.
        with tempfile.TemporaryDirectory() as tmp:
            ledger = prepare(Path(tmp))
            with substituted(ledger):
                top = driver.Topology()
                (top.private/'nodes').mkdir(mode=0o700)
                top.state['address'] = '9'*95
                top.start('A', fresh=True)
                top.stop('A')
                (top.private/'backups').mkdir(mode=0o700)
                d.copy_stopped(top.root('A'), top.private/'backups/A-1')
                with mock.patch.object(c, 'root_manifest', lambda root, expected: None):
                    with self.assertRaisesRegex(ValueError, 'backup refusal controls'):
                        top.backup_controls(top.private/'backups/A-1')

    def test_steady_node_exit_and_stalled_chain_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = prepare(Path(tmp))
            with substituted(ledger):
                top = driver.Topology()
                top.run()
                d.PROCS.clear(); d.SAVED.clear()
                top = driver.Topology()
                original = top.steady
                def crash():
                    d.PROCS['nodeC'][0].returncode = 1
                    ledger.nodes.pop('nodeC')
                    return original()
                with mock.patch.object(top, 'steady', crash):
                    with self.assertRaises(ValueError):
                        top.run()
        with tempfile.TemporaryDirectory() as tmp:
            ledger = prepare(Path(tmp))
            with substituted(ledger):
                top = driver.Topology()
                top.run()
                d.PROCS.clear(); d.SAVED.clear()
                top = driver.Topology()
                ledger.adverse = 'stall'
                with self.assertRaisesRegex(ValueError, 'did not advance'):
                    top.run()

    def test_main_failure_stops_nodes_and_marks_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            ledger = prepare(Path(tmp))
            ledger.adverse = 'wrong_genesis'
            control = Path(tmp)/'control'
            control.mkdir()
            os.chmod(Path(tmp)/'private', 0o700)
            with substituted(ledger) as clock, mock.patch.object(driver, 'END_FILE', control/'end-unix'):
                (control/'end-unix').write_text(str(int(clock.time())+t.WALL_SECONDS))
                self.assertEqual(driver.main(), 1)
            state = json.loads((Path(tmp)/'private/topology-state.json').read_text())
            self.assertEqual(state['phase'], 'failed')
            self.assertFalse(ledger.nodes)
            self.assertTrue((Path(tmp)/'private/failure-class').exists())
            self.assertEqual(stat.S_IMODE((Path(tmp)/'private/failure-traceback').stat().st_mode), 0o600)


class Contract(unittest.TestCase):
    def test_salted_digest_is_private_salt_bound(self):
        a, b = os.urandom(32), os.urandom(32)
        value = 'ab'*32
        self.assertEqual(t.salted(a, value), t.salted(a, value))
        self.assertNotEqual(t.salted(a, value), t.salted(b, value))
        self.assertNotEqual(t.salted(a, value), c.digest(value.encode()))
        for bad in ((b'short', value), (a, 'xyz'), (a, value.upper())):
            with self.assertRaises(t.PolicyRefusal):
                t.salted(*bad)

    def test_wallet_policy_is_loopback_signer_only(self):
        good = ['/b/monero-wallet-rpc', '--testnet', '--config-file', '/c', '--daemon-address', '127.0.0.1:48081',
                '--wallet-dir', '/w', '--rpc-bind-ip', '127.0.0.1', '--rpc-bind-port', '48083', '--rpc-ssl', 'disabled']
        t.check_argv('monero-wallet-rpc', good, signer=True)
        for bad in (good+['--password-file', '/p'], good+['--restricted-rpc'], good+['--offline'],
                    good[:5]+['10.0.0.2:48081']+good[6:], good[:9]+['0.0.0.0']+good[10:],
                    [x for x in good if x not in ('--config-file', '/c')]):
            with self.assertRaises(t.PolicyRefusal):
                t.check_argv('monero-wallet-rpc', bad, signer=True)
        with self.assertRaises(t.PolicyRefusal):
            t.check_argv('monerod', good)

    def test_shapes_cover_required_rows_and_reject_raw_values(self):
        shapes = t.shapes()
        for file, keys in t.REQUIRED.items():
            if file in ('resources.json', 'cleanup.json', 'persistence.json'):
                continue
            for key in keys:
                self.assertIn(key, shapes)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'topology.json'
            row = dict(status='PASS', nodes=3, seeds=2, client_late_join_count=7, client_from_genesis=True,
                       edges=3, client_peers=2, foreign_connections=0, tip_salted='a'*64)
            for forged in (dict(row, tip_salted='not-hex'), dict(row, address='9'*95), dict(row, nodes='3'),
                           dict(row, edges=4)):
                path.write_text(json.dumps({'third_seed_client': forged}))
                os.chmod(path, 0o600)
                with self.assertRaises(m.r.PublicWitnessError):
                    m.r.read_public_rows(path, shapes, t.REQUIRED)
            path.write_text(json.dumps({'third_seed_client': row}))
            self.assertEqual(m.r.read_public_rows(path, shapes, t.REQUIRED)['third_seed_client']['status'], 'PASS')

    def test_verdict(self):
        rows = t.empty_rows()
        self.assertEqual(t.verdict(rows), 'INCOMPLETE')
        for file in rows:
            for key in rows[file]:
                rows[file][key] = dict(status='PASS')
        self.assertEqual(t.verdict(rows), 'PASS_PERSISTENT_ISOLATED_TOPOLOGY_ONLY')
        rows['uptime.json']['uptime_24h']['status'] = 'FAIL'
        self.assertEqual(t.verdict(rows), 'FAIL')


class Manager(unittest.TestCase):
    def reuse(self):
        return dict(root=Path(m.r.funded.RETAINED_ROOT), manifest_sha256=m.r.funded.RETAINED_SHA256)

    def grant(self, out, **change):
        value = dict(schema='meownero-topology-grant/1', authorized=True, workload=t.WORKLOAD,
            candidate_commit='c'*40, inputs_sha256='i'*64, artifact_sha256='a'*64, runner_sha256='r'*64,
            driver_sha256='d'*64, output_root=str(out), attempts=1, retry=False, wall_seconds=t.WALL_SECONDS,
            uptime_seconds=t.UPTIME_SECONDS, container_flags=m.r.CONTAINER_FLAGS, mode='runtime-only',
            reuse_build_root=m.r.funded.RETAINED_ROOT, retained_build_sha256=m.r.funded.RETAINED_SHA256,
            retained_build_authority_comment=m.r.funded.AUTHORITY_COMMENT, main_chain_count_max=t.MAX_COUNT,
            mining_threads=1, transactions=0, heavy_lock='keeper-held-for-wall', detached_session=True,
            no_other_heavy_lock_workload_scheduled=True, host_overhead_allowance=m.OVERHEAD,
            listeners='loopback-only-network-none', public_launch=False,
            load_rule=dict(metric='host-load-1-5-15', maximum=[9, 9, 9]),
            valid_from_unix=1000, valid_until_unix=1000+49*3600,
            artifact_attachment_id='12345678-1234-1234-1234-123456789abc')
        value.update(change)
        return dict(issueId=t.ISSUE, authorAgentId=c.PLATFORM, authorUserId=None,
                    body='```meownero-topology-grant\n'+json.dumps(value)+'\n```')

    def parse(self, comment, out, **kwargs):
        args = dict(commit='c'*40, inputs_hash='i'*64, artifact_hash='a'*64, runner_hash='r'*64,
                    driver_hash='d'*64, output=out, now=2000, reuse=self.reuse())
        args.update(kwargs)
        return m.grant_payload(comment, **args)

    def test_grant_binds_issue_platform_candidate_wall_and_lock(self):
        out = Path('/tmp/never-created-tjs3920')
        self.assertTrue(self.parse(self.grant(out), out)['authorized'])
        bad = [dict(public_launch=True), dict(wall_seconds=200000), dict(heavy_lock='none'), dict(mining_threads=2),
               dict(listeners='0.0.0.0'), dict(retry=True), dict(valid_until_unix=1000+24*3600),
               dict(container_flags=['--network=host']), dict(main_chain_count_max=10**6)]
        for change in bad:
            with self.assertRaises(ValueError):
                self.parse(self.grant(out, **change), out)
        wrong_issue = dict(self.grant(out), issueId=c.ISSUE)
        with self.assertRaises(ValueError):
            self.parse(wrong_issue, out)
        with self.assertRaises(ValueError):
            self.parse(dict(self.grant(out), authorAgentId='x'), out)
        with self.assertRaises(ValueError):
            self.parse(self.grant(out), out, driver_hash='e'*64)
        with self.assertRaises(ValueError):
            self.parse(self.grant(out), out, now=1000+48*3600)

    def test_keeper_holds_and_releases_a_substituted_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock = Path(tmp)/'heavy.lock'
            lock.touch(mode=0o600)
            info = lock.stat()
            out = Path(tmp)/'attempt'
            out.mkdir(mode=0o700)
            with mock.patch.object(m.g, 'LOCK', lock), mock.patch.object(m.g, 'LOCK_ID', (info.st_dev, info.st_ino)):
                self.assertFalse(m.lock_held_elsewhere())
                code = ('import sys,runpy;sys.argv=["run-topology.py","keep-lock","--out",%r,"--until","%d"];'
                        'import importlib.util as u;s=u.spec_from_file_location("k",%r);k=u.module_from_spec(s);'
                        's.loader.exec_module(k);k.g.LOCK=__import__("pathlib").Path(%r);k.g.LOCK_ID=(%d,%d);'
                        'raise SystemExit(k.main())') % (str(out), int(time.time())+60,
                        str(c.HERE/'run-topology.py'), str(lock), info.st_dev, info.st_ino)
                keeper = subprocess.Popen([sys.executable, '-B', '-c', code], cwd=str(c.HERE),
                                          start_new_session=True)
                try:
                    for _ in range(100):
                        if (out/'keeper.json').exists():
                            break
                        time.sleep(.1)
                    record = m.read_private(out/'keeper.json')
                    self.assertTrue(m.lock_held_elsewhere())
                    self.assertTrue(m.alive(record['pid']))
                    self.assertEqual(stat.S_IMODE((out/'keeper.json').stat().st_mode), 0o600)
                    (out/'release').touch()
                    keeper.wait(timeout=15)
                    self.assertFalse(m.lock_held_elsewhere())
                finally:
                    if keeper.poll() is None:
                        keeper.kill()
                        keeper.wait()

    def test_heartbeat_and_owner_only_refusals(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'public').mkdir()
            good = dict(phase='steady', generation=2, count=10, samples=3, unix=5)
            for value in (dict(good, phase='other'), dict(good, extra=1), dict(good, count='1')):
                path = root/'public/heartbeat.json'
                path.write_text(json.dumps(value))
                os.chmod(path, 0o600)
                with self.assertRaises(ValueError):
                    m.heartbeat(root)
            path.write_text(json.dumps(good))
            self.assertEqual(m.heartbeat(root)['samples'], 3)
            data = root/'persistent'
            data.mkdir(mode=0o700)
            (data/'x').write_text('x')
            os.chmod(data/'x', 0o600)
            self.assertTrue(m.owner_only(data))
            os.chmod(data/'x', 0o644)
            with self.assertRaises(ValueError):
                m.owner_only(data)

    def observe(self, tmp, states, beats):
        root = Path(tmp)
        state = dict(end_unix=time.time()+3600, keeper=[1, '1'], managers=[dict(identity=[2, '2'])],
                     rows=t.empty_rows(), receipt={})
        control = types.SimpleNamespace(sample=lambda force=False: None)
        args = types.SimpleNamespace(out=root)
        seq = iter(states)
        beat = iter(beats)
        finished = []
        with mock.patch.object(m, 'alive', lambda x: True), \
             mock.patch.object(m, 'lock_held_elsewhere', lambda: True), \
             mock.patch.object(m, 'inspect', lambda *a: next(seq)), \
             mock.patch.object(m, 'heartbeat', lambda root: next(beat)), \
             mock.patch.object(m, 'write_private', lambda *a: None), \
             mock.patch.object(m.time, 'sleep', lambda s: None), \
             mock.patch.object(m, 'finish', lambda *a: finished.append(a[-1]) or 7):
            code = m.observe(args, state, control, 'n', 'i')
        return code, state, finished

    def test_observe_plans_restart_cycle_and_failure(self):
        running = dict(State=dict(Running=True, StartedAt='s1', ExitCode=0))
        exited = lambda code: dict(State=dict(Running=False, FinishedAt='f1', ExitCode=code))
        with tempfile.TemporaryDirectory() as tmp:
            code, state, _ = self.observe(tmp, [running, running],
                [dict(phase='steady', samples=1), dict(phase='steady', samples=12)])
            self.assertEqual(code, m.RESTART)
            self.assertEqual(state['manager_restart']['container_started'], 's1')
            code, state, _ = self.observe(tmp, [exited(0)], [dict(phase='cycle', samples=0)])
            self.assertEqual(code, m.CYCLE)
            code, state, finished = self.observe(tmp, [exited(0)], [dict(phase='complete', samples=0)])
            self.assertEqual((code, finished), (7, [None]))
            code, state, finished = self.observe(tmp, [exited(1)], [dict(phase='failed', samples=0)])
            self.assertEqual(finished, ['native_exit'])
            code, state, finished = self.observe(tmp, [exited(0)], [dict(phase='steady', samples=0)])
            self.assertEqual(finished, ['native_exit'])

    def test_container_command_uses_accepted_flags_and_owner_mounts(self):
        root = Path('/tmp/x-tjs3920')
        argv = m.container_command(root, 'n', 'img')
        joined = ' '.join(argv)
        for flag in m.r.CONTAINER_FLAGS:
            self.assertIn(flag, argv)
        self.assertIn('--network=none', argv)
        self.assertNotIn('-p', argv)
        self.assertNotIn('--publish', joined)
        self.assertIn(str(root/'persistent')+':/out/private', argv)
        self.assertIn(str(root/'staging/build')+':/out/build:ro', argv)
        self.assertTrue(argv[-1].endswith('topology-runtime.sh'))

    def test_resume_refuses_live_previous_manager_or_changed_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            state = dict(commit='0'*40, runner_sha256='x', driver_sha256='y', end_unix=time.time()+100,
                         container_id='c'*64, name='n', image='i', managers=[dict(identity=[1, '1'])])
            m.write_private(out/m.STATE, state)
            args = types.SimpleNamespace(out=out)
            with mock.patch.object(m.os, 'getsid', lambda x: m.os.getpid()):
                with self.assertRaisesRegex(ValueError, 'exact granted candidate'):
                    m.resume(args)


if __name__ == '__main__':
    unittest.main()
