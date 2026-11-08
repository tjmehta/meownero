#!/usr/bin/env python3
"""Native macOS cross-check: kernel process-table decode versus /bin/ps.

Runs after, never during, gate checks. Compares this runner user's processes
present in both views and exports only counts, field names and timings.
"""
import argparse
import datetime
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time

spec = importlib.util.spec_from_file_location('table_check', Path(__file__).with_name('run-portable-ci.py'))
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    began = time.monotonic()
    table = {row[0]: row for row in ci.darwin_process_table()}
    table_seconds = time.monotonic() - began
    began = time.monotonic()
    output = subprocess.run(['/bin/ps', '-axo', 'pid=,ppid=,ruid=,uid=,lstart=,state=,comm='],
                            capture_output=True, text=True, timeout=60, check=True).stdout
    ps_seconds = time.monotonic() - began
    compared, mismatches, comm_differences = 0, {}, {}
    for line in output.splitlines():
        fields = line.split(None, 10)
        if len(fields) != 11 or int(fields[2]) != os.getuid() or int(fields[0]) not in table:
            continue
        pid = int(fields[0])
        _, ppid, ruid, euid, start, state, comm, _execed = table[pid]
        started = datetime.datetime.strptime(' '.join(fields[4:9]), '%a %b %d %H:%M:%S %Y')
        expected = {'ppid': int(fields[1]), 'ruid': int(fields[2]), 'euid': int(fields[3]),
                    'start_second': int(started.timestamp()), 'zombie': fields[9].startswith('Z'),
                    'comm': os.path.basename(fields[10])[:16]}
        decoded = {'ppid': ppid, 'ruid': ruid, 'euid': euid, 'start_second': start[0], 'zombie': state == 'Z',
                   'comm': comm[:16]}
        compared += 1
        for key in expected:
            if expected[key] != decoded[key]:
                # comm is informational: ps prints argv[0], the kernel its executable name.
                bucket = comm_differences if key == 'comm' else mismatches
                bucket[key] = bucket.get(key, 0) + 1
    report = {'schema': 'meownero-darwin-process-table-crosscheck/1', 'evidence': 'NATIVE_DECODE_CROSSCHECK',
              'result': 'PASS' if compared >= 3 and not mismatches else 'FAIL', 'compared_same_uid_rows': compared,
              'mismatched_fields': mismatches, 'informational_comm_differences': comm_differences,
              'table_rows': len(table), 'table_seconds': round(table_seconds, 6),
              'ps_seconds': round(ps_seconds, 6)}
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
    return 0 if report['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
