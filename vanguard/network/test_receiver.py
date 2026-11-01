"""Injected manager properties and actual disposable parent/pidfd exits.

No live bus, installed service, FD-store, mount, original lock or native build.
Manager fixtures deliberately supply TEST authority, not an installed adapter.
"""
import copy
import errno
import json
import os
from pathlib import Path
import signal
import tempfile
import time
import unittest
from unittest.mock import patch

import profile_contract as c
import profile_ingress as i
import profile_packet as p
import profile_receiver as r


def bound_plan():
    plan=p.source_plan();plan['attempt_id']='1'*32
    plan['source']=dict(commit='b'*40,inputs_sha256='c'*64,artifact_sha256='d'*64,helper_sha256='e'*64)
    return plan


def binding(plan,receiver,*,origin=0,end=4500):
    launch=dict(plan=plan,record_binding=dict(contract_sha256='a'*64,inputs_sha256='c'*64,
        origin=origin,deadlines=dict(build=end-900,work=end-300,end=end)))
    return r.scope(launch,0,receiver)


class InjectedManager:
    def __init__(self,manager):
        self.manager=copy.deepcopy(manager);self.calls=[];self.properties={};self.acknowledged=[]
    def authenticate_manager(self):return copy.deepcopy(self.manager)
    def authenticate_launch(self,plan,manager):
        return dict(bindings={},record_binding=binding(plan,manager['process'])['record_binding'])
    def authenticate_receiver_delivery(self,plan,record,fd):return True
    def start_transient_unit(self,manager,call,deadline):
        self.calls.append(copy.deepcopy(call));return '/TEST/job/1'
    def receiver_properties(self,manager,unit,deadline):return copy.deepcopy(self.properties)
    def authenticate_settlement(self,receipt):return True
    def acknowledge_receiver(self,manager,unit,receipt):self.acknowledged.append(copy.deepcopy(receipt))


class ManagerTests(unittest.TestCase):
    def setUp(self):
        self.plan=bound_plan();self.receiver=i.process_identity(os.getpid())
        self.binding=binding(self.plan,self.receiver)
        self.manager=dict(bus='user',unique_name=':1.10',client_unique_name=':1.20',epoch='TEST-original-connection',
            boot_id=r.boot_id(),process=self.receiver,uid=os.getuid())
        self.backend=InjectedManager(self.manager);self.now=100
        self.transport=r.ManagerTransport(self.plan,self.manager,self.backend,clock=lambda:self.now)
        self.unit,_=self.transport.start_receiver(0,17,deadline=200)
        self.backend.properties=dict(unit=self.unit,object='/org/freedesktop/systemd1/unit/TEST',
            receiver=self.receiver,InvocationID='f'*32,MainPID=self.receiver['pid'],ExecMainPID=self.receiver['pid'],
            ExecMainStartTimestampMonotonic=1_000_000,ExecMainExitTimestampMonotonic=0,
            ExecMainCode=0,ExecMainStatus=0,NRestarts=0,Type='exec',Restart='no',RemainAfterExit=True,
            Refs=[self.manager['client_unique_name']],command=['/usr/bin/python3','-I','-B',
                '/opt/meownero/TJS-2504/helper/profile-root-helper.py'])
        self.transport.capture_receiver(self.unit,self.receiver,self.binding,deadline=200)

    def terminal(self,code=os.CLD_EXITED,status=0):
        self.backend.properties.update(MainPID=0,ExecMainExitTimestampMonotonic=99_000_000,
            ExecMainCode=code,ExecMainStatus=status)

    def observe(self,persist=None):
        return self.transport.observe_exit(self.unit,persist=persist or self.receipts.append,deadline=200)

    def test_bound_bus_is_independent_of_destination_and_fixed_receiver(self):
        call=self.backend.calls[0];self.assertEqual(call['bus'],'org.freedesktop.systemd1')
        props={name:(kind,value) for name,kind,value in call['args'][2]}
        self.assertEqual(props['Restart'],('s','no'));self.assertEqual(props['AddRef'],('b',True))
        self.assertEqual(props['RemainAfterExit'],('b',True))
        self.assertEqual(props['StandardInputFileDescriptor'],('h',17))
        self.assertEqual(props['ExecStart'][1][0][1],['/usr/bin/python3','-I','-B',
            '/opt/meownero/TJS-2504/helper/profile-root-helper.py'])
        self.assertEqual(self.transport.manager['bus'],'user')
        for bus in ('system','user'):
            manager=dict(self.manager,bus=bus);backend=InjectedManager(manager)
            transport=r.ManagerTransport(self.plan,manager,backend,clock=lambda:100)
            transport.start(p.units(self.plan)[0]['args'][0],deadline=200)
            self.assertEqual(backend.calls,[p.units(self.plan)[0]])

    def test_normal_nonzero_and_signal_terminal_events(self):
        for code,status,result in ((os.CLD_EXITED,0,0),(os.CLD_EXITED,9,9),
                (os.CLD_KILLED,signal.SIGTERM,-signal.SIGTERM),(os.CLD_DUMPED,signal.SIGABRT,-signal.SIGABRT)):
            with self.subTest(code=code,status=status):
                self.setUp();self.receipts=[];self.terminal(code,int(status));value=self.observe()
                self.assertEqual(self.transport.verify_exit(value,self.binding),result)
                self.assertEqual(self.receipts,[value]);self.assertFalse(self.backend.acknowledged)
                receipt=dict(confirmed=True,scope=self.binding,exit_witness_sha256=c.digest(c.canonical(value)))
                self.transport.acknowledge(self.unit,receipt);self.assertEqual(self.backend.acknowledged,[receipt])

    def test_absence_success_and_nonterminal_events_are_not_exit_witnesses(self):
        cases=[dict(MainPID=0),dict(MainPID=0,Result='success'),
            dict(MainPID=0,ExecMainExitTimestampMonotonic=99_000_000,ExecMainCode=os.CLD_STOPPED),
            dict(MainPID=0,ExecMainExitTimestampMonotonic=99_000_000,ExecMainCode=os.CLD_CONTINUED),
            dict(MainPID=0,ExecMainExitTimestampMonotonic=99_000_000,ExecMainCode=os.CLD_EXITED,ExecMainStatus=None)]
        for changes in cases:
            with self.subTest(changes=changes):
                self.setUp();self.backend.properties.update(changes);self.receipts=[]
                with self.assertRaises(ValueError):self.observe()
                self.assertEqual(self.receipts,[])

    def test_original_unit_invocation_pid_start_and_timestamp_are_pinned(self):
        cases=dict(unit='other.service',object='/org/freedesktop/systemd1/unit/OTHER',InvocationID='0'*32,
            receiver=dict(self.receiver,start='1'),ExecMainPID=self.receiver['pid']+1,
            ExecMainStartTimestampMonotonic=2_000_000,ExecMainExitTimestampMonotonic=101_000_000)
        for key,value in cases.items():
            with self.subTest(key=key):
                self.setUp();self.terminal();self.backend.properties[key]=value;self.receipts=[]
                with self.assertRaises(ValueError):self.observe()
                self.assertEqual(self.receipts,[])

    def test_bus_epoch_boot_and_connection_changes_refuse(self):
        for key,value in dict(bus='system',epoch='new',unique_name=':1.11',client_unique_name=':1.21',boot_id='other',uid=123,
                process=dict(self.receiver,start='1')).items():
            with self.subTest(key=key):
                self.setUp();self.terminal();self.backend.manager[key]=value;self.receipts=[]
                with self.assertRaises(ValueError):self.observe()
                self.assertEqual(self.receipts,[])

    def test_persistence_failure_late_read_and_retained_property_change_refuse_release(self):
        self.terminal();self.receipts=[]
        with self.assertRaises(OSError):self.observe(lambda value:(_ for _ in ()).throw(OSError(errno.ENOSPC,'TEST')))
        self.assertFalse(self.backend.acknowledged)
        with self.assertRaises(ValueError):self.observe()
        self.setUp();self.terminal();self.receipts=[]
        value=self.observe();self.backend.properties['InvocationID']='0'*32
        with self.assertRaises(ValueError):self.transport.verify_exit(value,self.binding)
        self.setUp();self.terminal();self.receipts=[]
        def late(value):self.now=201
        with self.assertRaises(ValueError):self.observe(late)
        self.assertFalse(self.backend.acknowledged)

    def test_changed_scope_and_unconfirmed_receipts_cannot_release(self):
        self.terminal();self.receipts=[];value=self.observe()
        wrong=copy.deepcopy(self.binding);wrong['record']=1
        with self.assertRaises(ValueError):self.transport.verify_exit(value,wrong)
        for receipt in (None,dict(confirmed=True),dict(confirmed=True,scope=self.binding,exit_witness_sha256='0'*64)):
            with self.assertRaises(ValueError):self.transport.acknowledge(self.unit,receipt)
        self.assertFalse(self.backend.acknowledged)

    def test_lost_start_reply_burns_receiver_name_and_record54_refuses(self):
        manager=self.manager;backend=InjectedManager(manager)
        transport=r.ManagerTransport(self.plan,manager,backend,clock=lambda:100)
        with patch.object(backend,'start_transient_unit',side_effect=OSError('TEST lost reply')):
            with self.assertRaises(OSError):transport.start_receiver(0,17,deadline=200)
        with self.assertRaises(ValueError):transport.start_receiver(0,17,deadline=200)
        with self.assertRaises(ValueError):transport.start_receiver(54,17,deadline=200)
        self.assertFalse(backend.calls)

    def test_original_deadlines_and_caller_reference_cannot_be_replaced(self):
        manager=self.manager;backend=InjectedManager(manager)
        authority=backend.authenticate_launch(self.plan,manager)
        authority['record_binding']['deadlines']['end']+=1
        with patch.object(backend,'authenticate_launch',return_value=authority):
            with self.assertRaises(ValueError):r.ManagerTransport(self.plan,manager,backend,clock=lambda:100)
        for deadline in (float('inf'),4501):
            with self.assertRaises(ValueError):self.transport.start_receiver(1,17,deadline=deadline)
        wrong=copy.deepcopy(self.binding);wrong['record_binding']['origin']+=1
        with self.assertRaises(ValueError):self.transport.capture_receiver(self.unit,self.receiver,wrong,deadline=200)
        self.backend.properties['Refs']=[self.manager['unique_name']]
        self.transport.receivers.clear()
        with self.assertRaises(ValueError):self.transport.capture_receiver(self.unit,self.receiver,self.binding,deadline=200)


class ChildTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='TJS2504-pidfd-source-');self.addCleanup(self.temp.cleanup)
        self.plan=bound_plan();self.reaped=set();self.children=[]
        self.addCleanup(self.cleanup_children)

    def cleanup_children(self):
        for pid in self.children:
            if pid in self.reaped:continue
            try:os.kill(pid,signal.SIGKILL);os.waitpid(pid,0)
            except ProcessLookupError:pass
            except ChildProcessError:pass

    def child(self,status=0):
        read,write=os.pipe();self.addCleanup(os.close,write)
        pid=os.fork()
        if pid==0:
            os.close(write);os.read(read,1);os.close(read);os._exit(status)
        os.close(read);self.children.append(pid)
        receiver=i.process_identity(pid);now=time.monotonic()
        scope=binding(self.plan,receiver,origin=now-1,end=now+10)
        witness=r.ChildExitWitness(receiver,scope);self.addCleanup(witness.close)
        return pid,write,witness,scope

    def observe(self,pid,witness,persist):
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            try:
                result=witness.observe(persist,deadline=deadline);self.reaped.add(pid);return result
            except ValueError as exc:
                if str(exc)!='exact child terminal event required':raise
                time.sleep(.005)
        self.fail('no child exit')

    def test_waitid_pins_child_persists_before_reap_and_decodes_exit9(self):
        pid,write,witness,scope=self.child(9);receipts=[]
        with self.assertRaises(ValueError):witness.observe(receipts.append,deadline=time.monotonic()+5)
        self.assertFalse(receipts);os.write(write,b'x')
        def persist(value):
            path=Path(self.temp.name)/'receipt'
            with path.open('wb') as stream:
                stream.write(c.canonical(value));stream.flush();os.fsync(stream.fileno())
            self.assertEqual(json.loads(path.read_bytes()),value)
            if not value['detail']['reaped']:
                event=os.waitid(os.P_PIDFD,witness.fd,os.WEXITED|os.WNOHANG|os.WNOWAIT)
                self.assertEqual(event.si_status,9)
            receipts.append(value)
        value=self.observe(pid,witness,persist)
        self.assertEqual([row['detail']['reaped'] for row in receipts],[False,True])
        self.assertEqual(r.validate_witness(value,scope,i.process_identity(os.getpid()),'parent_pidfd',time.monotonic()),9)
        with self.assertRaises(FileNotFoundError):i.process_identity(pid)
        with self.assertRaises(ValueError):witness.observe(persist,deadline=time.monotonic()+5)

    def test_terminal_signal_is_abnormal_and_cannot_decode_as_zero(self):
        pid,write,witness,scope=self.child();os.kill(pid,signal.SIGTERM)
        value=self.observe(pid,witness,lambda row:None)
        self.assertEqual(r.exit_status(value['code'],value['status']),-signal.SIGTERM)
        self.assertNotEqual(value['code'],os.CLD_EXITED)

    def test_persistence_failure_retains_waitable_event_and_no_witness(self):
        pid,write,witness,scope=self.child();os.write(write,b'x')
        def fail(value):raise OSError(errno.EIO,'TEST durable write failed')
        with self.assertRaises(OSError):self.observe(pid,witness,fail)
        event=os.waitid(os.P_PIDFD,witness.fd,os.WEXITED|os.WNOHANG|os.WNOWAIT)
        self.assertEqual(event.si_code,os.CLD_EXITED)
        with self.assertRaises(ValueError):witness.observe(lambda row:None,deadline=time.monotonic()+5)

    def test_nonchild_echild_and_substituted_start_are_not_status_zero(self):
        receiver=i.process_identity(os.getpid());scope=binding(self.plan,receiver,origin=0,end=time.monotonic()+10)
        witness=r.ChildExitWitness(receiver,scope);self.addCleanup(witness.close)
        with self.assertRaises(ChildProcessError):witness.observe(lambda row:None,deadline=time.monotonic()+5)
        pid,write,witness,scope=self.child();wrong=dict(scope['receiver'],start='1')
        with self.assertRaises(ValueError):r.ChildExitWitness(wrong,dict(scope,receiver=wrong))

    def test_stopped_continued_missing_and_impossible_status_are_rejected(self):
        for code,status in ((os.CLD_STOPPED,signal.SIGSTOP),(os.CLD_CONTINUED,signal.SIGCONT),
                (os.CLD_EXITED,256),(os.CLD_KILLED,0),(None,0)):
            with self.assertRaises(ValueError):r.exit_status(code,int(status))


if __name__=='__main__':unittest.main(verbosity=2)
