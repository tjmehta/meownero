#!/usr/bin/env python3
"""Check exact Mac archives with explicit native or Rosetta execution evidence."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import resource
import signal
import subprocess
import sys
import tarfile
import time

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('tester', ROOT / 'vanguard/tester.py')
tester = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tester)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--target', choices=['macos-aarch64', 'macos-x86_64'], default='macos-aarch64')
    parser.add_argument('--translated-macos-x86_64', action='store_true')
    args = parser.parse_args()
    tester.require(platform.system() == 'Darwin', 'macOS required')
    expected_host = 'aarch64' if args.target == 'macos-aarch64' or args.translated_macos_x86_64 else 'x86_64'
    tester.require(not args.translated_macos_x86_64 or args.target == 'macos-x86_64', 'translation requires Intel archive')
    archive, out = tester.regular(args.archive), tester.fresh(args.out)
    tester.require(tester.sha(archive) == args.sha256, 'archive hash mismatch')
    with tester.heavy_lock():
        out.mkdir(mode=0o700)
        extracted = out / 'extract'
        extracted.mkdir(mode=0o700)
        with tarfile.open(archive) as stream:
            tester.require(all(m.isfile() for m in stream.getmembers()), 'archive must contain only regular files')
            stream.extractall(extracted, filter='data')
        package = extracted / ('meownero-vanguard-' + args.target)
        native_spec = importlib.util.spec_from_file_location('packaged_mac_guard', package / 'tester.py')
        native = importlib.util.module_from_spec(native_spec)
        native_spec.loader.exec_module(native)
        tester.require(native.mac_physical_architecture() == expected_host, 'wrong physical/native Mac target')
        receipt = {'schema': 'meownero-portable-native-mac-check/1', 'archive_sha256': args.sha256,
                   'result': 'FAIL', 'phases': [], 'resident_limit_bytes': 4 * 1024**3,
                   'peak_resident_bytes': 0, 'cleanup': []}
        receipt['execution_substrate'] = 'ROSETTA_TRANSLATED_MACOS_X86_64' if args.translated_macos_x86_64 else 'NATIVE'
        began, known = time.monotonic(), set()

        def save():
            tester.write(out / 'check-receipt.json', receipt)

        def descendants(pid):
            rows = [tuple(map(int, line.split())) for line in
                    subprocess.check_output(['ps', '-axo', 'pid=,ppid=,rss='], text=True, timeout=10).splitlines()]
            owned = {pid}
            while True:
                children = {p for p, parent, _ in rows if parent in owned}
                if children <= owned:
                    break
                owned |= children
            return owned, sum(rss * 1024 for p, _, rss in rows if p in owned)

        def phase(name, argv):
            row = {'name': name, 'argv': argv, 'reaped': False}
            receipt['phases'].append(row)
            process = None
            mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT})
            def setup():
                resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
                signal.pthread_sigmask(signal.SIG_SETMASK, mask)
            try:
                with (out / (name + '.log')).open('wb') as log:
                    process = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT,
                                               cwd=out, start_new_session=True, preexec_fn=setup)
                    row['pid'] = process.pid
                    known.add(process.pid)
                    save()
                    signal.pthread_sigmask(signal.SIG_SETMASK, mask)
                    while process.poll() is None:
                        owned, resident = descendants(process.pid)
                        known.update(owned)
                        receipt['peak_resident_bytes'] = max(receipt['peak_resident_bytes'], resident)
                        tester.require(resident <= receipt['resident_limit_bytes'], 'native resident memory cap')
                        tester.require(time.monotonic() - began <= 1500, 'native check deadline')
                        try:
                            process.wait(timeout=0.5)
                        except subprocess.TimeoutExpired:
                            pass
                    row['exit'] = process.returncode
                    tester.require(process.returncode == 0, name + ' failed; preserve private diagnostics')
            finally:
                # Repeated cancellation cannot interrupt owned cleanup.
                signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT})
                if process is not None:
                    if process.poll() is None:
                        process.terminate()
                    try:
                        process.wait(timeout=60)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                    row['reaped'] = process.poll() is not None
                save()
                signal.pthread_sigmask(signal.SIG_SETMASK, mask)

        try:
            (out / 'environment.txt').write_text('macOS ' + tester.command(['sw_vers', '-productVersion']) + '\n' +
                tester.command(['uname', '-smr']) + '\n' + sys.version + '\n')
            translated = ['--translated-macos-x86_64'] if args.translated_macos_x86_64 else []
            phase('preflight', [sys.executable, '-B', str(package / 'tester.py'), 'preflight', *translated])
            phase('journey', [sys.executable, '-B', str(package / 'tester.py'), 'run', '--out', str(out / 'journey'), *translated])
            phase('controls', [sys.executable, '-B', str(ROOT / 'vanguard/test-portable-refusals.py'),
                              '--package', str(package), '--out', str(out / 'controls'), *translated])
            journey = tester.read(out / 'journey/result.json')
            tester.require(journey['result'] == ('PASS_TRANSLATED_JOURNEY' if args.translated_macos_x86_64 else 'PASS_NATIVE_JOURNEY') and all(p['removed'] for p in journey['cleanup']), 'journey cleanup')
            tester.require(tester.read(out / 'controls/controls.json')['result'] == 'PASS_REFUSALS', 'native controls')
            tester.require(tester.sha(archive) == args.sha256, 'archive changed')
            receipt['result'] = 'PASS_TRANSLATED_ARCHIVE_JOURNEY' if args.translated_macos_x86_64 else 'PASS_NATIVE_ARCHIVE_JOURNEY'
        finally:
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            signal.signal(signal.SIGINT, signal.SIG_IGN)
            try:
                for pid in sorted(known):
                    probe = subprocess.run(['ps', '-p', str(pid), '-o', 'command='], capture_output=True, text=True, timeout=10)
                    command = probe.stdout.strip()
                    if command:
                        # Check the owned extract/output identity again before signalling
                        # a remembered PID; preserve any PID reused by unrelated work.
                        owned = str(package) in command or str(out) in command
                        tester.require(owned, 'remembered PID reused; preserve unrelated process')
                        os.kill(pid, signal.SIGTERM)
                        end = time.monotonic() + 10
                        while time.monotonic() < end and subprocess.run(['ps', '-p', str(pid)],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
                            time.sleep(0.2)
                        if subprocess.run(['ps', '-p', str(pid)], stdout=subprocess.DEVNULL,
                                          stderr=subprocess.DEVNULL).returncode == 0:
                            os.kill(pid, signal.SIGKILL)
                            time.sleep(0.2)
                        tester.require(subprocess.run(['ps', '-p', str(pid)], stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL).returncode != 0, 'owned native process remains')
                    receipt['cleanup'].append({'pid': pid, 'removed': True})
            except BaseException:
                receipt['result'] = 'FAIL'
                raise
            finally:
                receipt['wall_seconds'] = round(time.monotonic() - began, 3)
                save()
        print(receipt['result'])


if __name__ == '__main__':
    def cancelled(signum, frame):
        raise RuntimeError('native check cancelled; clean its owned processes')
    signal.signal(signal.SIGTERM, cancelled)
    main()
