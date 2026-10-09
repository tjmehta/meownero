#!/usr/bin/env python3
"""Native offline preparation check, never a cross-host acceptance witness."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import time
import urllib.error
import urllib.request


def main():
    out = Path('/out')
    token = secrets.token_hex(32)
    env = {**os.environ, 'MEOWNERO_CONTROL_TOKEN': token,
           'MEOWNERO_PEER_DATA': '/out/peer-data',
           'MEOWNERO_DAEMON': os.environ.get('MEOWNERO_DAEMON', '/src/build/vanguard/bin/monerod')}
    rows = []
    with (out / 'supervisor.log').open('wb') as stream:
        proc = subprocess.Popen(['python3', '-B', os.environ.get('MEOWNERO_SUPERVISOR', '/harness/railway-peer.py')],
                                env=env, stdout=stream, stderr=subprocess.STDOUT)

    def call(route, body=None, auth=True):
        req = urllib.request.Request('http://127.0.0.1:8080/' + route,
            json.dumps(body or {}).encode(), {'Content-Type': 'application/json',
            **({'Authorization': 'Bearer ' + token} if auth else {})})
        with urllib.request.urlopen(req, timeout=35) as reply:
            return json.load(reply)

    def denied(route, body, auth, code):
        try:
            call(route, body, auth)
        except urllib.error.HTTPError as err:
            assert err.code == code
            rows.append({'route': route, 'status': err.code, 'body': json.loads(err.read())})
        else:
            raise AssertionError('unauthorized control accepted')

    try:
        end = time.monotonic() + 60
        while True:
            try:
                tip = call('rpc', {'path': 'json_rpc', 'body': {
                    'jsonrpc': '2.0', 'id': '0', 'method': 'get_info'}})
                assert tip.get('result', {}).get('status') == 'OK'
                assert tip['result'].get('top_block_hash') and tip['result']['height'] >= 1
                break
            except (OSError, AssertionError):
                assert proc.poll() is None and time.monotonic() < end
                time.sleep(0.5)
        before = call('state')
        for route in ('state', 'restart', 'stop', 'rpc'):
            denied(route, {}, False, 401)
        denied('rpc', {'path': 'json_rpc', 'body': {'method': 'generateblocks'}}, True, 403)
        denied('rpc', {'path': 'send_raw_transaction', 'body': {}}, True, 403)
        restart = call('restart')
        assert restart['reopened_info']['result']['top_block_hash'] == tip['result']['top_block_hash']
        assert restart['reopened_info']['result']['height'] == tip['result']['height']
        assert 'exit' not in restart['before']['generations'][-1], 'before snapshot changed after stopping'
        while True:
            try:
                after_tip = call('rpc', {'path': 'json_rpc', 'body': {
                    'jsonrpc': '2.0', 'id': '0', 'method': 'get_info'}})
                assert after_tip['result']['status'] == 'OK'
                assert after_tip['result']['top_block_hash'] == tip['result']['top_block_hash']
                assert after_tip['result']['height'] == tip['result']['height']
                break
            except (OSError, KeyError):
                assert proc.poll() is None and time.monotonic() < end
                time.sleep(0.5)
        time.sleep(10)
        after = call('state')
        assert before['process']['exe_sha256'] == after['process']['exe_sha256']
        assert before['process']['start_ticks'] != after['process']['start_ticks']
        final = call('stop')
        proc.wait(30)
        assert proc.returncode == 0 and all(g['exit'] == 0 for g in final['generations'])
        events = dict(line.split() for line in final['memory.events'].splitlines())
        assert int(events['oom']) == int(events['oom_kill']) == 0
        result = {'result': 'PASS_PREPARATION_ONLY', 'scope': 'offline genesis and authenticated control',
                  'before_tip': tip, 'after_tip': after_tip, 'before': before, 'restart': restart,
                  'after': after, 'final': final, 'refusals': rows, 'supervisor_exit': proc.returncode,
                  'supervisor_sha256': hashlib.sha256(Path(os.environ.get('MEOWNERO_SUPERVISOR', '/harness/railway-peer.py')).read_bytes()).hexdigest()}
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(result['result'], 'peak bytes', final['memory.peak'], flush=True)
    finally:
        if proc.poll() is None:
            proc.send_signal(signal.SIGTERM)
            try:
                proc.wait(30)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(5)


if __name__ == '__main__':
    main()
