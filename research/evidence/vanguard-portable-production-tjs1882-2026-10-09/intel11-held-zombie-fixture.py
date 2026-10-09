"""A real unreaped child stays unverified; only the fixture owner may reap it."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

source = Path(__file__).resolve().parents[3] / 'vanguard/run-portable-ci.py'
spec = importlib.util.spec_from_file_location('ci', source)
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)
pid = os.fork()
if pid == 0:
    os._exit(0)
original_popen, original_output, original_kill = subprocess.Popen, subprocess.check_output, os.kill
wrapper, signals = [], []
try:
    end = time.monotonic() + 5
    while time.monotonic() < end:
        status = original_output(['/bin/ps', '-p', str(pid), '-o', 'state='], text=True).strip()
        if status.startswith('Z'):
            break
        time.sleep(.01)
    assert status.startswith('Z')
    with tempfile.TemporaryDirectory(prefix='tjs1882-intel11-zombie-') as tmp:
        out = Path(tmp)
        public = out / 'public'
        public.mkdir(mode=0o700)
        worker = out / 'worker.py'
        worker.write_text('import time\ntime.sleep(10)\n')

        def popen(*args, **kwargs):
            p = original_popen(*args, **kwargs)
            if args[0][0] == sys.executable and str(worker) in args[0]:
                wrapper.append(p.pid)
            return p

        def snapshot(argv, **kwargs):
            value = original_output(argv, **kwargs)
            if argv[:2] != ['/bin/ps', '-axo'] or not wrapper:
                return value
            rows = []
            for line in value.splitlines():
                row = line.split(None, 10)
                if len(row) == 11 and int(row[0]) == pid:
                    row[1] = str(wrapper[0])  # Only ancestry is injected.
                    line = ' '.join(row)
                rows.append(line)
            return '\n'.join(rows)

        def kill(target, number):
            if target == pid and number:
                signals.append(int(number))
            return original_kill(target, number)

        subprocess.Popen, subprocess.check_output, os.kill = popen, snapshot, kill
        try:
            ci.mac_check([sys.executable, '-B', worker], out, public, timeout=2, cleanup_seconds=.2)
        except AssertionError:
            pass
        receipt = json.loads((public / 'supervision.json').read_text())
        assert receipt['failure_reason'] == 'UNVERIFIED_FIRST_ZOMBIE'
        assert receipt['failure_observation']['pid'] == pid and not signals
        assert receipt['rejected_observation_cleanup'] == [{'pid': pid, 'removed': False,
            'proof': 'PRESENT_UNVERIFIED_NEVER_SIGNALLED'}]
        assert 'cleanup_failure_type' in receipt and receipt['wrapper_reaped']
finally:
    subprocess.Popen, subprocess.check_output, os.kill = original_popen, original_output, original_kill
    assert os.waitpid(pid, 0)[0] == pid
    try:
        os.kill(pid, 0)
        raise AssertionError('fixture zombie remains')
    except ProcessLookupError:
        pass
result = {'schema': 'meownero-intel11-real-held-zombie-fixture/1',
          'result': 'PASS_REJECT_ACCOUNT_NO_SIGNAL_RETAIN_UNTIL_OWNER_REAP',
          'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
          'actual_unreaped_zombie': True, 'ps_metadata': 'ONLY_PARENT_INJECTED',
          'signals_to_unverified_pid': signals, 'fixture_owner_reaped': True,
          'native_Intel_journey': 'UNTESTED'}
Path(__file__).with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n')
print(result['result'])
