"""Observed wallet<->daemon transport metadata + one denial/recovery correlation.

Runs the real selected daemon and wallet on an isolated fixed-difficulty chain
(--network none, disposable keys) with a RECORDING FORWARDING PROXY on the
wallet's configured daemon boundary. The wallet is pointed at the proxy with an
EXPLICIT --untrusted-daemon (a local daemon is auto-trusted otherwise), and that
untrusted mode is verified at runtime via a trusted-daemon-gated RPC. The proxy is
a stand-in for an on-path observer / the node operator: it records the request
metadata the node actually sees (HTTP method, path, body size, timing, client
connection) while transparently forwarding to the daemon, then injects ONE denied
response and classifies the wallet's OBSERVABLE reaction strictly from evidence
(the raw RPC reply plus the recorded post-denial retries) before asserting
recovery. It never asserts an error that did not actually surface.

This is execution evidence for the "intended wallet transport / observer metadata"
acceptance item, NOT an anonymity claim and NOT a Tor/I2P deployment. Observed
exposure is separated from hypotheses in result.json. Recordings are metadata
only: method, path, byte counts, sha256 of the body, timing. No request/response
body bytes, mnemonic, key, or address are stored; the harness asserts this.
"""
from collections import Counter
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import subprocess
import threading
import time
import urllib.error
import urllib.request

BIN = Path('/src/build/release/bin')
WORK = Path('/work')
COIN = 1_000_000_000_000
EXPECTED_REWARD = 9 * COIN
DAEMON_RPC = 19081          # wallet never talks here directly
PROXY_PORT = 19092          # the wallet's configured daemon boundary
processes = []

# Proxy shared state (single wallet, single proxy thread pool).
records = []                # metadata-only request records
record_lock = threading.Lock()
deny_next_bin = threading.Event()   # one-shot: deny the next .bin request (a refresh call)
denied_paths = []
denied_indices = []                 # index into records[] of each denied request


def request(port, path, body):
    req = urllib.request.Request(f'http://127.0.0.1:{port}/{path}',
                                 json.dumps(body).encode(), {'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=120) as response:
        result = json.load(response)
    assert 'error' not in result, (path, result.get('error'))
    return result


def rpc(port, method, params=None):
    return request(port, 'json_rpc', {'jsonrpc': '2.0', 'id': '0',
                                      'method': method, 'params': params or {}})['result']


def raw_json_rpc(port, method, params=None):
    """Return (envelope, transport_exception_name) without asserting.

    `envelope` is the full parsed JSON-RPC reply (it may carry 'result' OR
    'error'); a genuine RPC/daemon error is therefore captured as evidence
    instead of being masked by an assertion. `transport_exception_name` is set
    only when no HTTP reply was received at all (connection dropped/refused).
    """
    body = {'jsonrpc': '2.0', 'id': '0', 'method': method, 'params': params or {}}
    req = urllib.request.Request(f'http://127.0.0.1:{port}/json_rpc',
                                 json.dumps(body).encode(), {'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            return json.load(response), None
    except urllib.error.HTTPError as exc:          # HTTP reply arrived with error status
        try:
            return json.load(exc), None
        except (ValueError, OSError):
            return {'http_status': exc.code}, None
    except (urllib.error.URLError, OSError) as exc:  # no usable reply at all
        return None, type(exc).__name__


def wait_until(check, label, seconds=240):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        assert all(p.poll() is None for p in processes), 'a test process exited early'
        try:
            if check():
                return
        except (OSError, ValueError, AssertionError):
            pass
        time.sleep(0.5)
    raise AssertionError(f'timeout: {label}')


def start(binary, args, name):
    with (WORK / f'{name}.stdout.log').open('w') as log:
        process = subprocess.Popen([str(BIN / binary), *args], stdout=log, stderr=subprocess.STDOUT)
    processes.append(process)
    return process


def daemon_height():
    return rpc(DAEMON_RPC, 'get_info')['height']


def mine_blocks(address, count, label):
    target = daemon_height() + count

    def begin():
        r = request(DAEMON_RPC, 'start_mining', {'miner_address': address, 'threads_count': 1,
                    'do_background_mining': False, 'ignore_battery': True})
        assert r['status'] == 'OK', r
        return True
    wait_until(begin, f'start mining ({label})', seconds=60)
    wait_until(lambda: daemon_height() >= target, label, seconds=360)
    assert request(DAEMON_RPC, 'stop_mining', {})['status'] == 'OK'


# --- Recording forwarding proxy: wallet -> (record) -> daemon ---------------
class Proxy(ThreadingHTTPServer):
    daemon_threads = True


class ProxyHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, *args):
        pass

    def _handle(self, method):
        length = int(self.headers.get('Content-Length', '0') or '0')
        body = self.rfile.read(length) if length else b''
        path = self.path
        # Metadata only: never store body bytes; a hash lets a reviewer prove
        # two captures are the same request class without revealing contents.
        with record_lock:
            idx = len(records)
            records.append({'method': method, 'path': path, 'req_bytes': length,
                            'req_sha256': hashlib.sha256(body).hexdigest()[:16],
                            'client': self.client_address[0],
                            't': round(time.monotonic(), 4)})
        # One-shot injected denial: refuse the next binary sync call as an
        # untrusted/unavailable node would, to observe wallet recovery.
        if path.endswith('.bin') and deny_next_bin.is_set():
            deny_next_bin.clear()
            denied_paths.append(path)
            denied_indices.append(idx)
            payload = b'{"status":"Failed","untrusted":true}'
            self.send_response(503)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        try:
            upstream = http.client.HTTPConnection('127.0.0.1', DAEMON_RPC, timeout=60)
            headers = {'Content-Type': self.headers.get('Content-Type', 'application/octet-stream')}
            upstream.request(method, path, body, headers)
            response = upstream.getresponse()
            data = response.read()
            self.send_response(response.status)
            self.send_header('Content-Type',
                             response.getheader('Content-Type', 'application/octet-stream'))
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            upstream.close()
        except OSError:
            self.close_connection = True

    def do_POST(self):
        self._handle('POST')

    def do_GET(self):
        self._handle('GET')


def snapshot(port):
    rpc(port, 'refresh', {'start_height': 0})
    return rpc(port, 'get_balance')['balance']


def scan_for_secrets():
    """Prove the transport recording holds only sanitized metadata: no 25-word
    mnemonic and no raw 32-byte key/seed hex. Also assert no mnemonic phrase
    leaked into any captured error/log text. Public tx ids in the case results
    are 64-hex by nature and are not secret, so the strict hex rule stays scoped
    to the recording, not to those identifiers."""
    records_blob = json.dumps(records)
    assert not re.search(r'(?:\b[a-z]+\b[ ]){24}[a-z]+', records_blob), 'mnemonic-like text in records'
    assert not re.search(r'\b[0-9a-f]{64}\b', records_blob), 'raw 32-byte hex (key/seed-like) in records'
    assert not re.search(r'(?:\b[a-z]+\b[ ]){24}[a-z]+', json.dumps(cases)), 'mnemonic-like text in cases'
    return True


cases = []


def record(name, **fields):
    row = {'case': name, 'result': 'PASS', **fields}
    cases.append(row)
    print(json.dumps(row), flush=True)


try:
    start('monerod', ['--data-dir', str(WORK / 'chain'), '--non-interactive', '--no-igd', '--offline',
          '--p2p-bind-ip', '127.0.0.1', '--p2p-bind-port', '19080', '--rpc-bind-ip', '127.0.0.1',
          '--rpc-bind-port', str(DAEMON_RPC), '--zmq-rpc-bind-ip', '127.0.0.1',
          '--out-peers', '0', '--in-peers', '0', '--disable-dns-checkpoints',
          '--check-updates', 'disabled', '--fixed-difficulty', '1',
          '--log-file', str(WORK / 'daemon.log')], 'daemon')
    wait_until(lambda: daemon_height() == 1, 'daemon genesis')

    proxy = Proxy(('127.0.0.1', PROXY_PORT), ProxyHandler)
    threading.Thread(target=proxy.serve_forever, daemon=True).start()

    # Intended remote-node boundary: wallet talks to the proxy as an UNTRUSTED
    # daemon. --untrusted-daemon is EXPLICIT: for a local (127.0.0.1) daemon,
    # wallet2.cpp make_basic auto-sets trusted_daemon=true unless a trust flag is
    # given (see the "Daemon is local, assuming trusted" path), so merely omitting
    # --trusted-daemon would leave the wallet TRUSTED. --log-level 1 captures that
    # decision line for corroboration; runtime mode is verified below.
    wdir = WORK / 'A'
    wdir.mkdir()
    start('monero-wallet-rpc', ['--rpc-bind-ip', '127.0.0.1', '--rpc-bind-port', '19100',
          '--disable-rpc-login', '--untrusted-daemon', '--log-level', '1',
          '--wallet-dir', str(wdir),
          '--daemon-address', f'http://127.0.0.1:{PROXY_PORT}',
          '--log-file', str(WORK / 'A.log')], 'wallet-A')
    wait_until(lambda: rpc(19100, 'get_version')['version'] > 0, 'wallet RPC')
    rpc(19100, 'create_wallet', {'filename': 'A', 'password': 'disposable', 'language': 'English'})
    addr = rpc(19100, 'get_address')['address']
    assert addr.startswith('M')

    # 0) Verify ACTUAL trust mode at runtime, not just the flag. rescan_spent is
    #    gated by is_trusted_daemon() in wallet_rpc_server.cpp::on_rescan_spent and
    #    an untrusted wallet MUST reject it before touching the daemon. This ties
    #    the --untrusted-daemon flag to the observed mode with version-specific
    #    source/runtime evidence.
    probe, probe_exc = raw_json_rpc(19100, 'rescan_spent')
    assert probe_exc is None, ('rescan_spent probe had no reply', probe_exc)
    assert isinstance(probe, dict) and 'error' in probe, \
        ('rescan_spent was NOT rejected; wallet is running trusted, not untrusted', probe)
    probe_msg = probe['error'].get('message', '')
    assert 'requires a trusted daemon' in probe_msg, ('unexpected rescan_spent error', probe['error'])
    log_text = (WORK / 'A.log').read_text(errors='ignore') if (WORK / 'A.log').exists() else ''
    record('untrusted_mode_verified', probe_rpc='rescan_spent',
           rejected_code=probe['error'].get('code'), rejected_message=probe_msg,
           auto_local_trust_log_present=('assuming trusted' in log_text),
           source='wallet_rpc_server.cpp on_rescan_spent is_trusted_daemon() gate; '
                  'wallet2.cpp make_basic --untrusted-daemon vs local-address auto-trust')

    # Fund by mining directly at the daemon (operator action, not wallet transport).
    mine_blocks(addr, 90, '90 coinbase blocks')
    height = daemon_height()
    mined = height - 1

    # 1) Normal sync over the boundary: capture what the node observes on refresh.
    before = len(records)
    bal = snapshot(19100)
    assert bal == mined * EXPECTED_REWARD, (bal, mined * EXPECTED_REWARD)
    sync_records = records[before:]
    sync_paths = Counter(r['path'] for r in sync_records)
    record('observed_sync', balance_atomic=bal, requests=len(sync_records),
           distinct_paths=sorted(sync_paths), path_histogram=dict(sync_paths))

    # 2) Spend over the boundary: capture decoy fetch + first-relay submission.
    before = len(records)
    sent = rpc(19100, 'transfer', {'destinations': [{'amount': 5 * COIN, 'address': addr}],
               'get_tx_key': True})
    txid, fee = sent['tx_hash'], sent['fee']
    spend_records = records[before:]
    spend_paths = Counter(r['path'] for r in spend_records)
    submit = [r for r in spend_records if 'sendrawtransaction' in r['path']]
    outs = [r for r in spend_records if 'get_outs' in r['path'] or 'get_o_indexes' in r['path']]
    assert submit, 'no sendrawtransaction seen at the node boundary'
    record('observed_spend', txid=txid, fee_atomic=fee, requests=len(spend_records),
           distinct_paths=sorted(spend_paths),
           first_relay_submissions=len(submit), decoy_or_index_fetches=len(outs))
    mine_blocks(addr, 15, 'confirm spend')

    # 3) One justified denial correlated with wallet recovery. The proxy really
    #    returns 503 for one .bin sync call; the wallet's OBSERVABLE reaction is
    #    then classified strictly from evidence (raw RPC envelope + proxy records).
    #    No error is asserted unless one actually surfaced.
    deny_next_bin.set()
    refresh_reply, transport_exc = raw_json_rpc(19100, 'refresh', {'start_height': 0})
    assert denied_paths, 'the injected denial was never exercised'
    assert all(p.poll() is None for p in processes), 'wallet or daemon crashed on the denial'

    post_denial = records[denied_indices[0] + 1:]
    retry_bins = [r['path'] for r in post_denial if r['path'].endswith('.bin')]
    if transport_exc is not None:
        # No usable HTTP reply reached the RPC client.
        observed = {'mode': 'transport_error_to_client', 'exception': transport_exc,
                    'post_denial_bin_retries': retry_bins}
    elif isinstance(refresh_reply, dict) and 'error' in refresh_reply:
        # The daemon failure surfaced to the wallet RPC client: capture it verbatim.
        err = refresh_reply['error']
        observed = {'mode': 'surfaced_daemon_error',
                    'rpc_error_code': err.get('code'), 'rpc_error_message': err.get('message'),
                    'post_denial_bin_retries': retry_bins}
    else:
        # refresh returned a normal result: the denial did NOT surface to the RPC
        # client. That is only truthful as "recovery" if the node actually saw the
        # wallet re-request the sync after the 503 — assert that evidence exists.
        assert retry_bins, ('refresh returned no error yet no post-denial .bin retry '
                            'was recorded at the node; cannot substantiate recovery')
        observed = {'mode': 'transparent_retry_no_client_error',
                    'post_denial_bin_retries': retry_bins}

    # Recovery: proxy forwards again; consecutive refreshes must converge, and the
    # balance equals coinbase*reward (self-send + self-mined fee net to zero).
    recovered = snapshot(19100)
    again = snapshot(19100)
    assert recovered == again, ('unstable recovery', recovered, again)
    coinbase = daemon_height() - 1
    assert recovered == coinbase * EXPECTED_REWARD, (recovered, coinbase * EXPECTED_REWARD)
    record('denial_and_recovery', denied_path=denied_paths[0],
           injected_response='503 {"status":"Failed","untrusted":true} on one .bin sync call',
           wallet_observed=observed, recovered_balance_atomic=recovered,
           recovery='two consecutive refreshes converged to coinbase*reward after the node stopped refusing')

    # 4) Sanitation proof + exposure summary.
    assert scan_for_secrets()
    all_paths = Counter(r['path'] for r in records)
    clients = sorted({r['client'] for r in records})
    record('recording_sanitized', total_requests=len(records),
           distinct_paths=sorted(all_paths), observed_client_sources=clients,
           stored_fields=['method', 'path', 'req_bytes', 'req_sha256', 'client', 't'])

    summary = {
        'result': 'PASS',
        'cases': cases,
        'boundary': 'wallet (--untrusted-daemon, runtime-verified) -> recording forwarding '
                    'proxy (untrusted remote node) -> daemon; --network none',
        'trust_mode': {
            'flag': '--untrusted-daemon (explicit)',
            'runtime_verified': 'rescan_spent rejected with "This command requires a trusted daemon."',
            'note': 'wallet2.cpp make_basic auto-trusts a local (127.0.0.1) daemon unless a trust '
                    'flag is given, so the explicit flag is required for untrusted mode.',
        },
        'observed_exposure': {
            'note': 'Metadata the node/on-path observer actually saw in this run.',
            'request_paths': sorted(all_paths),
            'path_histogram': dict(all_paths),
            'total_requests': len(records),
            'client_sources_seen_by_proxy': clients,
            'first_relay_origin_recorded': True,
        },
        'hypotheses_not_tested': [
            'On a real network the node sees the operator public IP, not 127.0.0.1, '
            'unless Tor/I2P is used (not deployed or tested here).',
            'Repeated get_outs/get_transactions patterns narrow wallet-owned outputs by '
            'intersection over time; not quantified here.',
            'Timing/traffic-analysis resistance and Dandelion++ relay origin hiding are '
            'not evaluated.',
        ],
        'sanitization': 'records hold method/path/size/sha256/client/time only; no bodies, '
                        'mnemonic, keys, or addresses; asserted by scan_for_secrets().',
        'scope': 'selected 9/90 real daemon+wallet, --untrusted-daemon (runtime-verified); '
                 'isolated fixed-difficulty chain; disposable keys; one evidence-classified '
                 'denial/recovery correlation; not an anonymity or Tor/I2P test.',
    }
    (WORK / 'result.json').write_text(json.dumps(summary, indent=2) + '\n')
    # Durable metadata-only capture for the reviewer.
    (WORK / 'transport-records.json').write_text(json.dumps(records, indent=2) + '\n')
    print(json.dumps(summary, indent=2))
finally:
    try:
        proxy.shutdown()
    except Exception:
        pass
    for process in reversed(processes):
        process.terminate()
    for process in reversed(processes):
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
