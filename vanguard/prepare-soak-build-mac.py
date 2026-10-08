#!/usr/bin/env python3
"""Prepare the task-owned Linux/ARM64 Vanguard build on build-mac, never globally.

Run from the owned clean checkout. Network is used only for pinned dependency
preparation. The native build is offline and serial under the shared heavy lock.
"""
import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import time
import urllib.request

IMAGE = 'sha256:345b4ccbee39f1231271234eddcc38e9e7c492114744ca21796b517913ee544b'
ROOT = Path(__file__).resolve().parent.parent
PIN = json.loads((ROOT / 'vanguard/source-lock.json').read_text())


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    args = parser.parse_args()
    assert platform.system() == 'Darwin' and platform.machine() == 'arm64'
    assert subprocess.check_output(['hostname'], text=True).strip().split('.')[0] == 'build-mac'
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=False)
    logs = work / 'preparation'
    logs.mkdir()
    receipt = {'schema': 'vanguard-build-mac-arm64-build/1', 'image': IMAGE,
               'started_utc': datetime.now(timezone.utc).isoformat(),
               'commands': [], 'downloads': [], 'result': 'INCOMPLETE'}

    def save():
        (logs / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')

    def run(label, argv, timeout=600):
        row = {'label': label, 'argv': argv,
               'started_utc': datetime.now(timezone.utc).isoformat()}
        receipt['commands'].append(row)
        save()
        began = time.monotonic()
        with (logs / (label + '.stdout.log')).open('wb') as stdout, \
             (logs / (label + '.stderr.log')).open('wb') as stderr:
            try:
                result = subprocess.run(argv, stdout=stdout, stderr=stderr, timeout=timeout)
                row['exit'] = result.returncode
            except subprocess.TimeoutExpired:
                row['exit'] = 124
                raise
            finally:
                row['wall_seconds'] = time.monotonic() - began
                save()
        print(label, row['exit'], flush=True)
        assert row['exit'] == 0, label + ' failed; inspect ' + str(logs)
        return (logs / (label + '.stdout.log')).read_text()

    def container(label, script, network='none', timeout=600):
        name = 'tjs1816-5a24-' + label
        argv = ['docker', '--context', 'colima', 'run', '--rm', '--pull=never',
                '--name', name, '--network=' + network, '--cap-drop=ALL',
                '--security-opt=no-new-privileges', '--cpus=2', '--memory=4g',
                '--memory-swap=4g', '--pids-limit=256', '--ulimit', 'core=0',
                '-u', f'{os.getuid()}:{os.getgid()}', '-v', f'{work}:/work',
                '-e', 'HOME=/work/home', '-e', 'CARGO_HOME=/work/cargo-home',
                '-e', 'PATH=/work/rust/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
                '-w', '/work', IMAGE, 'bash', '-euc', script]
        try:
            return run(label, argv, timeout)
        finally:
            # This exact name belongs to this invocation only.
            subprocess.run(['docker', '--context', 'colima', 'rm', '-f', name],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    with open('/tmp/meownero-swarm-20260912-heavy.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            memory = run('vm-memory', ['colima', 'ssh', '--', 'cat', '/proc/meminfo'])
            available = int(next(x.split()[1] for x in memory.splitlines() if x.startswith('MemAvailable:')))
            assert available >= 5 * 1024**2 and shutil.disk_usage(work).free >= 5 * 1024**3
            inventory = run('container-baseline', ['docker', '--context', 'colima', 'ps', '--format', '{{json .}}'])
            assert not inventory.strip(), 'another container is active; no competing heavy work'
            image = json.loads(run('image', ['docker', '--context', 'colima', 'image', 'inspect', IMAGE]))[0]
            assert image['Architecture'] == 'arm64' and image['Os'] == 'linux' and image['Id'] == IMAGE
            up = work / 'monero-fcmp'
            run('clone', ['git', 'clone', '--filter=blob:none', '--no-checkout', PIN['upstream']['url'], str(up)])
            run('checkout', ['git', '-C', str(up), 'checkout', '--detach', PIN['upstream']['commit']])
            run('submodules', ['git', '-C', str(up), 'submodule', 'update', '--init'], 900)
            assert subprocess.check_output(['git', '-C', str(up), 'rev-parse', 'HEAD'], text=True).strip() == PIN['upstream']['commit']
            for path, rev in PIN['upstream']['submodules'].items():
                assert subprocess.check_output(['git', '-C', str(up / path), 'rev-parse', 'HEAD'], text=True).strip() == rev
            assert sha(up / PIN['rust']['cargo_lock_path']) == PIN['rust']['cargo_lock_sha256']
            receipt['upstream_commit'] = PIN['upstream']['commit']
            receipt['submodules'] = PIN['upstream']['submodules']
            receipt['cargo_lock_sha256'] = PIN['rust']['cargo_lock_sha256']
            downloads = work / 'downloads'
            downloads.mkdir()
            for component in ('rustc', 'cargo', 'rust-std'):
                filename = component + '-1.93.0-aarch64-unknown-linux-gnu.tar.xz'
                url = 'https://static.rust-lang.org/dist/' + filename
                with urllib.request.urlopen(url + '.sha256', timeout=60) as response:
                    checksum = response.read().decode()
                (downloads / (filename + '.sha256')).write_text(checksum)
                expected = checksum.split()[0]
                path = downloads / filename
                with urllib.request.urlopen(url, timeout=120) as response, path.open('wb') as stream:
                    shutil.copyfileobj(response, stream)
                actual = sha(path)
                assert actual == expected, 'download checksum mismatch'
                receipt['downloads'].append({'url': url, 'checksum_url': url + '.sha256',
                                             'sha256': actual, 'bytes': path.stat().st_size})
                save()
                print('verified download', filename, actual, flush=True)
            (work / 'home').mkdir()
            container('rust-install', 'mkdir rust\nfor archive in downloads/*.tar.xz; do tar -xf "$archive" -C downloads; done\n'
                      'for installer in downloads/*/install.sh; do bash "$installer" --prefix=/work/rust --disable-ldconfig; done\n'
                      'rustc -Vv\ncargo -V')
            version = container('rust-version', 'rustc -V')
            assert version.strip() == PIN['builder']['rustc'], 'compiler version mismatch'
            receipt['rustc'] = version.strip()
            container('cargo-fetch', 'cd monero-fcmp/src/fcmp_pp/fcmp_pp_rust\ncargo fetch --locked', 'bridge', 900)
            container('configure', 'mkdir -p monero-fcmp/build/vanguard\ncd monero-fcmp/build/vanguard\n'
                      'CARGO_NET_OFFLINE=true cmake -D CMAKE_BUILD_TYPE=Release -D ARCH=default '
                      '-D BUILD_TESTS=OFF -D USE_DEVICE_TREZOR=OFF -D BUILD_GUI_DEPS=OFF ../..', timeout=300)
            container('build', 'trap \'cat /sys/fs/cgroup/memory.peak > /work/preparation/build.memory; '
                      'cat /sys/fs/cgroup/memory.events > /work/preparation/build.memory-events; '
                      'cat /sys/fs/cgroup/cpu.stat > /work/preparation/build.cpu\' EXIT\n'
                      'cd monero-fcmp/build/vanguard\nCARGO_NET_OFFLINE=true timeout 3500 make -j1 daemon wallet_rpc_server', timeout=3600)
            receipt['binary'] = {name: {'sha256': sha(up / 'build/vanguard/bin' / name),
                'bytes': (up / 'build/vanguard/bin' / name).stat().st_size}
                for name in ('monerod', 'monero-wallet-rpc')}
            container('native-versions', 'uname -m\nmonero-fcmp/build/vanguard/bin/monerod --version\n'
                      'monero-fcmp/build/vanguard/bin/monero-wallet-rpc --version')
            receipt['result'] = 'PASS_BUILD'
        finally:
            receipt['finished_utc'] = datetime.now(timezone.utc).isoformat()
            save()


if __name__ == '__main__':
    main()
