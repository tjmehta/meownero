#!/usr/bin/env python3
"""Prepare a contained task-owned Ubuntu 22.04 builder; never change host libc."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time
import uuid

spec = importlib.util.spec_from_file_location('portable_build', Path(__file__).with_name('portable-build.py'))
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
tester = builder.tester
BASE = 'ubuntu@sha256:08ea48a03a3e78ebc7cd526e6a275053223aadd88bfc09cc49b06d5281525fde'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = tester.fresh(args.out)
    with tester.heavy_lock():
        tester.require(shutil.disk_usage(out.parent).free >= 10 * 1024**3, 'requires ten GiB disk reserve')
        tester.require(shutil.disk_usage('/var/lib/docker').free >= 10 * 1024**3, 'requires ten GiB Docker disk reserve')
        available = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))) * 1024
        tester.require(available >= 5 * 1024**3, 'requires five GiB available memory')
        out.mkdir(mode=0o700)
        receipt = {'schema': 'meownero-older-linux-builder/1', 'base_manifest': BASE,
                   'distribution': 'Ubuntu 22.04', 'commands': [], 'result': 'INCOMPLETE'}

        def save():
            tester.write(out / 'preparation.json', receipt)

        def run(label, argv, timeout=600):
            row = {'label': label, 'argv': argv}
            receipt['commands'].append(row)
            began = time.monotonic()
            save()
            try:
                with (out / (label + '.log')).open('wb') as stream:
                    result = subprocess.run(argv, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
                    row['exit'] = result.returncode
                tester.require(row['exit'] == 0, label + ' failed; preserve diagnostics')
            finally:
                row['wall_seconds'] = time.monotonic() - began
                save()
            print(label, row['exit'], flush=True)

        invocation = uuid.uuid4().hex
        name = 'tjs1882-3175-old-builder-' + invocation
        cidfile = out / 'container.id'
        try:
            run('pull-pinned-base', ['docker', 'pull', BASE], 180)
            image = tester.command(['docker', 'image', 'inspect', BASE, '--format', '{{.Id}}'])
            tester.require(tester.command(['docker', 'image', 'inspect', image, '--format', '{{.Architecture}} {{.Os}}']) == 'amd64 linux', 'wrong older builder architecture')
            receipt['base_image'] = image
            script = """set -e
test "$(. /etc/os-release; echo "$VERSION_ID")" = 22.04
trap 'cat /sys/fs/cgroup/memory.peak > /out/preparation.memory; cat /sys/fs/cgroup/memory.events > /out/preparation.memory-events; chown -R """ + str(os.getuid()) + ':' + str(os.getgid()) + """ /out' EXIT
apt-get -o Acquire::Retries=1 -o Acquire::http::Timeout=30 update
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends build-essential cmake pkg-config python3 git ca-certificates curl bzip2 xz-utils autoconf automake libtool gettext unzip libboost-chrono-dev libboost-filesystem-dev libboost-program-options-dev libboost-serialization-dev libboost-system-dev libboost-thread-dev libboost-test-dev libboost-locale-dev libssl-dev libsodium-dev libunbound-dev libzmq3-dev liblzma-dev libexpat1-dev libunwind-dev zlib1g-dev
dpkg-query -W -f='${binary:Package}=${Version}\\n' | sort > /out/dependencies.txt
ldd --version > /out/glibc.txt
gcc --version > /out/compiler.txt
cmake --version >> /out/compiler.txt
python3 --version >> /out/compiler.txt
"""
            run('prepare', ['docker', 'run', '--pull=never', '--name', name, '--cidfile', str(cidfile),
                           '--label', 'meownero.invocation=' + invocation, '--cpus=2', '--memory=768m',
                           '--memory-swap=768m', '--pids-limit=128', '--security-opt=no-new-privileges',
                           '--ulimit', 'core=0', '-v', str(out) + ':/out', image, 'bash', '-ec', script], 900)
            cid = cidfile.read_text().strip()
            run('commit-builder', ['docker', 'commit', cid], 120)
            receipt['builder_image'] = (out / 'commit-builder.log').read_text().strip()
            tester.require(receipt['builder_image'].startswith('sha256:') and len(receipt['builder_image']) == 71, 'missing builder image identity')
            receipt['result'] = 'PREPARED_OLDER_BUILDER'
        except BaseException as error:
            receipt['result'] = 'FAILED_ATTEMPT'
            receipt['failure'] = str(error)
            raise
        finally:
            if cidfile.exists():
                cid = cidfile.read_text().strip()
                proof = json.loads(tester.command(['docker', 'inspect', cid]))[0]
                tester.require(proof['Id'] == cid and proof['Name'] == '/' + name and proof['Image'] == receipt['base_image'] and proof['Config']['Labels'].get('meownero.invocation') == invocation, 'older builder ownership proof failed')
                run('cleanup', ['docker', 'rm', '-f', cid], 30)
                removed = cid not in tester.command(['docker', 'ps', '-aq', '--no-trunc']).splitlines()
                receipt['cleanup'] = {'id': cid, 'removed': removed}
                tester.require(removed, 'owned older builder remains')
            save()


if __name__ == '__main__':
    def cancelled(signum, frame):
        raise RuntimeError('older builder cancelled; clean exact owned container')
    signal.signal(signal.SIGTERM, cancelled)
    main()
