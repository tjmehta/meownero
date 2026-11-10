#!/usr/bin/env python3
"""TJS-4177 exposure-candidate manager. Needs a fresh exact Platform grant.

Reuses the accepted topology manager's keeper (the original heavy lock for the
whole wall), measured host-overhead allowance, admissions, retained build
verification and closed public-row reader. It creates one owned Docker
`--internal` bridge network with a fixed /29 and three containers on it, one
per network namespace (seed, client, foreign peer), with no published host
port. After all containers exit it collects the closed rows, removes the
containers and the network and releases the keeper. It never activates anything public.

Exit codes: 0 PASS (or rehearsal pass), 1 FAIL, 3 refused before attempt.
"""
import argparse
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import network as n
import profile_contract as c
from integration import exposure_contract as x

spec = importlib.util.spec_from_file_location('topology_manager', c.HERE/'run-topology.py')
rt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rt)
r, g = rt.r, rt.g

STATE = 'exposure-state.json'
DRIVER = 'integration/exposure_driver.py'
LABEL = 'meownero.exposure.attempt'
# The accepted container limits, with only the network mode replaced by the owned bridge.
FLAGS = [f for f in r.CONTAINER_FLAGS if f != '--network=none']
NETWORK = dict(driver='bridge', internal=True, subnet=x.SUBNET, gateway=x.GATEWAY, seed_ip=x.SEED_IP,
               client_ip=x.CLIENT_IP, foreign_ip=x.FOREIGN_IP, published_ports=0)
PHASES = ('new', 'rows', 'probed', 'exposed', 'foreign-start', 'foreign-armed', 'foreign-done', 'foreign-checked',
          'bootstrapped', 'restart-seed', 'restarted', 'caught-up', 'steady', 'done', 'complete', 'failed')


def grant_payload(comment, *, commit, inputs_hash, artifact_hash, runner_hash, driver_hash, output, now, reuse):
    c.require(comment['issueId'] == x.ISSUE and comment.get('authorAgentId') == c.PLATFORM and
              comment.get('authorUserId') is None, 'Platform-authored TJS-4177 grant required')
    blocks = re.findall(r'```meownero-exposure-grant\s*\n(.*?)\n```', comment['body'], re.S)
    c.require(len(blocks) == 1, 'one exposure grant block required')
    value = json.loads(blocks[0])
    expected = dict(schema='meownero-exposure-grant/1', authorized=True, workload=x.WORKLOAD,
        candidate_commit=commit, inputs_sha256=inputs_hash, artifact_sha256=artifact_hash,
        runner_sha256=runner_hash, driver_sha256=driver_hash, output_root=str(output), attempts=1,
        retry=False, container_flags=FLAGS, network=NETWORK, mode='runtime-only',
        reuse_build_root=str(reuse['root']), retained_build_sha256=reuse['manifest_sha256'],
        retained_build_authority_comment=r.funded.AUTHORITY_COMMENT, main_chain_count_max=x.MAX_COUNT,
        mining_threads=1, transactions=0, heavy_lock='keeper-held-for-wall', detached_session=True,
        no_other_heavy_lock_workload_scheduled=True, host_overhead_allowance=rt.OVERHEAD,
        listeners='internal-bridge-no-published-port', public_launch=False, launch_ready=False)
    c.require(all(type(value.get(k)) is type(v) and value[k] == v for k, v in expected.items()),
              'exposure grant binding mismatch')
    c.require(type(value.get('uptime_seconds')) is int and value['uptime_seconds'] in x.MODES and
              value.get('wall_seconds') == x.MODES[value['uptime_seconds']] and
              value.get('verdict_label') == ('full' if value['uptime_seconds'] == x.UPTIME_SECONDS else 'rehearsal'),
              'grant uptime mode/wall/label')
    c.require(str(reuse['root']) == r.funded.RETAINED_ROOT and reuse['manifest_sha256'] == r.funded.RETAINED_SHA256,
              'published retained build authority required')
    rule = value['load_rule']
    c.require(rule['metric'] == 'host-load-1-5-15' and len(rule['maximum']) == 3 and
              all(type(v) in (int, float) and 0 < v < 1000 for v in rule['maximum']), 'explicit load rule')
    c.require(value['valid_until_unix']-value['valid_from_unix'] >= 48*3600 and
              value['valid_from_unix'] <= now and now+value['wall_seconds'] <= value['valid_until_unix'],
              'grant validity window')
    c.require(re.fullmatch(r'[0-9a-f-]{36}', value['artifact_attachment_id']) is not None, 'artifact attachment ID')
    return value


def keeper_alive(owned):
    """rt.alive, after reaping: this manager spawns the keeper, so an exited keeper stays a zombie
    (same /proc start time) until waited for (native rehearsal 1c226b32 lock_released)."""
    try:
        os.waitpid(owned[0], os.WNOHANG)
    except ChildProcessError:
        pass  # Not this process's child: nothing to reap.
    return rt.alive(owned)


def names(grant):
    return dict(network='meownero-exposure-'+grant, **{role: f'meownero-exposure-{role}-{grant}' for role in x.ROLES})


def subnet_free(control, deadline):
    """Refuse when any existing Docker network or host route overlaps the owned /29."""
    owned = ipaddress.ip_network(x.SUBNET)
    listing = control.run(g.DOCKER+['network', 'ls', '-q'], deadline, monitor=False)
    ids = listing.stdout.split()
    if ids:
        value = json.loads(control.run(g.DOCKER+['network', 'inspect', *ids], deadline, monitor=False).stdout)
        for item in value:
            for config in (item.get('IPAM') or {}).get('Config') or []:
                if config.get('Subnet') and ipaddress.ip_network(config['Subnet'], strict=False).overlaps(owned):
                    raise ValueError('owned exposure subnet already in use')
    for line in Path('/proc/net/route').read_text().splitlines()[1:]:
        parts = line.split()
        destination = ipaddress.ip_address(bytes.fromhex(parts[1])[::-1])
        mask = ipaddress.ip_address(bytes.fromhex(parts[7])[::-1])
        if parts[1] != '00000000' and ipaddress.ip_network(f'{destination}/{mask}', strict=False).overlaps(owned):
            raise ValueError('owned exposure subnet overlaps a host route')
    return True


def network_command(name):
    return g.DOCKER+['network', 'create', '--internal', '--driver', 'bridge', '--subnet', x.SUBNET,
        '--gateway', x.GATEWAY, '--label', LABEL+'='+name, name]


def inspect_network(control, name, deadline):
    result = control.run(g.DOCKER+['network', 'inspect', name], deadline, check=False, monitor=False)
    if result.returncode:
        listing = control.run(g.DOCKER+['network', 'ls', '-q', '--filter', 'label='+LABEL+'='+name],
                              deadline, check=False, monitor=False)
        c.require(listing.returncode == 0 and not listing.stdout.strip(), 'network absence unconfirmed')
        return None
    value, = json.loads(result.stdout)
    config = (value.get('IPAM') or {}).get('Config') or []
    c.require(value['Name'] == name and value['Driver'] == 'bridge' and value['Internal'] is True and
              value['Labels'].get(LABEL) == name and len(config) == 1 and config[0].get('Subnet') == x.SUBNET and
              config[0].get('Gateway') == x.GATEWAY and not value.get('EnableIPv6'), 'owned network identity mismatch')
    return value


def container_command(root, role, name, network, image):
    staging = root/'staging'
    return g.DOCKER+['create', '--name', name, '--label', LABEL+'='+name, '--cidfile', str(root/f'{role}.cid'),
        *FLAGS, '--network', network, '--ip', x.ROLES[role], '--user', f'{os.getuid()}:{os.getgid()}',
        '-v', str(staging/'harness')+':/out/harness:ro', '-v', str(staging/'build')+':/out/build:ro',
        '-v', str(staging/'inputs.json')+':/out/inputs.json:ro', '-v', str(staging/('control-'+role))+':/out/control',
        '-v', str(staging/('tmp-'+role))+':/out/tmp', '-v', str(root/'persistent'/role)+':/out/private',
        '-v', str(root/'exchange')+':/out/exchange', '-v', str(root/'public'/role)+':/public',
        '--workdir', '/out', image, '/bin/bash', '/out/harness/integration/exposure-runtime.sh']


def verify_limits(value, network, role):
    """The accepted kernel limits, with the owned bridge as the only network and no published port."""
    h = value['HostConfig']
    networks = value['NetworkSettings']['Networks']
    endpoint = networks.get(network) or {}
    # Docker fills IPAddress only once the container runs; the requested static address is in
    # IPAMConfig from create on (native rehearsal 1c226b32). A running container needs both.
    assigned = endpoint.get('IPAddress') == x.ROLES[role] or not value['State']['Running'] and \
        endpoint.get('IPAddress') == ''
    c.require(h['NetworkMode'] == network and set(networks) == {network} and
        (endpoint.get('IPAMConfig') or {}).get('IPv4Address') == x.ROLES[role] and assigned and
        h['NanoCpus'] == 2_000_000_000 and
        h['Memory'] == h['MemorySwap'] == 4*rt.GiB and h['PidsLimit'] == 256 and h['CapDrop'] == ['ALL'] and
        'no-new-privileges' in h['SecurityOpt'] and not h['Privileged'] and not h.get('PortBindings') and
        not h.get('PublishAllPorts') and not any(value['NetworkSettings'].get('Ports') or {}) and
        any(u['Name'] == 'core' and u['Soft'] == u['Hard'] == 0 for u in h['Ulimits']) and
        value['Config']['User'] == f'{os.getuid()}:{os.getgid()}', 'container limit mismatch')


def inspect(control, state, role, deadline, verify=True):
    name, image, root = state['names'][role], state['image'], control.root
    result = control.run(g.DOCKER+['inspect', name], deadline, check=False, monitor=False)
    if result.returncode:
        known = state.get('ids', {}).get(role)
        for identity_filter in ['label='+LABEL+'='+name, 'name=^/'+re.escape(name)+'$']+(['id='+known] if known else []):
            listing = control.run(g.DOCKER+['ps', '--all', '--no-trunc', '--format', '{{.ID}}', '--filter',
                identity_filter], deadline, check=False, monitor=False)
            c.require(listing.returncode == 0 and not listing.stdout.strip(), 'container absence unconfirmed')
        return None
    value, = json.loads(result.stdout)
    c.require(value['Name'] == '/'+name and value['Image'] == image and
              value['Config']['Labels'].get(LABEL) == name and
              any(m['Source'] == str(root/'persistent'/role) and m['Destination'] == '/out/private'
                  for m in value['Mounts']) and re.fullmatch('[0-9a-f]{64}', value['Id']) is not None and
              state.get('ids', {}).get(role) in (None, value['Id']), 'owned container identity mismatch')
    state.setdefault('ids', {})[role] = value['Id']
    if verify:  # Cleanup binds identity only, so a limit mismatch can still be removed.
        verify_limits(value, state['names']['network'], role)
    return value


def heartbeat(root, role):
    try:
        value = r.bounded_json(root/'public'/role/'heartbeat.json', 1024)
    except FileNotFoundError:
        return None
    c.require(set(value) == {'role', 'phase', 'count', 'samples', 'unix'} and value['role'] == role and
              value['phase'] in PHASES and
              all(type(value[k]) is int and 0 <= value[k] < 2**40 for k in ('count', 'samples', 'unix')),
              'heartbeat shape')
    return value


def collect(root, rows, receipt):
    shapes = x.shapes()
    rejected = []
    for role, files in x.DRIVER_FILES.items():
        public = root/'public'/role
        for filename in files:
            try:
                rows[filename].update(r.read_public_rows(public/filename, shapes, x.REQUIRED))
            except FileNotFoundError:
                pass
            except Exception as error:
                rejected.append(error.key_path if isinstance(error, r.PublicWitnessError) else filename)
        for path in (public.iterdir() if public.is_dir() else ()):
            if path.name not in files+('heartbeat.json',):
                rejected.append('unexpected-public-entry')
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()
    if rejected:
        receipt.update(result='FAIL', rejected_evidence=sorted(set(rejected)))


def counters(root):
    values = []
    for role in x.ROLES:
        for path in sorted((root/'staging'/('control-'+role)).glob('resources-*.json')):
            value = r.bounded_json(path, 1024)
            c.require(set(value) == {'oom', 'oom_kill', 'memory_peak_bytes', 'cpu_usage_usec'} and
                      all(type(v) is int and 0 <= v < 2**64 for v in value.values()), 'invalid resource counters')
            values.append(dict(value, role=role))
    return values


def host_rows(control, state):
    """Manager witnesses: internal owned network, no published port, two namespaces."""
    rows = state['rows']['host.json']
    network = inspect_network(control, state['names']['network'], time.monotonic()+60)
    values = {role: inspect(control, state, role, time.monotonic()+60) for role in x.ROLES}
    c.require(network is not None and all(values.values()), 'exposure objects missing')
    attached = {v['Name'] for v in network['Containers'].values()} if network.get('Containers') else set()
    rows['network_internal'] = dict(status='PASS', internal=True, subnet_prefix=29, attached=len(attached),
                                    external_route=False)
    rows['no_published_ports'] = dict(status='PASS', containers=len(values), port_bindings=0, publish_all=False)
    keys = {v['NetworkSettings']['SandboxKey'] for v in values.values()}
    c.require(len(keys) == len(x.ROLES) and all(keys), 'containers share a network namespace')
    rows['distinct_namespaces'] = dict(status='PASS', namespaces=len(keys), role_ips_match=True)


def finish(args, state, control, result_code):
    rows, receipt = state['rows'], state['receipt']
    if result_code is not None:
        receipt.setdefault('failure_class', result_code)
        receipt['result'] = 'FAIL'
    control.cleaning = True
    try:
        exits = {}
        for role in x.ROLES:
            value = inspect(control, state, role, control.end+300, verify=False)
            if value and value['State']['Running']:
                control.run(g.DOCKER+['stop', '--time', '120', value['Id']], time.monotonic()+180, check=False,
                            monitor=False)
                value = inspect(control, state, role, time.monotonic()+60, verify=False)
            if value:
                exits[role] = dict(code=value['State']['ExitCode'], oom=value['State']['OOMKilled'])
        state['exit'] = exits
        collect(args.out, rows, receipt)
        state['counters'] = counters(args.out)
        for role in x.ROLES:
            if state.get('ids', {}).get(role):
                control.run(g.DOCKER+['rm', '-f', state['ids'][role]], time.monotonic()+60, check=False, monitor=False)
            c.require(inspect(control, state, role, time.monotonic()+60, verify=False) is None, 'owned CID remains')
        rows['cleanup.json']['owned_cid_absent'] = dict(status='PASS', containers=len(x.ROLES))
        control.run(g.DOCKER+['network', 'rm', state['names']['network']], time.monotonic()+60, check=False,
                    monitor=False)
        c.require(inspect_network(control, state['names']['network'], time.monotonic()+60) is None,
                  'owned network remains')
        rows['cleanup.json']['owned_network_absent'] = dict(status='PASS')
        if (args.out/'staging').exists():
            os.close(r.private_directory(args.out/'staging'))
            shutil.rmtree(args.out/'staging')
        if (args.out/'exchange').exists():
            shutil.rmtree(args.out/'exchange')  # Steps, counts, tips and pins only; no credential.
        rows['cleanup.json']['owned_staging_removed'] = dict(status='PASS')
    except Exception as error:
        for key in ('owned_cid_absent', 'owned_network_absent', 'owned_staging_removed'):
            if rows['cleanup.json'][key]['status'] != 'PASS':
                rows['cleanup.json'][key] = dict(status='FAIL')
        receipt.update(result='FAIL', cleanup_failure_class=type(error).__name__)
    try:
        for child in control.children:
            control.stop(child)
        rows['cleanup.json']['owned_pids_absent'] = dict(status='PASS', count=len(control.children))
    except Exception:
        rows['cleanup.json']['owned_pids_absent'] = dict(status='FAIL')
        receipt['result'] = 'FAIL'
    keeper = state.get('keeper')
    (args.out/'release').touch(mode=0o600)
    end = time.monotonic()+30
    while keeper and keeper_alive(keeper) and time.monotonic() < end:
        time.sleep(1)
    released = not (keeper and keeper_alive(keeper)) and not rt.lock_held_elsewhere()
    rows['cleanup.json']['lock_released'] = dict(status='PASS' if released else 'FAIL', keeper_exited=released)
    try:
        rows['cleanup.json']['persistent_root_owner_only'] = dict(status='PASS', retained=True,
            mode='0700-dirs-0600-files') if rt.owner_only(args.out/'persistent') else dict(status='FAIL')
    except Exception:
        rows['cleanup.json']['persistent_root_owner_only'] = dict(status='FAIL')
    no_oom = len(state.get('counters', [])) == len(x.ROLES) and all(v['oom'] == v['oom_kill'] == 0 for v in state['counters']) \
        and not any(v['oom'] for v in state.get('exit', {}).values())
    rows['resources.json'] = dict(
        parent_enclosure=dict(status='PASS' if state.get('ids') else 'NOT_RUN',
            mode='container-kernel-limits; host-overhead-measured-only', flags=FLAGS, network=NETWORK,
            host_overhead_allowance=rt.OVERHEAD, measured=dict(control.peak), samples=control.samples),
        deadlines=dict(status='PASS' if time.time() < state['end_unix'] else 'FAIL',
            wall_seconds=x.MODES[state['uptime']], uptime_seconds=state['uptime']),
        disk=dict(status='PASS' if control.samples else 'NOT_RUN', peak_bytes=control.peak['disk_bytes'],
            abort_bytes=15*rt.GiB, minimum_free_bytes=4*rt.GiB, mode='sampled-abort-not-quota'),
        no_oom=dict(status='PASS' if no_oom else 'FAIL', containers=len(state.get('counters', []))))
    if receipt['result'] == 'INCOMPLETE':
        receipt['result'] = x.verdict(rows, state['uptime'])
    receipt['rows'] = rows
    rt.write_private(args.out/STATE, state)
    r.publish_evidence(args.out, rows, receipt)
    print(json.dumps(dict(result=receipt['result'], public_launch=False)))
    return 0 if receipt['result'].startswith(('PASS_', 'REHEARSAL_PASS_')) else 1


def observe(args, state, control):
    """Watch every role container until all exit; one failure stops the others."""
    while True:
        c.require(time.time() < state['end_unix'], 'exposure wall exhausted')
        c.require(keeper_alive(state['keeper']) and rt.lock_held_elsewhere(), 'heavy-lock keeper lost')
        control.sample()
        values = {role: inspect(control, state, role, time.monotonic()+60) for role in x.ROLES}
        c.require(all(values.values()), 'owned container missing')
        if state['rows']['host.json']['network_internal']['status'] == 'NOT_RUN' and \
                all(v['State']['Running'] for v in values.values()):
            host_rows(control, state)
            rt.write_private(args.out/STATE, state)
        beats = {role: heartbeat(args.out, role) for role in x.ROLES}
        stopped = {role: v['State']['ExitCode'] for role, v in values.items() if not v['State']['Running']}
        if any(code != 0 for code in stopped.values()):
            return finish(args, state, control, 'native_exit')
        if len(stopped) == len(x.ROLES):
            done = all(beat and beat['phase'] == 'complete' for beat in beats.values())
            return finish(args, state, control, None if done else 'native_exit')
        time.sleep(30)


def start(args):
    c.require(os.getsid(0) == os.getpid(), 'exposure manager requires a detached session leader')
    c.require(re.fullmatch(r'[0-9a-f-]{36}', args.grant_comment) is not None and
              re.fullmatch('[0-9a-f]{64}', args.artifact_sha256) is not None, 'new exact grant and artifact digest')
    c.require(args.out.is_absolute() and args.out == args.out.resolve() and args.out.parent.is_dir() and
              not args.out.exists(), 'fresh absolute output root required')
    commit = subprocess.check_output(['git', '-C', str(n.ROOT), 'rev-parse', 'HEAD'], text=True, timeout=10).strip()
    c.require(not subprocess.check_output(['git', '-C', str(n.ROOT), 'status', '--porcelain'], text=True,
              timeout=10).strip(), 'commit exact candidate first')
    manifest = r.check_inputs(args.inputs)
    reuse = r.reuse_build(args.reuse_build, manifest)
    comment = json.loads(r.api('/api/issues/'+x.ISSUE+'/comments/'+args.grant_comment))
    c.require(comment['id'] == args.grant_comment, 'grant comment identity')
    runner = c.digest(Path(__file__).read_bytes())
    driver = c.digest((c.HERE/DRIVER).read_bytes())
    grant = grant_payload(comment, commit=commit, inputs_hash=c.digest(args.inputs.read_bytes()),
        artifact_hash=args.artifact_sha256, runner_hash=runner, driver_hash=driver, output=args.out,
        now=time.time(), reuse=reuse)
    c.require(c.digest(r.api('/api/attachments/'+grant['artifact_attachment_id']+'/content')) == args.artifact_sha256,
              'authenticated artifact digest mismatch')
    image = manifest['builder_image']
    first = r.admit(image, args.out.parent, grant)
    c.require(not rt.lock_held_elsewhere(), 'heavy lock busy')
    n.fresh_directory(args.out)  # Durable one-use marker; a crash after this consumes the grant.
    end_unix = int(time.time())+grant['wall_seconds']
    state = dict(schema='meownero-exposure-manager/1', grant=args.grant_comment, commit=commit,
        uptime=grant['uptime_seconds'], runner_sha256=runner, driver_sha256=driver, end_unix=end_unix,
        names=names(args.grant_comment), image=image, rows=x.empty_rows(),
        receipt=dict(schema='meownero-exposure-attempt/1', result='INCOMPLETE', public_launch=False,
            launch_ready=False, mode=grant['verdict_label'], grant=args.grant_comment, candidate_commit=commit,
            runner_sha256=runner, driver_sha256=driver, first_admission=first, network=NETWORK,
            exclusions={k: 'NOT_RUN' for k in x.EXCLUDED},
            build_reuse=dict(retained_build_sha256=reuse['manifest_sha256'],
                             authority_comment=r.funded.AUTHORITY_COMMENT)))
    holder = {}
    try:
        return launch(args, state, grant, reuse, image, end_unix, holder)
    except Exception as error:
        control = holder.get('control') or rt.Manager(args.out, grant, time.monotonic(),
                                                      time.monotonic()+max(60, end_unix-time.time()))
        state['receipt']['failure_class'] = type(error).__name__
        return finish(args, state, control, 'manager_'+type(error).__name__)


def launch(args, state, grant, reuse, image, end_unix, holder):
    keeper = rt.spawn_keeper(args.out, end_unix+600)
    deadline = time.time()+30
    while not (args.out/'keeper.json').exists() and keeper.poll() is None and time.time() < deadline:
        time.sleep(.2)
    record = rt.read_private(args.out/'keeper.json')
    c.require(keeper.poll() is None and record['pid'] == rt.identity(keeper.pid) and
              tuple((record['lock']['device'], record['lock']['inode'])) == g.LOCK_ID and rt.lock_held_elsewhere(),
              'lock keeper did not take the original heavy lock')
    state['keeper'] = record['pid']
    state['receipt']['lock'] = record['lock']
    rt.write_private(args.out/STATE, state)
    control = holder['control'] = rt.Manager(args.out, grant, time.monotonic(), time.monotonic()+(end_unix-time.time()))
    staging = args.out/'staging'
    staging.mkdir(mode=0o700)
    for role in x.ROLES:
        for sub in ('tmp-'+role, 'control-'+role):
            (staging/sub).mkdir(mode=0o700)
        (staging/('control-'+role)/'role').write_text(role+'\n')
        (staging/('control-'+role)/'end-unix').write_text(str(end_unix)+'\n')
        (staging/('control-'+role)/'uptime-seconds').write_text(str(grant['uptime_seconds'])+'\n')
    for sub in ('public', 'persistent'):
        (args.out/sub).mkdir(mode=0o700)
        for role in x.ROLES:
            (args.out/sub/role).mkdir(mode=0o700)
    (args.out/'exchange').mkdir(mode=0o700)
    shutil.copytree(c.HERE, staging/'harness', copy_function=control.copy,
                    ignore=shutil.ignore_patterns('evidence', '__pycache__', 'core-review'))
    control.copy(args.inputs, staging/'inputs.json')
    binaries = staging/'build/bin'
    binaries.mkdir(parents=True, mode=0o700)
    source = r.private_directory(reuse['root']/'retained-build')
    target = r.private_directory(binaries)
    try:
        for binary in r.BINARIES:
            r.binary_copy(source, binary, reuse['binaries'][binary], target, control)
    finally:
        os.close(source)
        os.close(target)
    # Both admissions precede the first owned container (admission counts native containers).
    state['receipt']['second_admission'] = r.admit(image, args.out, grant)
    info = control.run(g.DOCKER+['image', 'inspect', image], time.monotonic()+30, monitor=False)
    c.require(json.loads(info.stdout)[0]['Id'] == image, 'local pinned image required')
    subnet_free(control, time.monotonic()+60)
    control.run(network_command(state['names']['network']), time.monotonic()+30)
    c.require(inspect_network(control, state['names']['network'], time.monotonic()+30) is not None,
              'created network missing')
    state['network_created'] = True
    for role in x.ROLES:
        control.run(container_command(args.out, role, state['names'][role], state['names']['network'], image),
                    time.monotonic()+30)
        c.require(inspect(control, state, role, time.monotonic()+30) is not None, 'created container missing')
    state['receipt']['container_ids'] = dict(state['ids'])
    rt.write_private(args.out/STATE, state)
    for role in x.ROLES:  # Seed, client, foreign.
        control.run(g.DOCKER+['start', state['ids'][role]], time.monotonic()+30)
    rt.write_private(args.out/STATE, state)
    return observe(args, state, control)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    first = sub.add_parser('start')
    first.add_argument('--inputs', type=Path, default=c.HERE/'integration/inputs.json')
    first.add_argument('--grant-comment', required=True)
    first.add_argument('--artifact-sha256', required=True)
    first.add_argument('--reuse-build', type=Path, required=True)
    first.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    return start(args)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as error:
        print('REFUSED: '+type(error).__name__+': '+str(error)[:200], file=sys.stderr)
        raise SystemExit(3)
