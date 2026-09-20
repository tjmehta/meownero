"""Lightweight TJS-165 frozen-receipt checks; no daemon/container launch.

Run from the repository root: python3 research/evidence/qa-tjs165-2026-09-20/readback.py
This checks retained observations, not a fresh consensus execution.
"""
import hashlib
import json
from pathlib import Path

E = Path('research/evidence/vardiff-2026-09-18')
Q = Path(__file__).parent
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(E / 'MANIFEST.sha256') == 'd310fabf9e10280448c0559b4471215f981562b0275893b6d940c9167356ce08'
entries = (E / 'MANIFEST.sha256').read_text().splitlines()
assert len(entries) == 9
for line in entries:
    expected, name = line.split(maxsplit=1)
    assert sha(E / name) == expected, name
for line in (E / 'freeze/INPUT_SHA256').read_text().splitlines():
    expected, name = line.split(maxsplit=1)
    # Bind to pre-correction bytes captured by QA, not concurrent TJS-166 edits.
    assert sha(Q / (Path(name).name + '.before')) == expected
expected, name = (E / 'freeze/BINARY_SHA256').read_text().split()
assert sha(Path(name)) == expected
assert (E / 'freeze/SOURCE_REVISIONS').read_text().splitlines() == [
    '7410c04bab0e304112710d63c3225c110bd8b4de',
    '4db958cb96d72943c5c2433bd5f4a8f730037148']
assert (E / 'freeze/BUILDER_IMAGE_ID').read_text().strip() == 'sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e'

runs = []
for number, filename in [(3, 'result.json'), (4, 'result-repeat.json')]:
    raw = E / filename
    assert raw.read_bytes() == Path(f'build/reorg-vardiff-20260918/run{number}/result.json').read_bytes()
    for receipt in ['SOURCE_REVISIONS', 'BUILDER_IMAGE_ID', 'BINARY_SHA256', 'INPUT_SHA256']:
        assert (E / 'freeze' / receipt).read_bytes() == Path(f'build/reorg-vardiff-20260918/run{number}/{receipt}').read_bytes()
    d = json.loads(raw.read_text())
    a, b, c = (d['phases'][key] for key in ['A_witness', 'B_departure_recovery', 'C_vardiff_reorg'])
    base, attack = d['difficulty_trajectory_base'], d['attacker_blocks_detail']
    assert (d['reward_atomic'], d['target_seconds'], d['min_difficulty_floor'], d['level']) == (9000000000000, 90, 1, 32)
    assert a == dict(base_blocks=12, ramp_peak_difficulty=33, stable_difficulty=32, root_height=12, root_cumulative_difficulty=312)
    assert [x['difficulty'] for x in base] == [1, 1, 18, 33, 33, 33, 32, 32, 32, 32, 32, 32]
    assert b['stable'] == [32]*4
    assert b['departure_50pct_2x_spacing'] == [32, 30, 29, 27, 26]
    assert b['departure_90pct_10x_spacing'] == [25, 19, 15, 12, 11]
    assert b['recovery_faster_spacing'] == [10]*8 + [11]*7 + [12]*6 + [13]*3
    cumulative = 1  # Genesis work.
    for h, block in enumerate(base + attack, 1):
        cumulative += block['difficulty']
        assert (block['height'], block['cumulative_difficulty']) == (h, cumulative)
        assert block['pow_submits'] >= 1
    assert [x['cumulative_difficulty'] for x in attack] == [344, 376, 408, 440, 472]
    assert all(x['difficulty'] == 32 for x in attack)
    assert (c['main_height'], c['main_cumulative_difficulty'], c['main_blocks'], c['main_added_work'], c['main_last_difficulty']) == (36, 467, 24, 155, 2)
    assert (c['attacker_height'], c['attacker_cumulative_difficulty'], c['attacker_blocks']) == (17, 472, 5)
    assert (c['height_delta_attacker_minus_main'], c['work_delta_attacker_minus_main']) == (-19, 5)
    assert c['switch_at_attacker_block_index'] == next(i for i, x in enumerate(attack) if x['cumulative_difficulty'] > 467) == 4
    assert c['displaced_main_blocks'] == 24 and c['orphan_status_confirmed_via_alt_lookup'] == 5
    assert c['emission_height'] == 17 and c['emission_amount'] == 17 * d['reward_atomic'] == 153000000000000
    assert c['recomputed_cumulative_difficulty'] == cumulative == 472
    assert c['restart_preserved_tip'] is True and len(c['converged_tip_hash']) == 64
    assert c['recovery_after_reorg_difficulty'] == [32]*3
    computed = {
        'AC1_non_floor_variable_difficulty': max(x['difficulty'] for x in base) >= 16 and cumulative > 18,
        'AC2_departure_recovery_response': min(b['departure_50pct_2x_spacing']) < b['stable'][-1] and min(b['departure_90pct_10x_spacing']) < min(b['departure_50pct_2x_spacing']) and b['recovery_faster_spacing'][-1] > min(b['departure_90pct_10x_spacing']),
        'AC3_cumulative_work_not_height_selection': 17 < 36 and 472 > 467 and c['switch_at_attacker_block_index'] == 4 and c['displaced_main_blocks'] == c['main_blocks'],
        # Convergence/restart remain harness-recorded assertions, not independently reconstructed from full logs.
        'AC4_invariants_convergence_restart': c['restart_preserved_tip'] and c['emission_amount'] == 17*9000000000000 and cumulative == c['recomputed_cumulative_difficulty'],
    }
    assert computed == d['criteria'] and all(computed.values()) and d['result'] == 'PASS'
    log = (E / f'reorg-log-run{number}-node0.txt').read_text()
    for text in ['REORGANIZE on height: 13 of 36 with cum_difficulty 467', 'alternative blockchain size: 5 with cum_difficulty 472', 'REORGANIZE SUCCESS! on height: 13, new blockchain size: 18']:
        assert text in log
    runs.append(d)

def structure(value):
    if isinstance(value, dict):
        return {k: structure(v) for k, v in value.items() if k not in ['timestamp', 'pow_submits', 'total_pow_submits', 'converged_tip_hash']}
    if isinstance(value, list):
        return [structure(v) for v in value]
    return value

assert structure(runs[0]) == structure(runs[1])
assert [d['total_pow_submits'] for d in runs] == [750, 536]
print(json.dumps({'status': 'PASS', 'mode': 'frozen evidence readback; no daemon rerun', 'manifest': '9/9', 'original_run_receipts': 'both match', 'criteria_each_run': runs[0]['criteria'], 'chain_structure_repeat': 'identical excluding timestamps, nonce counts, tip hash', 'equal_work_exercised': False, 'full_daemon_logs_available': False, 'convergence_restart_basis': 'retained harness assertions; not independently replayed'}, indent=2))
