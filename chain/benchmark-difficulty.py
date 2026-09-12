"""Paired 90s/0.675 vs 120s/0.9 models using the compiled production DAA.

Simulates hashrate arrivals, not real miners, transactions or a peer network.
Floor alternatives are model-only proposals; shipped consensus is never modified.
"""
import ctypes
import json
import math
from pathlib import Path
import random
import statistics
import sys
import time

H = 5_000_000  # assumed hashes/second, not measured launch commitment
YEAR = 365 * 24 * 3600
PAIRINGS = [(90, 675_000_000_000), (120, 900_000_000_000)]
SCENARIOS = {
    'steady': [(24 * 3600, H)],
    'late_join': [(3600, 10_000), (24 * 3600, H)],
    'whiplash': [(6 * 3600, H), (8 * 3600, H * 10), (24 * 3600, H)],
    'disappear_recover_low': [(6 * 3600, H), (8 * 3600, 0), (16 * 3600, H // 100), (24 * 3600, H)],
    'future_20pct': [(24 * 3600, H)],
    'future_50pct': [(24 * 3600, H)],
}


def native_function(path):
    library = ctypes.CDLL(path)
    fn = library.meow_next_difficulty
    fn.argtypes = [ctypes.POINTER(ctypes.c_uint64), ctypes.POINTER(ctypes.c_uint64),
                   ctypes.c_size_t, ctypes.c_size_t]
    fn.restype = ctypes.c_uint64

    def difficulty(ts, work, target):
        assert len(ts) == len(work) <= 735
        array = ctypes.c_uint64 * len(ts)
        result = fn(array(*ts), array(*work), len(ts), target)
        assert result > 0, 'native DAA overflow/unsupported 64-bit model range'
        return result
    return difficulty


def block_time(now, hashes, schedule):
    # Integrate the exponential work draw across hashrate changes; a block that
    # finishes after the horizon is not counted, and zero hashrate mines nothing.
    for end, rate in schedule:
        if end <= now:
            continue
        if rate and hashes <= (end - now) * rate:
            completion = now + hashes / rate
            return completion if completion < schedule[-1][0] else None
        hashes -= (end - now) * rate
        now = end
    return None


def simulate(native, target, reward, policy, scenario, seed):
    rng = random.Random(seed)
    attacks = random.Random(seed + 100_000)
    timestamps, cumulative = [0], [1]  # genesis has difficulty one and zero reward
    now = 0.0
    intervals, hours = [], [0] * 24
    floor = H * target // 4
    while True:
        # Match the caller: skip genesis, last 735 samples; native code keeps first 720.
        start = max(1, len(timestamps) - 735)
        d = native(timestamps[start:], cumulative[start:], target)
        if policy == 'permanent' or (policy == 'startup_720' and len(timestamps) <= 720):
            d = max(d, floor)
        mined_at = block_time(now, rng.expovariate(1.0) * d, SCENARIOS[scenario])
        if mined_at is None:
            break
        share = 0.2 if scenario == 'future_20pct' else 0.5 if scenario == 'future_50pct' else 0
        stamp = int(mined_at) + (7200 if attacks.random() < share else 0)
        if len(timestamps) >= 60:
            # Native rule accepts equality with median (not median + 1).
            stamp = max(stamp, int(statistics.median(timestamps[-60:])))
        assert stamp <= int(mined_at) + 7200
        timestamps.append(stamp)
        cumulative.append(cumulative[-1] + d)
        assert cumulative[-1] < 2**64
        intervals.append(mined_at - now)
        hours[int(mined_at // 3600)] += 1
        now = mined_at
    count = len(timestamps) - 1
    assert count == sum(hours)
    return {'target_seconds': target, 'reward_atomic': reward, 'policy': policy,
            'scenario': scenario, 'seed': seed, 'blocks': count, 'issuance_atomic': count * reward,
            'blocks_by_hour': hours, 'peak_hour_blocks': max(hours),
            'longest_gap_seconds': max([24 * 3600 - now, *intervals]),
            'cumulative_work': cumulative[-1]}


def percentile(values, fraction):
    return sorted(values)[math.ceil(fraction * len(values)) - 1]


if __name__ == '__main__':
    native = native_function(sys.argv[1])
    for target, reward in PAIRINGS:
        assert YEAR % target == 0
        assert YEAR // target * reward == 236_520 * 10**12
        assert native([], [], target) == 1
        assert native([0, 120], [0, 1_000_000_000], target) == target * 1_000_000_000 // 120
    assert block_time(0, 10, [(10, 0), (20, 1)]) is None  # horizon is exclusive
    assert block_time(0, 9, [(10, 0), (20, 1)]) == 19
    started = time.monotonic()
    rows, summaries = [], []
    for scenario in SCENARIOS:
        for policy in ('shipped_floor_1', 'permanent', 'startup_720'):
            for target, reward in PAIRINGS:
                group = [simulate(native, target, reward, policy, scenario, seed) for seed in range(20)]
                rows.extend(group)
                summary = {'scenario': scenario, 'policy': policy, 'target_seconds': target,
                           'seeds': len(group), 'mean_blocks': statistics.mean(r['blocks'] for r in group),
                           'mean_issuance_meow': statistics.mean(r['issuance_atomic'] for r in group) / 10**12,
                           'p95_longest_gap_seconds': percentile([r['longest_gap_seconds'] for r in group], .95),
                           'mean_peak_hour_blocks': statistics.mean(r['peak_hour_blocks'] for r in group)}
                summaries.append(summary)
                print(json.dumps(summary), flush=True)
    paired = []
    for scenario in SCENARIOS:
        for policy in ('shipped_floor_1', 'permanent', 'startup_720'):
            samples = {target: sorted((r for r in rows if r['scenario'] == scenario and
                       r['policy'] == policy and r['target_seconds'] == target), key=lambda r: r['seed'])
                       for target, _ in PAIRINGS}
            differences = [(a['issuance_atomic'] - b['issuance_atomic']) / 10**12
                           for a, b in zip(samples[90], samples[120])]
            mean = statistics.mean(differences)
            margin = 2.093 * statistics.stdev(differences) / math.sqrt(len(differences))
            paired.append({'scenario': scenario, 'policy': policy,
                           'mean_90_minus_120_meow': mean, 'approximate_95pct_mean_ci': [mean - margin, mean + margin]})
    result = {'scope': 'native DAA, simulated hashrates and clocks; no P2P, proofs, capacity or selfish mining',
              'assumed_hashrate': H, 'expected_annual_meow_both': 236520,
              'seeds': list(range(20)), 'seconds': time.monotonic() - started,
              'floor_alternatives': 'model only: H*target/4 permanent or blocks 1..720; not adopted',
              'summaries': summaries, 'paired_issuance_differences': paired, 'runs': rows}
    Path(sys.argv[2]).write_text(json.dumps(result, indent=2) + '\n')
