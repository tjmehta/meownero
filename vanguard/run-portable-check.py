#!/usr/bin/env python3
"""Clean-extract a hashed archive and run its native journey in an owned container."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import uuid

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('tester', ROOT / 'vanguard/tester.py')
tester = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tester)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--target', choices=['linux-x86_64', 'linux-aarch64'], required=True)
    parser.add_argument('--runtime-image', help='Exact sha256 image ID for a prepared Linux distribution')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    archive, out = tester.regular(args.archive), tester.fresh(args.out)
    tester.require(tester.sha(archive) == args.sha256, 'archive hash mismatch')
    arm = args.target == 'linux-aarch64'
    arch = 'aarch64' if arm else 'x86_64'
    image = args.runtime_image or (tester.PROFILE['image'] if arm else tester.PIN['builder']['image_id'])
    tester.require(image.startswith('sha256:') and len(image) == 71 and
                   all(c in '0123456789abcdef' for c in image[7:]), 'exact image ID required')
    host_arch = {'arm64': 'aarch64', 'amd64': 'x86_64'}.get(platform.machine(), platform.machine())
    tester.require(host_arch == arch, 'native runtime host architecture required')
    docker = ['docker', '--context', 'colima'] if platform.system() == 'Darwin' else ['docker']
    with tester.heavy_lock():
        tester.require(tester.command(docker + ['image', 'inspect', image, '--format', '{{.Architecture}} {{.Os}}']) ==
                       ('arm64' if arm else 'amd64') + ' linux', 'wrong runtime image architecture or OS')
        if platform.system() == 'Darwin':
            tester.require(not tester.command(docker + ['ps', '-q']), 'Docker busy; preserve other workloads')
        out.mkdir(mode=0o700)
        owner = uuid.uuid4().hex
        name, cidfile = 'tjs1882-' + owner + '-journey', out / 'container.id'
        script = '''set -e
trap 'cat /sys/fs/cgroup/memory.peak > /out/runtime.memory; cat /sys/fs/cgroup/memory.events > /out/runtime.memory-events' EXIT
uname -smr > /out/environment.txt
cat /etc/os-release >> /out/environment.txt
python3 --version >> /out/environment.txt
mkdir /out/extract
tar -xzf /artifact.tar.gz -C /out/extract
cd /out/extract/meownero-vanguard-ARCH
python3 -B tester.py preflight
python3 -B tester.py run --out /out/journey
python3 -B /harness/test-portable-refusals.py --package "$PWD" --out /out/controls
'''.replace('ARCH', arch)
        command = docker + ['run', '--pull=never', '--name', name, '--cidfile', str(cidfile),
            '--label', 'meownero.invocation=' + owner, '--network=none', '--read-only', '--tmpfs', '/tmp:rw,size=64m',
            '--cpus=2', '--memory=2g', '--memory-swap=2g', '--pids-limit=256', '--cap-drop=ALL',
            '--security-opt=no-new-privileges', '--ulimit', 'core=0', '-u', f'{os.getuid()}:{os.getgid()}',
            '-v', f'{archive}:/artifact.tar.gz:ro', '-v', f'{out}:/out', '-v', f'{ROOT / "vanguard"}:/harness:ro',
            '--entrypoint', '/bin/bash', image, '-ec', script]
        receipt = {'schema': 'meownero-portable-check/1', 'archive_sha256': args.sha256, 'target': args.target,
                   'image': image, 'argv': command, 'result': 'FAIL', 'cleanup': {'removed': False}}
        try:
            with (out / 'runtime.log').open('wb') as stream:
                result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, timeout=1500)
            receipt['exit'] = result.returncode
            tester.require(result.returncode == 0, 'native archive journey failed; preserve private diagnostics')
            journey = tester.read(out / 'journey/result.json')
            tester.require(journey['result'] == 'PASS_NATIVE_JOURNEY', 'native journey did not pass')
            tester.require(tester.read(out / 'controls/controls.json')['result'] == 'PASS_REFUSALS', 'controls failed')
            events = dict(row.split() for row in (out / 'runtime.memory-events').read_text().splitlines())
            tester.require(events['oom'] == '0' and events['oom_kill'] == '0' and
                           0 < int((out / 'runtime.memory').read_text()) <= 2 * 1024**3, 'runtime memory gate')
            tester.require(tester.sha(archive) == args.sha256, 'archive changed during journey')
            receipt['result'] = 'PASS_NATIVE_ARCHIVE_JOURNEY'
        finally:
            try:
                if cidfile.exists():
                    cid = cidfile.read_text().strip()
                    receipt['cleanup'] = {'id': cid, 'removed': False}
                    proof = json.loads(tester.command(docker + ['inspect', cid]))[0]
                    tester.require(proof['Id'] == cid and proof['Name'] == '/' + name and proof['Image'] == image and
                        proof['Config']['Labels'].get('meownero.invocation') == owner, 'container ownership not proven')
                    tester.command(docker + ['rm', '-f', cid])
                    tester.require(cid not in tester.command(docker + ['ps', '-aq', '--no-trunc']).splitlines(),
                                   'owned container remains')
                    receipt['cleanup']['removed'] = True
            except BaseException:
                receipt['result'] = 'FAIL'
                raise
            finally:
                tester.write(out / 'check-receipt.json', receipt)
        print(receipt['result'])


if __name__ == '__main__':
    def cancelled(signum, frame):
        raise RuntimeError('archive check cancelled; clean proven owned container')
    signal.signal(signal.SIGTERM, cancelled)
    main()
