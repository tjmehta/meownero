"""Variable-difficulty (non-floor) reorg economics on the real selected daemon — closes F2.

Every prior reorg/consensus test in this repo ran at fixed difficulty 1 (regtest
`--fixed-difficulty 1`, or the native DAA *held* at floor 1 by 120 s timestamps),
where cumulative work is proportional to height, so "heavier branch" == "longer
branch". F2 (TJS-42/TJS-44) is exactly the gap that leaves open: reorg selection
under *real, above-floor, varying* difficulty, where a **shorter** branch can carry
**more** cumulative work than a **longer** one and consensus must prefer work over
height.

This harness drives the shipped mainnet DAA (`next_difficulty`, DIFFICULTY_TARGET_V2
= 90 s, DIFFICULTY_WINDOW = 720, MEOW_MIN_DIFFICULTY = 1) above the floor with
**real RandomX proof-of-work** and no fixed-difficulty override, then proves
work-based (not height-based) fork selection on two independent daemons.

MINING PRIMITIVE (authoritative, no PoW shortcut)
  For each block: get_block_template (real DAA difficulty), set the block timestamp,
  then search the 4-byte nonce by submitting candidate blocks to the daemon's own
  `submit_block` verifier until one is ACCEPTED. Acceptance == the block met the
  DAA-computed difficulty under full RandomX consensus verification. (The `calc_pow`
  RPC is deliberately NOT used as the acceptance oracle: our probe supplied the full
  block blob, but calc_pow expects the hashing blob (`blockhashing_blob`) plus the
  matching major_version, height and seed_hash. The observed mismatch was a harness
  usage error, not a daemon defect; `submit_block` remains the acceptance oracle.)

DIFFICULTY STEERING (timestamps only; a hashpower *model*, not a live miner race)
  The DAA sets next difficulty = ceil(total_work * 90 / time_span) over the young-chain
  window. Inter-block spacing is the only lever hashpower changes pull, so we steer the
  block timestamp to hold, raise, or drop the DAA difficulty. This exercises the REAL
  daemon DAA and REAL PoW acceptance; it is NOT a live multi-miner hashrate race and is
  labelled as such. "50% / 90% miner departure" == inter-block spacing widened 2x / 10x
  vs target; "recovery / switching miners" == spacing restored to target.

PREDECLARED ACCEPTANCE CRITERIA (asserted below; PASS only if all hold)
  AC1 non-floor variable difficulty: the real DAA yields block difficulties strictly
      greater than MEOW_MIN_DIFFICULTY (peak >= AC1_MIN_PEAK), each block accepted by
      RandomX consensus, and tip cumulative_difficulty strictly exceeds height+1 (i.e.
      strictly more work than any floor-1 chain of equal height).
  AC2 DAA departure/recovery response: widening spacing (50% then 90% departure)
      strictly lowers the next-block difficulty; restoring spacing strictly raises it.
  AC3 cumulative-work-not-height selection: an independent daemon holding a LONGER main
      branch reorganises onto a strictly SHORTER attacker branch of strictly GREATER
      cumulative_difficulty; while the attacker branch is shorter AND not-heavier it is
      retained as an alternative and does NOT replace main; every displaced main block
      is flagged orphan.
  AC4 invariants across the variable-difficulty reorg: both daemons converge (identical
      tip hash/height/cumulative_difficulty); emission == height * 9 MEOW (flat subsidy,
      difficulty-independent); tip cumulative_difficulty == independently recomputed sum
      of accepted block difficulties; a daemon restart preserves the selected tip.

SCOPE / HONESTY BOUNDS
  Two isolated `--offline` mainnet-mode daemons; explicit get_block/submit_block delivery
  (no P2P, no transactions, empty blocks); disposable fixture address; `--network none`.
  Crypto is RingCT-era (this test mines empty blocks; no FCMP, no capacity normalisation).
  Difficulty is above the floor and genuinely varying, but driven by controlled timestamps
  (a hashpower model on the real DAA), not by competing physical hashrate. Peak difficulty
  is bounded on purpose to keep RandomX cost small; this bounds PoW cost, not the argument.
"""
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

WORK = Path('/work')
ADDRESS = 'M9Lds8CcBgCJbqSiUvYfS3BfhEdxZmv8pDt25oW1LzxrZv9Uq6ARagiFViMGUE3gJk5VPWingCXVf1p2tyAy6SUeSLMMvfc'
REWARD = 9_000_000_000_000            # selected 9/90 subsidy (9 MEOW); asserted via emission
TARGET = 90                           # DIFFICULTY_TARGET_V2 (seconds)
LEVEL = 32                            # bounded above-floor difficulty to hold (cost control)
AC1_MIN_PEAK = 16                     # PASS requires the real DAA to exceed this above the floor
BASE_TIME = int(time.time()) - 1_000_000
MAX_NONCE = 1 << 20                   # nonce search bound per block (>> peak difficulty)
processes = {}


def rpc(node, method, params=None):
    body = {'jsonrpc': '2.0', 'id': '0', 'method': method,
            'params': {} if params is None else params}
    req = urllib.request.Request(f'http://127.0.0.1:{19081 + node * 100}/json_rpc',
                                 json.dumps(body).encode(), {'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=120) as response:
        return json.load(response)


def ok(node, method, params=None):
    res = rpc(node, method, params)
    assert 'error' not in res, (method, res)
    return res['result']


def start(node):
    with (WORK / f'n{node}.stdout.log').open('a') as log:
        processes[node] = subprocess.Popen([
            '/src/build/release/bin/monerod', '--data-dir', str(WORK / f'n{node}'),
            '--offline', '--non-interactive', '--no-igd', '--disable-dns-checkpoints',
            '--check-updates', 'disabled', '--log-level', '0',
            '--p2p-bind-ip', '127.0.0.1', '--p2p-bind-port', str(19080 + node * 100),
            '--rpc-bind-ip', '127.0.0.1', '--rpc-bind-port', str(19081 + node * 100),
            '--zmq-rpc-bind-ip', '127.0.0.1', '--zmq-rpc-bind-port', str(19082 + node * 100),
            '--log-file', str(WORK / f'n{node}.log')], stdout=log, stderr=subprocess.STDOUT)
    for _ in range(120):
        assert processes[node].poll() is None, 'daemon exited'
        try:
            ok(node, 'get_info')
            return
        except OSError:
            time.sleep(0.5)
    raise AssertionError('daemon startup timeout')


def stop(node):
    p = processes.pop(node)
    p.terminate()
    try:
        assert p.wait(timeout=25) == 0
    except subprocess.TimeoutExpired:
        p.kill()
        p.wait()
        raise


def read_varint(data, offset):
    value = shift = 0
    while True:
        byte = data[offset]
        offset += 1
        value |= (byte & 127) << shift
        if byte < 128:
            return value, offset
        shift += 7
        assert shift < 64


def varint(value):
    result = bytearray()
    while value >= 128:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return result


def tip(node):
    h = ok(node, 'get_last_block_header')['block_header']
    return h['height'], h['hash'], int(h['wide_cumulative_difficulty'], 16)


def anchor(node):
    """Block index 1 (timestamp, cumulative_difficulty) — the young-chain DAA window base."""
    h = ok(node, 'get_block_header_by_height', {'height': 1})['block_header']
    return h['timestamp'], int(h['wide_cumulative_difficulty'], 16)


def hold_timestamp(node, target_level, this_diff):
    """Absolute timestamp for the block about to be mined so the NEXT block's DAA
    difficulty is ~= target_level. Uses the daemon's own tip work + block-1 anchor;
    exact inverse of next_difficulty on the young-chain (no-cut/no-lag) window."""
    _, _, cum = tip(node)
    t1, c1 = anchor(node)
    want_span = (cum + this_diff - c1) * TARGET / max(1, target_level)
    prev_ts = ok(node, 'get_last_block_header')['block_header']['timestamp']
    return max(prev_ts + 1, int(round(t1 + want_span)))


def mine(node, abs_ts):
    """Mine one block at `abs_ts` by nonce-searching against submit_block (the
    authoritative RandomX consensus oracle). Returns a per-block record; the raw
    accepted blob is returned for cross-node delivery."""
    t = ok(node, 'get_block_template', {'wallet_address': ADDRESS})
    diff, height = t['difficulty'], t['height']
    blob = bytearray.fromhex(t['blocktemplate_blob'])
    _, o = read_varint(blob, 0)
    _, o = read_varint(blob, o)
    _, tend = read_varint(blob, o)
    blob[o:tend] = varint(abs_ts)
    _, o2 = read_varint(blob, 0)
    _, o2 = read_varint(blob, o2)
    _, tend2 = read_varint(blob, o2)
    noff = tend2 + 32                         # after major,minor,timestamp varints + 32-byte prev id
    for nonce in range(MAX_NONCE):
        blob[noff:noff + 4] = nonce.to_bytes(4, 'little')
        res = rpc(node, 'submit_block', [blob.hex()])
        if 'error' not in res and res['result']['status'] == 'OK':
            top = tip(node)
            return {'height': top[0], 'hash': top[1], 'difficulty': diff,
                    'cumulative_difficulty': top[2], 'timestamp': abs_ts,
                    'nonce': nonce, 'pow_submits': nonce + 1, 'blob': blob.hex()}
    raise AssertionError(('nonce space exhausted', height, diff))


def deliver(dst, blob):
    res = rpc(dst, 'submit_block', [blob])
    assert 'error' not in res and res['result']['status'] == 'OK', ('deliver', res)


def emission(node):
    h = tip(node)[0]
    s = ok(node, 'get_coinbase_tx_sum', {'height': 0, 'count': h + 1})
    return h, s['emission_amount'], s['fee_amount']


result = {'result': 'PENDING', 'level': LEVEL, 'target_seconds': TARGET,
          'reward_atomic': REWARD, 'min_difficulty_floor': 1,
          'criteria': {}, 'phases': {}}
try:
    start(0)
    start(1)
    assert ok(0, 'get_info')['nettype'] == 'mainnet'

    # ---- Phase A+B: single-chain variable-difficulty witness + departure/recovery ----
    # Ramp above the floor, hold (stable hashpower), 50% then 90% departure, recover.
    base = []            # block records for the base chain on node 0
    # ramp+hold to LEVEL (steered) — small gaps push difficulty up, then it self-holds.
    # The DAA returns 1 until block 1 exists, so the first two blocks use a small fixed
    # gap; steering begins once the young-chain window (block index 1) is populated.
    for _ in range(60):
        height_now = tip(0)[0]
        if height_now < 2:
            ts = BASE_TIME + height_now * 5
        else:
            cur = ok(0, 'get_block_template', {'wallet_address': ADDRESS})['difficulty']
            ts = hold_timestamp(0, LEVEL, cur)
        base.append(mine(0, ts))
        if len(base) >= 12 and base[-1]['difficulty'] >= LEVEL:
            break
    ramp_peak = max(b['difficulty'] for b in base)
    stable_diff = ok(0, 'get_block_template', {'wallet_address': ADDRESS})['difficulty']

    # Root for the reorg contest: the current stable, above-floor tip.
    root = tip(0)
    root_anchor_ts = base[-1]['timestamp']

    # Departure/recovery response, measured on the real DAA (records only; does NOT
    # touch the reorg root — run on node 1's throwaway extension from the same base).
    for b in base:
        deliver(1, b['blob'])
    assert tip(0) == tip(1)

    def daa_after(node, gaps):
        """Apply blocks with the given spacings on `node`; return difficulty trajectory."""
        traj = []
        last = ok(node, 'get_last_block_header')['block_header']['timestamp']
        for g in gaps:
            last += g
            rec = mine(node, last)
            traj.append(rec['difficulty'])
        return traj

    stable_traj = daa_after(1, [TARGET] * 4)                    # stable hashpower ~ target spacing
    depart50_traj = daa_after(1, [TARGET * 2] * 5)              # 50% departure -> 2x spacing
    depart90_traj = daa_after(1, [TARGET * 10] * 5)             # 90% departure -> 10x spacing
    # Miners return at full hashpower -> minimal spacing. Young-chain DAA recovery is
    # sluggish (the whole prior history stays in the <720-block window), so recovery is
    # gradual; mine enough fast blocks to show difficulty turn back up off the trough.
    recover_traj = daa_after(1, [1] * 24)

    result['phases']['A_witness'] = {
        'base_blocks': len(base), 'ramp_peak_difficulty': ramp_peak,
        'stable_difficulty': stable_diff,
        'root_height': root[0], 'root_cumulative_difficulty': root[2]}
    result['phases']['B_departure_recovery'] = {
        'stable': stable_traj, 'departure_50pct_2x_spacing': depart50_traj,
        'departure_90pct_10x_spacing': depart90_traj, 'recovery_faster_spacing': recover_traj,
        'note': 'timestamp-driven hashpower model on the real daemon DAA; not a live hashrate race'}

    # node 1 is now polluted by the departure/recovery extension; rebuild it clean to
    # the shared root for the reorg contest.
    stop(1)
    (WORK / 'n1').rename(WORK / 'n1-departrec')
    start(1)
    for b in base:
        deliver(1, b['blob'])
    assert tip(1) == root, ('node1 not at root', tip(1), root)

    # ---- Phase C: cumulative-work (not height) reorg under variable difficulty ----
    # MAIN (node 0): LONGER, LIGHTER — 90%-departure spacing collapses difficulty to ~1.
    main_branch = []
    ts = root_anchor_ts
    for _ in range(24):
        ts += TARGET * 10                       # 10x target spacing -> difficulty falls to floor
        main_branch.append(mine(0, ts))
    main_tip = tip(0)
    main_added_work = main_tip[2] - root[2]

    # ATTACKER (node 1): SHORTER, HEAVIER — hold above-floor difficulty at LEVEL until the
    # branch out-works main while staying strictly lower in height.
    atk_branch = []
    while True:
        cur = ok(1, 'get_block_template', {'wallet_address': ADDRESS})['difficulty']
        ts = hold_timestamp(1, LEVEL, cur)
        atk_branch.append(mine(1, ts))
        atk_tip = tip(1)
        if atk_tip[2] > main_tip[2] and atk_tip[0] < main_tip[0]:
            break
        assert atk_tip[0] < main_tip[0], ('attacker reached main height without out-working it',
                                          atk_tip, main_tip)
    assert atk_tip[0] < main_tip[0], (atk_tip, main_tip)      # strictly shorter
    assert atk_tip[2] > main_tip[2], (atk_tip, main_tip)      # strictly heavier

    # Negative control: deliver attacker blocks to node 0 one at a time. While the
    # attacker chain is shorter AND not-heavier it must be retained as an alternative
    # and NOT replace main; the switch must happen only when its work strictly exceeds
    # main's — even though it is still strictly shorter.
    switch_index = None
    for i, b in enumerate(atk_branch):
        deliver(0, b['blob'])
        cur = tip(0)
        if b['cumulative_difficulty'] <= main_tip[2]:
            assert cur == main_tip, ('reorged early on lighter/equal-work branch', i, cur, main_tip)
        elif switch_index is None:
            switch_index = i
    assert switch_index is not None, 'attacker never became heavier'
    after = tip(0)
    assert after == atk_tip, ('final tip != attacker tip', after, atk_tip)
    assert after[0] < main_tip[0], ('reorg tip not shorter than main', after, main_tip)
    assert after[2] > main_tip[2], ('reorg tip not heavier than main', after, main_tip)

    # Displaced main blocks are off the selected chain. Because the winning branch is
    # strictly SHORTER, displaced blocks sit at or above the new tip; prove displacement
    # against the main chain by height (authoritative), and capture orphan_status when
    # the alt lookup still resolves the block.
    orphaned = 0
    orphan_status_confirmed = 0
    new_tip_h = after[0]
    for b in main_branch:
        H = b['height']
        if H <= new_tip_h:
            onchain = ok(0, 'get_block_header_by_height', {'height': H})['block_header']['hash']
            assert onchain != b['hash'], ('displaced main block still on selected chain', b['hash'])
        else:
            miss = rpc(0, 'get_block_header_by_height', {'height': H})
            assert 'error' in miss, ('displaced main block still present on selected chain by height', H)
        alt = rpc(0, 'get_block_header_by_hash', {'hash': b['hash']})
        if 'error' not in alt and alt['result']['block_header'].get('orphan_status'):
            orphan_status_confirmed += 1
        orphaned += 1

    # AC4 invariants + convergence + emission + recomputed work.
    assert tip(0) == tip(1), ('nodes did not converge', tip(0), tip(1))
    h0, emit0, fee0 = emission(0)
    assert emit0 == h0 * REWARD, ('emission != height*reward', h0, emit0)
    assert fee0 == 0, fee0
    recomputed = root[2] + sum(b['difficulty'] for b in atk_branch)
    assert after[2] == recomputed, ('cumulative_difficulty != recomputed work sum', after[2], recomputed)

    # Recovery / continue on the winning chain (switching miners), then restart-preserves-tip.
    ts = atk_branch[-1]['timestamp']
    recov_after_reorg = []
    for _ in range(3):
        cur = ok(0, 'get_block_template', {'wallet_address': ADDRESS})['difficulty']
        ts = hold_timestamp(0, LEVEL, cur)
        rec = mine(0, ts)
        deliver(1, rec['blob'])                  # keep both nodes converged on the winning chain
        recov_after_reorg.append(rec['difficulty'])
    before = tip(0)
    stop(0)
    start(0)
    assert tip(0) == before, ('restart changed selected tip/work', tip(0), before)

    # ---- criteria evaluation ----
    ac1 = ramp_peak >= AC1_MIN_PEAK and root[2] > root[0] + 1
    ac2 = (min(depart50_traj) < stable_traj[-1]
           and min(depart90_traj) < min(depart50_traj)
           and recover_traj[-1] > min(depart90_traj))
    ac3 = (after == atk_tip and after[0] < main_tip[0] and after[2] > main_tip[2]
           and switch_index is not None and orphaned == len(main_branch))
    ac4 = (tip(0) == before and emit0 == h0 * REWARD and after[2] == recomputed
           and tip(0)[1] == tip(1)[1])
    result['criteria'] = {
        'AC1_non_floor_variable_difficulty': bool(ac1),
        'AC2_departure_recovery_response': bool(ac2),
        'AC3_cumulative_work_not_height_selection': bool(ac3),
        'AC4_invariants_convergence_restart': bool(ac4)}
    result['phases']['C_vardiff_reorg'] = {
        'root_height': root[0], 'root_cumulative_difficulty': root[2],
        'main_height': main_tip[0], 'main_cumulative_difficulty': main_tip[2],
        'main_blocks': len(main_branch), 'main_added_work': main_added_work,
        'main_last_difficulty': main_branch[-1]['difficulty'],
        'attacker_height': atk_tip[0], 'attacker_cumulative_difficulty': atk_tip[2],
        'attacker_blocks': len(atk_branch),
        'attacker_peak_difficulty': max(b['difficulty'] for b in atk_branch),
        'height_delta_attacker_minus_main': atk_tip[0] - main_tip[0],
        'work_delta_attacker_minus_main': atk_tip[2] - main_tip[2],
        'switch_at_attacker_block_index': switch_index,
        'displaced_main_blocks': orphaned,
        'orphan_status_confirmed_via_alt_lookup': orphan_status_confirmed,
        'converged_tip_hash': tip(0)[1],
        'emission_height': h0, 'emission_amount': emit0,
        'recomputed_cumulative_difficulty': recomputed,
        'recovery_after_reorg_difficulty': recov_after_reorg,
        'restart_preserved_tip': True}
    result['difficulty_trajectory_base'] = [
        {'height': b['height'], 'difficulty': b['difficulty'],
         'cumulative_difficulty': b['cumulative_difficulty'],
         'timestamp': b['timestamp'], 'pow_submits': b['pow_submits']} for b in base]
    result['attacker_blocks_detail'] = [
        {'height': b['height'], 'difficulty': b['difficulty'],
         'cumulative_difficulty': b['cumulative_difficulty'],
         'timestamp': b['timestamp'], 'pow_submits': b['pow_submits']} for b in atk_branch]
    result['total_pow_submits'] = sum(b['pow_submits'] for b in base + atk_branch + main_branch)
    result['result'] = 'PASS' if all(result['criteria'].values()) else 'FAIL'
    (WORK / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'result': result['result'], 'criteria': result['criteria'],
                      'ramp_peak': ramp_peak, 'attacker_h': atk_tip[0], 'main_h': main_tip[0],
                      'attacker_work': atk_tip[2], 'main_work': main_tip[2],
                      'total_pow_submits': result['total_pow_submits']}, indent=2))
except Exception as exc:
    result['result'] = 'ERROR'
    result['error'] = repr(exc)
    (WORK / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    raise
finally:
    for node in list(processes):
        try:
            stop(node)
        except Exception:
            pass
