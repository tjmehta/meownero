"""Connected source traversal. All OS effects/manager observations are MODELED.

Fifty-four records traverse fresh root entries; record 54 must refuse. This is
not the conditional OS-state matrix or installed prefix/terminal qualification.
"""
import copy
import errno
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock,patch

import profile_contract as c
import profile_executor as e
import profile_manager as m
import profile_packet as p
import profile_runtime as r
import test_executor
import test_supervisor


def bindings(plan):
    packet=p.render(plan)
    tokens=e.TOKEN.findall(json.dumps([packet['records'],packet['operator_prefix']['operations']]))
    values={name[1:]:'/fixture/'+name[1:] for name in tokens}
    values.update(BOUND_PYTHON='/usr/bin/python3',BOUND_RUN_OUTER=e.CHILD_DIRECTORY+'/run-outer.py',
        BOUND_RUN_PROFILE=e.CHILD_DIRECTORY+'/run-profile.py',W='/fixture/W')
    return values


class PrefixBoundary(test_executor.InjectedBoundary):
    def authenticate_prefix(self,plan,digest):
        self.calls.append(('authenticate',digest));return bindings(plan)
    def establish_prefix_accounting(self,charge):self.calls.append(('accounting',copy.deepcopy(charge)))
    def admit_prefix_record(self,record):self.calls.append(('prefix_admit',record['sequence']));return 200
    def complete_prefix_record(self,record,deadline):
        self.calls.append(('prefix_complete',record['sequence']))
        return dict(original_record_sha256=c.digest(c.canonical(record)),identity=['TEST',record['sequence']])
    def verify_prepared_identity(self,observed):self.calls.append(('identity',copy.deepcopy(observed)))


class LifecycleSourceTests(unittest.TestCase):
    def prefix(self,plan=None):
        plan=p.source_plan() if plan is None else plan
        backend=PrefixBoundary();runner=Mock(return_value=types.SimpleNamespace(returncode=0))
        prefix=e.PrefixExecutor(plan,backend,clock=lambda:100,run=runner)
        return plan,backend,prefix,runner

    def test_fourteen_originals_accounted_then_verify_prepared_without_reexecution(self):
        plan,backend,prefix,runner=self.prefix();prepared=prefix.run_authenticated_inherited_entry()
        originals=p.render(plan)['operator_prefix']['operations']
        self.assertEqual(len(prepared),14)
        self.assertEqual(backend.calls[1][0],'accounting')
        self.assertEqual([x[1] for x in backend.calls if x[0]=='prefix_complete'],[x['sequence'] for x in originals])
        count=runner.call_count
        for record in p.render(plan)['records']:
            if record['operation']=='verify_prepared':prefix.verify_prepared(record['args'])
        self.assertEqual(runner.call_count,count)
        with self.assertRaises(ValueError):prefix.run_authenticated_inherited_entry()
        request=copy.deepcopy(p.render(plan)['records'][1]['args']);request['original_record_sha256']='0'*64
        with self.assertRaises(ValueError):prefix.verify_prepared(request)
        backend.verify_prepared_identity=Mock(side_effect=ValueError('original identity lost'))
        with self.assertRaises(ValueError):prefix.verify_prepared(p.render(plan)['records'][1]['args'])

    def test_prefix_failed_accounting_never_effects_or_retries(self):
        unused,backend,prefix,runner=self.prefix()
        backend.establish_prefix_accounting=Mock(side_effect=OSError(errno.ENOSPC,'TEST'))
        with self.assertRaises(OSError):prefix.run_authenticated_inherited_entry()
        runner.assert_not_called();self.assertEqual(len(backend.calls),1)
        with self.assertRaises(ValueError):prefix.run_authenticated_inherited_entry()

    def test_original_reservations_never_overwrite_partial_fsync_failure(self):
        with tempfile.TemporaryDirectory(prefix='TJS2504-prefix-source-') as name:
            root=Path(name);root.chmod(0o700);fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY)
            try:
                with patch.object(os,'fsync',side_effect=OSError(errno.EIO,'TEST')):
                    with self.assertRaises(OSError):r.reserve_record_state(fd,{},[0,44],[44],b'x'*32,owner_uid=os.getuid())
                before=(root/'record-order').read_bytes()
                with self.assertRaises(FileExistsError):r.reserve_record_state(fd,{},[0,44],[44],b'x'*32,owner_uid=os.getuid())
                self.assertEqual(before,(root/'record-order').read_bytes())
            finally:os.close(fd)

    def test_fixed_custodian_default_refusal_and_empty_registry(self):
        path=c.HERE/'profile-custodian.py'
        spec=importlib.util.spec_from_file_location('source_custodian',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.assertEqual(module.QUALIFIED_CUSTODIANS,{})
        for flags in (['-B'],['-I','-B']):
            result=subprocess.run([sys.executable,*flags,str(path)],capture_output=True,text=True,timeout=5)
            self.assertEqual(result.returncode,3);self.assertEqual(result.stderr,'')
            self.assertFalse(json.loads(result.stdout)['launch_ready'])
        with redirect_stdout(io.StringIO()):self.assertEqual(module.main(['forbidden']),3)

    def terminal(self):
        boundary=Mock()
        for name in ('record_durably_completed','all_C_entries_exited_and_closed','independent_workers_exited',
                'normal_unmount_C_and_absence','independent_original_lock_reacquire'):
            getattr(boundary,name).return_value=True
        return boundary,r.TerminalCustody(boundary,dict(deadlines=dict(end=200)),clock=lambda:100)

    def test_terminal_retains_custody_until_durable_records_independent_exits_and_tail(self):
        backend,terminal=self.terminal();result=terminal.run_authenticated_inherited_entry()
        self.assertEqual(result['native_execution'],'NOT_RUN')
        self.assertEqual([call[0] for call in backend.mock_calls],[
            'authenticate_terminal','record_durably_completed','record_durably_completed',
            'all_C_entries_exited_and_closed','independent_workers_exited','account_and_sync_final_tail',
            'preserve_control_quarantine_and_archive','close_all_C_writers','normal_unmount_C_and_absence',
            'close_original_namespace','release_original_lock_descriptions','independent_original_lock_reacquire'])
        with self.assertRaises(ValueError):terminal.run_authenticated_inherited_entry()

    def test_terminal_failure_never_releases_namespace_or_original_lock(self):
        for name in ('record_durably_completed','all_C_entries_exited_and_closed','independent_workers_exited',
                'normal_unmount_C_and_absence'):
            with self.subTest(name=name):
                backend,terminal=self.terminal();getattr(backend,name).return_value=False
                with self.assertRaises(ValueError):terminal.run_authenticated_inherited_entry()
                backend.close_original_namespace.assert_not_called();backend.release_original_lock_descriptions.assert_not_called()
        backend,terminal=self.terminal();backend.account_and_sync_final_tail.side_effect=OSError(errno.ENOSPC,'TEST')
        with self.assertRaises(OSError):terminal.run_authenticated_inherited_entry()
        backend.close_all_C_writers.assert_not_called();backend.release_original_lock_descriptions.assert_not_called()

    def test_all_non_disposal_records_fresh_root_entries_and_eight_unit_declarations(self):
        case=test_supervisor.SupervisorTests();case.itinerary=list(range(54));case.setUp()
        try:
            f=case.fixture;plan,backend,prefix,runner=self.prefix(f.plan)
            prefix.run_authenticated_inherited_entry()
            f.backend.authenticate_executor=lambda unused:bindings(f.plan)
            f.backend.execution_context=lambda record,exact,deadline:dict(env={'LC_ALL':'C'},cwd='/fixture/W',
                pass_fds=[],uid=record['uid'],gid=record['gid'],extra_groups=[])
            def syscall(operation,args,deadline):
                if operation=='verify_prepared':prefix.verify_prepared(args)
            f.backend.syscall.side_effect=syscall
            case.start()
            for number in range(54):
                self.assertEqual(case.issue(number,recovered=number>=f.cleanup,generated=True),0,'record '+str(number))
            m.send_packet(case.channel,dict(operation='snapshot'))
            snapshot,_=m.receive_packet(case.channel,case.server_credentials,200,clock=lambda:100)
            self.assertEqual(snapshot['completed'],list(range(54)));self.assertTrue(snapshot['entries_closed'])
            self.assertEqual(case.issue(54,recovered=True),3)
            self.assertEqual(len(p.units(f.plan)),8)
            self.assertEqual(f.state()['position'],len(f.recovery))
        finally:case.doCleanups()


if __name__=='__main__':unittest.main(verbosity=2)
