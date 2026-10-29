"""Typed keeper/outer/controller state machine at injected OS boundaries.

No adapter is installed or qualified. The production CLI cannot construct this
object from JSON. Tests inject disposable operations; their receipts are modeled.
The backend owns the namespace, dedicated socket, write meter and persistent
journal, and must enforce every absolute timeout independently of this process.
"""
import fcntl
import json
import math
import os
import re
import stat
import time

import profile_contract as c
import profile_manager as m
import profile_packet as p

FD_COUNTS = dict(retain=1,first_admission=0,quarantine=0,provision=1,run_controller=3,
    inspect_image=0,observe_and_create=0,start_and_wait=0,inspect_owned=0,remove_owned=0,
    recover=0,observe_after_exit=0)
CONTRACT_FIELDS = {'bindings','attempt_id','spec_sha256','archive_sha256','image_id',
    'ledger_sha256','original_lock_witness_sha256','origin','deadlines'}
QUALIFIED_OS = {}  # Independent exact-source qualification must populate this by a reviewed source delta.
RECOVERY = {'recover','observe_after_exit'}


def validate_contract(value):
    c.require(set(value)==CONTRACT_FIELDS, 'complete immutable protocol contract')
    c.require(set(value['bindings']) == {'grant_id','grant_sha256','candidate_commit','inputs_sha256',
        'artifact_sha256','bootstrap_sha256'}, 'exact grant/source/artifact/bootstrap bindings')
    for key in ('spec_sha256','archive_sha256','ledger_sha256','original_lock_witness_sha256'):
        c.require((key=='ledger_sha256' and value[key] is None) or
            bool(re.fullmatch('[0-9a-f]{64}',value[key] or '')), 'bound digest: '+key)
    c.require(value['image_id']==m.IMAGE and bool(re.fullmatch('[0-9a-f]{32}',value['attempt_id'])), 'image/attempt')
    origin=value['origin']
    c.require(type(origin) in (int,float) and math.isfinite(origin) and
        value['deadlines']==dict(build=origin+3600,work=origin+4200,end=origin+4500), 'original absolute deadlines')
    return value


def directory_fd(fd, expected, *, uid=1000):
    info=os.fstat(fd)
    c.require(stat.S_ISDIR(info.st_mode) and info.st_uid==uid and info.st_gid==uid and
        stat.S_IMODE(info.st_mode)==0o700 and [info.st_dev,info.st_ino]==expected,
        'inherited ledger directory identity/uid/gid/mode')
    c.require(fcntl.fcntl(fd,fcntl.F_GETFL) & os.O_ACCMODE == os.O_RDONLY, 'read-only directory handle')
    return info


def ledger_fd(fd, contract):
    info=os.fstat(fd)
    c.require(stat.S_ISREG(info.st_mode) and info.st_uid==1000 and info.st_gid==1000 and
        stat.S_IMODE(info.st_mode)==0o600 and info.st_nlink==1 and 0<info.st_size<=65536 and
        fcntl.fcntl(fd,fcntl.F_GETFL)&os.O_ACCMODE==os.O_RDONLY, 'task-owned readonly consumed ledger FD')
    raw=os.pread(fd,info.st_size,0)
    value=json.loads(raw)
    c.require(c.canonical(value)==raw and c.digest(raw)==contract['ledger_sha256'] and
        value['schema']=='meownero-consumed-ledger/3' and value['state']=='CONSUMED' and
        value['bindings']==contract['bindings'] and value['origin']==contract['origin'], 'exact durable ledger')
    return value


def observed_work(value, plan):
    c.require(type(value) is dict and set(value)==set(p.IDENTITIES)|{'owner_uid','owner_gid','mount_mode',
        'user_directory','user_owner','user_mode','length','allocated_bytes','filesystem_capacity','namespace_retained'},
        'complete observed W identity')
    for key in p.IDENTITIES:
        if key=='loop':c.require(bool(re.fullmatch('/dev/loop[0-9]+',value[key])), 'observed owned loop')
        else:c.require(type(value[key]) is int and value[key]>0, 'positive observed W '+key)
    c.require(value['owner_uid']==value['owner_gid']==0 and value['mount_mode']==0o700 and
        value['user_owner']==[1000,1000] and value['user_mode']==0o700 and
        value['length']==value['allocated_bytes']==plan['allocation']['workload'] and
        0<value['filesystem_capacity']<=value['length'] and value['namespace_retained'] is True,
        'root W backing and separately writable uid1000 directory')
    c.require(type(value['user_directory']) is str and value['user_directory'].startswith('/') and
        value['user_directory'].endswith('/user') and '..' not in value['user_directory'].split('/'), 'owned user directory')
    return value


def create_spec(contract, work, payload):
    """The caller supplies a staging digest, never Docker argv or host mounts."""
    c.require(set(payload)=={'staging_sha256'} and bool(re.fullmatch('[0-9a-f]{64}',payload['staging_sha256'])),
              'typed create input')
    root=work['user_directory']
    return dict(schema='meownero-owned-create/3', image=m.IMAGE, attempt_id=contract['attempt_id'],
        bindings=contract['bindings'], archive_sha256=contract['archive_sha256'],
        staging_sha256=payload['staging_sha256'], user=[1000,1000], writable_root=root,
        mounts={'/out':root+'/attempt','/tmp':root+'/attempt/tmp','/public':root+'/public'},
        network='none',read_only=True,log_driver='none',cap_drop=['ALL'],no_new_privileges=True,
        cpus=2,memory=3840*p.MIB,swap=0,pids=224,compiler_jobs=1,
        readonly_toolchain=dict(identity_from='frozen_inputs.rust_inputs',destination='/opt/rust'),
        labels={'meownero.task':'TJS-2504','meownero.attempt':contract['attempt_id'],
            'meownero.grant':contract['bindings']['grant_id'],'meownero.inputs':contract['bindings']['inputs_sha256']},
        environment=dict(PATH='/opt/rust/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
            CARGO_HOME='/out/cargo-home',CARGO_NET_OFFLINE='true',CARGO_BUILD_JOBS='1',HOME='/out/tmp',
            LC_ALL='C',PYTHONDONTWRITEBYTECODE='1'),command=['bash','/out/harness/integration/build.sh'])


class Budget:
    """Independent hard meters are a qualification input; samples cannot enforce writes."""
    def __init__(self, *, phase='preparation'):
        self.phase=phase
        self.writes=0
        self.occupied=0
        self.failed=False

    def charge(self, *, written, occupied):
        c.require(not self.failed, 'exhausted budget never rearms')
        self.failed=True
        c.require(type(written) is int and written>=0 and type(occupied) is int and occupied>=0,
                  'separate nonnegative byte counters')
        # Advance before refusing: an exhausted counter never rearms by retry.
        self.writes+=written
        self.occupied=occupied
        c.require(self.writes<=4*p.GIB and self.occupied<=(4 if self.phase=='preparation' else 15)*p.GIB,
                  'cumulative writes or occupied allocation exhausted')
        self.failed=False


class Dispatcher:
    def __init__(self, plan, contract, backend, *, clock=time.monotonic, recovered=False):
        p.validate_plan(plan);validate_contract(contract)
        c.require(c.digest(c.canonical(plan))==contract['spec_sha256'], 'exact spec contract')
        self.plan,self.contract,self.backend,self.clock=plan,contract,backend,clock
        self.sequences={'outer':0,'controller':0}
        self.state='RECOVERY_ONLY' if recovered else 'RESERVED'
        self.first=None;self.work=None;self.gate=None;self.cid=None
        self.create_intent=None;self.controller_started=False
        self.retained=False;self.first_used=False;self.create_used=False
        self.cleanup=None;self.phase=None;self.removed=False;self.created_receipt=None
        self.end=contract['deadlines']['end']
        # Startup always validates the existing slot. A missing/corrupt slot
        # cannot be recreated; even RESERVED is recovery-only after restart.
        backend.validate_slot(contract, recovery_only=recovered)

    def check(self, deadline, channel):
        c.require(type(deadline) in (int,float) and math.isfinite(deadline) and
            self.clock()<deadline<=self.end, 'absolute request deadline')
        self.backend.check_peer_start(channel)

    def dispatch(self, request, fds=(), *, channel='outer'):
        operation=request.get('operation')
        try:
            c.require(set(request)=={'schema','operation','sequence','contract','deadline','payload'} and
                request['schema']=='meownero-private-helper/3' and operation in FD_COUNTS, 'typed request')
            c.require(channel in self.sequences, 'fixed inherited channel role')
            allowed=(set(FD_COUNTS)-{'inspect_image','observe_and_create','start_and_wait','inspect_owned','remove_owned'}
                if channel=='outer' else {'inspect_image','observe_and_create','start_and_wait','inspect_owned','remove_owned'})
            c.require(operation in allowed, 'operation not permitted for this inherited role')
            c.require(request['sequence']==self.sequences[channel], 'replayed/out-of-order request')
            self.sequences[channel]+=1  # All uncertainty consumes sequence and activation.
            if operation=='provision' and self.contract['ledger_sha256'] is None and len(fds)==1:
                c.require(self.state=='QUARANTINED', 'no W or ledger binding before durable quarantine')
                info=os.fstat(fds[0])
                c.require(stat.S_ISREG(info.st_mode) and 0<info.st_size<=65536, 'bounded regular ledger FD')
                proposed={**self.contract,'ledger_sha256':c.digest(os.pread(fds[0],65537,0))}
                c.require(request['contract']==proposed, 'single authenticated ledger digest binding')
                ledger_fd(fds[0],proposed)
                self.contract=proposed
            c.require(request['contract']==self.contract and len(fds)==FD_COUNTS[operation], 'request binding/FD count')
            self.check(request['deadline'],channel)
            c.require(self.state!='RECOVERY_ONLY' or operation in RECOVERY, 'recovery-only, never rearm')
            result=self._operation(operation,request['payload'],fds,request['deadline'])
            self.check(request['deadline'],channel)
            return dict(schema='meownero-private-reply/3',sequence=request['sequence'],
                request_sha256=c.digest(c.canonical(request)),contract=self.contract,ok=True,result=result)
        except BaseException:
            self.state='RECOVERY_ONLY'
            self.backend.quarantine_uncertainty(self.contract,self.create_intent,self.cid)
            raise

    def _operation(self, operation, payload, fds, deadline):
        if operation=='retain':
            c.require(self.state=='RESERVED' and not self.retained and payload=={}, 'one retain')
            # Mark before entering PID1: lost barrier/readback ack retains custody.
            self.retained=True
            result=self.backend.retain_two_fds(fds[0],self.contract,deadline)
            c.require(set(result)=={'same_open_description','lock_identity','namespace_identity',
                'independent_pid1_readback','deadline_owner_armed','deadlines','origin'} and
                result['same_open_description'] is True and result['lock_identity']==list(c.LOCK_ID) and
                type(result['namespace_identity']) is int and result['namespace_identity']>0 and
                result['independent_pid1_readback'] is True and result['deadline_owner_armed'] is True and
                result['deadlines']==self.contract['deadlines'] and result['origin']==self.contract['origin'],
                'two-FD custody and independent original-deadline readback required')
            self.state='RETAINED'
            return result
        if operation=='first_admission':
            c.require(self.state=='RETAINED' and not self.first_used and payload=={}, 'first admission one-use')
            self.first_used=True
            before=self.clock()
            value=self.backend.observe_full(self.contract,deadline)
            after=self.clock()
            c.require(before<=value['started_at']<=value['at']<=after<=value['started_at']+5 and
                after<self.contract['deadlines']['build'], 'full first observation freshness')
            c.require(value['bindings']==self.contract['bindings'] and value['attempt_id']==self.contract['attempt_id'] and
                value['original_lock']==list(c.LOCK_ID) and
                value['original_lock_witness_sha256']==self.contract['original_lock_witness_sha256'], 'first observation binding')
            c.admit(value['snapshot']);self.backend.check_original_lock()
            self.first=value
            self.state='ADMITTED'
            return value
        if operation=='quarantine':
            c.require(self.state=='ADMITTED' and payload=={}, 'quarantine order')
            c.require(self.clock()<=self.first['started_at']+5, 'first observation expired')
            self.state='RECOVERY_ONLY' # Failure cannot return to ADMITTED.
            value=self.backend.durable_quarantine(self.contract,deadline)
            c.require(value['state']=='QUARANTINED' and re.fullmatch('[0-9a-f]{64}',value['sha256']), 'durable quarantine')
            c.require(self.clock()<=self.first['started_at']+5, 'quarantine expired')
            self.state='QUARANTINED';return value
        if operation=='provision':
            c.require(self.state=='QUARANTINED' and payload=={}, 'W only after quarantine/consumption')
            ledger=ledger_fd(fds[0],self.contract)
            c.require(ledger['first_started_at']==self.first['started_at'] and
                self.first['at']<=ledger['consumed_at']<=self.clock()<=self.first['started_at']+5 and
                self.clock()<=self.first['started_at']+5, 'first observation through durable consumption')
            self.state='RECOVERY_ONLY'
            value=self.backend.provision_owned_work(self.contract,ledger,deadline)
            self.work=observed_work(value['observed_work'],self.plan)
            self.state='PROVISIONED';return value
        if operation=='run_controller':
            c.require(self.state=='PROVISIONED' and not self.controller_started and payload=={}, 'one controller')
            self.controller_started=True
            outcome=self.backend.run_controller(fds,self.contract,self.work,deadline,self)
            c.require(self.created_receipt is not None, 'root-owned atomic-create receipt required')
            return dict(outcome,create_receipt=dict(count=1,**self.created_receipt))
        if operation=='inspect_image':
            c.require(self.state=='PROVISIONED' and payload=={}, 'image before atomic observation')
            value=self.backend.inspect_fixed_image(self.contract,deadline)
            c.require(value['image_id']==m.IMAGE and value['os']=='linux' and value['architecture']=='amd64', 'fixed image')
            return value
        if operation=='observe_and_create':
            c.require(self.state=='PROVISIONED' and not self.create_used, 'one atomic create')
            self.create_used=True # Before input validation, inspection, hashing or observation.
            exact=create_spec(self.contract,self.work,payload)
            self.backend.prevalidate_create(exact,deadline) # paths, image/config/layers, immutable toolchain, stage digest
            digest=c.digest(c.canonical(exact))
            self.create_intent=dict(spec=exact,sha256=digest,ownership=self.contract['attempt_id'])
            self.backend.persist_create_intent(self.create_intent,deadline)
            bound=dict(bindings=self.contract['bindings'],attempt_id=self.contract['attempt_id'],
                ledger_sha256=self.contract['ledger_sha256'],build_deadline=self.contract['deadlines']['build'],
                original_lock_witness_sha256=self.contract['original_lock_witness_sha256'],create_sha256=digest)
            self.gate=m.AdmissionGate(bound,clock=self.clock)
            def create():
                remaining=min(self.contract['deadlines']['build'],self.gate_started+5)
                cid=self.backend.create_fixed(exact,deadline=remaining)
                self.cid=cid  # Preserve late CID before AdmissionGate rejects it.
                self.backend.record_owned_cid(cid,self.create_intent,deadline=self.end)
                return cid
            def observe():
                self.gate_started=self.clock()
                return self.backend.observe_create(bound,deadline=min(deadline,self.gate_started+5))
            result=self.gate.create(bound,check_peer=lambda:self.backend.check_peer_start('controller'),
                check_lock=self.backend.check_original_lock,observe=observe,create=create)
            self.created_receipt=result
            self.state='CREATED'
            return result
        if operation in ('start_and_wait','inspect_owned','remove_owned'):
            allowed={'container_id','phase'} if operation=='start_and_wait' else {'container_id'}
            c.require(set(payload)==allowed and self.cid is not None and payload['container_id']==self.cid,
                'exact owned CID only')
            if operation=='start_and_wait':
                c.require(self.state=='CREATED' and not self.removed and
                    ((self.phase is None and payload['phase']=='build') or
                     (self.phase=='build' and payload['phase']=='runtime')), 'one build then one runtime phase')
                if payload['phase']=='runtime':
                    c.require(self.clock()+600<=self.contract['deadlines']['work'], 'full runtime allowance')
                self.phase=payload['phase']
                bound=self.contract['deadlines']['build' if payload['phase']=='build' else 'work']
                c.require(deadline<=bound, 'phase deadline extension')
                return self.backend.start_and_wait_owned(self.cid,payload['phase'],deadline)
            if operation=='inspect_owned':return self.backend.inspect_owned(self.cid,deadline)
            c.require(not self.removed, 'owned removal already consumed')
            self.removed=True
            return self.backend.remove_owned(self.cid,deadline)
        if operation=='recover':
            c.require(payload=={}, 'no recovery executable or changed deadlines')
            self.state='RECOVERY_ONLY'
            self.cleanup=self.backend.recover_owned(self.contract,self.work,self.create_intent,self.cid,deadline)
            c.require(self.cleanup['work_population']==0 and self.cleanup['remaining_cids']==[] and
                self.cleanup['remaining_work_mounts']==[] and self.cleanup['remaining_work_loops']==[] and
                self.cleanup['control_retained'] is True and self.cleanup['slot_retained'] is True and
                self.cleanup['lock_held'] is True, 'work cleanup versus retained C')
            return self.cleanup
        if operation=='observe_after_exit':
            c.require(self.cleanup is not None and payload.keys()=={'result'}, 'cleanup before observer')
            value=self.backend.arm_final_observer(self.contract,self.cleanup,payload['result'],deadline)
            c.require(value['result']=='PENDING_OBSERVER_EXIT', 'observer cannot attest own exit')
            return value
        raise ValueError('unknown operation')

    def serve_one(self, endpoint, credentials, deadline, *, channel='outer'):
        """Kernel sender credentials + separately bound PID/start for each packet."""
        fds=()
        try:
            # receive_packet must know the expected count before accepting FDs.
            # Peek has no side effects and accepts no ancillary ownership. The
            # actual authenticated recv remains authoritative and is rechecked.
            import socket
            left=deadline-self.clock()
            c.require(left>0, 'receive deadline')
            endpoint.settimeout(left)
            raw=endpoint.recv(m.MAX_PACKET,socket.MSG_PEEK)
            try:
                preview=json.loads(raw)
                operation=preview.get('operation') if type(preview) is dict else None
            except (ValueError,TypeError):operation=None
            count=FD_COUNTS.get(operation,0)
            request,fds=m.receive_packet(endpoint,credentials,deadline,fd_count=count,clock=self.clock)
            self.backend.check_peer_start(channel)
            reply=self.dispatch(request,fds,channel=channel)
            m.send_packet(endpoint,reply,deadline=deadline,clock=self.clock)
        except BaseException:
            self.state='RECOVERY_ONLY'
            self.backend.quarantine_uncertainty(self.contract,self.create_intent,self.cid)
            raise
        finally:
            for fd in fds:os.close(fd)


class Client:
    def __init__(self,endpoint,credentials,contract,*,check_peer,clock=time.monotonic):
        validate_contract(contract)
        import socket
        c.require(endpoint.family==socket.AF_UNIX and endpoint.type & socket.SOCK_SEQPACKET==socket.SOCK_SEQPACKET and
            endpoint.getsockopt(socket.SOL_SOCKET,socket.SO_PASSCRED)==1, 'credentialed seqpacket endpoint')
        c.require(endpoint.getsockname() in ('',b'') and endpoint.getpeername() in ('',b''), 'unnamed inherited channel')
        self.endpoint,self.credentials,self.contract=endpoint,credentials,contract
        self.check_peer,self.clock=check_peer,clock
        self.sequence=0;self.failed=False

    def request(self,operation,payload,*,deadline,fds=()):
        c.require(operation in FD_COUNTS and len(fds)==FD_COUNTS[operation], 'typed operation and FD count')
        c.require(not self.failed or operation in RECOVERY, 'lost reply is recovery only')
        self.check_peer()
        request=dict(schema='meownero-private-helper/3',operation=operation,sequence=self.sequence,
            contract=self.contract,deadline=deadline,payload=payload)
        self.sequence+=1
        try:
            m.send_packet(self.endpoint,request,fds,deadline=deadline,clock=self.clock)
            reply,_=m.receive_packet(self.endpoint,self.credentials,deadline,clock=self.clock)
            self.check_peer()
            c.require(reply['schema']=='meownero-private-reply/3' and reply['contract']==self.contract and
                reply['request_sha256']==c.digest(c.canonical(request)) and
                reply['sequence']==request['sequence'] and reply['ok'] is True, 'exact authenticated reply')
            return reply['result']
        except BaseException:self.failed=True;raise

    def observe_and_create(self,staging_sha256,*,deadline):
        return self.request('observe_and_create',dict(staging_sha256=staging_sha256),deadline=deadline)

    def start_and_wait(self,cid,phase,*,deadline):
        return self.request('start_and_wait',dict(container_id=cid,phase=phase),deadline=deadline)

    def inspect_owned(self,cid,*,deadline):
        return self.request('inspect_owned',dict(container_id=cid),deadline=deadline)

    def remove_owned(self,cid,*,deadline):
        return self.request('remove_owned',dict(container_id=cid),deadline=deadline)


def authorize_mode(mode,plan,spec_sha256,authority,context,*,backend_table=QUALIFIED_OS):
    """Hashes/JSON are assertions; inherited authenticated FDs supply authority."""
    p.validate_plan(plan)
    c.require(c.digest(c.canonical(plan))==spec_sha256, 'exact canonical spec digest')
    c.require(mode in ('prepare','serve','recover','observe','dispose'), 'mutation mode')
    required=('operator','authentication_route','preparation_authority','tool_versions','hard_write_enforcement',
        'namespace_access','pid1_custody_readback','overhead_qualification','lifecycle_authority','retained_control_custodian')
    c.require(all(plan['authority'][key] is not None for key in required), 'UNBOUND authority/qualification')
    if mode=='serve':
        c.require(all(plan['authority'][key] is not None for key in ('runtime_grant','platform_review','core_review',
            'security_review','bootstrap_sha256','archive_sha256','archive_provenance','producer_receipt')), 'runtime review/grant binding')
    if mode=='dispose':c.require(plan['authority']['disposition_authority'] is not None, 'separate disposition authority')
    for key,value in plan['source'].items():
        c.require(type(value) is str and bool(re.fullmatch('[0-9a-f]{'+('40' if key=='commit' else '64')+'}',value)),
            'exact nonnull source hash: '+key)
    digest=plan['authority']['bootstrap_sha256']
    c.require(digest in backend_table, 'no exact-source qualified OS adapter')
    adapter=backend_table[digest]
    if mode in ('serve','recover','observe') and authority is None and context is None:
        adapter.authenticate_restart(mode,plan,spec_sha256)
    else:
        c.require(type(authority) is int and type(context) is int and authority>2 and context>2 and authority!=context,
            'distinct inherited authority/context FDs')
        adapter.authenticate_inherited(mode,authority,context,plan,spec_sha256)
    return adapter


def stored_fds(environment,*,pid,validate_lock,validate_namespace,setns):
    """Recover only from the two named PID1 FDs; never reopen a namespace path."""
    c.require(environment.get('LISTEN_PID')==str(pid) and environment.get('LISTEN_FDS')=='2' and
        set(environment.get('LISTEN_FDNAMES','').split(':'))=={'original-lock','mount-namespace'}, 'exact named stored FDs')
    named={name:3+i for i,name in enumerate(environment['LISTEN_FDNAMES'].split(':'))}
    lock,namespace=named['original-lock'],named['mount-namespace']
    validate_lock(lock);validate_namespace(namespace)
    setns(namespace,0x00020000) # CLONE_NEWNS; caller must have qualified access.
    for fd in (3,4):os.set_inheritable(fd,False)
    return dict(lock_fd=lock,namespace_fd=namespace,recovery_only=True)


class OuterManager(Client):
    """The same typed protocol supplies the task-user outer's Manager interface."""
    def retain(self,lock_fd,bindings,deadlines,*,deadline):
        c.require(bindings==self.contract['bindings'] and deadlines==self.contract['deadlines'], 'outer contract')
        return self.request('retain',{},deadline=deadline,fds=(lock_fd,))

    def admit(self,number,*,deadline):
        c.require(number==1, 'second observation exists only inside observe_and_create')
        return self.request('first_admission',{},deadline=deadline)

    def quarantine(self,bindings,*,deadline):
        c.require(bindings==self.contract['bindings'], 'quarantine grant')
        return self.request('quarantine',{},deadline=deadline)

    def provision(self,ledger,*,deadline):
        c.require(self.contract['ledger_sha256'] is None, 'ledger binding is one-use')
        self.contract={**self.contract,'ledger_sha256':c.digest(os.pread(ledger,65537,0))}
        return self.request('provision',{},deadline=deadline,fds=(ledger,))

    def run_controller(self,context_fd,lock_fd,ledger_fd,*,deadlines):
        c.require(deadlines==self.contract['deadlines'], 'controller original deadlines')
        return self.request('run_controller',{},deadline=deadlines['work'],fds=(context_fd,lock_fd,ledger_fd))

    def recover(self,*,deadline):return self.request('recover',{},deadline=deadline)

    def complete_after_exit(self,result,*,deadline):
        return self.request('observe_after_exit',{'result':result},deadline=deadline)


class LifecycleAdapter:
    """Fixed lifecycle orchestration over a separately qualified syscall boundary.

    The boundary is compiled/registered by exact source, never loaded from the
    spec. apply_record accepts only this renderer's fixed operations. Its waits,
    process placement and hard write ceilings must work if this Python dies.
    """
    def __init__(self,boundary,*,clock=time.monotonic):
        self.boundary,self.clock=boundary,clock
        self.authenticated=None
        self.preparation_used=False

    def authenticate_inherited(self,mode,authority,context,plan,spec_sha256):
        receipt=self.boundary.authenticate_inherited(mode,authority,context,plan,spec_sha256)
        c.require(receipt['mode']==mode and receipt['spec_sha256']==spec_sha256 and
            receipt['source']==plan['source'] and receipt['task_only'] is True and
            receipt['hard_byte_and_write_limits'] is True and receipt['overhead_within_reservation'] is True,
            'authenticated source/authority/hard limits/overhead')
        self.authenticated=receipt

    def authenticate_restart(self,mode,plan,spec_sha256):
        receipt=self.boundary.authenticate_installed_recovery(mode,plan,spec_sha256)
        c.require(receipt['mode']==mode and receipt['spec_sha256']==spec_sha256 and
            receipt['source']==plan['source'] and receipt['installed_root_owned_source'] is True and
            receipt['exact_task_unit_pid1_sender'] is True and receipt['recovery_only'] is True,
            'restart needs independent installed-source/unit authority, never activation')
        self.authenticated=receipt

    def enter(self,mode,plan,*,deadline_owner=False):
        c.require(self.authenticated is not None and self.authenticated['mode']==mode, 'inherited authority first')
        if mode=='prepare':return self.prepare(plan)
        context=self.boundary.read_existing_context()
        validate_contract(context['contract'])
        if mode=='serve':
            recovered=self.authenticated.get('recovery_only',False) or context['recovered'] or not context['live_one_use_activation']
            dispatcher=Dispatcher(plan,context['contract'],self.boundary,clock=self.clock,recovered=recovered)
            if recovered:self.boundary.reenter_stored_namespace(stored_fds)
            return self.boundary.serve_inherited_channels(dispatcher)
        if mode=='recover':
            self.boundary.reenter_stored_namespace(stored_fds)
            if deadline_owner:
                # Absolute CLOCK_MONOTONIC wait, never a new origin/timer on restart.
                self.boundary.wait_until(context['contract']['deadlines']['work'])
            end=context['contract']['deadlines']['end']
            c.require(self.clock()<end, 'original cleanup deadline exhausted; retain custody')
            return self.boundary.recover_owned(context['contract'],context['observed_work'],
                context['create_intent'],context['owned_cid'],end)
        if mode=='observe':
            self.boundary.wait_owned_cleanup_keeper_exit(context['contract']['deadlines']['end'])
            pending=self.boundary.observe_retained_and_work_absence(context)
            c.require(pending['result']=='PENDING_OBSERVER_EXIT', 'external lifecycle must finish after observer exit')
            return pending
        if mode=='dispose':
            c.require(self.authenticated['separate_disposition'] is True and
                self.authenticated['irrevocable_grant_tombstone'] is True, 'separate disposition/tombstone')
            return self.boundary.dispose_exact_retained(context)
        raise ValueError('unknown lifecycle mode')

    def prepare(self,plan):
        c.require(not self.preparation_used, 'preparation is one-use, never resume')
        self.preparation_used=True
        packet=p.render(plan)
        meter=Budget()
        origin=self.clock()
        phases={}
        try:
            for record in packet['records']:
                if record['phase'] not in ('install','control','archive'):continue
                phase=record['phase']
                if phase not in phases:phases[phase]=dict(origin=self.clock(),writes=0)
                # Independent enforcement is established before execution; this
                # readback checks its meter, not a substitute sampling limiter.
                result=self.boundary.apply_preparation_record(record,absolute_end=origin+1200,
                    phase_end=phases[phase]['origin']+(300 if phase=='control' else 900 if phase=='archive' else 1200))
                meter.charge(written=result['written_bytes'],occupied=result['occupied_bytes'])
                phases[phase]['writes']+=result['written_bytes']
                cap=p.PREPARATION['control' if phase=='control' else 'archive']['writes'] if phase!='install' else p.PREPARATION['other_writes']
                c.require(phases[phase]['writes']<=cap and self.clock()<=origin+1200 and
                    self.clock()<=phases[phase]['origin']+(300 if phase=='control' else 900 if phase=='archive' else 1200),
                    'preparation phase writes/time exhausted')
            receipt=self.boundary.preparation_readback()
            c.require(receipt['slot_state']=='RESERVED' and receipt['root_slot_owner']==[0,0] and
                receipt['ledger_directory_owner']==[1000,1000] and receipt['observed_work'] is None and
                receipt['archive_sealed'] is True and receipt['archive_plus_overhead_bytes']<=2*p.GIB,
                'prepared C/ledger/archive with absent W')
            return dict(result='PREPARED_UNACTIVATED',receipt=receipt,cumulative_writes=meter.writes,
                occupied_bytes=meter.occupied,activation='SEPARATE_EXACT_RUNTIME_GRANT_REQUIRED')
        except BaseException:
            self.boundary.preparation_uncertainty_never_rearm()
            raise


def launch_outer(context_fd,helper_fd,ledger_directory_fd,manifest,*,clock=time.monotonic):
    """Task uid1000 entry behind the exact-source qualification gate.

    A sealed caller-created memfd alone is never authority. The qualified
    custodian authenticates the actual source, grant/artifact/reviews and sender.
    """
    import socket
    from pathlib import Path
    import profile_handoff as h
    import profile_outer as outer
    h.require_bootstrap(manifest)
    c.require(os.getuid()==os.getgid()==1000 and len({context_fd,helper_fd,ledger_directory_fd})==3 and
        all(type(fd) is int and fd>2 for fd in (context_fd,helper_fd,ledger_directory_fd)), 'outer uid and inherited FDs')
    seals=fcntl.F_SEAL_SEAL|fcntl.F_SEAL_SHRINK|fcntl.F_SEAL_GROW|fcntl.F_SEAL_WRITE
    c.require(fcntl.fcntl(context_fd,fcntl.F_GET_SEALS)&seals==seals, 'sealed startup context')
    info=os.fstat(context_fd)
    c.require(info.st_uid==1000 and stat.S_IMODE(info.st_mode)==0o600 and 0<info.st_size<=65536, 'private bounded startup')
    value=json.loads(os.pread(context_fd,info.st_size,0))
    c.require(value['schema']=='meownero-outer-start/3', 'outer start schema')
    bound=validate_contract(value['contract'])
    digest=bound['bindings']['bootstrap_sha256']
    c.require(digest in QUALIFIED_OS, 'no qualified outer authority adapter')
    QUALIFIED_OS[digest].boundary.authenticate_outer(value,context_fd,helper_fd,ledger_directory_fd,manifest)
    directory_fd(ledger_directory_fd,value['ledger_directory_identity'])
    peer=value['helper_credentials'];owned=value['helper_pid_identity']
    def check_peer():
        live=[peer[0],Path(f'/proc/{peer[0]}/stat').read_text().rsplit(')',1)[1].split()[19]]
        c.stop_identity(owned,live)
    endpoint=socket.socket(fileno=helper_fd)
    client=OuterManager(endpoint,peer,bound,check_peer=check_peer,clock=clock)
    try:return outer.Outer(client,clock=clock).run(bound['bindings'],ledger_directory_fd,
        ledger_identity=value['ledger_directory_identity'])
    finally:endpoint.close()
