#!/usr/bin/env python3
"""TJS-3920 persistent isolated topology manager. Needs a fresh exact Platform grant.

Reuses the accepted direct runner's lock, admissions, container flags, retained
build verification and closed public-row reader. A separate keeper process holds
the original heavy lock for the whole grant so this manager itself can stop and
start; the container and its owner-only persistent root survive both.

Exit codes: 0 PASS, 1 FAIL, 3 refused before attempt, 10 planned full cycle
(container and manager stopped; run `resume`), 11 planned manager-only restart.
"""
import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import sys
import time

import network as n
import profile_contract as c
from integration import topology_contract as t

spec = importlib.util.spec_from_file_location('direct_runner', c.HERE/'run-profile.py')
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
g = r.g

GiB = r.GiB
STATE = 'manager-state.json'
CYCLE, RESTART = 10, 11
MANAGER_RESTART_AFTER_SAMPLES = 12  # One steady hour.
SAMPLE_SECONDS = 60
OVERHEAD = dict(mode='measured-controller-and-descendants-not-kernel-enforced',
                peak_rss_bytes=GiB, cpu_seconds=4000, peak_pids=32)


def grant_payload(comment, *, commit, inputs_hash, artifact_hash, runner_hash, driver_hash, output, now, reuse):
    c.require(comment['issueId'] == t.ISSUE and comment.get('authorAgentId') == c.PLATFORM and
              comment.get('authorUserId') is None, 'Platform-authored TJS-3920 grant required')
    blocks = re.findall(r'```meownero-topology-grant\s*\n(.*?)\n```', comment['body'], re.S)
    c.require(len(blocks) == 1, 'one topology grant block required')
    value = json.loads(blocks[0])
    expected = dict(schema='meownero-topology-grant/1', authorized=True, workload=t.WORKLOAD,
        candidate_commit=commit, inputs_sha256=inputs_hash, artifact_sha256=artifact_hash,
        runner_sha256=runner_hash, driver_sha256=driver_hash, output_root=str(output), attempts=1,
        retry=False, wall_seconds=t.WALL_SECONDS, uptime_seconds=t.UPTIME_SECONDS,
        container_flags=r.CONTAINER_FLAGS, mode='runtime-only', reuse_build_root=str(reuse['root']),
        retained_build_sha256=reuse['manifest_sha256'], retained_build_authority_comment=r.funded.AUTHORITY_COMMENT,
        main_chain_count_max=t.MAX_COUNT, mining_threads=1, transactions=0,
        heavy_lock='keeper-held-for-wall', detached_session=True, no_other_heavy_lock_workload_scheduled=True,
        host_overhead_allowance=OVERHEAD, listeners='loopback-only-network-none', public_launch=False)
    c.require(all(type(value.get(k)) is type(v) and value[k] == v for k, v in expected.items()),
              'topology grant binding mismatch')
    c.require(str(reuse['root']) == r.funded.RETAINED_ROOT and reuse['manifest_sha256'] == r.funded.RETAINED_SHA256,
              'published retained build authority required')
    rule = value['load_rule']
    c.require(rule['metric'] == 'host-load-1-5-15' and len(rule['maximum']) == 3 and
              all(type(x) in (int, float) and 0 < x < 1000 for x in rule['maximum']), 'explicit load rule')
    c.require(value['valid_until_unix']-value['valid_from_unix'] >= 48*3600 and
              value['valid_from_unix'] <= now and now+t.WALL_SECONDS <= value['valid_until_unix'],
              'grant validity window')
    c.require(re.fullmatch(r'[0-9a-f-]{36}', value['artifact_attachment_id']) is not None, 'artifact attachment ID')
    return value


def identity(pid):
    return r.pid_identity(pid)


def alive(owned):
    try:
        return identity(owned[0]) == owned
    except (FileNotFoundError, ProcessLookupError, IndexError):
        return False


def write_private(path, value):
    raw = (json.dumps(value, indent=2, sort_keys=True)+'\n').encode()
    temporary = path.with_name(path.name+'.new')
    if temporary.exists() or temporary.is_symlink():
        temporary.unlink()
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def read_private(path):
    return json.loads(c.check_file(path))


def lock_held_elsewhere():
    """True only when another open description holds the original heavy lock."""
    fd = os.open(g.LOCK, os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        c.require((info.st_dev, info.st_ino) == g.LOCK_ID, 'heavy lock identity changed')
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    finally:
        os.close(fd)


def keep_lock(root, until):
    """Detached keeper: the sole lock descriptor for the grant wall."""
    os.umask(0o077)
    fd, lock = r.acquire_lock()
    write_private(root/'keeper.json', dict(pid=identity(os.getpid()), lock=lock, until=until))
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
    try:
        while time.time() < until and not (root/'release').exists():
            time.sleep(5)
    finally:
        os.close(fd)
    return 0


class Manager(r.Controller):
    """Same measured host-overhead rules; sampled every 60 s over the long wall."""
    def __init__(self, root, grant, start, end_monotonic):
        super().__init__(root, grant, start)
        self.build_end = self.work_end = self.end = end_monotonic

    def sample(self, force=False):
        now = time.monotonic()
        if not force and now-self.last_sample < SAMPLE_SECONDS:
            return
        self.last_sample = now
        try:
            free = shutil.disk_usage(self.root).free
        except OSError:
            raise r.MetrologyFailure('metrology_backing_disk', 'observation_failed') from None
        if free < 4*GiB:
            raise r.MetrologyFailure('metrology_backing_disk', 'free disk below 4 GiB')
        used = self.disk_bytes(min(now+60, self.end))
        self.peak['disk_bytes'] = max(self.peak['disk_bytes'], used)
        if used > 15*GiB:
            raise r.MetrologyFailure('metrology_disk_walk', 'owned directory exceeds 15 GiB')
        self.sample_host()
        self.samples += 1


def container_command(root, name, image):
    staging = root/'staging'
    return g.DOCKER+['create', '--name', name, '--label', 'meownero.topology.attempt='+name,
        '--cidfile', str(root/'container.cid'), *r.CONTAINER_FLAGS, '--user', f'{os.getuid()}:{os.getgid()}',
        '-v', str(staging/'harness')+':/out/harness:ro', '-v', str(staging/'build')+':/out/build:ro',
        '-v', str(staging/'inputs.json')+':/out/inputs.json:ro', '-v', str(staging/'control')+':/out/control',
        '-v', str(staging/'tmp')+':/out/tmp', '-v', str(root/'persistent')+':/out/private',
        '-v', str(root/'public')+':/public', '--workdir', '/out', image,
        '/bin/bash', '/out/harness/integration/topology-runtime.sh']


def inspect(control, name, image, deadline):
    result = control.run(g.DOCKER+['inspect', name], deadline, check=False, monitor=False)
    if result.returncode:
        for identity_filter in ['label=meownero.topology.attempt='+name, 'name=^/'+re.escape(name)+'$'] + (
                ['id='+control.container_id] if control.container_id else []):
            listing = control.run(g.DOCKER+['ps', '--all', '--no-trunc', '--format', '{{.ID}}', '--filter',
                identity_filter], deadline, check=False, monitor=False)
            c.require(listing.returncode == 0 and not listing.stdout.strip(), 'container absence unconfirmed')
        return None
    value, = json.loads(result.stdout)
    c.require(value['Name'] == '/'+name and value['Image'] == image and
              value['Config']['Labels'].get('meownero.topology.attempt') == name and
              any(m['Source'] == str(control.root/'persistent') and m['Destination'] == '/out/private'
                  for m in value['Mounts']) and
              re.fullmatch('[0-9a-f]{64}', value['Id']) is not None and
              control.container_id in (None, value['Id']), 'owned container identity mismatch')
    control.container_id = value['Id']
    r.verify_limits(value)
    return value


def owner_only(root):
    for path in [root, *root.rglob('*')]:
        info = path.lstat()
        c.require(info.st_uid == os.getuid() and not path.is_symlink() and
                  (stat.S_ISDIR(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o700 or
                   stat.S_ISREG(info.st_mode) and not stat.S_IMODE(info.st_mode) & 0o077), 'persistent root mode')
    return True


def heartbeat(root):
    try:
        value = r.bounded_json(root/'public/heartbeat.json', 1024)
    except FileNotFoundError:
        return None
    c.require(set(value) == {'phase', 'generation', 'count', 'samples', 'unix'} and
              value['phase'] in ('rows', 'new', 'cycle', 'steady', 'complete', 'failed') and
              all(type(value[k]) is int and 0 <= value[k] < 2**40 for k in ('generation', 'count', 'samples', 'unix')),
              'heartbeat shape')
    return value


def collect(root, rows, receipt):
    shapes = t.shapes()
    rejected = []
    public = root/'public'
    for filename in t.DRIVER_FILES+('persistence.json',):
        try:
            value = r.read_public_rows(public/filename, shapes, t.REQUIRED)
            if filename == 'persistence.json':
                c.require(set(value) <= set(t.DRIVER_PERSISTENCE), 'driver persistence row')
            rows[filename].update(value)
        except FileNotFoundError:
            pass
        except Exception as error:
            rejected.append(error.key_path if isinstance(error, r.PublicWitnessError) else filename)
    for path in public.iterdir():
        if path.name not in t.DRIVER_FILES+('persistence.json', 'heartbeat.json'):
            rejected.append('unexpected-public-entry')
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
    if rejected:
        receipt.update(result='FAIL', rejected_evidence=sorted(set(rejected)))


def counters(root):
    values = []
    for path in sorted((root/'staging/control').glob('resources-*.json')):
        value = r.bounded_json(path, 1024)
        c.require(set(value) == {'oom', 'oom_kill', 'memory_peak_bytes', 'cpu_usage_usec'} and
                  all(type(x) is int and 0 <= x < 2**64 for x in value.values()), 'invalid resource counters')
        values.append(value)
    return values


def finish(args, state, control, name, image, result_code):
    """Collect, remove the container, release the keeper and publish 0600 evidence."""
    rows, receipt = state['rows'], state['receipt']
    if result_code is not None:
        receipt.setdefault('failure_class', result_code)
        receipt['result'] = 'FAIL'
    control.cleaning = True
    try:
        value = inspect(control, name, image, control.end+300)
        if value and value['State']['Running']:
            control.run(g.DOCKER+['stop', '--time', '120', value['Id']], time.monotonic()+180, check=False, monitor=False)
            value = inspect(control, name, image, time.monotonic()+60)
        if value:
            state['exit'] = dict(code=value['State']['ExitCode'], oom=value['State']['OOMKilled'])
        collect(args.out, rows, receipt)
        state['counters'] = counters(args.out)
        if value:
            control.run(g.DOCKER+['rm', '-f', value['Id']], time.monotonic()+60, check=False, monitor=False)
        c.require(inspect(control, name, image, time.monotonic()+60) is None, 'owned CID remains')
        rows['cleanup.json']['owned_cid_absent'] = dict(status='PASS')
    except Exception as error:
        rows['cleanup.json']['owned_cid_absent'] = dict(status='FAIL')
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
    while keeper and alive(keeper) and time.monotonic() < end:
        time.sleep(1)
    released = not (keeper and alive(keeper)) and not lock_held_elsewhere()
    rows['cleanup.json']['lock_released'] = dict(status='PASS' if released else 'FAIL', keeper_exited=released)
    try:
        rows['cleanup.json']['persistent_root_owner_only'] = dict(status='PASS', retained=True,
            mode='0700-dirs-0600-files') if owner_only(args.out/'persistent') else dict(status='FAIL')
    except Exception:
        rows['cleanup.json']['persistent_root_owner_only'] = dict(status='FAIL')
    no_oom = bool(state.get('counters')) and all(x['oom'] == x['oom_kill'] == 0 for x in state['counters']) and \
        not state.get('exit', {}).get('oom', False)
    rows['resources.json'] = dict(
        parent_enclosure=dict(status='PASS' if state.get('container_id') else 'NOT_RUN',
            mode='container-kernel-limits; host-overhead-measured-only', flags=r.CONTAINER_FLAGS,
            host_overhead_allowance=OVERHEAD, measured=dict(control.peak), samples=control.samples),
        deadlines=dict(status='PASS' if time.time() < state['end_unix'] else 'FAIL', wall_seconds=t.WALL_SECONDS,
            uptime_seconds=t.UPTIME_SECONDS),
        disk=dict(status='PASS' if control.samples else 'NOT_RUN', peak_bytes=control.peak['disk_bytes'],
            abort_bytes=15*GiB, minimum_free_bytes=4*GiB, mode='sampled-abort-not-quota'),
        no_oom=dict(status='PASS' if no_oom else 'FAIL', generations=len(state.get('counters', []))))
    if receipt['result'] == 'INCOMPLETE':
        receipt['result'] = t.verdict(rows)
    receipt['rows'] = rows
    receipt['manager_generations'] = state['managers']
    write_private(args.out/STATE, state)
    r.publish_evidence(args.out, rows, receipt)
    print(json.dumps(dict(result=receipt['result'], public_launch=False)))
    return 0 if receipt['result'].startswith('PASS_') else 1


def observe(args, state, control, name, image):
    """Watch the container; plan the manager restart and the full cycle by exit code."""
    managers = state['managers']
    me = managers[-1]
    while True:
        c.require(time.time() < state['end_unix'], 'topology wall exhausted')
        keeper = state['keeper']
        c.require(alive(keeper) and lock_held_elsewhere(), 'heavy-lock keeper lost')
        control.sample()
        value = inspect(control, name, image, time.monotonic()+60)
        c.require(value is not None, 'owned container missing')
        beat = heartbeat(args.out)
        if value['State']['Running']:
            if (beat and beat['phase'] == 'steady' and beat['samples'] >= MANAGER_RESTART_AFTER_SAMPLES and
                    'manager_restart' not in state):
                state['manager_restart'] = dict(before=me['identity'], container_started=value['State']['StartedAt'],
                                                samples=beat['samples'])
                write_private(args.out/STATE, state)
                return RESTART
            time.sleep(30)
            continue
        code = value['State']['ExitCode']
        if code == 0 and beat and beat['phase'] == 'cycle' and 'cycle' not in state:
            state['cycle'] = dict(before=me['identity'], container_finished=value['State']['FinishedAt'])
            write_private(args.out/STATE, state)
            return CYCLE
        if code == 0 and beat and beat['phase'] == 'complete':
            return finish(args, state, control, name, image, None)
        return finish(args, state, control, name, image, 'native_exit')


def start(args):
    c.require(os.getsid(0) == os.getpid(), 'topology manager requires a detached session leader')
    c.require(re.fullmatch(r'[0-9a-f-]{36}', args.grant_comment) is not None and
              re.fullmatch('[0-9a-f]{64}', args.artifact_sha256) is not None, 'new exact grant and artifact digest')
    c.require(args.out.is_absolute() and args.out == args.out.resolve() and args.out.parent.is_dir() and
              not args.out.exists(), 'fresh absolute output root required')
    commit = subprocess.check_output(['git', '-C', str(n.ROOT), 'rev-parse', 'HEAD'], text=True, timeout=10).strip()
    c.require(not subprocess.check_output(['git', '-C', str(n.ROOT), 'status', '--porcelain'], text=True,
              timeout=10).strip(), 'commit exact candidate first')
    manifest = r.check_inputs(args.inputs)
    reuse = r.reuse_build(args.reuse_build, manifest)
    comment = json.loads(r.api('/api/issues/'+t.ISSUE+'/comments/'+args.grant_comment))
    c.require(comment['id'] == args.grant_comment, 'grant comment identity')
    runner = c.digest(Path(__file__).read_bytes())
    driver = c.digest((c.HERE/'integration/topology_driver.py').read_bytes())
    grant = grant_payload(comment, commit=commit, inputs_hash=c.digest(args.inputs.read_bytes()),
        artifact_hash=args.artifact_sha256, runner_hash=runner, driver_hash=driver, output=args.out,
        now=time.time(), reuse=reuse)
    c.require(c.digest(r.api('/api/attachments/'+grant['artifact_attachment_id']+'/content')) == args.artifact_sha256,
              'authenticated artifact digest mismatch')
    image = manifest['builder_image']
    first = r.admit(image, args.out.parent, grant)
    c.require(not lock_held_elsewhere(), 'heavy lock busy')
    n.fresh_directory(args.out)  # Durable one-use marker; a crash after this consumes the grant.
    end_unix = int(time.time())+t.WALL_SECONDS
    state = dict(schema='meownero-topology-manager/1', grant=args.grant_comment, commit=commit,
        runner_sha256=runner, driver_sha256=driver, end_unix=end_unix, managers=[], rows=t.empty_rows(),
        receipt=dict(schema='meownero-topology-attempt/1', result='INCOMPLETE', public_launch=False,
            launch_ready=False, grant=args.grant_comment, candidate_commit=commit, runner_sha256=runner,
            driver_sha256=driver, first_admission=first, exclusions={k: 'NOT_RUN' for k in t.EXCLUDED},
            build_reuse=dict(prior_attempt_root=str(reuse['root']), retained_build_sha256=reuse['manifest_sha256'])))
    holder = {}
    try:
        return launch(args, state, grant, reuse, image, end_unix, holder)
    except Exception as error:
        control = holder.get('control') or Manager(args.out, grant, time.monotonic(),
                                                   time.monotonic()+max(60, end_unix-time.time()))
        control.container_id = state.get('container_id')
        state['receipt']['failure_class'] = type(error).__name__
        return finish(args, state, control, state.get('name', 'meownero-topology-'+args.grant_comment),
                      image, 'manager_'+type(error).__name__)


def launch(args, state, grant, reuse, image, end_unix, holder):
    keeper = subprocess.Popen([sys.executable, '-I', '-B', str(Path(__file__).resolve()), 'keep-lock',
        '--out', str(args.out), '--until', str(end_unix+600)], start_new_session=True, close_fds=True,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        env=dict(PATH=os.environ['PATH'], LC_ALL='C'))
    deadline = time.time()+30
    while not (args.out/'keeper.json').exists() and keeper.poll() is None and time.time() < deadline:
        time.sleep(.2)
    record = read_private(args.out/'keeper.json')
    c.require(keeper.poll() is None and record['pid'] == identity(keeper.pid) and
              tuple((record['lock']['device'], record['lock']['inode'])) == g.LOCK_ID and lock_held_elsewhere(),
              'lock keeper did not take the original heavy lock')
    state['keeper'] = record['pid']
    state['receipt']['lock'] = record['lock']
    state['managers'].append(dict(identity=identity(os.getpid()), reason='start', unix=int(time.time())))
    write_private(args.out/STATE, state)
    control = holder['control'] = Manager(args.out, grant, time.monotonic(), time.monotonic()+(end_unix-time.time()))
    staging = args.out/'staging'
    staging.mkdir(mode=0o700)
    for sub in ('tmp', 'control'):
        (staging/sub).mkdir(mode=0o700)
    (args.out/'public').mkdir(mode=0o700)
    (args.out/'persistent').mkdir(mode=0o700)
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
    (staging/'control/end-unix').write_text(str(end_unix)+'\n')
    state['receipt']['second_admission'] = r.admit(image, args.out, grant)
    name = 'meownero-topology-'+args.grant_comment
    state['name'], state['image'] = name, image
    info = control.run(g.DOCKER+['image', 'inspect', image], time.monotonic()+30, monitor=False)
    c.require(json.loads(info.stdout)[0]['Id'] == image, 'local pinned image required')
    control.run(container_command(args.out, name, image), time.monotonic()+30)
    value = inspect(control, name, image, time.monotonic()+30)
    c.require(value is not None, 'created container missing')
    state['container_id'] = state['receipt']['container_id'] = value['Id']
    write_private(args.out/STATE, state)
    control.run(g.DOCKER+['start', value['Id']], time.monotonic()+30)
    write_private(args.out/STATE, state)
    return observe(args, state, control, name, image)


def resume(args):
    c.require(os.getsid(0) == os.getpid(), 'topology manager requires a detached session leader')
    state = read_private(args.out/STATE)
    commit = subprocess.check_output(['git', '-C', str(n.ROOT), 'rev-parse', 'HEAD'], text=True, timeout=10).strip()
    c.require(state['commit'] == commit and state['runner_sha256'] == c.digest(Path(__file__).read_bytes()) and
              state['driver_sha256'] == c.digest((c.HERE/'integration/topology_driver.py').read_bytes()),
              'resume requires the exact granted candidate')
    c.require(not (args.out/'evidence').exists(), 'attempt already finished')
    grant = dict(host_overhead_allowance=OVERHEAD)
    control = Manager(args.out, grant, time.monotonic(), time.monotonic()+(state['end_unix']-time.time()))
    control.container_id = state['container_id']
    name, image = state['name'], state['image']
    previous = state['managers'][-1]
    c.require(not alive(previous['identity']), 'previous manager still alive')
    me = dict(identity=identity(os.getpid()), unix=int(time.time()))
    if 'cycle' in state and 'cycle_resumed' not in state:
        value = inspect(control, name, image, time.monotonic()+60)
        c.require(value is not None and not value['State']['Running'] and value['State']['ExitCode'] == 0 and
                  value['State']['FinishedAt'] == state['cycle']['container_finished'], 'cycle container state')
        me['reason'] = 'full-cycle'
        state['managers'].append(me)
        control.run(g.DOCKER+['start', value['Id']], time.monotonic()+30)
        after = inspect(control, name, image, time.monotonic()+60)
        state['cycle_resumed'] = True
        state['rows']['persistence.json']['manager_cycle'] = dict(status='PASS', manager_changed=True,
            container_restarted=after['State']['StartedAt'] != value['State']['StartedAt'], same_container=True,
            keeper_unchanged=alive(state['keeper']))
    elif 'manager_restart' in state and 'manager_resumed' not in state:
        value = inspect(control, name, image, time.monotonic()+60)
        beat = heartbeat(args.out)
        continuous = (value is not None and value['State']['Running'] and
                      value['State']['StartedAt'] == state['manager_restart']['container_started'])
        me['reason'] = 'manager-only'
        state['managers'].append(me)
        state['manager_resumed'] = True
        state['rows']['persistence.json']['manager_restart'] = dict(status='PASS' if continuous and beat else 'FAIL',
            manager_changed=True, container_continuous=continuous, keeper_unchanged=alive(state['keeper']),
            heartbeat_samples_before=state['manager_restart']['samples'])
    else:
        raise ValueError('no planned manager restart is pending')
    write_private(args.out/STATE, state)
    try:
        return observe(args, state, control, name, image)
    except Exception as error:
        state['receipt']['failure_class'] = type(error).__name__
        return finish(args, state, control, name, image, 'manager_'+type(error).__name__)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    first = sub.add_parser('start')
    first.add_argument('--inputs', type=Path, default=c.HERE/'integration/inputs.json')
    first.add_argument('--grant-comment', required=True)
    first.add_argument('--artifact-sha256', required=True)
    first.add_argument('--reuse-build', type=Path, required=True)
    first.add_argument('--out', type=Path, required=True)
    again = sub.add_parser('resume')
    again.add_argument('--out', type=Path, required=True)
    keeper = sub.add_parser('keep-lock')
    keeper.add_argument('--out', type=Path, required=True)
    keeper.add_argument('--until', type=int, required=True)
    args = parser.parse_args()
    os.umask(0o077)
    if args.command == 'keep-lock':
        return keep_lock(args.out, args.until)
    return start(args) if args.command == 'start' else resume(args)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as error:
        print('REFUSED: '+type(error).__name__+': '+str(error)[:200], file=sys.stderr)
        raise SystemExit(3)
