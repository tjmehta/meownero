#!/usr/bin/env python3
"""Finite validation-only regtest peer; authenticated read-only control."""
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import threading
import time
import urllib.request

METHODS = {'get_last_block_header', 'get_block', 'get_connections', 'get_info'}
ENDPOINTS = {'get_transactions', 'get_transaction_pool'}
TOKEN = os.environ.get('MEOWNERO_CONTROL_TOKEN', '')
ROOT = Path(os.environ.get('MEOWNERO_PEER_DATA', '/data'))
BIN = Path(os.environ.get('MEOWNERO_DAEMON', '/app/monerod'))
PROC = None
GENERATIONS = []
GUARD = threading.Lock()
STOP = threading.Event()


def metrics():
    result = {'architecture': platform.machine(), 'generations': GENERATIONS.copy()}
    for filename in ('memory.current', 'memory.peak', 'memory.max', 'memory.events', 'cpu.stat'):
        p = Path('/sys/fs/cgroup') / filename
        if p.exists():
            result[filename] = p.read_text().strip()
    result['disk_bytes'] = sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file())
    if PROC and PROC.poll() is None:
        p = Path(f'/proc/{PROC.pid}')
        result['process'] = {
            'pid': PROC.pid, 'exe_sha256': hashlib.sha256((p / 'exe').read_bytes()).hexdigest(),
            'start_ticks': (p / 'stat').read_text().rsplit(')', 1)[1].split()[19],
            'command': (p / 'cmdline').read_bytes().decode().split('\0')[:-1],
            'rss_kib': next(int(row.split()[1]) for row in (p / 'status').read_text().splitlines()
                            if row.startswith('VmRSS:'))}
    result['monotonic_s'] = time.monotonic()
    return result


def start():
    global PROC
    args = [str(BIN), '--data-dir', str(ROOT / 'chain'), '--regtest', '--keep-fakechain',
            '--fixed-difficulty', '1', '--non-interactive', '--no-igd', '--allow-local-ip',
            '--disable-dns-checkpoints', '--check-updates', 'disabled', '--hide-my-port',
            '--max-concurrency', '1', '--no-zmq', '--rpc-ssl', 'disabled',
            '--p2p-bind-ip', '0.0.0.0', '--p2p-bind-port', '19080',
            '--rpc-bind-ip', '127.0.0.1', '--rpc-bind-port', '19081',
            '--add-exclusive-node', '127.0.0.1:1', '--log-level', '0',
            '--log-file', str(ROOT / 'daemon.log')]
    with (ROOT / 'daemon.stdout').open('ab') as stream:
        PROC = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=stream, stderr=stream)
    GENERATIONS.append({'pid': PROC.pid, 'started_s': time.monotonic(), 'command': args})


def stop():
    if PROC and PROC.poll() is None:
        PROC.send_signal(signal.SIGINT)
        try:
            PROC.wait(20)
        except subprocess.TimeoutExpired:
            PROC.kill()
            PROC.wait(5)
    if PROC:
        GENERATIONS[-1]['exit'] = PROC.returncode
        GENERATIONS[-1]['ended_s'] = time.monotonic()


class Control(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Never log authentication headers or request bodies.

    def reply(self, code, value):
        raw = json.dumps(value).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        if not hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + TOKEN):
            self.reply(401, {'error': 'unauthorized'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 65536:
                self.reply(413, {'error': 'bounded body required'})
                return
            body = json.loads(self.rfile.read(length))
            with GUARD:
                if self.path == '/state':
                    value = metrics()
                elif self.path == '/restart':
                    before = metrics()
                    stop()
                    start()
                    value = {'before': before, 'after': metrics()}
                elif self.path == '/stop':
                    stop()
                    value = metrics()
                    STOP.set()
                elif self.path == '/rpc':
                    path = body.get('path')
                    payload = body.get('body', {})
                    if not ((path == 'json_rpc' and payload.get('method') in METHODS)
                            or path in ENDPOINTS):
                        self.reply(403, {'error': 'read-only method required'})
                        return
                    req = urllib.request.Request('http://127.0.0.1:19081/' + path,
                        json.dumps(payload).encode(), {'Content-Type': 'application/json'})
                    with urllib.request.urlopen(req, timeout=30) as response:
                        value = json.load(response)
                else:
                    self.reply(404, {'error': 'unknown route'})
                    return
            self.reply(200, value)
        except (ValueError, TypeError, OSError, subprocess.SubprocessError):
            self.reply(503, {'error': 'peer unavailable'})


def main():
    if len(TOKEN) < 32:
        raise SystemExit('A runtime control secret of at least 32 characters is required')
    ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.umask(0o077)
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: STOP.set())
    server = HTTPServer(('0.0.0.0', int(os.environ.get('PORT', '8080'))), Control)
    server.timeout = 0.5
    started = time.monotonic()
    start()
    try:
        while not STOP.is_set() and time.monotonic() - started < 1800 and PROC.poll() is None:
            server.handle_request()
    finally:
        with GUARD:
            stop()
            print(json.dumps({'event': 'peer_shutdown', 'metrics': metrics()}), flush=True)
        server.server_close()


if __name__ == '__main__':
    main()
