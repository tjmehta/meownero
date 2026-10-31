"""Connected generated argv/SCM_RIGHTS/main/SystemExit source fixtures.

Real local sockets, kernel credentials, seals and descriptor closure. Installed
unit identity, atomic custodian state, namespace entry and all host work are
MODELED. No production registry, original lock, PID1 or native workload is used.
"""
import array
import contextlib
import copy
import fcntl
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import profile_bootstrap as b
import profile_contract as c
import profile_dispatch as d
import profile_handoff as h
import profile_manager as m
import profile_packet as p
from test_dispatch import Boundary, contract


class InstalledBoundary(Boundary):
    def __init__(self,plan):
        super().__init__()
        self.plan=plan;self.expected=None;self.spent=set();self.restart=False
        self.namespace_entered=False;self.private_reads=0;self.states=[]
        self.failure=None;self.records=[]
        self.sender_start=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]

    def bootstrap_expectation(self,mode,role,plan,sha):
        self.namespace_entered=False
        return dict(entry='stored-recovery' if self.restart else 'fresh',
            delivery=None if self.restart else self.expected)

    def check_bootstrap_sender(self,value):
        self.call('sender_start')
        live=Path('/proc/'+str(value['sender_credentials'][0])+'/stat').read_text().rsplit(')',1)[1].split()[19]
        c.require(live==value['sender_start'], 'MODELED installed expectation with real sender start check')

    def consume_bootstrap_delivery(self,value,authority,context):
        key=(value['attempt_id'],value['role'],
            '' if value['role'] in ('prepare','keeper') else value['invocation_id'])
        c.require(key not in self.spent,'MODELED surviving custodian one-use burn')
        self.spent.add(key)
        return True

    def authenticate_inherited(self,mode,authority,context,plan,sha):
        self.call('authenticate')
        return dict(mode=mode,spec_sha256=sha,source=plan['source'],task_only=True,
            hard_byte_and_write_limits=True,overhead_within_reservation=True,
            private_secret='MUST_NOT_PRINT')

    def authenticate_installed_recovery(self,mode,plan,sha):
        self.call('installed_recovery')
        return dict(mode=mode,spec_sha256=sha,source=plan['source'],installed_root_owned_source=True,
            exact_task_unit_pid1_sender=True,recovery_only=True)

    def validate_retained_namespace(self,fd,value):
        self.call('namespace_validate')
        c.require(value['namespace_identity']==55 and os.pread(fd,32,0)==b'MODELED_NAMESPACE',
            'MODELED retained namespace identity/custody')

    def enter_retained_namespace(self,fd,kind):
        self.call('namespace_enter');c.require(kind==0x20000,'CLONE_NEWNS')
        self.namespace_entered=True

    def reenter_stored_namespace(self,resolve):
        self.call('stored_namespace')
        with patch.object(os,'set_inheritable'):
            result=resolve(dict(LISTEN_PID=str(os.getpid()),LISTEN_FDS='2',
                LISTEN_FDNAMES='original-lock:mount-namespace'),pid=os.getpid(),
                validate_lock=lambda fd:self.call('stored_lock'),
                validate_namespace=lambda fd:self.call('stored_namespace_validate'),
                setns=lambda fd,kind:self.call('stored_setns'))
        c.require(result['recovery_only'] is True,'recovery only')
        self.namespace_entered=True

    def read_existing_context(self):
        c.require(self.namespace_entered,'no private read before namespace entry')
        self.call('private_read');self.private_reads+=1
        return dict(contract=contract(self.plan),recovered=self.restart,live_one_use_activation=not self.restart,
            observed_work=None,create_intent=None,owned_cid=None)

    def serve_inherited_channels(self,dispatcher):
        self.call('serve');self.states.append(dispatcher.state)
        self.asserted_deadlines=dispatcher.contract['deadlines']
        return 0

    def apply_preparation_record(self,record,**deadlines):
        self.call('preparation');self.records.append(record)
        return dict(written_bytes=1,occupied_bytes=1024)

    def preparation_readback(self):
        return dict(slot_state='RESERVED',root_slot_owner=[0,0],ledger_directory_owner=[1000,1000],
            observed_work=None,archive_sealed=True,archive_plus_overhead_bytes=1024,private_secret='MUST_NOT_PRINT')

    def preparation_uncertainty_never_rearm(self):self.call('preparation_uncertainty')
    def wait_until(self,deadline):self.call('wait_original_work');self.waited=deadline
    def wait_owned_cleanup_keeper_exit(self,deadline):self.call('wait_cleanup');self.waited=deadline
    def observe_retained_and_work_absence(self,context):
        self.call('observe');return dict(result='PENDING_OBSERVER_EXIT',private_secret='MUST_NOT_PRINT')


class GeneratedEntryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='TJS2504-generated-source-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.spec=self.root/'spec.json'
        self.plan=p.source_plan();self.plan['attempt_id']='1'*32
        self.plan['source']={k:('b'*40 if k=='commit' else 'c'*64) for k in self.plan['source']}
        self.plan['authority']={k:'e'*64 for k in self.plan['authority']}
        self.spec.write_bytes(c.canonical(self.plan));self.sha=c.digest(c.canonical(self.plan))
        self.boundary=InstalledBoundary(self.plan)
        self.invocation='2'*32
        spec=importlib.util.spec_from_file_location('generated_helper',c.HERE/'profile-helper.py')
        self.helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.helper)

    def delivery(self,role):
        bound=contract(self.plan)
        return dict(schema='meownero-helper-bootstrap/1',task='TJS-2504',attempt_id=self.plan['attempt_id'],
            role=role,mode=p.delivery_contract(role)['mode'],invocation_id=self.invocation,source=self.plan['source'],
            spec_sha256=self.sha,contract_sha256=c.digest(c.canonical(bound)),origin=bound['origin'],
            deadlines=bound['deadlines'],sender_credentials=[os.getpid(),os.getuid(),os.getgid()],
            sender_start=self.boundary.sender_start,delivery_deadline=104,
            namespace_identity=None if role=='prepare' else 55)

    def generated(self,role):
        call=next(x for x in p.units(self.plan) if x['delivery'] and x['delivery']['role']==role)
        self.assertEqual(call['delivery']['receiving_fd'],0)
        prop={name:(kind,value) for name,kind,value in call['args'][2]}
        self.assertEqual(prop['StandardInputFileDescriptor'],('h','$BOOTSTRAP_'+role.upper()+'_RECEIVE_FD'))
        argv=prop['ExecStart'][1][0][1][3:]
        return [str(self.spec) if x=='$ROOT_OWNED_SPEC' else self.sha if x=='$SPEC_SHA256' else x for x in argv]

    def memfd(self,raw,sealed=True):
        fd=os.memfd_create('TJS2504-source-fixture',os.MFD_CLOEXEC|os.MFD_ALLOW_SEALING)
        self.addCleanup(os.close,fd);os.write(fd,raw)
        if sealed:fcntl.fcntl(fd,fcntl.F_ADD_SEALS,b.SEALS)
        return fd

    def invoke(self,role,*,mutate=None,kind=None,restart=False,default=False):
        expected=self.delivery(role);packet=copy.deepcopy(expected)
        if mutate:mutate(packet)
        self.boundary.expected=expected;self.boundary.restart=restart
        left,right=b.delivery_pair();self.addCleanup(left.close);self.addCleanup(right.close)
        auth,peer=m.private_pair();self.addCleanup(auth.close);self.addCleanup(peer.close)
        ctx=self.memfd(c.canonical(dict(schema='meownero-helper-bootstrap-context/1',delivery=packet,
            contract=contract(self.plan))),sealed=kind!='unsealed')
        fds=[auth.fileno(),ctx]
        if role!='prepare':fds.append(self.memfd(b'WRONG_NAMESPACE' if kind=='namespace' else b'MODELED_NAMESPACE'))
        if kind=='authority':fds[0]=self.memfd(b'WRONG_AUTHORITY_KIND')
        if kind=='context':fds[1]=auth.fileno()
        if kind=='missing':fds=[]
        if kind=='extra':fds.append(self.memfd(b'UNSOLICITED'))
        if kind=='credentials':self.boundary.expected['sender_credentials'][0]+=1
        if kind=='start':self.boundary.expected['sender_start']='0'
        if not restart:
            if kind=='truncated':
                left.sendmsg([b'x'*(m.MAX_PACKET+1)],[(socket.SOL_SOCKET,socket.SCM_RIGHTS,array.array('i',fds))])
            else:m.send_packet(left,packet,fds)
        saved=os.dup(0);output=io.StringIO();errors=io.StringIO()
        try:
            os.dup2(right.fileno(),0)
            adapter=d.LifecycleAdapter(self.boundary,clock=lambda:self.boundary.now)
            table={} if default else {'e'*64:adapter}
            with contextlib.redirect_stdout(output),contextlib.redirect_stderr(errors),self.assertRaises(SystemExit) as end:
                self.helper.run(self.generated(role),backend_table=table,clock=lambda:self.boundary.now)
            self.assertIs(type(end.exception.code),int)
            self.assertEqual(errors.getvalue(),'')
            payload=json.loads(output.getvalue())
            self.assertLessEqual(set(payload),{'result','failure_class','native_execution','launch_ready'})
            self.assertNotIn('MUST_NOT_PRINT',output.getvalue())
            self.assertEqual(d.QUALIFIED_OS,{});self.assertEqual(h.QUALIFIED_BOOTSTRAPS,{})
            return end.exception.code,payload
        finally:os.dup2(saved,0);os.close(saved)

    def test_generated_prepare_main_systemexit_numeric_sanitized_success_and_replay(self):
        self.assertEqual(self.invoke('prepare'),(0,dict(result='PREPARED_UNACTIVATED',native_execution='NOT_RUN',launch_ready=False)))
        count=len(self.boundary.records)
        self.assertGreater(count,0);self.assertEqual(self.invoke('prepare')[0],3)
        self.assertEqual(len(self.boundary.records),count)

    def test_generated_first_activation_once_then_independent_recovery_original_deadlines(self):
        self.assertEqual(self.invoke('keeper')[0],0)
        self.assertEqual(self.boundary.states,['RESERVED'])
        self.invocation='3'*32 # New process invocation cannot refresh first activation.
        self.assertEqual(self.invoke('keeper')[0],3)
        self.assertEqual(self.invoke('keeper',restart=True)[0],0)
        self.assertEqual(self.boundary.states,['RESERVED','RECOVERY_ONLY'])
        self.assertEqual(self.boundary.asserted_deadlines,dict(build=3700,work=4300,end=4600))
        self.assertEqual(self.boundary.calls.count('stored_lock'),1)

    def test_separate_deadline_and_observer_namespace_before_private_read(self):
        for role in ('deadline','observer'):
            self.boundary.calls=[]
            status,result=self.invoke(role)
            self.assertEqual(status,0)
            calls=self.boundary.calls
            self.assertLess(calls.index('namespace_validate'),calls.index('namespace_enter'))
            self.assertLess(calls.index('namespace_enter'),calls.index('private_read'))
            self.assertNotIn('stored_namespace',calls)
            if role=='observer':self.assertEqual(result['result'],'PENDING_OBSERVER_EXIT')
            else:self.assertEqual(self.boundary.waited,4300)

    def test_missing_wrong_kind_extra_unsealed_truncated_credentials_and_start_refuse(self):
        for kind in ('missing','authority','context','extra','unsealed','truncated','credentials','start','namespace'):
            with self.subTest(kind=kind):
                self.boundary.spent.clear();self.boundary.calls=[]
                self.assertEqual(self.invoke('observer',kind=kind)[0],3)
                self.assertNotIn('observe',self.boundary.calls)

    def test_wrong_role_invocation_source_deadline_contract_refuse(self):
        for key,value in [('role','keeper'),('invocation_id','4'*32),('source',{}),
            ('delivery_deadline',99),('contract_sha256','f'*64),('attempt_id','5'*32)]:
            with self.subTest(key=key):
                self.boundary.spent.clear()
                self.assertEqual(self.invoke('prepare',mutate=lambda x:x.update({key:value}))[0],3)
                self.assertEqual(self.boundary.records,[])

    def test_main_failure_sanitizes_exception_and_burns_capability(self):
        self.boundary.failure='preparation'
        status,result=self.invoke('prepare')
        self.assertEqual(status,3);self.assertEqual(result['failure_class'],'OSError')
        self.boundary.failure=None
        self.assertEqual(self.invoke('prepare')[0],3)

    def test_default_registry_refuses_even_filled_source_before_bootstrap_or_OS(self):
        self.assertEqual(self.invoke('prepare',default=True)[0],3)
        self.assertEqual(self.boundary.calls,[])

    def test_eight_calls_supported_slices_hierarchy_and_render_consistency(self):
        packet=p.render(self.plan);calls=packet['units']
        self.assertEqual(len(calls),8)
        slices=[x for x in calls if x['args'][0].endswith('.slice')]
        allowed={'CPUQuotaPerSecUSec':'t','MemoryMax':'t','MemorySwapMax':'t','TasksMax':'t'}
        self.assertEqual(len(slices),3)
        parent=slices[0]['args'][0]
        for call in slices:
            self.assertEqual({name:kind for name,kind,value in call['args'][2]},allowed)
        for call in slices[1:]:self.assertEqual(call['args'][0].rsplit('-',1)[0]+'.slice',parent)
        records=[r['args'] for r in packet['records'] if r['kind']=='dbus' and r['operation']=='StartTransientUnit']
        records+=[r['args'] for r in packet['operator_prefix']['operations']
            if r['kind']=='dbus' and r['operation']=='StartTransientUnit']
        self.assertEqual(len(records),8)  # Prefix creations and later verification do not duplicate units.
        self.assertEqual({x['args'][0]:x for x in calls},{x['args'][0]:x for x in records})
        self.assertEqual(len([r for r in packet['records'] if r['operation']=='bootstrap_delivery']),4)

    def test_real_default_process_exits_three_without_raw_receipt(self):
        result=subprocess.run([sys.executable,'-B',str(c.HERE/'profile-helper.py'),
            *self.generated('prepare')],capture_output=True,text=True,timeout=5)
        self.assertEqual(result.returncode,3);self.assertEqual(result.stderr,'')
        self.assertEqual(json.loads(result.stdout)['result'],'REFUSED_BEFORE_HOST_OPERATIONS')

    def test_known_bad_sender_PASSCRED_autobinds_and_is_rejected(self):
        for factory,valid in [(m.private_pair,False),(b.delivery_pair,True)]:
            left,right=factory()
            try:
                m.send_packet(left,{'fixture':True})
                if valid:
                    b.seqpacket(right)
                    self.assertEqual(right.getpeername(),'')
                    value,_=m.receive_packet(right,[os.getpid(),os.getuid(),os.getgid()],104,
                        clock=lambda:100)
                    self.assertEqual(value,{'fixture':True})
                else:
                    with self.assertRaises(ValueError):b.seqpacket(right)
            finally:left.close();right.close()

    def test_ambiguous_stored_custody_refuses_without_namespace_or_rearm(self):
        calls=[]
        for names in ('original-lock','original-lock:mount-namespace:original-lock','x:mount-namespace'):
            with self.subTest(names=names),self.assertRaises(ValueError):
                d.stored_fds(dict(LISTEN_PID='123',LISTEN_FDS='2',LISTEN_FDNAMES=names),pid=123,
                    validate_lock=lambda fd:calls.append('lock'),validate_namespace=lambda fd:calls.append('ns'),
                    setns=lambda fd,kind:calls.append('setns'))
        self.assertEqual(calls,[])

    def test_rejected_bootstrap_closes_every_received_descriptor(self):
        for kind in ('extra','truncated','authority'):
            closed=[];real_close=os.close
            def close(fd):
                closed.append(fd)
                return real_close(fd)
            with patch.object(m.os,'close',side_effect=close):
                self.assertEqual(self.invoke('observer',kind=kind)[0],3)
            # Three role FDs (four with an unsolicited one), plus saved stdin.
            self.assertGreaterEqual(len(closed),5 if kind=='extra' else 4)
            for fd in closed:
                with self.assertRaises(OSError):os.fstat(fd)


if __name__=='__main__':unittest.main(verbosity=2)
