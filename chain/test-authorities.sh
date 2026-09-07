#!/usr/bin/env bash
# Isolated-container checks for disabled inherited authorities and donations.
set -euo pipefail
SRC=$(realpath "$1")
docker run --rm -i --network none -v "$SRC:/src:ro" -w /tmp \
  "${MEOW_BUILDER_IMAGE:-meownero-chain-builder}" python3 - <<'PY'
import json
import pathlib
import subprocess
import tempfile
import time
import urllib.request

BIN = pathlib.Path('/src/build/release/bin')

# An offline failure alone would not prove inherited endpoint removal.
for relative, forbidden in [
    ('src/common/updates.cpp', ['updates.moneropulse.', 'downloads.getmonero.org', 'updates.getmonero.org']),
    ('src/p2p/net_node.inl', ['blocklist.moneropulse.']),
    ('src/simplewallet/simplewallet.cpp', ['MONERO_DONATION_ADDR', 'donate.getmonero.org']),
]:
    source = (pathlib.Path('/src') / relative).read_text()
    assert not any(value in source for value in forbidden), relative

def request(path, body):
    req = urllib.request.Request('http://127.0.0.1:28081/' + path,
        json.dumps(body).encode(), {'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=5) as response:
        return json.load(response)

def rpc(method, params):
    result = request('json_rpc', {'jsonrpc': '2.0', 'id': '0', 'method': method, 'params': params})
    assert 'error' not in result, result
    return result['result']

with tempfile.TemporaryDirectory(prefix='meow-authorities-') as work:
    root = pathlib.Path(work)
    with (root / 'daemon.log').open('w+') as log:
        daemon = subprocess.Popen([
            str(BIN / 'monerod'), '--data-dir', str(root / 'chain'), '--no-igd',
            '--log-level', '1', '--log-file', str(root / 'daemon-detail.log'),
            '--non-interactive', '--p2p-bind-ip', '127.0.0.1', '--p2p-bind-port', '28080',
            '--rpc-bind-ip', '127.0.0.1', '--rpc-bind-port', '28081',
            '--zmq-rpc-bind-ip', '127.0.0.1', '--zmq-rpc-bind-port', '28082',
            '--out-peers', '0', '--in-peers', '0', '--disable-dns-checkpoints',
            '--check-updates', 'download', '--enable-dns-blocklist',
        ], stdout=log, stderr=subprocess.STDOUT)
        try:
            for attempt in range(60):
                assert daemon.poll() is None, 'daemon exited before RPC became ready'
                try:
                    rpc('get_info', {})
                    break
                except (OSError, ValueError):
                    time.sleep(0.5)
            else:
                raise AssertionError('daemon RPC startup timeout')
            for command in ['check', 'download', 'update']:
                result = request('update', {'command': command, 'path': str(root / 'download')})
                assert result['status'] == 'Error checking for updates', result
                assert not result['update'], result
                assert not result.get('auto_uri') and not result.get('user_uri'), result
                assert not (root / 'download').exists()
            assert rpc('set_bans', {'bans': [{'host': '192.0.2.1', 'ban': True, 'seconds': 60}]})['status'] == 'OK'
            assert any(ban['host'] == '192.0.2.1' for ban in rpc('get_bans', {})['bans'])
        finally:
            daemon.terminate()
            try:
                daemon.wait(timeout=20)
            except subprocess.TimeoutExpired:
                daemon.kill()
                daemon.wait()
        log.seek(0)
        logs = log.read() + (root / 'daemon-detail.log').read_text()
        assert 'DNS blocklists are disabled: no Meownero blocklist authority is configured' in logs, logs
    print('PASS: explicit RPC update modes fail closed; DNS-blocklist opt-in warns; local bans work')

    # Disposable, unfunded test wallets only. Seed output stays in memory, not logs.
    for network in [[], ['--testnet'], ['--stagenet']]:
        result = subprocess.run([
            str(BIN / 'monero-wallet-cli'), '--generate-new-wallet', str(root / ('wallet' + ''.join(network))),
            '--password', '', '--mnemonic-language', 'English', '--offline',
            '--log-file', str(root / 'wallet.log'), *network, 'donate', '1',
        ], input='', text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
        assert result.returncode == 0, 'wallet command failed'
        assert 'Donations are disabled: no Meownero donation address is configured.' in result.stdout
    print('PASS: donate is disabled on all three networks; no transfers or external networking')
PY
