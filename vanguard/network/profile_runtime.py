"""Source implementations behind an independently authenticated OS boundary.

Disposable-file tests exercise durable burns and write-ahead reservations. These
objects cannot confine an external process or establish installed crash survival.
The qualified boundary must mediate every writer and survive the keeper.
"""
import fcntl
import math
import os
import re
import stat
import time

import profile_contract as c
import profile_manager as m
import profile_packet as p


class CapabilityStore:
    """Burn an existing operator-reserved slot; never create/repair/rearm it.

    Separate opens serialize competing processes. A role/attempt/source-bound
    live secret is required as well as RESERVED bytes. A recovered custodian
    has no activation authority even if a crash left RESERVED on disk.
    """
    def __init__(self, directory_fd, identities, *, owner_uid=0, recovered=False):
        info=os.fstat(directory_fd)
        c.require(stat.S_ISDIR(info.st_mode) and info.st_uid==owner_uid and
            stat.S_IMODE(info.st_mode)==0o700, 'private custodian slot directory')
        self.directory_fd,self.identities,self.owner_uid=directory_fd,identities,owner_uid
        self.recovered=recovered
        self.used=set()

    def consume(self, name, expected, secret, *, deadline, clock=time.monotonic):
        c.require(name in self.identities and re.fullmatch('[a-z][a-z0-9-]{0,63}',name), 'reserved role slot only')
        c.require(expected.get('role')==name, 'capability slot is bound to its exact role')
        c.require(not self.recovered and name not in self.used, 'recovery or uncertain burn never reauthorizes')
        self.used.add(name)  # Any uncertainty poisons this instance before file IO.
        fd=os.open(name,os.O_RDWR|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK,dir_fd=self.directory_fd)
        try:
            info=os.fstat(fd)
            c.require([info.st_dev,info.st_ino]==self.identities[name] and info.st_gid==self.owner_uid,
                'original operator-reserved slot identity')
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            journal=m.GrantJournal(fd,expected,owner_uid=self.owner_uid)
            return journal.quarantine(expected['bindings'],activation=secret,deadline=deadline,clock=clock)
        finally:os.close(fd)


class WriteMeter:
    """Reserve worst-case writes BEFORE a mediated operation; never refund.

    Cumulative writes and occupied capacities are independent. All reservations,
    including failed/partial operations, remain charged. The durable boundary
    must commit the reservation before permitting the writer to proceed.
    """
    def __init__(self, *, phase, persist, recovered=None):
        c.require(phase in ('preparation','runtime'), 'fixed meter phase')
        self.phase,self.persist=phase,persist
        self.writes={key:0 for key in p.ALLOCATION}
        self.occupied={key:0 for key in p.ALLOCATION}
        self.failed=False
        if recovered is not None:
            c.require(recovered['phase']==phase and set(recovered['writes'])==set(self.writes) and
                set(recovered['occupied'])==set(self.occupied), 'complete persistent meter')
            self.writes=dict(recovered['writes']);self.occupied=dict(recovered['occupied'])
            self.failed=recovered['failed']
            self._check()

    def _check(self):
        c.require(type(self.failed) is bool and all(type(n) is int and n>=0 for n in
            [*self.writes.values(),*self.occupied.values()]), 'nonnegative integral counters')
        caps=p.ALLOCATION
        c.require(all(self.occupied[k]<=caps[k] for k in caps) and
            sum(self.occupied.values())<=15*p.GIB, 'hard occupied allocation')
        if self.phase=='preparation':
            limits=dict(control=p.PREPARATION['control']['writes'],workload=0,
                archive=p.PREPARATION['archive']['writes'],other=p.PREPARATION['other_writes'])
            c.require(all(self.writes[k]<=limits[k] for k in limits) and
                sum(self.writes.values())<=p.PREPARATION['writes'] and
                sum(self.occupied.values())<=p.PREPARATION['occupied'], 'preparation write/occupied ceiling')
        else:
            c.require(sum(self.writes.values())<=15*p.GIB, 'runtime cumulative writes ceiling')

    def snapshot(self):
        return dict(phase=self.phase,writes=dict(self.writes),occupied=dict(self.occupied),failed=self.failed)

    def reserve(self, area, maximum_written, occupied_after):
        c.require(not self.failed and area in self.writes and type(maximum_written) is int and
            maximum_written>=0 and type(occupied_after) is int and occupied_after>=0,
            'usable meter and bounded reservation')
        self.failed=True
        self.writes[area]+=maximum_written
        self.occupied[area]=occupied_after
        try:
            self._check()
            # A durable, independently surviving implementation is required.
            self.persist({**self.snapshot(),'failed':False})
        except BaseException:
            # No IO may begin after failed accounting. Never roll back charges.
            raise
        self.failed=False
        return self.snapshot()


class AbsoluteDeadlines:
    """Independent-owner loop over original CLOCK_MONOTONIC deadlines.

    Instantiation/arming happens in the separate deadline unit, not the keeper.
    Losing that unit or boot identity invalidates qualification, never resets
    origin. The supplied actions target only the exact workload unit.
    """
    def __init__(self, origin, boot_id, *, clock=time.monotonic):
        c.require(type(origin) in (int,float) and math.isfinite(origin) and origin>=0 and
            type(boot_id) is str and bool(boot_id), 'original clock/boot binding')
        self.origin,self.boot_id,self.clock=origin,boot_id,clock
        self.deadlines=dict(build=origin+3600,work=origin+4200,end=origin+4500)

    def check_boot(self, observed):c.require(observed==self.boot_id, 'reboot is failed recovery, never a fresh origin')

    def enforce(self, actions, wait_until, *, observed_boot):
        self.check_boot(observed_boot)
        c.require(set(actions)==set(self.deadlines), 'complete independent deadline actions')
        for phase,at in self.deadlines.items():
            if self.clock()<at:wait_until(at)
            c.require(self.clock()>=at, 'early/spurious deadline wait')
            actions[phase](at)  # Original absolute time, including on late restart.


class ObserverTail:
    """External owner completes only after exact observer exit and tail charge."""
    def __init__(self, contract, observer_identity, meter, *, clock=time.monotonic):
        self.contract,self.identity,self.meter,self.clock=contract,observer_identity,meter,clock
        self.finished=False

    def finish(self, pending, *, observe_exit, final_tail):
        c.require(not self.finished, 'one final observer completion')
        self.finished=True
        c.require(pending==dict(result='PENDING_OBSERVER_EXIT',contract_sha256=c.digest(c.canonical(self.contract)),
            observer_identity=self.identity), 'exact pending observer contract/identity')
        exit=observe_exit(self.identity,self.contract['deadlines']['end'])
        c.require(exit==dict(identity=self.identity,exited=True,reaped=True,status=0), 'independently witnessed exact observer exit')
        tail=final_tail()  # Independently measured after observer/recovery exit.
        c.require(set(tail)=={'written','occupied','cpu_seconds','memory_bytes','pids','all_workers_exited'} and
            type(tail['cpu_seconds']) in (int,float) and math.isfinite(tail['cpu_seconds']) and
            0<=tail['cpu_seconds']<=c.LIMITS['cpu_seconds'] and
            type(tail['memory_bytes']) is int and 0<=tail['memory_bytes']<=c.LIMITS['memory_bytes'] and
            type(tail['pids']) is int and 0<=tail['pids']<=c.LIMITS['pids'] and
            tail['all_workers_exited'] is True, 'complete bounded post-exit tail')
        self.meter.reserve('control',tail['written'],tail['occupied'])
        c.require(self.clock()<=self.contract['deadlines']['end'], 'observer tail exceeded original end')
        return dict(result='SOURCE_TAIL_ACCOUNTED',host_cleanup='NOT_RUN',native_execution='NOT_RUN')
