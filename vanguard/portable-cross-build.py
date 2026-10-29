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
import platform
import shutil
import signal
import subprocess
import tarfile
import time
import uuid
import urllib.request
import difflib
import re
from portable_provenance import recorded_receipt

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
    parser.add_argument('--i686-build-cache', type=Path, help='Retained failed, unpatched i686 compilation; verify pinned sources before copying')
    parser.add_argument('--builder-transfer', type=Path, help='Exact saved pinned image; verify legacy Docker config re-encoding on Colima')
    args = parser.parse_args()
    tester.require(not args.i686_build_cache or args.target == 'windows-i686', 'cache recovery is i686 only')
    for program in ('rustc', 'cargo'):
        executable = tester.regular(args.rust / 'bin' / program)
        with executable.open('rb') as stream:
            header = stream.read(20)
        tester.require(header[:6] == b'\x7fELF\x02\x01' and
                       int.from_bytes(header[18:20], 'little') == 62,
                       'Rust compiler input must be ELF64 amd64 for the pinned compiler container')
    out = tester.fresh(args.out)
    preflight = tester.read(args.preflight)
    tester.require(tester.sha(args.preflight) == 'f3f25c38fea7a53e20b8e113ef823d382ecd8b40ba2057352d8219a4cb60a205', 'unverified route preflight')
    host, rust_target, apt_arch = TARGETS[args.target]
    image = PIN['builder']['image_id']
    mac = platform.system() == 'Darwin'
    tester.require((mac and platform.machine() == 'arm64') or
                   (platform.system() == 'Linux' and platform.machine() == 'x86_64'), 'unsupported compiler host')
    docker = ['docker', '--context', 'colima'] if mac else ['docker']
    transfer = None
    with tester.heavy_lock():
        tester.require(shutil.disk_usage(out.parent).free >= 10 * 1024**3, 'requires ten GiB disk reserve')
        memory = tester.command(['colima', 'ssh', '--', 'cat', '/proc/meminfo']) if mac else Path('/proc/meminfo').read_text()
        available = int(next(line.split()[1] for line in memory.splitlines() if line.startswith('MemAvailable:'))) * 1024
        tester.require(available >= 5 * 1024**3, 'requires five GiB available memory')
        docker_free = int(tester.command(['colima', 'ssh', '--', 'df', '-B1', '/var/lib/docker']).splitlines()[-1].split()[3]) if mac else shutil.disk_usage('/var/lib/docker').free
        tester.require(docker_free >= 10 * 1024**3, 'requires ten GiB Docker disk reserve')
        if args.builder_transfer:
            tester.require(mac and tester.sha(args.builder_transfer) == '01a5bd95b757995fb4d1f2212cb44805c8173217e94d58e3fb6d2ee6a4630ca2', 'unverified builder transfer')
            with tarfile.open(args.builder_transfer) as archive:
                manifests = json.load(archive.extractfile('manifest.json'))
                tester.require(len(manifests) == 1, 'ambiguous transferred image')
                config_bytes = archive.extractfile(manifests[0]['Config']).read()
            import hashlib
            tester.require('sha256:' + hashlib.sha256(config_bytes).hexdigest() == image, 'saved image does not match the pinned config')
            source_config = json.loads(config_bytes)
            image = 'sha256:d0d9ff472379e2cc7a1f9b046fc6bc031ef98c36dcf08614b307d59323b6cb4c'
            observed = json.loads(tester.command(docker + ['image', 'inspect', image]))[0]
            tester.require(observed['Id'] == image and observed['Config'] == source_config['config'] and
                           observed['RootFS']['Layers'] == source_config['rootfs']['diff_ids'] and
                           observed['Created'] == source_config['created'] and observed['Os'] == source_config['os'] and
                           observed['Architecture'] == source_config['architecture'] and
                           observed.get('Author', '') == source_config.get('author', '') and
                           observed.get('DockerVersion', '') == source_config.get('docker_version', ''), 'loaded image content/configuration differs from the pin')
            transfer = {'source_image': PIN['builder']['image_id'], 'loaded_image': image,
                        'transfer_archive_sha256': tester.sha(args.builder_transfer),
                        'identical_rootfs_diff_ids': source_config['rootfs']['diff_ids'],
                        'runtime_config_identical': True, 'reason': 'Legacy Docker loader re-encoded image metadata; complete filesystem layers and runtime configuration verified identical.'}
        tester.require(tester.command(docker + ['image', 'inspect', image, '--format', '{{.Architecture}} {{.Os}}']) == 'amd64 linux', 'wrong builder architecture')
        if mac:
            tester.require(not tester.command(docker + ['ps', '-q']), 'Docker busy; preserve other workloads')
            emulation = tester.command(['colima', 'ssh', '--', 'cat', '/proc/sys/fs/binfmt_misc/qemu-x86_64'])
            tester.require(emulation.startswith('enabled\n') and 'flags: POCF' in emulation, 'already-enabled x64 container translation required')
        out.mkdir(mode=0o700)
        receipt = {'schema': 'meownero-windows-cross-build/1', 'source_lock': PIN, 'target': args.target,
                   'builder_image': image, 'compiler_execution_substrate': 'PREEXISTING_QEMU_AMD64_ON_COLIMA_ARM64' if mac else 'NATIVE_AMD64_LINUX',
                   'commands': [], 'containers': [], 'patches': [], 'result': 'INCOMPLETE'}
        if transfer:
            receipt['builder_transfer'] = transfer

        def save():
            tester.write(out / 'build-receipt.json', recorded_receipt(receipt))

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
                cleanup_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT})
                cleanup_handlers = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGINT)}
                try:
                    row['wall_seconds'] = time.monotonic() - began
                    save()
                finally:
                    try:
                        for number, handler in cleanup_handlers.items():
                            signal.signal(number, handler)
                    finally:
                        signal.pthread_sigmask(signal.SIG_SETMASK, cleanup_mask)
            try:
                print(label, row['exit'], flush=True)
            except BrokenPipeError:
                pass

        def contained(label, script, network=False, timeout=1800):
            invocation = uuid.uuid4().hex
            name = 'tjs1882-3175-' + invocation
            cidfile = out / (invocation + '.container.id')
            row = {'label': label, 'invocation': invocation, 'removed': False}
            receipt['containers'].append(row)
            save()
            argv = docker + ['run', '--platform=linux/amd64', '--pull=never', '--name', name, '--cidfile', str(cidfile),
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
                cleanup_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT})
                cleanup_handlers = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGINT)}
                try:
                    if cidfile.exists():
                        cid = cidfile.read_text().strip()
                        observed = json.loads(tester.command(docker + ['inspect', cid]))[0]
                        tester.require(observed['Id'] == cid and observed['Name'] == '/' + name and observed['Image'] == image and observed['Config']['Labels'].get('meownero.invocation') == invocation, 'owned container proof failed')
                        row['id'] = cid
                        run(label + '-cleanup', docker + ['rm', '-f', cid], 30)
                        tester.require(cid not in tester.command(docker + ['ps', '-aq', '--no-trunc']).splitlines(), 'owned container remains')
                        row['removed'] = True
                        save()
                finally:
                    try:
                        for number, handler in cleanup_handlers.items():
                            signal.signal(number, handler)
                    finally:
                        signal.pthread_sigmask(signal.SIG_SETMASK, cleanup_mask)

        try:
            if args.i686_build_cache:
                cached = args.i686_build_cache.resolve()
                prior = tester.read(cached / 'build-receipt.json')
                tester.require(prior['source_lock'] == PIN and prior['target'] == args.target and
                               prior['result'] == 'FAILED_ATTEMPT' and not prior['patches'] and
                               all(c['removed'] for c in prior['containers']), 'unverified failed compilation cache')
                verified = out / 'verified-sources'
                builder.export_sources(args.cache.resolve(), verified, out, run)
                files = [p for p in verified.rglob('*') if p.is_file()]
                for path in files:
                    tester.require(tester.sha(path) == tester.sha(cached / 'monero-fcmp' / path.relative_to(verified)), 'cached pinned source changed')
                tester.require(tester.sha(cached / 'rust/bin/rustc') == prior['rustc_sha256'] and
                               tester.sha(cached / 'rust/bin/cargo') == prior['cargo_sha256'], 'cached Rust compiler changed')
                for name, digest in prior['toolchain_packages'].items():
                    tester.require(tester.sha(cached / 'downloads' / name) == digest, 'cached signed toolchain download changed')
                tester.require(tester.sha(cached / 'downloads/rust-std.tar.xz') == prior['rust_std_download']['published_sha256'], 'cached target std changed')
                tester.require(tester.sha(cached / 'monero-fcmp/build/portable/src/fcmp_pp/fcmp_pp_rust/libfcmp_pp_rust.a') == 'a936650965fda87e81acd6e4319fea4a362d606d1251fe2f8ce6a4442382e547', 'cached compiled Rust archive differs from the retained ABI probe')
                shutil.copytree(cached, out, dirs_exist_ok=True, symlinks=True)
                shutil.copyfile(cached / 'build-receipt.json', out / 'cached-build-receipt.json')
                receipt['verified_cached_sources'] = len(files)
                receipt['cached_build'] = {'receipt_sha256': tester.sha(out / 'cached-build-receipt.json'), 'path': str(cached)}
                for key in ('rustc_sha256', 'cargo_sha256', 'toolchain_packages', 'rust_target', 'rust_std_download', 'downloads'):
                    receipt[key] = prior[key]
                helper = Path(__file__).with_name('portable_i686_unwind.py')
                shutil.copyfile(helper, out / 'i686-unwind.py')
                receipt['abi_helper_sha256'] = tester.sha(helper)
                save()
                contained('build', 'cd build/portable\nmake -j1 fcmp_pp_rust\npython3 /out/i686-unwind.py\nmake -j1 daemon simplewallet wallet_rpc_server\nfor program in monerod monero-wallet-cli monero-wallet-rpc; do i686-w64-mingw32-nm --defined-only bin/$program.exe > /out/$program.symbols; done\n', timeout=3600)
                adaptation = tester.read(out / 'i686-unwind-adaptation.json')
                for program in ('monerod', 'monero-wallet-cli', 'monero-wallet-rpc'):
                    symbols = (out / (program + '.symbols')).read_text()
                    strong = re.findall(r'^([0-9a-f]+) T __Unwind_Resume$', symbols, re.M)
                    tester.require(len(strong) == 1, 'missing strong GNU unwind implementation')
                    mapping = (out / (program + '.map')).read_text()
                    lines = mapping.splitlines()
                    matches = [i for i, line in enumerate(lines) if re.search(r'\s_Unwind_Resume$', line)]
                    tester.require(len(matches) == 1, 'ambiguous unwind link map')
                    block = next(line for line in reversed(lines[:matches[0]]) if line.startswith(' .text '))
                    tester.require('libgcc_eh.a(unwind-dw2.o)' in block and int(strong[0], 16) == int(lines[matches[0]].split()[0], 16), 'unwind bound to compatibility stub')
                fixture = Path(__file__).with_name('i686-exception-probe.cpp')
                shutil.copyfile(fixture, out / fixture.name)
                contained('exception-probe', 'cd /out\ni686-w64-mingw32-g++-posix -std=c++17 -O0 -static -Imonero-fcmp/src/fcmp_pp/fcmp_pp_rust /out/i686-exception-probe.cpp monero-fcmp/build/portable/src/fcmp_pp/fcmp_pp_rust/libfcmp_pp_rust.a -lws2_32 -luserenv -lntdll -lbcrypt -ladvapi32 -lsynchronization -Wl,-Map,/out/i686-exception-probe.map -o /out/i686-exception-probe.exe\ni686-w64-mingw32-objdump -d /out/i686-exception-probe.exe > /out/i686-exception-probe.disassembly\n', timeout=180)
                receipt['exception_probe'] = {'file': 'i686-exception-probe.exe', 'sha256': tester.sha(out / 'i686-exception-probe.exe'), 'source_sha256': tester.sha(fixture), 'native_execution': 'UNTESTED'}
                receipt['patches'].append({'kind': 'compiled ABI metadata only; pinned source unchanged', 'receipt_sha256': tester.sha(out / 'i686-unwind-adaptation.json'), 'all_other_archive_bytes_unchanged': adaptation['all_other_archive_bytes_unchanged'], 'native_exception_probe': 'UNTESTED'})
                receipt['binaries'] = {name: {'sha256': tester.sha(out / 'monero-fcmp/build/portable/bin' / (name + '.exe'))} for name in ('monerod', 'monero-wallet-cli', 'monero-wallet-rpc')}
                receipt['result'] = 'BUILT_UNTESTED'
                return
            builder.export_sources(args.cache.resolve(), out / 'monero-fcmp', out, run)
            shutil.copytree(args.cache / 'cargo-home', out / 'cargo-home')
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
            preparation = 'test "$(rustc -V)" = "' + PIN['builder']['rustc'] + '"\nmkdir -p /out/downloads /out/toolchain\n'
            packages = ['curl']
            if apt_arch:
                packages += ['binutils-mingw-w64-' + apt_arch, 'gcc-mingw-w64-' + apt_arch + '-posix',
                            'gcc-mingw-w64-' + apt_arch + '-posix-runtime', 'g++-mingw-w64-' + apt_arch + '-posix',
                            'mingw-w64-' + apt_arch + '-dev', 'mingw-w64-common', 'gcc-mingw-w64-base']
            apt_options = '-o Dir::State::lists=/out/apt-lists -o Dir::Cache=/out/apt-cache'
            unpack = 'dpkg-deb -x "$pkg" /out/toolchain'
            if mac and not apt_arch:
                # The informational curl changelog symlink fails on this
                # existing shared filesystem. Executables and license texts
                # still come intact from the same signed package.
                unpack = 'dpkg-deb --fsys-tarfile "$pkg" | tar --exclude=./usr/share/doc/curl/changelog.Debian.gz -xf - -C /out/toolchain'
                receipt['toolchain_unpack'] = {'excluded_documentation_symlink': './usr/share/doc/curl/changelog.Debian.gz', 'executables_and_license_texts_unchanged': True}
            preparation += 'mkdir -p /out/apt-lists/partial /out/apt-cache\napt-get ' + apt_options + ' -o Acquire::Retries=1 -o Acquire::http::Timeout=30 update\ncd /out/downloads\napt-get ' + apt_options + ' download ' + ' '.join(packages) + '\nfor pkg in *.deb; do ' + unpack + '; done\n'
            preparation += 'apt-cache ' + apt_options + ' policy ' + ' '.join(packages) + ' > /out/toolchain-packages.txt\nsha256sum *.deb > /out/toolchain-SHA256SUMS\n'
            if not apt_arch:
                llvm = preflight['llvm_mingw_option']
                download(llvm['url'], llvm['github_asset_digest'].split(':')[1], 'llvm.tar.xz')
                if mac:
                    # Native extraction preserves the distribution's relative
                    # header symlinks; translated GNU tar failed on this share.
                    with tarfile.open(downloads / 'llvm.tar.xz') as archive:
                        members = archive.getmembers()
                        roots = {Path(member.name).parts[0] for member in members}
                        tester.require(len(roots) == 1, 'ambiguous LLVM archive root')
                        archive.extractall(downloads, filter='data')
                    (downloads / roots.pop()).rename(out / 'llvm')
                    receipt['llvm_unpack'] = {'method': 'native Python tarfile data filter', 'archive_sha256': tester.sha(downloads / 'llvm.tar.xz'), 'distribution_symlinks_preserved': True}
                    save()
                else:
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
                adapt('contrib/depends/hosts/mingw32.mk', 'mingw32_ARFLAGS=cr',
                      'mingw32_ARFLAGS=cr\nmingw32_CPPFLAGS=-DWINVER=0x0A00 -D_WIN32_WINNT=0x0A00 -DBOOST_USE_WINAPI_VERSION=0x0A00')
                adapt('CMakeLists.txt', 'add_definitions(-DWINVER=0x0601 -D_WIN32_WINNT=0x0601)',
                      'if(CMAKE_SYSTEM_PROCESSOR STREQUAL "aarch64" AND CMAKE_CXX_COMPILER_ID MATCHES "Clang")\n      add_definitions(-DWINVER=0x0A00 -D_WIN32_WINNT=0x0A00 -DBOOST_USE_WINAPI_VERSION=0x0A00)\n    else()\n      add_definitions(-DWINVER=0x0601 -D_WIN32_WINNT=0x0601)\n    endif()')
                receipt['windows_api_floor'] = 'Windows 10 across the ARM64 dependency and program closure; matches tester minimum, resolves Boost atomic wait declarations.'
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
                # Exact non-crypto ARM64 MinGW counter compatibility backport.
                # Keep ZeroMQ4.3.5 and every dependency archive pin unchanged.
                adapt('contrib/depends/packages/zeromq.mk',
                      '$(package)_sha256_hash=6653ef5910f17954861fe72332e68b03ca6e4d9c7160eb3a8de5a5a913bfab43',
                      '$(package)_sha256_hash=6653ef5910f17954861fe72332e68b03ca6e4d9c7160eb3a8de5a5a913bfab43\n$(package)_patches=windows-arm-counter.patch windows-arm-nothrow.patch')
                adapt('contrib/depends/packages/zeromq.mk',
                      '  cp -f $(BASEDIR)/config.guess $(BASEDIR)/config.sub config',
                      '  cp -f $(BASEDIR)/config.guess $(BASEDIR)/config.sub config && \\\n  patch -p1 < $($(package)_patch_dir)/windows-arm-counter.patch && \\\n  patch -p1 < $($(package)_patch_dir)/windows-arm-nothrow.patch')
                counter = source / 'contrib/depends/patches/zeromq/windows-arm-counter.patch'
                counter.parent.mkdir(parents=True, exist_ok=True)
                counter.write_text('--- a/src/clock.cpp\n+++ b/src/clock.cpp\n@@ -225,2 +225,6 @@\n     return _ReadStatusReg (pmccntr_el0);\n+#elif (defined(_WIN32) && defined(__GNUC__) && defined(__aarch64__))\n+    uint64_t val;\n+    __asm__ volatile("mrs %0, pmccntr_el0" : "=r"(val));\n+    return val;\n #elif (defined __GNUC__ && (defined __i386__ || defined __x86_64__))\n')
                receipt['patches'].append({'file': str(counter.relative_to(source)), 'sha256': tester.sha(counter),
                    'reference': 'https://github.com/zeromq/libzmq/commit/b71434140e8ed40b1840a5704370bfc8dfdbf627',
                    'scope': 'Exact upstream ARM64 Windows GNU counter branch only; no version/crypto/consensus change.'})
                nothrow = counter.with_name('windows-arm-nothrow.patch')
                nothrow.write_text('--- a/src/polling_util.hpp\n+++ b/src/polling_util.hpp\n@@ -6,2 +6,3 @@\n #include <stdlib.h>\n+#include <new>\n #include <vector>\n')
                receipt['patches'].append({'file': str(nothrow.relative_to(source)), 'sha256': tester.sha(nothrow),
                    'reference': 'https://github.com/zeromq/libzmq/commit/2e8a6ccb414ca79636392604893c79c3b0d00dc4',
                    'scope': 'Exact upstream missing C++ <new> declaration include for std::nothrow; no implementation/version/crypto/consensus change.'})
                allocator = source / 'external/randomx/src/intrin_portable.h'
                allocator_patch = Path(__file__).with_name('patches') / 'randomx-aaafe713-windows-arm64-aligned-allocator.patch'
                tester.require(args.target == 'windows-aarch64' and
                    PIN['upstream']['submodules']['external/randomx'] == 'aaafe71322df6602c21a5c72937ac284724ae561' and
                    tester.sha(allocator) == '07588f5d3e01d1ad9ad375b05a232f5c43c9f6a3c264c2960e7306cdbf73c80f' and
                    tester.sha(allocator_patch) == '175fc5e0344b3e8e1932eebbf39a3c23314c401ad9bc20a588cd8fe6e5052b82',
                    'unverified ARM64 platform allocator adaptation')
                run('randomx-arm64-allocator', ['patch', '-p1', '-F', '0', '-i', str(allocator_patch)],
                    cwd=source / 'external/randomx')
                tester.require(tester.sha(allocator) == 'd5abf99da75d0cbaa68d9503d3568079cc1707bc40ede9a949cd2e49dadbd02a',
                    'ARM64 allocator adaptation output differs')
                receipt['patches'].append({'file': str(allocator.relative_to(source)),
                    'before_sha256': '07588f5d3e01d1ad9ad375b05a232f5c43c9f6a3c264c2960e7306cdbf73c80f',
                    'after_sha256': tester.sha(allocator), 'patch_sha256': tester.sha(allocator_patch),
                    'reference': 'https://learn.microsoft.com/en-us/cpp/c-runtime-library/reference/aligned-malloc',
                    'scope': 'Windows ARM64 platform allocation only: matching UCRT _aligned_malloc/_aligned_free; POSIX branch, intrinsics, source/version pins and crypto/consensus unchanged.'})
                assembly = source / 'external/randomx/src/jit_compiler_a64_static.S'
                assembly_patch = Path(__file__).with_name('patches') / 'randomx-aaafe713-windows-arm64-hidden.patch'
                tester.require(args.target == 'windows-aarch64' and
                    PIN['upstream']['submodules']['external/randomx'] == 'aaafe71322df6602c21a5c72937ac284724ae561' and
                    tester.sha(assembly) == 'f31e68e4325bb5be41eaeaf63975bf760ff158be80f0ce800e43497e9d9f693f' and
                    tester.sha(assembly_patch) == '742daffebed9f21f73ced606accecf4bd44d08d2ce25699d45a9c7e2ed349f72',
                    'unverified ARM64 assembler adaptation source')
                run('randomx-arm64-hidden', ['patch', '-p1', '-F', '0', '-i', str(assembly_patch)],
                    cwd=source / 'external/randomx')
                tester.require(tester.sha(assembly) == '158033e0e3c552b201581ea1c427c4989abc65a462b05b5c72d9faf34c9438a1',
                    'ARM64 assembler adaptation output differs')
                receipt['patches'].append({'file': str(assembly.relative_to(source)),
                    'before_sha256': 'f31e68e4325bb5be41eaeaf63975bf760ff158be80f0ce800e43497e9d9f693f',
                    'after_sha256': tester.sha(assembly), 'patch_sha256': tester.sha(assembly_patch),
                    'scope': 'Windows ARM64 COFF assembler compatibility: exclude ELF .hidden only; instruction bytes and other platform preprocessing unchanged.'})
                save()
                random_source = source / 'src/crypto/random.c'
                tester.require(args.target == 'windows-aarch64' and
                    PIN['upstream']['commit'] == 'e151643c5269c83bf24a83b2548e2493876026b2' and
                    tester.sha(random_source) == 'a600a0a54df08eff9be89335daea5299d961fa43dc024c488eceb5a610ec93c6',
                    'unverified Windows ARM64 random source declaration adaptation')
                adapt('src/crypto/random.c', '#include <stdio.h>\n',
                      '#include <stdio.h>\n#include <process.h>\n')
                tester.require(tester.sha(random_source) == '9574e279b64cc3566c02b6dea77570319482c3056e19c49810442dffdb4ab213',
                    'Windows ARM64 random source declaration output differs')
                receipt['patches'][-1].update({
                    'reference': 'https://learn.microsoft.com/en-us/cpp/c-runtime-library/reference/exit-exit-exit',
                    'scope': 'Windows ARM64 declaration include only: process.h declares existing _exit; random generation, failure path, source pin and other targets unchanged.'})
                save()
                slow_hash = source / 'src/crypto/slow-hash.c'
                slow_hash_patch = Path(__file__).with_name('patches') / 'monero-e151643c-windows-arm64-slow-hash-platform.patch'
                tester.require(args.target == 'windows-aarch64' and
                    PIN['upstream']['commit'] == 'e151643c5269c83bf24a83b2548e2493876026b2' and
                    tester.sha(slow_hash) == '886ae10164b0593e35df7419cd5834ce66a6db5a5f54a623a5364804f868fd83' and
                    tester.sha(slow_hash_patch) == '38a310034b4ed0ee490aa2430d53f80866af83a8a769516b87720d8faa06cf80',
                    'unverified Windows ARM64 slow-hash platform adaptation')
                run('slow-hash-arm64-platform', ['patch', '-p1', '-F', '0', '-i', str(slow_hash_patch)], cwd=source)
                tester.require(tester.sha(slow_hash) == 'dae4f22d4034adc4d926f02f11b3cc6ab66b191384e31fd8b8e15656147221de',
                    'Windows ARM64 slow-hash platform adaptation output differs')
                receipt['patches'].append({'file': str(slow_hash.relative_to(source)),
                    'before_sha256': '886ae10164b0593e35df7419cd5834ce66a6db5a5f54a623a5364804f868fd83',
                    'after_sha256': tester.sha(slow_hash), 'patch_sha256': tester.sha(slow_hash_patch),
                    'references': [
                        'https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-virtualalloc',
                        'https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-virtualfree',
                        'https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-isprocessorfeaturepresent'],
                    'scope': 'Windows ARM64 allocation/release and OS CPU feature query only; malloc fallback, hash arithmetic, AES loops, source/dependency pins and non-Windows branches unchanged. Cross compilation is not native execution.'})
                save()
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
            cleanup_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT})
            cleanup_handlers = {s: signal.getsignal(s) for s in (signal.SIGTERM, signal.SIGINT)}
            try:
                save()
            finally:
                try:
                    for number, handler in cleanup_handlers.items():
                        signal.signal(number, handler)
                finally:
                    signal.pthread_sigmask(signal.SIG_SETMASK, cleanup_mask)


if __name__ == '__main__':
    def cancelled(signum, frame):
        raise RuntimeError('cross build cancelled; clean exact owned container')
    signal.signal(signal.SIGTERM, cancelled)
    main()
