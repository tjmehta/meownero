"""Selected rootful manager adapter, SOURCE ONLY and not a qualified bootstrap.

The private helper endpoint and systemd FD store are operator bindings, not
discovered privileges. No import or constructor opens the original heavy lock.
Disposable tests exercise real descriptor, journal and socket operations only.
"""
import array
import fcntl
import json
import math
import os
from pathlib import Path
import select
import socket
import stat
import struct
import time

import profile_contract as c
import profile_outer as outer

MAX_PACKET = 65536
CREDENTIAL = struct.Struct('3i')
IMAGE = 'sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e'
AUTHORIZATION = 'a5ec64fd-3da7-4044-8863-795ef7a6541f'


def private_pair():
    """Only inherited unnamed endpoints; no pathname or abstract listener."""
    pair = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC)
    for endpoint in pair:
        endpoint.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
    return pair


def send_packet(endpoint, value, fds=(), *, deadline=None, clock=time.monotonic):
    raw = c.canonical(value)
    c.require(0 < len(raw) <= MAX_PACKET and len(fds) <= 4, 'bounded helper packet')
    if deadline is not None:
        c.require(deadline > clock(), 'helper send deadline')
        endpoint.settimeout(deadline-clock())
    ancillary = [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', fds))] if fds else []
    c.require(endpoint.sendmsg([raw], ancillary) == len(raw), 'short helper packet')


def receive_packet(endpoint, expected_credentials, deadline, *, fd_count=0, clock=time.monotonic):
    """SCM_CREDENTIALS authenticates the sender of this packet after fork.

    SO_PEERCRED on a pre-fork socketpair would identify its creator, not the
    process sending this message. Start identity is additionally checked by
    the manager before each request. Reject unsolicited FDs and truncation.
    """
    remaining = deadline-clock()
    c.require(remaining > 0 and select.select([endpoint], [], [], remaining)[0], 'helper deadline')
    raw, ancillary, flags, _ = endpoint.recvmsg(MAX_PACKET, socket.CMSG_SPACE(16)+socket.CMSG_SPACE(16),
                                               socket.MSG_CMSG_CLOEXEC)
    received, credentials = [], []
    try:
        rights_count=0;invalid_ancillary=False
        for level, kind, data in ancillary:
            if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                rights_count+=1
                rights = array.array('i')
                rights.frombytes(data[:len(data)-len(data) % rights.itemsize])
                received.extend(rights)
                invalid_ancillary |= len(data)%rights.itemsize != 0
            elif level == socket.SOL_SOCKET and kind == socket.SCM_CREDENTIALS:
                if len(data)==CREDENTIAL.size:credentials.append(CREDENTIAL.unpack(data))
                else:invalid_ancillary=True
            else:
                invalid_ancillary=True
        # Collect every installed FD before rejecting any ancillary item.
        c.require(not invalid_ancillary and rights_count==(1 if fd_count else 0), 'exact ancillary records')
        c.require(not flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC), 'truncated helper packet')
        c.require(credentials == [tuple(expected_credentials)] and len(received) == fd_count,
                  'helper peer or descriptor count differs')
        c.require(0 < len(raw) <= MAX_PACKET and clock() < deadline, 'expired or empty helper reply')
        value = json.loads(raw)
        c.require(type(value) is dict and c.canonical(value) == raw, 'canonical helper object required')
        result, received = (value, tuple(received)), []
        return result
    finally:
        for fd in received:
            os.close(fd)


class GrantJournal:
    """Existing manager-owned per-attempt slot, independent of local ledger.

    The operator reserves this grant irrevocably BEFORE activation, inside the
    fixed filesystem. This code cannot create/rearm/repair a slot. A recovered
    manager can recover/observe only; RESERVED on disk is never restart authority.
    A fresh activation needs the operator's private live one-use channel as well
    as this exact reserved slot. Missing/corrupt state poisons the whole attempt.
    """
    def __init__(self, fd, expected, *, recovered=False, owner_uid=0):
        self.fd, self.expected, self.recovered = fd, expected, recovered
        self.used = False
        info = os.fstat(fd)
        c.require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and
                  info.st_uid == owner_uid and stat.S_IMODE(info.st_mode) == 0o600 and
                  0 < info.st_size <= 4096, 'private reserved manager slot required')
        c.require(fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE == os.O_RDWR, 'writable manager slot')
        value = json.loads(os.pread(fd, info.st_size, 0))
        c.require(value == dict(schema='meownero-manager-slot/1', state='RESERVED', **expected),
                  'manager reservation missing, spent or corrupt')

    def quarantine(self, bindings, *, activation, deadline, clock=time.monotonic):
        c.require(not self.used and not self.recovered, 'manager restart never reauthorizes a grant')
        self.used = True  # Errors, including activation loss and fsync failure, burn this instance.
        c.require(type(activation) is bytes and len(activation) == 32 and
                  c.digest(activation) == self.expected['activation_sha256'] and
                  bindings == self.expected['bindings'] and clock() < deadline,
                  'fresh private activation and exact reservation required')
        value = dict(schema='meownero-manager-slot/1', state='QUARANTINED', **self.expected)
        raw = c.canonical(value)
        # No truncate/recreate, rename or directory-entry durability window here.
        # An interrupted overwrite produces invalid or QUARANTINED state, both
        # refused; operator reservation and recovery-only restart close rollback.
        os.lseek(self.fd, 0, os.SEEK_SET)
        outer.write_all(self.fd, raw)
        os.ftruncate(self.fd, len(raw))
        os.fsync(self.fd)
        c.require(os.pread(self.fd, len(raw)+1, 0) == raw and clock() < deadline,
                  'manager quarantine not durable within admission lifetime')
        return dict(state='QUARANTINED', sha256=c.digest(raw),
                    identity=list((os.fstat(self.fd).st_dev, os.fstat(self.fd).st_ino)))


def store_custody(endpoint, lock_fd, namespace_fd, *, deadline, readback, clock=time.monotonic):
    """systemd notify FDSTORE plus processing barrier. Not a custody witness.

    The root helper must separately inspect the actual PID1 descriptor and
    verify the same flock witness before returning a retain acknowledgement.
    A processed notification alone does not prove that FDSTORE accepted it.
    """
    c.require(deadline > clock(), 'FD-store send deadline')
    endpoint.settimeout(deadline-clock())
    for name,fd in (('original-lock',lock_fd),('mount-namespace',namespace_fd)):
        endpoint.sendmsg([('FDSTORE=1\nFDNAME='+name+'\nFDPOLL=0').encode()],
            [(socket.SOL_SOCKET,socket.SCM_RIGHTS,array.array('i',[fd]))])
    read_fd, write_fd = os.pipe2(os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        endpoint.sendmsg([b'BARRIER=1'],
                         [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', [write_fd]))])
        os.close(write_fd)
        write_fd = None
        remaining = deadline-clock()
        c.require(remaining > 0 and select.select([read_fd], [], [], remaining)[0],
                  'FD-store barrier timeout; retain custody')
        c.require(os.read(read_fd, 1) == b'', 'invalid FD-store barrier')
    finally:
        os.close(read_fd)
        if write_fd is not None:
            os.close(write_fd)

    # A barrier acknowledges processing only. The independently authenticated
    # readback must establish both stored identities and the same flock OFD.
    witness=readback(lock_fd,namespace_fd,deadline)
    c.require(witness['same_open_description'] is True and witness['namespace_retained'] is True,
              'PID1 custody readback missing')
    return witness


def store_lock(endpoint,lock_fd,*,deadline,clock=time.monotonic):
    raise ValueError('two named FDs and independent custody readback required')


class AdmissionGate:
    """Helper-side one-use admission AND create, in the same owning process.

    No transferable admission token is returned for later independent create.
    The exact create argv is frozen and hashed before observing resources. This
    avoids image inspection, hashing, or IPC work between the check and create.
    """
    def __init__(self, binding, *, clock=time.monotonic):
        self.binding, self.clock, self.used = binding, clock, False

    def create(self, request, *, check_peer, check_lock, observe, create):
        c.require(not self.used, 'second admission already consumed')
        self.used = True
        c.require(request == self.binding, 'second admission binding differs')
        check_peer()
        check_lock()
        before = self.clock()
        c.require(before < request['build_deadline'], 'build deadline before observation')
        observed = observe()
        after = self.clock()
        at, started = observed['at'], observed['started_at']
        c.require(all(type(x) in (int, float) and math.isfinite(x) for x in (before, after, at, started)) and
                  before <= started <= at <= after <= started+5 and after < request['build_deadline'],
                  'stale complete second admission')
        c.admit(observed['snapshot'])
        c.require(observed['original_lock'] == list(c.LOCK_ID) and
                  observed['bindings'] == request['bindings'] and
                  observed['ledger_sha256'] == request['ledger_sha256'] and
                  observed['attempt_id'] == request['attempt_id'] and
                  observed['original_lock_witness_sha256'] == request['original_lock_witness_sha256'] and
                  observed['create_sha256'] == request['create_sha256'], 'admission witness differs')
        check_lock()
        check_peer()
        c.require(self.clock() <= started+5 and self.clock() < request['build_deadline'],
                  'admission expired before create')
        # create is the helper's prevalidated exact operation, never supplied
        # executable text from the packet. A failed create still consumes it.
        # Ownership is recorded even when create returns late or raises after
        # creating a container. The caller's backend must persist its CID intent
        # before sending create, and retain ambiguous outcomes for recovery.
        self.create_started = True
        self.container_id = None
        self.uncertain = True
        cid = create()
        self.container_id = cid
        completed = self.clock()
        c.require(type(cid) is str and len(cid) == 64 and
                  all(x in '0123456789abcdef' for x in cid), 'exact owned CID')
        c.require(completed < self.binding['build_deadline'] and
                  completed <= started+5, 'create completion exceeded freshness/deadline')
        self.uncertain = False
        return dict(observation=observed, container_id=cid, completed_at=completed,
                    create_sha256=self.binding['create_sha256'])


class RootfulManager:
    """Compatibility name for the single v3 outer/helper protocol."""
    def __new__(cls,*args,**kwargs):
        from profile_dispatch import OuterManager
        return OuterManager(*args,**kwargs)


def source_status():
    return dict(schema='meownero-selected-manager-source/1', authorization_comment=AUTHORIZATION,
                source_only=True, platform_bootstrap_sha256=None, native_execution='NOT_RUN',
                host_activation='UNAVAILABLE', launch_ready=False,
                required_bindings=['privileged_operator', 'systemd_custody_readback',
                    'private_fixed_ext4', 'reserved_manager_slot', 'immutable_offline_image',
                    'qualified_OS_adapter_and_real_lifecycle_facilities'])
