#!/usr/bin/env python3
"""Readiness refusal tests; no daemon/FCMP performance claims."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'spikes/network-benchmark/check-readiness.py'
spec = importlib.util.spec_from_file_location('readiness', MODULE)
readiness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(readiness)


class Profiles(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def source(self, name, target, reward, floor=300000):
        path = self.root / name
        (path / 'src').mkdir(parents=True)
        (path / 'src/cryptonote_config.h').write_text(f'''
#define DIFFICULTY_TARGET_V2 {target}
#define MEOW_BLOCK_REWARD ((uint64_t){reward})
#define CRYPTONOTE_BLOCK_GRANTED_FULL_REWARD_ZONE_V5 {floor}
#define CRYPTONOTE_REWARD_BLOCKS_WINDOW 100
#define CRYPTONOTE_LONG_TERM_BLOCK_WEIGHT_WINDOW_SIZE 100000
''')
        return path

    def test_selected_issuance_matches_but_actual_capacity_does_not(self):
        baseline = self.source('fallback', 120, 12_000_000_000_000)
        candidate = self.source('selected', 90, 9_000_000_000_000)
        result = readiness.report(baseline, candidate)
        self.assertEqual(result['status'], 'BLOCKED_INTEGRATION')
        self.assertFalse(result['launch_ready'])
        self.assertEqual([r['annual_meow_before_penalties'] for r in result['proposed_comparison']], ['3153600'] * 2)
        self.assertEqual(result['baseline_observed']['observed_floor_weight_per_second'], '2500')
        self.assertEqual(result['candidate_observed']['observed_floor_weight_per_second'], '10000/3')
        self.assertTrue(any('capacity normalization is not implemented' in b for b in result['blockers']))
        self.assertTrue(any('different wallclock durations' in b for b in result['blockers']))

    def test_historical_requires_explicit_family(self):
        baseline = self.source('historical', 120, 900_000_000_000)
        selected = readiness.report(baseline)
        self.assertTrue(any('MEOW_BLOCK_REWARD mismatch' in b for b in selected['blockers']))
        historical = readiness.report(baseline, family='historical')
        self.assertEqual(historical['proposed_comparison'][0]['annual_meow_before_penalties'], '236520')
        self.assertFalse(any('MEOW_BLOCK_REWARD mismatch' in b for b in historical['blockers']))

    def test_wrong_profile_refuses_before_p2p(self):
        baseline = self.source('old', 120, 900_000_000_000)
        with self.assertRaisesRegex(ValueError, 'mismatch'):
            readiness.validate_profile(baseline, 'selected-9-90')

    def test_dummy_binary_and_directory_never_prove_readiness(self):
        baseline = self.source('fallback', 120, 12_000_000_000_000)
        candidate = self.source('candidate', 90, 9_000_000_000_000, floor=225000)
        for path in (baseline, candidate):
            (path / 'src/fcmp_pp').mkdir()
            binary = path / 'build/release/bin/monerod'
            binary.parent.mkdir(parents=True)
            binary.write_bytes(b'not a built daemon')
        result = readiness.report(baseline, candidate)
        self.assertFalse(result['launch_ready'])
        self.assertFalse(result['candidate_observed']['binary_source_binding_verified'])
        self.assertTrue(any('No real FCMP' in b for b in result['blockers']))
        self.assertTrue(any('No saturated acceptance' in b for b in result['blockers']))

    def test_missing_and_malformed_source_report_blockers(self):
        path = self.source('bad', 0, 0)
        result = readiness.report(self.root / 'missing', path)
        self.assertIsNone(result['baseline_observed'])
        self.assertTrue(any('mismatch' in b for b in result['blockers']))


if __name__ == '__main__':
    unittest.main()
