#!/usr/bin/env python3
"""Prepare a contained task-owned Ubuntu 22.04 builder; never change host libc."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import stat
import subprocess
import time
import uuid

spec = importlib.util.spec_from_file_location('portable_build', Path(__file__).with_name('portable-build.py'))
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
tester = builder.tester
BASES = {
    'linux-x86_64': 'ubuntu@sha256:08ea48a03a3e78ebc7cd526e6a275053223aadd88bfc09cc49b06d5281525fde',
    'linux-aarch64': 'ubuntu@sha256:30dfd7fe96f97c5f5ddf388ce8d098aa509644ad68fdef67244fb71b8169ffcb',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--target', choices=BASES, default='linux-x86_64')
    parser.add_argument('--translated-linux-x86_64', action='store_true', help='Cross-produce amd64 on existing Colima QEMU; never native execution evidence')
    args = parser.parse_args()
    out = tester.fresh(args.out)
    base = BASES[args.target]
    architecture = 'amd64' if args.target == 'linux-x86_64' else 'arm64'
    native = {'x86_64': 'amd64', 'arm64': 'arm64', 'aarch64': 'arm64'}.get(platform.machine())
    mac = platform.system() == 'Darwin'
    translated = args.translated_linux_x86_64
    tester.require(not translated or (mac and native == 'arm64' and architecture == 'amd64'), 'translation requires the existing ARM64 Mac compiler host and an x64 target')
    tester.require(native == architecture or translated, 'native builder architecture required')
    docker = ['docker', '--context', 'colima'] if mac else ['docker']
    with tester.heavy_lock():
        tester.require(shutil.disk_usage(out.parent).free >= 10 * 1024**3, 'requires ten GiB disk reserve')
        docker_free = int(tester.command(['colima', 'ssh', '--', 'df', '-B1', '/var/lib/docker']).splitlines()[-1].split()[3]) if mac else shutil.disk_usage('/var/lib/docker').free
        tester.require(docker_free >= 10 * 1024**3, 'requires ten GiB Docker disk reserve')
        memory = tester.command(['colima', 'ssh', '--', 'cat', '/proc/meminfo']) if mac else Path('/proc/meminfo').read_text()
        available = int(next(line.split()[1] for line in memory.splitlines() if line.startswith('MemAvailable:'))) * 1024
        tester.require(available >= 5 * 1024**3, 'requires five GiB available memory')
        if mac:
            tester.require(not tester.command(docker + ['ps', '-q']), 'Docker busy; preserve non-owned work')
        if translated:
            emulation = tester.command(['colima', 'ssh', '--', 'cat', '/proc/sys/fs/binfmt_misc/qemu-x86_64'])
            tester.require(emulation.startswith('enabled\n') and 'flags: POCF' in emulation, 'already-enabled x64 container translation required')
        out.mkdir(mode=0o700)
        receipt = {'schema': 'meownero-older-linux-builder/1', 'base_manifest': base, 'target': args.target,
                   'compiler_execution_substrate': 'PREEXISTING_QEMU_AMD64_ON_COLIMA_ARM64' if translated else 'NATIVE',
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
            # Public image pulls must not consult an account/keychain helper.
            # Keep the existing local daemon and context unchanged.
            endpoint = tester.command(['docker', 'context', 'inspect', 'colima' if mac else 'default',
                                       '--format', '{{.Endpoints.docker.Host}}'])
            tester.require(endpoint.startswith('unix://') and
                           stat.S_ISSOCK(Path(endpoint[7:]).stat().st_mode), 'existing local Docker socket required')
            client = out / 'anonymous-docker-client'
            client.mkdir(mode=0o700)
            (client / 'config.json').write_text(
                '{"auths":{"https://index.docker.io/v1/":{}},'
                '"credHelpers":{"https://index.docker.io/v1/":""}}\n')
            (client / 'config.json').chmod(0o600)
            receipt['registry_access'] = 'Anonymous official public image, explicit empty Hub record and no helper in task-owned client'
            run('pull-pinned-base', ['docker', '--config', str(client), '--host', endpoint,
                'pull', '--platform=linux/' + architecture, base], 180)
            image = tester.command(docker + ['image', 'inspect', base, '--format', '{{.Id}}'])
            tester.require(tester.command(docker + ['image', 'inspect', image, '--format', '{{.Architecture}} {{.Os}}']) == architecture + ' linux', 'wrong older builder architecture')
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
            run('prepare', docker + ['run', '--platform=linux/' + architecture, '--pull=never', '--name', name, '--cidfile', str(cidfile),
                           '--label', 'meownero.invocation=' + invocation, '--cpus=2', '--memory=768m',
                           '--memory-swap=768m', '--pids-limit=128', '--security-opt=no-new-privileges',
                           '--ulimit', 'core=0', '-v', str(out) + ':/out', image, 'bash', '-ec', script], 900)
            cid = cidfile.read_text().strip()
            run('commit-builder', docker + ['commit', cid], 120)
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
                proof = json.loads(tester.command(docker + ['inspect', cid]))[0]
                tester.require(proof['Id'] == cid and proof['Name'] == '/' + name and proof['Image'] == receipt['base_image'] and proof['Config']['Labels'].get('meownero.invocation') == invocation, 'older builder ownership proof failed')
                run('cleanup', docker + ['rm', '-f', cid], 30)
                removed = cid not in tester.command(docker + ['ps', '-aq', '--no-trunc']).splitlines()
                receipt['cleanup'] = {'id': cid, 'removed': removed}
                tester.require(removed, 'owned older builder remains')
            save()


if __name__ == '__main__':
    def cancelled(signum, frame):
        raise RuntimeError('older builder cancelled; clean exact owned container')
    signal.signal(signal.SIGTERM, cancelled)
    main()
