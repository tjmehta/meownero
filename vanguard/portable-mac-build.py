#!/usr/bin/env python3
"""Try the locked upstream native Apple Silicon depends route, with owned writes."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import resource
import shutil
import signal
import subprocess
import tarfile
import time
import urllib.request

spec = importlib.util.spec_from_file_location('portable_build', Path(__file__).with_name('portable-build.py'))
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
tester, PIN = builder.tester, builder.PIN


def main():
    os.environ['GIT_OPTIONAL_LOCKS'] = '0'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    tester.require(platform.system() == 'Darwin' and platform.machine() == 'arm64', 'native Apple Silicon required')
    out = tester.fresh(args.out)
    with tester.heavy_lock():
        tester.require(shutil.disk_usage(out.parent).free >= 10 * 1024**3, 'requires ten GiB disk reserve')
        out.mkdir(mode=0o700)
        receipt = {'schema': 'meownero-native-mac-build/1', 'source_lock': PIN,
                   'commands': [], 'downloads': [], 'result': 'INCOMPLETE'}

        def save():
            tester.write(out / 'build-receipt.json', receipt)

        def run(label, argv, timeout=60, cwd=None):
            row = {'label': label, 'argv': argv}
            receipt['commands'].append(row)
            began = time.monotonic()
            def limits():
                resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
                resource.setrlimit(resource.RLIMIT_DATA, (4 * 1024**3, 4 * 1024**3))
            try:
                with (out / (label + '.log')).open('wb') as log:
                    process = subprocess.Popen(argv, cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
                                               start_new_session=True, preexec_fn=limits)
                    try:
                        row['exit'] = process.wait(timeout=timeout)
                    except BaseException as error:
                        os.killpg(process.pid, 15)
                        try:
                            process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            os.killpg(process.pid, 9)
                            process.wait(timeout=5)
                        row['exit'] = 124
                        if not isinstance(error, subprocess.TimeoutExpired):
                            raise
                tester.require(row['exit'] == 0, label + ' failed; preserved diagnostics')
            finally:
                row['wall_seconds'] = time.monotonic() - began
                save()
            print(label, row['exit'], flush=True)

        try:
            source = out / 'monero-fcmp'
            builder.export_sources(args.cache.resolve(), source, out, run)
            run('native-toolchain', ['sh', '-c', 'clang --version; cmake --version; xcrun --show-sdk-path; xcrun --show-sdk-version'])
            # Use the source-pinned downloader/checksum recipes. NO_WALLET only
            # omits hardware-wallet dependencies; simplewallet still builds.
            run('depends', ['make', '-j2', 'HOST=arm64-apple-darwin', 'NO_WALLET=1', 'NO_READLINE=1',
                            'DOWNLOAD_RETRIES=1', 'DOWNLOAD_CONNECT_TIMEOUT=20'], 2400,
                source / 'contrib/depends')
            downloads = out / 'downloads'
            downloads.mkdir()
            for component in ['rustc', 'cargo', 'rust-std']:
                filename = component + '-1.93.0-aarch64-apple-darwin.tar.xz'
                url = 'https://static.rust-lang.org/dist/' + filename
                with urllib.request.urlopen(url + '.sha256', timeout=30) as response:
                    expected = response.read().decode().split()[0]
                archive = downloads / filename
                with urllib.request.urlopen(url, timeout=90) as response, archive.open('wb') as stream:
                    shutil.copyfileobj(response, stream)
                tester.require(tester.sha(archive) == expected, 'Rust download checksum mismatch')
                receipt['downloads'].append({'url': url, 'sha256': expected})
                save()
                with tarfile.open(archive) as stream:
                    stream.extractall(downloads, filter='data')
                installer = downloads / filename.removesuffix('.tar.xz') / 'install.sh'
                run('install-' + component, ['sh', str(installer), '--prefix=' + str(out / 'rust'), '--disable-ldconfig'])
            tester.require(tester.command([str(out / 'rust/bin/rustc'), '-V']) == PIN['builder']['rustc'], 'Rust pin mismatch')
            shutil.copytree(args.cache / 'cargo-home', out / 'cargo-home')
            env = dict(os.environ, PATH=str(out / 'rust/bin') + ':' + os.environ['PATH'],
                       CARGO_HOME=str(out / 'cargo-home'), CARGO_NET_OFFLINE='true', CARGO_BUILD_JOBS='1')
            os.environ.update(env)
            binary_dir = source / 'build/portable'
            binary_dir.mkdir(parents=True)
            run('configure', ['cmake', '-DCMAKE_BUILD_TYPE=Release', '-DARCH=default', '-DBUILD_TESTS=OFF',
                '-DUSE_DEVICE_TREZOR=OFF', '-DUSE_READLINE=OFF', '-DMANUAL_SUBMODULES=ON',
                '-DCMAKE_OSX_DEPLOYMENT_TARGET=11.0', '-DCMAKE_TOOLCHAIN_FILE=' + str(source /
                'contrib/depends/arm64-apple-darwin/share/toolchain.cmake'), '../..'], 300, binary_dir)
            run('build', ['make', '-j1', 'daemon', 'simplewallet', 'wallet_rpc_server'], 2400, binary_dir)
            receipt['binaries'] = {name: tester.sha(binary_dir / 'bin' / name)
                                  for name in ['monerod', 'monero-wallet-cli', 'monero-wallet-rpc']}
            receipt['result'] = 'BUILT_JOURNEY_UNTESTED'
        finally:
            save()


if __name__ == '__main__':
    def cancelled(signum, frame):
        raise RuntimeError('native build cancelled; preserve owned diagnostics')
    signal.signal(signal.SIGTERM, cancelled)
    main()
