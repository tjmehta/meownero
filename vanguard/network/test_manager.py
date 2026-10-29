"""Disposable source fixtures, never a host manager/privilege/runtime test."""
import copy
import fcntl
import json
import os
from pathlib import Path
import socket
import shutil
import tempfile
import time
import unittest
from unittest.mock import patch

import profile_contract as c
import profile_helper as helper
import profile_manager as manager

BINDINGS = dict(grant_id='11111111-1111-4111-8111-111111111111', grant_sha256='a'*64,
    candidate_commit='b'*40, inputs_sha256='c'*64, artifact_sha256='d'*64, bootstrap_sha256='e'*64)
TOKEN = b't'*32
EXPECTED = dict(attempt_id='1'*32, bindings=BINDINGS, activation_sha256=c.digest(TOKEN))


def binding():
    root, control_root = '/synthetic/TJS2504/work', '/synthetic/TJS2504/control'
    value = dict(schema='meownero-rootful-helper-binding/2', attempt_id='1'*32, bindings=BINDINGS,
        operator='SYNTHETIC_NO_OPERATOR', authority_comment='SYNTHETIC_NO_AUTHORITY',
        systemd_version='255-documentation-only', helper_source_sha256='f'*64,
        preparation_receipt='SYNTHETIC_NOT_PREPARED', original_lock=list(c.LOCK_ID), limits=c.LIMITS,
        disk=dict(mount=root,backing='/synthetic/TJS2504/fixed.img',backing_filesystem='ext4',
            backing_device=66306,backing_inode=123,fully_allocated=True,length=11*helper.GIB,
            allocated_bytes=11*helper.GIB,filesystem='ext4',filesystem_capacity=10*helper.GIB,
            filesystem_device=999,nlink=1,loop='/dev/loop99',loop_device=999,mount_id=1234,namespace_inode=5678,
            owner_uid=0,owner_gid=0,backing_mode=0o600,mount_mode=0o700,identity_mutable=False),
        allocation=dict(control=helper.GIB,workload=11*helper.GIB,archive=2*helper.GIB,other=helper.GIB),
        control_reserves=dict(state=64*1024**2,log=256*1024**2,export=512*1024**2,overhead=192*1024**2),
        writes={x:(control_root if x in helper.CONTROL_PATHS else root)+'/'+x
                for x in helper.CONTROL_PATHS | helper.WORK_PATHS},
        writable_escape=False, shared_sockets_visible=False,
        offline_image=dict(image_id=manager.IMAGE, architecture='amd64',os='linux',read_only=True,immutable=True,
            path='/synthetic/immutable/builder.tar',length=1,device=1,inode=2,provenance='SYNTHETIC',sha256='9'*64),
        cgroup_parent='/synthetic/owned/meownero-TJS2504-'+'1'*32, existing_delegation=True)
    value['control_disk'] = {**value['disk'], 'mount':control_root, 'backing':'/synthetic/TJS2504/control.img',
        'backing_inode':124,'length':helper.GIB,'allocated_bytes':helper.GIB,
        'filesystem_capacity':900*1024**2,'filesystem_device':998,'loop':'/dev/loop98','loop_device':998,'mount_id':1235,
        'writable_by_workload':False,'prepared_before_first_admission':True,
        'custodian':'SYNTHETIC_NO_CUSTODIAN','custody_receipt':'SYNTHETIC_NOT_PREPARED',
        'retention':'explicit_authorized_disposition_only','restart':'recovery_only',
        'missing_or_corrupt':'quarantine_never_rearm'}
    value['control_identity_sha256'] = c.digest(c.canonical(value['control_disk']))
    return value


def consumption(value):
    return dict(attempt_id=value['attempt_id'],bindings=value['bindings'],
                control_identity_sha256=value.get('control_identity_sha256'),first_admission='PASS',
                manager_state='QUARANTINED',local_state='CONSUMED')


def command_plan(value):
    return helper.command_manifest(value,consumption=consumption(value))


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='TJS2504-source-manager-')
        self.root = Path(self.temp.name)
        self.path = self.root/'manager-slot'
        self.path.write_bytes(c.canonical(dict(schema='meownero-manager-slot/1', state='RESERVED', **EXPECTED)))
        self.path.chmod(0o600)
        self.fd = os.open(self.path, os.O_RDWR | os.O_CLOEXEC)

    def tearDown(self):
        os.close(self.fd)
        self.temp.cleanup()

    def test_quarantine_survives_local_ledger_deletion(self):
        journal = manager.GrantJournal(self.fd, EXPECTED)
        receipt = journal.quarantine(BINDINGS, activation=TOKEN, deadline=200, clock=lambda:100)
        local = self.root/'local-ledger'
        local.write_text('CONSUMED');local.unlink()
        self.assertEqual(receipt['state'], 'QUARANTINED')
        with self.assertRaises(ValueError): manager.GrantJournal(self.fd, EXPECTED)

    def test_workload_cleanup_cannot_rearm_persistent_control(self):
        # Real disposable removal, not a host mount/crash-survival observation.
        work = self.root/'work'
        work.mkdir()
        (work/'local-copy').write_text('CONSUMED')
        journal = manager.GrantJournal(self.fd, EXPECTED)
        journal.quarantine(BINDINGS, activation=TOKEN, deadline=200, clock=lambda:100)
        before = self.path.read_bytes()
        identity = (self.path.stat().st_dev,self.path.stat().st_ino)
        shutil.rmtree(work)
        self.assertEqual(self.path.read_bytes(),before)
        self.assertEqual((self.path.stat().st_dev,self.path.stat().st_ino),identity)
        with self.assertRaises(ValueError): manager.GrantJournal(self.fd, EXPECTED)

    def test_local_corruption_cannot_rearm_manager(self):
        journal = manager.GrantJournal(self.fd, EXPECTED)
        journal.quarantine(BINDINGS, activation=TOKEN, deadline=200, clock=lambda:100)
        (self.root/'local-ledger').write_text('{corrupt')
        with self.assertRaises(ValueError): journal.quarantine(BINDINGS, activation=TOKEN,deadline=200)
        with self.assertRaises(ValueError): manager.GrantJournal(self.fd, EXPECTED)

    def test_recovered_reserved_slot_is_recovery_only(self):
        journal = manager.GrantJournal(self.fd, EXPECTED, recovered=True)
        with self.assertRaises(ValueError): journal.quarantine(BINDINGS,activation=TOKEN,deadline=200,clock=lambda:100)

    def test_fsync_failure_never_retries(self):
        journal = manager.GrantJournal(self.fd, EXPECTED)
        with patch.object(os, 'fsync', side_effect=OSError('fixture sync failure')):
            with self.assertRaises(OSError): journal.quarantine(BINDINGS,activation=TOKEN,deadline=200,clock=lambda:100)
        with self.assertRaises(ValueError): journal.quarantine(BINDINGS,activation=TOKEN,deadline=200,clock=lambda:100)
        with self.assertRaises(ValueError): manager.GrantJournal(self.fd, EXPECTED)

    def test_crash_before_write_cannot_cold_resume(self):
        journal = manager.GrantJournal(self.fd, EXPECTED)
        with patch.object(manager.outer, 'write_all', side_effect=OSError('fixture prewrite crash')):
            with self.assertRaises(OSError): journal.quarantine(BINDINGS,activation=TOKEN,deadline=200,clock=lambda:100)
        recovered = manager.GrantJournal(self.fd, EXPECTED, recovered=True)
        with self.assertRaises(ValueError): recovered.quarantine(BINDINGS,activation=TOKEN,deadline=200,clock=lambda:100)

    def test_hash_in_slot_is_not_activation_secret(self):
        journal = manager.GrantJournal(self.fd, EXPECTED)
        with self.assertRaises(ValueError):
            journal.quarantine(BINDINGS, activation=EXPECTED['activation_sha256'],deadline=200,clock=lambda:100)
        with self.assertRaises(ValueError): journal.quarantine(BINDINGS,activation=TOKEN,deadline=200,clock=lambda:100)

    def test_changed_grant_and_expiry_refuse(self):
        for change in ('grant','deadline'):
            journal = manager.GrantJournal(self.fd, EXPECTED)
            with self.assertRaises(ValueError):
                journal.quarantine({**BINDINGS,'grant_id':'foreign'} if change=='grant' else BINDINGS,
                    activation=TOKEN,deadline=99 if change=='deadline' else 200,clock=lambda:100)

    def test_missing_corrupt_alias_slot_refuses(self):
        for raw in (b'', b'{corrupt', c.canonical({'state':'RESERVED'})):
            os.ftruncate(self.fd,0);os.pwrite(self.fd,raw,0)
            with self.assertRaises((ValueError,KeyError)): manager.GrantJournal(self.fd,EXPECTED)
        self.assertFalse((self.root/'missing').exists())


class ChannelTests(unittest.TestCase):
    def setUp(self):
        self.left,self.right = manager.private_pair()
        self.creds=(os.getpid(),os.getuid(),os.getgid())

    def tearDown(self):
        self.left.close();self.right.close()

    def test_authenticated_packet_and_real_duplicate_description(self):
        with tempfile.TemporaryFile() as lock:
            fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
            manager.send_packet(self.left,{'fixture':'only'},[lock.fileno()])
            value,fds=manager.receive_packet(self.right,self.creds,time.monotonic()+2,fd_count=1)
            try:
                self.assertEqual(value,{'fixture':'only'})
                os.lseek(fds[0],17,os.SEEK_SET)
                self.assertEqual(os.lseek(lock.fileno(),0,os.SEEK_CUR),17)
                self.assertFalse(os.get_inheritable(fds[0]))
            finally:os.close(fds[0])

    def test_wrong_sender_refuses(self):
        manager.send_packet(self.left,{'fixture':True})
        with self.assertRaises(ValueError): manager.receive_packet(self.right,(os.getpid()+1,*self.creds[1:]),time.monotonic()+2)

    def test_packet_credentials_identify_actual_child_after_fork(self):
        child=os.fork()
        if child==0:
            try:
                self.right.close()
                manager.send_packet(self.left,{'disposable_child':True})
            finally:os._exit(0)
        try:
            value,_=manager.receive_packet(self.right,(child,os.getuid(),os.getgid()),time.monotonic()+2)
            self.assertEqual(value,{'disposable_child':True})
        finally:
            _,status=os.waitpid(child,0)
        self.assertEqual(os.waitstatus_to_exitcode(status),0)

    def test_unsolicited_descriptors_closed(self):
        before=set(os.listdir('/proc/self/fd'))
        with tempfile.TemporaryFile() as file:
            manager.send_packet(self.left,{},[file.fileno()])
            with self.assertRaises(ValueError): manager.receive_packet(self.right,self.creds,time.monotonic()+2)
        self.assertEqual(set(os.listdir('/proc/self/fd')),before)

    def test_invalid_and_noncanonical_packets_refuse(self):
        for raw in (b'{} ',b'[]',b'{'):
            self.left.send(raw)
            with self.assertRaises(ValueError): manager.receive_packet(self.right,self.creds,time.monotonic()+2)

    def test_oversize_and_expired_refuse(self):
        with self.assertRaises(ValueError): manager.send_packet(self.left,{'huge':'x'*manager.MAX_PACKET})
        with self.assertRaises(ValueError): manager.receive_packet(self.right,self.creds,time.monotonic()-1)

    def test_notification_is_not_accepted_without_barrier(self):
        with tempfile.TemporaryFile() as file:
            with self.assertRaises(ValueError):
                manager.store_lock(self.left,file.fileno(),deadline=time.monotonic()-1)
        # No systemd was contacted. A fixture listener holding the barrier FD
        # does not acknowledge custody or make a notification a host witness.

    def test_client_rejects_wrong_bound_reply(self):
        client=manager.RootfulManager(self.left,self.creds,BINDINGS,check_peer=lambda:None)
        manager.send_packet(self.right,dict(sequence=0,ok=True,request_sha256='wrong',result={}))
        with self.assertRaises(ValueError):client.request('retain',{},deadline=time.monotonic()+2)

    def test_client_never_launches_unqualified_controller(self):
        client=manager.RootfulManager(self.left,self.creds,BINDINGS,check_peer=lambda:None)
        with self.assertRaises(ValueError):client.run_controller(3,4,5,None,deadlines={})
        self.assertEqual(client.sequence,0)


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.clock=100
        self.request=dict(bindings=BINDINGS,attempt_id='1'*32,ledger_sha256='2'*64,build_deadline=200,
                          original_lock_witness_sha256='3'*64,create_sha256='4'*64)
        self.observed=dict(at=100,started_at=100,bindings=BINDINGS,attempt_id='1'*32,ledger_sha256='2'*64,
            original_lock_witness_sha256='3'*64,create_sha256='4'*64,
            original_lock=list(c.LOCK_ID),snapshot=dict(available_memory_bytes=5*1024**3,
            free_disk_bytes=20*1024**3,load=[0,0,0],native_processes=[],native_containers=[]))
        self.calls=[]
        self.gate=manager.AdmissionGate(self.request,clock=lambda:self.clock)

    def run_gate(self,request=None):
        return self.gate.create(self.request if request is None else request,
            check_peer=lambda:self.calls.append('peer'),check_lock=lambda:self.calls.append('lock'),
            observe=lambda:copy.deepcopy(self.observed),create=lambda:self.calls.append('create') or 'c'*64)

    def test_positive_then_one_use_refusal(self):
        self.assertEqual(self.run_gate()['container_id'],'c'*64)
        with self.assertRaises(ValueError):self.run_gate()
        self.assertEqual(self.calls.count('create'),1)

    def test_every_full_observation_field_prevents_create(self):
        for field,value in [('available_memory_bytes',5*1024**3-1),('free_disk_bytes',20*1024**3-1),
                            ('load',[0,0,7]),('native_processes',['fixture']),('native_containers',['fixture'])]:
            with self.subTest(field=field):
                self.gate=manager.AdmissionGate(self.request,clock=lambda:self.clock)
                observed=copy.deepcopy(self.observed);self.observed['snapshot'][field]=value
                with self.assertRaises(ValueError):self.run_gate()
                self.observed=observed
        self.assertNotIn('create',self.calls)

    def test_stale_observation_consumes_channel(self):
        self.observed['at']=94
        with self.assertRaises(ValueError):self.run_gate()
        self.observed['at']=100
        with self.assertRaises(ValueError):self.run_gate()
        self.assertNotIn('create',self.calls)

    def test_attempt_grant_ledger_or_lock_mismatch_refuses(self):
        for key in ('bindings','attempt_id','ledger_sha256','original_lock',
                    'original_lock_witness_sha256','create_sha256'):
            with self.subTest(key=key):
                self.gate=manager.AdmissionGate(self.request,clock=lambda:self.clock)
                value=self.observed[key];self.observed[key]='wrong'
                with self.assertRaises(ValueError):self.run_gate()
                self.observed[key]=value
        self.assertNotIn('create',self.calls)

    def test_first_field_of_long_observation_is_too_old(self):
        self.observed['started_at']=94
        with self.assertRaises(ValueError):self.run_gate()
        self.assertNotIn('create',self.calls)

    def test_expired_create_and_bad_request_refuse(self):
        with self.assertRaises(ValueError):self.run_gate({**self.request,'attempt_id':'different'})
        self.gate=manager.AdmissionGate(self.request,clock=lambda:201)
        with self.assertRaises(ValueError):self.run_gate()
        self.assertNotIn('create',self.calls)


class HelperManifestTests(unittest.TestCase):
    def test_command_plan_keeps_fixed_paths_and_limits(self):
        value=binding();plan=command_plan(value)
        self.assertEqual(plan['cgroup_writes']['/sys/fs/cgroup'+value['cgroup_parent']+'/memory.max'],str(4*helper.GIB))
        self.assertTrue(plan['source_only'])
        self.assertEqual(plan['import_image'][-1],value['offline_image']['path'])
        self.assertNotIn('/var/run/docker.sock',json.dumps(plan))
        self.assertEqual(plan['activation'],'REFUSED_UNQUALIFIED')

    def test_storage_escape_sparse_oversize_foreign_mount_refuse(self):
        mutations=[('length',15*helper.GIB+1),('fully_allocated',False),('allocated_bytes',1),
            ('backing_filesystem','xfs'),('backing_device',1),('nlink',2),('namespace_inode',0)]
        for key,value in mutations:
            candidate=binding();candidate['disk'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):command_plan(candidate)
        for key in binding()['writes']:
            candidate=binding();candidate['writes'][key]='/escape'
            with self.subTest(write=key),self.assertRaises(ValueError):command_plan(candidate)

    def test_image_identity_missing_provenance_or_mutability_refuse(self):
        for key,value in [('image_id','sha256:'+'0'*64),('sha256',''),('provenance',''),
                          ('read_only',False),('immutable',False),('architecture','arm64')]:
            candidate=binding();candidate['offline_image'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):command_plan(candidate)

    def test_proposed_split_charges_retained_control_and_workload_cleanup_only(self):
        value=binding();plan=command_plan(value)
        self.assertEqual(plan['storage_fit']['charged_bytes'],15*helper.GIB)
        self.assertEqual(plan['storage_fit']['residual_workload_bytes'],11*helper.GIB)
        self.assertEqual(plan['control_retained'],value['control_disk'])
        self.assertNotIn(value['control_disk']['mount'],json.dumps(plan['cleanup']))
        self.assertNotIn(value['control_disk']['loop'],json.dumps(plan['cleanup']))
        self.assertIn(value['disk']['mount'],json.dumps(plan['cleanup']))

    def test_single_disk_legacy_contract_and_missing_control_refuse(self):
        value=binding();value['schema']='meownero-rootful-helper-binding/1'
        with self.assertRaises(ValueError):command_plan(value)
        for key in ('allocation','control_disk','control_identity_sha256','control_reserves'):
            value=binding();del value[key]
            with self.subTest(key=key),self.assertRaises(ValueError):command_plan(value)

    def test_split_rejects_zero_negative_overflow_bool_and_full_workload(self):
        for name,amount in [('control',0),('workload',0),('archive',-1),('other',True),
                            ('workload',15*helper.GIB),('control',2**64),('archive',2*helper.GIB+1)]:
            value=binding();value['allocation'][name]=amount
            with self.subTest(name=name,amount=amount),self.assertRaises(ValueError):command_plan(value)

    def test_control_identity_custody_mutability_and_alias_refuse(self):
        for key,amount in [('identity_mutable',True),('mount_id',0),('owner_uid',1),('backing_mode',0o666),
                           ('custodian',''),('custody_receipt',''),('writable_by_workload',True),
                           ('prepared_before_first_admission',False),('restart','normal'),
                           ('missing_or_corrupt','replace'),('retention','delete_after_work'),
                           ('backing',binding()['disk']['backing']),('loop_device',999),
                           ('mount',binding()['disk']['mount']+'/nested'),('namespace_inode',123)]:
            value=binding();value['control_disk'][key]=amount
            value['control_identity_sha256']=c.digest(c.canonical(value['control_disk']))
            with self.subTest(key=key),self.assertRaises(ValueError):command_plan(value)
        value=binding();value['control_disk']['mount_id']+=1
        with self.assertRaises(ValueError):command_plan(value)

    def test_capacity_and_preparation_archive_copies_must_fit(self):
        for field,amount in [('length',helper.GIB+1),('allocated_bytes',helper.GIB+512),
                             ('filesystem_capacity',800*1024**2)]:
            value=binding();value['control_disk'][field]=amount
            value['control_identity_sha256']=c.digest(c.canonical(value['control_disk']))
            with self.subTest(field=field),self.assertRaises(ValueError):command_plan(value)
        value=binding();value['control_reserves']['overhead']+=1
        with self.assertRaises(ValueError):command_plan(value)
        value=binding();value['offline_image']['length']=2*helper.GIB+1
        with self.assertRaises(ValueError):command_plan(value)

    def test_provisioning_refuses_before_both_durable_consumptions(self):
        value=binding()
        for field,bad in [('first_admission','NOT_RUN'),('manager_state','RESERVED'),
                          ('local_state','MISSING'),('control_identity_sha256','0'*64),
                          ('attempt_id','2'*32),('bindings',{})]:
            witness=consumption(value);witness[field]=bad
            with self.subTest(field=field),self.assertRaises(ValueError):
                helper.command_manifest(value,consumption=witness)

    def test_task_only_service_and_explicit_survival_gaps(self):
        contract=helper.unit_contract(binding())
        self.assertTrue(contract['unit'].startswith('meownero-TJS2504-'))
        self.assertEqual(contract['keeper_service']['FileDescriptorStorePreserve'],'yes')
        self.assertEqual(contract['keeper_service']['StandardOutput'],'null')
        self.assertTrue(contract['unresolved'])
        self.assertEqual(contract['native_execution'],'NOT_RUN')

    def test_paths_reject_shell_and_systemd_substitution(self):
        for path in ('/a/../b','/a//b','/a\nb','/a b','/a%nb','relative'):
            with self.assertRaises(ValueError):helper.absolute(path)

    def test_incomplete_or_foreign_recovery_never_releases(self):
        candidate=binding()
        valid=dict(attempt_id=candidate['attempt_id'],namespace_inode=candidate['disk']['namespace_inode'],
            loop_device=candidate['disk']['loop_device'],mount_id=candidate['disk']['mount_id'],
            work_population=0,daemon_helpers=[],remaining_cids=[],remaining_owned_pid_start_pairs=[],
            local_ledger_removed=False,manager_slot_removed=False,lock_still_held=True,
            control_retained=True,control_identity_sha256=candidate['control_identity_sha256'])
        self.assertEqual(helper.validate_recovery(valid,candidate),valid)
        for key,value in [('work_population',1),('namespace_inode',1),('remaining_cids',['c'*64]),
                          ('manager_slot_removed',True),('lock_still_held',False),('control_retained',False),
                          ('control_identity_sha256','0'*64)]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                helper.validate_recovery({**valid,key:value},candidate)


if __name__ == '__main__':unittest.main(verbosity=2)
