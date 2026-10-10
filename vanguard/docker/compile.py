"""Compile all three programs offline, then enforce existing package closure."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

BUILD = Path('/build')
SOURCE = BUILD / 'monero-fcmp'


def run(argv, cwd=SOURCE, timeout=3500):
    subprocess.run(argv, cwd=cwd, check=True, timeout=timeout)


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    inputs = json.loads((BUILD / 'inputs.json').read_text())
    pin = json.loads(Path('/recipe/vanguard/source-lock.json').read_text())
    assert os.uname().machine == 'x86_64'
    assert Path('/sys/fs/cgroup/memory.max').read_text().strip() == str(3 * 1024**3)
    assert Path('/sys/fs/cgroup/memory.swap.max').read_text().strip() == '0'
    assert Path('/sys/fs/cgroup/pids.max').read_text().strip() == '256'
    assert set(p.name for p in Path('/sys/class/net').iterdir()) == {'lo'}
    os.environ.update(PATH='/build/rust/bin:' + os.environ['PATH'], CARGO_HOME='/build/cargo-home',
                      CARGO_NET_OFFLINE='true', CARGO_BUILD_JOBS='1')
    depends = SOURCE / 'contrib/depends'
    host = 'x86_64-unknown-linux-gnu'
    run(['make', '-j2', 'HOST=' + host, 'NO_WALLET=1', 'NO_READLINE=1', 'linux_CC=gcc',
         'linux_CXX=g++', 'linux_AR=ar', 'linux_RANLIB=ranlib', 'linux_NM=nm', 'linux_STRIP=strip'], depends)
    toolchain = depends / host / 'share/toolchain.cmake'
    text = toolchain.read_text()
    assert text.count('SET(STATIC ON)') == 1
    toolchain.write_text(text.replace('SET(STATIC ON)', 'SET(STATIC OFF)'))
    binary_build = SOURCE / 'build/vanguard'
    run(['cmake', '-S', str(SOURCE), '-B', str(binary_build), '-DCMAKE_TOOLCHAIN_FILE=' + str(toolchain),
         '-DOPENSSL_USE_STATIC_LIBS=ON', '-DOPENSSL_CRYPTO_LIBRARY=' + str(depends / host / 'lib/libcrypto.a'),
         '-DOPENSSL_SSL_LIBRARY=' + str(depends / host / 'lib/libssl.a'), '-Dsodium_USE_STATIC_LIBS=ON',
         '-DCMAKE_BUILD_TYPE=Release', '-DARCH=default', '-DBUILD_TESTS=OFF', '-DUSE_DEVICE_TREZOR=OFF',
         '-DBUILD_GUI_DEPS=OFF', '-DMANUAL_SUBMODULES=ON', '-DSTATIC=OFF', '-DUSE_READLINE=OFF'])
    run(['make', '-j1', 'daemon', 'simplewallet', 'wallet_rpc_server'], binary_build)
    libraries = BUILD / 'runtime-libs'
    libraries.mkdir()
    binaries = {}
    for name in ('monerod', 'monero-wallet-cli', 'monero-wallet-rpc'):
        binary = binary_build / 'bin' / name
        run([str(binary), '--version'], timeout=20)
        binaries[name] = {'sha256': sha(binary), 'bytes': binary.stat().st_size}
        linked = subprocess.check_output(['ldd', str(binary)], text=True)
        assert 'not found' not in linked
        for path in re.findall(r'=> (/\S+)', linked):
            library = Path(path)
            if library.name.startswith(('libc.so.', 'libm.so.', 'libdl.so.', 'libpthread.so.', 'librt.so.')):
                continue
            target = libraries / library.name
            if target.exists():
                assert sha(target) == sha(library)
            else:
                shutil.copyfile(library, target)
    notices = BUILD / 'licenses'
    notices.mkdir()
    for path in Path('/usr/share/doc').glob('*/copyright'):
        shutil.copyfile(path, notices / ('COPYRIGHT-' + path.parent.name))
    for path in Path('/usr/share/common-licenses').iterdir():
        if path.is_file():
            shutil.copyfile(path, notices / ('COPYING-common-' + path.name))
    inventory = subprocess.check_output(['dpkg-query', '-W', '-f=${binary:Package}=${Version}\n'], text=True)
    (BUILD / 'dependencies.txt').write_text(inventory)
    receipt = {'schema': 'meownero-docker-source-build/1', 'source_lock': pin, 'target': 'linux-x86_64',
               'compiler_execution_substrate': 'NATIVE', 'offline_compile': True,
               'result': 'BUILT_VERSION_EXECUTED_JOURNEY_UNTESTED', 'binaries': binaries, 'patches': [],
               'depends_static_dependencies': True, 'builder_image': inputs['base'],
               'apt_snapshot': inputs['apt_snapshot'], 'generated_toolchain_sha256': sha(toolchain)}
    (BUILD / 'build-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    Path('/package').mkdir()
    run([sys.executable, '-B', '/recipe/vanguard/package-portable.py', '--build', '/build', '--out', '/package/export'])
    shutil.move('/package/export/meownero-vanguard-x86_64', '/package/meownero-vanguard-x86_64')
    (BUILD / 'docker-build.json').write_text(json.dumps({'inputs': inputs, 'build': receipt,
        'packages': inventory.splitlines(), 'status': 'BUILT_RUNTIME_UNTESTED'}, indent=2) + '\n')


if __name__ == '__main__':
    main()
