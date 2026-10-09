#!/usr/bin/env python3
"""Build pinned Windows programs with task-only compilers and owned containers.

Uses the pinned contrib/depends README route. Package downloads use signed apt
indices; Rust and LLVM archives use the independently recorded exact checksums.
Cross outputs are always BUILT_UNTESTED, never native execution evidence.
"""
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
import urllib.request
import difflib
import re

spec = importlib.util.spec_from_file_location('portable_build', Path(__file__).with_name('portable-build.py'))
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
tester, PIN = builder.tester, builder.PIN

TARGETS = {
    'windows-x86_64': ('x86_64-w64-mingw32', 'x86_64-pc-windows-gnu', 'x86-64'),
    'windows-i686': ('i686-w64-mingw32', 'i686-pc-windows-gnu', 'i686'),
    'windows-aarch64': ('aarch64-w64-mingw32', 'aarch64-pc-windows-gnullvm', None),
}


def main():
    os.environ['GIT_OPTIONAL_LOCKS'] = '0'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--rust', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--target', choices=TARGETS, required=True)
    parser.add_argument('--preflight', type=Path, required=True)
    args = parser.parse_args()
    out = tester.fresh(args.out)
    preflight = tester.read(args.preflight)
    tester.require(tester.sha(args.preflight) == 'f3f25c38fea7a53e20b8e113ef823d382ecd8b40ba2057352d8219a4cb60a205', 'unverified route preflight')
    host, rust_target, apt_arch = TARGETS[args.target]
    image = PIN['builder']['image_id']
    with tester.heavy_lock():
        tester.require(shutil.disk_usage(out.parent).free >= 10 * 1024**3, 'requires ten GiB disk reserve')
        available = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))) * 1024
        tester.require(available >= 5 * 1024**3, 'requires five GiB available memory')
        tester.require(tester.command(['docker', 'image', 'inspect', image, '--format', '{{.Architecture}} {{.Os}}']) == 'amd64 linux', 'wrong builder architecture')
        out.mkdir(mode=0o700)
        receipt = {'schema': 'meownero-windows-cross-build/1', 'source_lock': PIN, 'target': args.target,
                   'builder_image': image, 'commands': [], 'containers': [], 'patches': [], 'result': 'INCOMPLETE'}

        def save():
            tester.write(out / 'build-receipt.json', receipt)

        def run(label, argv, timeout=60, cwd=None):
            row = {'label': label, 'argv': argv}
            receipt['commands'].append(row)
            began = time.monotonic()
            save()
            try:
                with (out / (label + '.log')).open('wb') as log:
                    mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT})
                    p = None
                    try:
                        p = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT, cwd=cwd,
                            start_new_session=True, preexec_fn=lambda: signal.pthread_sigmask(signal.SIG_SETMASK, mask))
                        row['process_group'] = p.pid
                        signal.pthread_sigmask(signal.SIG_SETMASK, mask)
                        row['exit'] = p.wait(timeout=timeout)
                    finally:
                        signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT})
                        if p is not None and p.poll() is None:
                            os.killpg(p.pid, signal.SIGTERM)
                            try:
                                p.wait(timeout=10)
                            except subprocess.TimeoutExpired:
                                os.killpg(p.pid, signal.SIGKILL)
                                p.wait(timeout=5)
                        row['reaped'] = p is None or p.poll() is not None
                        signal.pthread_sigmask(signal.SIG_SETMASK, mask)
                tester.require(row['exit'] == 0, label + ' failed; diagnostics preserved')
            finally:
                row['wall_seconds'] = time.monotonic() - began
                save()
            print(label, row['exit'], flush=True)

        def contained(label, script, network=False, timeout=1800):
            invocation = uuid.uuid4().hex
            name = 'tjs1882-3175-' + invocation
            cidfile = out / (invocation + '.container.id')
            row = {'label': label, 'invocation': invocation, 'removed': False}
            receipt['containers'].append(row)
            save()
            argv = ['docker', 'run', '--pull=never', '--name', name, '--cidfile', str(cidfile),
                    '--label', 'meownero.invocation=' + invocation,
                    '--network=' + ('bridge' if network else 'none'), '--cpus=2', '--memory=3g',
                    '--memory-swap=3g', '--pids-limit=256', '--cap-drop=ALL',
                    '--security-opt=no-new-privileges', '--ulimit', 'core=0', '-u', f'{os.getuid()}:{os.getgid()}',
                    '-v', str(out) + ':/out', '-w', '/out/monero-fcmp',
                    '-e', 'HOME=/tmp', '-e', 'CARGO_HOME=/out/cargo-home', '-e', 'CARGO_NET_OFFLINE=true',
                    '-e', 'CARGO_BUILD_JOBS=1', '-e', 'PATH=/out/toolchain/usr/bin:/out/llvm/bin:/out/rust/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
                    image, 'bash', '-ec', 'trap \'cat /sys/fs/cgroup/memory.peak > /out/' + label + '.memory; cat /sys/fs/cgroup/memory.events > /out/' + label + '.memory-events\' EXIT\n' + script]
            try:
                run(label, argv, timeout)
            finally:
                if cidfile.exists():
                    cid = cidfile.read_text().strip()
                    observed = json.loads(tester.command(['docker', 'inspect', cid]))[0]
                    tester.require(observed['Id'] == cid and observed['Name'] == '/' + name and observed['Image'] == image and observed['Config']['Labels'].get('meownero.invocation') == invocation, 'owned container proof failed')
                    row['id'] = cid
                    run(label + '-cleanup', ['docker', 'rm', '-f', cid], 30)
                    tester.require(cid not in tester.command(['docker', 'ps', '-aq', '--no-trunc']).splitlines(), 'owned container remains')
                    row['removed'] = True
                    save()

        try:
            builder.export_sources(args.cache.resolve(), out / 'monero-fcmp', out, run)
            shutil.copytree(args.cache / 'cargo-home', out / 'cargo-home')
            tester.require(tester.command([str(args.rust / 'bin/rustc'), '-V']) == PIN['builder']['rustc'], 'Rust pin mismatch')
            shutil.copytree(args.rust, out / 'rust', symlinks=False)
            rust_archive = preflight['rust_std_artifacts'][rust_target]
            downloads = out / 'downloads'
            downloads.mkdir()

            def download(url, checksum, filename):
                path = downloads / filename
                with urllib.request.urlopen(url, timeout=180) as response, path.open('wb') as stream:
                    shutil.copyfileobj(response, stream)
                tester.require(tester.sha(path) == checksum, 'download checksum mismatch: ' + filename)
                receipt.setdefault('downloads', []).append({'url': url, 'sha256': checksum, 'bytes': path.stat().st_size})
                save()

            download(rust_archive['url'], rust_archive['published_sha256'], 'rust-std.tar.xz')
            preparation = 'mkdir -p /out/downloads /out/toolchain\n'
            packages = ['curl']
            if apt_arch:
                packages += ['binutils-mingw-w64-' + apt_arch, 'gcc-mingw-w64-' + apt_arch + '-posix',
                            'gcc-mingw-w64-' + apt_arch + '-posix-runtime', 'g++-mingw-w64-' + apt_arch + '-posix',
                            'mingw-w64-' + apt_arch + '-dev', 'mingw-w64-common', 'gcc-mingw-w64-base']
            apt_options = '-o Dir::State::lists=/out/apt-lists -o Dir::Cache=/out/apt-cache'
            preparation += 'mkdir -p /out/apt-lists/partial /out/apt-cache\napt-get ' + apt_options + ' -o Acquire::Retries=1 -o Acquire::http::Timeout=30 update\ncd /out/downloads\napt-get ' + apt_options + ' download ' + ' '.join(packages) + '\nfor pkg in *.deb; do dpkg-deb -x "$pkg" /out/toolchain; done\n'
            preparation += 'apt-cache ' + apt_options + ' policy ' + ' '.join(packages) + ' > /out/toolchain-packages.txt\nsha256sum *.deb > /out/toolchain-SHA256SUMS\n'
            if not apt_arch:
                llvm = preflight['llvm_mingw_option']
                download(llvm['url'], llvm['github_asset_digest'].split(':')[1], 'llvm.tar.xz')
                preparation += 'mkdir /out/llvm\ntar -xJf /out/downloads/llvm.tar.xz --strip-components=1 -C /out/llvm\n'
            preparation += 'tar -xJf /out/downloads/rust-std.tar.xz -C /out/downloads\nsh /out/downloads/rust-std-1.93.0-' + rust_target + '/install.sh --prefix=/out/rust --disable-ldconfig\n'
            contained('toolchain', preparation, network=True, timeout=600)
            receipt['rustc_sha256'] = tester.sha(out / 'rust/bin/rustc')
            receipt['cargo_sha256'] = tester.sha(out / 'rust/bin/cargo')
            receipt['toolchain_packages'] = {path.name: tester.sha(path) for path in sorted(downloads.glob('*.deb'))}
            receipt['rust_target'] = rust_target
            receipt['rust_std_download'] = rust_archive
            cc = '/out/toolchain/usr/bin/' + host + '-gcc-posix' if apt_arch else '/out/llvm/bin/' + host + '-clang'
            cxx = cc.replace('gcc-posix', 'g++-posix') if apt_arch else cc + '++'
            options = ['HOST=' + host, 'NO_WALLET=1', 'NO_READLINE=1', 'DOWNLOAD_RETRIES=1', 'DOWNLOAD_CONNECT_TIMEOUT=20', 'mingw32_CC=' + cc, 'mingw32_CXX=' + cxx]
            if not apt_arch:
                source = out / 'monero-fcmp'

                def adapt(relative, old, new):
                    path = source / relative
                    original = path.read_text()
                    tester.require(original.count(old) == 1, 'adaptation does not match pinned source: ' + relative)
                    before = tester.sha(path)
                    changed = original.replace(old, new)
                    path.write_text(changed)
                    patch = out / ('adaptation-' + relative.replace('/', '-') + '.patch')
                    patch.write_text(''.join(difflib.unified_diff(original.splitlines(True), changed.splitlines(True), fromfile=relative, tofile=relative)))
                    receipt['patches'].append({'file': relative, 'before_sha256': before, 'after_sha256': tester.sha(path), 'patch_sha256': tester.sha(patch)})
                    save()

                adapt('src/fcmp_pp/fcmp_pp_rust/CMakeLists.txt', 'if(MINGW)\n  set(RUST_PLATFORM "pc-windows")\n  set(RUST_TOOLCHAIN "-gnu")',
                      'if(MINGW)\n  set(RUST_PLATFORM "pc-windows")\n  if(RUST_ARCH STREQUAL "aarch64" AND CMAKE_CXX_COMPILER_ID MATCHES "Clang")\n    set(RUST_TOOLCHAIN "-gnullvm")\n  else()\n    set(RUST_TOOLCHAIN "-gnu")\n  endif()')
                adapt('contrib/depends/packages/boost.mk', '$(package)_config_opts_i686_mingw32=address-model=32',
                      '$(package)_config_opts_i686_mingw32=address-model=32\n$(package)_config_opts_aarch64_mingw32=address-model=64 architecture=arm')
                adapt('contrib/depends/packages/openssl.mk', '$(package)_config_opts_i686_mingw32=mingw',
                      '$(package)_config_opts_i686_mingw32=mingw\n$(package)_config_opts_aarch64_mingw32=mingwarm64')
                adapt('contrib/depends/packages/openssl.mk', '$(package)_patches=fix-android.patch',
                      '$(package)_patches=fix-android.patch 99-tjs1882-mingwarm64.conf')
                adapt('contrib/depends/packages/openssl.mk', '  patch -p1 < $($(package)_patch_dir)/fix-android.patch &&',
                      '  patch -p1 < $($(package)_patch_dir)/fix-android.patch && \\\n  cp $($(package)_patch_dir)/99-tjs1882-mingwarm64.conf Configurations/99-tjs1882-mingwarm64.conf &&')
                config = source / 'contrib/depends/patches/openssl/99-tjs1882-mingwarm64.conf'
                # Configuration-only backport from openssl/e9344b08, 10-main.conf.
                # The pinned 3.5.8 cryptographic implementation is unchanged.
                config.write_text('my %targets = (\n    "mingwarm64" => {\n        inherit_from => [ "mingw-common" ],\n        cflags => "",\n        sys_id => "MINGWARM64",\n        bn_ops => add("SIXTY_FOUR_BIT"),\n        asm_arch => "aarch64",\n        uplink_arch => "armv8",\n        perlasm_scheme => "win64",\n        shared_rcflag => "",\n        multilib => "-arm64",\n    },\n);\n')
                receipt['patches'].append({'file': str(config.relative_to(source)), 'sha256': tester.sha(config), 'reference': 'https://raw.githubusercontent.com/openssl/openssl/e9344b082ffa78cb1d68f6446c1b6417c4244a00/Configurations/10-main.conf'})
                options += ['boost_toolset_mingw32=clang']
                options += ['mingw32_' + upper + '=/out/llvm/bin/llvm-' + lower for upper, lower in [('AR', 'ar'), ('RANLIB', 'ranlib'), ('NM', 'nm'), ('STRIP', 'strip')]]
                options += ['host_WINDRES=/out/llvm/bin/' + host + '-windres']
            make = ' '.join(options)
            contained('download-depends', 'cd contrib/depends\nmake -j2 ' + make + ' download-win\n', network=True, timeout=600)
            script = cc + ' --version > /out/compiler.txt\n' + (host + '-ld' if apt_arch else '/out/llvm/bin/ld.lld') + ' --version >> /out/compiler.txt\nrustc -Vv >> /out/compiler.txt\n'
            if apt_arch:
                script += host + '-ld --version | head -1 | grep -E " (2\\.(4[0-9]|[5-9][0-9])|[3-9]\\.)"\n'
            script += 'test "$(rustc -V)" = "' + PIN['builder']['rustc'] + '"\n'
            script += 'cd contrib/depends\nmake -j2 ' + make + '\ncd ../..\nmkdir -p build/portable\ncd build/portable\ncmake -DCMAKE_BUILD_TYPE=Release -DARCH=default -DBUILD_TESTS=OFF -DUSE_DEVICE_TREZOR=OFF -DUSE_READLINE=OFF -DMANUAL_SUBMODULES=ON -DCMAKE_TOOLCHAIN_FILE=/out/monero-fcmp/contrib/depends/' + host + '/share/toolchain.cmake ../..\nmake -j1 daemon simplewallet wallet_rpc_server\n'
            contained('build', script, timeout=3600)
            receipt['binaries'] = {name: {'sha256': tester.sha(out / 'monero-fcmp/build/portable/bin' / (name + '.exe'))} for name in ('monerod', 'monero-wallet-cli', 'monero-wallet-rpc')}
            receipt['result'] = 'BUILT_UNTESTED'
        except BaseException as error:
            receipt['result'] = 'FAILED_ATTEMPT'
            receipt['failure'] = str(error)
            raise
        finally:
            save()


if __name__ == '__main__':
    def cancelled(signum, frame):
        raise RuntimeError('cross build cancelled; clean exact owned container')
    signal.signal(signal.SIGTERM, cancelled)
    main()
