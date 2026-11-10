#!/usr/bin/env python3
"""TJS-4177 exposure candidate driver. Requires an exact runtime grant.

Runs once per container on the owned `--internal` bridge, in role `seed`,
`client` or `foreign` (read from /out/control/role). The seed container owns
node S, whose P2P listener and TLS restricted daemon RPC bind the seed bridge
IP. The client container owns K (first client) and N (cold newcomer from
genesis); the foreign container owns F (a `--stagenet` peer) on its own
address. Each container writes only its own file in the
shared private exchange directory; it carries steps, counts, tips and TLS
certificate pins, never a credential. Every daemon login stays in its child's
environment (L4) and only salted witnesses reach /public (L3).

Reuses the accepted genesis helpers (process ownership, Digest client, seal and
manifest checks) and the milestone-2 topology node lifecycle without changing
them. A container restart is never planned here: any restart refuses.
"""
import contextlib
import hashlib
import http.client
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import ssl
import sys
import time
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import profile_contract as c
from integration import exposure_contract as x
from integration import topology_contract as t
from integration import topology_driver as td

d = td.d
ROLE_FILE = Path('/out/control/role')
EXCHANGE = Path('/out/exchange')
STATE = 'exposure-state.json'
WRONG_NETWORK = b'WRONG NETWORK AGENT CONNECTED!'
CLIENT_STEPS = ('new', 'probed', 'bootstrapped', 'foreign-start', 'restart-seed', 'caught-up',
                'steady', 'done')
SEED_STEPS = ('new', 'exposed', 'foreign-armed', 'foreign-checked', 'restarted', 'complete')
FOREIGN_STEPS = ('new', 'foreign-done', 'done')
STEPS = {'seed': SEED_STEPS, 'client': CLIENT_STEPS, 'foreign': FOREIGN_STEPS}


class PinMismatch(ConnectionError):
    """The presented certificate is not the pinned launch certificate; nothing was sent."""


def peer_pin(host, port, timeout=5):
    """SHA-256 of the DER certificate presented by a TLS listener (no request is sent)."""
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE  # Authentication is the pin comparison below.
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    raw = socket.create_connection((host, port), timeout=d.budget(timeout))
    try:
        wrapped = context.wrap_socket(raw)
    except BaseException:
        raw.close()
        raise
    return wrapped, hashlib.sha256(wrapped.getpeercert(binary_form=True)).hexdigest()


class TLSRPC:
    """Digest-over-TLS client: the pin must match before the first request byte."""
    def __init__(self, host, port, pin, login=None):
        self.host, self.port, self.pin, self.login = host, port, x.pin(pin), login

    def session(self):
        sock, presented = peer_pin(self.host, self.port)
        if presented != self.pin:
            sock.close()
            raise PinMismatch('certificate pin mismatch')
        connection = http.client.HTTPConnection(self.host, self.port, timeout=d.budget(5))
        connection.sock = sock
        # A closed session must never be reopened: http.client would reconnect in plaintext
        # and send the Digest header before any pin check (Platform 68a99d55).
        connection.auto_open = 0
        return connection

    def call(self, method, params=None, login='current', raw=False):
        auth = self.login if login == 'current' else login
        body = json.dumps({'jsonrpc': '2.0', 'id': '0', 'method': method, 'params': params or {}}).encode()
        url = f'https://{self.host}:{self.port}/json_rpc'
        connection = self.session()
        try:
            def exchange(authorization=None):
                headers = {'Content-Type': 'application/json'}
                if authorization is not None:
                    headers['Authorization'] = 'Digest '+authorization
                if connection.sock is None:  # epee closed the pinned session: never reconnect.
                    raise ConnectionError('pinned TLS session closed')
                connection.sock.settimeout(d.budget(5))
                connection.request('POST', '/json_rpc', body, headers)
                with connection.getresponse() as response:
                    return response.status, response.headers, response.read(1 << 20)
            code, headers, payload = exchange()
            # epee binds nonce/nc to this TLS session; never answer its challenge on another one.
            if code == 401 and auth:
                for field in headers.get_all('WWW-Authenticate', []):
                    scheme, _, value = field.partition(' ')
                    parsed = urllib.request.parse_keqv_list(urllib.request.parse_http_list(value))
                    if scheme.lower() == 'digest' and parsed.get('algorithm', 'MD5') == 'MD5' and parsed.get('qop') == 'auth':
                        manager = urllib.request.HTTPPasswordMgrWithDefaultRealm()
                        manager.add_password(None, url, *auth.split(':', 1))
                        request = urllib.request.Request(url, body, {'Content-Type': 'application/json'})
                        answer = urllib.request.HTTPDigestAuthHandler(manager).get_authorization(request, parsed)
                        if answer is not None:
                            code, headers, payload = exchange(answer)
                        break
        finally:
            connection.close()
        if raw:
            return code, (json.loads(payload) if 200 <= code < 300 else {})
        c.require(200 <= code < 300, 'HTTP authentication/transport failure')
        value = json.loads(payload)
        c.require('error' not in value, 'native RPC returned error')
        return value.get('result', value)

    def auth_controls(self):
        self.call('get_info')
        for login in (None, 'wrong:'+secrets.token_hex(8)):
            code, _ = self.call('get_info', login=login, raw=True)
            c.require(code == 401, 'missing/wrong credential accepted')
            self.call('get_info')
        return True


def plaintext_refused(host, port):
    """A plaintext HTTP client to the TLS listener gets no HTTP response."""
    with socket.create_connection((host, port), timeout=d.budget(5)) as sock:
        sock.settimeout(d.budget(5))
        sock.sendall(b'POST /json_rpc HTTP/1.1\r\nHost: x\r\nContent-Length: 2\r\n\r\n{}')
        reply = b''
        with contextlib.suppress(OSError):
            while len(reply) < 64:
                part = sock.recv(64)
                if not part:
                    break
                reply += part
    return not reply.startswith(b'HTTP/')


def classify(role, owned, routes):
    """Pure census rules for one namespace. owned: [(node or None, socket tuple)].

    Routes: loopback plus the owned /29 on the bridge, and no default route.
    Listeners: only the role's planned addresses (never a wildcard). Established
    sockets: seed P2P accepts only from the client and foreign IPs and the seed RPC only
    from the client IP (its planned probes); other nodes connect out to
    the exposed seed P2P from an ephemeral port; same-namespace driver RPC is ignored;
    every other socket, and any UDP socket, counts as foreign.
    """
    subnet = ''.join(f'{b:02X}' for b in socket.inet_aton(x.SUBNET.split('/')[0])[::-1])
    for line in routes:
        iface, destination, mask = line.split()[0], line.split()[1], line.split()[7]
        c.require(destination != '00000000', 'default route on the internal bridge')
        c.require(iface == 'lo' or destination == subnet and mask == 'F8FFFFFF', 'route outside the owned subnet')
    if role == 'seed':
        listen = {(x.SEED_IP, x.P2P['S']), (x.SEED_IP, x.RPC['S']), ('127.0.0.1', x.P2P['S']),
                  ('127.0.0.1', x.RPC['S']), ('127.0.0.1', x.WALLET_PORT)}  # Loopback: the private signer launch.
    else:
        listen = {('127.0.0.1', port) for n in x.NODES[role] for port in (x.P2P[n], x.RPC[n])}
    inbound = {x.CLIENT_IP: 'client', x.FOREIGN_IP: 'foreign'}
    edges, foreign = {}, 0
    for node, (kind, state, lip, lport, rip, rport) in owned:
        if kind.startswith('udp'):
            foreign += 1
        elif state == '0A':
            foreign += (lip, lport) not in listen and lip != '::1'
        elif state != '01':
            continue
        elif role == 'seed' and (lip, lport) == (x.SEED_IP, x.P2P['S']) and rip in inbound:
            edges[inbound[rip]] = edges.get(inbound[rip], 0)+1  # Peers by source namespace.
        elif role == 'seed' and (lip, lport) == (x.SEED_IP, x.RPC['S']) and rip == x.CLIENT_IP:
            continue  # The client's planned pin/TLS/auth probes; any other source stays foreign.
        elif role != 'seed' and lip == x.ROLES[role] and (rip, rport) == (x.SEED_IP, x.P2P['S']) and \
                lport not in x.P2P.values():
            edges[node] = edges.get(node, 0)+1  # Client-initiated to the exposed listener.
        elif lip == rip or lip in ('127.0.0.1', '::1') and rip in ('127.0.0.1', '::1'):
            continue  # Driver RPC client within this namespace.
        else:
            foreign += 1
    return edges, foreign


def ipv4(word):
    return socket.inet_ntoa(bytes.fromhex(word)[::-1])


def ipv6(word):
    raw = b''.join(bytes.fromhex(word[i:i+8])[::-1] for i in range(0, 32, 8))
    return socket.inet_ntop(socket.AF_INET6, raw)


def socket_table():
    """inode -> (proto, state, local ip, local port, remote ip, remote port)."""
    table = {}
    for kind in ('tcp', 'tcp6', 'udp', 'udp6'):
        decode = ipv6 if kind.endswith('6') else ipv4
        for line in Path('/proc/net/'+kind).read_text().splitlines()[1:]:
            parts = line.split()
            (lip, lport), (rip, rport) = (p.split(':') for p in parts[1:3])
            table[parts[9]] = (kind, parts[3], decode(lip), int(lport, 16), decode(rip), int(rport, 16))
    return table


class Exposure(td.Topology):
    """Milestone-2 node lifecycle (seal, manifest, light mode) with exposure argv and transport."""
    def __init__(self, role, private=None, public=None):
        c.require(role in x.ROLES, 'unknown exposure role')
        self.role = role
        self.private, self.public = private or d.PRIVATE, public or d.PUBLIC
        self.binaries = {name: c.digest((d.BIN/name).read_bytes()) for name in
                         ('monerod', 'monero-wallet-cli', 'monero-wallet-rpc')}
        c.require(not (self.private/STATE).exists(), 'unplanned restart refuses')
        self.rpc, self.pins, self.bound, self.light = {}, {}, {}, []
        self.launches = self.adverse_argv = self.census_samples = self.foreign_peak = 0
        self.salt = secrets.token_bytes(32)
        td.private_write(self.private/'salt', self.salt)
        self.state = dict(schema='meownero-exposure-state/1', role=role, phase='new', address=None,
                          rows={f: x.empty_rows()[f] for f in x.DRIVER_FILES[role]})
        self.step = 'new'
        self.save()

    # ---- persistence and exchange --------------------------------------------------
    def save(self):
        self.state['counters'] = dict(launches=self.launches, adverse_argv=self.adverse_argv,
            census=self.census_samples, foreign=self.foreign_peak, light=self.light)
        td.private_write(self.private/STATE, c.canonical(self.state))

    def row(self, file, key, **witness):
        c.require(file in x.DRIVER_FILES[self.role] and key in x.REQUIRED[file], 'unknown exposure row')
        self.state['rows'][file][key] = dict(status='PASS', **witness)
        self.save()

    def publish(self, phase=None):
        for file in x.DRIVER_FILES[self.role]:
            (self.public/file).write_text(json.dumps(self.state['rows'][file], indent=2)+'\n')
        self.heartbeat(phase)

    def heartbeat(self, phase=None, count=0, samples=0):
        value = dict(role=self.role, phase=phase or self.state['phase'], count=count, samples=samples,
                     unix=int(time.time()))
        td.private_write(self.public/'heartbeat.json', (json.dumps(value)+'\n').encode())

    def say(self, step, **data):
        order = STEPS[self.role]
        c.require(step == 'failed' or step in order and order.index(step) >= order.index(self.step), 'step order')
        self.step = step if step != 'failed' else self.step
        value = dict(role=self.role, step=step, unix=time.time(), **data)
        if self.role == 'seed' and 'S' in self.rpc:
            height, top, _ = self.info('S')
            value.update(count=height, top=top)
        td.private_write(EXCHANGE/(self.role+'.json'), (json.dumps(value)+'\n').encode())
        self.heartbeat(step, value.get('count', 0))

    def hear(self, role):
        try:
            value = json.loads((EXCHANGE/(role+'.json')).read_bytes())
        except FileNotFoundError:
            return None
        c.require(value.get('role') == role, 'exchange identity')
        c.require(value['step'] != 'failed', 'peer role failed')
        return value

    def reached(self, role, step):
        value = self.hear(role)
        order = STEPS[role]
        return value if value and order.index(value['step']) >= order.index(step) else None

    # ---- native processes --------------------------------------------------------
    def daemon_argv(self, name, root, *, mining=False, private=False):
        exposed = name == 'S' and not private
        ip = x.SEED_IP if exposed else '127.0.0.1'
        argv = [str(d.BIN/'monerod'), '--stagenet' if name == 'F' else '--testnet', '--data-dir', str(root),
            '--non-interactive', '--no-igd', '--allow-local-ip', '--disable-dns-checkpoints',
            '--check-updates', 'disabled', '--hide-my-port', '--max-concurrency', '1', '--no-zmq',
            '--rpc-ssl', 'enabled' if exposed else 'disabled', '--restricted-rpc']
        if exposed:
            argv.append('--confirm-external-bind')  # Accepted only with TLS on the owned bridge IP.
        argv += ['--p2p-bind-ip', ip, '--p2p-bind-ipv6-address', '::1', '--p2p-bind-port', str(x.P2P[name]),
            '--rpc-bind-ip', ip, '--rpc-bind-port', str(x.RPC[name]), '--max-connections-per-ip', '4',
            '--log-level', '1', '--log-file', str(root/'native.log')]
        if private:
            argv.append('--offline')
        else:
            argv += ['--add-exclusive-node', x.SEED_EXCLUSIVE if name == 'S' else x.SEED]
        if mining:
            argv += ['--start-mining', self.state['address'], '--mining-threads', '1']
        return argv

    def check(self, name, argv, *, mining=False, private=False):
        if private:
            return t.check_argv('monerod', argv, offline=True)  # Milestone-2 loopback shape, unchanged.
        return x.check_exposed('seed' if name == 'S' else 'foreign' if name == 'F' else 'client', argv, mining=mining)

    def start(self, name, *, mining=False, private=False, fresh=False):
        c.require(name in x.NODES[self.role], 'node/role mismatch')
        c.require(f'node{name}' not in self.running(), 'node already running')
        root = self.root(name)
        argv = self.daemon_argv(name, root, mining=mining, private=private)
        self.check(name, argv, mining=mining, private=private)  # Refuse before any root/process effect.
        if fresh:
            c.require(not root.exists(), 'fresh node root already exists')
            root.mkdir(mode=0o700)
            manifest = dict(d.creation('daemon', self.binaries), stopped_saved=False)
        else:
            c.root_manifest(root, d.SAVED[str(root)])
            d.released(root)
            manifest = dict(d.SAVED[str(root)], stopped_saved=False)
        (root/'creation.json').write_bytes(c.canonical(manifest))
        os.chmod(root/'creation.json', 0o600)
        d.SAVED.pop(str(root), None)
        login = 'node:'+secrets.token_hex(24)  # Fresh per launch; memory and child environment only.
        env = dict(d.ENV, RPC_LOGIN=login, MONERO_RANDOMX_UMASK='4')
        d.launch(f'node{name}', argv, root, env)
        self.bound[name] = x.SEED_IP if name == 'S' and not private else '127.0.0.1'
        self.launches += 1
        self.light.append(env['MONERO_RANDOMX_UMASK'] == '4')
        if name == 'S' and not private:
            # The owner reads the launch certificate from its own namespace (TOFU there only).
            def listening():
                sock, presented = peer_pin(x.SEED_IP, x.RPC['S'])
                sock.close()
                return presented
            self.pins['S'] = d.wait(listening, 120)
            rpc = TLSRPC(x.SEED_IP, x.RPC['S'], self.pins['S'], login)
        else:
            rpc = d.RPC(x.RPC[name], login)
        d.wait(lambda: rpc.call('get_info'), 120)
        self.rpc[name] = rpc
        self.save()
        return rpc

    def absent(self, name):
        host = self.bound[name]
        for port in (x.P2P[name], x.RPC[name]):
            with socket.socket() as sock:
                sock.settimeout(d.budget(1))
                c.require(sock.connect_ex((host, port)) != 0, 'listener remains')

    def stop(self, name, seal=True):
        identity = d.stop(f'node{name}')
        self.absent(name)
        if seal:
            root = self.root(name)
            d.released(root)
            d.seal(root, 'daemon', self.binaries)
        self.rpc.pop(name, None)
        self.save()
        return identity

    def info(self, name):
        if name == 'F':  # Foreign chain: its own genesis, never the testnet one.
            value = self.rpc['F'].call('get_info')
            return value['height'], td.hex64(value['top_block_hash']), 0
        return super().info(name)

    def miner_address(self):
        """F1's restore-signer shape against the seed's private offline loopback launch."""
        root = self.private/'wallets'/'miner'
        root.mkdir(parents=True, mode=0o700)
        os.chmod(root.parent, 0o700)
        cwd = self.private/'wallets'/'miner-rpc'
        cwd.mkdir(mode=0o700)
        config = self.private/'wallets'/'miner-cli.conf'
        td.private_write(config, ('daemon-login='+self.rpc['S'].login+'\ndaemon-ssl=disabled\n').encode())
        argv = [str(d.BIN/'monero-wallet-rpc'), '--testnet', '--config-file', str(config),
            '--daemon-address', f'127.0.0.1:{x.RPC["S"]}', '--wallet-dir', str(root),
            '--rpc-bind-ip', '127.0.0.1', '--rpc-bind-port', str(x.WALLET_PORT), '--rpc-ssl', 'disabled',
            '--log-file', str(cwd/'native.log')]
        t.check_argv('monero-wallet-rpc', argv, signer=True)
        d.launch('miner-wallet', argv, cwd)
        self.launches += 1
        login = d.wait(lambda: c.check_file(cwd/f'monero-wallet-rpc.{x.WALLET_PORT}.login',
                       modes=(0o400, 0o600)).decode(), 30)
        rpc = d.RPC(x.WALLET_PORT, login)
        d.wait(lambda: rpc.call('get_version'), 30)
        password = secrets.token_hex(32)
        td.private_write(root/'password', (password+'\n').encode())
        rpc.call('create_wallet', dict(filename='wallet', password=password, language='English'))
        address = rpc.call('get_address', dict(account_index=0, address_index=[]))['address']
        rpc.call('close_wallet')
        d.stop('miner-wallet')
        d.absent(x.WALLET_PORT)
        config.unlink()  # Its login dies with the private launch; no credential file is kept.
        self.state['address'] = address
        self.save()

    # ---- census ------------------------------------------------------------------
    def census(self):
        """Owned sockets only: allowed listeners, peer edges, and anything else as foreign."""
        self.census_samples += 1
        table = socket_table()
        owned = []
        for name, (process, _) in list(d.PROCS.items()):
            if process.poll() is not None:
                continue
            for fd in Path(f'/proc/{process.pid}/fd').iterdir():
                with contextlib.suppress(FileNotFoundError):
                    target = os.readlink(fd)
                    if target.startswith('socket:[') and target[8:-1] in table:
                        owned.append((name[4:] if name.startswith('node') else None, table[target[8:-1]]))
        edges, foreign = classify(self.role, owned, Path('/proc/net/route').read_text().splitlines()[1:])
        for node in self.rpc:
            c.require(d.PROCS[f'node{node}'][0].poll() is None, 'unexpected native exit')
        self.foreign_peak = max(self.foreign_peak, foreign)
        return edges, foreign

    def listeners(self):
        """Witness the exposed seed's listening sockets after start."""
        table = socket_table()
        process = d.PROCS['nodeS'][0]
        found = set()
        for fd in Path(f'/proc/{process.pid}/fd').iterdir():
            with contextlib.suppress(FileNotFoundError):
                target = os.readlink(fd)
                if target.startswith('socket:[') and target[8:-1] in table and table[target[8:-1]][1] == '0A':
                    found.add(table[target[8:-1]][2:4])
        c.require(found and all(ip not in ('0.0.0.0', '::') for ip, _ in found), 'wildcard listener')
        c.require({(x.SEED_IP, x.P2P['S']), (x.SEED_IP, x.RPC['S'])} <= found and
                  all(ip in (x.SEED_IP, '::1') for ip, _ in found), 'exposed listener set')
        return found

    def confirm_pin(self):
        """Re-read the pin after listeners() bound the listener to the launched PID."""
        sock, presented = peer_pin(x.SEED_IP, x.RPC['S'])
        sock.close()
        c.require(presented == self.pins['S'], 'launch certificate changed after listener check')
        return presented

    # ---- adverse launcher policy --------------------------------------------------
    def argv_controls(self):
        name = x.NODES[self.role][0]
        owner = self.role
        saved, self.state['address'] = self.state['address'], '9'*95  # Policy fixtures only.
        base = self.daemon_argv(name, self.root(name), mining=name == 'S')
        self.state['address'] = saved
        def swap(option, value):
            argv = list(base)
            argv[argv.index(option)+1] = value
            return argv
        cases = [swap('--rpc-bind-ip', '0.0.0.0'), swap('--p2p-bind-ip', '0.0.0.0'),
            swap('--p2p-bind-ipv6-address', '::'), swap('--add-exclusive-node', '10.0.0.1:18080'),
            [a for a in base if a != '--restricted-rpc'], base+['--public-node'], base+['--public-nod'],
            base+['--rpc-login', 'a:b'], base+['--seed-node', x.SEED], base+['--disable-rpc-login'],
            base+['--rpc-restricted-bind-port', '48089'], base+['--add-peer', x.SEED],
            base+['--rpc-ssl-allow-any-cert'], base+['--add-exclusive-node', x.SEED]]
        if owner == 'seed':
            cases += [swap('--rpc-ssl', 'disabled'), swap('--rpc-bind-ip', x.CLIENT_IP),
                      swap('--p2p-bind-ip', x.GATEWAY), [a for a in base if a != '--confirm-external-bind']]
        else:
            cases += [swap('--p2p-bind-ip', x.ROLES[owner]), swap('--rpc-ssl', 'enabled'),
                      base+['--start-mining', '9'*95, '--mining-threads', '1'], base+['--confirm-external-bind']]
        count = len(d.PROCS)
        for argv in cases:
            try:
                x.check_exposed(owner, argv, mining=owner == 'seed')
            except t.PolicyRefusal:
                self.adverse_argv += 1
            else:
                raise ValueError('adverse exposure argv accepted')
        # The milestone-2 loopback shape still refuses the external-bind option.
        private = self.daemon_argv(name, self.root(name), private=True)
        for argv in (private+['--confirm-external-bind'], [a if a != '127.0.0.1' else x.SEED_IP for a in private]):
            try:
                t.check_argv('monerod', argv, offline=True)
            except t.PolicyRefusal:
                self.adverse_argv += 1
            else:
                raise ValueError('adverse private argv accepted')
        c.require(len(d.PROCS) == count, 'refused argv started a process')
        self.save()

    # ---- seed role ---------------------------------------------------------------
    def until(self, role, step, seconds):
        """Wait for the other role's step while publishing this role's tip and census."""
        end = time.monotonic()+d.budget(seconds)
        while time.monotonic() < end:
            value = self.reached(role, step)
            if value:
                return value
            for other in x.ROLES:  # Any failed role ends every wait.
                if other != self.role:
                    self.hear(other)
            self.census()
            self.say(self.step, **self.state.get('said', {}))
            time.sleep(d.budget(2))
        raise TimeoutError('exposure step deadline '+step)

    def announce(self, step, **data):
        self.state['said'] = data
        self.say(step, **data)

    def seed(self):
        (self.private/'nodes').mkdir(mode=0o700)
        self.argv_controls()
        self.start('S', private=True, fresh=True)   # Offline loopback launch for the signer only.
        self.miner_address()
        self.stop('S')
        self.start('S', mining=True)
        self.listeners()
        self.confirm_pin()
        self.rpc['S'].auth_controls()
        self.row('seed.json', 'owner_namespace_auth', correct_login_accepted=True, missing_rejected=True,
                 wrong_rejected=True, pinned=True)
        first = self.pins['S']
        self.announce('exposed', pin=first, launch=1)
        self.row('seed.json', 'exposed_listener', p2p_bind='owned-bridge-ip', rpc_bind='owned-bridge-ip',
                 rpc_tls=True, restricted_rpc=True, login_env_only=True, wildcard_listeners=0,
                 loopback_listeners_only_signer=True, default_route=False, launches=self.launches)
        self.until('client', 'foreign-start', 3600)
        log = self.root('S')/'native.log'
        offset = log.stat().st_size
        self.announce('foreign-armed', pin=first, launch=1)
        done = self.until('foreign', 'foreign-done', 900)
        foreign_genesis = td.hex64(done['foreign_genesis'])
        seen = WRONG_NETWORK in log.read_bytes()[offset:]
        unchanged = self.known('S', foreign_genesis) is None
        # The refused host may be blocked after repeated failures; the clients' address is not.
        edges, foreign = self.wait(lambda: (lambda e: e if 'foreign' not in e[0] else None)(self.census()), 120)
        c.require(seen and unchanged and foreign == 0 and edges.get('client') == 2, 'foreign network not refused')
        self.row('seed.json', 'foreign_network_refused', network='stagenet', wrong_network_logged=True,
                 seed_count_unchanged_by_foreign=True, foreign_connections_after=0, clients_undisturbed=2)
        self.announce('foreign-checked', pin=first, launch=1, wrong_network_logged=True)
        self.until('client', 'restart-seed', 600)
        stopped = self.info('S')
        before = d.PROCS['nodeS'][1]
        self.stop('S')
        self.start('S', mining=True)
        self.listeners()
        self.confirm_pin()
        second = self.pins['S']
        resumed = self.info('S')
        # A block found during the graceful stop is part of the sealed tip, never a race.
        c.require(second != first and d.PROCS['nodeS'][1] != before and resumed[0] >= stopped[0] and
                  self.known('S', stopped[1]) is False, 'seed restart identity')
        self.row('seed.json', 'seed_restart', changed_process=True, sealed_and_reopened=True, new_certificate=True,
                 stopped_count=stopped[0], resumed_count=resumed[0])
        self.announce('restarted', pin=second, launch=2, resumed_count=resumed[0])
        self.until('client', 'done', 2*x.UPTIME_SECONDS+3600)
        final = self.info('S')
        self.stop('S')
        c.require(self.light and all(self.light), 'light-mode launch history')
        self.row('seed-isolation.json', 'native_mining_bounds', threads=1, light_mode=True, max_count=x.MAX_COUNT,
                 final_count=final[0], external_funding=False, transactions=0)
        self.row('seed-isolation.json', 'launcher_policy', launches=self.launches, refused_before_start=0,
                 adverse_argv_refused=self.adverse_argv, census_samples=self.census_samples,
                 foreign_connections=self.foreign_peak)
        self.announce('complete', final_count=final[0])

    # ---- client role -------------------------------------------------------------
    def seed_tip(self):
        value = self.hear('seed')
        return value['count'], value['top']

    def follow(self, names, count=0):
        """True when every named node is at the seed's latest published tip."""
        tip = self.seed_tip()
        states = [self.info(n)[:2] for n in names]
        return tip if tip[0] >= count and all(s == tip for s in states) else None

    def probes(self, pin):
        """From this namespace: pin, plaintext and Digest refusals against the exposed RPC."""
        wrong = hashlib.sha256(pin.encode()).hexdigest()
        try:
            TLSRPC(x.SEED_IP, x.RPC['S'], wrong).call('get_info', login=None, raw=True)
        except PinMismatch:
            pass
        else:
            raise ValueError('wrong certificate pin accepted')
        c.require(plaintext_refused(x.SEED_IP, x.RPC['S']), 'plaintext HTTP answered on the TLS listener')
        rpc = TLSRPC(x.SEED_IP, x.RPC['S'], pin)
        missing, _ = rpc.call('get_info', login=None, raw=True)
        bad, _ = rpc.call('get_info', login='node:'+secrets.token_hex(24), raw=True)
        c.require(missing == 401 and bad == 401, 'exposed RPC answered without the launch login')
        return missing, bad

    def client(self):
        (self.private/'nodes').mkdir(mode=0o700)
        self.argv_controls()
        first = self.until('seed', 'exposed', 3600)['pin']
        missing, bad = self.probes(first)
        self.row('client.json', 'missing_auth_refused', status_code=missing, over_pinned_tls=True, other_namespace=True)
        self.row('client.json', 'wrong_auth_refused', status_code=bad, over_pinned_tls=True, other_namespace=True)
        self.announce('probed')
        self.start('K', fresh=True)
        self.wait(lambda: self.follow(('K',), x.LATE_JOIN_COUNT), 3600)
        late = self.seed_tip()[0]
        self.start('N', fresh=True)
        synced = self.wait(lambda: self.follow(('K', 'N'), late), 900)
        edges, foreign = self.wait(lambda: (lambda e: e if e[0] == {'K': 1, 'N': 1} else None)(self.census()), 120)
        c.require(foreign == 0, 'foreign connection')
        self.row('client.json', 'cold_bootstrap', client_from_genesis=True, late_join_count=late, synced_count=synced[0],
                 client_initiated=True, other_namespace=True, peer_connections=1, tip_salted=self.tip(synced[1]))
        self.announce('bootstrapped')
        # Foreign network (third namespace): the clients stay connected throughout.
        self.announce('foreign-start')
        self.until('seed', 'foreign-checked', 1200)
        c.require(self.census()[0] == {'K': 1, 'N': 1}, 'clients lost the seed during the foreign window')
        # Seed restart: both clients reconnect; the previous launch pin is refused.
        self.announce('restart-seed')
        restarted = self.until('seed', 'restarted', 900)
        second = restarted['pin']
        c.require(second != first, 'seed certificate did not change')
        try:
            TLSRPC(x.SEED_IP, x.RPC['S'], first).call('get_info', login=None, raw=True)
        except PinMismatch:
            pass
        else:
            raise ValueError('stale certificate pin accepted')
        c.require(self.probes(second) == (401, 401), 'restarted seed auth')
        caught = self.wait(lambda: self.follow(('K', 'N'), restarted['resumed_count']+2), 1800)
        self.row('client.json', 'wrong_tls_refused', wrong_pin_refused=True, stale_pin_refused=True,
                 plaintext_no_http_response=True, request_bytes_on_refusal=0)
        self.row('client.json', 'seed_restart_catch_up', clients=2, reconnected=True, new_pin_accepted=True,
                 advanced_blocks=caught[0]-restarted['resumed_count'], tip_salted=self.tip(caught[1]))
        # Client restart and catch-up.
        old = self.info('K')[0]
        before = d.PROCS['nodeK'][1]
        self.stop('K')
        self.wait(lambda: self.seed_tip()[0] >= old+2, 1800)
        self.start('K')
        after = self.wait(lambda: self.follow(('K', 'N'), old+2), 900)
        c.require(d.PROCS['nodeK'][1] != before, 'client process did not change')
        self.row('client.json', 'client_restart_catch_up', detached_count=old, rejoined_count=after[0],
                 advanced_blocks=after[0]-old, changed_process=True, tip_salted=self.tip(after[1]))
        self.announce('caught-up')
        self.steady()
        for name in ('K', 'N'):
            self.stop(name)
        self.row('client-isolation.json', 'launcher_policy', launches=self.launches, refused_before_start=0,
                 adverse_argv_refused=self.adverse_argv, census_samples=self.census_samples,
                 foreign_connections=self.foreign_peak)
        self.announce('done')

    # ---- foreign role ------------------------------------------------------------
    def foreign(self):
        """A --stagenet peer in its own namespace dials the exposed seed and must stay alone."""
        (self.private/'nodes').mkdir(mode=0o700)
        self.argv_controls()
        self.until('client', 'foreign-start', 2*3600)
        self.until('seed', 'foreign-armed', 600)
        self.start('F', fresh=True)
        start = time.monotonic()
        foreign_genesis = self.info('F')[1]
        while time.monotonic()-start < x.FOREIGN_SECONDS:
            height, top, _ = self.info('F')
            c.require(height == 1 and top == foreign_genesis and top != c.GENESIS, 'foreign peer progressed')
            self.census()
            time.sleep(d.budget(5))
        self.stop('F', seal=False)
        self.announce('foreign-done', foreign_genesis=foreign_genesis)
        checked = self.until('seed', 'foreign-checked', 600)
        c.require(checked.get('wrong_network_logged') is True, 'seed did not log the foreign network')
        self.row('foreign.json', 'foreign_peer_isolated', network='stagenet', foreign_count=1,
                 foreign_genesis_differs=True, seconds=x.FOREIGN_SECONDS)
        self.row('foreign-isolation.json', 'launcher_policy', launches=self.launches, refused_before_start=0,
                 adverse_argv_refused=self.adverse_argv, census_samples=self.census_samples,
                 foreign_connections=self.foreign_peak)
        self.announce('done')

    def steady(self):
        uptime = int(td.UPTIME_FILE.read_text())
        c.require(uptime in x.MODES, 'grant-bound uptime mode')
        self.announce('steady')
        generations = {n: d.PROCS[f'node{n}'][1] for n in ('K', 'N')}
        start, start_count = time.time(), self.seed_tip()[0]
        samples = spread = gaps = 0
        while time.time()-start < uptime:
            for attempt in range(4):
                c.require(all(d.PROCS[f'node{n}'][1] == generations[n] and d.PROCS[f'node{n}'][0].poll() is None
                              for n in generations), 'client restarted or exited')
                edges, foreign = self.census()
                c.require(foreign == 0, 'foreign connection')
                seed = self.seed_tip()[0]
                heights = [seed]+[self.info(n)[0] for n in generations]
                if edges == {'K': 1, 'N': 1} and max(heights)-min(heights) <= x.MAX_SPREAD:
                    break
                c.require(attempt < 3, 'steady connectivity/spread fault '+repr((edges, heights)))
                gaps += 1
                time.sleep(d.budget(10))
            spread = max(spread, max(heights)-min(heights))
            samples += 1
            self.heartbeat('steady', max(heights), samples)
            self.say('steady')
            time.sleep(d.budget(max(1, min(x.SAMPLE_SECONDS, uptime-(time.time()-start)))))
        final = self.wait(lambda: self.follow(('K', 'N')), 600)
        blocks = final[0]-start_count
        c.require(blocks >= (30 if uptime == x.UPTIME_SECONDS else 5), 'steady chain did not advance')
        if uptime == x.UPTIME_SECONDS:  # A rehearsal leaves the steady row NOT_RUN.
            self.row('client.json', 'steady_exposed', seconds=int(time.time()-start), samples=samples, faults=0,
                     retried_samples=gaps, max_spread=spread, blocks=blocks, foreign_connections=0,
                     tip_salted=self.tip(final[1]))

    def run(self):
        self.state['phase'] = 'rows'
        self.save()
        dict(seed=self.seed, client=self.client, foreign=self.foreign)[self.role]()
        self.state['phase'] = 'complete'
        self.save()
        return 'complete'


def main():
    os.umask(0o077)
    c.require(d.PRIVATE.is_dir() and d.PRIVATE.stat().st_mode & 0o777 == 0o700, 'persistent root owner-only')
    c.require(EXCHANGE.is_dir() and EXCHANGE.stat().st_mode & 0o777 == 0o700, 'exchange owner-only')
    role = ROLE_FILE.read_text().strip()
    end = int(td.END_FILE.read_text())
    d.DEADLINE = time.monotonic()+(end-time.time())-120
    d.HARD_END = d.DEADLINE+90
    c.require(d.DEADLINE > time.monotonic()+600, 'exposure wall exhausted')
    def stopped(signum, frame):
        raise td.Stop('termination')
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, stopped)
    exposure = None
    try:
        exposure = Exposure(role)
        result = exposure.run()
        exposure.publish(result)
        return 0
    except BaseException as error:
        with contextlib.suppress(Exception):
            td.private_write(d.PRIVATE/'failure-class', (type(error).__name__+'\n').encode())
            td.private_write(d.PRIVATE/'failure-traceback', __import__('traceback').format_exc().encode())
        if exposure is not None:
            with contextlib.suppress(Exception):
                exposure.state['phase'] = 'failed'
                exposure.save()
            with contextlib.suppress(Exception):
                td.private_write(EXCHANGE/(role+'.json'),
                                 (json.dumps(dict(role=role, step='failed', unix=time.time()))+'\n').encode())
        return 1
    finally:
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            signal.signal(sig, signal.SIG_IGN)
        d.DEADLINE = d.HARD_END
        for name, (process, _) in list(d.PROCS.items()):
            if process.poll() is None and exposure is not None and name.startswith('node'):
                with contextlib.suppress(Exception):
                    exposure.stop(name[4:], seal=name != 'nodeF')
            if process.poll() is None:
                with contextlib.suppress(Exception):
                    d.stop(name, graceful=False)
        if exposure is not None:
            with contextlib.suppress(Exception):
                exposure.publish()


if __name__ == '__main__':
    raise SystemExit(main())
