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
import test_ingress


class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.fixture=test_ingress.IngressTests();self.fixture.setUp(itinerary=getattr(self,'itinerary',None))
        self.addCleanup(self.fixture.doCleanups)
        self.server=None;self.server_reaped=False
        self.invocation=dict(operator_unit='TEST-supervisor.service',operator_invocation='a'*32,
            receiver_unit='TEST-fixed-root.service',receiver_invocation='b'*32)

    def start(self,*,sync_error=None,sync_stage=None):
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
            order_identity=f.order_identity,capability_identities=f.identities,index_identity=i.identity(self.index_fd))
        os.write(fd,c.canonical(dict(schema='meownero-surviving-authority/1',binding=binding,
            mode='LIVE',position=0,pending=None,stage='RESERVED')));os.fsync(fd)
        self.channel,remote=m.private_pair();self.addCleanup(self.channel.close)
        owner=i.process_identity(os.getpid());creds=[os.getpid(),os.getuid(),os.getgid()]
        pid=os.fork()
        if pid==0:
            self.channel.close()
            try:
                authority=s.SurvivingAuthority(self.launch,f.dirfd,self.index_fd,fd,clock=lambda:100)
                if sync_error:
                    original_sync=os.fsync
                    def fail(target):
                        if sync_stage is None or json.loads(os.pread(fd,65537,0))['stage']==sync_stage:
                            raise OSError(sync_error,'TEST supervisor persistence failure')
                        return original_sync(target)
                    os.fsync=fail
                authority.serve(remote,creds,owner,deadline=200)
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

    def issue(self,n=0,*,crash=False,recovered=False,mutate=None,lost_ack=False,after_local=False):
        f=self.fixture;tx,rx=m.private_pair();parent=[os.getpid(),os.getuid(),os.getgid()]
        pid=os.fork()
        if pid==0:
            tx.close();self.channel.close()
            try:
                _,fds=m.receive_packet(rx,parent,200,fd_count=2,clock=lambda:100)
                client=s.AuthorityClient(fds[0],self.server_credentials,self.server_identity,n,200,clock=lambda:100)
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
                value=s.OperatorConstructor(backend,operator_fd=fds[1],clock=lambda:100,record_authority=client,
                    run=Mock(return_value=types.SimpleNamespace(returncode=0)))
                with redirect_stdout(io.StringIO()),patch.object(e.c,'HERE',f.install):
                    status=f.module.main([],qualified={c.digest((c.HERE/'profile-root-helper.py').read_bytes()):value})
                if status==0:client.close()
                os._exit(status)
            except BaseException:os._exit(3)
        rx.close();receiver=i.process_identity(pid)
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
            self.assertEqual(len(fds),2);m.send_packet(tx,dict(start=True),fds)
        finally:
            tx.close()
            for fd in fds:os.close(fd)
        status=os.waitstatus_to_exitcode(os.waitpid(pid,0)[1])
        if status==0:
            m.send_packet(self.channel,dict(operation='settle',receiver=receiver,status=status))
            response,_=m.receive_packet(self.channel,self.server_credentials,200,clock=lambda:100)
            self.assertEqual(response,dict(settled=True))
        return status

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


def identity_of(path):
    value=path.stat();return [value.st_dev,value.st_ino]


if __name__=='__main__':unittest.main(verbosity=2)
