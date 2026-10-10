"""Successful observer costs and component timing and unproven-disappearance refusal."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

root = Path(__file__).resolve().parents[3]
source = root / 'build/tjs1882-2493-intel22-supervisor.py'
spec = importlib.util.spec_from_file_location('ci22', source)
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)
cases = []
with tempfile.TemporaryDirectory(prefix='tjs1882-cost22-') as tmp:
    for mode in ('success', 'timeout', 'absence-unproven'):
        out = Path(tmp) / mode
        out.mkdir()
        public = out / 'public'
        public.mkdir()
        if mode == 'success':
            ci.mac_check([sys.executable, '-B', '-c', 'import time;time.sleep(2.5)'], out, public)
            receipt = json.loads((public / 'supervision.json').read_text())
            assert receipt['result'] == 'PASS_WRAPPER_AND_OWNED_CLEANUP'
        else:
            receipt = {}
            argv = [sys.executable, '-B', '-c', "print('PRIVATE_OUTPUT_SENTINEL',flush=True);import time;time.sleep(30)"] if mode == 'timeout' else ['/bin/ps', '-axo', 'pid=,ppid=,ruid=,uid=,lstart=,state=,command=']
            with patch.object(ci.os, 'kill', return_value=None) if mode == 'absence-unproven' else patch.object(ci.os, 'getpid', wraps=ci.os.getpid):
                try: ci.snapshot_output(argv, timeout=5, receipt=receipt, context='INITIAL_OBSERVATION')
                except subprocess.TimeoutExpired: assert mode == 'timeout'
                except AssertionError: assert mode == 'absence-unproven'
                else: raise AssertionError('unproven observer output accepted')
        cost = receipt['snapshot_cost']
        assert len(cost['recent']) <= 8 and cost['calls'] >= len(cost['recent'])
        if mode == 'success': assert cost['calls'] > 8
        for sample in cost['recent']:
            assert sample['spawn_seconds'] >= 0 and sample['communicate_seconds'] >= 0 and sample['reap_seconds'] >= 0
            assert sample['observer_reaped']
            if mode != 'absence-unproven': assert sample['numeric_pid_absent']
        if mode == 'timeout':
            assert cost['recent'][0]['result'] == 'TIMEOUT' and 'output_bytes' not in cost['recent'][0]
        if mode == 'absence-unproven':
            assert receipt['cleanup_failure_type'] == 'OBSERVER_DISAPPEARANCE_UNPROVEN'
        assert 'PRIVATE_' not in json.dumps(receipt)
        cases.append({'case': mode, 'bounded_recent_samples': len(cost['recent']), 'snapshot_calls': cost['calls'],
                      'owned_observer_reaped': True, 'no_partial_output_as_authority': True})
result = {'result': 'PASS', 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
          'cases': cases, 'native_Intel_execution': 'UNTESTED_BY_LINUX_FIXTURES'}
Path(__file__).with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n')
print('PASS_COMPONENT_TIMING_OWNED_OBSERVER_ABSENCE_AND_NO_PARTIAL_AUTHORITY')
