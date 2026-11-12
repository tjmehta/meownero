"""F3 unmocked procfs/CLI probe. Sleeping stand-in only; no native seed."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT/'vanguard/network'))
from integration import test_operator as tests
from integration import operator_contract as o


def banner(moment):
    return (moment.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]+
            "\tmain\tINFO\tglobal\tsrc/daemon/main.cpp:298\tMonero 'stand-in' (v0.18)\n").encode()


rows = []
with tempfile.TemporaryDirectory(prefix='TJS-4398-f3-cli-') as tmp:
    temp = Path(tmp)
    source = temp/'stand-in.c'
    source.write_text('#include <unistd.h>\nint main(void){sleep(120);return 0;}\n')
    subprocess.run(['/usr/bin/cc', str(source), '-o', str(temp/'monerod')], check=True)
    log, plan = temp/'native.log', temp/'plan.json'
    plan.write_text(json.dumps(o.plan(o.SEED_IP)))
    argv = tests.swap(tests.public(), '--log-file', str(log))
    argv[0] = str(temp/'monerod')

    def run(label, pid, raw, zone, expected, path=log):
        path.write_bytes(raw)
        result = subprocess.run([sys.executable, '-B', '-m', 'integration.activation_witness',
            '--pid', str(pid), '--log-file', str(path), '--plan-file', str(plan)],
            cwd=ROOT, env={'PYTHONPATH': str(ROOT/'vanguard/network'), 'TZ': zone},
            capture_output=True, text=True, timeout=10)
        row = dict(case=label, zone=zone, pid=pid, exit=result.returncode,
                   result=json.loads(result.stdout), stderr=result.stderr)
        rows.append(row)
        assert result.returncode == expected, row
        assert not result.stderr, row

    for zone in ('UTC', 'America/Los_Angeles', 'Europe/Berlin', 'Asia/Tokyo'):
        proc = subprocess.Popen(argv)
        try:
            time.sleep(0.1)  # Stand-in banner safely after the procfs start tick.
            now = datetime.now(timezone.utc)
            old = banner(now-timedelta(hours=1))
            current = banner(now)
            dial = b'I Connect failed to 176.9.0.187:28080\n'
            tail = b'I peer list loaded; retained white peers\n'
            run('UTC-stamped clean launch', proc.pid, current+tail, zone, 0)
            run('UTC-stamped upstream dial', proc.pid, current+dial, zone, 2)
            run('old launch only', proc.pid, old+tail, zone, 3)
            run('old upstream dial excluded', proc.pid, old+dial+current+tail, zone, 0)
            run('ambiguous current banners', proc.pid, current+current, zone, 3)
            # Emulate the fork's rename and continued writing at the same path.
            log.write_bytes(current+tail)
            rotated = temp/'native.log-2026-11-12-00-00-00'
            log.replace(rotated)
            run('rotated banner absent from running file', proc.pid, tail, zone, 3)
            run('rotated file refused as running file', proc.pid, current+tail, zone, 3, rotated)
            run('concatenated copy refused', proc.pid, current+tail, zone, 3, temp/'joined.log')
        finally:
            proc.terminate()
            proc.wait(timeout=5)
        # Execute the recovery's process/log boundary with actual new procfs
        # identity; accepted supervisor seal/attest behavior is not reimplemented.
        prior_pid = proc.pid
        proc = subprocess.Popen(argv)
        try:
            assert proc.pid != prior_pid
            time.sleep(0.1)
            current = banner(datetime.now(timezone.utc))
            run('planned restart new PID and banner no seed pass', proc.pid, tail+current+tail, zone, 0)
            run('planned restart still detects upstream dial', proc.pid, tail+current+dial, zone, 2)
        finally:
            proc.terminate()
            proc.wait(timeout=5)

print(json.dumps(dict(result='PASS', native_seed='NOT_RUN',
    recovery='planned restart with a new PID and a fresh UTC banner in the running file',
    supervisor_seal_attestation='not exercised by stand-in', cases=rows), indent=2))
