"""TJS-4238 operator-package source checks; native effects are explicitly substituted.

The three-role journey runs the real seed, client and monitor drivers concurrently
against a chain/transport model (the milestone-3 model, extended): the longest chain
wins on every connection, a SIGKILL leaves the seed root unsealed, a newcomer far
behind logs one `Synced` line per 100-block batch, and the manager's real relay
carries the pin and the operator status to the monitor. The seal, attestation,
backup copy and retention run on real files. The outside monitor and the host-reach
probe run against real local sockets.
"""
import contextlib
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import types
import unittest
from unittest import mock

import profile_contract as c
from integration import exposure_contract as x
from integration import exposure_driver as ed
from integration import host_reach as hr
from integration import operator_contract as o
from integration import operator_driver as od
from integration import outside_monitor as om
from integration import test_exposure as te
from integration import topology_contract as t
from integration import topology_driver as td
from integration.test_topology import Manager as TopologyManager

import importlib.util
spec = importlib.util.spec_from_file_location('operator_manager_tests', c.HERE/'run-operator.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
d = od.d
ADDRESS = '9'*95


def owner(**state):
    value = types.SimpleNamespace(state=dict(address=ADDRESS, **state),
                                  plan=o.plan(o.SEED_IP, in_peers=16, max_connections_per_ip=4))
    return value


def argv(name='S', **kwargs):
    return od.Operator.daemon_argv(owner(), name, Path('/r'), **kwargs)


def public(mining=True):
    return argv('S', mining=mining)


def swap(base, option, value):
    out = list(base)
    out[out.index(option)+1] = value
    return out


class PublicSeedShape(unittest.TestCase):
    """Item 1 (Core note 5, Security note 2)."""
    def test_driver_public_seed_argv_passes_and_m3_shape_cannot_express_it(self):
        plan = o.plan(o.SEED_IP)
        names = o.check_public_seed(public(), plan, mining=True)
        flags = [n for n, _ in names]
        for absent in ('--allow-local-ip', '--hide-my-port', '--add-exclusive-node'):
            self.assertNotIn(absent, flags)
        values = dict(names)
        self.assertEqual((values['--in-peers'], values['--out-peers'], values['--max-connections-per-ip']),
                         ('16', '0', '4'))
        with self.assertRaises(t.PolicyRefusal):  # The milestone-3 seed shape refuses the public shape.
            x.check_exposed('seed', public(), mining=True)
        private = o.plan('192.0.2.10', rpc='private')
        argv_private = swap(swap(swap(public(), '--p2p-bind-ip', '192.0.2.10'), '--rpc-bind-ip', '127.0.0.1'),
                            '--rpc-ssl', 'disabled')
        argv_private.remove('--confirm-external-bind')
        o.check_public_seed(argv_private, private, mining=True)

    def test_every_milestone_3_adverse_argv_and_each_new_bound_refuses(self):
        base, plan = public(), o.plan(o.SEED_IP)
        cases = {
            # Milestone-3 adverse argv (exposure_driver.argv_controls), on the public base.
            'rpc wildcard': swap(base, '--rpc-bind-ip', '0.0.0.0'), 'p2p wildcard': swap(base, '--p2p-bind-ip', '0.0.0.0'),
            'ipv6 wildcard': swap(base, '--p2p-bind-ipv6-address', '::'),
            'foreign exclusive': base+['--add-exclusive-node', '10.0.0.1:18080'],
            'unrestricted': [a for a in base if a != '--restricted-rpc'], 'public node': base+['--public-node'],
            'prefix': base+['--public-nod'], 'login argv': base+['--rpc-login', 'a:b'],
            'seed node': base+['--seed-node', o.SEED], 'no login': base+['--disable-rpc-login'],
            'restricted port': base+['--rpc-restricted-bind-port', '48089'], 'add peer': base+['--add-peer', o.SEED],
            'any cert': base+['--rpc-ssl-allow-any-cert'], 'exclusive seed': base+['--add-exclusive-node', o.SEED],
            'plaintext rpc': swap(base, '--rpc-ssl', 'disabled'), 'tls autodetect': swap(base, '--rpc-ssl', 'autodetect'),
            'rpc other ip': swap(base, '--rpc-bind-ip', o.CLIENT_IP), 'gateway bind': swap(base, '--p2p-bind-ip', o.GATEWAY),
            'no external confirm': [a for a in base if a != '--confirm-external-bind'],
            # New public-shape bounds.
            'allow local': base+['--allow-local-ip'], 'hide port': base+['--hide-my-port'],
            'loopback p2p': swap(base, '--p2p-bind-ip', '127.0.0.1'), 'priority': base+['--add-priority-node', o.SEED],
            'out peers': swap(base, '--out-peers', '8'), 'out default': swap(base, '--out-peers', '-1'),
            'in unlimited': swap(base, '--in-peers', '-1'), 'in high': swap(base, '--in-peers', '65'),
            'in differs': swap(base, '--in-peers', '8'), 'per ip high': swap(base, '--max-connections-per-ip', '9'),
            'per ip differs': swap(base, '--max-connections-per-ip', '2'), 'ban list': base+['--ban-list', '/x'],
            'offline': base+['--offline'], 'two threads': swap(base, '--mining-threads', '2'),
            'no in peers': [a for i, a in enumerate(base) if a != '--in-peers' and base[i-1] != '--in-peers'],
            'no out peers': [a for i, a in enumerate(base) if a != '--out-peers' and base[i-1] != '--out-peers'],
            'no per ip': [a for i, a in enumerate(base)
                          if a != '--max-connections-per-ip' and base[i-1] != '--max-connections-per-ip'],
            'ipv6 rpc': base+['--rpc-bind-ipv6-address', '::1'], 'use ipv6': base+['--p2p-use-ipv6'],
            'zmq': base+['--zmq-pub', 'tcp://127.0.0.1:1'], 'proxy': base+['--proxy', '127.0.0.1:9050'],
            'igd': base+['--igd', 'enabled'], 'wrong port': swap(base, '--p2p-bind-port', '48180'),
            'positional': base+['extra'], 'repeat': base+['--data-dir', '/other'], 'stagenet': base+['--stagenet'],
            'not mining': [a for a in base if a not in ('--start-mining', ADDRESS, '--mining-threads', '1')],
            'wallet': ['/bin/monero-wallet-rpc']+base[1:],
        }
        for label, value in cases.items():
            with self.subTest(label=label), self.assertRaises(t.PolicyRefusal):
                o.check_public_seed(value, plan, mining=label != 'not mining')
        with self.assertRaises(t.PolicyRefusal):
            o.check_public_seed([a for a in base if a not in ('--start-mining', ADDRESS, '--mining-threads', '1')],
                                plan, mining=True)

    def test_plan_bounds_and_owned_objects_refuse(self):
        good = o.plan(o.SEED_IP)
        self.assertEqual(o.check_plan(good), good)
        bad = [dict(good, out_peers=1), dict(good, in_peers=0), dict(good, in_peers=65),
               dict(good, max_connections_per_ip=5), dict(good, rpc='public'), dict(good, rpc='login-less'),
               dict(good, connection_rate=dict(good['connection_rate'], new_per_minute=0)),
               dict(good, connection_rate=dict(good['connection_rate'], new_per_minute=121)),
               dict(good, connection_rate=dict(good['connection_rate'], burst=0)),
               dict(good, connection_rate=dict(good['connection_rate'], owner='none')),
               dict(good, connection_rate=None), {k: v for k, v in good.items() if k != 'connection_rate'},
               dict(good, objects=dict(good['objects'], **{'port-rule': dict(created=True)})),
               dict(good, objects={'port-rule': dict(created=False)}), dict(good, p2p_port=18080),
               dict(good, extra=1), dict(good, schema='x')]
        for address in ('0.0.0.0', '127.0.0.1', '169.254.1.1', '224.0.0.1', '::', '::1', '240.0.0.1', 'host', 1):
            bad.append(dict(good, bind_ip=address))
        for value in bad:
            with self.subTest(value=value), self.assertRaises(t.PolicyRefusal):
                o.check_plan(value)
        for value in bad[:4]:  # The argv check refuses through the plan too.
            with self.assertRaises(t.PolicyRefusal):
                o.check_public_seed(public(), value, mining=True)

    def test_upstream_seed_dial_and_rate_facts_are_bound_in_the_shape(self):
        self.assertEqual(o.OUT_PEERS, 0)                               # No third-party seed dial.
        self.assertNotIn('--limit-rate', o.PUBLIC_ALLOWED)            # Rate is the port rule's job.
        self.assertEqual(o.OBJECT_CLASSES['port-rule']['removal'], ['nft', 'delete', 'table', 'inet', 'meownero_seed'])
        self.assertIn('limit rate over <rate>/minute', o.OBJECT_CLASSES['port-rule']['rule'])


class Absence(unittest.TestCase):
    """Item 3: an absence check never claims ABSENT without a vantage."""
    def test_fails_closed(self):
        def boom():
            raise OSError('no route')
        for probe, expected in ((lambda: True, 'PRESENT'), (lambda: False, 'ABSENT'), (lambda: None, 'UNVERIFIED'),
                                (boom, 'UNVERIFIED'), (lambda: 0, 'UNVERIFIED'), (lambda: 'absent', 'UNVERIFIED')):
            for kind in o.OBJECT_CLASSES:
                self.assertEqual(o.absence(kind, probe), expected)
        self.assertEqual(o.absence('port-rule', m.no_vantage), 'UNVERIFIED')
        with self.assertRaises(t.PolicyRefusal):
            o.absence('router', lambda: False)


class Contract(unittest.TestCase):
    def test_verdict_and_shapes(self):
        rows = {f: {k: {'status': 'PASS'} for k in keys} for f, keys in o.REQUIRED.items()}
        self.assertEqual(o.verdict(rows), 'PASS_OPERATOR_PACKAGE_DEV_HOST_ONLY')
        self.assertEqual(o.verdict(rows, o.REHEARSAL_UPTIME_SECONDS), 'FAIL')  # Depth row must stay NOT_RUN.
        rows['client.json']['newcomer_depth'] = {'status': 'NOT_RUN'}
        self.assertEqual(o.verdict(rows, o.REHEARSAL_UPTIME_SECONDS), 'REHEARSAL_PASS_NEWCOMER_DEPTH_NOT_RUN')
        self.assertEqual(o.verdict(rows), 'INCOMPLETE')
        rows['seed.json']['crash_recovery'] = {'status': 'FAIL'}
        self.assertEqual(o.verdict(rows, o.REHEARSAL_UPTIME_SECONDS), 'FAIL')
        shapes = o.shapes()
        self.assertEqual(set(shapes), {k for f, keys in o.REQUIRED.items() for k in keys
                                       if f not in ('resources.json', 'cleanup.json')})
        self.assertEqual(shapes['future_objects_fail_closed']['port_rule'], 'UNVERIFIED')
        self.assertFalse(shapes['outside_pin']['exchange_mounted'])


class Census(unittest.TestCase):
    ROUTES = ['lo\t0000007F\t00000000\t0001\t0\t0\t0\t000000FF\t0\t0\t0',
              'eth0\t004DE70A\t00000000\t0001\t0\t0\t0\tF8FFFFFF\t0\t0\t0']

    def test_seed_names_client_monitor_and_host_edges(self):
        sock = lambda lip, lport, rip, rport, state='01', kind='tcp': (kind, state, lip, lport, rip, rport)
        owned = [('S', sock(o.SEED_IP, 48080, '0.0.0.0', 0, '0A')), ('S', sock(o.SEED_IP, 48081, '0.0.0.0', 0, '0A')),
                 ('S', sock(o.SEED_IP, 48080, o.CLIENT_IP, 40000)), ('S', sock(o.SEED_IP, 48080, o.CLIENT_IP, 40001)),
                 ('S', sock(o.SEED_IP, 48080, o.MONITOR_IP, 40002)), ('S', sock(o.SEED_IP, 48081, o.MONITOR_IP, 40003)),
                 ('S', sock(o.SEED_IP, 48080, o.GATEWAY, 40004)), ('S', sock(o.SEED_IP, 48081, o.GATEWAY, 40005)),
                 ('S', sock(o.SEED_IP, 48081, o.SEED_IP, 40006))]
        self.assertEqual(od.classify('seed', owned, self.ROUTES), ({'client': 2, 'monitor': 1, 'host': 2}, 0))
        for extra in (sock(o.SEED_IP, 48081, o.CLIENT_IP, 1), sock(o.SEED_IP, 48080, '10.231.77.4', 1),
                      sock(o.SEED_IP, 40000, '1.2.3.4', 28080), sock('0.0.0.0', 48080, '0.0.0.0', 0, '0A'),
                      sock(o.SEED_IP, 1, '1.1.1.1', 53, '07', 'udp')):
            self.assertEqual(od.classify('seed', owned+[('S', extra)], self.ROUTES)[1], 1, extra)
        with self.assertRaises(ValueError):
            od.classify('seed', owned, self.ROUTES+['eth0\t00000000\t0177E70A\t0003\t0\t0\t0\t00000000\t0\t0\t0'])

    def test_client_and_monitor_edges(self):
        sock = lambda lip, lport, rip, rport: ('tcp', '01', lip, lport, rip, rport)
        self.assertEqual(od.classify('monitor', [('M', sock(o.MONITOR_IP, 51000, o.SEED_IP, 48080))], self.ROUTES),
                         ({'M': 1}, 0))
        self.assertEqual(od.classify('client', [('K', sock(o.CLIENT_IP, 51000, o.SEED_IP, 48080)),
                                                ('N', sock(o.CLIENT_IP, 51001, o.SEED_IP, 48080))], self.ROUTES),
                         ({'K': 1, 'N': 1}, 0))
        self.assertEqual(od.classify('monitor', [('M', sock(o.MONITOR_IP, 51000, o.SEED_IP, 48081))], self.ROUTES)[1], 1)


class OutsideMonitor(unittest.TestCase):
    """Item 4 reference implementation, against real files and a real local TLS listener."""
    def status(self, **change):
        value = dict(count=10, top='a'*64, inbound=dict(client=2, monitor=1), launch=5, step='serving', unix=1000)
        value.update(change)
        return value

    def test_pure_checks(self):
        self.assertTrue(om.check_pin('a'*64, 'a'*64))
        with self.assertRaises(om.Alert):
            om.check_pin('a'*64, 'b'*64)
        with self.assertRaises(om.Unverified):
            om.check_pin('short', 'short')
        self.assertEqual(om.check_status(self.status(), 1010, in_peers=16, max_age=180), (3, 10))
        with self.assertRaises(om.Alert):
            om.check_status(self.status(), 2000, in_peers=16, max_age=180)
        with self.assertRaises(om.Alert):
            om.check_status(self.status(inbound=dict(client=17)), 1000, in_peers=16, max_age=180)
        for bad in (dict(self.status(), extra=1), self.status(top='x'), self.status(count='10'), [1]):
            with self.assertRaises(om.Unverified):
                om.check_status(bad, 1000, in_peers=16, max_age=180)
        self.assertTrue(om.check_tip((10, 'a'*64), self.status(), max_spread=2))
        self.assertFalse(om.check_tip((9, 'b'*64), self.status(), max_spread=2))
        with self.assertRaises(om.Alert):
            om.check_tip((10, 'b'*64), self.status(), max_spread=2)
        with self.assertRaises(om.Alert):
            om.check_tip((5, 'b'*64), self.status(), max_spread=2)

    @unittest.skipUnless(shutil.which('openssl'), 'openssl CLI needed for a local certificate')
    def test_evaluate_reads_only_out_of_band_files_and_a_real_tls_pin(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            server = te.TLSServer(base)
            self.addCleanup(server.close)
            presented = om.presented_pin('127.0.0.1', server.port)
            self.assertEqual(presented, server.pin)
            self.assertEqual(server.requests, 0)  # The pin read writes no request byte.
            (base/'pin').write_text(server.pin+'\n')
            (base/'status.json').write_text(json.dumps(self.status(unix=int(time.time()))))
            run = lambda **k: om.evaluate(seed_host='127.0.0.1', pin_file=base/'pin', status_file=base/'status.json',
                follower=lambda: (10, 'a'*64), in_peers=16, pin_of=lambda host: om.presented_pin(host, server.port), **k)
            self.assertEqual(run()['state'], 'OK')
            (base/'pin').write_text(hashlib.sha256(b'x').hexdigest())
            self.assertEqual(run()['state'], 'ALERT')
            (base/'pin').unlink()
            self.assertEqual(run()['state'], 'UNVERIFIED')
            (base/'pin').write_text(server.pin)
            (base/'status.json').write_text('{')
            self.assertEqual(run()['state'], 'UNVERIFIED')
            self.assertEqual(server.requests, 0)
            # A seed that does not answer is an alert, not a pass.
            self.assertEqual(om.evaluate(seed_host='127.0.0.1', pin_file=base/'pin', status_file=base/'status.json',
                                         follower=lambda: (1, 'a'*64), in_peers=16,
                                         pin_of=lambda host: om.presented_pin(host, 9))['state'], 'ALERT')


class HostReach(unittest.TestCase):
    """Item 5: the probe is connect-only and reports each outcome."""
    def test_connected_and_refused(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen(1)
            port = listener.getsockname()[1]
            self.assertEqual(hr.probe('127.0.0.1', port, timeout=2), 'connected')
            peer, _ = listener.accept()
            with peer:
                peer.settimeout(1)
                self.assertEqual(peer.recv(16), b'')  # No byte was sent.
        with socket.socket() as closed:
            closed.bind(('127.0.0.1', 0))
            port = closed.getsockname()[1]
        self.assertEqual(hr.probe('127.0.0.1', port, timeout=2), 'refused')
        self.assertIn(hr.probe('192.0.2.1', 9, timeout=.2), ('unreachable', 'timeout'))


# ---- three-role journey ------------------------------------------------------------------
class OpClock(te.Clock):
    def sleep(self, seconds):
        super().sleep(seconds)
        net = self.net
        role = getattr(net.local, 'role', None)
        with net.lock:
            stop = net.rollback and role and role not in net.stopped
            if stop:
                net.stopped.add(role)
        if stop:
            raise td.Stop('termination')


class OpNet(te.Net):
    """The milestone-3 model with the monitor follower, crashes, longest-chain sync and the relay."""
    def __init__(self, root, adverse=None):
        super().__init__(root, adverse)
        self.pid, self.relay_elapsed, self.rollback, self.stopped = 4_000_000, 0, False, set()
        self.local, self.ops, self.relays, self.pin_of = threading.local(), {}, 0, None

    def launch(self, name, argv, cwd, env=None, **kwargs):
        process = super().launch(name, argv, cwd, env, **kwargs)
        process.send_signal = lambda sig: self.kill(name)
        node = self.nodes.get(name)
        if name == 'nodeS' and node and node['exposed']:  # One seed pass that dials nobody (--out-peers 0).
            with (node['root']/'native.log').open('ab') as log:
                log.write(b'W Failed to connect to any of seed peers, '+o.SEED_PASS+b'\n')
                if self.adverse == 'dial':
                    log.write(o.DIAL_ATTEMPTED+b'176.9.0.187:28080\n')
        return process

    def kill(self, name):
        with self.lock:
            self.nodes.pop(name, None)  # Nothing is stored: the root stays as the crash left it.
            d.PROCS[name][0].returncode = -9

    def connected(self):
        return [n for n in ('nodeK', 'nodeN', 'nodeM') if n in self.nodes and self.seed_online()]

    def tick(self, seconds):
        with self.lock:
            self.elapsed += seconds
            while self.elapsed >= 90:
                self.elapsed -= 90
                seed = self.nodes.get('nodeS')
                if seed and seed['mining'] and seed['sync'] and self.adverse != 'stall':
                    self.block += 1
                    seed['chain'].append(f'{self.block:064x}')
            peers = self.connected()
            if peers:
                seed = self.nodes['nodeS']
                seed['sync'] = True
                group = [seed]+[self.nodes[n] for n in peers]
                longest = max(group, key=lambda n: len(n['chain']))['chain']
                for node in group:
                    gained = len(longest)-len(node['chain'])
                    if node['chain'] != longest:
                        if gained > 0:
                            with (node['root']/'native.log').open('a') as log:
                                for _ in range(math.ceil(gained/o.SYNC_BATCH)):
                                    log.write(f'Synced {len(longest)}/{len(longest)}\n')
                        node['chain'] = list(longest)
            self.relay_elapsed += seconds
            if self.relay_elapsed >= 30:
                self.relay_elapsed = 0
                m.relay(self.root)
                self.relays += 1
            if self.ops and all(op.step == 'serving' for op in self.ops.values()):
                self.rollback = True

    def census(self, op):
        with self.lock:
            op.census_samples += 1
            if op.role == 'seed':
                edges = {}
                clients = [n for n in self.connected() if n != 'nodeM']
                if clients:
                    edges['client'] = len(clients)
                if 'nodeM' in self.connected():
                    edges['monitor'] = 1
            else:
                edges = {n[4:]: 1 for n in self.connected() if n[4:] in o.NODES[op.role]}
            for key, value in edges.items():
                op.planned[key] = max(op.planned.get(key, 0), value)
            return edges, 0

    def presented(self, host, port=None, timeout=None):
        with self.lock:
            if not self.seed_online():
                raise ConnectionRefusedError(port)
            return self.pin


@contextlib.contextmanager
def substituted(net):
    clock = OpClock(net)
    patches = [
        mock.patch.object(d, 'BIN', net.root/'bin'), mock.patch.object(d, 'launch', net.launch),
        mock.patch.object(d, 'stop', net.stop), mock.patch.object(d, 'RPC', net.rpc),
        mock.patch.object(d, 'absent', lambda port: None), mock.patch.object(d, 'released', lambda root: None),
        mock.patch.object(d, 'wait', lambda check, seconds=30: check()),
        mock.patch.object(d, 'creation', lambda kind, binaries: dict(kind=kind, profile='p', overlay='o',
                                                                     binaries=binaries, stopped_saved=True)),
        mock.patch.object(d, 'identity', lambda pid: next(owned for p, owned in d.PROCS.values() if p.pid == pid)),
        mock.patch.object(d, 'DEADLINE', time.monotonic()+10**9),
        mock.patch.object(od, 'time', clock), mock.patch.object(ed, 'time', clock), mock.patch.object(td, 'time', clock),
        mock.patch.object(om, 'time', clock), mock.patch.object(od, 'pid_absent', lambda pid: True),
        mock.patch.object(od.signal, 'signal', lambda *a: None),
        mock.patch.object(ed, 'TLSRPC', net.tls()), mock.patch.object(ed, 'peer_pin', net.peer_pin),
        mock.patch.object(om, 'presented_pin', net.pin_of or net.presented),
        mock.patch.object(od.Operator, 'census', lambda self: net.census(self)),
        mock.patch.object(od.Operator, 'listeners', lambda self: {(o.SEED_IP, 48080), (o.SEED_IP, 48081)}),
        mock.patch.object(od.Operator, 'absent', lambda self, name: None),
        mock.patch.dict(d.PROCS, clear=True), mock.patch.dict(d.SAVED, clear=True)]
    mask = os.umask(0o077)
    for p in patches:
        p.start()
    try:
        yield clock
    finally:
        for p in reversed(patches):
            p.stop()
        os.umask(mask)


def prepare(base):
    for sub in ('bin', 'exchange', 'staging')+tuple(f'{r}-{k}' for r in o.ROLES for k in ('private', 'public')):
        (base/sub).mkdir(mode=0o700)
    for role in o.ROLES:
        (base/'staging'/('control-'+role)).mkdir(mode=0o700)
    for name in ('monerod', 'monero-wallet-cli', 'monero-wallet-rpc'):
        (base/'bin'/name).write_bytes(name.encode())
    return OpNet(base)


def journey(base, uptime, adverse=None, hooks=None, pin_of=None):
    """Run all three real roles concurrently; return (net, {role: operator}, {role: error})."""
    net = prepare(base)
    net.adverse, net.pin_of = adverse, pin_of
    roles, errors = {}, {}
    with substituted(net):
        for role in o.ROLES:
            roles[role] = od.Operator(role, base/(role+'-private'), base/(role+'-public'),
                                      control=base/'staging'/('control-'+role),
                                      exchange=base/('exchange' if role != 'monitor' else 'no-exchange'))
        net.ops = roles
        for hook in hooks or ():
            hook(net, roles)
        def run(role):
            net.local.role = role
            try:
                roles[role].run(uptime)
                roles[role].publish('complete')
            except BaseException as error:  # Mirrors main(): announce failure to the other roles.
                errors[role] = error
                with net.lock:
                    net.rollback = True  # A failure ends the attempt; the others are stopped.
                if role != 'monitor':
                    td.private_write(base/'exchange'/(role+'.json'),
                                     (json.dumps(dict(role=role, step='failed', unix=0))+'\n').encode())
                with contextlib.suppress(Exception):
                    roles[role].state['phase'] = 'failed'
                    roles[role].publish('failed')
        threads = [threading.Thread(target=run, args=(role,), daemon=True) for role in o.ROLES]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(300)
        assert not any(thread.is_alive() for thread in threads), 'journey hung'
    return net, roles, errors


def rows_from(base):
    rows = o.empty_rows()
    for role, files in o.DRIVER_FILES.items():
        for name in files:
            rows[name].update(m.r.read_public_rows(base/(role+'-public')/name, o.shapes(), o.REQUIRED))
    return rows


class Journey(unittest.TestCase):
    def run_journey(self, uptime, **kwargs):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        net, roles, errors = journey(base, uptime, **kwargs)
        return base, net, roles, errors

    def test_full_journey_passes_every_driver_row(self):
        base, net, roles, errors = self.run_journey(o.UPTIME_SECONDS)
        self.assertEqual(errors, {})
        rows = rows_from(base)
        for role, files in o.DRIVER_FILES.items():
            for file in files:
                for key, value in rows[file].items():
                    self.assertEqual(value['status'], 'PASS', (file, key))
        seed = rows['seed.json']
        self.assertEqual(seed['cold_backup_retention']['retained'], 2)
        self.assertEqual(sorted(p.name for p in (base/'seed-private/backups').iterdir()), ['0002', '0003'])
        self.assertTrue((base/'seed-private/quarantine/S-0001').is_dir())
        self.assertGreaterEqual(seed['crash_recovery']['lost_blocks'], o.LOST_BLOCKS)
        self.assertGreaterEqual(seed['crash_recovery']['recovered_count'], seed['crash_recovery']['crash_count'])
        newcomer = rows['client.json']['newcomer_depth']
        self.assertGreaterEqual(newcomer['join_count'], o.NEWCOMER_COUNT)
        self.assertGreaterEqual(newcomer['synced_log_lines'], 2)
        self.assertEqual(rows['client.json']['follows_restarts']['seed_launches_followed'], o.BACKUPS+2)
        self.assertEqual(rows['seed-isolation.json']['launcher_policy']['planned_edges'], dict(client=2, monitor=1))
        self.assertTrue(rows['monitor.json']['outside_pin']['wrong_pin_alarm'])
        self.assertGreater(net.relays, 0)
        # The seed sealed S on the rollback's SIGTERM; the host can attest it offline.
        self.assertTrue(m.attest_sealed(base/'seed-private/nodes/S'))
        for role in o.ROLES:
            self.assertEqual(roles[role].state['phase'], 'complete')
        # L3: no pin, login or raw tip reaches a public file.
        raw = b''.join(p.read_bytes() for r in o.ROLES for p in (base/(r+'-public')).iterdir())
        self.assertNotIn(net.pin.encode(), raw)
        self.assertNotIn(b'node:', raw)
        chain = json.loads((base/'seed-private/nodes/S/lmdb/data.mdb').read_text())
        self.assertGreater(len(chain), o.NEWCOMER_COUNT)
        self.assertFalse(any(tip.encode() in raw for tip in chain))

    def test_rehearsal_leaves_the_newcomer_depth_row_not_run(self):
        base, net, roles, errors = self.run_journey(o.REHEARSAL_UPTIME_SECONDS)
        self.assertEqual(errors, {})
        rows = rows_from(base)
        self.assertEqual(rows['client.json']['newcomer_depth']['status'], 'NOT_RUN')
        rest = [v['status'] for f in rows for k, v in rows[f].items()
                if f in sum(o.DRIVER_FILES.values(), ()) and (f, k) not in o.REHEARSAL_NOT_RUN]
        self.assertTrue(rest and all(s == 'PASS' for s in rest))

    def test_a_disabled_attestation_lets_the_crashed_root_through_and_fails(self):
        # Sabotage control: the crashed root must be refused by attest(); without it the supervisor stops.
        base, net, roles, errors = self.run_journey(
            o.REHEARSAL_UPTIME_SECONDS, hooks=[lambda net, roles: setattr(roles['seed'], 'attest', lambda root, seal: True)])
        self.assertIn('seed', errors)
        self.assertIn('crashed root attested', str(errors['seed']))
        self.assertEqual(rows_from(base)['seed.json']['crash_refused_root']['status'], 'NOT_RUN')

    def test_crash_refuses_reopen_quarantines_and_restores_the_newest_backup(self):
        base, net, roles, errors = self.run_journey(o.REHEARSAL_UPTIME_SECONDS)
        self.assertEqual(errors, {})
        seed = roles['seed']
        launches = [e for e in net.events if e[0] == 'launch' and e[1] == 'nodeS']
        # Private signer launch, first public launch, three planned restarts, one recovery: no
        # launch on the crashed or quarantined root.
        self.assertEqual(len(launches), 1+1+o.BACKUPS+1)
        quarantine = base/'seed-private/quarantine/S-0001'
        manifest = json.loads((quarantine/'creation.json').read_text())
        self.assertIs(manifest['stopped_saved'], False)  # The crash left it unsealed.
        with self.assertRaises(ValueError):
            seed.attest(quarantine, seed.state['seals']['S'])
        self.assertTrue(od.owner_only(base/'seed-private/quarantine'))
        self.assertEqual(seed.state['backups'][-1]['number'], o.BACKUPS)

    def test_a_disabled_retention_prune_is_detected(self):
        with mock.patch.object(od.shutil, 'rmtree', lambda path: None):
            base, net, roles, errors = self.run_journey(o.REHEARSAL_UPTIME_SECONDS)
        # Without pruning a third backup stays; the supervisor refuses instead of writing retained=2.
        self.assertEqual(len(list((base/'seed-private/backups').iterdir())), o.RETAIN+1)
        self.assertIn('backup retention', str(errors['seed']))
        self.assertEqual(rows_from(base)['seed.json']['cold_backup_retention']['status'], 'NOT_RUN')

    def test_wrong_out_of_band_pin_alarms_and_fails_the_monitor(self):
        wrong = lambda host, port=None, timeout=None: 'f'*64
        base, net, roles, errors = self.run_journey(o.REHEARSAL_UPTIME_SECONDS, pin_of=wrong)
        self.assertIn('monitor', errors)
        self.assertEqual(rows_from(base)['monitor.json']['outside_pin']['status'], 'NOT_RUN')

    def test_a_seed_log_showing_an_outbound_dial_fails_the_shape_row(self):
        base, net, roles, errors = self.run_journey(o.REHEARSAL_UPTIME_SECONDS, adverse='dial')
        self.assertIn('public seed dialled out', str(errors['seed']))
        self.assertEqual(rows_from(base)['seed.json']['public_seed_shape']['status'], 'NOT_RUN')

    def test_stalled_chain_fails_closed(self):
        base, net, roles, errors = self.run_journey(o.REHEARSAL_UPTIME_SECONDS, adverse='stall')
        self.assertTrue(errors)

    def test_stop_before_serving_fails_and_the_monitor_never_reads_the_exchange(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        net = prepare(base)
        with substituted(net):
            seed = od.Operator('seed', base/'seed-private', base/'seed-public', control=base/'staging/control-seed',
                               exchange=base/'exchange')
            with self.assertRaisesRegex(ValueError, 'stopped before serving'):
                seed.rolled_back()
            monitor = od.Operator('monitor', base/'monitor-private', base/'monitor-public',
                                  control=base/'staging/control-monitor', exchange=base/'exchange')
            with self.assertRaisesRegex(ValueError, 'never'):
                monitor.hear('seed')
            with self.assertRaisesRegex(ValueError, 'never mounts the exchange'):
                monitor.monitor(o.REHEARSAL_UPTIME_SECONDS)
            with self.assertRaisesRegex(ValueError, 'unplanned restart'):
                od.Operator('seed', base/'seed-private', base/'seed-public', control=base/'staging/control-seed')

    def test_adverse_argv_controls_refuse_before_any_launch(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        net = prepare(base)
        with substituted(net):
            for role in o.ROLES:
                op = od.Operator(role, base/(role+'-private'), base/(role+'-public'),
                                 control=base/'staging'/('control-'+role), exchange=base/'exchange')
                op.argv_controls()
                self.assertGreaterEqual(op.adverse_argv, 8)
            self.assertEqual(net.events, [])


# ---- manager ---------------------------------------------------------------------------
class OperatorManager(unittest.TestCase):
    def grant(self, out, **change):
        base = json.loads(TopologyManager().grant(out)['body'].split('\n', 1)[1].rsplit('\n', 1)[0])
        for key in ('verdict_label', 'uptime_seconds', 'wall_seconds', 'container_flags', 'listeners'):
            base.pop(key)
        base.update(schema='meownero-operator-grant/1', workload=o.WORKLOAD, container_flags=m.FLAGS,
                    network=m.NETWORK, listeners='internal-bridge-public-seed-shape-no-published-port',
                    launch_ready=False, firewall_or_dns_change=False, uid_creation=False,
                    uptime_seconds=o.REHEARSAL_UPTIME_SECONDS, wall_seconds=o.MODES[o.REHEARSAL_UPTIME_SECONDS],
                    verdict_label='rehearsal', main_chain_count_max=o.MAX_COUNT)
        base.update(change)
        return dict(issueId=o.ISSUE, authorAgentId=c.PLATFORM, authorUserId=None,
                    body='```meownero-operator-grant\n'+json.dumps(base)+'\n```')

    def parse(self, comment, out):
        return m.grant_payload(comment, commit='c'*40, inputs_hash='i'*64, artifact_hash='a'*64,
            runner_hash='r'*64, driver_hash='d'*64, output=out, now=2000, reuse=TopologyManager().reuse())

    def test_grant_binds_issue_network_and_no_activation(self):
        out = Path('/tmp/never-created-tjs4238')
        self.assertTrue(self.parse(self.grant(out), out)['authorized'])
        self.assertEqual(self.parse(self.grant(out, uptime_seconds=o.UPTIME_SECONDS, wall_seconds=o.MODES[o.UPTIME_SECONDS],
                                               verdict_label='full'), out)['verdict_label'], 'full')
        for change in (dict(network=dict(m.NETWORK, internal=False)), dict(network=dict(m.NETWORK, published_ports=1)),
                       dict(container_flags=m.FLAGS+['-p', '48080:48080']), dict(public_launch=True),
                       dict(launch_ready=True), dict(firewall_or_dns_change=True), dict(uid_creation=True),
                       dict(listeners='internal-bridge-no-published-port'), dict(verdict_label='full'),
                       dict(schema='meownero-exposure-grant/1')):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.parse(self.grant(out, **change), out)
        exposure = te.ExposureManager().grant(out)  # A milestone-3 grant never binds this runner.
        with self.assertRaises(ValueError):
            self.parse(dict(exposure, issueId=o.ISSUE), out)
        with self.assertRaises(ValueError):
            self.parse(dict(self.grant(out), issueId=x.ISSUE), out)

    def test_monitor_container_has_no_exchange_mount(self):
        root = Path('/tmp/r')
        for role in o.ROLES:
            argv = m.container_command(root, role, 'name', 'net', 'sha256:'+'1'*64)
            mounts = [argv[i+1] for i, a in enumerate(argv) if a == '-v']
            self.assertEqual(f'{root}/exchange:/out/exchange' in mounts, role != 'monitor')
            self.assertEqual(argv[argv.index('--ip')+1], o.ROLES[role])
            self.assertFalse({'-p', '--publish', '-P', '--publish-all', '--network=host'} & set(argv))
            self.assertEqual(argv[-1], '/out/harness/integration/operator-runtime.sh')

    def test_relay_copies_only_valid_operator_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for role in ('seed', 'monitor'):
                (root/'staging'/('control-'+role)).mkdir(parents=True, mode=0o700)
            m.relay(root)  # Nothing to relay yet.
            self.assertEqual(list((root/'staging/control-monitor').iterdir()), [])
            seed = root/'staging/control-seed'
            (seed/'pin').write_text('a'*64+'\n')
            (seed/'pin').chmod(0o600)
            (seed/'status.json').write_text(json.dumps(OutsideMonitor().status()))
            (seed/'status.json').chmod(0o600)
            m.relay(root)
            self.assertEqual((root/'staging/control-monitor/pin').read_text(), 'a'*64+'\n')
            self.assertEqual((root/'staging/control-monitor/pin').stat().st_mode & 0o777, 0o600)
            for name, raw in (('pin', 'not-a-pin'), ('status.json', '{"count": 1}')):
                (seed/name).write_text(raw)
                with self.assertRaises(ValueError):
                    m.relay(root)

    def test_standalone_rollback_stops_seed_first_seals_and_releases(self):
        # The runbook kill switch, with the attempt's manager gone.
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base/'journey').mkdir(mode=0o700)
            journey(base/'journey', o.REHEARSAL_UPTIME_SECONDS)
            out = base/'attempt'
            out.mkdir(mode=0o700)
            for role in o.ROLES:
                for sub in ('public/'+role, 'persistent/'+role, 'staging/control-'+role):
                    (out/sub).mkdir(parents=True, mode=0o700)
            image, grant = 'sha256:'+'1'*64, '12345678-0000-0000-0000-000000000000'
            docker = FakeDocker(out, image, {r: {} for r in o.ROLES}, base/'journey/seed-private/nodes/S')
            state = dict(schema='meownero-operator-manager/1', manager=[os.getpid(), 'not-this-start-time'],
                         names=m.names(grant), image=image)
            with mock.patch.object(m.rt.Manager, 'run', lambda control, argv, deadline, **k: docker.run(argv, deadline, **k)), \
                    mock.patch.object(te.m, 'LABEL', m.LABEL), mock.patch.object(te, 'x', o), \
                    mock.patch.object(m.hr, 'probe', lambda host, port, timeout=3.0, hold=0.0: 'unreachable'), \
                    mock.patch.object(m, 'route_absent', lambda: True):
                docker.run(m.network_command(state['names']['network']), 0)
                for role in o.ROLES:
                    docker.run(m.container_command(out, role, state['names'][role], state['names']['network'], image), 0)
                    info = docker.containers[role]
                    state.setdefault('ids', {})[role] = info['id']
                    docker.run(m.g.DOCKER+['start', info['id']], 0)
                m.rt.write_private(out/m.STATE, state)
                code = m.standalone_rollback(types.SimpleNamespace(out=out))
            self.assertEqual(code, 0)
            self.assertEqual(docker.order, ['seed', 'client', 'monitor'])
            saved = m.rt.read_private(out/m.STATE)['standalone_rollback']
            self.assertTrue(all(v['status'] == 'PASS' for v in saved['rows'].values()), saved)
            self.assertEqual(docker.containers, {})
            self.assertIsNone(docker.network)
            self.assertTrue((out/'release').exists())

    def test_standalone_rollback_refuses_while_the_manager_lives(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            m.rt.write_private(out/m.STATE, dict(schema='meownero-operator-manager/1',
                                                manager=m.rt.identity(os.getpid())))
            with self.assertRaisesRegex(ValueError, 'still alive'):
                m.standalone_rollback(types.SimpleNamespace(out=out))


class FakeDocker(te.FakeDocker):
    """Containers run until the rollback stops them; then each role writes its final outputs."""
    def __init__(self, out, image, outputs, sealed, fail=None, published=False, stuck=None):
        super().__init__(out, image, outputs, fail, published)
        self.sealed, self.stuck, self.order = sealed, stuck, []

    def serving(self, role):
        public = self.out/'public'/role
        beat = dict(role=role, phase='serving', count=50, samples=1, unix=1)
        (public/'heartbeat.json').write_text(json.dumps(beat))
        if role == 'seed':
            control = self.out/'staging/control-seed'
            td.private_write(control/'pin', ('a'*64+'\n').encode())  # 0600, as the seed writes it.
            td.private_write(control/'status.json', json.dumps(OutsideMonitor().status(unix=int(time.time()))).encode())

    def complete(self, role, info):
        super().complete(role, info)
        if role == 'seed' and self.sealed:
            (self.out/'persistent/seed/nodes').mkdir(mode=0o700)
            shutil.copytree(self.sealed, self.out/'persistent/seed/nodes/S')

    def run(self, argv, deadline, check=True, monitor=True, **kwargs):
        rest = [a.decode() if isinstance(a, bytes) else a for a in argv][self.offset:]
        if rest[:1] == ['inspect']:
            info = next((i for i in self.containers.values() if i['name'] == rest[1] or i['id'] == rest[1]), None)
            if info and info['state']['Running']:
                info['polls'] += 1
                if self.fail == info['role'] and info['polls'] >= 2:  # Exits before serving.
                    self.complete(info['role'], info)
                elif info['polls'] == 2:
                    self.serving(info['role'])
                return subprocess.CompletedProcess(argv, 0, json.dumps([self.value(info)]).encode(), b'')
        if rest[:1] == ['stop']:
            info = next(i for i in self.containers.values() if i['id'] == rest[-1])
            self.order.append(info['role'])
            if info['role'] != self.stuck:
                self.complete(info['role'], info)
            return subprocess.CompletedProcess(argv, 0, b'', b'')
        return super().run(argv, deadline, check, monitor, **kwargs)


class ManagerIntegration(unittest.TestCase):
    def drive(self, fail=None, published=False, stuck=None, reach='connected', listener='unreachable'):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        (base/'journey').mkdir(mode=0o700)
        net, roles, errors = journey(base/'journey', o.REHEARSAL_UPTIME_SECONDS)
        assert not errors, errors
        outputs = {role: {p.name: p.read_bytes() for p in (base/'journey'/(role+'-public')).iterdir()}
                   for role in o.ROLES}
        retained = base/'retained'
        (retained/'retained-build').mkdir(parents=True, mode=0o700)
        binaries = {}
        for name in m.r.BINARIES:
            path = retained/'retained-build'/name
            path.write_bytes(name.encode()*10)
            os.chmod(path, 0o700)
            binaries[name] = c.digest(path.read_bytes())
        parent = base/'runs'
        parent.mkdir(mode=0o700)
        out = parent/'attempt'
        image = 'sha256:'+'1'*64
        reuse = dict(root=retained, manifest_sha256=m.r.funded.RETAINED_SHA256, binaries=binaries)
        artifact = b'packet'
        grant = OperatorManager().grant(out, reuse_build_root=str(retained), candidate_commit='c'*40,
            runner_sha256=c.digest((c.HERE/'run-operator.py').read_bytes()),
            driver_sha256=c.digest((c.HERE/m.DRIVER).read_bytes()),
            inputs_sha256=c.digest((c.HERE/'integration/inputs.json').read_bytes()), artifact_sha256=c.digest(artifact),
            valid_from_unix=int(time.time())-60, valid_until_unix=int(time.time())+49*3600)
        grant.update(id='12345678-0000-0000-0000-000000000000')
        docker = FakeDocker(out, image, outputs, base/'journey/seed-private/nodes/S', fail, published, stuck)
        lock = dict(held=False)
        keeper = [999999, '1']
        def spawn(root, until):
            lock['held'] = True
            m.rt.write_private(root/'keeper.json', dict(pid=keeper, lock=dict(device=m.g.LOCK_ID[0],
                inode=m.g.LOCK_ID[1]), until=until))
            return types.SimpleNamespace(pid=keeper[0], poll=lambda: None)
        def alive(owned):
            if owned == keeper and (out/'release').exists():
                lock['held'] = False
            return owned == keeper and lock['held']
        probes = []
        def probe(host, port, timeout=3.0, hold=0.0):
            probes.append((host, port, hold))
            return reach if hold else listener
        inputs = json.loads((c.HERE/'integration/inputs.json').read_text())
        inputs['builder_image'] = image
        patches = [
            mock.patch.object(m.r, 'api', lambda path: json.dumps(grant).encode() if '/comments/' in path else artifact),
            mock.patch.object(m.r, 'check_inputs', lambda p: inputs),
            mock.patch.object(m.r, 'reuse_build', lambda root, manifest: reuse),
            mock.patch.object(m.r, 'admit', lambda image, root, grant: dict(load=[1, 1, 1])),
            mock.patch.object(m.r.funded, 'RETAINED_ROOT', str(retained)),
            mock.patch.object(m.rt, 'spawn_keeper', spawn), mock.patch.object(m.rt, 'alive', alive),
            mock.patch.object(m.rt, 'lock_held_elsewhere', lambda: lock['held']),
            mock.patch.object(m.rt, 'identity', lambda pid: keeper if pid == keeper[0] else [pid, 'x']),
            mock.patch.object(m.subprocess, 'check_output', lambda argv, **k: 'c'*40+'\n' if 'rev-parse' in argv else ''),
            mock.patch.object(m.os, 'getsid', lambda pid: os.getpid()),
            mock.patch.object(m.rt.Manager, 'run', lambda control, argv, deadline, **k: docker.run(argv, deadline, **k)),
            mock.patch.object(m.hr, 'probe', probe), mock.patch.object(m, 'route_absent', lambda: True),
            # The milestone-3 fake reads its own module's label and role list.
            mock.patch.object(te.m, 'LABEL', m.LABEL), mock.patch.object(te, 'x', o),
            mock.patch.object(m.time, 'sleep', lambda s: None)]
        for patch in patches:
            patch.start()
        try:
            args = types.SimpleNamespace(command='start', inputs=c.HERE/'integration/inputs.json',
                grant_comment=grant['id'], artifact_sha256=c.digest(artifact), reuse_build=retained, out=out)
            code = m.start(args)
        finally:
            for patch in reversed(patches):
                patch.stop()
        receipt = json.loads((out/'evidence/receipt.json').read_text())
        return code, out, docker, receipt, probes

    def test_rehearsal_relays_probes_rolls_back_in_order_and_cleans(self):
        code, out, docker, receipt, probes = self.drive()
        self.assertEqual((code, receipt['result']), (0, 'REHEARSAL_PASS_NEWCOMER_DEPTH_NOT_RUN'), receipt)
        rows = receipt['rows']
        self.assertEqual(docker.order, ['seed', 'client', 'monitor'])  # The seed is stopped first.
        for file in ('rollback.json', 'cleanup.json', 'host.json'):
            self.assertTrue(all(v['status'] == 'PASS' for v in rows[file].values()), (file, rows[file]))
        self.assertEqual(rows['host.json']['host_reach']['p2p'], 'connected')
        self.assertTrue(rows['host.json']['host_reach']['same_uid_boundary'])
        self.assertEqual(rows['rollback.json']['future_objects_fail_closed']['port_rule'], 'UNVERIFIED')
        self.assertGreater(rows['rollback.json']['rollback_timing']['seconds'], 0)
        self.assertEqual(receipt['rollback']['absence'], {'port-rule': 'UNVERIFIED', 'dns-record': 'UNVERIFIED'})
        self.assertIn((o.SEED_IP, o.P2P['S'], o.HOST_PROBE_HOLD), probes)
        self.assertGreaterEqual(rows['seed.json']['public_seed_shape']['seed_pass_lines'], 1)
        self.assertEqual(set(receipt['exclusions']), set(o.EXCLUDED))
        self.assertTrue(all(v['status'] == 'NOT_RUN' and v['reason'] for v in receipt['exclusions'].values()))
        self.assertIsNone(docker.network)
        self.assertEqual(docker.containers, {})
        self.assertFalse((out/'staging').exists() or (out/'exchange').exists())
        for path in (out/'evidence').iterdir():
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertNotIn(b'/home/', path.read_bytes())
            self.assertNotIn(b'a'*64, path.read_bytes())  # The relayed pin stays out of the evidence.

    def test_host_unreachable_is_recorded_not_failed(self):
        code, out, docker, receipt, probes = self.drive(reach='unreachable')
        self.assertEqual(code, 0)
        self.assertEqual(receipt['rows']['host.json']['host_reach']['p2p'], 'unreachable')
        self.assertFalse(receipt['rows']['host.json']['host_reach']['same_uid_boundary'])

    def test_a_listener_still_reachable_after_rollback_fails_closed(self):
        code, out, docker, receipt, probes = self.drive(listener='connected')
        self.assertEqual((code, receipt['result']), (1, 'FAIL'))
        self.assertEqual(receipt['rows']['rollback.json']['owned_objects_absent']['status'], 'FAIL')

    def test_an_unsealed_seed_root_fails_the_rollback(self):
        code, out, docker, receipt, probes = self.drive(stuck='seed')
        self.assertEqual(code, 1)
        self.assertEqual(receipt['rows']['rollback.json']['seed_sealed_on_stop']['status'], 'FAIL')

    def test_a_role_exit_before_rollback_fails_and_still_cleans(self):
        code, out, docker, receipt, probes = self.drive(fail='client')
        self.assertEqual((code, receipt['result']), (1, 'FAIL'))
        self.assertEqual(receipt['failure_class'], 'native_exit')
        self.assertTrue(all(v['status'] == 'PASS' for v in receipt['rows']['cleanup.json'].values()))
        self.assertIsNone(docker.network)

    def test_a_published_port_fails_closed_and_cleans(self):
        code, out, docker, receipt, probes = self.drive(published=True)
        self.assertEqual((code, receipt['result']), (1, 'FAIL'))
        self.assertIsNone(docker.network)
        self.assertEqual(docker.containers, {})


if __name__ == '__main__':
    unittest.main()
