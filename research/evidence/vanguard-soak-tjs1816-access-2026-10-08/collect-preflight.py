#!/usr/bin/env python3
"""Capture read-only build-mac probes. No runtime start, build or native test."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time

SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
       '-o', 'ConnectTimeout=10', 'build-mac']
PROBES = [
    ('host', 'hostname; uname -srm; sw_vers; sysctl -n hw.memsize hw.ncpu; uptime'),
    ('capacity', 'vm_stat; df -k ~/Developer'),
    ('contexts', 'docker context ls'),
    ('colima-status', 'colima status'),
    ('docker-colima', 'docker --context colima version'),
    ('docker-desktop', 'docker --context desktop-linux version'),
    ('docker-default', 'docker --context default version'),
    ('docker-legacy-colima', 'docker --host unix://~/.colima/docker.sock version'),
    ('active-work', 'ps -axo pid,ppid,%cpu,rss,etime,comm | '
     'egrep -i "(docker|colima|lima|qemu|monero|vanguard|cmake|ninja|make$|clang|rustc|cargo)"'),
    ('remote-source', 'git -C <repo> rev-parse HEAD; '
     'git -C <repo> status --short; '
     'ls -ld <repo>/vanguard'),
    ('caches', 'ls -la <repo>/build; '
     'ls -la ~/.rustup/toolchains'),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    rows = []
    for name, command in PROBES:
        began = time.monotonic()
        at = datetime.now(timezone.utc).isoformat()
        argv = SSH + [command]
        try:
            result = subprocess.run(argv, capture_output=True, timeout=40)
            code, stdout, stderr = result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired as error:
            code, stdout, stderr = 124, error.stdout or b'', error.stderr or b''
        (args.out / (name + '.stdout.log')).write_bytes(stdout)
        (args.out / (name + '.stderr.log')).write_bytes(stderr)
        rows.append({'probe': name, 'argv': argv, 'started_utc': at,
                     'wall_seconds': time.monotonic() - began, 'exit': code})
        (args.out / 'commands.json').write_text(json.dumps(rows, indent=2) + '\n')
        print(name, code, flush=True)
    (args.out / 'MANIFEST.sha256').write_text(''.join(
        hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + path.name + '\n'
        for path in sorted(args.out.iterdir()) if path.name != 'MANIFEST.sha256'))


if __name__ == '__main__':
    main()
