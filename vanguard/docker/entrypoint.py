"""Run only the contained disposable journey; publish only its safe receipt."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import sys

GIB = 1024**3


def capacity(state):
    """Keep host/VM admission separate from the enforced two-GiB cgroup."""
    assert os.getuid() != 0, 'nonroot required'
    assert set(p.name for p in Path('/sys/class/net').iterdir()) == {'lo'}, 'offline network required'
    cgroup = Path('/sys/fs/cgroup')
    limit = int((cgroup / 'memory.max').read_text())
    used = int((cgroup / 'memory.current').read_text())
    assert limit == 2 * GIB and int((cgroup / 'memory.swap.max').read_text()) == 0
    assert limit - used >= 1536 * 1024**2, 'insufficient cgroup headroom'
    assert (cgroup / 'pids.max').read_text().strip() == '256'
    cpu = (cgroup / 'cpu.max').read_text().split()
    assert cpu[0] != 'max' and int(cpu[0]) <= 2 * int(cpu[1])
    host = int(next(row.split()[1] for row in Path('/proc/meminfo').read_text().splitlines()
                    if row.startswith('MemAvailable:'))) * 1024
    assert host >= 5 * GIB, 'host/VM five-GiB reserve unavailable'
    assert shutil.disk_usage('/output').free >= 5 * GIB, 'output filesystem five-GiB reserve unavailable'
    mounts = [line.split() for line in Path('/proc/self/mountinfo').read_text().splitlines()]
    state_mount = next(row for row in mounts if row[4] == str(state))
    assert state_mount[state_mount.index('-') + 1] == 'tmpfs', 'private state must be tmpfs'
    assert shutil.disk_usage(state).free >= 768 * 1024**2, 'private-state space unavailable'
    assert next(row for row in mounts if row[4] == '/')[5].split(',')[0] == 'ro', 'read-only root required'
    return {'host_available_bytes': host, 'container_limit_bytes': limit,
            'container_available_bytes': limit - used, 'host_reserve_bytes': 5 * GIB}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--deadline-seconds', type=int, default=1200)
    args = parser.parse_args()
    assert 1 <= args.deadline_seconds <= 1200
    output = Path('/output/result.json')
    assert not output.exists() and not output.is_symlink(), 'fresh public output required'
    spec = importlib.util.spec_from_file_location('journey', '/opt/tester/tester.py')
    journey = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(journey)
    state = Path('/state')
    receipt = {'schema': 'meownero-contained-journey/1', 'result': 'FAIL_CONTAINER_ADMISSION'}
    outcome = 1
    try:
        receipt['capacity'] = capacity(state)
        journey.run(state / 'journey', deadline_seconds=args.deadline_seconds, container_capacity=capacity)
        outcome = 0
    except Exception as error:
        receipt['failure_type'] = type(error).__name__
    finally:
        native = state / 'journey/result.json'
        if native.exists():
            info = native.lstat()
            assert stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= 256 * 1024
            receipt['journey'] = json.loads(native.read_text())
            receipt['result'] = receipt['journey']['result']
        # Wallets, logs, ring DB and chain state remain only in the tmpfs. The
        # launcher destroys that filesystem when it removes this exact container.
        with output.open('x') as stream:
            json.dump(receipt, stream, indent=2)
            stream.write('\n')
        output.chmod(0o600)
    print(receipt['result'], flush=True)
    return outcome


if __name__ == '__main__':
    sys.exit(main())
