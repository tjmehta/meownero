"""Original deadline regressions through generated receiver delivery and real main.

Clock and effects/OS launch are injected. Authority sockets, producer process,
install guard, journal and exact child-exit witness are real. No host authority.
"""
import copy
import json
import mmap
import os
import struct
import subprocess
import types
import unittest
from unittest.mock import Mock

import profile_contract as c
import profile_packet as p
import profile_receiver as r
import test_lifecycle_source as lifecycle
import test_supervisor as supervisor


class SharedClock:
    def __init__(self,value=100):
        self.memory=mmap.mmap(-1,8);self.set(value)
    def set(self,value):self.memory[:]=struct.pack('d',value)
    def __call__(self):return struct.unpack('d',self.memory[:])[0]
    def close(self):self.memory.close()


class DeadlineTests(unittest.TestCase):
    def fixture(self,records,*,lost_reply=None):
        clock=SharedClock();self.addCleanup(clock.close)
        case=supervisor.SupervisorTests();case.itinerary=records;case.setUp();self.addCleanup(case.doCleanups)
        f=case.fixture
        f.backend.authenticate_executor=lambda plan:lifecycle.bindings(plan)
        f.backend.execution_context=lambda record,exact,deadline:dict(env={'LC_ALL':'C'},cwd='/fixture/W',
            pass_fds=[],uid=record['uid'],gid=record['gid'],extra_groups=[])
        def effect(*args):
            with (f.root/'effects').open('ab') as stream:stream.write(b'effect\n')
            clock.set(getattr(case,'effect_time',clock()))
            if getattr(case,'effect_timeout',False):raise subprocess.TimeoutExpired('TEST injected effect',1)
            return types.SimpleNamespace(returncode=0)
        case.command_effect=effect
        f.backend.syscall.side_effect=effect;f.backend.docker.side_effect=effect;f.backend.dbus=Mock(side_effect=effect)
        case.start(clock=clock,lost_reply=lost_reply)
        return case,clock

    def test_valid_long_records_consume_generated_call_and_complete_after_thirty_seconds(self):
        for number in (17,25,39,41,43):
            with self.subTest(record=number):
                case,clock=self.fixture([number,44]);case.effect_time=131
                self.assertEqual(case.issue(number,generated=True),0)
                snapshot=case.wait_closed();self.assertEqual(snapshot['completed'],[number])
                self.assertFalse(snapshot['state']['dispositions'][str(number)]['uncertain'])
                props={key:value for key,kind,value in case.generated_call['args'][2]}
                cutoff=p.operation_deadline(case.fixture.plan,number,case.fixture.binding)
                self.assertEqual(props['RuntimeMaxUSec'],int((cutoff-100)*1e6))
                self.assertGreater(props['RuntimeMaxUSec'],30_000_000)
                self.assertEqual((case.fixture.root/'effects').read_bytes(),b'effect\n')
                self.assertEqual(clock(),131)

    def test_expiry_and_equality_before_issue_have_no_effect(self):
        for number,at in ((17,1000),(25,4300),(39,3700),(41,4301),(43,4300),(44,4600)):
            with self.subTest(record=number,at=at):
                case,clock=self.fixture([number]);clock.set(at)
                self.assertEqual(case.issue(number,generated=True,recovered=number>=44),3)
                self.assertFalse((case.fixture.root/'effects').exists())
                state=json.loads(case.state_path.read_bytes())
                self.assertEqual(state['dispositions'],{})

    def test_original_phase_limits_and_preparation_caps_are_distinct(self):
        case,clock=self.fixture([0]);binding=case.fixture.binding;plan=case.fixture.plan
        expected={0:1300,7:400,17:1000,24:3700,25:4300,26:3700,28:3700,
            29:3700,39:3700,41:4300,42:3700,43:4300,44:4600,53:4600}
        for number,cutoff in expected.items():
            self.assertEqual(p.operation_deadline(plan,number,binding),cutoff,number)
        altered=copy.deepcopy(binding);altered['preparation']['archive_origin']=600
        self.assertEqual(p.operation_deadline(plan,17,altered),1300)
        with self.assertRaises(ValueError):p.operation_deadline(plan,54,binding)

    def test_inconsistent_or_substituted_bindings_refuse_before_effect(self):
        mutations=(lambda a:a['record_binding']['deadlines'].update(work=9999),
            lambda a:a['record_binding']['preparation'].update(origin=101),
            lambda a:a['envelope']['request'].update(deadline=9999),
            lambda a:a['record_binding']['preparation'].update(archive_origin=float('nan')))
        for mutate in mutations:
            with self.subTest(mutation=mutations.index(mutate)):
                case,clock=self.fixture([25,44])
                self.assertEqual(case.issue(25,generated=True,entry_mutate=mutate),3)
                self.assertFalse((case.fixture.root/'effects').exists())
                self.assertEqual(case.wait_closed()['state']['mode'],'RECOVERY_ONLY')
                self.assertEqual(case.issue(25,generated=True),3)

    def test_delayed_receiver_start_does_not_renew_delivery_or_operation(self):
        for at,status in ((102,0),(105,3),(4300,3)):
            with self.subTest(at=at):
                case,clock=self.fixture([25,44])
                self.assertEqual(case.issue(25,generated=True,launch_delay=lambda:clock.set(at)),status)
                state=case.wait_closed()['state']
                if status:
                    self.assertTrue(state['dispositions']['25']['uncertain'])
                    self.assertFalse((case.fixture.root/'effects').exists())
                self.assertEqual(case.issue(25,generated=True),3)

    def test_expiry_after_bound_record_verification_prevents_effect(self):
        case,clock=self.fixture([25,44]);original=case.fixture.backend.verify_bound_record
        def expired(*args):original(*args);clock.set(4300)
        case.fixture.backend.verify_bound_record=expired
        self.assertEqual(case.issue(25,generated=True),3)
        self.assertFalse((case.fixture.root/'effects').exists())
        self.assertTrue(case.wait_closed()['state']['dispositions']['25']['uncertain'])

    def test_late_and_timeout_effects_retain_consumption_and_only_original_cleanup(self):
        for number,at,timeout in ((25,4300,False),(43,4301,False),(39,3700,False),(25,131,True)):
            with self.subTest(record=number,at=at,timeout=timeout):
                case,clock=self.fixture([number,44,45]);case.effect_time=at;case.effect_timeout=timeout
                before=case.snapshot_local()
                self.assertEqual(case.issue(number,generated=True),3)
                state=case.wait_closed()['state'];self.assertEqual(state['mode'],'RECOVERY_ONLY')
                self.assertTrue(state['dispositions'][str(number)]['consumed'])
                self.assertTrue(state['dispositions'][str(number)]['uncertain'])
                case.restore_local(before);self.assertEqual(case.issue(number,generated=True),3)
                case.effect_timeout=False
                self.assertEqual(case.issue(44,generated=True,recovered=True),0)
                self.assertEqual(case.issue(44,generated=True,recovered=True),3)
                self.assertEqual(case.issue(54,generated=True,recovered=True),3)
                self.assertEqual(case.wait_closed()['state']['binding']['record_binding'],case.fixture.binding)

    def test_ambiguous_launch_retains_original_consumption_and_manager_name(self):
        case,clock=self.fixture([25,44]);case.effect_time=131
        self.assertEqual(case.issue(25,generated=True,ambiguous_launch=True,unknown_status=True),0)
        state=case.wait_closed()['state'];self.assertEqual(state['mode'],'RECOVERY_ONLY')
        self.assertTrue(state['dispositions']['25']['uncertain'])
        with self.assertRaises(ValueError):case.generated_transport.start_receiver(25,17,deadline=136)
        self.assertEqual(case.issue(25,generated=True),3)
        self.assertEqual(case.issue(44,generated=True,recovered=True),0)

    def test_lost_long_completion_and_settlement_replies_cannot_reactivate(self):
        for lost in ('complete','settle','close'):
            with self.subTest(reply=lost):
                case,clock=self.fixture([25,44],lost_reply=lost if lost!='complete' else None)
                case.effect_time=131
                self.assertEqual(case.issue(25,generated=True,lost_ack=lost=='complete'),3 if lost=='complete' else 0)
                state=case.wait_closed()['state'];self.assertEqual(state['mode'],'RECOVERY_ONLY')
                self.assertTrue(state['dispositions']['25']['uncertain'])
                self.assertEqual(case.issue(25,generated=True),3)
                self.assertEqual(case.issue(44,generated=True,recovered=True),0)

    def test_late_settlement_confirmation_keeps_completed_record_uncertain(self):
        case,clock=self.fixture([25,44]);case.effect_time=131
        self.assertEqual(case.issue(25,generated=True,settle=False),0)
        receiver=case.last_receiver
        self.assertEqual(case.settle(receiver,0,confirm=False),dict(settled=True))
        clock.set(4300)
        import profile_manager as m
        witness=case.exit_witnesses[(receiver['pid'],receiver['start'])]
        m.send_packet(case.channel,dict(operation='confirm_settlement',receiver=receiver,
            exit_witness_sha256=c.digest(c.canonical(witness))))
        response,_=m.receive_packet(case.channel,case.server_credentials,4600,clock=clock)
        self.assertTrue(response['confirmed'])
        state=case.wait_closed()['state'];self.assertEqual(state['mode'],'RECOVERY_ONLY')
        self.assertTrue(state['dispositions']['25']['uncertain'])
        self.assertEqual(case.issue(25,generated=True),3)


if __name__=='__main__':unittest.main(verbosity=2)
