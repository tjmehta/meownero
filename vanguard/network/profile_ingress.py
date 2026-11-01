"""Connected root ingress; no installed constructor or authority is supplied.

The exact-source qualified constructor must receive `trusted` independently
from the surviving operator/custodian, never from argv, environment, local JSON
or received descriptors. Tests supply that contract explicitly. Its immutable
index bytes, peer/start/endpoint identities, record scope and original state
identities are the trust anchor; sealed memfds alone supply no authority.
"""
import copy
import fcntl
import json
import os
from pathlib import Path
import stat
import time

import profile_bootstrap as b
import profile_contract as c
import profile_dispatch as d
import profile_manager as m
import profile_packet as p
import profile_runtime as r


def identity(fd):
    info=os.fstat(fd)
    return [info.st_dev,info.st_ino]


def process_identity(pid):
    # Only exact caller/custodian PIDs from the independent anchor are inspected.
    start=Path('/proc/'+str(pid)+'/stat').read_text().rsplit(')',1)[1].split()[19]
    return dict(pid=pid,start=start)


def sealed_bytes(fd, maximum):
    info=os.fstat(fd)
    c.require(stat.S_ISREG(info.st_mode) and 0<info.st_size<=maximum and
        fcntl.fcntl(fd,fcntl.F_GET_SEALS)&b.SEALS==b.SEALS,'bounded immutable ingress bytes')
    raw=os.pread(fd,info.st_size+1,0)
    c.require(len(raw)==info.st_size,'complete sealed ingress bytes')
    return raw


def authority_binding(anchor):
    """Exact entry scope, compared on the independently authenticated link."""
    return dict(plan=anchor['plan'],receiver=anchor['receiver'],custodian=anchor['custodian'],
        record_binding=anchor['record_binding'],directory_identity=anchor['directory_identity'],
        order_identity=anchor['order_identity'],capability_identities=anchor['capability_identities'],
        request=anchor['envelope']['request'],recovery_only=anchor['envelope']['recovery_only'])


class InstalledIngress:
    """Supply RootEntry's authentication and durable record admission methods.

    OS effects/enforcement still belong to `backend`. That adapter and the
    authenticated constructor/anchor lifecycle remain absent and unqualified.
    No received field can select an adapter, program, path or trust anchor.
    """
    def __init__(self, backend, trusted, directory_fd, *, endpoint_fd=0, clock=time.monotonic,record_authority=None):
        self.backend,self.trusted=backend,copy.deepcopy(trusted)
        self.directory_fd,self.endpoint_fd,self.clock=directory_fd,endpoint_fd,clock
        self.fds=();self.packet=None;self.journal=None
        self.record_authority=record_authority

    def __getattr__(self,name):return getattr(self.backend,name)

    def _peers(self):
        anchor=self.trusted
        c.require(anchor['receiver_credentials']==[os.getpid(),os.getuid(),os.getgid()] and
            process_identity(os.getpid())==anchor['receiver'],'exact installed receiver invocation')
        sender=anchor['envelope']['delivery']
        c.require(process_identity(sender['sender_credentials'][0])==anchor['custodian'] and
            anchor['custodian']==dict(pid=sender['sender_credentials'][0],start=sender['sender_start']),
            'exact surviving custodian PID/start')

    def authenticate_root_entry(self):
        anchor=self.trusted
        c.require(self.record_authority is not None,'authenticated surviving record authority required')
        c.require(set(anchor)=={'schema','plan','inputs_raw','envelope','receiver_credentials','receiver',
            'custodian','descriptor_identities','endpoint_identity','directory_identity','order_identity',
            'capability_identities','capability_expected','record_binding','itinerary','recovery','owner_uid'} and
            anchor['schema']=='meownero-root-trust/1','independent installed trust contract required')
        plan=p.validate_plan(anchor['plan'])
        envelope=anchor['envelope'];delivery=envelope['delivery']
        c.require(set(envelope)=={'schema','delivery','request','activation','recovery_only'} and
            envelope['schema']=='meownero-root-ingress/1' and type(envelope['recovery_only']) is bool,
            'exact root envelope')
        c.require(delivery['role'] in (('deadline','observer') if envelope['recovery_only'] else ('prepare','keeper')),
            'independently classified activation or recovery role')
        b.validate_delivery(delivery,delivery['role'],plan,c.digest(c.canonical(plan)),self.clock())
        self._peers()
        c.require(identity(self.endpoint_fd)==anchor['endpoint_identity'],'original root receive endpoint')
        with b.socket_from_fd(self.endpoint_fd) as endpoint:
            b.seqpacket(endpoint)
            packet,self.fds=m.receive_packet(endpoint,delivery['sender_credentials'],
                delivery['delivery_deadline'],fd_count=3,clock=self.clock)
        self._peers()
        c.require(packet==envelope and [identity(fd) for fd in self.fds]==anchor['descriptor_identities'] and
            len({tuple(identity(fd)) for fd in self.fds})==3,'exact anchor-bound authority/context/index delivery')
        authority,context,index=self.fds
        with b.socket_from_fd(authority) as endpoint:b.seqpacket(endpoint)
        raw=sealed_bytes(context,m.MAX_PACKET)
        value=json.loads(raw)
        c.require(c.canonical(value)==raw and set(value)=={'schema','delivery','contract'} and
            value['schema']=='meownero-helper-bootstrap-context/1' and value['delivery']==delivery,
            'original generated-entry context')
        contract=d.validate_contract(value['contract'])
        c.require(c.digest(c.canonical(contract))==delivery['contract_sha256'] and
            contract['spec_sha256']==delivery['spec_sha256'] and contract['attempt_id']==plan['attempt_id'] and
            contract['origin']==delivery['origin'] and contract['deadlines']==delivery['deadlines'] and
            anchor['record_binding']==dict(contract_sha256=delivery['contract_sha256'],
                inputs_sha256=c.digest(anchor['inputs_raw']),origin=contract['origin'],deadlines=contract['deadlines']),
            'authority/source/index/original deadline binding')
        c.require(sealed_bytes(index,1024*1024)==anchor['inputs_raw'] and
            contract['bindings']['inputs_sha256']==plan['source']['inputs_sha256']==c.digest(anchor['inputs_raw']) and
            contract['bindings']['candidate_commit']==plan['source']['commit'] and
            contract['bindings']['artifact_sha256']==plan['source']['artifact_sha256'] and
            json.loads(anchor['inputs_raw'])['candidate_files']['vanguard/network/profile-helper.py']==
                plan['source']['helper_sha256'], 'exact independent index and source contract')
        info=os.fstat(self.directory_fd)
        c.require(identity(self.directory_fd)==anchor['directory_identity'] and stat.S_ISDIR(info.st_mode) and
            info.st_uid==info.st_gid==anchor['owner_uid'] and stat.S_IMODE(info.st_mode)==0o700,
            'original private control-directory custody')
        c.require(self.backend.authenticate_root_entry()==plan,'OS authority must agree with independent anchor')
        c.require(self.record_authority.authenticate(anchor) is True,
            'surviving authority must authenticate this original entry scope')
        store=r.CapabilityStore(self.directory_fd,anchor['capability_identities'],owner_uid=anchor['owner_uid'])
        self.journal=r.RecordJournal(self.directory_fd,anchor['order_identity'],anchor['record_binding'],
            anchor['itinerary'],anchor['recovery'],store,owner_uid=anchor['owner_uid'],clock=self.clock)
        self.packet=packet
        return plan

    def authenticated_installation_inputs(self):
        c.require(self.packet is not None,'authenticated ingress before index')
        return self.trusted['inputs_raw']

    def receive_authenticated_record_request(self):
        c.require(self.packet is not None,'authenticated ingress before request')
        return copy.deepcopy(self.packet['request'])

    def authenticate_executor(self,plan):
        c.require(self.packet is not None and plan==self.trusted['plan'],'authenticated executor plan')
        return self.backend.authenticate_executor(plan)

    def admit_record(self,record,deadline):
        c.require(self.packet['request']==dict(operation=record['operation'],record=record['sequence'],deadline=deadline),
            'exact authenticated record request')
        self._peers()
        role='record-'+str(record['sequence']);expected=self.trusted['capability_expected'][role]
        c.require(expected['bindings']==self.trusted['record_binding'] and
            expected['delivery_role']==self.packet['delivery']['role'],'record capability source/role binding')
        recovered=self.packet['recovery_only']
        position=self.record_authority.recovery_position(record) if recovered else None
        self.journal.begin(record,deadline,expected,bytes.fromhex(self.packet['activation']),
            recovered=recovered,recovery_position=position)
        self.record_authority.admit(record)
        self.backend.admit_record(record,deadline)  # Hard enforcement/ownership remain independently required.

    def complete_record(self,record,deadline):
        self.backend.complete_record(record,deadline)
        self.journal.complete(record,deadline)
        self.record_authority.complete(record)

    def quarantine_record_uncertainty(self,record):
        try:
            try:
                if self.record_authority is not None:self.record_authority.uncertain(record)
            finally:
                if self.journal is not None:self.journal.uncertain(record)
        finally:self.backend.quarantine_record_uncertainty(record)

    def close_authenticated_entry(self):
        if self.journal is not None:self.journal.close()
        for fd in self.fds:os.close(fd)
        self.fds=();self.packet=None
