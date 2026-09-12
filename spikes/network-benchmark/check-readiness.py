#!/usr/bin/env python3
"""Report exact matched-budget arithmetic and local integration blockers.

Exit 2 means blocked. This deliberately cannot turn source availability or
synthetic timing into a successful FCMP workload measurement.
"""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, required=True, help='read-only current 120-second source')
parser.add_argument('--candidate-source', type=Path, help='separate 90-second experimental source, if built')
args = parser.parse_args()


def inspect(source):
    config = (source / 'src/cryptonote_config.h').read_text()
    values = {}
    for name in ['DIFFICULTY_TARGET_V2', 'MEOW_BLOCK_REWARD', 'CRYPTONOTE_BLOCK_GRANTED_FULL_REWARD_ZONE_V5',
                 'CRYPTONOTE_REWARD_BLOCKS_WINDOW', 'CRYPTONOTE_LONG_TERM_BLOCK_WEIGHT_WINDOW_SIZE']:
        match = re.search(r'^#define\s+' + name + r'\s+(?:\(\(uint64_t\))?(\d+)', config, re.M)
        values[name] = int(match[1]) if match else None
    binary = source / 'build/release/bin/monerod'
    values['binary_sha256'] = hashlib.file_digest(binary.open('rb'), 'sha256').hexdigest() if binary.exists() else None
    values['fcmp_source_directory_present'] = (source / 'src/fcmp_pp').is_dir()
    return values


baseline = inspect(args.source)
candidate = inspect(args.candidate_source) if args.candidate_source else None
assert baseline['DIFFICULTY_TARGET_V2'] == 120
assert baseline['MEOW_BLOCK_REWARD'] == 900_000_000_000
floor = baseline['CRYPTONOTE_BLOCK_GRANTED_FULL_REWARD_ZONE_V5']
assert floor == 300000
rows = []
for target, reward in [(120, 900_000_000_000), (90, 675_000_000_000)]:
    scale = Fraction(target, 120)
    median = int(floor * scale)
    rows.append(dict(target_seconds=target, reward_atomic=reward,
                     issuance_atomic_per_second=str(Fraction(reward, target)),
                     configured_minimum_penalty_free_weight=median,
                     configured_max_weight_at_floor=2 * median,
                     penalty_free_weight_per_second=str(Fraction(median, target)),
                     maximum_weight_per_second_at_floor=str(Fraction(2 * median, target)),
                     confirmation_horizon_3600s_blocks=3600 // target,
                     maximum_budget_enforcement_tested=False,
                     dynamic_median_ratio_enforcement_tested=False))
assert rows[0]['issuance_atomic_per_second'] == rows[1]['issuance_atomic_per_second']
assert rows[0]['maximum_weight_per_second_at_floor'] == rows[1]['maximum_weight_per_second_at_floor']
blockers = ['No real FCMP transaction/proof workload receipts or instrumented validation/relay timings.',
            'No saturated acceptance/rejection boundary probes proving 0.75 capacity ratio through floor, short median, long median and surge states.',
            'No paired actual 90/120 network workload run with shared transaction/proof mix and wallclock horizon.']
if candidate is None:
    blockers.append('No separately built 90-second / 0.675 candidate source supplied.')
else:
    for name, wanted in [('DIFFICULTY_TARGET_V2', 90), ('MEOW_BLOCK_REWARD', 675_000_000_000),
                         ('CRYPTONOTE_BLOCK_GRANTED_FULL_REWARD_ZONE_V5', 225000)]:
        if candidate[name] != wanted:
            blockers.append(f'Candidate {name} mismatch: {candidate[name]} != {wanted}.')
    if not candidate['binary_sha256']:
        blockers.append('Candidate daemon is not built.')
if not baseline['fcmp_source_directory_present']:
    blockers.append('Current pinned source has no src/fcmp_pp integration.')
print(json.dumps(dict(status='BLOCKED_INTEGRATION', baseline_observed=baseline,
                      candidate_observed=candidate, configured_comparison=rows,
                      blockers=blockers), indent=2))
raise SystemExit(2)
