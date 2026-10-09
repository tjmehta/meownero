#!/usr/bin/env python3
"""Build locked Mac targets using explicit Xcode targets and owned writes."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import resource
import portable_licenses
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
    parser.add_argument('--target', choices=['macos-aarch64', 'macos-x86_64'], default='macos-aarch64')
    args = parser.parse_args()
    tester.require(platform.system() == 'Darwin' and platform.machine() == 'arm64', 'native Apple Silicon required')
    out = tester.fresh(args.out)
    with tester.heavy_lock():
        tester.require(shutil.disk_usage(out.parent).free >= 10 * 1024**3, 'requires ten GiB disk reserve')
        out.mkdir(mode=0o700)
        host = 'arm64-apple-darwin' if args.target == 'macos-aarch64' else 'x86_64-apple-darwin'
        receipt = {'schema': 'meownero-native-mac-build/1', 'source_lock': PIN, 'target': args.target,
                   'execution_substrate': 'NATIVE_ARM64' if args.target == 'macos-aarch64' else 'CROSS_BUILT_ON_ARM64',
                   'commands': [], 'downloads': [], 'result': 'INCOMPLETE'}

        def save():
            tester.write(out / 'build-receipt.json', receipt)

        def run(label, argv, timeout=60, cwd=None):
            row = {'label': label, 'argv': argv}
            receipt['commands'].append(row)
            began = time.monotonic()
            def limits():
                resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
            try:
                with (out / (label + '.log')).open('wb') as log:
                    mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT})
                    def child_setup():
                        limits()
                        signal.pthread_sigmask(signal.SIG_SETMASK, mask)
                    try:
                        process = subprocess.Popen(argv, cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
                                                   start_new_session=True, preexec_fn=child_setup)
                        row['process_group'] = process.pid
                        row['peak_resident_bytes'] = 0
                        row['resident_limit_bytes'] = 4 * 1024**3
                        row['reaped'] = False
                        save()
                        signal.pthread_sigmask(signal.SIG_SETMASK, mask)
                        # Darwin rejects a four-GiB RLIMIT_DATA. Bound the owned
                        # process group's total resident memory instead.
                        while True:
                            rows = subprocess.check_output(['ps', '-axo', 'pgid=,rss='], text=True, timeout=10)
                            resident = sum(int(fields[1]) * 1024 for line in rows.splitlines()
                                if len(fields := line.split()) == 2 and int(fields[0]) == process.pid)
                            row['peak_resident_bytes'] = max(row['peak_resident_bytes'], resident)
                            tester.require(resident <= row['resident_limit_bytes'], 'owned process memory limit')
                            remaining = timeout - (time.monotonic() - began)
                            if remaining <= 0:
                                raise subprocess.TimeoutExpired(argv, timeout)
                            try:
                                row['exit'] = process.wait(timeout=min(1, remaining))
                                break
                            except subprocess.TimeoutExpired:
                                pass
                    except BaseException as error:
                        if 'process' in locals():
                            try:
                                os.killpg(process.pid, 15)
                            except ProcessLookupError:
                                pass
                            try:
                                process.wait(timeout=10)
                            except subprocess.TimeoutExpired:
                                os.killpg(process.pid, 9)
                                process.wait(timeout=5)
                        row['exit'] = 124
                        if not isinstance(error, subprocess.TimeoutExpired):
                            raise
                    finally:
                        signal.pthread_sigmask(signal.SIG_SETMASK, mask)
                        if 'process' in locals():
                            row['reaped'] = process.poll() is not None
                tester.require(row['exit'] == 0, label + ' failed; preserved diagnostics')
            finally:
                row['wall_seconds'] = time.monotonic() - began
                save()
            print(label, row['exit'], flush=True)

        try:
            source = out / 'monero-fcmp'
            builder.export_sources(args.cache.resolve(), source, out, run)
            run('native-toolchain', ['sh', '-c', 'clang --version; cmake --version; xcrun --show-sdk-path; xcrun --show-sdk-version'])
            sdk = tester.command(['xcrun', '--show-sdk-path'])
            cc = tester.command(['xcrun', '-f', 'clang'])
            cxx = tester.command(['xcrun', '-f', 'clang++'])
            receipt['sdk'] = sdk
            receipt['sdk_version'] = tester.command(['xcrun', '--show-sdk-version'])
            # Use the source-pinned downloader/checksum recipes. NO_WALLET only
            # omits hardware-wallet dependencies; simplewallet still builds.
            run('depends', ['make', '-j2', 'HOST=' + host, 'NO_WALLET=1', 'NO_READLINE=1',
                            'DOWNLOAD_RETRIES=1', 'DOWNLOAD_CONNECT_TIMEOUT=20',
                            'darwin_CC=' + cc + ' --target=' + host + ' -isysroot ' + sdk + ' -mmacosx-version-min=11.0',
                            'darwin_CXX=' + cxx + ' --target=' + host + ' -isysroot ' + sdk + ' -mmacosx-version-min=11.0 -stdlib=libc++',
                            'darwin_LDFLAGS=-Wl,-platform_version,macos,11.0,' + receipt['sdk_version']], 2400,
                source / 'contrib/depends')
            receipt['dependency_licenses'] = portable_licenses.retain_depends(out)
            save()
            downloads = out / 'downloads'
            downloads.mkdir()
            components = [(component, 'aarch64-apple-darwin') for component in ['rustc', 'cargo', 'rust-std']]
            if args.target == 'macos-x86_64':
                components.append(('rust-std', 'x86_64-apple-darwin'))
            for component, rust_host in components:
                filename = component + '-1.93.0-' + rust_host + '.tar.xz'
                url = 'https://static.rust-lang.org/dist/' + filename
                with urllib.request.urlopen(url + '.sha256', timeout=30) as response:
                    expected = response.read().decode().split()[0]
                if rust_host == 'x86_64-apple-darwin':
                    tester.require(expected == 'f112d41c8a31794f0f561d37fe77010ed0b405fa70284a2910891869d8c52418', 'Intel std differs from verified preflight')
                archive = downloads / filename
                with urllib.request.urlopen(url, timeout=90) as response, archive.open('wb') as stream:
                    shutil.copyfileobj(response, stream)
                tester.require(tester.sha(archive) == expected, 'Rust download checksum mismatch')
                receipt['downloads'].append({'url': url, 'sha256': expected})
                save()
                with tarfile.open(archive) as stream:
                    stream.extractall(downloads, filter='data')
                installer = downloads / filename.removesuffix('.tar.xz') / 'install.sh'
                run('install-' + component + '-' + rust_host, ['sh', str(installer), '--prefix=' + str(out / 'rust'), '--disable-ldconfig'])
            tester.require(tester.command([str(out / 'rust/bin/rustc'), '-V']) == PIN['builder']['rustc'], 'Rust pin mismatch')
            shutil.copytree(args.cache / 'cargo-home', out / 'cargo-home')
            env = dict(os.environ, PATH=str(out / 'rust/bin') + ':' + os.environ['PATH'],
                       CARGO_HOME=str(out / 'cargo-home'), CARGO_NET_OFFLINE='true', CARGO_BUILD_JOBS='1',
                       SDKROOT=sdk, MACOSX_DEPLOYMENT_TARGET='11.0')
            os.environ.update(env)
            binary_dir = source / 'build/portable'
            binary_dir.mkdir(parents=True)
            run('configure', ['cmake', '-DCMAKE_BUILD_TYPE=Release', '-DARCH=default', '-DBUILD_TESTS=OFF',
                '-DUSE_DEVICE_TREZOR=OFF', '-DUSE_READLINE=OFF', '-DMANUAL_SUBMODULES=ON',
                '-DCMAKE_OSX_DEPLOYMENT_TARGET=11.0', '-DCMAKE_TOOLCHAIN_FILE=' + str(source /
                ('contrib/depends/' + host + '/share/toolchain.cmake')), '../..'], 300, binary_dir)
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
