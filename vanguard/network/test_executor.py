"""Disposable source checks; privileged effects and installed survival NOT_RUN."""
import copy
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
import profile_dispatch as d
import profile_executor as e
import profile_packet as p
import profile_runtime as r


def transport_predicate(calls):
    services=[x for x in calls if x['args'][0].endswith('.service')]
    props=lambda call:{key:value for key,kind,value in call['args'][2]}
    ipv4=[x for x in services if 'AF_INET' in props(x)['RestrictAddressFamilies'][1]]
    return (len(calls)==8 and len(ipv4)==1 and ipv4[0]['args'][0].endswith('-workload.service') and
        props(ipv4[0])['KillMode']=='control-group' and
        props(ipv4[0])['ExecStart'][0][1]==p.dockerd_argv() and
        all('AF_INET6' not in props(x)['RestrictAddressFamilies'][1] and
            'AF_PACKET' not in props(x)['RestrictAddressFamilies'][1] for x in services))


class TransportTests(unittest.TestCase):
    def test_new_transport_and_known_bad_exact_base(self):
        calls=p.units(p.source_plan())
        self.assertTrue(transport_predicate(calls))
        base=json.loads(subprocess.check_output(['git','show',
            '160c4651bfbb5de74be34d928496e9f73c5b772f:vanguard/network/integration/unit-manifest.json']))
        original=base['units'] if isinstance(base,dict) else base
        self.assertFalse(transport_predicate(original))

    def test_dockerd_argv_unchanged_and_no_keeper_child_exec(self):
        base=json.loads(subprocess.check_output(['git','show',
            '160c4651bfbb5de74be34d928496e9f73c5b772f:vanguard/network/integration/lifecycle-packet.json']))
        old=next(x['args'] for x in base['records'] if x['operation']=='dockerd')
        self.assertEqual(p.dockerd_argv(),old)
        packet=p.render(p.source_plan())
        self.assertNotIn('dockerd',[x['operation'] for x in packet['records'] if x['kind']=='argv'])
        workload=packet['units'][-1]
        props={k:v for k,t,v in workload['args'][2]}
        self.assertTrue(props['Slice'].endswith('-work.slice'))
        self.assertEqual(props['InaccessiblePaths'],['-/run/docker.sock','-/var/run/docker.sock'])
        # Model only: kernel filters and actual container ancestry are NOT_RUN.
        descendants={'monerod':'container','container':'dockerd','dockerd':workload['args'][0]}
        name='monerod'
        while name in descendants:name=descendants[name]
        self.assertEqual(name,workload['args'][0])
        start=next(x['sequence'] for x in packet['records'] if x['operation']=='StartTransientUnit' and
            x['args']['args'][0].endswith('-workload.service'))
        view=next(x['sequence'] for x in packet['records'] if x['operation']=='workload_namespace_view')
        mount=max(x['sequence'] for x in packet['records'] if x['operation']=='mount' and x['phase']=='work')
        self.assertLess(mount,view);self.assertLess(view,start)

    def test_control_services_keep_original_families(self):
        for call in p.units(p.source_plan()):
            if call['delivery'] is not None:
                props={k:v for k,t,v in call['args'][2]}
                self.assertEqual(props['RestrictAddressFamilies'],[True,['AF_UNIX','AF_NETLINK']])


class BurnTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='TJS2504-capability-source-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.dirfd=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC);self.addCleanup(os.close,self.dirfd)
        self.secret=b'x'*32
        self.expected=dict(bindings={'source':'a'*64,'attempt':'1'*32},activation_sha256=c.digest(self.secret),role='prepare')
        self.identities={}
        for role in ('prepare','first-serve'):
            expected={**self.expected,'role':role}
            path=self.root/role;path.write_bytes(c.canonical(dict(schema='meownero-manager-slot/1',state='RESERVED',**expected)))
            path.chmod(0o600);self.identities[role]=[path.stat().st_dev,path.stat().st_ino]

    def store(self,**kwargs):
        return r.CapabilityStore(self.dirfd,self.identities,owner_uid=os.getuid(),**kwargs)

    def test_preparation_and_first_activation_are_distinct_and_persistent(self):
        for role in self.identities:
            expected={**self.expected,'role':role}
            self.assertEqual(self.store().consume(role,expected,self.secret,deadline=2,clock=lambda:1)['state'],'QUARANTINED')
            with self.assertRaises(ValueError):self.store().consume(role,expected,self.secret,deadline=2,clock=lambda:1)

    def test_recovery_reserved_state_never_rearms(self):
        with self.assertRaises(ValueError):self.store(recovered=True).consume('prepare',self.expected,self.secret,deadline=2,clock=lambda:1)
        self.assertEqual(json.loads((self.root/'prepare').read_bytes())['state'],'RESERVED')

    def test_wrong_secret_source_or_deadline_has_no_effect(self):
        for expected,secret,end in [(self.expected,b'y'*32,2),({**self.expected,'bindings':{}},self.secret,2),
                (self.expected,self.secret,0)]:
            with self.assertRaises(ValueError):self.store().consume('prepare',expected,secret,deadline=end,clock=lambda:1)
        self.assertEqual(json.loads((self.root/'prepare').read_bytes())['state'],'RESERVED')

    def test_fsync_uncertainty_burns_instance_and_spent_slot(self):
        store=self.store()
        with patch.object(os,'fsync',side_effect=OSError('fixture fsync failure')):
            with self.assertRaises(OSError):store.consume('prepare',self.expected,self.secret,deadline=2,clock=lambda:1)
        with self.assertRaises(ValueError):store.consume('prepare',self.expected,self.secret,deadline=2,clock=lambda:1)
        with self.assertRaises(ValueError):self.store().consume('prepare',self.expected,self.secret,deadline=2,clock=lambda:1)

    def test_workload_deletion_cannot_clear_control_burn(self):
        self.store().consume('prepare',self.expected,self.secret,deadline=2,clock=lambda:1)
        work=self.root/'disposable-workload';work.mkdir();work.rmdir()
        self.assertEqual([ (self.root/'prepare').stat().st_dev,(self.root/'prepare').stat().st_ino],self.identities['prepare'])
        with self.assertRaises(ValueError):self.store().consume('prepare',self.expected,self.secret,deadline=2,clock=lambda:1)

    def test_symlink_replacement_and_missing_slots_refuse(self):
        path=self.root/'prepare';path.unlink();path.symlink_to(self.root/'first-serve')
        with self.assertRaises(OSError):self.store().consume('prepare',self.expected,self.secret,deadline=2,clock=lambda:1)
        path.unlink()
        with self.assertRaises(OSError):self.store().consume('prepare',self.expected,self.secret,deadline=2,clock=lambda:1)

    def test_fresh_process_cannot_replay_spent_capability(self):
        expected={**self.expected,'role':'first-serve'}
        self.store().consume('first-serve',expected,self.secret,deadline=2,clock=lambda:1)
        pid=os.fork()
        if pid==0:
            try:self.store().consume('first-serve',expected,self.secret,deadline=2,clock=lambda:1)
            except ValueError:os._exit(0)
            except BaseException:os._exit(2)
            os._exit(1)
        self.assertEqual(os.waitpid(pid,0)[1],0)

    def test_two_competing_processes_have_at_most_one_success(self):
        children=[]
        for unused in range(2):
            pid=os.fork()
            if pid==0:
                try:self.store().consume('prepare',self.expected,self.secret,deadline=2,clock=lambda:1)
                except (ValueError,OSError):os._exit(1)
                except BaseException:os._exit(2)
                os._exit(0)
            children.append(pid)
        statuses=[os.waitpid(pid,0)[1] for pid in children]
        self.assertEqual(sorted(statuses),[0,256])


class MeterDeadlineTailTests(unittest.TestCase):
    def test_cumulative_overwrites_not_refunded_by_lower_occupancy(self):
        persisted=[];meter=r.WriteMeter(phase='runtime',persist=lambda value:persisted.append(copy.deepcopy(value)))
        meter.reserve('workload',10*p.GIB,p.GIB)
        meter.reserve('workload',5*p.GIB,1)
        with self.assertRaises(ValueError):meter.reserve('workload',1,0)
        self.assertEqual(meter.writes['workload'],15*p.GIB+1)
        with self.assertRaises(ValueError):meter.reserve('control',0,0)
        self.assertEqual(len(persisted),2)

    def test_each_capacity_and_preparation_write_limit(self):
        for area,size in p.ALLOCATION.items():
            with self.subTest(area=area):
                meter=r.WriteMeter(phase='runtime',persist=lambda value:None)
                with self.assertRaises(ValueError):meter.reserve(area,0,size+1)
        meter=r.WriteMeter(phase='preparation',persist=lambda value:None)
        with self.assertRaises(ValueError):meter.reserve('workload',1,0)
        meter=r.WriteMeter(phase='preparation',persist=lambda value:None)
        with self.assertRaises(ValueError):meter.reserve('control',1536*p.MIB+1,0)

    def test_persist_failure_prevents_writer_and_does_not_refund(self):
        meter=r.WriteMeter(phase='runtime',persist=Mock(side_effect=OSError('fixture ENOSPC')))
        writer=Mock()
        with self.assertRaises(OSError):
            meter.reserve('control',42,42);writer()
        writer.assert_not_called();self.assertEqual(meter.writes['control'],42)
        with self.assertRaises(ValueError):meter.reserve('control',0,0)

    def test_recovered_accounting_keeps_cumulative_charges(self):
        state=[];meter=r.WriteMeter(phase='runtime',persist=lambda value:state.append(value))
        meter.reserve('workload',15*p.GIB,1)
        recovered=r.WriteMeter(phase='runtime',persist=lambda value:None,recovered=state[-1])
        with self.assertRaises(ValueError):recovered.reserve('control',1,0)

    def test_deadline_owner_enforces_original_times_on_late_restart(self):
        now=[4400];calls=[]
        timer=r.AbsoluteDeadlines(100,'fixture-boot',clock=lambda:now[0])
        def wait(at):calls.append(('wait',at));now[0]=at
        timer.enforce({key:lambda at,key=key:calls.append((key,at)) for key in timer.deadlines},wait,observed_boot='fixture-boot')
        self.assertEqual(calls,[('build',3700),('work',4300),('wait',4600),('end',4600)])
        with self.assertRaises(ValueError):timer.enforce({},wait,observed_boot='different-boot')

    def tail(self,*,now=4500):
        contract=dict(deadlines=dict(end=4600),source='fixture')
        identity=[123,'456'];meter=r.WriteMeter(phase='runtime',persist=lambda x:None)
        tail=r.ObserverTail(contract,identity,meter,clock=lambda:now)
        pending=dict(result='PENDING_OBSERVER_EXIT',contract_sha256=c.digest(c.canonical(contract)),observer_identity=identity)
        exit=Mock(return_value=dict(identity=identity,exited=True,reaped=True,status=0))
        metrics=Mock(return_value=dict(written=10,occupied=10,cpu_seconds=1,memory_bytes=1,pids=1,all_workers_exited=True))
        return tail,pending,exit,metrics

    def test_tail_after_exact_observer_exit_is_charged(self):
        tail,pending,exit,metrics=self.tail();order=[]
        exit.side_effect=lambda *args:(order.append('exit') or exit.return_value)
        metrics.side_effect=lambda:(order.append('tail') or metrics.return_value)
        self.assertEqual(tail.finish(pending,observe_exit=exit,final_tail=metrics)['result'],'SOURCE_TAIL_ACCOUNTED')
        self.assertEqual(order,['exit','tail']);self.assertEqual(tail.meter.writes['control'],10)

    def test_tail_wrong_exit_identity_or_missing_metrics_never_completes(self):
        tail,pending,exit,metrics=self.tail();exit.return_value['identity']=[123,'reused']
        with self.assertRaises(ValueError):tail.finish(pending,observe_exit=exit,final_tail=metrics)
        metrics.assert_not_called()
        tail,pending,exit,metrics=self.tail(now=4601)
        with self.assertRaises(ValueError):tail.finish(pending,observe_exit=exit,final_tail=metrics)


class InjectedBoundary:
    """MODELED authority/enforcement; never an installed OS backend."""
    def __init__(self):self.calls=[]
    def authenticate_executor(self,plan):return {'W':'/fixture/W'}
    def admit_record(self,record,deadline):self.calls.append('admit')
    def verify_bound_record(self,record,exact,deadline):self.calls.append('verify')
    def execution_context(self,record,exact,deadline):
        return dict(env={'LC_ALL':'C'},cwd='/fixture/W',pass_fds=[],uid=0,gid=0,extra_groups=[])
    def complete_record(self,record,deadline):self.calls.append('complete')
    def quarantine_record_uncertainty(self,record):self.calls.append('quarantine')
    def dbus(self,args,deadline):self.calls.append(('dbus',args))
    def syscall(self,operation,args,deadline):self.calls.append(('syscall',operation))
    def docker(self,operation,args,deadline):self.calls.append(('docker',operation))


class ExecutorTests(unittest.TestCase):
    def executor(self):
        boundary=InjectedBoundary();run=Mock(return_value=types.SimpleNamespace(returncode=0))
        return e.RecordExecutor(p.source_plan(),boundary,clock=lambda:100,run=run),boundary,run

    def request(self,executor,operation,phase=None):
        record=next(x for x in executor.records if x['operation']==operation and (phase is None or x['phase']==phase))
        return dict(operation=operation,record=record['sequence'],deadline=200)

    def test_exact_fixed_argv_and_private_environment(self):
        executor,boundary,run=self.executor()
        request=self.request(executor,'umount');executor.execute(request)
        self.assertEqual(run.call_args.args[0],['/usr/bin/umount','--','/fixture/W'])
        self.assertFalse(run.call_args.kwargs['shell']);self.assertEqual(run.call_args.kwargs['env'],{'LC_ALL':'C'})
        self.assertEqual(run.call_args.kwargs['timeout'],100)
        self.assertEqual(boundary.calls,['admit','verify','complete'])

    def test_argv_injection_unknown_operation_and_record_mismatch(self):
        for bad in ({'operation':'shell','record':0,'deadline':200},
                {'operation':'mount','record':0,'deadline':200},
                {'operation':'mount','record':0,'deadline':200,'argv':['sh']}):
            executor,boundary,run=self.executor()
            with self.assertRaises(ValueError):executor.execute(bad)
            self.assertEqual(boundary.calls,[]);run.assert_not_called()

    def test_unbound_paths_and_denied_meter_never_spawn(self):
        executor,boundary,run=self.executor();executor.bindings={}
        with self.assertRaises(ValueError):executor.execute(self.request(executor,'umount'))
        run.assert_not_called();self.assertTrue(executor.failed)
        executor,boundary,run=self.executor();boundary.admit_record=Mock(side_effect=ValueError('unqualified meter'))
        with self.assertRaises(ValueError):executor.execute(self.request(executor,'umount'))
        run.assert_not_called()

    def test_command_failure_and_late_return_keep_ownership(self):
        executor,boundary,run=self.executor();run.side_effect=subprocess.TimeoutExpired('fixture',100)
        with self.assertRaises(subprocess.TimeoutExpired):executor.execute(self.request(executor,'umount'))
        self.assertTrue(executor.failed);self.assertEqual(boundary.calls[-1],'quarantine')
        with self.assertRaises(ValueError):executor.execute(self.request(executor,'mount'))

    def test_complete_command_allowlist_and_default_root_refusal(self):
        proposal=e.proposal(p.source_plan())
        self.assertEqual(set(proposal['operations']),{x['operation'] for x in proposal['command_allowlist']})
        root=c.HERE/'profile-root-helper.py'
        for flags in (['-B'],['-I','-B']):
            result=subprocess.run([sys.executable,*flags,str(root)],capture_output=True,text=True,timeout=5)
            self.assertEqual(result.returncode,3);self.assertEqual(result.stderr,'')
            self.assertEqual(json.loads(result.stdout)['result'],'REFUSED_UNQUALIFIED')
        self.assertEqual(e.QUALIFIED_ROOT,{})

    def test_actual_root_main_through_record_executor_and_sanitized_failure(self):
        import hashlib
        path=c.HERE/'profile-root-helper.py'
        spec=importlib.util.spec_from_file_location('root_source_fixture',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        executor,boundary,run=self.executor()
        boundary.authenticate_root_entry=lambda:p.source_plan()
        boundary.authenticated_installation_inputs=lambda:b''  # Isolated layout is tested separately.
        boundary.receive_authenticated_record_request=lambda:self.request(executor,'umount')
        entry=e.RootEntry(boundary,clock=lambda:100,run=run)
        fixture={hashlib.sha256(path.read_bytes()).hexdigest():entry}
        output=io.StringIO()
        with redirect_stdout(output),patch.object(e,'verify_installation'):
            status=module.main([],qualified=fixture)
        self.assertEqual(status,0);self.assertEqual(run.call_count,1)
        self.assertEqual(json.loads(output.getvalue())['result'],'HELPER_RETURNED')
        run.side_effect=subprocess.CalledProcessError(1,['sensitive-fixture-not-for-output'])
        output=io.StringIO()
        with redirect_stdout(output),patch.object(e,'verify_installation'):
            status=module.main([],qualified=fixture)
        self.assertEqual(status,3);self.assertNotIn('sensitive',output.getvalue())
        self.assertEqual(e.QUALIFIED_ROOT,{})

    def test_hard_enforcement_omission_refuses_real_entry_before_commands(self):
        boundary=InjectedBoundary();boundary.authenticate_root_entry=Mock(side_effect=ValueError('missing hard writer confinement'))
        runner=Mock();entry=e.RootEntry(boundary,clock=lambda:100,run=runner)
        with self.assertRaises(ValueError):entry.run_authenticated_inherited_entry()
        runner.assert_not_called()


if __name__=='__main__':unittest.main(verbosity=2)
