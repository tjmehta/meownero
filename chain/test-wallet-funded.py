"""Funded private-devnet wallet integration; run inside the builder with --network none.

Extends test-seed-recovery.py (coinbase receive + restore + reopen) to the
untested M1/M2 wallet gaps: an actual send between wallets, restore-then-spend,
outgoing-metadata recovery from a chain rescan, fee and atomic-unit arithmetic,
and an aggregate cross-check of the real daemon's coinbase/fee tally against the
wallets' own fee reports.

Every key is a disposable test key on an isolated fixed-difficulty chain with no
peers and no external networking (the container has --network none). Evidence
records amounts in atomic units and counts only; it never copies a mnemonic,
address, spend key, RPC password or request body. This is not a transport-privacy
(anonymity) test: the wallet<->daemon channel is trusted loopback HTTP. See the
observer note emitted in result.json and the accompanying research doc.
"""
import json
from pathlib import Path
import subprocess
import time
import urllib.request

BIN = Path('/src/build/release/bin')
WORK = Path('/work')
COIN = 1_000_000_000_000            # inherited atomic precision, 12 dp
UNLOCK_WINDOW = 60                  # CRYPTONOTE_MINED_MONEY_UNLOCK_WINDOW
EXPECTED_REWARD = 9 * COIN         # selected 9/90 profile subsidy; asserted, not assumed blindly
DAEMON_RPC = 19081

processes = []


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
    """Solo-mine `count` blocks to `address` on the isolated chain."""
    start_height = daemon_height()
    target = start_height + count

    def begin():
        result = request(DAEMON_RPC, 'start_mining', {'miner_address': address, 'threads_count': 1,
                         'do_background_mining': False, 'ignore_battery': True})
        assert result['status'] == 'OK', result   # 'BUSY' while the core is still initialising
        return True
    wait_until(begin, f'start mining ({label})', seconds=60)
    wait_until(lambda: daemon_height() >= target, label, seconds=360)
    assert request(DAEMON_RPC, 'stop_mining', {})['status'] == 'OK'
    return daemon_height()


def refresh(port):
    rpc(port, 'refresh', {'start_height': 0})


def balances(port):
    refresh(port)
    b = rpc(port, 'get_balance')
    return b['balance'], b['unlocked_balance']


def transfers(port, direction):
    refresh(port)
    key = 'in' if direction == 'in' else 'out'
    return rpc(port, 'get_transfers', {key: True}).get(key, [])


def in_history(port):
    rows = transfers(port, 'in')
    return sorted((t['txid'], t['height'], t['amount'], t['type']) for t in rows)


def record(name, **fields):
    row = {'case': name, 'result': 'PASS', **fields}
    cases.append(row)
    print(json.dumps(row), flush=True)


cases = []
try:
    start('monerod', ['--data-dir', str(WORK / 'chain'), '--non-interactive', '--no-igd', '--offline',
          '--p2p-bind-ip', '127.0.0.1', '--p2p-bind-port', '19080', '--rpc-bind-ip', '127.0.0.1',
          '--rpc-bind-port', str(DAEMON_RPC), '--zmq-rpc-bind-ip', '127.0.0.1',
          '--out-peers', '0', '--in-peers', '0', '--disable-dns-checkpoints',
          '--check-updates', 'disabled', '--fixed-difficulty', '1',
          '--log-file', str(WORK / 'daemon.log')], 'daemon')
    # Genesis-only chain: height 1 before any block is mined.
    wait_until(lambda: daemon_height() == 1, 'daemon genesis')

    ports = {'A': 19100, 'B': 19101, 'C': 19102, 'S': 19103}
    for name, port in ports.items():
        directory = WORK / name
        directory.mkdir()
        start('monero-wallet-rpc', ['--rpc-bind-ip', '127.0.0.1', '--rpc-bind-port', str(port),
              '--disable-rpc-login', '--wallet-dir', str(directory),
              '--daemon-address', f'http://127.0.0.1:{DAEMON_RPC}', '--trusted-daemon',
              '--log-file', str(WORK / f'{name}.log')], f'wallet-{name}')
        wait_until(lambda p=port: rpc(p, 'get_version')['version'] > 0, f'{name} RPC')

    # --- Wallets A (miner+sender), B (receiver), S (mining sink for confirmations) ---
    rpc(ports['A'], 'create_wallet', {'filename': 'A', 'password': 'disposable', 'language': 'English'})
    addr_a = rpc(ports['A'], 'get_address')['address']
    assert addr_a.startswith('M'), addr_a
    seed_a = rpc(ports['A'], 'query_key', {'key_type': 'mnemonic'})['key']
    assert len(seed_a.split()) == 25
    rpc(ports['B'], 'create_wallet', {'filename': 'B', 'password': 'disposable', 'language': 'English'})
    addr_b = rpc(ports['B'], 'get_address')['address']
    rpc(ports['S'], 'create_wallet', {'filename': 'S', 'password': 'disposable', 'language': 'English'})
    addr_s = rpc(ports['S'], 'get_address')['address']

    # --- Fund A by mining; verify coinbase receive, balance and history ---
    mine_blocks(addr_a, 90, '90 coinbase blocks to A')
    height = daemon_height()
    mined_a = height - 1                          # genesis coinbase is zero-amount / unowned
    bal_a, unlocked_a = balances(ports['A'])
    hist_a = in_history(ports['A'])
    assert len(hist_a) == mined_a, (len(hist_a), mined_a)
    assert all(row[2] == EXPECTED_REWARD for row in hist_a), 'a coinbase reward differs from 9 MEOW'
    assert bal_a == mined_a * EXPECTED_REWARD, (bal_a, mined_a * EXPECTED_REWARD)
    assert sum(row[2] for row in hist_a) == bal_a
    assert unlocked_a >= (mined_a - UNLOCK_WINDOW) * EXPECTED_REWARD > 0
    record('receive_coinbase', reward_atomic=EXPECTED_REWARD, mined_blocks=mined_a,
           balance_atomic=bal_a, unlocked_atomic=unlocked_a, history_entries=len(hist_a))

    # --- Actual send A -> B, then confirm by mining to sink S (isolates fee accounting) ---
    amount1 = 5 * COIN
    sent1 = rpc(ports['A'], 'transfer', {'destinations': [{'amount': amount1, 'address': addr_b}],
                'get_tx_key': True})
    txid1, fee1 = sent1['tx_hash'], sent1['fee']
    assert sent1['amount'] == amount1, sent1
    assert fee1 > 0, 'fee must be non-zero'
    mine_blocks(addr_s, 15, 'confirm tx1 via sink')

    bal_b, _ = balances(ports['B'])
    in_b = in_history(ports['B'])
    assert bal_b == amount1, (bal_b, amount1)
    assert any(row[0] == txid1 and row[2] == amount1 for row in in_b), 'B did not receive tx1'
    record('send_receive', amount_atomic=amount1, fee_atomic=fee1, txid=txid1,
           receiver_balance_atomic=bal_b)

    bal_a_after, _ = balances(ports['A'])
    assert bal_a_after == bal_a - amount1 - fee1, (bal_a_after, bal_a - amount1 - fee1)
    out_a = transfers(ports['A'], 'out')
    assert any(t['txid'] == txid1 and t['fee'] == fee1 for t in out_a), 'A missing outgoing record'
    record('fee_atomic_units', sender_balance_before=bal_a, sender_balance_after=bal_a_after,
           debit_atomic=amount1 + fee1, identity='before - amount - fee == after')

    # --- Restore A from seed into C; recover outgoing metadata from a full rescan ---
    restored = rpc(ports['C'], 'restore_deterministic_wallet', {'seed': seed_a, 'restore_height': 0,
                   'filename': 'C', 'password': 'disposable', 'autosave_current': True})
    del seed_a
    assert restored['address'] == addr_a
    bal_c, unlocked_c = balances(ports['C'])
    assert bal_c == bal_a_after, (bal_c, bal_a_after)
    assert in_history(ports['C']) == in_history(ports['A']), 'restored incoming history differs'
    out_c = transfers(ports['C'], 'out')
    assert any(t['txid'] == txid1 and t['fee'] == fee1 for t in out_c), \
        'restore did not recover the outgoing spend from chain scan'
    record('restore_outgoing_metadata', balance_atomic=bal_c, address_matches=True,
           recovered_out_txids=[t['txid'] for t in out_c])

    # --- Spend from the RESTORED wallet C -> B (restore-then-spend) ---
    amount2 = 3 * COIN
    sent2 = rpc(ports['C'], 'transfer', {'destinations': [{'amount': amount2, 'address': addr_b}],
                'get_tx_key': True})
    txid2, fee2 = sent2['tx_hash'], sent2['fee']
    assert fee2 > 0
    mine_blocks(addr_s, 15, 'confirm tx2 via sink')

    bal_b2, _ = balances(ports['B'])
    assert bal_b2 == amount1 + amount2, (bal_b2, amount1 + amount2)
    assert any(row[0] == txid2 and row[2] == amount2 for row in in_history(ports['B']))
    bal_c_after, _ = balances(ports['C'])
    assert bal_c_after == bal_c - amount2 - fee2, (bal_c_after, bal_c - amount2 - fee2)
    record('restore_then_spend', amount_atomic=amount2, fee_atomic=fee2, txid=txid2,
           restored_balance_after=bal_c_after, receiver_balance_atomic=bal_b2)

    # --- Reopen the restored wallet; state must be stable across close/open ---
    snap = {'balance': bal_c_after, 'in': in_history(ports['C']),
            'out': sorted((t['txid'], t['fee']) for t in transfers(ports['C'], 'out'))}
    rpc(ports['C'], 'close_wallet')
    rpc(ports['C'], 'open_wallet', {'filename': 'C', 'password': 'disposable'})
    reopened = {'balance': balances(ports['C'])[0], 'in': in_history(ports['C']),
                'out': sorted((t['txid'], t['fee']) for t in transfers(ports['C'], 'out'))}
    assert reopened == snap, 'reopened restored wallet state differs'
    record('reopen', balance_atomic=reopened['balance'],
           in_entries=len(reopened['in']), out_entries=len(reopened['out']))

    # --- Aggregate reporting: real daemon coinbase/fee tally vs wallet fee reports ---
    total_height = daemon_height()
    coinbase_blocks = total_height - 1            # every non-genesis block minted one subsidy
    agg = rpc(DAEMON_RPC, 'get_coinbase_tx_sum', {'height': 0, 'count': total_height})
    assert agg['emission_amount'] == coinbase_blocks * EXPECTED_REWARD, \
        (agg['emission_amount'], coinbase_blocks * EXPECTED_REWARD)
    assert agg['fee_amount'] == fee1 + fee2, (agg['fee_amount'], fee1 + fee2)
    record('aggregate_reporting', height=total_height, coinbase_blocks=coinbase_blocks,
           emission_atomic=agg['emission_amount'], fee_atomic=agg['fee_amount'],
           wallet_reported_fees=fee1 + fee2, cross_check='daemon fee tally == wallet fee reports')

    summary = {
        'result': 'PASS',
        'cases': cases,
        'reward_atomic': EXPECTED_REWARD,
        'height': total_height,
        'emission_atomic': agg['emission_amount'],
        'fee_total_atomic': fee1 + fee2,
        'scope': ('real selected 9/90 monerod + monero-wallet-rpc on an isolated fixed-difficulty '
                  'chain; disposable keys; coinbase-funded; ring/CLSAG defaults; no external network'),
        'transport_observer_note': (
            'wallet<->daemon is trusted loopback HTTP over the container network namespace with '
            '--network none; NOT an anonymity test. A real remote node would additionally observe '
            'the source address, the set of txids/outputs the wallet fetches, restore height and '
            'request timing. Transport hardening (Tor/i2p, untrusted-node behaviour) is not '
            'exercised here; see the controller checkpoint (chain/privacy-test.py) and the '
            'observer threat model in research/wallet-funded-2026-09-18.md.'),
    }
    (WORK / 'result.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))
finally:
    for process in reversed(processes):
        process.terminate()
    for process in reversed(processes):
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
