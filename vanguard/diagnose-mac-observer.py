#!/usr/bin/env python3
"""Diagnostic only: time process-snapshot variants on a native macOS host.

Runs beside an unchanged native archive check and records which observer
column set stalls, for how long, and which syscall the blocked helper is in.
It never signals or inspects anything except its own helpers, exports only
scalar timings, process states/names of the runner's own UID and sanitized
symbol frames, and never qualifies or accepts a package.
"""
import argparse
import ctypes
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time

VARIANTS = {
    'full': 'pid=,ppid=,ruid=,uid=,lstart=,state=,command=',
    'no_state': 'pid=,ppid=,ruid=,uid=,lstart=,command=',
    'no_command': 'pid=,ppid=,ruid=,uid=,lstart=,state=',
    'minimal': 'pid=,ppid=,ruid=,uid=,lstart=',
}
STALL_SECONDS = 1.0
HARD_SECONDS = 20.0
PRIVATE = re.compile(r'/(Users|private|Volumes|tmp|var)/')


class BsdInfo(ctypes.Structure):
    _fields_ = [('flags', ctypes.c_uint32), ('status', ctypes.c_uint32), ('xstatus', ctypes.c_uint32),
                ('pid', ctypes.c_uint32), ('ppid', ctypes.c_uint32), ('uid', ctypes.c_uint32),
                ('gid', ctypes.c_uint32), ('ruid', ctypes.c_uint32), ('rgid', ctypes.c_uint32),
                ('svuid', ctypes.c_uint32), ('svgid', ctypes.c_uint32), ('rfu', ctypes.c_uint32),
                ('comm', ctypes.c_char * 16), ('name', ctypes.c_char * 32), ('nfiles', ctypes.c_uint32),
                ('pgid', ctypes.c_uint32), ('pjobc', ctypes.c_uint32), ('tdev', ctypes.c_uint32),
                ('tpgid', ctypes.c_uint32), ('nice', ctypes.c_int32), ('start_sec', ctypes.c_uint64),
                ('start_usec', ctypes.c_uint64)]


def libproc_snapshot(library):
    """In-process kernel table read; same-UID names only, never another user's."""
    count = library.proc_listallpids(None, 0)
    pids = (ctypes.c_int * (count + 64))()
    count = library.proc_listallpids(pids, ctypes.sizeof(pids))
    rows, now = [], time.time()
    for pid in list(pids)[:max(count, 0)]:
        info = BsdInfo()
        if library.proc_pidinfo(pid, 3, 0, ctypes.byref(info), ctypes.sizeof(info)) != ctypes.sizeof(info):
            continue
        row = {'pid': pid, 'ppid': info.ppid, 'status': info.status, 'flags': info.flags,
               'age_seconds': round(now - info.start_sec - info.start_usec / 1e6, 3)}
        if info.ruid == os.getuid():
            row['comm'] = info.comm.decode(errors='replace')
        rows.append(row)
    return rows


def sanitized_frames(text):
    frames = []
    for line in text.splitlines():
        line = re.sub(r'\[0x[0-9a-f,]+\]|0x[0-9a-f]+', '', line).rstrip()
        if ('(in ' in line or 'Thread_' in line) and not PRIVATE.search(line):
            frames.append(line.strip()[:160])
    return frames[:80]


class Sampler:
    def __init__(self, out, stop):
        self.out, self.stop, self.lock = out, stop, threading.Lock()
        self.stats = {name: {'calls': 0, 'max_seconds': 0.0, 'over_1s': 0, 'over_5s': 0, 'errors': 0}
                      for name in [*VARIANTS, 'libproc']}
        self.stalls = []
        self.library = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
        self.library.proc_listallpids.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.library.proc_pidinfo.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_int]

    def record(self, name, elapsed, error=None):
        with self.lock:
            row = self.stats[name]
            row['calls'] += 1
            row['max_seconds'] = max(row['max_seconds'], round(elapsed, 6))
            row['over_1s'] += elapsed > 1
            row['over_5s'] += elapsed > 5
            row['errors'] += error is not None

    def stall(self, name, began, helper):
        event = {'variant': name, 'began_monotonic': round(began, 6)}
        try:
            snapshot_began = time.monotonic()
            event['kernel_table'] = [r for r in libproc_snapshot(self.library)
                                     if 'comm' in r or r['age_seconds'] < 10 or r['status'] != 3][:400]
            event['kernel_table_seconds'] = round(time.monotonic() - snapshot_began, 6)
        except Exception as error:  # Diagnostic: keep sampling.
            event['kernel_table_error'] = type(error).__name__
        try:
            sample = subprocess.run(['sudo', '-n', '/usr/bin/sample', str(helper.pid), '1', '-mayDie'],
                                    capture_output=True, text=True, timeout=15)
            event['sample_exit'] = sample.returncode
            event['blocked_frames'] = sanitized_frames(sample.stdout)
        except Exception as error:
            event['sample_error'] = type(error).__name__
        event['helper_alive_after_sample'] = helper.poll() is None
        return event

    def run_ps(self, name, columns):
        while not self.stop.exists():
            began = time.monotonic()
            helper = subprocess.Popen(['/bin/ps', '-axo', columns], stdout=subprocess.PIPE, text=True)
            event, error = None, None
            try:
                helper.communicate(timeout=STALL_SECONDS)
            except subprocess.TimeoutExpired:
                event = self.stall(name, began, helper)
                try:
                    helper.communicate(timeout=max(0.1, HARD_SECONDS - (time.monotonic() - began)))
                except subprocess.TimeoutExpired:
                    error = 'HARD_TIMEOUT'
                    killed = time.monotonic()
                    helper.kill()
                    helper.communicate()
                    event['reap_after_kill_seconds'] = round(time.monotonic() - killed, 6)
            elapsed = time.monotonic() - began
            if event is not None:
                event.update(elapsed_seconds=round(elapsed, 6), exit=helper.returncode, hard_timeout=error is not None)
                with self.lock:
                    if len(self.stalls) < 40:
                        self.stalls.append(event)
            self.record(name, elapsed, error)
            time.sleep(0.2)

    def run_libproc(self):
        while not self.stop.exists():
            began = time.monotonic()
            error = None
            try:
                libproc_snapshot(self.library)
            except Exception as caught:
                error = type(caught).__name__
            self.record('libproc', time.monotonic() - began, error)
            time.sleep(0.2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--stop', type=Path, required=True)
    parser.add_argument('--max-seconds', type=float, default=1080)
    args = parser.parse_args()
    sampler = Sampler(args.out, args.stop)
    threads = [threading.Thread(target=sampler.run_ps, args=item, daemon=True) for item in VARIANTS.items()]
    threads.append(threading.Thread(target=sampler.run_libproc, daemon=True))
    began = time.monotonic()
    for thread in threads:
        thread.start()
    while not args.stop.exists() and time.monotonic() - began < args.max_seconds:
        time.sleep(0.5)
    args.stop.touch()
    for thread in threads:
        thread.join(timeout=HARD_SECONDS + 20)
    report = {'schema': 'meownero-mac-observer-diagnostic/1', 'evidence': 'DIAGNOSTIC_NOT_ACCEPTANCE',
              'started_monotonic': round(began, 6), 'ended_monotonic': round(time.monotonic(), 6),
              'stall_threshold_seconds': STALL_SECONDS, 'variants': VARIANTS, 'stats': sampler.stats,
              'stalls': sampler.stalls, 'threads_alive': sum(t.is_alive() for t in threads)}
    args.out.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
