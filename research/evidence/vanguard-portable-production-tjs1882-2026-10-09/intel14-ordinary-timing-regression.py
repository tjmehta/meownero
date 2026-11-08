"""Owned Darwin regression of real native preflight at ordinary process timing.

Run through existing writer SSH capability; no heavy build, lock, held helper,
private wallet journey, or actual failed Intel PID identity claim.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import sys

assert platform.system() == 'Darwin'
probe = Path('~/Developer/tjs1882-3175/mac-observer-normal-lifecycle12')
source = probe / 'corrected14-quarantine-ci.py'
expected = sys.argv[1]
assert hashlib.sha256(source.read_bytes()).hexdigest() == expected
spec = importlib.util.spec_from_file_location('ci14', source)
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)
cases = []
for number in range(10):
    out = probe / ('final14c-%02d' % number)
    out.mkdir(mode=0o700)
    public = out / 'public'
    public.mkdir(mode=0o700)
    native = out / 'native-check'
    ci.mac_check([sys.executable, '-B', probe / 'preflight-worker.py', native,
                  probe / 'package/meownero-vanguard-macos-aarch64'],
                 out, public, timeout=30, cleanup_seconds=30)
    supervision = json.loads((public / 'supervision.json').read_text())
    phases = json.loads((native / 'check-receipt.json').read_text())['phases']
    assert len(phases) == 5 and all(row['exit'] == 0 for row in phases)
    assert supervision['result'] == 'PASS_WRAPPER_AND_OWNED_CLEANUP'
    assert supervision['wrapper_reaped'] and all(row['removed'] for row in supervision['cleanup'])
    assert all(row['removed'] for row in supervision.get('rejected_observation_cleanup', []))
    cases.append({'case': number, 'five_actual_native_preflights': 'PASS',
                  'wrapper_reaped_and_all_recorded_observations_absent': True,
                  'approved_helper_observations': len(supervision['helper_observations']),
                  'independently_absent_stale_snapshots': len(supervision['unverified_observations'])})
result = {'schema': 'meownero-intel14-ordinary-darwin-preflight-regression/1',
          'result': 'PASS_50_NATIVE_PREFLIGHTS_ORDINARY_TIMING_VERIFIED_CLEANUP',
          'supervisor_sha256': expected,
          'preflight_worker_sha256': hashlib.sha256((probe / 'preflight-worker.py').read_bytes()).hexdigest(),
          'package_tester_sha256': hashlib.sha256((probe / 'package/meownero-vanguard-macos-aarch64/tester.py').read_bytes()).hexdigest(),
          'cases': cases, 'host': 'Darwin_ARM64',
          'actual_failed_Intel_PID4071_identity': 'UNKNOWN', 'physical_Intel_journey': 'UNTESTED'}
(probe / 'intel14-ordinary-timing-regression.json').write_text(json.dumps(result, indent=2) + '\n')
print(result['result'])
