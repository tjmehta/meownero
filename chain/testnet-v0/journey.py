#!/usr/bin/env python3
"""TJS-313: one-command testnet v0 operator journey; the five accepted milestone recipes in order, one output directory, one manifest pair."""
import argparse
import datetime
import fcntl
import importlib
import json
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

import launch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
payment = importlib.import_module('payment')
recover = importlib.import_module('recover')
pool_restart = importlib.import_module('pool-restart')
RECIPE_MANIFEST = ROOT / 'research/evidence/testnet-v0-launch-tjs229-2026-09-20/launch/INPUTS.sha256'
RECIPE_MANIFEST_SHA = '1e3b8a784828b05634abd4b4ac22ba7cc83652b32af023c71c146f3216a5e59f'
NEW_FILES = ['journey.py', 'verify-journey.py', 'test-journey-refusals.py', 'journey.md']
LOCK = '/tmp/meownero-swarm-20260912-heavy.lock'  # the existing shared heavy-work lock, taken by each step itself
CONTROL = 'PASS: five accepted recipe admissions, profile, binaries, builder image and baseline inputs verified; no process started'
save, require, digest = launch.save, launch.require, launch.digest
# The five accepted milestone recipes in freeze order. Each one runs unchanged as its own process and its own
# container on its own fresh two-peer chain from the same genesis; the recipes refuse existing node state and their
# verifiers require a fresh-genesis readback, so the journey sequences them and rolls their receipts up. It never
# reuses a daemon, a data directory or a run directory. Bounds are each recipe's container wall limit plus its forced
# cleanup; the accepted seconds are the container elapsed times of the accepted TJS-229/230/242/287/297 runs.
STEPS = [
    {'name': '01-launch', 'milestone': 'M1 TJS-229 two-peer launch', 'script': 'launch.py', 'verifier': 'verify.py',
     'binaries': ('binary',), 'profile': True, 'bound_seconds': 420 + 75, 'accepted_seconds': 25.4,
     'control': 'PASS: profile, binary and baseline inputs verified; no process started'},
    {'name': '02-payment', 'milestone': 'M2 TJS-230 payment, seed restore, reopen', 'script': 'payment.py', 'verifier': 'verify-payment.py',
     'binaries': ('binary', 'wallet'), 'profile': False, 'bound_seconds': payment.RUN_LIMIT_SECONDS + 150, 'accepted_seconds': 10004.9,
     'control': 'PASS_ADMISSION: accepted recipe manifest, daemon, wallet and profile pinned'},
    {'name': '03-sync', 'milestone': 'M3 TJS-242 late peer sync and restart', 'script': 'sync.py', 'verifier': 'verify-sync.py',
     'binaries': ('binary',), 'profile': True, 'bound_seconds': 1500 + 75, 'accepted_seconds': 164.6,
     'control': 'PASS: accepted recipe manifest, profile, binary and baseline inputs verified; no process started'},
    {'name': '04-recover', 'milestone': 'M4 TJS-287 cold backup/restore and payout wallet', 'script': 'recover.py', 'verifier': 'verify-recover.py',
     'binaries': ('binary', 'wallet'), 'profile': True, 'bound_seconds': recover.RUN_LIMIT_SECONDS + 75, 'accepted_seconds': 45.0,
     'control': 'PASS: accepted recipe manifest, profile, binary, wallet and baseline inputs verified; no process started'},
    {'name': '05-pool-restart', 'milestone': 'M5 TJS-297 pool restart at the common tip', 'script': 'pool-restart.py', 'verifier': 'verify-pool-restart.py',
     'binaries': ('binary', 'pool'), 'profile': True, 'bound_seconds': pool_restart.RUN_LIMIT_SECONDS + 75, 'accepted_seconds': 41.3,
     'control': 'PASS: accepted recipe manifest, profile, binary, pool and baseline inputs verified; no process started'},
]


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')


def step_command(step, args, work):
    """The recipe's own command line; payment.py reads the recipe profile directly and admits only an exact copy."""
    cmd = [sys.executable, '-B', str(HERE / step['script']), '--work', str(work / step['name'])]
    for kind in step['binaries']:
        cmd += [f'--{kind}', str(getattr(args, kind))]
    if step['profile']:
        cmd += ['--profile', str(args.profile)]
    return cmd


def admission(args, work):
    """Shared pins first, then every recipe's own --check-only, then the builder image; nothing is started."""
    manifest = launch.preflight(args.binary, args.profile)
    require(digest(args.wallet) == payment.WALLET_SHA, f'wallet SHA-256 mismatch: expected {payment.WALLET_SHA}')
    require(digest(args.pool) == pool_restart.POOL_SHA, f'pool binary SHA-256 mismatch: expected {pool_restart.POOL_SHA}')
    require(digest(RECIPE_MANIFEST) == RECIPE_MANIFEST_SHA, 'accepted recipe manifest mismatch')
    inputs = {}
    for line in RECIPE_MANIFEST.read_text().splitlines():
        expected, name = line.split('  ', 1)
        require(digest(ROOT / name) == expected, f'accepted recipe input differs: {name}')
        inputs[name] = expected
    for path in [RECIPE_MANIFEST, *(HERE / name for name in NEW_FILES)]:
        inputs[str(path.relative_to(ROOT))] = digest(path)
    admissions = []
    for step in STEPS:
        cmd = step_command(step, args, work) + ['--check-only']
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        admissions.append({'step': step['name'], 'command': cmd, 'exit': proc.returncode, 'stdout': proc.stdout, 'stderr': proc.stderr})
        require(proc.returncode == 0 and step['control'] in proc.stdout,
                f"{step['name']} admission refused: {(proc.stderr or proc.stdout).strip()}")
    cmd = ['docker', 'image', 'inspect', launch.IMAGE, '--format', '{{.Id}}']
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    image = {'command': cmd, 'exit': proc.returncode, 'stdout': proc.stdout, 'stderr': proc.stderr}
    require(proc.returncode == 0 and proc.stdout.strip() == launch.IMAGE, 'pinned builder image is not present locally')
    return manifest, inputs, admissions, image


def lock_free():
    """Probe the shared heavy lock without holding it: each step takes and releases the lock itself."""
    with open(LOCK, 'a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        fcntl.flock(lock, fcntl.LOCK_UN)
        return True


def run_step(step, args, work):
    """Run one accepted recipe to completion as its own process; stream its output and keep its exit receipt."""
    cmd = step_command(step, args, work)
    row = {'step': step['name'], 'milestone': step['milestone'], 'command': cmd, 'started_utc': utc(), 'exit': None}
    print(json.dumps({'event': 'step_started', 'step': step['name'], 'milestone': step['milestone'], 'started_utc': row['started_utc'],
                      'bound_seconds': step['bound_seconds'], 'accepted_seconds': step['accepted_seconds']}), flush=True)
    started = time.monotonic()
    process = None
    try:
        with (work / f"{step['name']}.launcher.log").open('w') as log:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in process.stdout:
                print(line, end='', flush=True)
                log.write(line)
                log.flush()
            row['exit'] = process.wait()
    finally:
        if process is not None and process.poll() is None:
            # The recipes stop their own owned container on SIGINT; wait for that instead of orphaning it.
            process.send_signal(signal.SIGINT)
            try:
                row['exit'] = process.wait(timeout=180)
            except subprocess.TimeoutExpired:
                process.kill()
                row['exit'] = process.wait()
        row.update(finished_utc=utc(), seconds=time.monotonic() - started)
        (work / f"{step['name']}.exit").write_text(f"{row['exit']}\n")
        step_dir = work / step['name']
        for name, key in (('container.exit', 'container_exit'), ('launcher.exit', 'launcher_exit')):
            if (step_dir / name).exists():
                row[key] = (step_dir / name).read_text().strip()
        try:
            container = json.loads((step_dir / 'container-command.json').read_text())
            row['container'] = container[container.index('--name') + 1]
        except (OSError, ValueError, IndexError):
            pass
        try:
            result = json.loads((step_dir / 'result.json').read_text())
            row['result'] = result.get('result')
            row['peers'] = result.get('peers', result.get('tip'))
        except (OSError, ValueError):
            row['result'] = None
        print(json.dumps({'event': 'step_finished', **{k: row.get(k) for k in ('step', 'exit', 'result', 'seconds', 'container')}}), flush=True)
    return row


def rollup_inputs(work, inputs):
    """One INPUTS.sha256 for the whole journey: the union of every step's pins plus the journey's own; conflicts are returned."""
    union, conflicts = dict(inputs), set()
    for step in STEPS:
        manifest = work / step['name'] / 'INPUTS.sha256'
        if manifest.exists():
            for line in manifest.read_text().splitlines():
                sha, name = line.split('  ', 1)
                if union.setdefault(name, sha) != sha:
                    conflicts.add(name)
    (work / 'INPUTS.sha256').write_text(''.join(f'{v}  {k}\n' for k, v in sorted(union.items())))
    return sorted(conflicts)


def rollup_evidence(work):
    """One EVIDENCE.sha256 for the whole journey: every step's public receipts (never its data) plus the journey's own files."""
    rows = {}
    for step in STEPS:
        manifest = work / step['name'] / 'EVIDENCE.sha256'
        if manifest.exists():
            for line in manifest.read_text().splitlines():
                name = line.split('  ', 1)[1]
                rows[f"{step['name']}/{name}"] = digest(work / step['name'] / name)
            rows[f"{step['name']}/EVIDENCE.sha256"] = digest(manifest)
    for path in work.iterdir():
        if path.is_file() and path.name != 'EVIDENCE.sha256':
            rows[path.name] = digest(path)
    (work / 'EVIDENCE.sha256').write_text(''.join(f'{v}  {k}\n' for k, v in sorted(rows.items())))


def outside(args):
    work = args.work.absolute()
    require(not work.exists() and not work.is_symlink(), f'stale data/output directory refused: {work}; choose a new path')
    manifest, inputs, admissions, image = admission(args, work)
    if args.check_only:
        print(CONTROL)
        return 0
    work.mkdir(parents=True, mode=0o700)
    save(work / 'launcher-command.json', [sys.executable, *sys.argv])
    save(work / 'baseline.json', manifest)
    shutil.copyfile(args.profile, work / 'profile.json')
    (work / 'INPUTS.sha256').write_text(''.join(f'{v}  {k}\n' for k, v in sorted(inputs.items())))
    (work / 'BINARY.sha256').write_text(''.join(f'{digest(p)}  {p}\n' for p in (args.binary, args.wallet, args.pool)))
    save(work / 'admission.json', admissions)
    save(work / 'image-check.json', image)
    save(work / 'journey.json', {
        'steps': [{k: s[k] for k in ('name', 'milestone', 'script', 'verifier', 'bound_seconds', 'accepted_seconds')} for s in STEPS],
        'expected_wall_seconds': sum(s['accepted_seconds'] for s in STEPS),
        'bound_wall_seconds': sum(s['bound_seconds'] for s in STEPS),
        'chains': 'one fresh two-peer chain per step from the same genesis; the accepted recipes refuse existing node state',
        'containers': 'one at a time; each step owns its container and takes the shared heavy lock itself',
        'started_utc': utc()})
    steps, started, code = [], time.monotonic(), 2
    result = {'result': 'FAIL', 'steps': steps}
    try:
        free = lock_free()
        save(work / 'lock-probe.json', {'path': LOCK, 'busy': not free, 'probed_utc': utc()})
        if not free:
            result.update(result='BLOCKED', reason='shared heavy lock busy; wait for its owner and rerun with a fresh path')
            print('BLOCKED: shared heavy lock busy', file=sys.stderr)
            code = 75
            return code
        available = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                             if line.startswith('MemAvailable:'))) * 1024
        disk = shutil.disk_usage(work).free
        save(work / 'preflight-resources.json', {'available_ram_bytes': available, 'free_disk_bytes': disk, 'minimum_bytes': 5 * 1024**3})
        require(min(available, disk) >= 5 * 1024**3, 'need at least 5 GiB available RAM and disk')
        for step in STEPS:
            row = run_step(step, args, work)
            steps.append(row)
            save(work / 'steps.json', steps)
            if row['exit'] != 0:
                result.update(result='BLOCKED' if row['exit'] == 75 else 'FAIL', failed_step=step['name'],
                              reason=f"{step['name']} exited {row['exit']}; inspect {work / step['name']}")
                code = row['exit']
                return code
        conflicts = rollup_inputs(work, inputs)
        if conflicts:
            result.update(result='FAIL', reason='an input changed between steps', conflicts=conflicts)
            code = 1
            return code
        result.update(result='PASS', total_step_seconds=sum(r['seconds'] for r in steps),
                      chains='five fresh two-peer chains from one genesis, one per accepted recipe, run one at a time',
                      scope='sequenced execution of the accepted M1-M5 recipes; each step keeps its own receipts and verifier')
        code = 0
        return code
    except KeyboardInterrupt:
        result.update(result='FAIL', reason='interrupted; the current step stopped its owned container')
        code = 130
        raise
    except (OSError, ValueError, KeyError) as error:
        result.update(result='FAIL', reason=f'refused: {error}')
        raise
    finally:
        rollup_inputs(work, inputs)
        result.update(elapsed_seconds=time.monotonic() - started, finished_utc=utc())
        save(work / 'result.json', result)
        (work / 'launcher.exit').write_text(f'{code}\n')
        rollup_evidence(work)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    bindir = ROOT / 'build/repro-selected-20260918/selected-9-90/first/source/build/release/bin'
    parser.add_argument('--binary', type=Path, default=bindir / 'monerod')
    parser.add_argument('--wallet', type=Path, default=bindir / 'monero-wallet-rpc')
    parser.add_argument('--pool', type=Path, default=ROOT / 'build/tjs187-port-20260920/source/build-local/p2pool')
    parser.add_argument('--profile', type=Path, default=HERE / 'profile.json')
    parser.add_argument('--work', type=Path)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    if args.work is None:
        parser.error('--work requires a fresh directory path')
    args.binary, args.wallet, args.pool, args.profile = (p.resolve() for p in (args.binary, args.wallet, args.pool, args.profile))

    def interrupted(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    try:
        return outside(args)
    except KeyboardInterrupt:
        print('Interrupted; the current step stopped its owned container', file=sys.stderr)
        return 130
    except (OSError, ValueError, KeyError) as error:
        print(f'REFUSED: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
