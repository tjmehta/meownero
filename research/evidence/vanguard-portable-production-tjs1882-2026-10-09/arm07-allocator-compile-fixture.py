"""Owned offline old/new ARM64-UCRT compilation; never native Windows proof."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import time
import uuid

root = Path('~/Developer/tjs1882-3175')
prior = root / 'windows-arm-attempt06'
out = root / 'randomx-arm07-allocator-fixture01'
patch = root / 'randomx-arm07-aligned-allocator.patch'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert platform.system() == 'Darwin' and platform.machine() == 'arm64'
assert not out.exists() and sha(patch) == '175fc5e0344b3e8e1932eebbf39a3c23314c401ad9bc20a588cd8fe6e5052b82'
header = prior / 'monero-fcmp/external/randomx/src/intrin_portable.h'
assert sha(header) == '07588f5d3e01d1ad9ad375b05a232f5c43c9f6a3c264c2960e7306cdbf73c80f'
spec = importlib.util.spec_from_file_location('tester', root / 'kit13/vanguard/tester.py')
tester = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tester)
docker = ['docker', '--context', 'colima']
lock_inode = tester.LOCK.stat().st_ino
original_handlers = {number: signal.getsignal(number) for number in (signal.SIGTERM, signal.SIGINT)}

def cancelled(number, frame):
    raise RuntimeError('owned allocator fixture cancelled')

for number in original_handlers:
    signal.signal(number, cancelled)
proof = {'schema': 'meownero-arm07-allocator-compile-fixture/1', 'result': 'FAIL',
         'source_commit': 'aaafe71322df6602c21a5c72937ac284724ae561',
         'old_header_sha256': sha(header), 'patch_sha256': sha(patch),
         'native_Windows_ARM_execution': 'UNTESTED', 'owned_container_removed': False}
try:
    with tester.heavy_lock():
        assert shutil.disk_usage(root).free >= 10 * 1024**3
        memory = subprocess.check_output(['colima', 'ssh', '--', 'cat', '/proc/meminfo'], text=True, timeout=15)
        assert int(next(line.split()[1] for line in memory.splitlines() if line.startswith('MemAvailable:'))) * 1024 >= 5 * 1024**3
        disk = subprocess.check_output(['colima', 'ssh', '--', 'df', '-B1', '/var/lib/docker'], text=True, timeout=15)
        assert int(disk.splitlines()[-1].split()[3]) >= 10 * 1024**3
        assert not subprocess.check_output(docker + ['ps', '-q'], text=True, timeout=10).strip()
        image = 'sha256:d0d9ff472379e2cc7a1f9b046fc6bc031ef98c36dcf08614b307d59323b6cb4c'
        receipt = json.loads((prior / 'build-receipt.json').read_text())
        assert receipt['builder_image'] == image and receipt['result'] == 'FAILED_ATTEMPT'
        assert all(row['removed'] for row in receipt['containers'])
        observed = json.loads(subprocess.check_output(docker + ['image', 'inspect', image], text=True, timeout=10))[0]
        assert observed['Id'] == image and observed['RootFS']['Layers'] == receipt['builder_transfer']['identical_rootfs_diff_ids']
        assert observed['Architecture'] == 'amd64' and observed['Os'] == 'linux'
        out.mkdir(mode=0o700)
        for version in ('old', 'new'):
            dest = out / version / 'src'
            dest.mkdir(parents=True, mode=0o700)
            shutil.copyfile(header, dest / 'intrin_portable.h')
        subprocess.run(['patch', '-p1', '-F', '0', '-i', str(patch)], cwd=out / 'new', check=True, timeout=10)
        assert sha(out / 'new/src/intrin_portable.h') == 'd5abf99da75d0cbaa68d9503d3568079cc1707bc40ede9a949cd2e49dadbd02a'
        subprocess.run(['patch', '-R', '-p1', '-F', '0', '--dry-run', '-i', str(patch)], cwd=out / 'new', check=True, timeout=10)
        probe = out / 'probe.cpp'
        probe.write_text('#include "intrin_portable.h"\nextern "C" void* probe_allocate(){return rx_aligned_alloc(128,64);}\nextern "C" void probe_free(void* p){rx_aligned_free(p);}\n')
        compiler = '/llvm/bin/aarch64-w64-mingw32-clang++'
        common = compiler + ' -std=c++11 -march=armv8-a+crypto -DWINVER=0x0A00 -D_WIN32_WINNT=0x0A00 -DBOOST_USE_WINAPI_VERSION=0x0A00 -I/randomx'
        script = 'set -eu\n' + common + ' --version > /fixture/compiler.txt\n' + common + ' -I/fixture/old/src -c /fixture/probe.cpp -o /fixture/old.obj > /fixture/old.log 2>&1 && exit 51\ngrep -q posix_memalign /fixture/old.log\n' + common + ' -I/fixture/new/src -c /fixture/probe.cpp -o /fixture/new.obj > /fixture/new.log 2>&1\n/llvm/bin/llvm-nm --undefined-only /fixture/new.obj > /fixture/undefined.txt\n/llvm/bin/llvm-objdump -f /fixture/new.obj > /fixture/object.txt\n'
        name = 'tjs1882-3175-arm07-allocator-' + uuid.uuid4().hex[:10]
        cidfile = out / 'cid'
        label = 'meownero.tjs1882.fixture=arm07-allocator'
        argv = docker + ['run', '--name', name, '--label', label, '--cidfile', str(cidfile),
            '--network', 'none', '--cpus', '2', '--memory', '256m', '--memory-swap', '256m', '--pids-limit', '64',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
            '-v', str(prior / 'llvm') + ':/llvm:ro', '-v', str(header.parent) + ':/randomx:ro',
            '-v', str(out) + ':/fixture', image, 'bash', '-c', script]
        try:
            began = time.monotonic()
            run = subprocess.run(argv, capture_output=True, timeout=40)
            proof['compile_exit'] = run.returncode
            proof['wall_seconds'] = round(time.monotonic() - began, 3)
            assert run.returncode == 0
            undefined = (out / 'undefined.txt').read_text()
            assert '_aligned_malloc' in undefined and '_aligned_free' in undefined and 'posix_memalign' not in undefined
            assert 'coff-arm64' in (out / 'object.txt').read_text()
            proof.update(result='PASS_OLD_POSIX_REFUSAL_NEW_MATCHED_UCRT_ALLOCATOR_ARM64_OBJECT',
                patched_header_sha256=sha(out / 'new/src/intrin_portable.h'),
                compiled_object_sha256=sha(out / 'new.obj'), compiler_description_sha256=sha(out / 'compiler.txt'),
                original_posix_memalign_failure_reproduced=True, matching_UCRT_allocator_and_free=True,
                object_machine='COFF_ARM64', offline=True, memory_limit_bytes=256 * 1024**2, cpu_limit=2)
        finally:
            blocked = signal.pthread_sigmask(signal.SIG_BLOCK, set(original_handlers))
            try:
                if cidfile.exists():
                    cid = cidfile.read_text().strip()
                    info = json.loads(subprocess.check_output(docker + ['inspect', cid], text=True, timeout=10))[0]
                    assert info['Id'] == cid and info['Name'] == '/' + name
                    assert info['Config']['Labels'].get('meownero.tjs1882.fixture') == 'arm07-allocator'
                    subprocess.run(docker + ['rm', '-f', cid], check=True, capture_output=True, timeout=15)
                    absent = subprocess.run(docker + ['inspect', cid], capture_output=True, timeout=10)
                    assert absent.returncode != 0
                    proof['owned_container_removed'] = True
                assert tester.LOCK.stat().st_ino == lock_inode
                proof['existing_lock_inode_preserved'] = True
            except BaseException as error:
                proof['result'] = 'FAIL'
                proof['cleanup_failure_type'] = type(error).__name__
                raise
            finally:
                try:
                    (out / 'fixture-receipt.json').write_text(json.dumps(proof, indent=2) + '\n')
                    for path in out.rglob('*'):
                        if path.is_file():
                            path.chmod(0o600)
                finally:
                    try:
                        for number, handler in original_handlers.items():
                            signal.signal(number, handler)
                    finally:
                        signal.pthread_sigmask(signal.SIG_SETMASK, blocked)
finally:
    for number, handler in original_handlers.items():
        signal.signal(number, handler)
print(proof['result'])
