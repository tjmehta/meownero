#!/usr/bin/env python3
"""Inventory actual source profiles; exit 2 until paired network integration exists.

Selected defaults to 12/120 fallback versus 9/90. Historical controls are opt-in.
Neither source constants nor a binary's presence proves its build provenance.
"""
import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re

PROFILES = {
    'historical-0.9-120': (120, 900_000_000_000),
    'historical-0.675-90': (90, 675_000_000_000),
    'fallback-12-120': (120, 12_000_000_000_000),
    'selected-9-90': (90, 9_000_000_000_000),
}
FIELDS = ['DIFFICULTY_TARGET_V2', 'MEOW_BLOCK_REWARD',
          'CRYPTONOTE_BLOCK_GRANTED_FULL_REWARD_ZONE_V5',
          'CRYPTONOTE_REWARD_BLOCKS_WINDOW',
          'CRYPTONOTE_LONG_TERM_BLOCK_WEIGHT_WINDOW_SIZE']


def inspect(source):
    config_path = source / 'src/cryptonote_config.h'
    config = config_path.read_text()
    values = {}
    for name in FIELDS:
        match = re.search(r'^#define\s+' + name + r'\s+(?:\(\(uint64_t\))?(\d+)', config, re.M)
        values[name] = int(match[1]) if match else None
    binary = source / 'build/release/bin/monerod'
    values['binary_sha256'] = None
    if binary.is_file():
        with binary.open('rb') as stream:
            values['binary_sha256'] = hashlib.file_digest(stream, 'sha256').hexdigest()
    values['config_sha256'] = hashlib.sha256(config_path.read_bytes()).hexdigest()
    values['binary_source_binding_verified'] = False
    values['fcmp_source_directory_present'] = (source / 'src/fcmp_pp').is_dir()
    target = values['DIFFICULTY_TARGET_V2']
    floor = values['CRYPTONOTE_BLOCK_GRANTED_FULL_REWARD_ZONE_V5']
    values['observed_floor_weight_per_second'] = str(Fraction(floor, target)) if floor and target else None
    values['observed_window_seconds'] = {
        name: values[name] * target if values[name] and target else None
        for name in FIELDS[-2:]
    }
    return values


def validate_profile(source, profile):
    values = inspect(source)
    target, reward = PROFILES[profile]
    for key, expected in [('DIFFICULTY_TARGET_V2', target), ('MEOW_BLOCK_REWARD', reward)]:
        if values[key] != expected:
            raise ValueError(f'{profile}: {key} mismatch: {values[key]} != {expected}')
    return values


def report(source, candidate_source=None, family='selected'):
    names = ('fallback-12-120', 'selected-9-90') if family == 'selected' else ('historical-0.9-120', 'historical-0.675-90')
    blockers = [
        'No real FCMP transaction/proof workload receipts or instrumented validation/relay timings.',
        'No saturated acceptance/rejection probes proving 0.75 capacity ratio through floor, short median, long median and surge states.',
        'No paired actual 90/120 loaded network run with shared transaction/proof mix and wallclock horizon.',
        'Full binary/source binding, wallet/fee integration and native difficulty/timeout recovery remain unverified.',
    ]
    observed = []
    rows = []
    for path, name in zip((source, candidate_source), names):
        target, reward = PROFILES[name]
        # This is an experimental budget proposal, never an observed/configured capacity rule.
        proposed_floor = 300_000 * target // 120
        rows.append(dict(profile=name, target_seconds=target, reward_atomic=reward,
                         issuance_atomic_per_second=str(Fraction(reward, target)),
                         annual_meow_before_penalties=str(Fraction(reward * 365 * 86400, target * 10**12)),
                         proposed_penalty_free_weight=proposed_floor,
                         proposed_maximum_weight_at_floor=2 * proposed_floor,
                         proposed_floor_weight_per_second=str(Fraction(proposed_floor, target)),
                         confirmation_horizon_3600s_blocks=3600 // target,
                         capacity_enforcement_tested=False))
        if path is None:
            observed.append(None)
            blockers.append(f'No separate {name} source supplied.')
            continue
        try:
            values = inspect(path)
            observed.append(values)
            validate_profile(path, name)
        except (OSError, ValueError) as error:
            if len(observed) < len(rows):
                observed.append(None)
            blockers.append(str(error))
            continue
        if values['CRYPTONOTE_BLOCK_GRANTED_FULL_REWARD_ZONE_V5'] != proposed_floor:
            blockers.append(f'{name}: observed floor differs from proposed matched-time budget; capacity normalization is not implemented.')
        if not values['binary_sha256']:
            blockers.append(f'{name}: daemon is not built.')
        if not values['fcmp_source_directory_present']:
            blockers.append(f'{name}: no src/fcmp_pp integration.')
    if all(observed) and observed[0]['observed_window_seconds'] != observed[1]['observed_window_seconds']:
        blockers.append('Observed short/long median windows span different wallclock durations; no rounding/scaling policy selected.')
    return dict(status='BLOCKED_INTEGRATION', family=family, launch_ready=False,
                baseline_observed=observed[0], candidate_observed=observed[1],
                proposed_comparison=rows, blockers=blockers)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='read-only 120-second source for the chosen family')
    parser.add_argument('--candidate-source', type=Path, help='separate 90-second source')
    parser.add_argument('--family', choices=['selected', 'historical'], default='selected')
    args = parser.parse_args()
    print(json.dumps(report(args.source, args.candidate_source, args.family), indent=2))
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
