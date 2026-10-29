"""Outer lifecycle source; no host manager adapter has been qualified.

Only the installed, independently surviving manager may implement Manager below.
Tests supply an in-memory manager and disposable files. Nothing in this module
discovers privileges, provisions a host, or turns a JSON binding into authority.
"""
import fcntl
import math
import os
from pathlib import Path
import re
import stat
import time
from typing import Protocol

import profile_contract as c
import profile_handoff as h

CAPABILITIES = ('manager', 'fixed_disk', 'offline_image', 'second_admission')
SEALS = fcntl.F_SEAL_SEAL | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_GROW | fcntl.F_SEAL_WRITE


class Manager(Protocol):
    """Unavailable host boundary, not an installed adapter.

    Every call has an absolute deadline enforced independently of this process.
    retain duplicates the SAME lock description before acknowledging custody,
    arms crash/OOM/timeout recovery and post-exit observation, and accounts for
    its own bounded overhead. A lost acknowledgement cannot discard custody.
    provision contains ALL setup, image import and later task writes/processes.
    run_controller uses only inherited descriptors, services the private second
    admission callback immediately before create, and enforces all phase limits.
    recover handles partial setup too; failures retain manager lock custody.
    complete_after_exit queues final observation AFTER this launcher exits. It
    must not release custody while descendants, mounts or cleanup are unresolved.
    """
    def retain(self, lock_fd, bindings, deadlines, *, deadline): ...
    def admit(self, number, *, deadline): ...
    def quarantine(self, bindings, *, deadline): ...
    def provision(self, ledger_fd, *, deadline): ...
    def run_controller(self, context_fd, lock_fd, ledger_fd, second_admission, *, deadlines): ...
    def recover(self, *, deadline): ...
    def complete_after_exit(self, result, *, deadline): ...


def capability_check(value):
    c.require(value['schema'] == 'meownero-outer-capabilities/1', 'capability schema')
    c.require(set(value['capabilities']) == set(CAPABILITIES), 'four named capabilities required')
    missing = [name for name in CAPABILITIES if value['capabilities'][name] is None]
    return dict(result='REFUSED_UNBOUND_CAPABILITIES' if missing else 'UNQUALIFIED_BINDINGS_ONLY',
                missing=missing, native_execution='NOT_RUN', launch_ready=False)


def require_runtime(manifest, capabilities):
    check = capability_check(capabilities)
    c.require(not check['missing'], 'unbound capabilities: '+', '.join(check['missing']))
    # Even four nonnull objects cannot authorize any operation. The independent
    # source qualification table is deliberately empty in this candidate.
    return h.require_bootstrap(manifest)


def check_original(fd, *, held=True):
    info = os.fstat(fd)
    c.check_lock(info, os.getuid())
    c.require(info.st_nlink == 1, 'original lock link count')
    c.check_lock(os.stat(c.LOCK, follow_symlinks=False), os.getuid())
    if held:
        h.lock_witness(Path(f'/proc/self/fdinfo/{fd}').read_text(), os.getpid())


def acquire_original():
    """Future grant-only operation. Never create, truncate, unlink or unlock."""
    fd = os.open(c.LOCK, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        check_original(fd, held=False)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        check_original(fd)
        return fd
    except BaseException:
        os.close(fd)
        raise


def write_all(fd, raw):
    view = memoryview(raw)
    while view:
        written = os.write(fd, view)
        c.require(written > 0, 'short durable write')
        view = view[written:]


def consume(directory, bindings, origin, consumed_at):
    """Durable one-use receipt. Keep any partial file forever; never retry it.

    The pre-existing private ledger directory and its bounded storage allocation
    belong to the qualified manager. This function creates no directories.
    """
    grant_id = bindings['grant_id']
    c.require(bool(re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', grant_id))
              and grant_id not in c.CONSUMED, 'new exact ledger grant id required')
    directory = c.no_alias(directory)
    parent = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    fd = readonly = None
    try:
        info = os.fstat(parent)
        c.require(info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700,
                  'private ledger directory owner/mode')
        name = grant_id+'.json'
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                     0o600, dir_fd=parent)
        value = dict(schema='meownero-consumed-ledger/2', state='CONSUMED', bindings=bindings,
                     origin=origin, consumed_at=consumed_at)
        write_all(fd, c.canonical(value))
        os.fsync(fd)
        os.fsync(parent)
        readonly = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
        written, read = os.fstat(fd), os.fstat(readonly)
        c.require((written.st_dev, written.st_ino) == (read.st_dev, read.st_ino)
                  and read.st_nlink == 1 and stat.S_IMODE(read.st_mode) == 0o600
                  and read.st_uid == os.getuid(), 'durable ledger identity changed')
        c.require(os.pread(readonly, read.st_size, 0) == c.canonical(value), 'durable ledger bytes changed')
        result, readonly = readonly, None
        return result, value
    finally:
        for item in (fd, readonly, parent):
            if item is not None:
                os.close(item)


def sealed_context(value):
    fd = os.memfd_create('meownero-private-context', os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
    try:
        os.fchmod(fd, 0o600)
        raw = c.canonical(value)
        c.require(0 < len(raw) <= 1024*1024, 'bounded private context required')
        write_all(fd, raw)
        fcntl.fcntl(fd, fcntl.F_ADD_SEALS, SEALS)
        return fd
    except BaseException:
        os.close(fd)
        raise


class Outer:
    """Manager-hosted launcher core; access only after qualification and grant.

    This core deliberately cannot construct a Manager. The CLI never reaches
    it while capabilities or the qualified bootstrap are absent. An adapter
    added later must authenticate source/artifact/grant and independent review
    receipts before calling it. Source fixtures are not such authorization.
    """
    def __init__(self, manager: Manager, *, clock=time.monotonic):
        self.manager, self.clock = manager, clock

    def run(self, bindings, ledger_directory):
        origin = self.clock()
        c.require(type(origin) in (int, float) and math.isfinite(origin), 'finite monotonic origin')
        deadlines = dict(build=origin+3600, work=origin+4200, end=origin+4500)
        lock_fd = acquire_original()
        ledger_fd = context_fd = None
        retained = False
        result = dict(result='REFUSED_BEFORE_ATTEMPT', native_execution='NOT_RUN', launch_ready=False,
                      bindings=bindings, rows=c.empty_rows(), manager_completion='NOT_RUN')
        try:
            # No provisioning or ledger creation before independent custody and
            # first admission. The manager must already be authorized/available.
            self.manager.retain(lock_fd, bindings, deadlines, deadline=deadlines['build'])
            retained = True
            check_original(lock_fd)
            first = self.fresh_admission(1, lock_fd, origin, deadlines['build'])
            consumed_at = self.clock()
            c.require(first['at'] <= consumed_at <= first['at']+5, 'stale first admission at consumption')
            # Includes partial file/fsync failure: the attempt never resumes.
            result['result'] = 'FAIL'
            # Persist the independent manager's failed-grant obligation BEFORE
            # local consumption can be uncertain. Missing/corrupt local ledgers
            # can never restore eligibility. A restart may only recover/observe.
            quarantine = self.manager.quarantine(bindings, deadline=min(deadlines['build'], first['at']+5))
            c.require(quarantine['state'] == 'QUARANTINED' and
                      bool(re.fullmatch('[0-9a-f]{64}', quarantine['sha256'])),
                      'independent durable manager quarantine required')
            c.require(self.clock() <= first['at']+5, 'first admission expired during manager quarantine')
            ledger_fd, ledger = consume(ledger_directory, bindings, origin, consumed_at)
            c.require(self.clock() <= first['at']+5, 'first admission expired during durable consumption')
            enclosure = self.manager.provision(ledger_fd, deadline=deadlines['build'])
            check_original(lock_fd)
            provisioned = self.clock()
            context = dict(schema='meownero-private-handoff/2', bindings=bindings,
                origin=origin, consumed_at=consumed_at, provisioned_at=provisioned,
                first_admission=first, deadlines=deadlines,
                ledger=dict(identity=list((os.fstat(ledger_fd).st_dev, os.fstat(ledger_fd).st_ino)),
                            sha256=c.digest(c.canonical(ledger))), **enclosure)
            h.validate_context(context, ledger, bindings=bindings, now=provisioned)
            context_fd = sealed_context(context)
            second = []

            def admit_second():
                c.require(not second, 'second admission is one-shot; no polling or retry')
                second.append(None)  # A failed observation also consumes the request.
                observation = self.fresh_admission(2, lock_fd, origin, deadlines['build'])
                second[0] = observation
                return observation

            # The qualified manager must bind this callback to the private
            # pre-create channel. The existing inner still refuses that channel.
            outcome = self.manager.run_controller(context_fd, lock_fd, ledger_fd, admit_second,
                                                  deadlines=deadlines)
            c.require(len(second) == 1 and second[0] is not None, 'second fresh admission missing')
            c.require(self.clock() <= deadlines['work'], 'work timeout; cleanup reserve retained')
            c.require(outcome['exit_code'] == 0, 'controller failed')
            rows = h.inner_rows(outcome['rows'])
            result.update(result='PENDING_MANAGER_COMPLETION', rows=rows,
                          native_execution='UNACCEPTED_CONTROLLER_OUTPUT', second_admission=second[0])
        except Exception as error:
            # Error messages may contain credentials or raw process output.
            result['failure_class'] = type(error).__name__
        finally:
            # SIGKILL/OOM cannot run finally. retain's independent watchdog must
            # perform this SAME recovery, using its own retained lock description.
            try:
                if retained:
                    try:
                        c.require(self.clock() < deadlines['end'], 'cleanup deadline exhausted')
                        self.manager.recover(deadline=deadlines['end'])
                        c.require(self.clock() <= deadlines['end'], 'cleanup exceeded deadline')
                        check_original(lock_fd)
                    except Exception as error:
                        result.update(result='FAIL', recovery_failure_class=type(error).__name__)
                    try:
                        self.manager.complete_after_exit(result, deadline=deadlines['end'])
                        result['manager_completion'] = 'PENDING_INDEPENDENT_POST_EXIT_OBSERVATION'
                    except Exception as error:
                        result.update(result='FAIL', completion_failure_class=type(error).__name__)
            finally:
                # Even interruption of recovery closes local copies. The manager
                # must still retain its independent copy and watchdog obligation.
                for fd in (context_fd, ledger_fd, lock_fd):
                    if fd is not None:
                        os.close(fd)
        # This result cannot establish its own death, lock release, or cleanup.
        # Only a separately observed validate_completion receipt may do so.
        return result

    def fresh_admission(self, number, lock_fd, origin, deadline):
        before = self.clock()
        c.require(origin <= before < deadline, 'admission deadline exhausted')
        check_original(lock_fd)
        value = self.manager.admit(number, deadline=deadline)
        after = self.clock()
        at = value['at']
        c.require(type(at) in (int, float) and math.isfinite(at)
                  and before <= at <= after < deadline and after-at <= 5,
                  'fresh attempt-bound admission required')
        c.admit(value['snapshot'])
        check_original(lock_fd)
        return value
