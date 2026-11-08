"""Original source process -> produced packets -> real root main and journal.

The initial launch is TEST authority, supplied once before the producer starts.
Manager observations and effects are injected. Installed protection is NOT_RUN.
"""
import copy
import errno
import io
import json
import os
import signal
import time
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch
from unittest.mock import Mock
import types

import profile_bootstrap as b
import profile_constructor as s
import profile_contract as c
import profile_executor as e
import profile_ingress as i
import profile_manager as m
import profile_packet as p
import profile_receiver as receiver_exit
import test_ingress


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.fixture=test_ingress.IngressTests();self.fixture.setUp(itinerary=getattr(self,'itinerary',None))
        self.addCleanup(self.fixture.doCleanups)
        self.server=None;self.server_reaped=False
        self.exit_witnesses={}
        self.invocation=dict(operator_unit='TEST-supervisor.service',operator_invocation='a'*32,
            receiver_unit='TEST-fixed-root.service',receiver_invocation='b'*32)

    def start(self,*,sync_error=None,sync_stage=None,lost_reply=None,clock_value=100,clock=None):
        self.clock=clock or (lambda:clock_value)
        # Harness transport stays available to observe a refused exhausted grant.
        # It never changes the authority's original end cutoff.
        self.transport_deadline=max(self.fixture.binding['deadlines']['end']+60,clock_value+1)
        f=self.fixture;self.index_fd=f.memfd(f.index)
        self.state_path=f.control/'supervisor-state'
        fd=os.open(self.state_path,os.O_CREAT|os.O_EXCL|os.O_RDWR|os.O_CLOEXEC,0o600)
        self.state_fd=fd
        self.addCleanup(lambda:os.close(self.state_fd) if self.state_fd is not None else None)
        self.launch=dict(plan=f.plan,contract=f.contract,inputs_raw=f.index,record_binding=f.binding,
            directory_identity=i.identity(f.dirfd),order_identity=f.order_identity,
            capability_identities=f.identities,capability_expected=f.expected,itinerary=f.itinerary,
            recovery=f.recovery,owner_uid=os.getuid(),namespace_identity=55,secret=f.secret,
            index_identity=i.identity(self.index_fd),supervisor_identity=i.identity(fd),invocation=self.invocation)
        binding=dict(record_binding=f.binding,boot_id=s.boot_identity(),directory_identity=i.identity(f.dirfd),
            task='TJS-2504',attempt_id=f.plan['attempt_id'],source=f.plan['source'],
            supervisor_identity=i.identity(fd),namespace_identity=55,
            order_identity=f.order_identity,capability_identities=f.identities,index_identity=i.identity(self.index_fd))
        os.write(fd,c.canonical(dict(schema='meownero-surviving-authority/2',binding=binding,
            mode='LIVE',position=0,pending=None,stage='RESERVED',receiver=None,dispositions={})));os.fsync(fd)
        self.channel,remote=m.private_pair();self.addCleanup(self.channel.close)
        owner=i.process_identity(os.getpid());creds=[os.getpid(),os.getuid(),os.getgid()]
        pid=os.fork()
        if pid==0:
            self.channel.close()
            try:
                authority=s.SurvivingAuthority(self.launch,f.dirfd,self.index_fd,fd,clock=self.clock)
                if lost_reply:
                    original_send=m.send_packet;dropped=False
                    def lose(channel,message,*args,**kwargs):
                        nonlocal dropped
                        if not dropped and (lost_reply=='settle' and message.get('settled') is True or
                                lost_reply=='close' and message.get('result',{}).get('ack')=='close'):
                            dropped=True;raise OSError('TEST lost '+lost_reply+' acknowledgement')
                        return original_send(channel,message,*args,**kwargs)
                    m.send_packet=lose
                if sync_error:
                    original_sync=os.fsync
                    def fail(target):
                        if sync_stage is None or json.loads(os.pread(fd,65537,0))['stage']==sync_stage:
                            raise OSError(sync_error,'TEST supervisor persistence failure')
                        return original_sync(target)
                    os.fsync=fail
                authority.serve(remote,creds,owner,deadline=self.transport_deadline)
                os._exit(0)
            except BaseException:os._exit(2)
        remote.close();os.close(fd);self.state_fd=None;self.server=pid
        self.server_identity=i.process_identity(pid)
        self.server_credentials=[pid,os.getuid(),os.getgid()]
        self.addCleanup(self.stop)

    def stop(self):
        if self.server and not self.server_reaped:
            try:m.send_packet(self.channel,dict(operation='stop'))
            except OSError:pass
            import time
            until=time.monotonic()+2
            while time.monotonic()<until:
                if os.waitpid(self.server,os.WNOHANG)[0]:self.server_reaped=True;return
                time.sleep(.005)
            if i.process_identity(self.server)==self.server_identity:os.kill(self.server,signal.SIGKILL)
            os.waitpid(self.server,0);self.server_reaped=True

    def issue(self,n=0,*,crash=False,recovered=False,mutate=None,lost_ack=False,after_local=False,
              settle=True,exit_after_close=None,unknown_status=False,pause_after_close=None,before_wait=None,skip_auth=False,
              generated=False,launch_delay=None,ambiguous_launch=False,entry_mutate=None):
        f=self.fixture;tx,rx=m.private_pair();parent=[os.getpid(),os.getuid(),os.getgid()]
        pid=os.fork()
        if pid==0:
            tx.close();self.channel.close()
            try:
                command,fds=m.receive_packet(rx,parent,self.transport_deadline,fd_count=2,clock=self.clock)
                client=s.AuthorityClient(fds[0],self.server_credentials,self.server_identity,n,
                    self.clock()+5,clock=self.clock)
                if skip_auth:client.authenticate=lambda anchor:True
                backend=f.backend
                backend.operator_entry_expectation=lambda:client.call('expectation')
                backend.operator_invocation_observation=lambda:copy.deepcopy(self.invocation)
                if crash:
                    def effect(*args):
                        with open(f.root/'effects','ab') as stream:stream.write(b'effect\n')
                        os._exit(9)
                    backend.syscall.side_effect=effect
                if after_local:client.admit=lambda record:os._exit(9)
                if lost_ack:
                    original=client.call
                    def lose(operation):
                        result=original(operation)
                        if operation=='complete':raise OSError('TEST lost completion acknowledgement')
                        return result
                    client.call=lose
                if entry_mutate:
                    original=i.InstalledIngress
                    def changed(boundary,anchor,*args,**kwargs):
                        entry_mutate(anchor)
                        return original(boundary,anchor,*args,**kwargs)
                    i.InstalledIngress=changed
                operator_fd=fds[1]
                if generated:
                    # Consume the generated fixed command and transferred stdin.
                    # OS service launch is injected; the main/constructor/guard,
                    # real sockets, journal, producer and child exit are real.
                    c.require(command['argv']==['/usr/bin/python3','-I','-B',
                        '/opt/meownero/TJS-2504/helper/profile-root-helper.py'],'generated receiver command')
                    os.dup2(fds[1],0);operator_fd=0
                value=s.OperatorConstructor(backend,operator_fd=operator_fd,clock=self.clock,record_authority=client,
                    run=Mock(side_effect=getattr(self,'command_effect',None),
                        return_value=types.SimpleNamespace(returncode=0)))
                with redirect_stdout(io.StringIO()),patch.object(e.c,'HERE',f.install):
                    status=f.module.main([],qualified={c.digest((c.HERE/'profile-root-helper.py').read_bytes()):value})
                if status==0:client.close()
                if status==0 and pause_after_close is not None:os.read(pause_after_close,1)
                if status==0 and exit_after_close is not None:os._exit(exit_after_close)
                os._exit(status)
            except BaseException:os._exit(3)
        rx.close();receiver=i.process_identity(pid)
        witness=None
        if 0<=n<54:
            witness=receiver_exit.ChildExitWitness(receiver,receiver_exit.scope(self.launch,n,receiver),clock=self.clock)
            self.addCleanup(witness.close)
        request=dict(operation='issue',receiver=receiver,record=n,recovered=recovered)
        if mutate:mutate(request)
        m.send_packet(self.channel,request)
        import array,socket
        self.channel.settimeout(5)
        raw,anc,flags,_=self.channel.recvmsg(m.MAX_PACKET,socket.CMSG_SPACE(16)+socket.CMSG_SPACE(16))
        reply=json.loads(raw);fds=[]
        for level,kind,data in anc:
            if kind==socket.SCM_RIGHTS:
                values=array.array('i');values.frombytes(data);fds.extend(values)
        try:
            if not reply.get('issued'):
                os.kill(pid,signal.SIGKILL);os.waitpid(pid,0);return 3
            self.assertEqual(len(fds),2)
            if generated:
                import test_receiver
                manager=dict(bus='user',unique_name=':1.10',client_unique_name=':1.20',epoch='TEST-generated-launch',
                    boot_id=receiver_exit.boot_id(),process=i.process_identity(os.getpid()),uid=os.getuid())
                backend=test_receiver.InjectedManager(manager)
                backend.authenticate_launch=lambda plan,owner:dict(bindings={},record_binding=f.binding)
                def launch(owner,call,deadline):
                    props={key:value for key,kind,value in call['args'][2]}
                    self.generated_call=copy.deepcopy(call)
                    c.require(props['StandardInputFileDescriptor']==fds[1],'original produced operator channel')
                    if launch_delay:launch_delay()
                    m.send_packet(tx,dict(argv=props['ExecStart'][0][1]),[fds[0],props['StandardInputFileDescriptor']])
                    if ambiguous_launch:raise TimeoutError('TEST ambiguous receiver launch after delivery')
                    return '/TEST/generated/job'
                backend.start_transient_unit=launch
                transport=receiver_exit.ManagerTransport(f.plan,manager,backend,clock=self.clock)
                self.generated_transport=transport
                try:transport.start_receiver(n,fds[1],deadline=min(self.clock()+5,
                    p.operation_deadline(f.plan,n,f.binding)))
                except (ValueError,TimeoutError):
                    if not ambiguous_launch and not launch_delay:raise
            else:m.send_packet(tx,dict(start=True),fds)
        finally:
            tx.close()
            for fd in fds:os.close(fd)
        if before_wait:before_wait(receiver)
        def persist(value):
            path=f.root/('receiver-exit-'+str(pid))
            with path.open('wb') as stream:
                stream.write(c.canonical(value));stream.flush();os.fsync(stream.fileno())
            self.assertEqual(json.loads(path.read_bytes()),value)
        until=time.monotonic()+5
        while time.monotonic()<until:
            try:
                value=witness.observe(persist,deadline=f.binding['deadlines']['end']);break
            except ValueError as exc:
                if str(exc)!='exact child terminal event required':raise
                time.sleep(.005)
        else:self.fail('no exact child terminal event')
        self.exit_witnesses[(receiver['pid'],receiver['start'])]=value
        status=receiver_exit.exit_status(value['code'],value['status'])
        self.last_receiver=receiver
        if settle:
            until=time.monotonic()+3
            while time.monotonic()<until:
                snapshot=self.snapshot()
                if 'state' not in snapshot:break  # Failed persistence stays poisoned.
                if snapshot['awaiting_exit']==receiver:
                    self.last_settle=self.settle(receiver,None if unknown_status else status)
                    if self.last_settle!=dict(settled=True) and self.snapshot().get('awaiting_exit')==receiver:
                        # A missing reply retains custody. The original parent
                        # can settle uncertainty, never infer a successful ack.
                        self.last_settle=self.settle(receiver,None)
                    if self.last_settle==dict(settled=True):self.wait_closed()
                    break
                time.sleep(.005)
            else:self.fail('surviving owner did not retain exact exited receiver')
        return status

    def snapshot(self):
        m.send_packet(self.channel,dict(operation='snapshot'))
        return m.receive_packet(self.channel,self.server_credentials,self.transport_deadline,clock=self.clock)[0]

    def wait_closed(self):
        until=time.monotonic()+3
        while time.monotonic()<until:
            snapshot=self.snapshot()
            if snapshot.get('entries_closed'):return snapshot
            time.sleep(.005)
        self.fail('entries did not close under original owner')

    def settle(self,receiver,status,*,confirm=True):
        witness=self.exit_witnesses.get((receiver['pid'],receiver['start']))
        m.send_packet(self.channel,dict(operation='settle',receiver=receiver,witness=witness,uncertain=status is None))
        response=m.receive_packet(self.channel,self.server_credentials,self.transport_deadline,clock=self.clock)[0]
        if response.get('settled') is True:
            expected=dict(scope=witness['scope'],exit_witness_sha256=c.digest(c.canonical(witness)))
            self.assertEqual(response,dict(settled=True,**expected))
        if response.get('settled') is True and confirm:
            m.send_packet(self.channel,dict(operation='confirm_settlement',receiver=receiver,
                exit_witness_sha256=c.digest(c.canonical(witness))))
            confirmed=m.receive_packet(self.channel,self.server_credentials,self.transport_deadline,clock=self.clock)[0]
            if confirmed!=dict(confirmed=True,**expected):return confirmed
            self.last_confirmation=confirmed
        return dict(settled=True) if response.get('settled') is True else response

    def restore_local(self,before):
        for path,(raw,identity) in before.items():
            path.write_bytes(raw);self.assertEqual(identity_of(path),identity)

    def snapshot_local(self):
        f=self.fixture
        return {path:(path.read_bytes(),identity_of(path)) for path in
            [f.order,*[f.control/name for name in f.identities]]}

    def test_fresh_entries_use_original_producer_and_durable_completion(self):
        self.start();self.assertEqual(self.issue(),0)
        self.assertEqual(self.fixture.state()['position'],1)
        self.assertEqual(self.issue(),3);self.assertEqual(self.issue(1),0)
        self.assertEqual(self.fixture.state()['position'],2);self.assertEqual(e.QUALIFIED_ROOT,{})

    def test_same_inode_restoration_after_child_exit9_never_reactivates(self):
        self.start();before=self.snapshot_local();self.assertEqual(self.issue(crash=True),9)
        self.assertEqual(self.fixture.state()['pending'],0);self.restore_local(before)
        self.assertEqual(self.issue(),3);self.assertEqual(self.issue(),3)
        self.assertEqual((self.fixture.root/'effects').read_bytes(),b'effect\n')
        self.assertNotEqual(json.loads(self.state_path.read_bytes())['stage'],'RESERVED')

    def test_crash_between_local_intent_and_supervisor_admission_refuses(self):
        self.start();before=self.snapshot_local();self.assertEqual(self.issue(after_local=True),9)
        self.assertEqual(self.fixture.state()['pending'],0);self.restore_local(before)
        self.assertEqual(self.issue(),3);self.assertFalse((self.fixture.root/'effects').exists())

    def test_lost_completion_acknowledgement_cannot_advance(self):
        self.start();before=self.snapshot_local();self.assertEqual(self.issue(lost_ack=True),3)
        self.restore_local(before);self.assertEqual(self.issue(),3);self.assertEqual(self.issue(1),3)

    def test_supervisor_fsync_and_enospc_prevent_receipt_delivery(self):
        for error in (errno.EIO,errno.ENOSPC):
            with self.subTest(error=error):
                case=SupervisorTests();case.setUp()
                try:
                    case.start(sync_error=error);self.assertEqual(case.issue(),3);self.assertEqual(case.issue(),3)
                    self.assertEqual(case.fixture.state()['position'],0)
                finally:case.doCleanups()

    def test_wrong_receiver_start_and_record54_refuse(self):
        self.start();self.assertEqual(self.issue(mutate=lambda x:x['receiver'].update(start='1')),3)
        self.assertEqual(self.issue(54,recovered=True),3);self.assertEqual(self.fixture.state()['position'],0)

    def test_original_supervisor_loss_has_no_reconnect_or_reconstruction(self):
        self.start();self.stop()
        client=s.AuthorityClient(self.channel.fileno(),self.server_credentials,self.server_identity,0,200,clock=lambda:100)
        with self.assertRaises((FileNotFoundError,ValueError,OSError)):client.call('expectation')

    def test_surviving_memory_refuses_rollback_of_its_own_state_file(self):
        self.start();original=self.state_path.read_bytes();self.assertEqual(self.issue(),0)
        self.state_path.write_bytes(original)
        self.assertEqual(self.issue(1),3);self.assertEqual(self.issue(),3)

    def test_pending_persistence_failure_blocks_effect_and_later_activation(self):
        for error in (errno.EIO,errno.ENOSPC):
            with self.subTest(error=error):
                case=SupervisorTests();case.setUp()
                try:
                    case.start(sync_error=error,sync_stage='PENDING');before=case.snapshot_local()
                    self.assertEqual(case.issue(crash=True),3);case.restore_local(before)
                    self.assertEqual(case.issue(),3);self.assertFalse((case.fixture.root/'effects').exists())
                finally:case.doCleanups()

    def test_uncertain_activation_can_only_enter_original_surviving_cleanup(self):
        self.start();self.assertEqual(self.issue(crash=True),9)
        self.assertEqual(self.issue(self.fixture.cleanup,recovered=True),0)
        self.assertEqual(self.issue(),3)

    def test_uncertain_cleanup_records_never_repeat_after_same_inode_restoration(self):
        import test_lifecycle_source
        for number in range(44,54):
            with self.subTest(record=number):
                case=SupervisorTests();case.itinerary=[number];case.setUp()
                try:
                    f=case.fixture
                    f.backend.authenticate_executor=lambda unused:test_lifecycle_source.bindings(f.plan)
                    def effect(*args,**kwargs):
                        with (f.root/'effects').open('ab') as stream:stream.write(b'effect\n')
                        os._exit(9)
                    f.backend.syscall.side_effect=effect;f.backend.docker.side_effect=effect
                    f.backend.dbus=Mock(side_effect=effect);case.command_effect=effect
                    case.start();before=case.snapshot_local()
                    self.assertEqual(case.issue(number,recovered=True),9)
                    state=case.wait_closed()['state']
                    self.assertTrue(state['dispositions'][str(number)]['uncertain'])
                    self.assertEqual(state['binding']['record_binding']['deadlines'],f.binding['deadlines'])
                    case.restore_local(before)
                    self.assertEqual(case.issue(number,recovered=True),3);case.wait_closed()
                    self.assertEqual((f.root/'effects').read_bytes(),b'effect\n')
                finally:case.doCleanups()

    def test_settled_cleanup_cannot_replay_after_later_uncertainty(self):
        case=SupervisorTests();case.itinerary=[44,45,48];case.setUp()
        try:
            f=case.fixture;case.start();before=case.snapshot_local()
            def completed(*args):
                with (f.root/'effects44').open('ab') as stream:stream.write(b'effect\n')
            f.backend.docker.side_effect=completed
            self.assertEqual(case.issue(44,recovered=True),0);case.wait_closed()
            def uncertain(operation,*args):
                if operation=='terminate_owned':
                    with (f.root/'effects45').open('ab') as stream:stream.write(b'effect\n')
                    os._exit(9)
            f.backend.syscall.side_effect=uncertain
            self.assertEqual(case.issue(45,recovered=True),9);case.wait_closed()
            case.restore_local(before)
            self.assertEqual(case.issue(44,recovered=True),3);case.wait_closed()
            self.assertEqual(case.issue(45,recovered=True),3);case.wait_closed()
            self.assertEqual(case.issue(48,recovered=True),0)
            state=case.wait_closed()['state']
            self.assertTrue(state['dispositions']['44']['completed'])
            self.assertTrue(state['dispositions']['45']['uncertain'])
            self.assertEqual((f.root/'effects44').read_bytes(),b'effect\n')
            self.assertEqual((f.root/'effects45').read_bytes(),b'effect\n')
            self.assertEqual(case.issue(),3)
        finally:case.doCleanups()

    def test_later_cleanup_can_run_after_uncertain_record_without_local_restoration(self):
        case=SupervisorTests();case.itinerary=[44,45];case.setUp()
        try:
            f=case.fixture;case.start()
            f.backend.docker.side_effect=lambda *args:os._exit(9)
            self.assertEqual(case.issue(44,recovered=True),9);case.wait_closed()
            self.assertEqual(case.issue(45,recovered=True),0);case.wait_closed()
            self.assertEqual(f.state()['uncertain'],44)
            self.assertEqual(case.issue(44,recovered=True),3)
        finally:case.doCleanups()

    def test_post_close_abnormal_and_unknown_exits_enter_recovery_only(self):
        for unknown in (False,True):
            with self.subTest(unknown=unknown):
                case=SupervisorTests();case.setUp()
                try:
                    case.start();self.assertEqual(case.issue(exit_after_close=9,unknown_status=unknown),9)
                    state=case.wait_closed()['state']
                    self.assertEqual(state['mode'],'RECOVERY_ONLY')
                    self.assertTrue(state['dispositions']['0']['completed'])
                    self.assertTrue(state['dispositions']['0']['uncertain'])
                    self.assertEqual(state['position'],0)
                    self.assertEqual(case.issue(),3);self.assertEqual(case.issue(44,recovered=True),0)
                finally:case.doCleanups()

    def test_lost_close_and_settle_acknowledgements_never_rearm(self):
        for operation in ('close','settle'):
            with self.subTest(operation=operation):
                case=SupervisorTests();case.setUp()
                try:
                    case.start(lost_reply=operation)
                    self.assertEqual(case.issue(),3 if operation=='close' else 0)
                    # A lost settle reply is ambiguous, but the durable settle
                    # still closes custody; the old record remains consumed.
                    state=case.wait_closed()['state'];self.assertEqual(state['mode'],'RECOVERY_ONLY')
                    self.assertTrue(state['dispositions']['0']['uncertain'])
                    self.assertEqual(case.issue(),3);self.assertEqual(case.issue(1),3)
                    self.assertEqual(case.issue(44,recovered=True),0)
                finally:case.doCleanups()

    def test_missing_and_wrong_receiver_settlement_cannot_release_custody(self):
        self.start();self.assertEqual(self.issue(exit_after_close=9,settle=False),9)
        until=time.monotonic()+3
        while self.snapshot().get('awaiting_exit') is None and time.monotonic()<until:time.sleep(.005)
        self.assertEqual(self.issue(44,recovered=True),3)
        wrong=dict(self.last_receiver,start='wrong')
        self.assertEqual(self.settle(wrong,9),dict(issued=False))
        self.assertFalse(self.snapshot()['entries_closed'])
        self.assertEqual(self.settle(self.last_receiver,9),dict(settled=True));self.wait_closed()
        self.assertEqual(self.issue(44,recovered=True),0)

    def test_live_receiver_and_concurrent_entry_refuse_before_exit(self):
        self.start();read_fd,write_fd=os.pipe()
        self.addCleanup(os.close,read_fd);self.addCleanup(os.close,write_fd)
        def concurrent(receiver):
            try:
                until=time.monotonic()+3
                while time.monotonic()<until:
                    if self.snapshot()['awaiting_exit']==receiver:break
                    time.sleep(.005)
                else:self.fail('receiver did not close before exit')
                self.assertEqual(self.settle(receiver,0),dict(issued=False))
                self.assertEqual(self.issue(1),3)
                self.assertFalse(self.snapshot()['entries_closed'])
            finally:os.write(write_fd,b'x')
        self.assertEqual(self.issue(pause_after_close=read_fd,before_wait=concurrent),0)
        self.wait_closed();self.assertEqual(self.issue(1),0)

    def test_unreceived_settlement_reply_retains_custody_until_uncertain_settlement(self):
        self.start();self.assertEqual(self.issue(settle=False),0)
        self.assertEqual(self.settle(self.last_receiver,0,confirm=False),dict(settled=True))
        # Deliberately withhold confirmation, modeling a reply lost at the
        # launcher even though the server's socket send succeeded.
        self.assertFalse(self.snapshot()['entries_closed'])
        self.assertEqual(self.issue(1),3);self.assertEqual(self.issue(44,recovered=True),3)
        self.assertEqual(self.settle(self.last_receiver,None),dict(settled=True))
        state=self.wait_closed()['state'];self.assertEqual(state['mode'],'RECOVERY_ONLY')
        self.assertTrue(state['dispositions']['0']['uncertain'])
        self.assertEqual(self.issue(1),3);self.assertEqual(self.issue(44,recovered=True),0)

    def test_settlement_fsync_and_enospc_never_release_or_rearm(self):
        for error in (errno.EIO,errno.ENOSPC):
            for stage in ('COMPLETED','SETTLEMENT_SENT'):
                with self.subTest(error=error,stage=stage):
                    case=SupervisorTests();case.setUp()
                    try:
                        case.start(sync_error=error,sync_stage=stage)
                        status=case.issue(exit_after_close=9 if stage=='SETTLEMENT_SENT' else None)
                        self.assertEqual(status,9 if stage=='SETTLEMENT_SENT' else 0)
                        self.assertEqual(case.snapshot(),dict(issued=False))
                        self.assertEqual(case.issue(),3);self.assertEqual(case.issue(44,recovered=True),3)
                    finally:case.doCleanups()

    def test_expired_original_deadline_refuses_issuance(self):
        self.start(clock_value=4600)
        self.assertEqual(self.issue(),3);self.assertEqual(self.issue(44,recovered=True),3)

    def test_missing_stale_substituted_and_unreaped_witnesses_retain_custody(self):
        self.start();self.assertEqual(self.issue(exit_after_close=9,settle=False),9)
        receiver=self.last_receiver;original=self.exit_witnesses[(receiver['pid'],receiver['start'])]
        cases=[None]
        for mutate in (lambda x:x['scope'].update(record=1),lambda x:x.update(boot_id='wrong'),
                lambda x:x['observer'].update(start='1'),lambda x:x['detail'].update(reaped=False),
                lambda x:x['scope']['record_binding']['deadlines'].update(end=9999),
                lambda x:x.update(code=None,status=None),lambda x:x.update(observed_at=201)):
            changed=copy.deepcopy(original);mutate(changed);cases.append(changed)
        for witness in cases:
            m.send_packet(self.channel,dict(operation='settle',receiver=receiver,witness=witness,uncertain=False))
            self.assertEqual(m.receive_packet(self.channel,self.server_credentials,200,clock=lambda:100)[0],
                dict(issued=False))
            self.assertFalse(self.snapshot()['entries_closed'])
        # A supplied legacy zero cannot replace the raw kernel status nine.
        m.send_packet(self.channel,dict(operation='settle',receiver=receiver,status=0))
        self.assertEqual(m.receive_packet(self.channel,self.server_credentials,200,clock=lambda:100)[0],dict(issued=False))
        self.assertEqual(self.settle(receiver,0),dict(settled=True))
        self.assertEqual(self.wait_closed()['state']['mode'],'RECOVERY_ONLY')

    def test_confirmation_requires_exact_durable_witness_digest(self):
        self.start();self.assertEqual(self.issue(settle=False),0)
        self.assertEqual(self.settle(self.last_receiver,0,confirm=False),dict(settled=True))
        m.send_packet(self.channel,dict(operation='confirm_settlement',receiver=self.last_receiver,
            exit_witness_sha256='0'*64))
        self.assertEqual(m.receive_packet(self.channel,self.server_credentials,200,clock=lambda:100)[0],dict(issued=False))
        self.assertFalse(self.snapshot()['entries_closed'])
        self.assertEqual(self.settle(self.last_receiver,None),dict(settled=True))
        self.assertEqual(self.wait_closed()['state']['mode'],'RECOVERY_ONLY')

    def test_skipped_surviving_authentication_cannot_admit_effect(self):
        self.start();self.assertEqual(self.issue(skip_auth=True),3)
        self.assertEqual(self.wait_closed()['state']['mode'],'RECOVERY_ONLY')
        self.assertEqual(self.fixture.backend.calls.count('effect'),0)


def identity_of(path):
    value=path.stat();return [value.st_dev,value.st_ino]


if __name__=='__main__':unittest.main(verbosity=2)
