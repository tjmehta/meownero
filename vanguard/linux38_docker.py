"""Linux38 native x64 host and pinned Ubuntu22 userland admission.

Used only by the separately staged Docker successor. No hosted identity, VM,
idle-daemon or container-marker assumption is made. Qualification probes and
workers use the existing local daemon; no daemon settings are changed.
"""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import subprocess
import sys
import uuid

BASE = 'ubuntu@sha256:08ea48a03a3e78ebc7cd526e6a275053223aadd88bfc09cc49b06d5281525fde'
SCOPE = 'NATIVE_X64_UBUNTU22_DOCKER_USERLAND'
GIB = 1024**3
LOCK = Path('/tmp/meownero-swarm-20260912-heavy.lock')
_binding = None


def sha(path):
    assert path.is_file() and not path.is_symlink() and path.stat().st_nlink == 1
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def query(*args):
    return subprocess.check_output(['docker', *args], text=True, timeout=30).strip()


def admit(path, digest, target):
    global _binding
    assert target == 'linux-x86_64', 'Linux38 x64 only'
    assert digest and re.fullmatch('[0-9a-f]{64}', digest) and sha(path) == digest, 'provenance checksum mismatch'
    value = json.loads(path.read_text())
    assert set(value) == {'schema', 'issue', 'target', 'machine_id_sha256', 'boot_id_sha256',
                          'kernel', 'docker_id', 'docker_name', 'docker_root', 'docker_version',
                          'qualification_evidence_sha256'}
    assert value['schema'] == 'meownero-linux38-native-docker/1' and value['issue'] == 'TJS-1882'
    assert value['target'] == target
    for key in ('machine_id_sha256', 'boot_id_sha256', 'qualification_evidence_sha256'):
        assert isinstance(value[key], str) and re.fullmatch('[0-9a-f]{64}', value[key])
    assert not any(k.startswith(('GITHUB_', 'RUNNER_')) for k in os.environ), 'hosted identity forbidden'
    assert not any(os.environ.get(k) for k in ('DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH')), 'Docker overrides forbidden'
    assert platform.system() == 'Linux' and platform.machine() == 'x86_64' and sys.version_info >= (3, 13)
    release = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
    assert release['ID'].strip('"') == 'ubuntu' and release['VERSION_ID'].strip('"') == '24.04', 'Ubuntu24 controller required'
    assert subprocess.check_output(['getconf', 'GNU_LIBC_VERSION'], text=True, timeout=10).strip() == 'glibc 2.39'
    assert sha(Path('/etc/machine-id')) == value['machine_id_sha256'], 'controller machine changed'
    assert sha(Path('/proc/sys/kernel/random/boot_id')) == value['boot_id_sha256'], 'boot changed; requalify'
    assert platform.release() == value['kernel'], 'kernel changed; requalify'
    context = json.loads(query('context', 'inspect'))
    assert len(context) == 1 and context[0]['Name'] == 'default'
    assert context[0]['Endpoints']['docker']['Host'] == 'unix:///var/run/docker.sock'
    assert stat.S_ISSOCK(Path('/var/run/docker.sock').stat().st_mode)
    info = json.loads(query('info', '--format', '{{json .}}'))
    for actual, bound in [('ID', 'docker_id'), ('Name', 'docker_name'), ('DockerRootDir', 'docker_root'),
                          ('ServerVersion', 'docker_version'), ('KernelVersion', 'kernel')]:
        assert isinstance(value[bound], str) and value[bound] and info[actual] == value[bound], 'daemon binding changed'
    assert info['Architecture'] == 'x86_64' and info['OSType'] == 'linux' and info['CgroupVersion'] == '2'
    assert all(info.get(k) is True for k in ('MemoryLimit', 'SwapLimit', 'PidsLimit', 'CpuCfsQuota')), 'daemon lacks resource controls'
    assert value['docker_root'] == '/var/lib/docker' and Path(value['docker_root']).is_dir()
    _binding = (path.absolute(), digest, value)
    return {'execution_provider': SCOPE, 'provenance_sha256': digest,
            'qualification_evidence_sha256': value['qualification_evidence_sha256'],
            'machine_id_sha256': value['machine_id_sha256'], 'boot_id_sha256': value['boot_id_sha256'],
            'docker_id_sha256': hashlib.sha256(value['docker_id'].encode()).hexdigest(),
            'host_kernel': value['kernel'], 'controller_os': 'Ubuntu24.04', 'controller_glibc': '2.39',
            'worker_userland': 'Ubuntu22.04', 'worker_glibc': '2.35', 'physical_host_architecture': 'x86_64'}


@contextmanager
def shared_lock():
    # Never create, replace or unlink the canonical inode.
    assert LOCK.is_file() and not LOCK.is_symlink() and LOCK.stat().st_nlink == 1
    with LOCK.open('rb') as stream:
        before = os.fstat(stream.fileno())
        assert before.st_uid == os.getuid()
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield before.st_ino
        finally:
            assert LOCK.stat().st_ino == before.st_ino and not LOCK.is_symlink(), 'shared lock identity changed'
            fcntl.flock(stream, fcntl.LOCK_UN)


def unrelated():
    return set(query('ps', '-aq', '--no-trunc').splitlines())


def preserved(ids):
    assert ids <= unrelated(), 'pre-existing container disappeared; stop and inspect external changes'


def cleanup_owned(name, image, invocation):
    """Recover a container accepted before its CLI wrote the CID file."""
    sys.path.insert(0, str(Path(__file__).with_name('docker')))
    from docker_support import cleanup_named
    result = cleanup_named(name, image, invocation)
    assert result['removed'], 'owned named-container cleanup unresolved'
    return result


def check_witness(lines, value, digest):
    assert len(lines) == 11, 'invalid capacity witness'
    arch, kernel, boot, binding, distro, libc, mem, output, daemon, limits, cpu = lines
    assert arch == 'x86_64' and kernel == value['kernel']
    assert hashlib.sha256((boot + '\n').encode()).hexdigest() == value['boot_id_sha256'], 'daemon uses another kernel boot'
    assert binding.split()[0] == digest, 'daemon bind source differs from controller'
    assert distro == '22.04' and libc == 'glibc 2.35', 'pinned Ubuntu22 userland required'
    assert limits == '67108864 0 16' and cpu == '100000 100000', 'actual cgroup limits differ'
    free = [int(mem) * 1024, *[int(a) * int(b) for a, b in (output.split(), daemon.split())]]
    assert free[0] >= 6 * GIB, 'host available memory below six GiB'
    assert min(free[1:]) >= 10 * GIB, 'output/daemon disk reserve below ten GiB'
    return dict(zip(('available_memory_bytes', 'free_disk_bytes', 'docker_free_disk_bytes'), free))


def resources(parent, reserve=10, minimum_available=6 * GIB):
    """Fresh daemon-side topology, mounts, headroom and actual cgroup witness."""
    assert _binding is not None, 'Docker provenance admission required'
    path, digest, value = _binding
    admit(path, digest, 'linux-x86_64')
    assert minimum_available == 6 * GIB and reserve == 10, 'resource policy reduction forbidden'
    parent = parent.absolute()
    assert parent.is_dir() and not any(p.is_symlink() for p in (parent, *parent.parents))
    assert not any(c in str(parent) + str(path) for c in (',', '\n', ':'))
    assert shutil.disk_usage(parent).free >= 10 * GIB
    # Reuse the existing exact-name recovery/ownership helper. A lost create
    # response must still discover and remove only this invocation's container.
    sys.path.insert(0, str(Path(__file__).with_name('docker')))
    from docker_support import cleanup_named, cleanup_signals, proof
    image = json.loads(query('image', 'inspect', BASE))[0]
    assert image['Os'] == 'linux' and image['Architecture'] == 'amd64'
    invocation = uuid.uuid4().hex
    name = 'tjs1882-' + invocation + '-linux38-admission'
    baseline = unrelated()
    script = '''set -e
uname -m
uname -r
cat /proc/sys/kernel/random/boot_id
sha256sum /binding
. /etc/os-release; echo "$VERSION_ID"
getconf GNU_LIBC_VERSION
awk '/^MemAvailable:/ {print $2}' /proc/meminfo
stat -f -c '%a %S' /output
stat -f -c '%a %S' /capacity
echo "$(cat /sys/fs/cgroup/memory.max) $(cat /sys/fs/cgroup/memory.swap.max) $(cat /sys/fs/cgroup/pids.max)"
cat /sys/fs/cgroup/cpu.max
'''
    cleanup = None
    receipt = {'schema': 'meownero-linux38-docker-admission/1', 'result': 'FAIL',
               'image': image['Id'], 'invocation': invocation, 'name': name,
               'provenance_sha256': digest}
    try:
        cid = query('create', '--name', name, '--label', 'meownero.invocation=' + invocation,
                    '--pull=never', '--network=none', '--read-only', '--cpus=1', '--memory=64m',
                    '--memory-swap=64m', '--pids-limit=16', '--cap-drop=ALL',
                    '--security-opt=no-new-privileges', '--ulimit', 'core=0',
                    '--mount', 'type=bind,src=' + str(path) + ',dst=/binding,readonly',
                    '--mount', 'type=bind,src=' + str(parent) + ',dst=/output,readonly',
                    '--mount', 'type=bind,src=/var/lib/docker,dst=/capacity,readonly',
                    image['Id'], 'sh', '-ec', script)
        proof(cid, 'meownero.invocation', invocation, name=name, image=image['Id'])
        receipt['cid'] = cid
        result = check_witness(query('start', '-a', cid).splitlines(), value, digest)
        receipt.update(result='PASS', resources=result)
    finally:
        with cleanup_signals():
            try:
                cleanup = cleanup_named(name, image['Id'], invocation)
                receipt['cleanup'] = cleanup
                assert cleanup['removed'], 'qualification cleanup unresolved'
                preserved(baseline)
                receipt['unrelated_containers_preserved'] = True
            except BaseException:
                receipt['result'] = 'FAIL'
                raise
            finally:
                (parent / ('linux38-admission-' + invocation + '.json')).write_text(json.dumps(receipt, indent=2) + '\n')
    result.update(cgroup_enforcement='PASS_64M_ZERO_SWAP_ONE_CPU_16_PIDS',
                  probe_image=image['Id'], owned_probe_removed=cleanup['removed'],
                  unrelated_container_count=len(baseline))
    return result


def compile_resources(target, preparation, parent):
    assert target == 'linux-x86_64' and preparation['target'] == target
    assert preparation['distribution'] == 'Ubuntu 22.04' and preparation['base_manifest'] == BASE
    assert preparation['compiler_execution_substrate'] == 'NATIVE' and preparation['cleanup']['removed']
    observed = resources(parent)
    return {'scope': SCOPE, 'container_memory_bytes': 4 * GIB,
            'container_memory_swap_bytes': 4 * GIB, 'host_minimum_available_bytes': 6 * GIB,
            'measured_available_bytes': observed['available_memory_bytes']}
