"""Real disposable root main/FD/journal fixtures, injected authority and OS effects.

The constructor anchor is TEST authority. No installed operator, privileged
adapter, host crash/power loss, storage enclosure or native outcome is tested.
"""
import copy
import fcntl
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock,patch

import profile_bootstrap as b
import profile_contract as c
import profile_dispatch as d
import profile_executor as e
import profile_ingress as i
import profile_manager as m
import profile_packet as p
import profile_runtime as r
from test_executor import InjectedBoundary


class TestRecordAuthority:
    """Explicit TEST-only authority for local journal/transport fixtures.

    No surviving-owner or installed-launch claim; test_supervisor exercises the
    separate real source process instead of this intentionally injected stub.
    """
    def authenticate(self,anchor):return True
    def recovery_position(self,record):return None
    def admit(self,record):pass
    def complete(self,record):pass
    def uncertain(self,record):pass


class IngressTests(unittest.TestCase):
    def setUp(self,*,itinerary=None):
        self.temp=tempfile.TemporaryDirectory(prefix='TJS2504-ingress-source-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.control=self.root/'control';self.control.mkdir(mode=0o700)
        self.dirfd=os.open(self.control,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
        self.addCleanup(os.close,self.dirfd)
        self.install=self.root/'helper';self.install.mkdir()
        index=(c.HERE/'integration/inputs.json').read_bytes()
        inventory=c.json_file(c.HERE/'integration/installation-inventory.json')
        for members in inventory['groups'].values():
            for name,destination in members.items():
                dest=self.install/destination;dest.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(c.HERE.parent.parent/name,dest)
        (self.install/'runtime/vanguard/network/integration/inputs.json').write_bytes(index)
        self.plan=p.source_plan();self.plan['attempt_id']='1'*32
        self.plan['source']=dict(commit='b'*40,inputs_sha256=c.digest(index),artifact_sha256='d'*64,
            helper_sha256=c.digest((c.HERE/'profile-helper.py').read_bytes()))
        spec=c.digest(c.canonical(self.plan))
        self.contract=dict(bindings=dict(grant_id='11111111-1111-4111-8111-111111111111',grant_sha256='a'*64,
            candidate_commit='b'*40,inputs_sha256=c.digest(index),artifact_sha256='d'*64,bootstrap_sha256='e'*64),
            attempt_id='1'*32,spec_sha256=spec,archive_sha256='f'*64,image_id=m.IMAGE,ledger_sha256=None,
            original_lock_witness_sha256='2'*64,origin=100,deadlines=dict(build=3700,work=4300,end=4600))
        d.validate_contract(self.contract)
        self.records=p.render(self.plan)['records']
        self.cleanup=next(x['sequence'] for x in self.records if x['phase']=='cleanup')
        self.itinerary=[0,1,self.cleanup] if itinerary is None else list(itinerary)
        self.recovery=[self.cleanup] if itinerary is None else [n for n in self.itinerary
            if self.records[n]['phase'] in ('cleanup','completion')]
        self.binding=dict(contract_sha256=c.digest(c.canonical(self.contract)),inputs_sha256=c.digest(index),
            origin=100,deadlines=self.contract['deadlines'],preparation=dict(origin=100,archive_origin=100))
        self.secret=b'x'*32
        reserved=r.reserve_record_state(self.dirfd,self.binding,self.itinerary,self.recovery,
            self.secret,owner_uid=os.getuid())
        self.expected=reserved['capability_expected'];self.identities=reserved['capability_identities']
        self.order=self.control/'record-order';self.order_identity=reserved['order_identity']
        self.index=index;self.backend=InjectedBoundary()
        self.backend.authenticate_executor=lambda plan:dict(W='/fixture/W',BOUND_HELPER_AND_SPEC_BYTES='MODELED_BYTES')
        self.backend.authenticate_root_entry=lambda:copy.deepcopy(self.plan)
        self.backend.syscall=Mock(side_effect=lambda *args:self.backend.calls.append('effect'))
        self.backend.docker=Mock(side_effect=lambda *args:self.backend.calls.append('effect'))
        self.sender_identity=i.process_identity(os.getpid())
        spec=importlib.util.spec_from_file_location('root_ingress_fixture',c.HERE/'profile-root-helper.py')
        self.module=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.module)

    def path_identity(self,path):
        info=path.stat();return [info.st_dev,info.st_ino]

    def memfd(self,raw,*,sealed=True):
        fd=os.memfd_create('TJS2504-source',os.MFD_CLOEXEC|os.MFD_ALLOW_SEALING)
        self.addCleanup(os.close,fd);os.write(fd,raw)
        if sealed:fcntl.fcntl(fd,fcntl.F_ADD_SEALS,b.SEALS)
        return fd

    def other_authority(self):
        sender,receiver=b.delivery_pair()
        self.addCleanup(sender.close);self.addCleanup(receiver.close)
        return receiver.fileno()

    def invocation(self,n=0,*,recovered=False,mutate=None,anchor_mutate=None,unsealed=False):
        tx,rx=b.delivery_pair();self.addCleanup(tx.close);self.addCleanup(rx.close)
        atx,arx=b.delivery_pair();self.addCleanup(atx.close);self.addCleanup(arx.close)
        delivery=dict(schema='meownero-helper-bootstrap/1',task='TJS-2504',attempt_id='1'*32,
            role='observer' if recovered else 'keeper',mode='observe' if recovered else 'serve',invocation_id=os.urandom(16).hex(),
            source=self.plan['source'],spec_sha256=c.digest(c.canonical(self.plan)),
            contract_sha256=self.binding['contract_sha256'],origin=100,deadlines=self.contract['deadlines'],
            sender_credentials=[os.getpid(),os.getuid(),os.getgid()],sender_start=self.sender_identity['start'],
            delivery_deadline=104,namespace_identity=55)
        context=dict(schema='meownero-helper-bootstrap-context/1',delivery=delivery,contract=self.contract)
        ctx=self.memfd(c.canonical(context),sealed=not unsealed);idx=self.memfd(self.index)
        record=self.records[n]
        envelope=dict(schema='meownero-root-ingress/1',delivery=delivery,
            request=dict(operation=record['operation'],record=n,deadline=p.operation_deadline(self.plan,n,self.binding)),
            activation=self.secret.hex(),recovery_only=recovered)
        anchor=dict(schema='meownero-root-trust/1',plan=self.plan,inputs_raw=self.index,
            envelope=copy.deepcopy(envelope),receiver_credentials=[os.getpid(),os.getuid(),os.getgid()],
            receiver=self.sender_identity,custodian=self.sender_identity,
            descriptor_identities=[i.identity(arx.fileno()),i.identity(ctx),i.identity(idx)],
            endpoint_identity=i.identity(rx.fileno()),directory_identity=i.identity(self.dirfd),order_identity=self.order_identity,
            capability_identities=self.identities,capability_expected=self.expected,record_binding=self.binding,
            itinerary=self.itinerary,recovery=self.recovery,owner_uid=os.getuid())
        fds=[arx.fileno(),ctx,idx]
        if mutate:mutate(envelope,fds)
        if anchor_mutate:anchor_mutate(anchor)
        m.send_packet(tx,envelope,fds)
        ingress=i.InstalledIngress(self.backend,anchor,self.dirfd,endpoint_fd=rx.fileno(),clock=lambda:100,
            record_authority=TestRecordAuthority())
        entry=e.RootEntry(ingress,clock=lambda:100,run=Mock(side_effect=AssertionError('real subprocess forbidden')))
        return entry,ingress

    def invoke(self,*args,**kwargs):
        entry,ingress=self.invocation(*args,**kwargs)
        output=io.StringIO()
        with redirect_stdout(output),patch.object(e.c,'HERE',self.install):
            status=self.module.main([],qualified={c.digest((c.HERE/'profile-root-helper.py').read_bytes()):entry})
        self.assertEqual(ingress.fds,())
        self.assertEqual(output.getvalue().count('\n'),1)
        return status,json.loads(output.getvalue())

    def state(self):return json.loads(self.order.read_bytes())

    def test_missing_or_refusing_surviving_authority_cannot_admit(self):
        for authority in (None,Mock(authenticate=Mock(return_value=False))):
            entry,ingress=self.invocation();ingress.record_authority=authority
            with self.assertRaises(ValueError):entry.run_authenticated_inherited_entry()
        self.backend.syscall.assert_not_called()
        self.assertEqual(self.state()['position'],0)

    def test_real_main_ingress_installation_and_durable_order_across_invocations(self):
        self.assertEqual(self.invoke()[0],0)
        self.assertEqual(self.state()['position'],1)
        self.assertEqual(self.invoke()[0],3)
        self.assertEqual(self.invoke(1)[0],0)
        self.assertEqual(self.state()['position'],2)
        self.assertEqual(self.backend.calls.count('effect'),2)
        self.assertEqual(json.loads((self.control/'record-0').read_bytes())['state'],'QUARANTINED')
        self.assertEqual(e.QUALIFIED_ROOT,{})

    def test_substituted_delivery_index_authority_and_receiver_fail_before_effects(self):
        cases=[dict(mutate=lambda env,fds:env['request'].update(record=1)),
            dict(mutate=lambda env,fds:env['delivery'].update(sender_start='1')),
            dict(mutate=lambda env,fds:env.update(activation='00'*32)),
            dict(mutate=lambda env,fds:fds.__setitem__(2,self.memfd(self.index+b' '))),
            dict(mutate=lambda env,fds:fds.__setitem__(1,self.memfd(c.canonical(dict(schema='forged'))))),
            dict(mutate=lambda env,fds:fds.__setitem__(0,self.other_authority())),
            dict(anchor_mutate=lambda a:a.update(receiver=dict(pid=os.getpid(),start='1'))),
            dict(anchor_mutate=lambda a:a.update(custodian=dict(pid=os.getpid(),start='1'))),
            dict(anchor_mutate=lambda a:a.update(endpoint_identity=[1,2])),dict(unsealed=True)]
        before=self.order.read_bytes()
        for case in cases:
            with self.subTest(case=case):self.assertEqual(self.invoke(**case)[0],3)
        self.backend.syscall.assert_not_called();self.assertEqual(self.order.read_bytes(),before)

    def test_same_bytes_sealed_index_substitution_is_not_authority(self):
        self.assertEqual(self.invoke(mutate=lambda env,fds:fds.__setitem__(2,self.memfd(self.index)))[0],3)
        self.backend.syscall.assert_not_called()

    def test_altered_installation_refuses_before_capability_or_effect(self):
        path=self.install/'runtime/vanguard/network/network.py';path.write_bytes(path.read_bytes()+b'\n# altered\n')
        self.assertEqual(self.invoke()[0],3)
        self.assertEqual(json.loads((self.control/'record-0').read_bytes())['state'],'RESERVED')
        self.backend.syscall.assert_not_called()

    def test_out_of_order_and_changed_original_deadlines_refuse(self):
        self.assertEqual(self.invoke(1)[0],3)
        self.assertEqual(self.invoke(anchor_mutate=lambda a:a['record_binding']['deadlines'].update(end=9999))[0],3)
        self.backend.syscall.assert_not_called()

    def test_fresh_process_replay_refuses(self):
        self.assertEqual(self.invoke()[0],0)
        pid=os.fork()
        if pid==0:
            try:
                self.sender_identity=i.process_identity(os.getpid())
                os._exit(0 if self.invoke()[0]==3 else 1)
            except BaseException:os._exit(2)
        self.assertEqual(os.waitpid(pid,0)[1],0)

    def test_crash_after_admission_keeps_pending_and_requires_recovery(self):
        pid=os.fork()
        if pid==0:
            try:
                self.sender_identity=i.process_identity(os.getpid())
                self.backend.syscall.side_effect=lambda *args:os._exit(9)
                self.invoke()  # Actual main -> ingress -> installation -> journal -> modeled effect.
                os._exit(1)
            except BaseException:os._exit(2)
        self.assertEqual(os.waitpid(pid,0)[1],9*256)
        self.assertEqual(self.state()['pending'],0)
        self.assertEqual(self.invoke()[0],3)
        self.assertEqual(self.invoke(self.cleanup,recovered=True)[0],0)
        self.assertEqual(self.state()['mode'],'RECOVERY_ONLY')
        self.assertEqual(self.state()['uncertain'],0)
        self.assertEqual(self.state()['binding']['deadlines'],self.contract['deadlines'])
        self.assertEqual(self.invoke(1)[0],3)

    def test_concurrent_connected_processes_have_at_most_one_effect(self):
        children=[]
        for unused in range(2):
            pid=os.fork()
            if pid==0:
                try:
                    self.sender_identity=i.process_identity(os.getpid())
                    os._exit(self.invoke()[0])
                except BaseException:os._exit(2)
            children.append(pid)
        self.assertEqual(sorted(os.waitpid(pid,0)[1] for pid in children),[0,3*256])
        self.assertEqual(self.state()['position'],1)

    def test_record_role_and_contract_source_substitution_refuse(self):
        self.assertEqual(self.invoke(anchor_mutate=lambda a:
            a['capability_expected']['record-0'].update(delivery_role='prepare'))[0],3)
        self.backend.syscall.assert_not_called()

    def test_failed_durability_has_no_effect_and_cannot_reuse_slot(self):
        with patch.object(os,'fsync',side_effect=OSError('disposable uncertain sync')):
            self.assertEqual(self.invoke()[0],3)
        self.backend.syscall.assert_not_called()
        self.assertEqual(self.invoke()[0],3)

    def test_partial_order_write_or_missing_original_refuses_without_repair(self):
        original=self.order.read_bytes()
        self.order.write_bytes(original[:25]);self.assertEqual(self.invoke()[0],3)
        self.assertEqual(self.order.read_bytes(),original[:25])
        self.order.unlink();self.assertEqual(self.invoke()[0],3);self.assertFalse(self.order.exists())
        self.backend.syscall.assert_not_called()

    def test_modeled_effect_failure_preserves_recovery_only_state(self):
        self.backend.syscall.side_effect=OSError('MODELED failed effect')
        self.assertEqual(self.invoke()[0],3)
        self.assertEqual(self.state()['mode'],'RECOVERY_ONLY')
        self.assertEqual(self.invoke(1)[0],3)

    def test_known_bad_exact_base_has_only_per_instance_record_use(self):
        raw=subprocess.check_output(['git','show','e9cb885fbf9513801fca216fe033df7fad38f58a:vanguard/network/profile_executor.py'])
        namespace={'__name__':'known_bad_executor'};exec(compile(raw,'exact-e9cb885-profile_executor.py','exec'),namespace)
        # Keep the negative control's own renderer. Combining the old executor
        # with the new prefix would fail its operation-table check before replay.
        packet_raw=subprocess.check_output(['git','show',
            'e9cb885fbf9513801fca216fe033df7fad38f58a:vanguard/network/profile_packet.py'])
        original=types.ModuleType('exact_base_packet')
        exec(compile(packet_raw,'exact-e9cb885-profile_packet.py','exec'),original.__dict__)
        namespace['p']=original
        backend=InjectedBoundary()
        request=dict(operation=self.records[0]['operation'],record=0,deadline=200)
        for unused in range(2):
            namespace['RecordExecutor'](original.source_plan(),backend,clock=lambda:100).execute(request)
        self.assertEqual(sum(isinstance(x,tuple) and x[0]=='syscall' for x in backend.calls),2)
        self.assertEqual(self.invoke()[0],0);self.assertEqual(self.invoke()[0],3)


if __name__=='__main__':unittest.main(verbosity=2)
