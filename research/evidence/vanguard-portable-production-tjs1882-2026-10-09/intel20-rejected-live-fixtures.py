"""Execute the real supervisor and lock finalizer with an owned live PID.

Only ps ancestry/effective-UID metadata is injected. The observer must never
signal that unverified PID; the fixture owns and reaps it independently.
"""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import signal
import tempfile
import time

root = Path(__file__).resolve().parents[3]
source = root / 'build/tjs1882-3175-intel20-supervisor.py'
spec = importlib.util.spec_from_file_location('ci', source)
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)
tree = ast.parse(source.read_text())
main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
finalizer = next(n.finalbody for n in ast.walk(main) if isinstance(n, ast.Try) and
                 any(isinstance(q, ast.Call) and getattr(q.func, 'attr', None) == 'unlink'
                     for q in ast.walk(ast.Module(body=n.finalbody, type_ignores=[]))))
lock_code = compile(ast.Module(body=finalizer, type_ignores=[]), str(source), 'exec')
cases = []
with tempfile.TemporaryDirectory(prefix='tjs1882-intel20-owned-') as tmp:
    for transition, should_disappear in ((m, absent) for m in ('unchanged', 'normal-euid', 'reused-start') for absent in (True, False)):
        out = Path(tmp) / (transition + '-' + str(should_disappear))
        out.mkdir(mode=0o700)
        public = out / 'public'
        public.mkdir(mode=0o700)
        worker = out / 'worker.py'
        worker.write_text('import signal,sys,time\ndef stop(n,f):\n time.sleep(.5)\n sys.exit(0)\nsignal.signal(signal.SIGTERM,stop)\ntime.sleep(10)\n')
        child = subprocess.Popen([sys.executable, '-B', '-c', 'import time;time.sleep(10)'])
        original_popen, original_output, original_kill = subprocess.Popen, subprocess.check_output, os.kill
        wrapper, signals, observations = [], [], []
        began = time.monotonic()

        def popen(*args, **kwargs):
            p = original_popen(*args, **kwargs)
            if args[0][0] == sys.executable and str(worker) in args[0]:
                wrapper.append(p.pid)
            return p

        def snapshot_output(argv, **kwargs):
            # A source-bound adverse observation; never actual native UID proof.
            if should_disappear and time.monotonic() - began > .35 and child.poll() is None:
                original_kill(child.pid, 15)  # Fixture owner, not supervisor authority.
                child.wait(timeout=5)
            output = original_output(argv, **kwargs)
            if argv[:2] != ['/bin/ps', '-axo'] or not wrapper:
                return output
            lines = []
            for line in output.splitlines():
                parts = line.split(None, 10)
                if len(parts) == 11 and int(parts[0]) == child.pid:
                    parts[1], parts[2], parts[3] = str(wrapper[0]), str(os.getuid()), str(os.geteuid() + 1)
                    if observations and transition == 'normal-euid':
                        parts[3] = str(os.geteuid())
                    if observations and transition == 'reused-start':
                        parts[8] = '1999'
                    observations.append(True)
                    parts[10] = 'UNAPPROVED_HELPER_PRIVATE_SENTINEL'
                    line = ' '.join(parts)
                lines.append(line)
            return '\n'.join(lines)

        def kill(pid, number):
            if pid == child.pid and number != 0:
                signals.append(int(number))
            return original_kill(pid, number)

        subprocess.Popen, subprocess.check_output, os.kill = popen, snapshot_output, kill
        try:
            try:
                ci.mac_check([sys.executable, '-B', worker], out, public, timeout=2, cleanup_seconds=1)
            except BaseException:
                pass
        finally:
            subprocess.Popen, subprocess.check_output, os.kill = original_popen, original_output, original_kill
        receipt = json.loads((public / 'supervision.json').read_text())
        assert receipt['result'] == 'FAIL' and receipt['failure_reason'] == 'EFFECTIVE_UID_NOT_ALLOWLISTED'
        assert receipt['failure_observation']['pid'] == child.pid and not signals
        assert all(row['pid'] != child.pid for row in receipt['cleanup']), 'quarantined PID promoted to known'
        if transition != 'unchanged':
            assert any(row['role'] == 'PERMANENTLY_QUARANTINED_OBSERVATION' and
                       row['identity_state'] == 'INITIAL_ANCESTRY_UID_OR_START_CHANGED'
                       for row in receipt['unverified_observations'])
        observed = receipt['rejected_observation_cleanup']
        assert observed == [{'pid': child.pid, 'removed': should_disappear,
                             'proof': 'ACTUAL_PID_ABSENCE' if should_disappear else 'PRESENT_UNVERIFIED_NEVER_SIGNALLED'}]
        lock = out / 'owned.lock'
        lock.touch(mode=0o600)
        proof = {}
        namespace = dict(json=json, public=public, lock=lock, lock_identity=lock.stat().st_ino,
                         os=os, signal=signal, proof=proof)
        try:
            exec(lock_code, namespace)
        except AssertionError:
            assert not should_disappear
        assert lock.exists() != should_disappear
        assert 'PRIVATE_SENTINEL' not in json.dumps(receipt)
        cases.append({'case': transition + ('-reaped' if should_disappear else '-remains'),
                      'unverified_pid_signals': signals, 'actual_absence': should_disappear,
                      'lock_removed': not lock.exists(), 'wrapper_reaped': receipt['wrapper_reaped'],
                      'cleanup_failure_recorded': 'cleanup_failure_type' in receipt})
        if child.poll() is None:
            child.terminate()
        child.wait(timeout=5)
result = {'schema': 'meownero-intel20-rejected-live-cleanup-fixtures/1',
          'result': 'PASS_REJECT_ACCOUNT_NO_SIGNAL_VERIFIED_ABSENCE_OR_RETAIN_LOCK',
          'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'cases': cases,
          'ps_metadata': 'INJECTED_ADVERSE_UID_AND_ANCESTRY_ONLY',
          'unverified_pid': 'ACTUAL_OWNED_PROCESS_INDEPENDENTLY_REAPED', 'native_Intel_journey': 'UNTESTED'}
Path(__file__).with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n')
print(result['result'])
