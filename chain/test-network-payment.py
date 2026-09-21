"""Cross-node private payment + seed recovery over an actual two-daemon P2P network.

Closes the TJS-44 seam that two single-component passes did not cover: a real
private (RingCT) payment SENT by a wallet on node A, RELAYED over P2P to node B,
CONFIRMED in a block that propagates back across P2P, RECEIVED by a wallet on
node B; then that receiver wallet is RESTORED FROM SEED on node B and its
restored copy SPENDS back to node A, with the spend relayed over P2P and observed
on node A. Chain tips, emission and cumulative difficulty are asserted equal on
both daemons.

Two `monerod` in regtest/fakechain mode, connected only to each other by
`--add-exclusive-node` (real TCP P2P, no RPC block/tx injection between nodes),
fixed difficulty 1. Blocks are produced with `generateblocks`; the payment is
built by `monero-wallet-rpc` and enters a node's pool via ordinary relay, then
propagates over P2P. Container has `--network none`; every key is disposable.

Sanitized evidence: amounts (atomic, 12 dp), fees, counts, txids, block hashes
and heights only. It never records a mnemonic, address, spend key, RPC password
or request body. This is a fund-propagation / recovery correctness test on an
isolated devnet, NOT an anonymity or FCMP measurement (regtest, small decoy pool,
CLSAG/bulletproof+ RingCT, no FCMP).
"""
import json
from pathlib import Path
import subprocess
import time
import urllib.request

BIN = Path('/src/build/release/bin')
WORK = Path('/work')
COIN = 1_000_000_000_000
UNLOCK_WINDOW = 60          # CRYPTONOTE_MINED_MONEY_UNLOCK_WINDOW
SPENDABLE_AGE = 10          # CRYPTONOTE_DEFAULT_TX_SPENDABLE_AGE
EXPECTED_REWARD = 9 * COIN  # selected 9/90 profile subsidy; asserted, not assumed
FUND_BLOCKS = 100           # deep enough for a ring-16 decoy set from unlocked coinbases
CONFIRM_BLOCKS = 12         # confirm + clear the 10-block spendable age

processes = []
cases = []


def post(port, path, body):
    req = urllib.request.Request(f'http://127.0.0.1:{port}/{path}',
                                 json.dumps(body).encode(), {'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=120) as response:
        return json.load(response)


def drpc(node, method, params=None):
    port = 19081 + node * 100
    r = post(port, 'json_rpc', {'jsonrpc': '2.0', 'id': '0', 'method': method, 'params': params or {}})
    assert 'error' not in r, (node, method, r.get('error'))
    return r['result']


def dget(node, path, body=None):
    return post(19081 + node * 100, path, body or {})


def wrpc(port, method, params=None):
    r = post(port, 'json_rpc', {'jsonrpc': '2.0', 'id': '0', 'method': method, 'params': params or {}})
    assert 'error' not in r, (method, r.get('error'))
    return r['result']


def wait_until(check, label, seconds=180):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        assert all(p.poll() is None for p in processes), 'a test process exited early'
        try:
            if check():
                return
        except (OSError, ValueError, AssertionError, KeyError):
            pass
        time.sleep(0.4)
    raise AssertionError(f'timeout: {label}')


def start(binary, args, name):
    with (WORK / f'{name}.stdout.log').open('a') as log:
        process = subprocess.Popen([str(BIN / binary), *args], stdout=log, stderr=subprocess.STDOUT)
    processes.append(process)
    return process


def start_daemon(node):
    p2p = 19080 + node * 100
    rpc = 19081 + node * 100
    zmq = 19082 + node * 100
    peer = 19080 + (1 - node) * 100
    start('monerod', ['--data-dir', str(WORK / f'n{node}'), '--regtest', '--keep-fakechain',
          '--fixed-difficulty', '1', '--non-interactive', '--no-igd', '--allow-local-ip',
          '--disable-dns-checkpoints', '--check-updates', 'disabled',
          '--add-exclusive-node', f'127.0.0.1:{peer}',
          '--p2p-bind-ip', '127.0.0.1', '--p2p-bind-port', str(p2p),
          '--rpc-bind-ip', '127.0.0.1', '--rpc-bind-port', str(rpc),
          '--zmq-rpc-bind-ip', '127.0.0.1', '--zmq-rpc-bind-port', str(zmq),
          '--log-file', str(WORK / f'n{node}.log')], f'n{node}')


def start_wallet(name, port, node):
    (WORK / name).mkdir()
    start('monero-wallet-rpc', ['--rpc-bind-ip', '127.0.0.1', '--rpc-bind-port', str(port),
          '--disable-rpc-login', '--wallet-dir', str(WORK / name),
          '--daemon-address', f'http://127.0.0.1:{19081 + node * 100}', '--trusted-daemon',
          '--allow-mismatched-daemon-version', '--log-file', str(WORK / f'{name}.log')], f'w{name}')
    wait_until(lambda: wrpc(port, 'get_version')['version'] > 0, f'{name} wallet rpc')


def tip(node):
    h = drpc(node, 'get_last_block_header')['block_header']
    return h['height'], h['hash'], h['wide_cumulative_difficulty']


def connections(node):
    info = drpc(node, 'get_info')
    return info['incoming_connections_count'] + info['outgoing_connections_count']


def generate(node, count, address):
    r = drpc(node, 'generateblocks', {'wallet_address': address, 'amount_of_blocks': count})
    assert 'blocks' in r and len(r['blocks']) == count, r
    return r['blocks']


def converge(seconds=120):
    """Wait until both daemons agree on the exact tip (P2P block propagation)."""
    wait_until(lambda: tip(0) == tip(1), 'cross-node tip convergence', seconds)
    assert tip(0) == tip(1)
    return tip(0)


def pool_hashes(node):
    return {t['id_hash'] for t in dget(node, 'get_transaction_pool').get('transactions', [])}


def refresh(port):
    wrpc(port, 'refresh', {'start_height': 0})


def balance(port):
    refresh(port)
    b = wrpc(port, 'get_balance')
    return b['balance'], b['unlocked_balance']


def in_rows(port):
    refresh(port)
    return sorted((t['txid'], t['amount']) for t in wrpc(port, 'get_transfers', {'in': True}).get('in', []))


def record(name, **fields):
    row = {'case': name, 'result': 'PASS', **fields}
    cases.append(row)
    print(json.dumps(row), flush=True)


try:
    # --- Two daemons, peered only to each other over real TCP P2P ---
    start_daemon(0)
    start_daemon(1)
    wait_until(lambda: drpc(0, 'get_info')['height'] == 1 and drpc(1, 'get_info')['height'] == 1,
               'both daemons at genesis')
    wait_until(lambda: connections(0) >= 1 and connections(1) >= 1, 'nodes peered over P2P')
    record('two_node_p2p_up', node0_conns=connections(0), node1_conns=connections(1),
           genesis_hash=tip(0)[1], scope='regtest fixed-difficulty-1; exclusive-node P2P; no RPC block injection')

    # Wallet A + sink S on node 0; receiver B + restored D on node 1.
    start_wallet('A', 19090, 0)
    start_wallet('S', 19091, 0)
    start_wallet('B', 19190, 1)
    start_wallet('D', 19191, 1)
    wrpc(19090, 'create_wallet', {'filename': 'A', 'password': 'disposable', 'language': 'English'})
    addr_a = wrpc(19090, 'get_address')['address']
    assert addr_a.startswith('M'), addr_a
    wrpc(19091, 'create_wallet', {'filename': 'S', 'password': 'disposable', 'language': 'English'})
    addr_s = wrpc(19091, 'get_address')['address']
    wrpc(19190, 'create_wallet', {'filename': 'B', 'password': 'disposable', 'language': 'English'})
    addr_b = wrpc(19190, 'get_address')['address']
    seed_b = wrpc(19190, 'query_key', {'key_type': 'mnemonic'})['key']
    assert len(seed_b.split()) == 25

    # --- Fund A on node 0; blocks must propagate to node 1 over P2P ---
    generate(0, FUND_BLOCKS, addr_a)
    funded_tip = converge()
    bal_a, unlocked_a = balance(19090)
    coinbases = funded_tip[0]                       # block_header height == top index == #coinbase blocks
    assert bal_a == coinbases * EXPECTED_REWARD, (bal_a, coinbases * EXPECTED_REWARD)
    assert unlocked_a > 0
    record('fund_and_block_propagation', fund_blocks=FUND_BLOCKS, node0_tip_height=funded_tip[0],
           node1_tip_height=tip(1)[0], tip_hash=funded_tip[1], tips_match=True,
           miner_balance_atomic=bal_a, reward_atomic=EXPECTED_REWARD)

    # --- Private payment A(node0) -> B(node1), RELAYED over P2P to node1's pool ---
    amount1 = 5 * COIN
    sent1 = wrpc(19090, 'transfer', {'destinations': [{'amount': amount1, 'address': addr_b}],
                 'get_tx_key': True})
    txid1, fee1 = sent1['tx_hash'], sent1['fee']
    assert sent1['amount'] == amount1 and fee1 > 0, sent1
    assert txid1 in pool_hashes(0), 'tx1 not in origin node pool'
    wait_until(lambda: txid1 in pool_hashes(1), 'tx1 relayed to node1 pool over P2P')
    # Observe it is a RingCT (non-transparent) tx, as data — not an anonymity claim.
    txd = dget(0, 'get_transactions', {'txs_hashes': [txid1], 'decode_as_json': True})
    tx_json = json.loads(txd['txs'][0]['as_json'])
    rct_type = tx_json['rct_signatures']['type']
    ring_size = len(tx_json['vin'][0]['key']['key_offsets'])
    assert tx_json['version'] == 2 and rct_type in (5, 6) and ring_size == 16, (tx_json['version'], rct_type, ring_size)
    record('payment_relayed_p2p', txid=txid1, amount_atomic=amount1, fee_atomic=fee1,
           reached_node1_pool=True, tx_version=tx_json['version'], rct_type=rct_type, ring_size=ring_size)

    # --- Confirm on node0 (mine to sink S so A's only debit is the spend); block propagates ---
    generate(0, CONFIRM_BLOCKS, addr_s)
    confirmed_tip = converge()
    assert txid1 not in pool_hashes(0) and txid1 not in pool_hashes(1), 'tx1 still pooled after mining'
    bal_b, _ = balance(19190)
    assert bal_b == amount1, (bal_b, amount1)
    assert (txid1, amount1) in in_rows(19190), 'B (node1) did not receive tx1 across P2P'
    bal_a_after, _ = balance(19090)
    assert bal_a_after == bal_a - amount1 - fee1, (bal_a_after, bal_a - amount1 - fee1)
    record('payment_confirmed_cross_node', txid=txid1, receiver_node=1, receiver_balance_atomic=bal_b,
           sender_balance_after_atomic=bal_a_after, tip_hash=confirmed_tip[1], tips_match=True)

    # --- Seed recovery of the receiver, on node 1 ---
    restored = wrpc(19191, 'restore_deterministic_wallet', {'seed': seed_b, 'restore_height': 0,
                    'filename': 'D', 'password': 'disposable', 'autosave_current': True})
    del seed_b
    assert restored['address'] == addr_b
    bal_d, _ = balance(19191)
    assert bal_d == bal_b, (bal_d, bal_b)
    assert in_rows(19191) == in_rows(19190), 'restored receiver incoming rows differ'
    record('seed_recovery_cross_node', restore_node=1, restored_balance_atomic=bal_d,
           incoming_rows=len(in_rows(19191)), address_matches=True,
           note='asserts balance and incoming (txid,amount) rows; not a wallet-file byte comparison')

    # --- Restored wallet D(node1) spends back to A(node0), RELAYED over P2P to node0's pool ---
    amount2 = 2 * COIN
    sent2 = wrpc(19191, 'transfer', {'destinations': [{'amount': amount2, 'address': addr_a}],
                 'get_tx_key': True})
    txid2, fee2 = sent2['tx_hash'], sent2['fee']
    assert fee2 > 0
    assert txid2 in pool_hashes(1), 'tx2 not in origin node1 pool'
    wait_until(lambda: txid2 in pool_hashes(0), 'tx2 relayed to node0 pool over P2P')
    generate(0, CONFIRM_BLOCKS, addr_s)
    spent_tip = converge()
    bal_a_final, _ = balance(19090)
    assert (txid2, amount2) in in_rows(19090), 'A (node0) did not observe restored-wallet spend'
    assert bal_a_final == bal_a_after + amount2, (bal_a_final, bal_a_after + amount2)
    bal_d_after, _ = balance(19191)
    assert bal_d_after == bal_d - amount2 - fee2, (bal_d_after, bal_d - amount2 - fee2)
    record('restored_spend_observed_cross_node', txid=txid2, amount_atomic=amount2, fee_atomic=fee2,
           spender_node=1, observer_node=0, spender_balance_after_atomic=bal_d_after,
           observer_received_atomic=amount2, tip_hash=spent_tip[1], tips_match=True)

    # --- Final: both daemons agree on tip, emission and cumulative difficulty ---
    t0, t1 = tip(0), tip(1)
    assert t0 == t1, (t0, t1)
    per_node = {}
    for node in (0, 1):
        info = drpc(node, 'get_info')
        h = info['height']                          # RPC height: counts genesis (top index + 1)
        supply = drpc(node, 'get_coinbase_tx_sum', {'height': 0, 'count': h})
        assert supply['emission_amount'] == (h - 1) * EXPECTED_REWARD, (node, supply['emission_amount'])
        assert supply['fee_amount'] == fee1 + fee2, (node, supply['fee_amount'])
        assert info['cumulative_difficulty'] == h, (node, info['cumulative_difficulty'], h)
        per_node[str(node)] = {'rpc_height': h, 'top_block_index': h - 1,
                               'emission_atomic': supply['emission_amount'],
                               'fee_atomic': supply['fee_amount'],
                               'cumulative_difficulty': info['cumulative_difficulty'],
                               'top_block_hash': info['top_block_hash']}
    assert per_node['0'] == per_node['1'], per_node
    record('cross_node_convergence', rpc_height=per_node['0']['rpc_height'],
           top_block_index=per_node['0']['top_block_index'],
           emission_atomic=per_node['0']['emission_atomic'],
           emission_formula='(rpc_height - 1) * reward; genesis coinbase = 0',
           cumulative_difficulty=per_node['0']['cumulative_difficulty'],
           cumulative_difficulty_formula='== rpc_height at fixed difficulty 1',
           fee_total_atomic=fee1 + fee2, both_nodes_identical=True)

    summary = {
        'result': 'PASS',
        'cases': cases,
        'reward_atomic': EXPECTED_REWARD,
        'rpc_height': per_node['0']['rpc_height'],
        'top_block_index': per_node['0']['top_block_index'],
        'emission_atomic': per_node['0']['emission_atomic'],
        'fee_total_atomic': fee1 + fee2,
        'txids': {'payment_a_to_b': txid1, 'restored_spend_b_to_a': txid2},
        'per_node': per_node,
        'scope': ('two actual monerod peers over TCP P2P (regtest, fixed difficulty 1, exclusive-node, '
                  'no RPC block/tx injection between nodes); RingCT CLSAG/bulletproof+; disposable keys; '
                  'container --network none. Cross-node private payment relayed+confirmed, receiver '
                  'seed-restored on the far node, restored-wallet spend observed on the origin node.'),
        'not_tested': ('anonymity/unlinkability, FCMP, variable-difficulty DAA, matched-capacity load, '
                       'Tor/i2p transport, untrusted-node behaviour, multi-destination/subaddress/sweep, '
                       'interactive CLI restore, repetition beyond a single run'),
    }
    (WORK / 'result.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))
finally:
    receipt = {}
    for name in ['memory.peak', 'memory.events', 'memory.max', 'memory.swap.max', 'cpu.max']:
        path = Path('/sys/fs/cgroup') / name
        if path.exists():
            receipt[name] = path.read_text()
    for process in reversed(processes):
        process.terminate()
    for process in reversed(processes):
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    receipt['exit_codes'] = [p.returncode for p in processes]
    (WORK / 'resources.json').write_text(json.dumps(receipt, indent=2) + '\n')
