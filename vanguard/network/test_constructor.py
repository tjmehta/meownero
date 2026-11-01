"""Operator packet -> actual constructor -> ingress -> installed layout -> journal.

All operator/manager authority and OS effects are injected TEST facilities.
Packets, credentials, index seals, process exits and durable files are real,
disposable local observations. No installed startup or survival is established.
"""
import copy
import errno
import io
import json
import os
import types
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock,patch

import profile_bootstrap as b
import profile_constructor as constructor
import profile_contract as c
import profile_executor as e
import profile_ingress as i
import profile_manager as m
import profile_packet as p
import test_ingress


class ConstructorTests(unittest.TestCase):
    def setUp(self):
        self.fixture=test_ingress.IngressTests();self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def wire(self,n=0,*,recovered=False):
        fixture=self.fixture
        entry,ingress=fixture.invocation(n,recovered=recovered)
        tx,rx=b.delivery_pair();fixture.addCleanup(tx.close);fixture.addCleanup(rx.close)
        anchor=copy.deepcopy(ingress.trusted)
        anchor['inputs_sha256']=c.digest(anchor.pop('inputs_raw'))
        invocation=dict(operator_unit='TEST-operator.service',operator_invocation='a'*32,
            receiver_unit='TEST-root-entry.service',receiver_invocation='b'*32)
        receipt=dict(schema='meownero-operator-entry/1',boot_id=constructor.boot_identity(),
            invocation=invocation,anchor=anchor)
        index=fixture.memfd(fixture.index)
        fds=[ingress.endpoint_fd,fixture.dirfd,index]
        expected=dict(schema='meownero-operator-expectation/1',
            operator=i.process_identity(os.getpid()),operator_credentials=[os.getpid(),os.getuid(),os.getgid()],
            receiver=i.process_identity(os.getpid()),receiver_credentials=[os.getpid(),os.getuid(),os.getgid()],
            boot_id=constructor.boot_identity(),invocation=invocation,receipt_sha256='',
            endpoint_identity=i.identity(rx.fileno()),descriptor_identities=[i.identity(fd) for fd in fds],deadline=104)
        return tx,rx,receipt,fds,expected

    def invoke(self,n=0,*,mutate=None,expectation_mutate=None,recovered=False,fresh=False,crash=False):
        fixture=self.fixture
        tx,rx,receipt,fds,expected=self.wire(n,recovered=recovered)
        # The operator pins the canonical receipt independently of its transport.
        expected['receipt_sha256']=c.digest(c.canonical(receipt))
        if expectation_mutate:expectation_mutate(expected)
        if mutate:mutate(receipt,fds)
        backend=fixture.backend
        backend.operator_invocation_observation=lambda:copy.deepcopy(expected['invocation'])
        backend.operator_entry_expectation=lambda:copy.deepcopy(expected)
        runner=Mock(return_value=types.SimpleNamespace(returncode=0))

        def run():
            if crash:backend.syscall.side_effect=lambda *args:os._exit(9)
            value=constructor.OperatorConstructor(backend,operator_fd=rx.fileno(),clock=lambda:100,run=runner,
                record_authority=test_ingress.TestRecordAuthority())
            table={c.digest((c.HERE/'profile-root-helper.py').read_bytes()):value}
            output=io.StringIO()
            with redirect_stdout(output),patch.object(e.c,'HERE',fixture.install):
                status=fixture.module.main([],qualified=table)
            self.assertNotIn('activation',output.getvalue())
            return status

        if not fresh:
            m.send_packet(tx,receipt,fds)
            return run()
        # A separate inherited fixture-only pipe supplies the TEST protected
        # expectation. It is not an implementation of installed authentication.
        read_fd,write_fd=os.pipe()
        pid=os.fork()
        if pid==0:
            os.close(write_fd)
            try:
                with os.fdopen(read_fd) as stream:expected.update(json.load(stream))
                os._exit(run())
            except BaseException:os._exit(2)
        os.close(read_fd)
        try:
            receiver=i.process_identity(pid)
            receipt['anchor']['receiver']=receiver
            receipt['anchor']['receiver_credentials']=[pid,os.getuid(),os.getgid()]
            expected.update(receiver=receiver,receiver_credentials=[pid,os.getuid(),os.getgid()],
                receipt_sha256=c.digest(c.canonical(receipt)))
            m.send_packet(tx,receipt,fds)
            with os.fdopen(write_fd,'w') as stream:json.dump(expected,stream)
        except BaseException:
            os.kill(pid,9);os.waitpid(pid,0)
            raise
        return os.waitstatus_to_exitcode(os.waitpid(pid,0)[1])

    def test_operator_packet_connects_real_root_main_and_replay_refuses(self):
        self.assertEqual(self.invoke(fresh=True),0)
        self.assertEqual(self.fixture.state()['position'],1)
        self.assertEqual(self.invoke(fresh=True),3)
        self.assertEqual(self.invoke(1,fresh=True),0)
        self.assertEqual(e.QUALIFIED_ROOT,{})

    def test_wrong_issuer_boot_unit_source_and_index_refuse_before_effect(self):
        cases=[dict(expectation_mutate=lambda x:x.update(operator=dict(pid=os.getpid(),start='1'))),
            dict(expectation_mutate=lambda x:x.update(boot_id='wrong-boot')),
            dict(expectation_mutate=lambda x:x.update(receiver=dict(pid=os.getpid(),start='1'))),
            dict(mutate=lambda x,f:x['invocation'].update(receiver_unit='wrong-unit')),
            dict(mutate=lambda x,f:x['anchor']['plan']['source'].update(commit='0'*40)),
            dict(mutate=lambda x,f:f.__setitem__(2,self.fixture.memfd(self.fixture.index)))]
        before=self.fixture.order.read_bytes()
        for case in cases:
            with self.subTest(case=case):self.assertEqual(self.invoke(**case),3)
        self.fixture.backend.syscall.assert_not_called()
        self.assertEqual(before,self.fixture.order.read_bytes())

    def test_operator_does_not_trust_an_unpinned_received_receipt(self):
        self.assertEqual(self.invoke(expectation_mutate=lambda x:x.update(receipt_sha256='0'*64)),3)
        self.fixture.backend.syscall.assert_not_called()

    def test_missing_surviving_authority_refuses_before_receipt_or_effect(self):
        boundary=Mock()
        value=constructor.OperatorConstructor(boundary,clock=lambda:100)
        with self.assertRaises(ValueError):value.run_authenticated_inherited_entry()
        boundary.operator_entry_expectation.assert_not_called()

    def test_child_crash_cannot_reactivate_and_recovery_keeps_deadlines(self):
        self.assertEqual(self.invoke(fresh=True,crash=True),9)
        self.assertEqual(self.fixture.state()['pending'],0)
        self.assertEqual(self.invoke(fresh=True),3)
        self.assertEqual(self.invoke(self.fixture.cleanup,recovered=True,fresh=True),0)
        self.assertEqual(self.fixture.state()['mode'],'RECOVERY_ONLY')
        self.assertEqual(self.fixture.state()['binding']['deadlines'],self.fixture.contract['deadlines'])

    def test_uncertain_operator_delivery_and_ENOSPC_never_repair_state(self):
        self.assertEqual(self.invoke(expectation_mutate=lambda x:x.update(deadline=99)),3)
        with patch.object(os,'fsync',side_effect=OSError(errno.ENOSPC,'TEST write failure')):
            self.assertEqual(self.invoke(),3)
        self.fixture.backend.syscall.assert_not_called()
        self.assertEqual(self.invoke(),3)


class PrefixLifetimeTests(unittest.TestCase):
    def test_prepared_objects_have_no_second_creation_path(self):
        packet=p.render(p.source_plan())
        prefix=packet['operator_prefix']['operations']
        self.assertEqual({x['sequence'] for x in prefix},{1,2,3,4,7,8,9,10,11,12,13,14,15,16})
        for original in prefix:
            record=packet['records'][original['sequence']]
            self.assertEqual(record['operation'],'verify_prepared')
            self.assertEqual(record['args']['original_record_sha256'],c.digest(c.canonical(original)))
            self.assertEqual(record['writable'],[])
        self.assertEqual(len(packet['records']),55);self.assertEqual(len(packet['units']),8)
        self.assertEqual(packet['operator_prefix']['installed_implementation'],'UNIMPLEMENTED_UNQUALIFIED')

    def test_terminal_unmount_is_after_journal_exit_and_final_tail(self):
        packet=p.render(p.source_plan())
        self.assertNotIn('normal_unmount_C',packet['records'][52]['args'])
        terminal=packet['terminal_handoff']['ordered']
        self.assertLess(terminal.index('record53_pending_observer_and_durable_completion'),
            terminal.index('all_C_bound_entries_exit_and_close_journal_directory_descriptors'))
        self.assertLess(terminal.index('account_and_sync_final_C_export_tail'),
            terminal.index('normal_C_unmount_and_independent_absence'))
        self.assertEqual(packet['records'][54]['phase'],'dispose')
        self.assertEqual(packet['terminal_handoff']['implementation'],'UNIMPLEMENTED_UNQUALIFIED')


if __name__=='__main__':unittest.main(verbosity=2)
