"""Source fixtures at the real dispatcher/controller boundary.

No host cgroup, namespace, PID1, Docker, image, heavy lock or native process.
Crash/OOM/death results are MODELED, never live survival evidence.
"""
import copy
import errno
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import profile_contract as c
import profile_dispatch as d
import profile_handoff as h
import profile_manager as m
import profile_outer as outer
import profile_packet as p

BINDINGS=dict(grant_id='11111111-1111-4111-8111-111111111111',grant_sha256='a'*64,
    candidate_commit='b'*40,inputs_sha256='c'*64,artifact_sha256='d'*64,bootstrap_sha256='e'*64)


def contract(plan):
    return dict(bindings=BINDINGS,attempt_id='1'*32,spec_sha256=c.digest(c.canonical(plan)),
        archive_sha256='f'*64,image_id=m.IMAGE,ledger_sha256=None,
        original_lock_witness_sha256='2'*64,origin=100,deadlines=dict(build=3700,work=4300,end=4600))


def work():
    return dict(backing_inode=11,filesystem_device=22,loop='/dev/loop90',loop_device=33,mount_id=44,
        namespace_inode=55,owner_uid=0,owner_gid=0,mount_mode=0o700,user_directory='/modeled/task/user',
        user_owner=[1000,1000],user_mode=0o700,length=11*p.GIB,allocated_bytes=11*p.GIB,
        filesystem_capacity=10*p.GIB,namespace_retained=True)


def observation(now=100):
    return dict(started_at=now,at=now,snapshot=dict(available_memory_bytes=5*p.GIB,
        free_disk_bytes=20*p.GIB,load=[0,0,0],native_processes=[],native_containers=[]))


class Boundary:
    """Injected OS boundary, all host receipts explicitly MODELED."""
    def __init__(self):
        self.now=100;self.calls=[];self.failure=None;self.owned=[]
        self.create_delay=0;self.observe_delay=0;self.retained=False

    def call(self,name):
        self.calls.append(name)
        if self.failure==name:raise OSError(errno.ENOSPC,'MODELED boundary failure')

    def validate_slot(self,value,*,recovery_only):self.call('validate_slot')
    def check_peer_start(self,channel='outer'):self.call('peer')
    def check_original_lock(self):self.call('lock')
    def quarantine_uncertainty(self,*args):self.calls.append('uncertain')
    def retain_two_fds(self,fd,value,deadline):
        self.retained=True;self.call('retain')
        return dict(same_open_description=True,lock_identity=list(c.LOCK_ID),namespace_identity=55,
            independent_pid1_readback=True,deadline_owner_armed=True,deadlines=value['deadlines'],origin=value['origin'])
    def observe_full(self,value,deadline):
        self.call('first')
        return dict(**observation(self.now),bindings=value['bindings'],attempt_id=value['attempt_id'],
            original_lock=list(c.LOCK_ID),original_lock_witness_sha256=value['original_lock_witness_sha256'])
    def durable_quarantine(self,value,deadline):self.call('quarantine');return dict(state='QUARANTINED',sha256='3'*64)
    def provision_owned_work(self,value,ledger,deadline):
        self.call('provision');return dict(observed_work=work())
    def inspect_fixed_image(self,*args):
        self.call('image');return dict(image_id=m.IMAGE,os='linux',architecture='amd64')
    def prevalidate_create(self,exact,deadline):self.call('prevalidate')
    def persist_create_intent(self,intent,deadline):self.call('intent')
    def observe_create(self,bound,*,deadline):
        self.call('second');value=observation(self.now);self.now+=self.observe_delay;value['at']=self.now
        return dict(**value,**{k:bound[k] for k in ('bindings','attempt_id','ledger_sha256',
            'original_lock_witness_sha256','create_sha256')},original_lock=list(c.LOCK_ID))
    def create_fixed(self,exact,*,deadline):
        self.create_deadline=deadline;self.call('create');self.now+=self.create_delay;return 'c'*64
    def record_owned_cid(self,cid,intent,*,deadline):self.owned.append(cid);self.call('record_cid')
    def start_and_wait_owned(self,cid,phase,deadline):
        self.call(phase);return dict(exit_code=0,oom_killed=False)
    def inspect_owned(self,cid,deadline):self.call('inspect');return dict(container_id=cid)
    def remove_owned(self,cid,deadline):self.call('remove');return dict(absent=True)
    def recover_owned(self,value,work,intent,cid,deadline):
        self.call('recover');return dict(work_population=0,remaining_cids=[],remaining_work_mounts=[],
            remaining_work_loops=[],control_retained=True,slot_retained=True,lock_held=True)
    def arm_final_observer(self,*args):self.call('observer');return dict(result='PENDING_OBSERVER_EXIT')


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.plan=p.source_plan();self.bound=Boundary()
        self.dispatch=d.Dispatcher(self.plan,contract(self.plan),self.bound,clock=lambda:self.bound.now)
        self.temp=tempfile.TemporaryDirectory(prefix='TJS2504-dispatch-source-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.dirfd=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
        self.addCleanup(os.close,self.dirfd)
        self.identity=[self.root.stat().st_dev,self.root.stat().st_ino]

    def request(self,op,payload=None,fds=(),*,channel='outer',deadline=None):
        request=dict(schema='meownero-private-helper/3',operation=op,sequence=self.dispatch.sequences[channel],
            contract=copy.deepcopy(self.dispatch.contract),deadline=deadline or 3700,payload={} if payload is None else payload)
        return self.dispatch.dispatch(request,fds,channel=channel)['result']

    def provision(self):
        self.request('retain',fds=(self.dirfd,)) # FD is only an injected custody input, not a namespace/lock claim.
        self.request('first_admission');self.request('quarantine')
        fd,value=outer.consume(self.dirfd,BINDINGS,100,100,identity=self.identity,first_started_at=100)
        self.addCleanup(os.close,fd)
        proposed={**self.dispatch.contract,'ledger_sha256':c.digest(c.canonical(value))}
        request=dict(schema='meownero-private-helper/3',operation='provision',sequence=self.dispatch.sequences['outer'],
            contract=proposed,deadline=3700,payload={})
        return self.dispatch.dispatch(request,(fd,))['result']

    def create(self):
        return self.request('observe_and_create',{'staging_sha256':'4'*64},channel='controller')

    def test_planned_absent_W_then_observed_only_after_consumption(self):
        self.assertIsNone(self.dispatch.work)
        self.assertTrue(all(x is None for x in p.render(self.plan)['plan']['planned_storage']['workload']['observed'].values()))
        result=self.provision()
        self.assertEqual(result['observed_work'],work())
        self.assertEqual(self.dispatch.work['user_owner'],[1000,1000])
        self.assertEqual(self.dispatch.work['owner_uid'],0)

    def test_provision_before_durable_consumption_refuses_and_never_rearms(self):
        with self.assertRaises(ValueError):self.request('provision',fds=(self.dirfd,))
        self.assertEqual(self.dispatch.state,'RECOVERY_ONLY')
        with self.assertRaises(ValueError):self.request('retain',fds=(self.dirfd,))
        self.assertNotIn('provision',self.bound.calls)

    def test_lost_custody_ack_retains_obligation(self):
        self.bound.failure='retain'
        with self.assertRaises(OSError):self.request('retain',fds=(self.dirfd,))
        self.assertTrue(self.bound.retained)
        self.assertEqual(self.dispatch.state,'RECOVERY_ONLY')
        self.assertEqual(self.request('recover',deadline=4600)['slot_retained'],True)

    def test_second_admission_and_actual_controller_create_path(self):
        self.provision()
        spec=importlib.util.spec_from_file_location('source_runner',c.HERE/'run-profile.py')
        runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
        fixture=self
        class Bridge:
            def observe_and_create(self,sha,*,deadline):
                return fixture.request('observe_and_create',{'staging_sha256':sha},channel='controller',deadline=deadline)
        result=runner.controller_create(Bridge(),'4'*64,deadline=3700)
        self.assertEqual(result['container_id'],'c'*64)
        order=[x for x in self.bound.calls if x in ('prevalidate','intent','second','create','record_cid')]
        self.assertEqual(order,['prevalidate','intent','second','create','record_cid'])
        self.assertLessEqual(self.bound.create_deadline,105)
        with self.assertRaises(ValueError):self.create()
        self.assertEqual(self.bound.calls.count('create'),1)

    def test_known_bad_start100_create201_deadline200_fails_retains_CID(self):
        self.provision();self.bound.create_delay=101
        # The actual immutable build deadline is 3700, but freshness is tighter;
        # AdmissionGate is also tested below with the review's exact deadline200.
        with self.assertRaises(ValueError):self.create()
        self.assertEqual(self.dispatch.cid,'c'*64)
        self.assertEqual(self.bound.owned,['c'*64])
        self.assertEqual(self.dispatch.state,'RECOVERY_ONLY')
        gatebound=dict(bindings=BINDINGS,attempt_id='1'*32,ledger_sha256='2'*64,build_deadline=200,
            original_lock_witness_sha256='3'*64,create_sha256='4'*64)
        now=[100];gate=m.AdmissionGate(gatebound,clock=lambda:now[0])
        observed=dict(**observation(),**{k:gatebound[k] for k in gatebound if k!='build_deadline'},original_lock=list(c.LOCK_ID))
        def create():now[0]=201;return 'c'*64
        with self.assertRaises(ValueError):gate.create(gatebound,check_peer=lambda:None,check_lock=lambda:None,observe=lambda:observed,create=create)
        self.assertEqual(gate.container_id,'c'*64);self.assertTrue(gate.uncertain)

    def test_slow_observation_consumes_without_create(self):
        self.provision();self.bound.observe_delay=6
        with self.assertRaises(ValueError):self.create()
        self.assertNotIn('create',self.bound.calls)
        with self.assertRaises(ValueError):self.create()

    def test_ambiguous_create_retains_intent_for_recovery(self):
        self.provision();self.bound.failure='create'
        with self.assertRaises(OSError):self.create()
        self.assertIsNotNone(self.dispatch.create_intent)
        self.assertEqual(self.dispatch.state,'RECOVERY_ONLY')

    def test_prevalidation_failure_burns_request(self):
        self.provision();self.bound.failure='prevalidate'
        with self.assertRaises(OSError):self.create()
        self.bound.failure=None
        with self.assertRaises(ValueError):self.create()
        self.assertNotIn('second',self.bound.calls)

    def test_no_arbitrary_command_or_mount_inputs(self):
        self.provision()
        with self.assertRaises(ValueError):self.request('observe_and_create',{'argv':['sh'],'staging_sha256':'4'*64},channel='controller')
        self.assertNotIn('create',self.bound.calls)

    def test_replay_and_changed_contract_are_recovery_only(self):
        request=dict(schema='meownero-private-helper/3',operation='retain',sequence=1,
            contract=self.dispatch.contract,deadline=3700,payload={})
        with self.assertRaises(ValueError):self.dispatch.dispatch(request,(self.dirfd,))
        self.assertEqual(self.dispatch.state,'RECOVERY_ONLY')
        self.assertNotIn('retain',self.bound.calls)

    def test_controller_cannot_call_privileged_lifecycle(self):
        with self.assertRaises(ValueError):self.request('retain',fds=(self.dirfd,),channel='controller')
        self.assertNotIn('retain',self.bound.calls)

    def test_no_phase_rearm_or_deadline_extension(self):
        self.provision();self.create()
        self.request('start_and_wait',dict(container_id='c'*64,phase='build'),channel='controller')
        with self.assertRaises(ValueError):self.request('start_and_wait',dict(container_id='c'*64,phase='build'),channel='controller')
        self.assertEqual(self.bound.calls.count('build'),1)
        self.assertEqual(self.dispatch.contract['deadlines'],dict(build=3700,work=4300,end=4600))

    def test_work_cleanup_retains_C_and_observer_waits_for_own_exit(self):
        self.provision();self.create()
        result=self.request('recover',deadline=4600)
        self.assertTrue(result['control_retained']);self.assertTrue(result['slot_retained'])
        observed=self.request('observe_after_exit',dict(result={'result':'FAIL'}),deadline=4600)
        self.assertEqual(observed['result'],'PENDING_OBSERVER_EXIT')
        with self.assertRaises(ValueError):h.validate_completion(observed,BINDINGS)

    def test_cleanup_failure_keeps_custody_and_quarantine(self):
        self.bound.failure='recover'
        with self.assertRaises(OSError):self.request('recover',deadline=4600)
        self.assertEqual(self.dispatch.state,'RECOVERY_ONLY')
        self.assertNotIn('observer',self.bound.calls)

    def test_modeled_restart_reserved_quarantined_or_corrupt_never_activates(self):
        for state in ('RESERVED','QUARANTINED','CORRUPT'):
            with self.subTest(modeled_state=state):
                backend=Boundary();backend.slot_state=state
                subject=d.Dispatcher(self.plan,contract(self.plan),backend,clock=lambda:100,recovered=True)
                request=dict(schema='meownero-private-helper/3',operation='retain',sequence=0,
                    contract=subject.contract,deadline=3700,payload={})
                with self.assertRaises(ValueError):subject.dispatch(request,(self.dirfd,))
                self.assertNotIn('retain',backend.calls)

    def test_real_seqpacket_client_and_dispatcher_authentication(self):
        left,right=m.private_pair();self.addCleanup(left.close);self.addCleanup(right.close)
        # Real time is transport-only; modeled origin governs injected operations.
        self.dispatch.state='PROVISIONED';self.dispatch.work=work()
        creds=(os.getpid(),os.getuid(),os.getgid())
        errors=[]
        def server():
            try:self.dispatch.serve_one(right,creds,3700,channel='controller')
            except BaseException as error:errors.append(error)
        thread=threading.Thread(target=server);thread.start()
        client=d.Client(left,creds,self.dispatch.contract,check_peer=lambda:None,clock=lambda:100)
        result=client.request('inspect_image',{},deadline=3700)
        thread.join(timeout=2)
        self.assertFalse(thread.is_alive());self.assertEqual(errors,[])
        self.assertEqual(result['image_id'],m.IMAGE)

    def test_dispatcher_unsolicited_FDs_close_and_quarantine(self):
        left,right=m.private_pair();self.addCleanup(left.close);self.addCleanup(right.close)
        before=set(os.listdir('/proc/self/fd'))
        request=dict(schema='meownero-private-helper/3',operation='first_admission',sequence=0,
            contract=self.dispatch.contract,deadline=3700,payload={})
        m.send_packet(left,request,[self.dirfd])
        with self.assertRaises(ValueError):self.dispatch.serve_one(right,(os.getpid(),os.getuid(),os.getgid()),3700)
        self.assertEqual(set(os.listdir('/proc/self/fd')),before)
        self.assertEqual(self.dispatch.state,'RECOVERY_ONLY')

    def test_unproven_custody_barrier_is_not_admission_authority(self):
        original=self.bound.retain_two_fds
        def unproven(*args):return dict(original(*args),independent_pid1_readback=False)
        self.bound.retain_two_fds=unproven
        with self.assertRaises(ValueError):self.request('retain',fds=(self.dirfd,))
        self.assertTrue(self.bound.retained)
        self.assertNotIn('first',self.bound.calls)

    def test_identity_checked_directory_FD_rejects_path_alias_and_foreign_inode(self):
        with self.assertRaises(ValueError):outer.consume(self.root,BINDINGS,100,100,identity=self.identity,first_started_at=100)
        with self.assertRaises(ValueError):outer.consume(self.dirfd,BINDINGS,100,100,identity=[0,0],first_started_at=100)
        d.directory_fd(self.dirfd,self.identity)
        self.root.chmod(0o755)
        with self.assertRaises(ValueError):d.directory_fd(self.dirfd,self.identity)

    def test_outer_typed_server_controller_receipt_and_durable_consumption(self):
        lock=self.root/'disposable.lock';lock.touch(mode=0o600)
        lockinfo=lock.stat()
        with patch.multiple(c,LOCK=lock,LOCK_ID=(lockinfo.st_dev,lockinfo.st_ino)):
            plan=p.source_plan();backend=Boundary();subject=d.Dispatcher(plan,contract(plan),backend,clock=lambda:backend.now)
            left,right=m.private_pair();self.addCleanup(left.close);self.addCleanup(right.close)
            creds=(os.getpid(),os.getuid(),os.getgid())
            def provision(value,ledger,deadline):
                return dict(observed_work=work(),
                    enclosure=dict(mechanism=h.MECHANISM,daemon_mode='platform-authorized-rootful-cgroupfs',
                        cgroup_parent='/owned',workload_cgroup='/owned/work'),
                    recovery=dict(owner=c.PLATFORM,implementation_sha256=BINDINGS['bootstrap_sha256'],kill_scope='/owned/work'))
            backend.provision_owned_work=provision
            def controller(fds,bound,writable,deadline,dispatcher):
                context=json.loads(os.pread(fds[0],65536,0))
                ledger=json.loads(os.pread(fds[2],65536,0))
                h.validate_context(context,ledger,bindings=BINDINGS,now=100)
                request=dict(schema='meownero-private-helper/3',operation='observe_and_create',sequence=0,
                    contract=dispatcher.contract,deadline=3700,payload={'staging_sha256':'4'*64})
                receipt=dispatcher.dispatch(request,channel='controller')['result']
                return dict(exit_code=0,rows=c.empty_rows(),create_receipt=dict(count=1,**receipt))
            backend.run_controller=controller
            errors=[]
            def server():
                try:
                    for i in range(7):subject.serve_one(right,creds,4600)
                except BaseException as error:errors.append(error)
            thread=threading.Thread(target=server,daemon=True);thread.start()
            manager=m.RootfulManager(left,creds,subject.contract,check_peer=lambda:None,clock=lambda:backend.now)
            result=outer.Outer(manager,clock=lambda:backend.now).run(BINDINGS,self.dirfd,ledger_identity=self.identity)
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive());self.assertEqual(errors,[])
            self.assertEqual(result['result'],'PENDING_MANAGER_COMPLETION')
            self.assertTrue((self.root/(BINDINGS['grant_id']+'.json')).exists())
            self.assertEqual(backend.calls.count('create'),1)
            self.assertEqual(subject.state,'RECOVERY_ONLY')


class PacketTests(unittest.TestCase):
    def test_render_pure_without_subprocess_or_resource_access(self):
        import subprocess
        with patch.object(subprocess,'run',side_effect=AssertionError('no execution')), \
             patch.object(os,'open',side_effect=AssertionError('no resource access')):
            packet=p.render(p.source_plan())
        self.assertTrue(packet['unbound'])
        self.assertEqual(packet['observed_storage'],None)
        self.assertEqual(sum(packet['plan']['allocation'].values()),15*p.GIB)
        for record in packet['records']:
            self.assertTrue(set(('uid','gid','writable','charge','deadline','preconditions','failure','recovery'))<=record.keys())
        keeper=next(call for call in packet['units'] if 'keeper.service' in call['args'][0])
        properties={key:value for key,kind,value in keeper['args'][2]}
        self.assertEqual(properties['FileDescriptorStoreMax'],2)
        self.assertEqual(properties['NotifyAccess'],'main')

    def test_all_modes_refuse_unbound_before_OS(self):
        for mode in ('prepare','serve','recover','observe','dispose'):
            with self.subTest(mode=mode),self.assertRaises(ValueError):
                d.authorize_mode(mode,p.source_plan(),c.digest(c.canonical(p.source_plan())),3,4)
        self.assertEqual(d.QUALIFIED_OS,{})
        self.assertEqual(h.QUALIFIED_BOOTSTRAPS,{})

    def test_occupied_and_cumulative_write_ENOSPC_are_separate(self):
        meter=d.Budget();meter.charge(written=3*p.GIB,occupied=p.GIB)
        with self.assertRaises(ValueError):meter.charge(written=2*p.GIB,occupied=p.GIB)
        with self.assertRaises(ValueError):meter.charge(written=0,occupied=0)
        meter=d.Budget()
        with self.assertRaises(ValueError):meter.charge(written=1,occupied=4*p.GIB+1)

    def test_stored_named_FDs_reenter_namespace_never_reset_deadlines(self):
        calls=[]
        with patch.object(os,'set_inheritable'):
            result=d.stored_fds(dict(LISTEN_PID='123',LISTEN_FDS='2',LISTEN_FDNAMES='original-lock:mount-namespace'),
                pid=123,validate_lock=lambda fd:calls.append(('lock',fd)),
                validate_namespace=lambda fd:calls.append(('namespace',fd)),setns=lambda fd,kind:calls.append(('setns',fd,kind)))
        self.assertTrue(result['recovery_only']);self.assertEqual(calls[-1],('setns',4,0x20000))
        with self.assertRaises(ValueError):d.stored_fds({},pid=123,validate_lock=None,validate_namespace=None,setns=None)


    def test_preparation_actual_orchestration_refuses_ENOSPC_without_rearm(self):
        class PreparationBoundary:
            def __init__(self):self.records=[];self.failed=False;self.fail=False
            def apply_preparation_record(self,record,**deadlines):
                self.records.append(record)
                if self.fail and record['phase']=='archive':raise OSError(errno.ENOSPC,'MODELED ENOSPC')
                return dict(written_bytes=1,occupied_bytes=1024)
            def preparation_readback(self):return dict(slot_state='RESERVED',root_slot_owner=[0,0],
                ledger_directory_owner=[1000,1000],observed_work=None,archive_sealed=True,archive_plus_overhead_bytes=1024)
            def preparation_uncertainty_never_rearm(self):self.failed=True
        backend=PreparationBoundary();adapter=d.LifecycleAdapter(backend,clock=lambda:100)
        result=adapter.prepare(p.source_plan())
        self.assertEqual(result['result'],'PREPARED_UNACTIVATED')
        self.assertEqual({r['phase'] for r in backend.records},{'install','control','archive'})
        backend.fail=True;adapter=d.LifecycleAdapter(backend,clock=lambda:100)
        with self.assertRaises(OSError):adapter.prepare(p.source_plan())
        self.assertTrue(backend.failed)
        with self.assertRaises(ValueError):adapter.prepare(p.source_plan())

    def test_no_observed_identity_in_planned_spec(self):
        value=p.source_plan();value['planned_storage']['workload']['observed']['backing_inode']=1
        with self.assertRaises(ValueError):p.render(value)


if __name__=='__main__':unittest.main(verbosity=2)
