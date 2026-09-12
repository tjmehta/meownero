#!/usr/bin/env python3
"""Controlled loopback observers; invoked by privacy-test.sh, never on a public net.

All wallets/certificates are disposable. Evidence contains counts/errors only,
never mnemonic, account address, key, RPC password or request body.
"""
from collections import Counter
from contextlib import contextmanager
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import select
import socket
import socketserver
import ssl
import subprocess
import threading
import time
import urllib.error
import urllib.request

WORK = Path('/work')
BIN = '/src/build/release/bin/monero-wallet-rpc'
LAUNCHER = '/harness/privacy-wallet-rpc.py'
DAEMON_PORT, PROXY_PORT, RPC_PORT, REDIRECT_PORT = 19881, 19890, 19800, 19883
events = []
cases = []
mode = 'missing_tx'


def record(name, **observations):
    case = {'name': name, 'result': 'PASS', **observations}
    cases.append(case)
    print(json.dumps(case), flush=True)


def counts():
    return dict(Counter(event['kind'] for event in events))


class Daemon(ThreadingHTTPServer):
    daemon_threads = True

    def get_request(self):
        connection, address = super().get_request()
        events.append({'kind': 'proxied_tcp' if address[0] == '127.0.0.2' else 'direct_tcp'})
        connection.settimeout(3)
        try:
            return tls.wrap_socket(connection, server_side=True), address
        except (OSError, ssl.SSLError):
            connection.close()
            raise


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *args):
        pass

    def do_POST(self):
        body = self.rfile.read(min(int(self.headers.get('Content-Length', '0')), 65536))
        events.append({'kind': 'daemon_http', 'path': self.path, 'mode': mode})
        if self.path == '/gettransactions':
            payload = {'status': 'OK', 'txs': []}
            if mode == 'duplicate_tx':
                payload['txs'] = [{'as_hex': '00'}, {'as_hex': '00'}]
            elif mode == 'invalid_tx':
                payload['txs'] = [{'as_hex': 'zz', 'pruned_as_hex': 'zz'}]
            if mode == 'malformed_json':
                raw = b'{"status":"OK","txs":['
            elif mode == 'redirect':
                self.send_response(302)
                self.send_header('Location', f'http://127.0.0.1:{REDIRECT_PORT}/leak')
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
            else:
                raw = json.dumps(payload).encode()
        elif self.path == '/json_rpc':
            method = json.loads(body).get('method')
            events.append({'kind': 'daemon_method', 'method': method})
            raw = json.dumps({'jsonrpc': '2.0', 'id': '0', 'result':
                             {'status': 'OK', 'version': 196622, 'height': 1}}).encode()
        else:
            raw = b'{"status":"BUSY"}'
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class RedirectTrap(socketserver.BaseRequestHandler):
    def handle(self):
        events.append({'kind': 'redirect_tcp'})


class DnsTrap(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(3)
        try:
            while True:
                size = int.from_bytes(exact(self.request, 2), 'big')
                packet = exact(self.request, size)
                cursor, labels = 12, []
                while packet[cursor]:
                    length = packet[cursor]
                    labels.append(packet[cursor + 1:cursor + 1 + length].decode('ascii'))
                    cursor += 1 + length
                end = cursor + 5
                events.append({'kind': 'dns_query', 'name': '.'.join(labels)})
                # Unsigned NXDOMAIN for synthetic test names; no forwarding.
                response = packet[:2] + b'\x81\x83\x00\x01' + b'\0' * 6 + packet[12:end]
                self.request.sendall(len(response).to_bytes(2, 'big') + response)
        except (OSError, IndexError, UnicodeError):
            return


def exact(connection, size):
    data = b''
    while len(data) < size:
        piece = connection.recv(size - len(data))
        if not piece:
            raise OSError('short SOCKS request')
        data += piece
    return data


def cstring(connection):
    data = b''
    while len(data) < 256:
        char = exact(connection, 1)
        if char == b'\0':
            return data.decode('ascii')
        data += char
    raise OSError('long SOCKS field')


class Socks(socketserver.BaseRequestHandler):
    def handle(self):
        client = self.request
        client.settimeout(3)
        try:
            header = exact(client, 8)
            if header[:2] != b'\x04\x01':
                raise OSError('expected pinned SOCKS4a CONNECT')
            port = int.from_bytes(header[2:4], 'big')
            cstring(client)  # disposable/empty SOCKS user id, never log it
            host = cstring(client) if header[4:7] == b'\0\0\0' else socket.inet_ntoa(header[4:8])
            events.append({'kind': 'socks_connect', 'host': host, 'port': port})
            # No DNS or arbitrary forwarding, even if the test is misconfigured.
            if host not in ('127.0.0.1', 'observer.invalid') or port != DAEMON_PORT:
                raise OSError('test proxy target outside allowlist')
            if self.server.refuse:
                client.sendall(b'\0\x5b' + header[2:8])
                return
            with socket.create_connection(('127.0.0.1', DAEMON_PORT), timeout=3,
                                          source_address=('127.0.0.2', 0)) as upstream:
                client.sendall(b'\0\x5a' + header[2:8])
                while True:
                    ready, _, _ = select.select([client, upstream], [], [], 5)
                    if not ready:
                        return
                    for source in ready:
                        data = source.recv(65536)
                        if not data:
                            return
                        (upstream if source is client else client).sendall(data)
        except OSError:
            return


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True
    refuse = False


def serve(server):
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def request(opener, method, params=None):
    req = urllib.request.Request(f'http://127.0.0.1:{RPC_PORT}/json_rpc',
        json.dumps({'jsonrpc': '2.0', 'id': '0', 'method': method, 'params': params or {}}).encode(),
        {'Content-Type': 'application/json'})
    # Upstream ties digest nonces to a connection; urllib's opener closes the
    # connection after each response. Keep the challenge/reply on one socket,
    # while using the standard library's Digest implementation.
    connection = http.client.HTTPConnection('127.0.0.1', RPC_PORT, timeout=12)
    try:
        headers = {'Content-Type': 'application/json'}
        connection.request('POST', '/json_rpc', req.data, headers)
        response = connection.getresponse()
        body = response.read()
        if response.status == 401 and opener is not None:
            challenge = response.getheader('WWW-Authenticate').split(', Digest ')[0]
            fields = urllib.request.parse_keqv_list(urllib.request.parse_http_list(challenge[7:]))
            headers['Authorization'] = 'Digest ' + opener.get_authorization(req, fields)
            connection.request('POST', '/json_rpc', req.data, headers)
            response = connection.getresponse()
            body = response.read()
        if response.status != 200:
            raise urllib.error.HTTPError(req.full_url, response.status, response.reason, response.headers, None)
        return json.loads(body)
    finally:
        connection.close()


def ok(opener, method, params=None):
    result = request(opener, method, params)
    assert 'result' in result and 'error' not in result, (method, result)
    return result['result']


def failure(opener):
    result = request(opener, 'get_spend_proof', {'txid': '00' * 32, 'message': 'disposable observer test'})
    assert 'error' in result and 'result' not in result, result
    assert ok(opener, 'get_balance')['balance'] == 0
    assert ok(opener, 'get_version')['version'] > 0
    return result['error']


@contextmanager
def wallet(name, direct=False, fingerprint=None, hostname='127.0.0.1'):
    state = WORK / name
    state.mkdir(mode=0o700)
    if not direct:
        plant_configs(state)
    address = f'https://{hostname}:{DAEMON_PORT}'
    if direct:
        argv = [BIN, '--wallet-dir', str(state / 'wallets'), '--rpc-bind-ip', '127.0.0.1',
                '--rpc-bind-port', str(RPC_PORT), '--daemon-address', address, '--untrusted-daemon',
                '--no-dns', '--shared-ringdb-dir', str(state / 'ringdb'), '--max-concurrency', '1',
                '--log-file', str(state / 'wallet-rpc.log'), '--daemon-ssl', 'enabled',
                '--daemon-ssl-allowed-fingerprints', fingerprint or pin]
    else:
        argv = ['python3', '-B', LAUNCHER, '--binary', BIN, '--state-dir', str(state),
                '--rpc-port', str(RPC_PORT), '--proxy', f'127.0.0.1:{PROXY_PORT}',
                '--daemon', address, '--daemon-fingerprint', fingerprint or pin]
    with (state / 'stdout.log').open('w') as log:
        environment = os.environ.copy()
        if name == 'openalias-boundary':
            # Route this boundary probe only to our local resolver using the
            # pinned upstream override; no system DNS or public fallback probe.
            environment['DNS_PUBLIC'] = 'tcp://127.0.0.1'
        process = subprocess.Popen(argv, cwd=state, env=environment, stdout=log, stderr=subprocess.STDOUT)
    try:
        deadline = time.monotonic() + 15
        while True:
            assert process.poll() is None, f'{name} wallet exited; inspect local log'
            try:
                login = (state / f'monero-wallet-rpc.{RPC_PORT}.login').read_text()
                user, password = login.split(':', 1)
                manager = urllib.request.HTTPPasswordMgrWithDefaultRealm()
                manager.add_password(None, f'http://127.0.0.1:{RPC_PORT}', user, password)
                opener = urllib.request.HTTPDigestAuthHandler(manager)
                ok(opener, 'get_version')
                break
            except (OSError, ValueError):
                if time.monotonic() > deadline:
                    raise AssertionError(f'{name}: wallet RPC unavailable')
                time.sleep(0.1)
        try:
            request(None, 'get_version')
            raise AssertionError('unauthenticated wallet RPC accepted')
        except urllib.error.HTTPError as error:
            assert error.code == 401
        assert (state / f'monero-wallet-rpc.{RPC_PORT}.login').stat().st_mode & 0o077 == 0
        ok(opener, 'create_wallet', {'filename': 'disposable', 'password': 'disposable', 'language': 'English'})
        ok(opener, 'auto_refresh', {'enable': False})
        if not direct:
            rejected = request(opener, 'start_mining', {'threads_count': 1})
            assert 'error' in rejected and 'trusted' in rejected['error']['message'].lower(), rejected
        yield opener
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def plant_configs(directory):
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Any implicit loading would either break startup or change observable auth,
    # trust or proxy behavior. Explicit --config-file is refused separately.
    for name in ['monero-wallet-rpc.conf', 'monero-wallet-rpc.cfg', 'wallet-rpc.conf', 'meownero.conf']:
        (directory / name).write_text('disable-rpc-login=1\ntrusted-daemon=1\nproxy=\ndaemon-ssl-allow-any-cert=1\n')


assert Path.home() == Path('/home/ubuntu'), 'runner HOME mount must match immutable image user'
for directory in [Path.home(), Path.home() / '.bitmonero', Path.home() / '.meownero']:
    plant_configs(directory)

subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                '-subj', '/CN=disposable-observer', '-keyout', str(WORK / 'tls.key'),
                '-out', str(WORK / 'tls.pem')], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
der = ssl.PEM_cert_to_DER_cert((WORK / 'tls.pem').read_text())
pin = hashlib.sha256(der).hexdigest()
tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
tls.load_cert_chain(WORK / 'tls.pem', WORK / 'tls.key')
daemon = serve(Daemon(('127.0.0.1', DAEMON_PORT), Handler))
redirect = serve(Server(('127.0.0.1', REDIRECT_PORT), RedirectTrap))
proxy_server = None
dns_server = None
reserved = socket.socket()
reserved.bind(('127.0.0.1', PROXY_PORT))  # bound but not listening: immediate refusal
started = time.monotonic()
try:
    base = ['python3', '-B', LAUNCHER, '--binary', BIN, '--state-dir', str(WORK / 'refused'),
            '--rpc-port', str(RPC_PORT), '--proxy', f'127.0.0.1:{PROXY_PORT}',
            '--daemon', f'https://127.0.0.1:{DAEMON_PORT}', '--daemon-fingerprint', pin]
    invalid = [(['--proxy', ''], 'empty_proxy'), (['--proxy', 'localhost:9050'], 'proxy_hostname'),
               (['--proxy', '192.0.2.1:9050'], 'nonlocal_proxy'), (['--proxy', '127.0.0.1:0'], 'zero_proxy_port'),
               (['--daemon', f'http://127.0.0.1:{DAEMON_PORT}'], 'cleartext_clearnet'),
               (['--daemon-fingerprint', ''], 'missing_pin'), (['--daemon-fingerprint', 'xx'], 'bad_pin'),
               (['--daemon', 'https://user:pass@observer.invalid:18081'], 'url_credentials'),
               (['--daemon', 'https://observer.invalid:18081/path'], 'url_path'),
               (['--daemon', 'https://observer.invalid:18081\n'], 'url_whitespace'),
               (['--daemon', 'http://short.onion:18081'], 'bad_onion'),
               (['--trusted-daemon'], 'trust_override'), (['--config-file', '/dev/null'], 'config_override'),
               (['--disable-rpc-login'], 'auth_override'), (['--pro', '127.0.0.1:9050'], 'abbreviated_override')]
    for extra, name in invalid:
        result = subprocess.run(base + extra, capture_output=True, timeout=3)
        assert result.returncode == 2, (name, result.returncode)
        assert not (WORK / 'refused').exists(), name
        record('refusal_' + name, exit_code=result.returncode)
    assert not events

    with wallet('direct-control', direct=True) as rpc:
        failure(rpc)
        assert counts().get('direct_tcp', 0) > 0
        assert any(e.get('path') == '/gettransactions' for e in events)
        record('direct_positive_control', counts=counts())
    events.clear()
    with wallet('dead-proxy') as rpc:
        errors = [failure(rpc) for _ in range(3)]
        assert not events, events
        # Authenticated controller changes daemon; absent per-daemon proxy must
        # not erase the startup global proxy.
        ok(rpc, 'set_daemon', {'address': f'https://127.0.0.1:{DAEMON_PORT}', 'trusted': False,
                             'ssl_support': 'enabled', 'ssl_allowed_fingerprints': [pin]})
        errors.append(failure(rpc))
        assert not events, events
        rejected = request(rpc, 'set_daemon', {'address': f'https://127.0.0.1:{DAEMON_PORT}',
                                             'proxy': '127.0.0.1:19999'})
        assert 'error' in rejected
        record('dead_proxy_and_set_daemon', attempts=4, direct_connections=0,
               errors=errors, proxy_override_error=rejected['error'])
        record('planted_default_configs_ignored', auth_required=True, untrusted_daemon=True,
               direct_connections=0, locations=['working directory', 'HOME', 'HOME/.bitmonero', 'HOME/.meownero'])
    reserved.close()
    proxy_server = serve(Server(('127.0.0.1', PROXY_PORT), Socks))
    events.clear()
    with wallet('live-proxy') as rpc:
        for attack in ['missing_tx', 'duplicate_tx', 'invalid_tx', 'malformed_json', 'redirect']:
            mode = attack
            before = len(events)
            error = failure(rpc)
            observed = events[before:]
            assert any(e.get('path') == '/gettransactions' and e.get('mode') == attack for e in observed)
            assert not counts().get('direct_tcp') and not counts().get('redirect_tcp')
            record('malicious_' + attack, error=error, wallet_alive=True, balance_atomic=0,
                   direct_connections=0, redirect_connections=0)
        assert counts().get('socks_connect', 0) > 0 and counts().get('proxied_tcp', 0) > 0
        record('live_proxy_control', counts=counts())
        # The authenticated controller can relax trust and TLS at runtime. Record
        # that boundary explicitly, then restore verified TLS before any request.
        ok(rpc, 'set_daemon', {'address': f'http://127.0.0.1:{DAEMON_PORT}', 'trusted': True,
                             'ssl_support': 'disabled'})
        record('runtime_controller_can_change_trust_and_tls', set_daemon_accepted=True,
               scope='startup TLS/untrusted defaults are not an RPC authorization boundary')
        # Failure after a working connection has been established.
        proxy_server.refuse = True
        ok(rpc, 'set_daemon', {'address': f'https://127.0.0.1:{DAEMON_PORT}', 'trusted': False,
                             'ssl_support': 'enabled', 'ssl_allowed_fingerprints': [pin]})
        events.clear()
        error = failure(rpc)
        assert counts().get('socks_connect', 0) > 0 and not counts().get('proxied_tcp')
        assert not counts().get('direct_tcp')
        record('proxy_refuses_after_success', counts=counts(), error=error)
        proxy_server.refuse = False
    events.clear()
    mode = 'missing_tx'
    with wallet('wrong-tls-pin', fingerprint='00' * 32) as rpc:
        error = failure(rpc)
        assert counts().get('proxied_tcp', 0) > 0 and not counts().get('daemon_http')
        assert not counts().get('direct_tcp')
        record('tls_pin_mismatch', counts=counts(), error=error, application_requests=0)
    events.clear()
    with wallet('proxy-dns', hostname='observer.invalid') as rpc:
        failure(rpc)
        assert any(e.get('host') == 'observer.invalid' for e in events)
        assert any(e.get('path') == '/gettransactions' for e in events)
        assert not counts().get('direct_tcp')
        record('hostname_sent_to_proxy', counts=counts(), host='observer.invalid')
    events.clear()
    dns_server = serve(Server(('127.0.0.1', 53), DnsTrap))
    with wallet('openalias-boundary') as rpc:
        before = counts().get('dns_query', 0)
        result = ok(rpc, 'validate_address', {'address': 'privacy-observer.example.com',
                                            'allow_openalias': False})
        assert not result['valid'] and counts().get('dns_query', 0) == before
        result = ok(rpc, 'validate_address', {'address': 'privacy-observer.example.com',
                                            'allow_openalias': True})
        assert not result['valid']
        assert any(e.get('name') == 'privacy-observer.example.com' for e in events)
        record('openalias_bypasses_no_dns_flag', dns_queries=counts().get('dns_query'),
               controlled_resolver='127.0.0.1:53 TCP', no_dns_flag_present=True,
               allow_openalias_false_queries=0,
               scope='known RPC-controller boundary, not a claim of process-wide DNS isolation')
    summary = {'result': 'PASS', 'cases': cases, 'duration_seconds': round(time.monotonic() - started, 3),
               'scope': 'pinned real wallet RPC, sequential disposable wallets, loopback SOCKS4a/TLS observers; no Tor network, daemon P2P or actual payment',
               'memory_limit_bytes': 512 * 1024 * 1024}
    memory_peak = Path('/sys/fs/cgroup/memory.peak')
    if memory_peak.exists():
        summary['cgroup_memory_peak_bytes'] = int(memory_peak.read_text())
    (WORK / 'result.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({key: value for key, value in summary.items() if key != 'cases'}))
finally:
    reserved.close()
    for server in [dns_server, proxy_server, redirect, daemon]:
        if server:
            server.shutdown()
            server.server_close()
