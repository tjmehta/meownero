"""Adverse source contracts, with synthetic contexts and disposable FD locks only."""
import copy
import fcntl
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import profile_contract as c
import profile_handoff as h


def fixture():
    binding = dict(grant_id='new',grant_sha256='g',candidate_commit='c',inputs_sha256='i',
                   artifact_sha256='a',bootstrap_sha256='b'*64)
    ledger = dict(schema='meownero-consumed-ledger/3',state='CONSUMED',bindings=binding,
                  origin=100,consumed_at=102,first_started_at=101)
    context = dict(schema='meownero-private-handoff/2',bindings=binding,
        origin=100,consumed_at=102,durable_consumed_at=102,provisioned_at=103,
        first_admission=dict(at=101,started_at=101,snapshot=dict(available_memory_bytes=5*1024**3,
            free_disk_bytes=20*1024**3,load=[0,0,0],native_processes=[],native_containers=[])),
        ledger=dict(sha256=c.digest(c.canonical(ledger))),
        deadlines=dict(build=3700,work=4300,end=4600),
        enclosure=dict(mechanism=h.MECHANISM,daemon_mode='platform-authorized-rootful-cgroupfs',
                       cgroup_parent='/attempt',workload_cgroup='/attempt/work'),
        recovery=dict(owner=c.PLATFORM,implementation_sha256='b'*64,kill_scope='/attempt/work'))
    return context,ledger,binding


class HandoffTests(unittest.TestCase):
    def test_no_manifest_value_substitutes_for_a_qualified_launcher(self):
        for sha in (None,'b'*64):
            with self.subTest(sha=sha),self.assertRaises(ValueError):
                h.require_bootstrap(dict(platform_bootstrap_sha256=sha))
        self.assertEqual(h.QUALIFIED_BOOTSTRAPS,{})

    def test_nonnull_hash_refuses_before_grant_resource_or_native_calls(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('handoff_runner',c.HERE/'run-profile.py')
        runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
        with patch.object(runner.subprocess,'check_output',side_effect=['candidate\n','']), \
             patch.object(runner,'check_inputs',return_value={'platform_bootstrap_sha256':'b'*64}), \
             patch.object(runner,'api') as api,patch.object(runner,'read_enclosure') as enclosure, \
             patch.object(runner.os,'open') as opened,patch.object(runner,'controller_create') as admission, \
             patch.object(runner.sys,'argv',['run-profile.py','--grant-comment',
                 '11111111-1111-4111-8111-111111111111','--artifact-sha256','pending']):
            with self.assertRaisesRegex(ValueError,'no qualified outer implementation'):runner.main()
            for operation in (api,enclosure,opened,admission):operation.assert_not_called()

    def check(self,context,ledger,binding,now=104):
        return h.validate_context(context,ledger,bindings=binding,now=now)

    def test_every_context_and_ledger_binding_is_exact(self):
        value,ledger,binding=fixture();self.check(value,ledger,binding)
        for key in binding:
            for target in ('context','ledger'):
                v,l=copy.deepcopy((value,ledger))
                (v if target=='context' else l)['bindings'][key]='other'
                with self.subTest(key=key,target=target),self.assertRaises(ValueError):self.check(v,l,binding)

    def test_no_reconstructed_unconsumed_or_changed_ledger(self):
        value,ledger,binding=fixture()
        for key,bad in [('state','NEW'),('origin',99),('consumed_at',103),('schema','old')]:
            changed=dict(ledger,**{key:bad})
            with self.subTest(key=key),self.assertRaises(ValueError):self.check(value,changed,binding)

    def test_admission_precedes_consumption_and_provisioning(self):
        value,ledger,binding=fixture()
        for path,bad in [('first_admission.at',103),('consumed_at',104),('provisioned_at',101),
                         ('origin',float('nan')),('first_admission.at',float('inf'))]:
            changed=copy.deepcopy(value);keys=path.split('.');target=changed
            for key in keys[:-1]:target=target[key]
            target[keys[-1]]=bad
            with self.subTest(path=path),self.assertRaises(ValueError):self.check(changed,ledger,binding)
        for now in (99,3700):
            with self.assertRaises(ValueError):self.check(value,ledger,binding,now)

    def test_stale_admission_and_changed_reserve_are_refused(self):
        value,ledger,binding=fixture()
        value['consumed_at']=110;value['durable_consumed_at']=110;value['provisioned_at']=111
        ledger['consumed_at']=110;value['ledger']['sha256']=c.digest(c.canonical(ledger))
        with self.assertRaisesRegex(ValueError,'stale'):self.check(value,ledger,binding,112)
        value,ledger,binding=fixture();value['deadlines']['work']+=1
        with self.assertRaises(ValueError):self.check(value,ledger,binding)

    def test_rootless_and_parent_kill_cannot_satisfy_recovery(self):
        value,ledger,binding=fixture()
        for section,key,bad in [('enclosure','daemon_mode','rootless'),
                                ('recovery','kill_scope','/attempt'),
                                ('recovery','implementation_sha256','assertion'),
                                ('recovery','owner','inner')]:
            changed=copy.deepcopy(value);changed[section][key]=bad
            with self.subTest(key=key),self.assertRaises(ValueError):self.check(changed,ledger,binding)

    def test_inherited_flock_is_visible_and_inner_close_preserves_outer(self):
        # This lock is a new disposable test file, never the original heavy inode.
        with tempfile.TemporaryFile() as outer:
            fcntl.flock(outer,fcntl.LOCK_EX|fcntl.LOCK_NB)
            inherited=os.dup(outer.fileno())
            other=os.open('/proc/self/fd/'+str(outer.fileno()),os.O_RDWR)
            info=os.fstat(outer.fileno())
            try:
                with patch.object(c,'LOCK_ID',(info.st_dev,info.st_ino)):
                    h.lock_witness(Path(f'/proc/self/fdinfo/{inherited}').read_text(),os.getpid())
                    with self.assertRaises(ValueError):
                        h.lock_witness(Path(f'/proc/self/fdinfo/{other}').read_text(),os.getpid())
                    os.close(inherited);inherited=None
                    with self.assertRaises(BlockingIOError):fcntl.flock(other,fcntl.LOCK_EX|fcntl.LOCK_NB)
                    h.lock_witness(Path(f'/proc/self/fdinfo/{outer.fileno()}').read_text(),os.getpid())
            finally:
                if inherited is not None:os.close(inherited)
                os.close(other)

    def test_inner_cannot_finalize_resource_or_cleanup_success(self):
        rows=c.empty_rows()
        for name,keys in c.REQUIRED.items():
            for key in keys:rows[name][key]={'status':'PASS'}
        self.assertEqual(c.verdict(h.inner_rows(rows)),'INCOMPLETE')
        for name in ('resources.json','cleanup.json'):
            self.assertTrue(all(row['status']=='NOT_RUN' for row in rows[name].values()))

    def test_runtime_facts_are_not_immutable_authorization(self):
        from test_profile import grant,check_grant
        comment,value=grant()
        for key in ('enclosure','ledger_directory'):
            with self.subTest(key=key),self.assertRaises(ValueError):check_grant(comment,dict(value,**{key:{}}))

    def test_completion_refuses_survivors_missing_release_and_dead_observer(self):
        _,_,bindings=fixture()
        rows=c.empty_rows()
        for name in ('resources.json','cleanup.json'):
            for key in rows[name]:rows[name][key]={'status':'PASS'}
        value=dict(schema='meownero-outer-completion/3',bindings=bindings,
            original_lock_identity=list(c.LOCK_ID), origin=100,observed_at=4405,
            exits={name:dict(at=4400+i,pid_identity=[i+1,'1']) for i,name in
                enumerate(('workload','cleanup','keeper','observer'))},
            lifecycle=dict(task_scoped=True,authenticated=True,pid_identity=[99,'1'],observer_exit_witness=True),
            result='COMPLETE_AFTER_OBSERVER_EXIT',aggregate_cpu_usec=100,memory_peak=100,pids_peak=10,
            occupied_bytes=1024,overhead_qualified=True,tail_charged=True,
            recursive_population=dict(work=0,control=0),live_owned_pid_identities=[],remaining_cids=[],
            remaining_work_mounts=[],remaining_work_loops=[],remaining_daemon_helpers=[],active_owned_units=[],
            open_lock_descriptors=[],pid1_stored_fd_names=[],
            retained_control=dict(slot_retained=True,archive_retained=True,
                mount_disposition='normal_unmounted_namespace_closed',custodian='MODELED',
                disposition='separate_explicit_authority',grant_state='QUARANTINED_NEVER_REARM',identity_sha256='a'*64),
            original_lock_release_witness='independent_nonblocking_acquire_then_close',rows=rows)
        h.validate_completion(value,bindings)
        for key,bad in [('remaining_daemon_helpers',[[1,'1']]),('remaining_work_mounts',['owned']),
                        ('remaining_work_loops',['owned']),('remaining_cids',['owned']),
                        ('live_owned_pid_identities',[[1,'1']]),('active_owned_units',['owned']),
                        ('open_lock_descriptors',[3]),('original_lock_release_witness','inner_assertion'),
                        ('recursive_population',dict(work=1,control=0)),('tail_charged',False),
                        ('observed_at',4399),('observed_at',4601),('aggregate_cpu_usec',9000*1000000+1),
                        ('lifecycle',dict(task_scoped=True,authenticated=True,pid_identity=[4,'1'],observer_exit_witness=True))]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                h.validate_completion(dict(value,**{key:bad}),bindings)
        value['rows']['cleanup.json']['lock_released']['status']='NOT_RUN'
        with self.assertRaises(ValueError):h.validate_completion(value,bindings)


if __name__=='__main__':unittest.main()
