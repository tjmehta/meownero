#!/usr/bin/env python3
"""Exercise contained admission and the preserved native refusal before spawn."""
import argparse
from contextlib import nullcontext
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
from unittest.mock import patch


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    assert args.out.parent.is_dir() and not args.out.exists()
    root = Path(__file__).resolve().parent
    entry = load('contained', root / 'entrypoint.py')
    journey = load('portable', root.parent / 'portable-tester.py')
    cases = []
    with tempfile.TemporaryDirectory(dir=args.out.parent) as temporary:
        fixture = Path(temporary)
        def mapped(path):
            return fixture / str(path).lstrip('/')
        def put(path, text):
            leaf = mapped(path)
            leaf.parent.mkdir(parents=True, exist_ok=True)
            leaf.write_text(text)
        def reset():
            shutil.rmtree(fixture / 'sys', ignore_errors=True)
            mapped('/sys/class/net/lo').mkdir(parents=True)
            for name, value in {'memory.max': 2 * 1024**3, 'memory.current': 16 * 1024**2,
                                'memory.swap.max': 0, 'pids.max': 256, 'cpu.max': '200000 100000'}.items():
                put('/sys/fs/cgroup/' + name, str(value))
            put('/proc/meminfo', 'MemAvailable: 6291456 kB\n')
            put('/proc/self/mountinfo', '1 0 0:1 / / ro - overlay overlay ro\n2 1 0:2 / /state rw - tmpfs tmpfs rw\n')
        free = {'/output': 10 * 1024**3, '/state': 1024**3}
        uid = [1000]
        with patch.object(entry, 'Path', mapped), patch.object(entry.os, 'getuid', side_effect=lambda: uid[0]), \
             patch.object(entry.shutil, 'disk_usage', side_effect=lambda path: SimpleNamespace(free=free[str(path)])):
            reset()
            result = entry.capacity(Path('/state'))
            assert result['container_limit_bytes'] == 2 * 1024**3
            assert result['container_available_bytes'] < 5 * 1024**3
            cases.append({'case': 'two-GiB-cgroup-with-separate-host-reserve', 'result': 'PASS'})
            variants = [
                ('cgroup-headroom', lambda: put('/sys/fs/cgroup/memory.current', str(1024**3))),
                ('unlimited-memory', lambda: put('/sys/fs/cgroup/memory.max', 'max')),
                ('oversized-memory', lambda: put('/sys/fs/cgroup/memory.max', str(4 * 1024**3))),
                ('swap-enabled', lambda: put('/sys/fs/cgroup/memory.swap.max', '1')),
                ('host-reserve', lambda: put('/proc/meminfo', 'MemAvailable: 4194304 kB\n')),
                ('output-reserve', lambda: free.update({'/output': 4 * 1024**3})),
                ('private-space', lambda: free.update({'/state': 512 * 1024**2})),
                ('public-network', lambda: mapped('/sys/class/net/eth0').mkdir()),
                ('pid-cap', lambda: put('/sys/fs/cgroup/pids.max', 'max')),
                ('unlimited-CPU', lambda: put('/sys/fs/cgroup/cpu.max', 'max 100000')),
                ('oversized-CPU', lambda: put('/sys/fs/cgroup/cpu.max', '400000 100000')),
                ('root-user', lambda: uid.__setitem__(0, 0)),
                ('writable-image', lambda: put('/proc/self/mountinfo', '1 0 0:1 / / rw - overlay overlay rw\n2 1 0:2 / /state rw - tmpfs tmpfs rw\n')),
                ('persistent-private-state', lambda: put('/proc/self/mountinfo', '1 0 0:1 / / ro - overlay overlay ro\n2 1 0:2 / /state rw - ext4 /dev/test rw\n')),
            ]
            for label, change in variants:
                reset()
                free.update({'/output': 10 * 1024**3, '/state': 1024**3})
                uid[0] = 1000
                change()
                try:
                    entry.capacity(Path('/state'))
                except (AssertionError, ValueError):
                    pass
                else:
                    raise AssertionError('unsafe admission passed: ' + label)
                cases.append({'case': label, 'result': 'PASS_REFUSAL'})
        out = fixture / 'native-out'
        with patch.object(journey, 'lock', return_value=nullcontext()), \
             patch.object(journey, 'preflight', return_value={}), \
             patch.object(journey, 'available_memory', return_value=4 * 1024**3), \
             patch.object(journey.shutil, 'disk_usage', return_value=SimpleNamespace(free=10 * 1024**3)), \
             patch.object(journey.subprocess, 'Popen', side_effect=AssertionError('unexpected child spawn')):
            try:
                journey.run(out)
            except RuntimeError as error:
                assert str(error) == 'requires five GiB available memory and disk'
            else:
                raise AssertionError('native reserve changed')
        assert not out.exists()
        cases.append({'case': 'native-default-five-GiB-refusal-before-output-or-spawn', 'result': 'PASS_REFUSAL'})
    result = {'schema': 'meownero-contained-capacity-fixtures/1', 'result': 'PASS', 'cases': cases,
              'source_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (root / 'entrypoint.py', root.parent / 'portable-tester.py')},
              'seams': 'Temporary proc/cgroup/mount files, UID and disk scalars; native preflight stub only for original reserve refusal.',
              'native_or_container_runtime_acceptance': False}
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print('PASS', len(cases), 'capacity controls')


if __name__ == '__main__':
    main()
