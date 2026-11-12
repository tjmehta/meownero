"""Unmocked procfs/CLI probe with a sleeping stand-in, not a native seed run."""
from datetime import datetime, timedelta
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
with tempfile.TemporaryDirectory(prefix='TJS-4398-correction-cli-') as tmp:
    temp = Path(tmp)
    source = temp/'stand-in.c'
    source.write_text('#include <unistd.h>\nint main(void){sleep(120);return 0;}\n')
    subprocess.run(['/usr/bin/cc', str(source), '-o', str(temp/'monerod')], check=True)
    log, plan = temp/'native.log', temp/'plan.json'
    plan.write_text(json.dumps(o.plan(o.SEED_IP)))
    args = tests.swap(tests.public(), '--log-file', str(log))
    args[0] = str(temp/'monerod')

    def run(label, pid, raw, expected, path=log):
        path.write_bytes(raw)
        result = subprocess.run([sys.executable, '-B', '-m', 'integration.activation_witness',
            '--pid', str(pid), '--log-file', str(path), '--plan-file', str(plan)],
            cwd=ROOT, env={'PYTHONPATH': str(ROOT/'vanguard/network')},
            capture_output=True, text=True, timeout=10)
        row = dict(case=label, exit=result.returncode, result=json.loads(result.stdout), stderr=result.stderr)
        rows.append(row)
        assert result.returncode == expected, row
        assert not result.stderr, row

    for level in ('1', 'net.p2p:WARNING', '1,net.p2p:WARNING', '*:WARNING'):
        argv = tests.swap(args, '--log-level', level)
        proc = subprocess.Popen(argv)
        try:
            time.sleep(0.1)  # Header is safely past procfs start tick for this stand-in.
            now = datetime.now()
            old = banner(now-timedelta(hours=1))+b'W continuing without seeds\n'
            current = banner(now)
            if level != '1':
                run('warning-only '+level, proc.pid, current+b'W continuing without seeds\n', 3)
                continue
            run('first launch', proc.pid, current+b'W continuing without seeds\n', 0)
            run('restart without seed pass', proc.pid, current, 0)
            run('old launch cannot supply coverage', proc.pid, old, 3)
            run('accumulated multi-launch', proc.pid, old+current, 0)
            run('old launch dial excluded', proc.pid, old+b'I Connect failed to 176.9.0.187:28080\n'+current, 0)
            run('current launch upstream dial', proc.pid, old+current+b'I Connect failed to 176.9.0.187:28080\n', 2)
            run('benign housekeeping and ping-back', proc.pid, current+b'I Connect failed to 203.0.113.10:48080\nW back ping connect failed to 198.51.100.5:48080\n', 0)
            run('missing header', proc.pid, b'W continuing without seeds\n', 3)
            run('wrong log path', proc.pid, current, 3, temp/'other.log')
        finally:
            proc.terminate(); proc.wait(timeout=5)
    run('dead pid', proc.pid, current, 3)
print(json.dumps(dict(result='PASS', native_seed='NOT_RUN', stand_in_source=source.read_text() if source.exists() else '#include <unistd.h>\nint main(void){sleep(120);return 0;}\n', cases=rows), indent=2))
