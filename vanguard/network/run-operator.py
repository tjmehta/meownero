#!/usr/bin/env python3
"""TJS-4238 operator-package manager. Needs a fresh exact Platform grant.

Derived from the accepted milestone-3 exposure manager (run-exposure.py): the same
keeper on the original heavy lock, measured host-overhead allowance, admissions,
retained build verification, closed public-row reader and owned `--internal` /29
with no published host port. Three containers, one per network namespace: the
public-shape seed, the client and the monitor. The monitor has no exchange mount;
this manager relays the seed's pin and operator status to it (the operator
channel). It runs the read-only host-reach probe (host_reach.py) while the seed
serves, and when every role serves it performs the timed rollback (`rollback`):
stop the seed first (it seals), then the others, attest the seal offline, remove
the containers and the network, and check absence from the host. Port-rule and
DNS-record absence checks run too and fail closed (UNVERIFIED) with no vantage.
It never activates anything public.

Exit codes: 0 PASS (or rehearsal pass), 1 FAIL, 3 refused before attempt.
"""
import argparse
import contextlib
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import network as n
import profile_contract as c
from integration import host_reach as hr
from integration import operator_contract as x
from integration import outside_monitor as om

spec = importlib.util.spec_from_file_location('topology_manager_for_operator', c.HERE/'run-topology.py')
rt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rt)
r, g = rt.r, rt.g

STATE = 'operator-state.json'
DRIVER = 'integration/operator_driver.py'
LABEL = 'meownero.operator.attempt'
ORDER = ('seed', 'client', 'monitor')  # Rollback stops the seed first: it is the kill switch.
# The accepted container limits, with only the network mode replaced by the owned bridge.
FLAGS = [f for f in r.CONTAINER_FLAGS if f != '--network=none']
NETWORK = dict(driver='bridge', internal=True, subnet=x.SUBNET, gateway=x.GATEWAY, seed_ip=x.SEED_IP,
               client_ip=x.CLIENT_IP, monitor_ip=x.MONITOR_IP, published_ports=0)
PHASES = ('new', 'rows', 'exposed', 'restarted', 'recovered', 'bootstrapped', 'newcomer', 'following', 'serving',
          'complete', 'failed')
SERVING = ('exposed', 'restarted', 'recovered', 'serving')


def grant_payload(comment, *, commit, inputs_hash, artifact_hash, runner_hash, driver_hash, output, now, reuse):
    c.require(comment['issueId'] == x.ISSUE and comment.get('authorAgentId') == c.PLATFORM and
              comment.get('authorUserId') is None, 'Platform-authored TJS-4238 grant required')
    blocks = re.findall(r'```meownero-operator-grant\s*\n(.*?)\n```', comment['body'], re.S)
    c.require(len(blocks) == 1, 'one operator grant block required')
    value = json.loads(blocks[0])
    expected = dict(schema='meownero-operator-grant/1', authorized=True, workload=x.WORKLOAD,
        candidate_commit=commit, inputs_sha256=inputs_hash, artifact_sha256=artifact_hash,
        runner_sha256=runner_hash, driver_sha256=driver_hash, output_root=str(output), attempts=1,
        retry=False, container_flags=FLAGS, network=NETWORK, mode='runtime-only',
        reuse_build_root=str(reuse['root']), retained_build_sha256=reuse['manifest_sha256'],
        retained_build_authority_comment=r.funded.AUTHORITY_COMMENT, main_chain_count_max=x.MAX_COUNT,
        mining_threads=1, transactions=0, heavy_lock='keeper-held-for-wall', detached_session=True,
        no_other_heavy_lock_workload_scheduled=True, host_overhead_allowance=rt.OVERHEAD,
        listeners='internal-bridge-public-seed-shape-no-published-port', public_launch=False, launch_ready=False,
        firewall_or_dns_change=False, uid_creation=False)
    c.require(all(type(value.get(k)) is type(v) and value[k] == v for k, v in expected.items()),
              'operator grant binding mismatch')
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
    return dict(network='meownero-operator-'+grant, **{role: f'meownero-operator-{role}-{grant}' for role in x.ROLES})


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
                    raise ValueError('owned operator subnet already in use')
    for line in Path('/proc/net/route').read_text().splitlines()[1:]:
        parts = line.split()
        destination = ipaddress.ip_address(bytes.fromhex(parts[1])[::-1])
        mask = ipaddress.ip_address(bytes.fromhex(parts[7])[::-1])
        if parts[1] != '00000000' and ipaddress.ip_network(f'{destination}/{mask}', strict=False).overlaps(owned):
            raise ValueError('owned operator subnet overlaps a host route')
    return True


def route_absent():
    """No host route overlaps the owned /29 (after the network is removed)."""
    owned = ipaddress.ip_network(x.SUBNET)
    for line in Path('/proc/net/route').read_text().splitlines()[1:]:
        parts = line.split()
        destination = ipaddress.ip_address(bytes.fromhex(parts[1])[::-1])
        mask = ipaddress.ip_address(bytes.fromhex(parts[7])[::-1])
        if parts[1] != '00000000' and ipaddress.ip_network(f'{destination}/{mask}', strict=False).overlaps(owned):
            return False
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
    """The monitor gets no exchange mount: its pin and status come only through the operator channel."""
    staging = root/'staging'
    exchange = [] if role == 'monitor' else ['-v', str(root/'exchange')+':/out/exchange']
    return g.DOCKER+['create', '--name', name, '--label', LABEL+'='+name, '--cidfile', str(root/f'{role}.cid'),
        *FLAGS, '--network', network, '--ip', x.ROLES[role], '--user', f'{os.getuid()}:{os.getgid()}',
        '-v', str(staging/'harness')+':/out/harness:ro', '-v', str(staging/'build')+':/out/build:ro',
        '-v', str(staging/'inputs.json')+':/out/inputs.json:ro', '-v', str(staging/('control-'+role))+':/out/control',
        '-v', str(staging/('tmp-'+role))+':/out/tmp', '-v', str(root/'persistent'/role)+':/out/private',
        *exchange, '-v', str(root/'public'/role)+':/public',
        '--workdir', '/out', image, '/bin/bash', '/out/harness/integration/operator-runtime.sh']


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
    c.require(network is not None and all(values.values()), 'operator objects missing')
    attached = {v['Name'] for v in network['Containers'].values()} if network.get('Containers') else set()
    rows['network_internal'] = dict(status='PASS', internal=True, subnet_prefix=29, attached=len(attached),
                                    external_route=False)
    rows['no_published_ports'] = dict(status='PASS', containers=len(values), port_bindings=0, publish_all=False)
    keys = {v['NetworkSettings']['SandboxKey'] for v in values.values()}
    c.require(len(keys) == len(x.ROLES) and all(keys), 'containers share a network namespace')
    rows['distinct_namespaces'] = dict(status='PASS', namespaces=len(keys), role_ips_match=True)


def attest_sealed(root):
    """Offline, on the host: the seed root's own manifest says stopped-and-saved and its digests match."""
    manifest = json.loads(c.check_file(root/'creation.json'))
    c.require(manifest.get('stopped_saved') is True, 'seed root not sealed on stop')
    c.root_manifest(root, manifest)
    return True


def read_relayed(path, attempts=5):
    """c.check_file, except a file replaced while open (the seed rewrites by rename every 2 s,
    so the old inode reads link count 0) is read again instead of refused."""
    for _ in range(attempts):
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            info = os.fstat(fd)
            if info.st_nlink == 0:
                continue  # Replaced under us: open the new file.
            c.require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == os.getuid() and
                      stat.S_IMODE(info.st_mode) == 0o600, 'private regular file identity/mode')
            return os.read(fd, 8192)
        finally:
            os.close(fd)
    raise ValueError('operator channel item kept changing')


def relay(root):
    """Operator channel: copy the seed's pin and status into the monitor's control directory."""
    source, target = root/'staging'/'control-seed', root/'staging'/'control-monitor'
    for name, destination in (('pin', 'pin'), ('status.json', 'seed-status.json')):
        try:
            raw = read_relayed(source/name)
        except FileNotFoundError:
            continue
        c.require(len(raw) <= 4096, 'operator channel item size')
        if name == 'pin':
            c.require(om.PIN.fullmatch(raw.decode().strip()) is not None, 'operator pin shape')
        else:
            value = json.loads(raw)
            c.require(type(value) is dict and set(value) == om.STATUS_KEYS, 'operator status shape')
        temporary = target/(destination+'.new')
        with contextlib.suppress(FileNotFoundError):
            temporary.unlink()
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
        os.replace(temporary, target/destination)


def host_reach(state):
    """Security note 1: a host-namespace connection to the seed's bridge address (no byte sent)."""
    outcomes = {port: hr.probe(x.SEED_IP, port, hold=x.HOST_PROBE_HOLD) for port in (x.P2P['S'], x.RPC['S'])}
    state['rows']['host.json']['host_reach'] = dict(status='PASS', p2p=outcomes[x.P2P['S']],
        rpc=outcomes[x.RPC['S']], bytes_sent=0, same_uid_boundary='connected' in outcomes.values(),
        probe='host-namespace-tcp-connect')
    return outcomes


def no_vantage():
    """The dev host has no outside vantage and creates no port rule or DNS record."""
    return None


def rollback(control, state, root):
    """Timed rollback; also the standalone `rollback` subcommand when the manager is gone.

    Returns (rollback.json rows, exits). Every absence check fails closed.
    """
    began, steps = time.monotonic(), 0
    rows = {key: dict(status='FAIL') for key in x.REQUIRED['rollback.json']}
    exits = {}
    for role in ORDER:  # The seed first: its driver stops and seals S on SIGTERM.
        value = inspect(control, state, role, time.monotonic()+60, verify=False)
        if value and value['State']['Running']:
            control.run(g.DOCKER+['stop', '--time', '120', value['Id']], time.monotonic()+180, check=False,
                        monitor=False)
            steps += 1
            value = inspect(control, state, role, time.monotonic()+60, verify=False)
        if value:
            exits[role] = dict(code=value['State']['ExitCode'], oom=value['State']['OOMKilled'])
    with contextlib.suppress(Exception):
        if attest_sealed(root/'persistent'/'seed'/'nodes'/'S'):
            rows['seed_sealed_on_stop'] = dict(status='PASS', stopped_saved=True, manifest_matches=True,
                                               attested_offline=True)
    steps += 1
    removed = 0
    for role in ORDER:
        if state.get('ids', {}).get(role):
            control.run(g.DOCKER+['rm', '-f', state['ids'][role]], time.monotonic()+60, check=False, monitor=False)
        removed += inspect(control, state, role, time.monotonic()+60, verify=False) is None
    steps += 1
    control.run(g.DOCKER+['network', 'rm', state['names']['network']], time.monotonic()+60, check=False,
                monitor=False)
    network = inspect_network(control, state['names']['network'], time.monotonic()+60) is None
    steps += 1
    route = route_absent()
    listener = hr.probe(x.SEED_IP, x.P2P['S'], timeout=2) != 'connected'
    steps += 1
    if removed == len(x.ROLES) and network and route and listener:
        rows['owned_objects_absent'] = dict(status='PASS', containers=removed, network=True, route=True,
                                            listener_from_host=True)
    verdicts = {kind: x.absence(kind, no_vantage) for kind in x.OBJECT_CLASSES}
    steps += 1
    if all(v == 'UNVERIFIED' for v in verdicts.values()):
        rows['future_objects_fail_closed'] = dict(status='PASS', classes=len(verdicts), created=0,
            port_rule=verdicts['port-rule'], dns_record=verdicts['dns-record'], removal_commands_recorded=True)
    seconds = round(time.monotonic()-began, 3)
    rows['rollback_timing'] = dict(status='PASS', seconds=seconds, steps=steps)
    state['rollback'] = dict(seconds=seconds, steps=steps, exits=exits, absence=verdicts)
    return rows, exits


def finish(args, state, control, result_code):
    rows, receipt = state['rows'], state['receipt']
    if result_code is not None:
        receipt.setdefault('failure_class', result_code)
        receipt['result'] = 'FAIL'
    control.cleaning = True
    try:
        rows['rollback.json'], exits = rollback(control, state, args.out)
        state['exit'] = exits
        if result_code is None:
            c.require(set(exits) == set(x.ROLES) and all(v['code'] == 0 for v in exits.values()),
                      'a role did not finish its rollback')
        collect(args.out, rows, receipt)
        state['counters'] = counters(args.out)
        c.require(all(inspect(control, state, role, time.monotonic()+60, verify=False) is None for role in x.ROLES),
                  'owned CID remains')
        rows['cleanup.json']['owned_cid_absent'] = dict(status='PASS', containers=len(x.ROLES))
        c.require(inspect_network(control, state['names']['network'], time.monotonic()+60) is None,
                  'owned network remains')
        rows['cleanup.json']['owned_network_absent'] = dict(status='PASS')
        if (args.out/'staging').exists():
            os.close(r.private_directory(args.out/'staging'))
            shutil.rmtree(args.out/'staging')
        if (args.out/'exchange').exists():
            shutil.rmtree(args.out/'exchange')  # Steps, counts and tips only; no credential, no pin.
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
    receipt['rollback'] = state.get('rollback')
    rt.write_private(args.out/STATE, state)
    r.publish_evidence(args.out, rows, receipt)
    print(json.dumps(dict(result=receipt['result'], public_launch=False)))
    return 0 if receipt['result'].startswith(('PASS_', 'REHEARSAL_PASS_')) else 1


def observe(args, state, control):
    """Watch every role; relay the operator channel; probe host reach; roll back when all serve."""
    while True:
        c.require(time.time() < state['end_unix'], 'operator wall exhausted')
        c.require(keeper_alive(state['keeper']) and rt.lock_held_elsewhere(), 'heavy-lock keeper lost')
        control.sample()
        values = {role: inspect(control, state, role, time.monotonic()+60) for role in x.ROLES}
        c.require(all(values.values()), 'owned container missing')
        if any(not v['State']['Running'] for v in values.values()):
            return finish(args, state, control, 'native_exit')  # Containers stop only in the rollback.
        if state['rows']['host.json']['network_internal']['status'] == 'NOT_RUN':
            host_rows(control, state)
            rt.write_private(args.out/STATE, state)
        beats = {role: heartbeat(args.out, role) for role in x.ROLES}
        relay(args.out)
        seed = beats['seed']
        if state['rows']['host.json']['host_reach']['status'] == 'NOT_RUN' and seed and seed['phase'] in SERVING:
            host_reach(state)
            rt.write_private(args.out/STATE, state)
        if all(beat and beat['phase'] == 'serving' for beat in beats.values()) and \
                state['rows']['host.json']['host_reach']['status'] == 'PASS':
            return finish(args, state, control, None)  # finish() performs the timed rollback.
        time.sleep(30)


def start(args):
    c.require(os.getsid(0) == os.getpid(), 'operator manager requires a detached session leader')
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
    state = dict(schema='meownero-operator-manager/1', grant=args.grant_comment, commit=commit,
        manager=rt.identity(os.getpid()),
        uptime=grant['uptime_seconds'], runner_sha256=runner, driver_sha256=driver, end_unix=end_unix,
        names=names(args.grant_comment), image=image, rows=x.empty_rows(),
        receipt=dict(schema='meownero-operator-attempt/1', result='INCOMPLETE', public_launch=False,
            launch_ready=False, mode=grant['verdict_label'], grant=args.grant_comment, candidate_commit=commit,
            runner_sha256=runner, driver_sha256=driver, first_admission=first, network=NETWORK,
            exclusions={k: dict(status='NOT_RUN', reason=v) for k, v in x.EXCLUDED.items()},
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
    for role in x.ROLES:  # Seed, client, monitor.
        control.run(g.DOCKER+['start', state['ids'][role]], time.monotonic()+30)
    rt.write_private(args.out/STATE, state)
    return observe(args, state, control)


def standalone_rollback(args):
    """Operator kill switch when the manager is gone: the same timed rollback, then release the keeper."""
    state = rt.read_private(args.out/STATE)
    c.require(state.get('schema') == 'meownero-operator-manager/1' and not rt.alive(state['manager']),
              'the attempt manager is still alive; it owns the rollback')
    c.require(not (args.out/'evidence').exists(), 'attempt already finished')
    control = rt.Manager(args.out, dict(host_overhead_allowance=rt.OVERHEAD), time.monotonic(), time.monotonic()+900)
    control.cleaning = True
    rows, exits = rollback(control, state, args.out)
    state['standalone_rollback'] = dict(rows=rows, exits=exits)
    rt.write_private(args.out/STATE, state)
    (args.out/'release').touch(mode=0o600)
    print(json.dumps(dict(rows=rows, seconds=state['rollback']['seconds']), sort_keys=True))
    return 0 if all(v['status'] == 'PASS' for v in rows.values()) else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    first = sub.add_parser('start')
    first.add_argument('--inputs', type=Path, default=c.HERE/'integration/inputs.json')
    first.add_argument('--grant-comment', required=True)
    first.add_argument('--artifact-sha256', required=True)
    first.add_argument('--reuse-build', type=Path, required=True)
    first.add_argument('--out', type=Path, required=True)
    back = sub.add_parser('rollback')
    back.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    return start(args) if args.command == 'start' else standalone_rollback(args)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as error:
        print('REFUSED: '+type(error).__name__+': '+str(error)[:200], file=sys.stderr)
        raise SystemExit(3)
