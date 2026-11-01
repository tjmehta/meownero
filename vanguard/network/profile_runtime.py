"""Source implementations behind an independently authenticated OS boundary.

Disposable-file tests exercise durable burns and write-ahead reservations. These
objects cannot confine an external process or establish installed crash survival.
The qualified boundary must mediate every writer and survive the keeper.
"""
import fcntl
import copy
import json
import math
import os
import re
import stat
import time

import profile_contract as c
import profile_manager as m
import profile_packet as p
import profile_outer as outer


def reserve_record_state(directory_fd,binding,itinerary,recovery,secret,*,owner_uid=0):
    """Prefix-only creation of original order and every role slot, never repair.

    Partial creation is retained on failure. A repeated prefix cannot overwrite
    or reserve any object again. The directory must already be independently
    owned, accounted and under original custody before this operation.
    """
    c.require(type(secret) is bytes and len(secret)==32 and itinerary and len(itinerary)<=55 and
        len(set(itinerary))==len(itinerary) and set(recovery)<=set(itinerary) and
        all(type(n) is int and 0<=n<54 for n in itinerary), 'bounded original activation/recovery route')
    info=os.fstat(directory_fd)
    c.require(stat.S_ISDIR(info.st_mode) and info.st_uid==info.st_gid==owner_uid and
        stat.S_IMODE(info.st_mode)==0o700,'original private prefix directory')
    expected={};identities={}
    values={'record-order':dict(schema='meownero-record-order/1',binding=binding,
        itinerary=itinerary,recovery=recovery,mode='LIVE',position=0,pending=None,uncertain=None)}
    for n in itinerary:
        role='record-'+str(n)
        expected[role]=dict(role=role,delivery_role='observer' if n in recovery else 'keeper',
            bindings=binding,activation_sha256=c.digest(secret))
        values[role]=dict(schema='meownero-manager-slot/1',state='RESERVED',**expected[role])
    for name,value in values.items():
        fd=os.open(name,os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_RDWR|os.O_CLOEXEC,0o600,dir_fd=directory_fd)
        try:
            raw=c.canonical(value);outer.write_all(fd,raw);os.fsync(fd)
            c.require(os.pread(fd,len(raw)+1,0)==raw,'complete original reservation')
            info=os.fstat(fd);identities[name]=[info.st_dev,info.st_ino]
        finally:os.close(fd)
    os.fsync(directory_fd)
    order=identities.pop('record-order')
    return dict(order_identity=order,capability_identities=identities,capability_expected=expected)


class TerminalCustody:
    """External terminal owner, after root record 53 and its entry have exited.

    Each witness must come from the independent original lifecycle boundary.
    No helper return, pathname/inode equality or observation of self-exit can
    satisfy it. These OS primitives remain unqualified in the installed route.
    """
    def __init__(self,boundary,contract,*,clock=time.monotonic):
        self.boundary,self.contract,self.clock=boundary,contract,clock
        self.used=False

    def run_authenticated_inherited_entry(self):
        c.require(not self.used,'one terminal handoff')
        self.used=True
        self.boundary.authenticate_terminal(self.contract)
        for number in (52,53):
            c.require(self.boundary.record_durably_completed(number) is True,'terminal record durably completed')
        c.require(self.boundary.all_C_entries_exited_and_closed() is True,'all C-bound entries/journals exited and closed')
        c.require(self.boundary.independent_workers_exited() is True,'independent keeper/cleanup/observer exit')
        self.boundary.account_and_sync_final_tail()
        c.require(self.clock()<=self.contract['deadlines']['end'],'final tail within original absolute end')
        self.boundary.preserve_control_quarantine_and_archive()
        self.boundary.close_all_C_writers()
        c.require(self.clock()<=self.contract['deadlines']['end'],'original end before normal unmount')
        c.require(self.boundary.normal_unmount_C_and_absence() is True,'normal C unmount with independent absence')
        c.require(self.clock()<=self.contract['deadlines']['end'],'original end before namespace close')
        self.boundary.close_original_namespace()
        c.require(self.clock()<=self.contract['deadlines']['end'],'original end before lock release')
        self.boundary.release_original_lock_descriptions()
        c.require(self.boundary.independent_original_lock_reacquire() is True,'original lock independently released')
        c.require(self.clock()<=self.contract['deadlines']['end'],'terminal completion within original end')
        return dict(result='SOURCE_TERMINAL_RETURNED',installed_cleanup='NOT_RUN',native_execution='NOT_RUN')


class RecordJournal:
    """Existing control file plus pre-reserved GrantJournal slots, never created here.

    Hold a separate-open flock through the effect and its durable completion.
    Pending, torn or missing state cannot resume activation. Recovery needs an
    independently authenticated recovery invocation and keeps the original
    binding/deadlines. Power-loss/rollback resistance and custodian survival
    remain properties of the separately qualified control-storage authority.
    """
    def __init__(self, directory_fd, identity, binding, itinerary, recovery,
                 capabilities, *, owner_uid=0, clock=time.monotonic):
        self.directory_fd,self.identity=directory_fd,identity
        self.binding=copy.deepcopy(binding)
        self.itinerary,self.recovery=list(itinerary),list(recovery)
        c.require(self.itinerary and len(self.itinerary)<=55 and
            len(set(self.itinerary))==len(self.itinerary) and
            all(type(x) is int and 0<=x<55 for x in self.itinerary) and
            self.recovery and len(set(self.recovery))==len(self.recovery) and
            set(self.recovery)<=set(self.itinerary), 'bounded frozen record itinerary')
        self.capabilities,self.owner_uid,self.clock=capabilities,owner_uid,clock
        self.fd=None;self.state=None

    def _persist(self):
        raw=c.canonical(self.state)
        c.require(len(raw)<=65536,'bounded record state')
        os.lseek(self.fd,0,os.SEEK_SET)
        outer.write_all(self.fd,raw)
        os.ftruncate(self.fd,len(raw));os.fsync(self.fd)
        c.require(os.pread(self.fd,len(raw)+1,0)==raw,'record state durable readback')

    def begin(self, record, deadline, expected, secret, *, recovered=False):
        c.require(self.fd is None,'one outstanding record')
        try:
            self.fd=os.open('record-order',os.O_RDWR|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK,
                dir_fd=self.directory_fd)
            info=os.fstat(self.fd)
            c.require(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and
                info.st_uid==info.st_gid==self.owner_uid and stat.S_IMODE(info.st_mode)==0o600 and
                [info.st_dev,info.st_ino]==self.identity and 0<info.st_size<=65536,'original record journal')
            fcntl.flock(self.fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            raw=os.pread(self.fd,65537,0);state=json.loads(raw)
            c.require(c.canonical(state)==raw and set(state)=={'schema','binding','itinerary','recovery',
                'mode','position','pending','uncertain'} and state['schema']=='meownero-record-order/1' and
                state['binding']==self.binding and state['itinerary']==self.itinerary and
                state['recovery']==self.recovery and state['mode'] in ('LIVE','RECOVERY_ONLY') and
                type(state['position']) is int and state['position']>=0 and
                (state['pending'] is None or type(state['pending']) is int and state['pending'] in self.itinerary) and
                (state['uncertain'] is None or type(state['uncertain']) is int and state['uncertain'] in self.itinerary) and
                (state['mode']!='LIVE' or state['uncertain'] is None),'exact persistent record authority')
            self.state=state
            if recovered and state['mode']=='LIVE':
                state.update(mode='RECOVERY_ONLY',position=0,uncertain=state['pending'],pending=None)
                self._persist()
            c.require(recovered or state['mode']=='LIVE','recovery cannot regain activation')
            route=self.recovery if state['mode']=='RECOVERY_ONLY' else self.itinerary
            c.require(state['pending'] is None and state['position']<len(route) and
                route[state['position']]==record['sequence'],'replay, pending or out-of-order record')
            c.require(state['mode']=='LIVE' or record['phase'] in ('cleanup','completion'),
                'recovery records only; no activation or disposition')
            c.require(self.clock()<deadline<=self.binding['deadlines']['end'],'original record deadline')
            name='record-'+str(record['sequence'])
            self.capabilities.consume(name,expected,secret,deadline=deadline,clock=self.clock)
            state['pending']=record['sequence']
            self._persist()  # Both one-use burn and pending intent precede ANY effect.
            c.require(self.clock()<deadline,'pending intent exceeded original record deadline')
        except BaseException:
            self.close()
            raise

    def complete(self, record, deadline):
        c.require(self.fd is not None and self.state['pending']==record['sequence'] and
            self.clock()<deadline,'exact timely pending record')
        self.state.update(pending=None,position=self.state['position']+1)
        self._persist()
        c.require(self.clock()<deadline,'record completion exceeded original deadline')
        self.close()

    def uncertain(self, record):
        if self.fd is not None:
            try:
                self.state.update(mode='RECOVERY_ONLY',position=0,pending=None,uncertain=record['sequence'])
                self._persist()
            finally:self.close()

    def close(self):
        if self.fd is not None:os.close(self.fd);self.fd=None


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
