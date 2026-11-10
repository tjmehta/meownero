"""TJS-4177 exposure candidate source checks; native effects are explicitly substituted.

The two-role journey runs the real seed and client drivers concurrently against a
chain/transport model: the seed mines only after a client synchronizes, a seed
restart presents a new certificate, a --stagenet peer is logged as a wrong
network and never shares the testnet chain. The pinned TLS/Digest client is
exercised against a real local TLS server.
"""
import contextlib
import hashlib
import http.server
import json
import os
from pathlib import Path
import shutil
import socket
import socketserver
import ssl
import subprocess
import tempfile
import threading
import time
import types
import unittest
from unittest import mock

import profile_contract as c
from integration import exposure_contract as x
from integration import exposure_driver as driver
from integration import topology_contract as t
from integration import topology_driver as td
from integration.test_topology import Manager as TopologyManager

import importlib.util
spec = importlib.util.spec_from_file_location('exposure_manager_tests', c.HERE/'run-exposure.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
d = driver.d
ADDRESS = '9'*95


def owner(**state):
    return types.SimpleNamespace(state=dict(address=ADDRESS, **state))


def argv(name, **kwargs):
    return driver.Exposure.daemon_argv(owner(), name, Path('/r'), **kwargs)


class Contract(unittest.TestCase):
    def test_driver_shapes_pass_and_bind_exact_addresses(self):
        seed = argv('S', mining=True)
        x.check_exposed('seed', seed, mining=True)
        self.assertEqual(dict(t.options(seed))['--rpc-bind-ip'], x.SEED_IP)
        self.assertIn('--confirm-external-bind', seed)
        x.check_exposed('seed', argv('S'))
        for name in ('K', 'N'):
            x.check_exposed('client', argv(name))
        x.check_exposed('foreign', argv('F'))
        t.check_argv('monerod', argv('S', private=True), offline=True)  # Signer launch: milestone-2 shape.

    def test_adverse_exposure_argv_refused(self):
        seed = argv('S', mining=True)
        def swap(base, option, value):
            out = list(base)
            out[out.index(option)+1] = value
            return out
        bad_seed = [swap(seed, '--rpc-ssl', 'disabled'), swap(seed, '--rpc-bind-ip', '0.0.0.0'),
            swap(seed, '--rpc-bind-ip', x.CLIENT_IP), swap(seed, '--p2p-bind-ip', x.GATEWAY),
            swap(seed, '--p2p-bind-ipv6-address', '::'), swap(seed, '--add-exclusive-node', '10.0.0.1:18080'),
            [a for a in seed if a != '--confirm-external-bind'], [a for a in seed if a != '--restricted-rpc'],
            seed+['--public-node'], seed+['--public-nod'], seed+['--confirm-external-bin'],
            seed+['--rpc-login', 'a:b'], seed+['--rpc-ssl-allow-any-cert'], seed+['--offline'],
            seed+['--in-peers', '0'], swap(seed, '--mining-threads', '2'), seed+['--add-exclusive-node', x.SEED]]
        for case in bad_seed:
            with self.subTest(case=case[-2:]), self.assertRaises(t.PolicyRefusal):
                x.check_exposed('seed', case, mining=True)
        client = argv('K')
        bad_client = [swap(client, '--p2p-bind-ip', x.CLIENT_IP), swap(client, '--rpc-ssl', 'enabled'),
            swap(client, '--add-exclusive-node', x.SEED_EXCLUSIVE), client+['--confirm-external-bind'],
            client+['--start-mining', ADDRESS, '--mining-threads', '1'], swap(client, '--testnet', '--stagenet')]
        for case in bad_client:
            with self.subTest(case=case[-2:]), self.assertRaises(t.PolicyRefusal):
                x.check_exposed('client', case)
        with self.assertRaises(t.PolicyRefusal):
            x.check_exposed('foreign', client)  # --testnet is unknown to the foreign allowlist.
        with self.assertRaises(t.PolicyRefusal):
            x.check_exposed('client', argv('F'))
        # The milestone-2 shape still refuses the external-bind option and any off-loopback bind.
        with self.assertRaises(t.PolicyRefusal):
            t.check_argv('monerod', argv('S', private=True)+['--confirm-external-bind'], offline=True)
        with self.assertRaises(t.PolicyRefusal):
            t.check_argv('monerod', seed, mining=True)

    def test_verdict_and_shapes(self):
        rows = x.empty_rows()
        self.assertEqual(x.verdict(rows), 'INCOMPLETE')
        for file, keys in x.REQUIRED.items():
            for key in keys:
                rows[file][key] = dict(status='PASS')
        self.assertEqual(x.verdict(rows), 'PASS_EXPOSURE_CANDIDATE_DEV_HOST_ONLY')
        self.assertEqual(x.verdict(rows, x.REHEARSAL_UPTIME_SECONDS), 'FAIL')  # Rehearsal cannot claim steady.
        rows['client.json']['steady_exposed']['status'] = 'NOT_RUN'
        self.assertEqual(x.verdict(rows), 'INCOMPLETE')
        self.assertEqual(x.verdict(rows, x.REHEARSAL_UPTIME_SECONDS), 'REHEARSAL_PASS_STEADY_NOT_RUN')
        rows['host.json']['no_published_ports']['status'] = 'FAIL'
        self.assertEqual(x.verdict(rows, x.REHEARSAL_UPTIME_SECONDS), 'FAIL')
        shapes = x.shapes()
        self.assertEqual(set(shapes), {k for f in x.DRIVER_FILES.values() for name in f for k in x.REQUIRED[name]})
        tip = shapes['cold_bootstrap']['tip_salted']
        self.assertTrue(tip('a'*64))
        self.assertFalse(tip('A'*64))
        with self.assertRaises(t.PolicyRefusal):
            x.pin('A'*64)


ROUTES = ['lo\t0000007F\t00000000\t0001\t0\t0\t0\t000000FF\t0\t0\t0',
          'eth0\t004DE70A\t00000000\t0001\t0\t0\t0\tF8FFFFFF\t0\t0\t0']


class Census(unittest.TestCase):
    def test_decoders(self):
        self.assertEqual(driver.ipv4('0100007F'), '127.0.0.1')
        self.assertEqual(driver.ipv4('024DE70A'), x.SEED_IP)
        self.assertEqual(driver.ipv6('00000000000000000000000001000000'), '::1')

    def test_seed_rules(self):
        sock = lambda state, lip, lport, rip, rport, kind='tcp': (kind, state, lip, lport, rip, rport)
        owned = [('S', sock('0A', x.SEED_IP, 48080, '0.0.0.0', 0)), ('S', sock('0A', x.SEED_IP, 48081, '0.0.0.0', 0)),
                 ('S', sock('01', x.SEED_IP, 48080, x.CLIENT_IP, 40000)),
                 ('S', sock('01', x.SEED_IP, 48080, x.CLIENT_IP, 40001)),
                 ('S', sock('01', x.SEED_IP, 48081, x.SEED_IP, 50000)),
                 ('S', sock('02', x.SEED_IP, 41000, x.CLIENT_IP, 48280))]   # Refused dial, not established.
        self.assertEqual(driver.classify('seed', owned, ROUTES), ({'client': 2}, 0))
        foreign = owned+[('S', sock('01', x.SEED_IP, 48080, x.FOREIGN_IP, 40100))]
        self.assertEqual(driver.classify('seed', foreign, ROUTES), ({'client': 2, 'foreign': 1}, 0))
        for extra in (sock('0A', '0.0.0.0', 48080, '0.0.0.0', 0), sock('01', x.SEED_IP, 48080, '10.9.9.9', 1),
                      sock('01', x.SEED_IP, 41000, '1.1.1.1', 443), sock('07', '0.0.0.0', 5353, '0.0.0.0', 0, 'udp')):
            self.assertEqual(driver.classify('seed', owned+[('S', extra)], ROUTES)[1], 1)
        for routes in (ROUTES+['eth0\t00000000\t014DE70A\t0003\t0\t0\t0\t00000000\t0\t0\t0'],
                       ROUTES+['eth1\t0000A8C0\t00000000\t0001\t0\t0\t0\t00FFFFFF\t0\t0\t0']):
            with self.assertRaises(ValueError):
                driver.classify('seed', owned, routes)

    def test_client_rules(self):
        owned = [('K', ('tcp', '0A', '127.0.0.1', 48280, '0.0.0.0', 0)),
                 ('K', ('tcp', '01', x.CLIENT_IP, 39000, x.SEED_IP, 48080)),
                 ('N', ('tcp', '01', x.CLIENT_IP, 39001, x.SEED_IP, 48080)),
                 ('K', ('tcp', '01', '127.0.0.1', 48281, '127.0.0.1', 52000))]
        self.assertEqual(driver.classify('client', owned, ROUTES), ({'K': 1, 'N': 1}, 0))
        f = [('F', ('tcp', '01', x.FOREIGN_IP, 39500, x.SEED_IP, 48080)), ('F', ('tcp', '0A', '127.0.0.1', 48480, '0.0.0.0', 0))]
        self.assertEqual(driver.classify('foreign', f, ROUTES), ({'F': 1}, 0))
        self.assertEqual(driver.classify('client', f, ROUTES)[1], 2)      # Wrong namespace for F's sockets.
        for extra in (('tcp', '0A', x.CLIENT_IP, 48280, '0.0.0.0', 0),          # Client listening on the bridge.
                      ('tcp', '01', x.CLIENT_IP, 48280, x.SEED_IP, 41000),       # Seed-initiated connection.
                      ('tcp', '01', x.CLIENT_IP, 39002, x.SEED_IP, 48081)):      # Node talking to seed RPC.
            self.assertEqual(driver.classify('client', owned+[('K', extra)], ROUTES)[1], 1)


class TLSServer:
    """Local TLS listener with epee-like per-connection Digest auth."""
    def __init__(self, base, login='node:right'):
        self.requests = 0
        key, cert = base/'key.pem', base/'cert.pem'
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-subj', '/CN=x', '-days', '1',
                        '-keyout', str(key), '-out', str(cert)], check=True, capture_output=True)
        der = ssl.PEM_cert_to_DER_cert(cert.read_text())
        self.pin = hashlib.sha256(der).hexdigest()
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert, key)
        user, password = login.split(':', 1)
        server = self
        md5 = lambda v: hashlib.md5(v.encode()).hexdigest()

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'
            def log_message(self, *args):
                pass
            def do_POST(self):
                server.requests += 1
                self.rfile.read(int(self.headers['Content-Length']))
                nonce = getattr(self.connection, 'nonce', None)
                auth = self.headers.get('Authorization', '')
                if auth.startswith('Digest ') and nonce:
                    import urllib.request
                    f = urllib.request.parse_keqv_list(urllib.request.parse_http_list(auth[7:]))
                    expect = md5(':'.join([md5(f'{user}:x:{password}'), nonce, f['nc'], f['cnonce'], 'auth',
                                           md5('POST:'+f['uri'])]))
                    if f['username'] == user and f['response'] == expect:
                        return self.reply(200, b'{"result":{"status":"OK","height":1}}')
                self.connection.nonce = os.urandom(8).hex()
                self.reply(401, b'', {'WWW-Authenticate':
                                      f'Digest qop="auth",algorithm=MD5,realm="x",nonce="{self.connection.nonce}"'})
            def reply(self, code, body, headers={}):
                self.send_response(code)
                for k, v in dict(headers, **{'Content-Length': str(len(body))}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(body)

        class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
            daemon_threads = True
            def get_request(self):
                sock, address = self.socket.accept()
                try:
                    return context.wrap_socket(sock, server_side=True), address
                except (ssl.SSLError, OSError):
                    sock.close()
                    raise
            def handle_error(self, request, address):
                pass
        self.httpd = Server(('127.0.0.1', 0), Handler)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@unittest.skipUnless(shutil.which('openssl'), 'openssl CLI needed for a local certificate')
class PinnedClient(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.server = TLSServer(Path(self.tmp.name))
        self.patch = mock.patch.object(d, 'DEADLINE', time.monotonic()+600)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.server.close()
        self.tmp.cleanup()

    def test_pin_digest_and_refusals(self):
        port, pin = self.server.port, self.server.pin
        sock, presented = driver.peer_pin('127.0.0.1', port)
        sock.close()
        self.assertEqual(presented, pin)
        rpc = driver.TLSRPC('127.0.0.1', port, pin, 'node:right')
        self.assertEqual(rpc.call('get_info')['height'], 1)                   # Same-session Digest retry.
        self.assertEqual(rpc.call('get_info', login=None, raw=True)[0], 401)
        self.assertEqual(rpc.call('get_info', login='node:wrong', raw=True)[0], 401)
        self.assertTrue(rpc.auth_controls())
        before = self.server.requests
        with self.assertRaises(driver.PinMismatch):
            driver.TLSRPC('127.0.0.1', port, 'b'*64).call('get_info', login=None, raw=True)
        time.sleep(.2)
        self.assertEqual(self.server.requests, before)                        # No request byte on a mismatch.
        self.assertTrue(driver.plaintext_refused('127.0.0.1', port))
        with self.assertRaises(t.PolicyRefusal):
            driver.TLSRPC('127.0.0.1', port, 'not-a-pin')

    def test_plaintext_server_is_not_mistaken_for_refusal(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen(1)
            def answer():
                conn, _ = listener.accept()
                conn.recv(1024)
                conn.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n')
                conn.close()
            threading.Thread(target=answer, daemon=True).start()
            self.assertFalse(driver.plaintext_refused('127.0.0.1', listener.getsockname()[1]))


class Clock:
    def __init__(self, net):
        self.net, self.now, self.mono, self.lock = net, 1_800_000_000.0, 1000.0, threading.RLock()

    def time(self):
        return self.now

    def monotonic(self):
        return self.mono

    def sleep(self, seconds):
        # Advance in 2 s steps, yielding between them, so the other role keeps pace
        # (the real seed republishes its tip every 2 s).
        while seconds > 0:
            step = min(2, seconds)
            seconds -= step
            with self.lock:
                self.now += step
                self.mono += step
                self.net.tick(step)
            time.sleep(.0002)


class Net:
    """Seed/client chain and transport model behind the real drivers' native calls."""
    STAGENET = '5'*64

    def __init__(self, root, adverse=None):
        self.root, self.adverse = root, adverse
        self.nodes, self.events, self.lock = {}, [], threading.RLock()
        self.pid, self.block, self.elapsed, self.launch_count = 300000, 0, 0.0, 0
        self.pin, self.seed_login = None, None

    def lmdb(self, root):
        return root/'lmdb'

    def load(self, root):
        path = self.lmdb(root)/'data.mdb'
        return json.loads(path.read_text()) if path.exists() else [c.GENESIS]

    def store(self, node):
        self.lmdb(node['root']).mkdir(parents=True, exist_ok=True, mode=0o700)
        (self.lmdb(node['root'])/'data.mdb').write_text(json.dumps(node['chain']))

    def launch(self, name, argv, cwd, env=None, **kwargs):
        with self.lock:
            self.events.append(('launch', name, list(argv)))
            self.pid += 1
            process = types.SimpleNamespace(pid=self.pid, returncode=None)
            process.poll = lambda: process.returncode
            process.wait = lambda timeout=None: process.returncode
            d.PROCS[name] = (process, [process.pid, str(self.pid)])
            if name.startswith('node'):
                options = dict(t.options(argv))
                flags = [k for k, _ in t.options(argv)]
                root = Path(options['--data-dir'])
                stagenet = '--stagenet' in flags
                chain = [self.STAGENET] if stagenet else self.load(root)
                with (root/'native.log').open('a') as log:
                    log.write('fixture\n')
                node = dict(root=root, chain=chain, stagenet=stagenet, offline='--offline' in flags,
                            exposed=options['--rpc-ssl'] == 'enabled', mining='--start-mining' in flags,
                            sync=False, rpc=int(options['--rpc-bind-port']), login=env['RPC_LOGIN'])
                self.nodes[name] = node
                if name == 'nodeS' and node['exposed']:
                    self.launch_count += 1
                    self.pin = hashlib.sha256(f'launch-{self.launch_count}'.encode()).hexdigest()
                    self.seed_login = env['RPC_LOGIN']
                if stagenet and self.seed_online():
                    with (self.nodes['nodeS']['root']/'native.log').open('ab') as log:
                        log.write(driver.WRONG_NETWORK+b' id=foreign\n')
                if not stagenet:
                    self.store(node)
            elif name == 'miner-wallet':
                port = int(dict(t.options(argv))['--rpc-bind-port'])
                (cwd/f'monero-wallet-rpc.{port}.login').write_text('fixture:PRIVATE')
                (cwd/f'monero-wallet-rpc.{port}.login').chmod(0o600)
            return process

    def stop(self, name, graceful=True):
        with self.lock:
            process, owned = d.PROCS[name]
            c.require(process.poll() is None, 'unexpected native exit')
            node = self.nodes.pop(name, None)
            if node and not node['stagenet']:
                self.store(node)
            process.returncode = 0
            return owned

    def seed_online(self):
        node = self.nodes.get('nodeS')
        return node is not None and node['exposed']

    def connected(self):
        return [n for n in ('nodeK', 'nodeN') if n in self.nodes and self.seed_online()]

    def tick(self, seconds):
        with self.lock:
            self.elapsed += seconds
            while self.elapsed >= 90:
                self.elapsed -= 90
                seed = self.nodes.get('nodeS')
                if seed and seed['mining'] and seed['sync'] and self.adverse != 'stall':
                    self.block += 1
                    seed['chain'].append(f'{self.block:064x}')
            if self.connected():
                self.nodes['nodeS']['sync'] = True
                for name in self.connected():
                    self.nodes[name]['chain'] = list(self.nodes['nodeS']['chain'])

    def info(self, node):
        return dict(status='OK', height=len(node['chain']), top_block_hash=node['chain'][-1],
                    wide_cumulative_difficulty=hex(len(node['chain'])*1000))

    def rpc(self, port, login):
        net = self
        class RPC:
            def __init__(self):
                self.port, self.login = port, login
            def call(self, method, params=None, path='json_rpc', login='current', raw=False):
                with net.lock:
                    if port == x.WALLET_PORT:
                        return dict(get_version={'version': 1}, create_wallet={}, close_wallet={},
                                    get_address={'address': ADDRESS}).get(method, {})
                    node = next((n for n in net.nodes.values() if n['rpc'] == port and not n['exposed']), None)
                    if node is None:
                        raise ConnectionRefusedError(port)
                    if method == 'get_info':
                        return net.info(node)
                    raise AssertionError(method)
        return RPC()

    def tls(self):
        net = self
        class FakeTLS(driver.TLSRPC):
            def call(self, method, params=None, login='current', raw=False):
                with net.lock:
                    c.require(net.seed_online(), 'seed down')
                    if self.pin != net.pin:
                        raise driver.PinMismatch('certificate pin mismatch')
                    auth = self.login if login == 'current' else login
                    net.events.append(('tls', method, auth == net.seed_login))
                    if auth != net.seed_login:
                        c.require(raw, 'HTTP authentication/transport failure')
                        return 401, {}
                    node = net.nodes['nodeS']
                    if method == 'get_info':
                        value = net.info(node)
                    elif method == 'get_block_header_by_hash':
                        h = params['hash']
                        value = dict(result=dict(block_header=dict(orphan_status=False))) if h in node['chain'] \
                            else dict(error=dict(code=-5))
                        return (200, value) if raw else value
                    return (200, value) if raw else value
        return FakeTLS

    def peer_pin(self, host, port, timeout=5):
        with self.lock:
            if not self.seed_online():
                raise ConnectionRefusedError(port)
            return types.SimpleNamespace(close=lambda: None), self.pin

    def census(self, exposure):
        with self.lock:
            exposure.census_samples += 1
            if exposure.role == 'seed':
                return ({'client': len(self.connected())} if self.connected() else {}), 0
            if exposure.role == 'foreign':
                return ({'F': 1} if 'nodeF' in self.nodes and self.seed_online() else {}), 0
            return {n[4:]: 1 for n in self.connected()}, 0


@contextlib.contextmanager
def substituted(net, uptime):
    clock = Clock(net)
    (net.root/'exchange').mkdir(mode=0o700)
    (net.root/'uptime').write_text(str(uptime))
    patches = [
        mock.patch.object(d, 'BIN', net.root/'bin'), mock.patch.object(d, 'launch', net.launch),
        mock.patch.object(d, 'stop', net.stop), mock.patch.object(d, 'RPC', net.rpc),
        mock.patch.object(d, 'absent', lambda port: None), mock.patch.object(d, 'released', lambda root: None),
        mock.patch.object(d, 'wait', lambda check, seconds=30: check()),
        mock.patch.object(d, 'creation', lambda kind, binaries: dict(kind=kind, profile='p', overlay='o',
                                                                     binaries=binaries, stopped_saved=True)),
        mock.patch.object(d, 'DEADLINE', time.monotonic()+10**9),
        mock.patch.object(driver, 'time', clock), mock.patch.object(td, 'time', clock),
        mock.patch.object(driver, 'EXCHANGE', net.root/'exchange'),
        mock.patch.object(td, 'UPTIME_FILE', net.root/'uptime'),
        mock.patch.object(driver, 'TLSRPC', net.tls()), mock.patch.object(driver, 'peer_pin', net.peer_pin),
        mock.patch.object(driver, 'plaintext_refused', lambda host, port: net.seed_online()),
        mock.patch.object(driver.Exposure, 'census', lambda self: net.census(self)),
        mock.patch.object(driver.Exposure, 'listeners', lambda self: {(x.SEED_IP, 48080), (x.SEED_IP, 48081)}),
        mock.patch.object(driver.Exposure, 'absent', lambda self, name: None),
        mock.patch.dict(d.PROCS, clear=True), mock.patch.dict(d.SAVED, clear=True)]
    for p in patches:
        p.start()
    try:
        yield clock
    finally:
        for p in reversed(patches):
            p.stop()


def prepare(base):
    for sub in ('bin',)+tuple(f'{r}-{k}' for r in x.ROLES for k in ('private', 'public')):
        (base/sub).mkdir(mode=0o700)
    for name in ('monerod', 'monero-wallet-cli', 'monero-wallet-rpc'):
        (base/'bin'/name).write_bytes(name.encode())
    return Net(base)


def journey(base, uptime, adverse=None, hooks=None):
    """Run both real roles concurrently; return (net, {role: exposure}, {role: error})."""
    net = prepare(base)
    net.adverse = adverse
    roles, errors = {}, {}
    with substituted(net, uptime):
        for role in x.ROLES:
            roles[role] = driver.Exposure(role, base/(role+'-private'), base/(role+'-public'))
        for hook in hooks or ():
            hook(net, roles)
        def run(role):
            try:
                roles[role].run()
                roles[role].publish('complete')
            except BaseException as error:  # Mirrors main(): announce failure to the other role.
                errors[role] = error
                td.private_write(driver.EXCHANGE/(role+'.json'),
                                 (json.dumps(dict(role=role, step='failed', unix=0))+'\n').encode())
        threads = [threading.Thread(target=run, args=(role,), daemon=True) for role in x.ROLES]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(120)
        assert not any(thread.is_alive() for thread in threads), 'journey hung'
    return net, roles, errors


def rows_from(base):
    rows = x.empty_rows()
    for role, files in x.DRIVER_FILES.items():
        for name in files:
            rows[name].update(m.r.read_public_rows(base/(role+'-public')/name, x.shapes(), x.REQUIRED))
    for file in ('host.json', 'resources.json', 'cleanup.json'):
        for key in x.REQUIRED[file]:
            rows[file][key] = dict(status='PASS')
    return rows


class Journey(unittest.TestCase):
    def test_full_journey_passes_every_driver_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            net, roles, errors = journey(base, x.UPTIME_SECONDS)
            self.assertEqual(errors, {})
            rows = rows_from(base)
            self.assertEqual(x.verdict(rows), 'PASS_EXPOSURE_CANDIDATE_DEV_HOST_ONLY')
            client = rows['client.json']
            self.assertGreaterEqual(client['cold_bootstrap']['late_join_count'], x.LATE_JOIN_COUNT)
            self.assertEqual(client['missing_auth_refused']['status_code'], 401)
            self.assertTrue(client['wrong_tls_refused']['stale_pin_refused'])
            self.assertEqual(rows['seed.json']['seed_restart']['new_certificate'], True)
            self.assertEqual(net.launch_count, 2)                     # Two exposed seed launches, two pins.
            # Logins: one fresh per launch, only ever in the child environment.
            launches = [e for e in net.events if e[0] == 'launch' and e[1].startswith('node')]
            self.assertEqual(rows['seed.json']['foreign_network_refused']['clients_undisturbed'], 2)
            self.assertEqual(rows['foreign.json']['foreign_peer_isolated']['foreign_count'], 1)
            self.assertTrue(all(not any(a.startswith('node:') for a in e[2]) for e in launches))
            # Public rows carry no pin, raw tip or login; the exchange carried no login either.
            public = b''.join(p.read_bytes() for r in x.ROLES for p in (base/(r+'-public')).iterdir())
            for secret in (net.pin.encode(), net.seed_login.encode(), b'node:'):
                self.assertNotIn(secret, public)
            exchange = b''.join(p.read_bytes() for p in (base/'exchange').iterdir())
            self.assertNotIn(b'node:', exchange)
            # Every launch passed its policy and ran in light mode.
            for role in x.ROLES:
                state = json.loads((base/(role+'-private')/driver.STATE).read_text())
                self.assertTrue(all(state['counters']['light']))
                self.assertEqual(state['phase'], 'complete')
            for name, (process, _) in d.PROCS.items():
                self.assertIsNotNone(process.poll(), name)

    def test_rehearsal_leaves_steady_row_not_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _, _, errors = journey(base, x.REHEARSAL_UPTIME_SECONDS)
            self.assertEqual(errors, {})
            rows = rows_from(base)
            self.assertEqual(rows['client.json']['steady_exposed']['status'], 'NOT_RUN')
            self.assertEqual(x.verdict(rows, x.REHEARSAL_UPTIME_SECONDS), 'REHEARSAL_PASS_STEADY_NOT_RUN')

    def test_stalled_chain_fails_both_roles_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            net, roles, errors = journey(Path(tmp), x.REHEARSAL_UPTIME_SECONDS, adverse='stall')
            self.assertIn('client', errors)
            self.assertIn('seed', errors)          # The seed sees the client's failed step.
            self.assertIn('foreign', errors)        # Every waiting role ends on the failure.
            self.assertEqual([e for e in net.events if e[0] == 'launch' and e[1] == 'nodeF'], [])

    def test_unchanged_certificate_after_restart_fails(self):
        def same_pin(net, roles):
            original = net.launch
            def launch(name, argv, cwd, env=None, **kwargs):
                process = original(name, argv, cwd, env, **kwargs)
                if name == 'nodeS' and net.launch_count == 2:
                    net.pin = hashlib.sha256(b'launch-1').hexdigest()
                return process
            d.launch = launch
        with tempfile.TemporaryDirectory() as tmp:
            _, _, errors = journey(Path(tmp), x.REHEARSAL_UPTIME_SECONDS, hooks=[same_pin])
            self.assertIn('seed', errors)
            self.assertIn('client', errors)

    def test_missing_wrong_network_log_fails(self):
        def silent(net, roles):
            original = net.launch
            def launch(name, argv, cwd, env=None, **kwargs):
                if name == 'nodeF':
                    with mock.patch.object(net, 'seed_online', lambda: False):
                        return original(name, argv, cwd, env, **kwargs)
                return original(name, argv, cwd, env, **kwargs)
            d.launch = launch
        with tempfile.TemporaryDirectory() as tmp:
            _, _, errors = journey(Path(tmp), x.REHEARSAL_UPTIME_SECONDS, hooks=[silent])
            self.assertIsInstance(errors.get('seed'), ValueError)
            self.assertIn('client', errors)
            self.assertIn('foreign', errors)

    def test_restart_refuses_and_rows_are_role_bound(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = prepare(Path(tmp)).root
            with substituted(Net(base), x.REHEARSAL_UPTIME_SECONDS):
                seed = driver.Exposure('seed', base/'seed-private', base/'seed-public')
                with self.assertRaises(ValueError):
                    seed.row('client.json', 'cold_bootstrap')
                with self.assertRaises(ValueError):
                    driver.Exposure('seed', base/'seed-private', base/'seed-public')
                with self.assertRaises(ValueError):
                    seed.start('K', fresh=True)          # Client nodes never run in the seed namespace.
                client = driver.Exposure('client', base/'client-private', base/'client-public')
                with self.assertRaises(ValueError):
                    client.start('F', fresh=True)        # The foreign peer has its own namespace.
                with self.assertRaises(ValueError):
                    driver.Exposure('both', base/'client-private', base/'client-public')

    def test_adverse_argv_controls_refuse_before_any_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            net = prepare(Path(tmp))
            with substituted(net, x.REHEARSAL_UPTIME_SECONDS):
                for role in x.ROLES:
                    exposure = driver.Exposure(role, net.root/(role+'-private'), net.root/(role+'-public'))
                    (exposure.private/'nodes').mkdir(mode=0o700)
                    exposure.argv_controls()
                    self.assertGreaterEqual(exposure.adverse_argv, 8)
                    self.assertIsNone(exposure.state['address'])
                self.assertEqual(net.events, [])


class ExposureManager(unittest.TestCase):
    def grant(self, out, **change):
        base = json.loads(TopologyManager().grant(out)['body'].split('\n', 1)[1].rsplit('\n', 1)[0])
        for key in ('verdict_label', 'uptime_seconds', 'wall_seconds', 'container_flags', 'listeners'):
            base.pop(key)
        base.update(schema='meownero-exposure-grant/1', workload=x.WORKLOAD, container_flags=m.FLAGS,
                    network=m.NETWORK, listeners='internal-bridge-no-published-port', launch_ready=False,
                    uptime_seconds=x.REHEARSAL_UPTIME_SECONDS, wall_seconds=x.MODES[x.REHEARSAL_UPTIME_SECONDS],
                    verdict_label='rehearsal', main_chain_count_max=x.MAX_COUNT)
        base.update(change)
        return dict(issueId=x.ISSUE, authorAgentId=c.PLATFORM, authorUserId=None,
                    body='```meownero-exposure-grant\n'+json.dumps(base)+'\n```')

    def parse(self, comment, out):
        return m.grant_payload(comment, commit='c'*40, inputs_hash='i'*64, artifact_hash='a'*64,
            runner_hash='r'*64, driver_hash='d'*64, output=out, now=2000, reuse=TopologyManager().reuse())

    def test_grant_binds_issue_network_and_listener_policy(self):
        out = Path('/tmp/never-created-tjs4177')
        self.assertTrue(self.parse(self.grant(out), out)['authorized'])
        self.assertEqual(self.parse(self.grant(out, uptime_seconds=x.UPTIME_SECONDS, wall_seconds=x.MODES[x.UPTIME_SECONDS],
                                               verdict_label='full'), out)['verdict_label'], 'full')
        for change in (dict(network=dict(m.NETWORK, internal=False)), dict(network=dict(m.NETWORK, published_ports=1)),
                       dict(container_flags=m.FLAGS+['-p', '48080:48080']), dict(public_launch=True),
                       dict(launch_ready=True), dict(listeners='loopback-only-network-none'),
                       dict(container_flags=['--network=host']+m.FLAGS), dict(verdict_label='full'),
                       dict(schema='meownero-topology-grant/1')):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.parse(self.grant(out, **change), out)
        topology = TopologyManager().grant(out)          # A milestone-2 grant never binds this runner.
        with self.assertRaises(ValueError):
            self.parse(dict(topology, issueId=x.ISSUE), out)
        with self.assertRaises(ValueError):
            self.parse(dict(self.grant(out), issueId=t.ISSUE), out)

    def test_network_and_container_commands_publish_nothing(self):
        root = Path('/tmp/r')
        command = m.network_command('net')
        self.assertIn('--internal', command)
        self.assertEqual(command[command.index('--subnet')+1], x.SUBNET)
        for role in x.ROLES:
            argv = m.container_command(root, role, 'name', 'net', 'sha256:'+'1'*64)
            self.assertNotIn('--network=none', argv)
            self.assertFalse({'-p', '--publish', '-P', '--publish-all', '--network=host', '--privileged'} & set(argv))
            self.assertEqual(argv[argv.index('--network')+1], 'net')
            self.assertEqual(argv[argv.index('--ip')+1], x.ROLES[role])
            mounts = [argv[i+1] for i, a in enumerate(argv) if a == '-v']
            self.assertIn(f'{root}/persistent/{role}:/out/private', mounts)
            self.assertIn(f'{root}/public/{role}:/public', mounts)
            self.assertTrue(all(v.endswith(':ro') for v in mounts if '/out/harness' in v or '/out/build' in v))
            for flag in m.FLAGS:
                self.assertIn(flag, argv)

    def inspected(self, role='seed', **host):
        h = dict(NetworkMode='net', NanoCpus=2_000_000_000, Memory=4*1024**3, MemorySwap=4*1024**3, PidsLimit=256,
                 CapDrop=['ALL'], SecurityOpt=['no-new-privileges'], Privileged=False, PortBindings={},
                 PublishAllPorts=False, Ulimits=[dict(Name='core', Soft=0, Hard=0)])
        h.update(host)
        return dict(HostConfig=h, Config=dict(User=f'{os.getuid()}:{os.getgid()}'),
                    NetworkSettings=dict(Networks={'net': dict(IPAddress=x.ROLES[role])}, Ports={}, SandboxKey='k'))

    def test_limits_refuse_published_ports_and_foreign_networks(self):
        m.verify_limits(self.inspected(), 'net', 'seed')
        for value in (self.inspected(PortBindings={'48080/tcp': [dict(HostPort='48080')]}),
                      self.inspected(PublishAllPorts=True), self.inspected(NetworkMode='bridge'),
                      self.inspected(NetworkMode='host'), self.inspected(Memory=8*1024**3)):
            with self.assertRaises(ValueError):
                m.verify_limits(value, 'net', 'seed')
        exposed = self.inspected()
        exposed['NetworkSettings']['Ports'] = {'48080/tcp': [dict(HostIp='0.0.0.0', HostPort='48080')]}
        with self.assertRaises(ValueError):
            m.verify_limits(exposed, 'net', 'seed')
        two = self.inspected()
        two['NetworkSettings']['Networks']['bridge'] = dict(IPAddress='172.17.0.2')
        with self.assertRaises(ValueError):
            m.verify_limits(two, 'net', 'seed')
        with self.assertRaises(ValueError):
            m.verify_limits(self.inspected('client'), 'net', 'seed')

    def test_subnet_collision_refuses(self):
        def control(subnets):
            def run(argv, deadline, **kwargs):
                if argv[-2:] == ['ls', '-q']:
                    return subprocess.CompletedProcess(argv, 0, 'a\n', '')
                return subprocess.CompletedProcess(argv, 0, json.dumps([dict(IPAM=dict(
                    Config=[dict(Subnet=s) for s in subnets]))]), '')
            return types.SimpleNamespace(run=run)
        self.assertTrue(m.subnet_free(control(['172.17.0.0/16']), 0))
        for subnet in ('10.231.77.0/29', '10.231.0.0/16', '10.0.0.0/8'):
            with self.subTest(subnet=subnet), self.assertRaises(ValueError):
                m.subnet_free(control([subnet]), 0)



class FakeDocker:
    """Docker CLI substitute for the owned network and both role containers."""
    def __init__(self, out, image, outputs, fail=None, published=False):
        self.out, self.image, self.outputs, self.fail, self.published = out, image, outputs, fail, published
        self.network, self.containers, self.calls = None, {}, []
        self.offset = len(m.g.DOCKER)

    def value(self, info):
        mounts = [dict(Source=src, Destination=dst) for src, dst in info['mounts']]
        ports = {'48080/tcp': [dict(HostIp='0.0.0.0', HostPort='48080')]} if self.published else {}
        return dict(Id=info['id'], Name='/'+info['name'], Image=self.image, Mounts=mounts,
            Config=dict(Labels={m.LABEL: info['name']}, User=f'{os.getuid()}:{os.getgid()}'),
            HostConfig=dict(NetworkMode=info['network'], NanoCpus=2_000_000_000, Memory=4*1024**3,
                MemorySwap=4*1024**3, PidsLimit=256, CapDrop=['ALL'], SecurityOpt=['no-new-privileges'],
                Privileged=False, PortBindings={}, PublishAllPorts=False, Ulimits=[dict(Name='core', Soft=0, Hard=0)]),
            NetworkSettings=dict(Networks={info['network']: dict(IPAddress=info['ip'])}, Ports=ports,
                                 SandboxKey='/var/run/docker/netns/'+info['id'][:12]),
            State=dict(info['state']))

    def complete(self, role, info):
        public = self.out/'public'/role
        for name, raw in self.outputs[role].items():
            (public/name).write_bytes(raw)
        code = 1 if self.fail == role else 0
        if code:
            beat = json.loads(self.outputs[role]['heartbeat.json'])
            (public/'heartbeat.json').write_text(json.dumps(dict(beat, phase='failed')))
        (self.out/'staging'/('control-'+role)/'resources-1.json').write_text(json.dumps(dict(
            oom=0, oom_kill=0, memory_peak_bytes=10**9, cpu_usage_usec=10**9)))
        info['state'].update(Running=False, ExitCode=code)

    def run(self, argv, deadline, check=True, monitor=True, **kwargs):
        argv = [a.decode() if isinstance(a, bytes) else a for a in argv]
        self.calls.append(argv)
        done = lambda out='', code=0: subprocess.CompletedProcess(argv, code, out.encode(), b'')
        if argv[0] == 'du':
            return done(f'4096\t{argv[-1]}\n')
        rest = argv[self.offset:]
        if rest[:2] == ['image', 'inspect']:
            return done(json.dumps([dict(Id=self.image)]))
        if rest[:2] == ['network', 'ls']:
            if '--filter' in rest:
                return done('n'*64 if self.network else '')
            return done('a'*12+'\n')
        if rest[:2] == ['network', 'inspect']:
            if rest[2] == 'a'*12:
                return done(json.dumps([dict(IPAM=dict(Config=[dict(Subnet='172.17.0.0/16')]))]))
            if not self.network:
                return done('', 1)
            containers = {i['id']: dict(Name=i['name']) for i in self.containers.values()}
            return done(json.dumps([dict(self.network, Containers=containers)]))
        if rest[:2] == ['network', 'create']:
            self.network = dict(Name=rest[-1], Driver='bridge', Internal='--internal' in rest, EnableIPv6=False,
                Labels={m.LABEL: rest[-1]}, IPAM=dict(Config=[dict(Subnet=rest[rest.index('--subnet')+1],
                                                                   Gateway=rest[rest.index('--gateway')+1])]))
            return done()
        if rest[:2] == ['network', 'rm']:
            c.require(not self.containers, 'network in use')
            self.network = None
            return done()
        verb = rest[0]
        if verb == 'create':
            name = argv[argv.index('--name')+1]
            role = next(r for r in x.ROLES if f'-{r}-' in name)
            self.containers[role] = dict(id=str(5+list(x.ROLES).index(role))*64, name=name, role=role,
                network=argv[argv.index('--network')+1], ip=argv[argv.index('--ip')+1],
                mounts=[tuple(argv[i+1].split(':')[:2]) for i, a in enumerate(argv) if a == '-v'],
                state=dict(Running=False, ExitCode=0, OOMKilled=False), polls=0)
            return done()
        if verb == 'inspect':
            info = next((i for i in self.containers.values() if i['name'] == rest[1] or i['id'] == rest[1]), None)
            if info is None:
                return done('', 1)
            if info['state']['Running']:
                info['polls'] += 1
                if info['polls'] > (2 if info['role'] == self.fail else 4):
                    self.complete(info['role'], info)
            return done(json.dumps([self.value(info)]))
        if verb == 'ps':
            return done('')
        if verb == 'start':
            info = next(i for i in self.containers.values() if i['id'] == rest[1])
            info['state'].update(Running=True)
            return done()
        if verb == 'stop':
            info = next(i for i in self.containers.values() if i['id'] == rest[-1])
            info['state'].update(Running=False, ExitCode=137)
            return done()
        if verb == 'rm':
            role = next(r for r, i in self.containers.items() if i['id'] == rest[-1])
            del self.containers[role]
            return done()
        raise AssertionError(argv)


class ManagerIntegration(unittest.TestCase):
    def outputs(self, base):
        journey(base, x.REHEARSAL_UPTIME_SECONDS)
        return {role: {p.name: p.read_bytes() for p in (base/(role+'-public')).iterdir()} for role in x.ROLES}

    def drive(self, fail=None, published=False):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        (base/'journey').mkdir(mode=0o700)
        outputs = self.outputs(base/'journey')
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
        grant = ExposureManager().grant(out, reuse_build_root=str(retained), candidate_commit='c'*40,
            runner_sha256=c.digest((c.HERE/'run-exposure.py').read_bytes()),
            driver_sha256=c.digest((c.HERE/m.DRIVER).read_bytes()),
            inputs_sha256=c.digest((c.HERE/'integration/inputs.json').read_bytes()), artifact_sha256=c.digest(artifact),
            valid_from_unix=int(time.time())-60, valid_until_unix=int(time.time())+49*3600)
        grant.update(id='12345678-0000-0000-0000-000000000000')
        docker = FakeDocker(out, image, outputs, fail, published)
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
        return code, out, docker, receipt

    def test_rehearsal_runs_both_namespaces_and_cleans_everything(self):
        code, out, docker, receipt = self.drive()
        self.assertEqual((code, receipt['result']), (0, 'REHEARSAL_PASS_STEADY_NOT_RUN'))
        rows = receipt['rows']
        self.assertTrue(all(v['status'] == 'PASS' for v in rows['cleanup.json'].values()))
        self.assertTrue(all(v['status'] == 'PASS' for v in rows['host.json'].values()))
        self.assertEqual(rows['resources.json']['no_oom']['containers'], 3)
        self.assertIsNone(docker.network)
        self.assertEqual(docker.containers, {})
        self.assertFalse((out/'staging').exists() or (out/'exchange').exists())
        for path in (out/'evidence').iterdir():
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertNotIn(b'/home/', path.read_bytes())
            self.assertNotIn(b'/tmp/', path.read_bytes())
        creates = [a for a in docker.calls if a[docker.offset:docker.offset+1] == ['create']]
        self.assertEqual(len(creates), 3)
        self.assertEqual(rows['host.json']['distinct_namespaces']['namespaces'], 3)
        network = next(a for a in docker.calls if a[docker.offset:docker.offset+2] == ['network', 'create'])
        self.assertIn('--internal', network)
        self.assertFalse(any(flag in a for a in creates for flag in ('-p', '--publish', '-P')))

    def test_one_role_failure_stops_the_other_and_still_cleans(self):
        code, out, docker, receipt = self.drive(fail='client')
        self.assertEqual((code, receipt['result']), (1, 'FAIL'))
        self.assertEqual(receipt['failure_class'], 'native_exit')
        self.assertTrue(all(v['status'] == 'PASS' for v in receipt['rows']['cleanup.json'].values()))
        self.assertTrue(any(a[docker.offset:docker.offset+1] == ['stop'] for a in docker.calls))
        self.assertIsNone(docker.network)

    def test_a_published_port_fails_closed_and_cleans(self):
        code, out, docker, receipt = self.drive(published=True)
        self.assertEqual(code, 1)
        self.assertEqual(receipt['result'], 'FAIL')
        self.assertIsNone(docker.network)
        self.assertEqual(docker.containers, {})


if __name__ == '__main__':
    unittest.main()
