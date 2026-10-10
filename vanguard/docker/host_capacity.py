"""Prove local daemon topology and measure its host before heavy work."""
import hashlib
import json
import os
from pathlib import Path
import stat

from docker_support import cleanup_named, cleanup_signals, proof, query, save

GIB = 1024**3


def local_endpoint():
    context = os.environ.get('DOCKER_CONTEXT')
    if context:
        endpoint = json.loads(query('context', 'inspect', context))[0]['Endpoints']['docker']['Host']
    elif os.environ.get('DOCKER_HOST'):
        endpoint = os.environ['DOCKER_HOST']
    else:
        endpoint = json.loads(query('context', 'inspect', query('context', 'show')))[0]['Endpoints']['docker']['Host']
    assert endpoint.startswith('unix:///'), 'requires a local Unix Docker endpoint'
    socket = Path(endpoint.removeprefix('unix://'))
    assert stat.S_ISSOCK(socket.stat().st_mode), 'Docker endpoint is not a local socket'
    return hashlib.sha256(endpoint.encode()).hexdigest()


def check_witness(values, client_boot_id):
    assert len(values) == 5 and values[0] == 'x86_64'
    assert values[1] == client_boot_id, 'Docker VM/remote kernel differs from Linux client'
    memory = int(values[2]) * 1024
    disk = int(values[3]) * int(values[4])
    assert memory >= 5 * GIB, 'requires five GiB available Docker-host memory'
    assert disk >= 10 * GIB, 'requires ten GiB on Docker data filesystem'
    return {'host_available_bytes': memory, 'docker_data_free_bytes': disk,
            'same_kernel_boot_id_sha256': hashlib.sha256(client_boot_id.encode()).hexdigest()}


def admit(base, invocation, out, receipt, phase):
    endpoint = local_endpoint()
    info = json.loads(query('info', '--format', '{{json .}}'))
    assert info['Architecture'] == 'x86_64' and info['OSType'] == 'linux' and info['CgroupVersion'] == '2'
    docker_root = info['DockerRootDir']
    assert Path(docker_root).is_absolute() and ',' not in docker_root
    image = json.loads(query('image', 'inspect', base))[0]
    assert image['Architecture'] == 'amd64' and image['Os'] == 'linux'
    image_id = image['Id']
    name = 'meownero-tjs1882-capacity-' + invocation + '-' + phase
    row = {'phase': phase, 'result': 'INCOMPLETE', 'endpoint_sha256': endpoint,
           'image': image_id, 'cleanup': {'removed': False}}
    receipt.setdefault('host_capacity', []).append(row)
    save(out / 'build.json', receipt)
    script = "uname -m; cat /proc/sys/kernel/random/boot_id; awk '/^MemAvailable:/ {print $2}' /proc/meminfo; stat -f -c '%a %S' /capacity"
    try:
        cid = query('create', '--name', name, '--label', 'meownero.invocation=' + invocation,
                    '--pull=never', '--network=none', '--read-only', '--cpus=1', '--memory=64m', '--memory-swap=64m',
                    '--pids-limit=16', '--cap-drop=ALL', '--security-opt=no-new-privileges',
                    '--mount', 'type=bind,src=' + docker_root + ',dst=/capacity,readonly',
                    image_id, 'sh', '-ec', script)
        proof(cid, 'meownero.invocation', invocation, name=name, image=image_id)
        values = query('start', '-a', cid).split()
        row.update(check_witness(values, Path('/proc/sys/kernel/random/boot_id').read_text().strip()), result='READY')
    except BaseException as error:
        row.update(result='REFUSED_OR_FAILED', failure_type=type(error).__name__)
        raise
    finally:
        with cleanup_signals():
            try:
                row['cleanup'] = cleanup_named(name, image_id, invocation)
                if not row['cleanup']['removed']:
                    row['result'] = 'UNRESOLVED_CAPACITY_CLEANUP'
            finally:
                save(out / 'build.json', receipt)
    assert row['cleanup']['removed'], 'capacity probe cleanup unresolved'
