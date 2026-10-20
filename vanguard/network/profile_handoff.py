"""Source-only outer/inner handoff. No qualified launcher is installed or supplied.

The empty implementation table is deliberate. A manifest edit or a consultation
cannot enable this runner. Adding an implementation requires a reviewed source
delta, Platform qualification, new hashes and a separately exact execution grant.
"""
import fcntl
import json
import math
import os
from pathlib import Path
import re
import stat

import profile_contract as c

QUALIFIED_BOOTSTRAPS = {}
MECHANISM = 'platform-rootful-cgroupfs-v2-fixed-ext4/2'


def require_bootstrap(manifest):
    sha = manifest.get('platform_bootstrap_sha256')
    c.require(sha is not None, 'Platform pre-admission enclosure bootstrap is not yet frozen')
    c.require(sha in QUALIFIED_BOOTSTRAPS, 'no qualified outer implementation for bootstrap hash')
    path = c.no_alias(QUALIFIED_BOOTSTRAPS[sha])
    c.require(c.digest(path.read_bytes()) == sha, 'actual launcher bytes differ')
    return path


def lock_witness(text, owner_pid):
    # Kernel proc documentation: locks associated with an FD appear in fdinfo.
    # A separate open without the inherited flock has no matching lock entry.
    major, minor = os.major(c.LOCK_ID[0]), os.minor(c.LOCK_ID[0])
    matches = []
    for line in text.splitlines():
        match = re.fullmatch(r'lock:\s+\d+: FLOCK\s+ADVISORY\s+WRITE\s+(\d+)\s+'
                             r'([0-9a-f]+):([0-9a-f]+):(\d+)\s+0\s+EOF', line)
        if match:
            pid, dev_major, dev_minor, inode = match.groups()
            if (int(pid), int(dev_major,16), int(dev_minor,16), int(inode)) == (
                    owner_pid, major, minor, c.LOCK_ID[1]):
                matches.append(match.group(0))
    c.require(len(matches) == 1, 'inherited exclusive original-lock witness missing')
    return matches[0]


def validate_context(value, ledger, *, bindings, now):
    c.require(value['schema'] == 'meownero-private-handoff/2', 'handoff schema')
    c.require(value['bindings'] == bindings and ledger['bindings'] == bindings, 'handoff binding mismatch')
    c.require(ledger['schema'] == 'meownero-consumed-ledger/2' and ledger['state'] == 'CONSUMED',
              'existing CONSUMED receipt required')
    c.require(value['ledger']['sha256'] == c.digest(c.canonical(ledger)), 'ledger receipt digest')
    origin, consumed, provisioned = [value[key] for key in ('origin','consumed_at','provisioned_at')]
    first = value['first_admission']
    times = [origin, first['at'], consumed, provisioned, now]
    c.require(all(type(t) in (int,float) and math.isfinite(t) for t in times), 'invalid monotonic times')
    c.require(origin <= first['at'] <= consumed <= provisioned <= now < origin+3600,
              'admission/consumption/provisioning order or build deadline')
    c.require(consumed-first['at'] <= 5, 'stale first admission')
    c.admit(first['snapshot'])
    c.require(ledger['origin'] == origin and ledger['consumed_at'] == consumed, 'ledger time binding')
    c.require(value['deadlines'] == dict(build=origin+3600,work=origin+4200,end=origin+4500),
              'phase deadlines or cleanup reserve changed')
    c.require(value['enclosure']['mechanism'] == MECHANISM and
              value['enclosure']['daemon_mode'] == 'platform-authorized-rootful-cgroupfs',
              'rootless/systemd is not this proposed interface')
    c.require(value['recovery']['owner'] == c.PLATFORM and
              value['recovery']['implementation_sha256'] == bindings['bootstrap_sha256'],
              'independent recovery implementation binding')
    parent = value['enclosure']['cgroup_parent']
    c.require(parent.startswith('/') and parent != '/' and '..' not in Path(parent).parts and
              value['enclosure']['workload_cgroup'] == parent+'/work', 'owned workload subtree')
    c.require(value['recovery']['kill_scope'] == value['enclosure']['workload_cgroup'] and
              value['enclosure']['cgroup_parent'] != value['recovery']['kill_scope'],
              'emergency kill must preserve recovery sibling')
    return value


def read_inherited(context_fd, lock_fd, ledger_fd, *, bindings, now, identity):
    c.require(len({context_fd,lock_fd,ledger_fd}) == 3 and
              all(type(fd) is int and fd > 2 for fd in (context_fd,lock_fd,ledger_fd)), 'distinct inherited FDs')
    seals = fcntl.F_SEAL_SEAL | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_GROW | fcntl.F_SEAL_WRITE
    c.require(fcntl.fcntl(context_fd,fcntl.F_GET_SEALS) & seals == seals, 'context must be sealed')
    def read(fd):
        info = os.fstat(fd)
        c.require(stat.S_ISREG(info.st_mode) and 0 < info.st_size <= 1024*1024 and
                  info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o600,
                  'private bounded regular descriptor')
        return json.loads(os.pread(fd,info.st_size,0))
    value,ledger = read(context_fd),read(ledger_fd)
    validate_context(value,ledger,bindings=bindings,now=now)
    info = os.fstat(ledger_fd)
    c.require((info.st_dev,info.st_ino) == tuple(value['ledger']['identity']) and
              info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1,
              'durable ledger descriptor identity/owner/mode')
    c.require(fcntl.fcntl(ledger_fd,fcntl.F_GETFL) & os.O_ACCMODE == os.O_RDONLY, 'ledger must be read-only')
    c.check_lock(os.fstat(lock_fd),os.getuid())
    c.check_lock(os.stat(c.LOCK,follow_symlinks=False),os.getuid())
    outer = value['outer']
    c.stop_identity(outer['pid_identity'],identity(outer['pid_identity'][0]))
    pid = outer['pid_identity'][0]
    own = lock_witness(Path(f'/proc/self/fdinfo/{lock_fd}').read_text(),pid)
    held = lock_witness(Path(f'/proc/{pid}/fdinfo/{outer["lock_fd"]}').read_text(),pid)
    c.require(own == held, 'supervisor retained lock description differs')
    c.require(c.digest(c.no_alias(outer['launcher_path']).read_bytes()) == bindings['bootstrap_sha256'],
              'live launcher file bytes differ')
    # Never flock, recreate the ledger, unlock, or pass these FDs to workload children.
    for fd in (context_fd,lock_fd,ledger_fd): os.set_inheritable(fd,False)
    return value


def inner_rows(rows):
    # Only the qualified outer, after this process exits, can finalize these rows.
    for name in ('resources.json','cleanup.json'):
        rows[name] = {key:dict(status='NOT_RUN') for key in c.REQUIRED[name]}
    return rows


def validate_completion(value, bindings):
    """Validate proposed outer evidence shape, never attest its host observations.

    The unimplemented qualified manager must collect these after recovery exit.
    A passing modeled receipt is not accepted as runtime evidence by this runner.
    """
    c.require(value['schema'] == 'meownero-outer-completion/2' and value['bindings'] == bindings,
              'outer completion binding')
    c.require(value['original_lock_identity'] == list(c.LOCK_ID), 'final original-inode identity')
    c.require(value['observer']['outside_attempt'] is True and
              value['observer']['pid_identity'] not in value['tracked_pid_identities'],
              'completion observer must survive the attempt')
    c.require(value['origin'] <= value['recovery_exit_at'] <= value['observed_at'] <= value['origin']+4500,
              'completion must follow recovery exit within total deadline')
    c.require(0 <= value['aggregate_cpu_usec'] <= 9000*1000000, 'final aggregate CPU budget')
    c.require(value['recursive_population'] == {'work':0,'recovery':0} and
              value['active_controllers'] == ['cpu','memory','pids'], 'final population/controllers')
    for key in ('live_owned_pid_identities','remaining_cids','remaining_mounts','remaining_loops',
                'remaining_daemon_helpers','active_owned_units','open_lock_descriptors'):
        c.require(value[key] == [], 'owned cleanup incomplete: '+key)
    c.require(value['original_lock_release_witness'] == 'independent_nonblocking_acquire_then_close',
              'independent final lock release witness absent')
    for name in ('resources.json','cleanup.json'):
        c.require(set(value['rows'][name]) == set(c.REQUIRED[name]) and
                  all(row['status'] == 'PASS' for row in value['rows'][name].values()),
                  'outer resource/cleanup witness incomplete')
    return value
