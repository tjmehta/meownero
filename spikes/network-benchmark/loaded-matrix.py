#!/usr/bin/env python3
"""Predeclared matched 90s-versus-120s loaded matrix driver (host side, sequential).

Runs chain/test-network-loaded.sh once per cell into a fresh work directory under
--root. Cells are interleaved by profile so both arms share the same host state
drift. Every cell inherits the wrapper's unchanged guards: shared heavy lock,
>=5 GiB available-RAM preflight (bounded wait), --network none, 1536 MiB / no swap
/ 2 CPUs. A gate refusal (wrapper exit 75) stops the driver with a checkpoint;
nothing is retried blindly and no gate is weakened here. Finished cells (an
`exit` file exists) are skipped, so an interrupted matrix resumes where it stopped.

Matched constants per cell: --duration, --tx-interval, --outputs, --link,
--accel, --seed, --competing-every, --partition-txs, caps and topology. Only the
profile (target seconds and reward) differs. Block capacity is NOT normalized.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
WRAPPER = REPO / 'chain' / 'test-network-loaded.sh'
HARNESS = REPO / 'chain' / 'test-network-loaded.py'
PROFILES = ['selected-9-90', 'fallback-12-120']
# Predeclared groups (see research/loaded-network-2026-09-15.md). Do not edit between arms.
GROUPS = {
    'accelerated': dict(accel=6, duration=240, tx_interval=2, outputs=2, competing_every=4,
                        partition_txs=5, links=['nominal', 'slow'], seeds=[1, 2, 3]),
    'size-sensitivity': dict(accel=6, duration=240, tx_interval=2, outputs=8, competing_every=4,
                             partition_txs=5, links=['nominal'], seeds=[1]),
    'target-rate': dict(accel=1, duration=600, tx_interval=2, outputs=2, competing_every=4,
                        partition_txs=5, links=['nominal'], seeds=[1]),
}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def mem_available_kib():
    for line in Path('/proc/meminfo').read_text().splitlines():
        if line.startswith('MemAvailable:'):
            return int(line.split()[1])
    raise RuntimeError('MemAvailable missing')


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def cells(groups):
    for group in groups:
        spec = GROUPS[group]
        for link in spec['links']:
            for seed in spec['seeds']:
                for profile in PROFILES:
                    yield dict(id=f'{group}/{link}-s{seed}/{profile}', group=group, link=link, seed=seed,
                               profile=profile, accel=spec['accel'], duration=spec['duration'],
                               tx_interval=spec['tx_interval'], outputs=spec['outputs'],
                               competing_every=spec['competing_every'], partition_txs=spec['partition_txs'])


def cell_args(c):
    return ['--seed', str(c['seed']), '--link', c['link'], '--accel', str(c['accel']),
            '--duration', str(c['duration']), '--tx-interval', str(c['tx_interval']),
            '--outputs', str(c['outputs']), '--competing-every', str(c['competing_every']),
            '--partition-txs', str(c['partition_txs'])]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--root', required=True, help='matrix output root (created if missing)')
    ap.add_argument('--selected-source', required=True)
    ap.add_argument('--fallback-source', required=True)
    ap.add_argument('--groups', nargs='+', default=list(GROUPS), choices=list(GROUPS))
    ap.add_argument('--only', help='substring filter on cell id')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--wait-seconds', type=int, default=300, help='MEOW_NETWORK_WAIT_SECONDS per cell')
    ap.add_argument('--cell-timeout', type=int, default=1800, help='MEOW_LOADED_TIMEOUT per cell')
    ap.add_argument('--continue-on-failure', action='store_true',
                    help='keep going after a non-gate cell failure (default: stop for inspection)')
    args = ap.parse_args()
    sources = {'selected-9-90': Path(args.selected_source).resolve(),
               'fallback-12-120': Path(args.fallback_source).resolve()}
    for profile, src in sources.items():
        for b in ('monerod', 'monero-wallet-rpc'):
            if not (src / 'build/release/bin' / b).is_file():
                sys.exit(f'{profile}: missing {src}/build/release/bin/{b}')
    plan = [c for c in cells(args.groups) if not args.only or args.only in c['id']]
    root = Path(args.root).resolve()
    if args.dry_run:
        for c in plan:
            print(c['id'], ' '.join(cell_args(c)))
        print(f'{len(plan)} cells')
        return 0
    root.mkdir(parents=True, exist_ok=True)
    head = subprocess.run(['git', '-C', str(REPO), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    matrix = dict(created=now(), git_head=head, wrapper_sha256=sha256(WRAPPER), harness_sha256=sha256(HARNESS),
                  driver_sha256=sha256(__file__), sources={k: str(v) for k, v in sources.items()},
                  binaries={k: {b: sha256(v / 'build/release/bin' / b) for b in ('monerod', 'monero-wallet-rpc')}
                            for k, v in sources.items()},
                  builder_image=os.environ.get('MEOW_BUILDER_IMAGE', 'meownero-chain-builder'),
                  groups={g: GROUPS[g] for g in args.groups}, cells=plan)
    (root / 'matrix.json').write_text(json.dumps(matrix, indent=2) + '\n')
    progress_path = root / 'progress.json'
    progress = json.loads(progress_path.read_text()) if progress_path.exists() else {'cells': {}}

    def save():
        progress['updated'] = now()
        progress_path.write_text(json.dumps(progress, indent=2) + '\n')

    for c in plan:
        work = root / c['id']
        rec = progress['cells'].get(c['id'], {})
        if (work / 'exit').exists():
            rec.setdefault('skipped_existing', True)
            progress['cells'][c['id']] = rec
            print(f"skip (done) {c['id']} exit={(work / 'exit').read_text().strip()}", flush=True)
            continue
        if work.exists():
            aside = work.with_name(work.name + '.interrupted-' + dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
            shutil.move(str(work), str(aside))
            rec['moved_aside'] = str(aside)
            print(f"moved aside interrupted {c['id']} -> {aside}", flush=True)
        rec.update(started=now(), mem_available_kib_at_launch=mem_available_kib())
        progress['cells'][c['id']] = rec
        save()
        env = dict(os.environ, MEOW_NETWORK_WAIT_SECONDS=str(args.wait_seconds), MEOW_LOADED_TIMEOUT=str(args.cell_timeout))
        cmd = [str(WRAPPER), str(sources[c['profile']]), str(work), c['profile'], *cell_args(c)]
        print(f"{now()} start {c['id']} mem={rec['mem_available_kib_at_launch']} KiB", flush=True)
        t0 = time.monotonic()
        work.parent.mkdir(parents=True, exist_ok=True)
        with (root / 'driver.log').open('a') as log:
            log.write(f"{now()} {c['id']} {' '.join(cmd)}\n")
            proc = subprocess.run(cmd, env=env, stdout=log, stderr=subprocess.STDOUT)
        rec.update(ended=now(), wall_s=round(time.monotonic() - t0, 1), wrapper_exit=proc.returncode,
                   mem_available_kib_at_end=mem_available_kib())
        result_path = work / 'result.json'
        if result_path.exists():
            r = json.loads(result_path.read_text())
            rec['result'] = r.get('result')
            rec['transactions_submitted'] = r.get('transactions_submitted')
            rec['transactions_lost'] = len(r.get('transactions_lost') or [])
        save()
        print(f"{now()} end {c['id']} exit={proc.returncode} result={rec.get('result')} wall={rec['wall_s']}s", flush=True)
        if proc.returncode == 75:
            progress['stopped'] = dict(reason='resource gate refused (wrapper exit 75)', cell=c['id'], at=now())
            save()
            print('STOP: resource gate refused; checkpointed, not retried', flush=True)
            return 75
        if proc.returncode != 0 and not args.continue_on_failure:
            progress['stopped'] = dict(reason=f'cell failed with wrapper exit {proc.returncode}', cell=c['id'], at=now())
            save()
            print('STOP: cell failed; inspect before continuing (no blind replay)', flush=True)
            return proc.returncode
    progress['completed'] = now()
    progress.pop('stopped', None)
    save()
    print('matrix complete', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
