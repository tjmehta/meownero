#!/usr/bin/env python3
"""Direct controller tests. Docker/native execution is replaced; host children are real."""
import ast
import contextlib
import copy
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import profile_contract as c

spec = importlib.util.spec_from_file_location('direct_profile',c.HERE/'run-profile.py')
r = importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
GRANT = '11111111-1111-4111-8111-111111111111'
IMAGE = 'sha256:'+'e'*64


def grant(output):
    return dict(schema='meownero-direct-profile-grant/1',authorized=True,
        candidate_commit='a'*40,inputs_sha256=c.digest(b'{}'),artifact_sha256=c.digest(b'packet'),
        runner_sha256=c.digest((c.HERE/'run-profile.py').read_bytes()),output_root=str(output),
        artifact_attachment_id='22222222-2222-4222-8222-222222222222',attempts=1,retry=False,
        wall_seconds=4500,build_seconds=3600,runtime_seconds=600,cleanup_seconds=300,
        container_flags=r.CONTAINER_FLAGS,workload='three-production-binaries-genesis-only',
        non_genesis_blocks=0,transactions=0,valid_from_unix=0,valid_until_unix=time.time()+10000,
        load_rule=dict(metric='host-load-1-5-15',maximum=[6,6,6]),
        host_overhead_allowance=dict(mode='measured-controller-and-descendants-not-kernel-enforced',
            peak_rss_bytes=2*r.GiB,cpu_seconds=600,peak_pids=32))


def comment(value):
    return dict(id=GRANT,issueId=c.ISSUE,authorAgentId=c.PLATFORM,authorUserId=None,
        body='```meownero-direct-profile-grant\n'+json.dumps(value)+'\n```')


class Direct(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name);self.output = self.base/'attempt'
        self.lock = self.base/'heavy.lock';self.lock.touch(mode=0o600)
        info = self.lock.stat()
        self.stack = contextlib.ExitStack();self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(r.g,'LOCK',self.lock))
        self.stack.enter_context(patch.object(r.g,'LOCK_ID',(info.st_dev,info.st_ino)))

    def validate(self,value):
        return r.grant_payload(comment(value),commit='a'*40,inputs_hash=c.digest(b'{}'),
            artifact_hash=c.digest(b'packet'),runner_hash=c.digest((c.HERE/'run-profile.py').read_bytes()),
            output=self.output,now=time.time())

    def test_exact_direct_grant_rejects_legacy_and_each_wrong_binding(self):
        value = grant(self.output);self.validate(value)
        for key,bad in [('schema','meownero-platform-grant/2'),('candidate_commit','b'*40),
            ('inputs_sha256','b'*64),('runner_sha256','b'*64),('artifact_sha256','b'*64),
            ('output_root',str(self.base/'other')),('attempts',2),('retry',True),
            ('wall_seconds',4600),('container_flags',[]),('transactions',1)]:
            with self.subTest(key=key),self.assertRaises(ValueError):self.validate(dict(value,**{key:bad}))
        for key in ('host_overhead_allowance','load_rule'):
            with self.assertRaises(KeyError):self.validate({k:v for k,v in value.items() if k != key})

    def test_lock_nonblocking_preserves_inode_and_releases_on_close(self):
        fd,receipt = r.acquire_lock()
        try:
            with self.assertRaises(BlockingIOError):r.acquire_lock()
            self.assertEqual(self.lock.stat().st_ino,receipt['inode'])
        finally:os.close(fd)
        fd,_ = r.acquire_lock();os.close(fd)

    def test_absent_lock_created_0600_and_wrong_existing_never_replaced(self):
        self.lock.unlink();fd,receipt = r.acquire_lock();os.close(fd)
        self.assertTrue(receipt['created']);self.assertEqual(self.lock.stat().st_mode & 0o777,0o600)
        self.lock.chmod(0o644);before = self.lock.stat()
        with self.assertRaisesRegex(ValueError,'metadata'):r.acquire_lock()
        self.assertEqual(self.lock.stat().st_ino,before.st_ino)

    def test_admission_checks_both_floors_collisions_and_explicit_load_rule(self):
        observation = dict(available_memory_bytes=5*r.GiB,native_processes=[],native_containers=[])
        with patch.object(r.g,'admission',return_value=observation), \
             patch.object(r.shutil,'disk_usage',return_value=type('Disk',(),{'free':20*r.GiB})()), \
             patch.object(r.os,'getloadavg',return_value=(6,6,6)):
            r.admit(IMAGE,self.base,grant(self.output))
            for key,bad in [('available_memory_bytes',5*r.GiB-1),('native_processes',[1]),('native_containers',[1])]:
                with patch.dict(observation,{key:bad}),self.assertRaises(ValueError):
                    r.admit(IMAGE,self.base,grant(self.output))
            with patch.object(r.shutil,'disk_usage',return_value=type('Disk',(),{'free':20*r.GiB-1})()), \
                 self.assertRaises(ValueError):r.admit(IMAGE,self.base,grant(self.output))
            with patch.object(r.os,'getloadavg',return_value=(6.01,0,0)),self.assertRaises(ValueError):
                r.admit(IMAGE,self.base,grant(self.output))

    def test_actual_child_deadline_kills_owned_group_and_preserves_unrelated_child(self):
        self.output.mkdir();controller = r.Controller(self.output,grant(self.output),time.monotonic())
        unrelated = subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])
        try:
            with self.assertRaisesRegex(ValueError,'deadline'):
                controller.run([sys.executable,'-c','import time; time.sleep(30)'],time.monotonic()+.2,monitor=False)
            self.assertIsNone(unrelated.poll())
            self.assertTrue(all(p.poll() is not None for p,_,_ in controller.children))
        finally:unrelated.terminate();unrelated.wait(timeout=5)

    def test_resource_sampling_records_owned_directory_and_measured_overhead(self):
        self.output.mkdir();(self.output/'data').write_bytes(b'x'*4096)
        controller = r.Controller(self.output,grant(self.output),time.monotonic())
        controller.sample(force=True)
        self.assertGreaterEqual(controller.peak['disk_bytes'],4096)
        self.assertGreater(controller.peak['peak_rss_bytes'],0)
        self.assertEqual(controller.samples,1)
        with patch.object(r.shutil,'disk_usage',return_value=type('Disk',(),{'free':4*r.GiB-1})()), \
             self.assertRaisesRegex(ValueError,'free disk'):controller.sample(force=True)

    def test_staging_high_water_abort_is_measured_without_claiming_a_quota(self):
        self.output.mkdir();controller = r.Controller(self.output,grant(self.output),time.monotonic())
        with patch.object(controller,'run',return_value=subprocess.CompletedProcess([],0,str(15*r.GiB+1).encode()+b' path',b'')), \
             self.assertRaisesRegex(ValueError,'15 GiB'):controller.sample(force=True)
        self.assertGreater(controller.peak['disk_bytes'],15*r.GiB)

    def test_expired_positive_command_budget_never_spawns(self):
        controller = r.Controller(self.base,grant(self.output),time.monotonic())
        with patch.object(r.subprocess,'Popen') as spawn,self.assertRaises(ValueError):
            controller.run(['unused'],time.monotonic()-1)
        spawn.assert_not_called()

    def test_entry_has_no_retired_facility_imports(self):
        tree = ast.parse((c.HERE/'run-profile.py').read_text())
        imports = [node.module for node in ast.walk(tree) if isinstance(node,ast.ImportFrom)]
        imports += [name.name for node in ast.walk(tree) if isinstance(node,ast.Import) for name in node.names]
        self.assertFalse(any(any(part in name for part in ('manager','outer','bootstrap','constructor','ingress','helper','handoff','dispatch'))
                             for name in imports if name))

    def test_actual_staging_prefix_reaches_frozen_driver_missing_binary_sentinel(self):
        class BeforeSourceRead(Exception): pass
        self.output.mkdir()
        control = type('Control',(),{'root':self.output})()
        with patch.object(c,'json_file',side_effect=BeforeSourceRead),self.assertRaises(BeforeSourceRead):
            r.stage_inputs(control,Path('unused'),{})
        private = self.output/'staging/private'
        self.assertFalse(private.exists())
        spec = importlib.util.spec_from_file_location('frozen_driver',c.HERE/'profile-integration.py')
        driver = importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
        driver.PRIVATE = private;driver.BIN = self.base/'missing-binaries'
        old_umask = os.umask(0o077)
        try:
            with patch.object(driver.subprocess,'Popen') as spawn,self.assertRaises(FileNotFoundError) as error:
                driver.main()
            self.assertEqual(Path(error.exception.filename),driver.BIN/'monerod')
            self.assertTrue(private.is_dir());self.assertEqual(private.stat().st_mode & 0o777,0o700)
            spawn.assert_not_called();self.assertFalse(driver.PROCS)
        finally:os.umask(old_umask)

    def exercise(self, *, refuse=None, uncertain_create=False, fail_runtime=False,
                 failed_phase=None, raised_phase=None, mutate_public=None, container_exit_only=False,
                 mutate_build=None):
        inputs = self.base/'inputs.json';inputs.write_bytes(b'{}')
        value = grant(self.output);events = [];state = {'container':None,'starts':0}
        case = self
        class FakeController(r.Controller):
            def sample(self,force=False):self.samples += 1
            def run(self,argv,deadline,**kwargs):
                case.assertGreater(deadline,time.monotonic())
                case.assertEqual(argv[:len(r.g.DOCKER)],r.g.DOCKER)
                cmd = argv[len(r.g.DOCKER):];events.append(cmd[0])
                output = b'';code = 0;error = b''
                if cmd[:2] == ['image','inspect']:output = json.dumps([{'Id':IMAGE}]).encode()
                elif cmd[0] == 'create':
                    case.assertEqual(cmd.count('--name'),1)
                    h = dict(NetworkMode='none',NanoCpus=2_000_000_000,Memory=4*r.GiB,
                        MemorySwap=4*r.GiB,PidsLimit=256,CapDrop=['ALL'],SecurityOpt=['no-new-privileges'],
                        Privileged=False,PortBindings={},Ulimits=[dict(Name='core',Soft=0,Hard=0)])
                    state['container'] = dict(Id='c'*64,Name='/meownero-profile-'+GRANT,Image=IMAGE,
                        Config=dict(Labels={'meownero.profile.attempt':'meownero-profile-'+GRANT},User=f'{os.getuid()}:{os.getgid()}'),
                        Mounts=[dict(Source=str(case.output/'staging'),Destination='/out')],
                        HostConfig=h,State=dict(Running=False,ExitCode=0,OOMKilled=False))
                    if uncertain_create:raise TimeoutError('create response lost')
                elif cmd[0] == 'inspect':
                    if state['container']:output = json.dumps([state['container']]).encode()
                    else:code,error = 1,b'Error: No such object'
                elif cmd[0] == 'start':
                    state['starts'] += 1
                    if state['starts'] == 2 and fail_runtime:
                        state['container']['State']['Running'] = True
                        raise RuntimeError('runtime failed')
                    phase = 'build' if state['starts'] == 1 else 'runtime'
                    (case.output/'staging'/('resources-'+phase+'.json')).write_text(json.dumps(dict(oom=0,oom_kill=0)))
                    for filename,keys in c.REQUIRED.items():
                        produced = ('build.json',) if phase == 'build' else set(c.REQUIRED)-{'build.json','cleanup.json','resources.json'}
                        if filename in produced:
                            (case.output/'public'/filename).write_text(json.dumps(case.producer_rows()[filename]))
                    if phase == 'build' and mutate_build:mutate_build(case.output/'public/build.json')
                    if phase in (failed_phase,raised_phase):
                        secret = 'PRIVATE_WALLET_RPC_LOGIN_FRAME_ENV_STDOUT_STDERR_SENTINEL'
                        for name in ('build.log','configure.log','private/console.log'):
                            (case.output/'staging'/name).write_text(secret)
                        if phase == 'runtime':
                            (case.output/'public/peer.json').write_text(json.dumps(dict(
                                native_handshake=dict(status='PASS',request_sha256='a'*64,command=1001))))
                        state['container']['State']['ExitCode'] = 17
                        if phase == raised_phase:
                            raise subprocess.CalledProcessError(17,argv,output=secret.encode(),stderr=secret.encode())
                        code = 0 if container_exit_only else 17
                        output = error = secret.encode()
                    if phase == 'runtime' and mutate_public:mutate_public(case.output)
                elif cmd[0] == 'stop':state['container']['State']['Running'] = False
                elif cmd[0] == 'rm':state['container'] = None
                else:raise AssertionError(cmd)
                return subprocess.CompletedProcess(argv,code,output,error)
        def admission(image,root,grant):
            events.append('admit')
            count = events.count('admit')
            if count == refuse:raise ValueError('real admission refusal')
            case.assertFalse((case.output/'staging').exists() if count == 1 else False)
            fd = os.open(case.lock,os.O_RDWR)
            try:
                with case.assertRaises(BlockingIOError):fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            finally:os.close(fd)
            return dict(available_memory_bytes=5*r.GiB,free_disk_bytes=20*r.GiB)
        def stage(control,inputs,manifest):
            events.append('stage');(case.output/'staging').mkdir();(case.output/'staging/private').mkdir()
            (case.output/'staging/private/secret').write_text('never export')
        def api(path):return json.dumps(comment(value)).encode() if '/comments/' in path else b'packet'
        with patch.object(r,'Controller',FakeController),patch.object(r,'stage_inputs',stage), \
             patch.object(r,'admit',admission),patch.object(r,'api',api), \
             patch.object(r,'check_inputs',return_value={'builder_image':IMAGE}), \
             patch.object(r.subprocess,'check_output',side_effect=['a'*40+'\n','']), \
             patch.object(sys,'argv',['run-profile.py','--inputs',str(inputs),'--grant-comment',GRANT,
                 '--artifact-sha256',c.digest(b'packet'),'--out',str(self.output)]):
            result = r.main()
        self.assertIsNone(state['container'])
        self.assertFalse((self.output/'staging').exists())
        fd,_ = r.acquire_lock();os.close(fd)
        receipt = json.loads((self.output/'public/receipt.json').read_text()) if self.output.exists() else None
        if receipt:
            self.assertEqual(receipt['rows']['cleanup.json']['lock_released']['status'],'PASS')
            self.assertNotIn('never export',json.dumps(receipt))
            for path in self.output.rglob('*'):
                if path.is_file():self.assertNotIn('PRIVATE_WALLET_RPC_LOGIN_FRAME_ENV_STDOUT_STDERR_SENTINEL',path.read_text())
        return result,receipt,events

    def test_two_admissions_one_container_same_container_restart_and_cleanup(self):
        result,receipt,events = self.exercise()
        self.assertEqual(result,0)
        self.assertEqual(events[:5],['admit','stage','image','admit','create'])
        self.assertEqual(events.count('create'),1);self.assertEqual(events.count('start'),2)
        self.assertTrue(receipt['result'].startswith('PASS_'));self.assertFalse(receipt['launch_ready'])
        self.assertTrue(all(x == 'NOT_RUN' for x in receipt['exclusions'].values()))
        self.assertTrue((self.output/'consumed.json').is_file())
        with patch.object(sys,'argv',['run-profile.py','--grant-comment',GRANT,'--artifact-sha256',
            c.digest(b'packet'),'--out',str(self.output)]),patch.object(r,'api') as api, \
             self.assertRaisesRegex(ValueError,'fresh absolute'):r.main()
        api.assert_not_called()

    def test_first_admission_refuses_before_staging_and_releases_lock(self):
        result,receipt,events = self.exercise(refuse=1)
        self.assertEqual(result,1);self.assertIsNone(receipt);self.assertEqual(events,['admit'])

    def test_writable_parent_refuses_before_staging_and_releases_lock(self):
        self.base.chmod(0o770)
        result,receipt,events = self.exercise()
        self.assertEqual(result,1);self.assertIsNone(receipt);self.assertEqual(events,['admit'])

    def test_second_admission_refuses_and_cleans_staging_without_create(self):
        result,receipt,events = self.exercise(refuse=2)
        self.assertEqual(result,1);self.assertNotIn('create',events)
        self.assertEqual(receipt['rows']['cleanup.json']['owned_staging_removed']['status'],'PASS')

    def test_ambiguous_create_is_recovered_by_exact_name_label_mount_and_removed(self):
        result,receipt,events = self.exercise(uncertain_create=True)
        self.assertEqual(result,1);self.assertIn('rm',events);self.assertNotIn('start',events)
        self.assertEqual(receipt['rows']['cleanup.json']['owned_cid_absent']['status'],'PASS')

    def test_runtime_failure_removes_owned_container_and_private_staging(self):
        result,receipt,events = self.exercise(fail_runtime=True)
        self.assertEqual(result,1);self.assertEqual(events.count('create'),1)
        self.assertLess(events.index('stop'),events.index('rm'))
        self.assertEqual(receipt['rows']['cleanup.json']['owned_cid_absent']['status'],'PASS')

    def test_failed_build_retains_partial_rows_and_sanitized_exit_before_cleanup(self):
        result,receipt,events = self.exercise(failed_phase='build')
        self.assertEqual(result,1);self.assertEqual(receipt['result'],'FAIL')
        self.assertEqual(receipt['failure_phase'],'build');self.assertEqual(events.count('start'),1)
        self.assertEqual(receipt['phase_diagnostics'],dict(build=dict(started=True,cli_exit_code=17,
            container_exit_code=17,oom_killed=False)))
        self.assertEqual(receipt['rows']['build.json']['three_production_binaries']['status'],'PASS')
        self.assertEqual(receipt['rows']['peer.json']['native_handshake']['status'],'NOT_RUN')

    def test_partial_runtime_failure_retains_observed_witnesses_and_unreached_rows(self):
        result,receipt,events = self.exercise(failed_phase='runtime',container_exit_only=True)
        self.assertEqual(result,1);self.assertEqual(receipt['result'],'FAIL')
        self.assertEqual(receipt['failure_phase'],'runtime');self.assertEqual(events.count('start'),2)
        self.assertEqual(receipt['phase_diagnostics']['runtime'],dict(started=True,cli_exit_code=0,
            container_exit_code=17,oom_killed=False))
        self.assertEqual(receipt['rows']['build.json']['rpc_translation_unit']['status'],'PASS')
        peer = receipt['rows']['peer.json']
        self.assertEqual(peer['native_handshake'],dict(status='PASS',request_sha256='a'*64,command=1001))
        self.assertEqual(peer['genesis_state']['status'],'NOT_RUN')
        self.assertEqual(json.loads((self.output/'public/peer.json').read_text()),peer)

    def test_raised_command_failure_keeps_exit_code_without_exception_transcripts(self):
        result,receipt,_ = self.exercise(raised_phase='runtime')
        self.assertEqual(result,1);self.assertEqual(receipt['failure_class'],'CalledProcessError')
        self.assertEqual(receipt['phase_diagnostics']['runtime']['cli_exit_code'],17)
        self.assertEqual(receipt['rows']['peer.json']['native_handshake']['status'],'PASS')

    def test_incomplete_build_evidence_prevents_runtime_start(self):
        result,receipt,events = self.exercise(mutate_build=lambda path:path.write_text('{}'))
        self.assertEqual(result,1);self.assertEqual(receipt['failure_phase'],'build')
        self.assertEqual(events.count('start'),1);self.assertEqual(receipt['result'],'FAIL')
        self.assertEqual(receipt['rows']['build.json'],c.empty_rows()['build.json'])

    def test_failed_runtime_rejects_malformed_oversized_symlink_and_unallowlisted_evidence(self):
        secret = 'PRIVATE_WALLET_RPC_LOGIN_FRAME_ENV_STDOUT_STDERR_SENTINEL'
        outside = self.base/'private-transcript';outside.write_text(secret)
        def mutate(root):
            public = root/'public'
            (public/'build.json').write_text('{')
            (public/'wallet.json').write_text(json.dumps(dict(persisted_height_zero=dict(status='PASS',login=secret))))
            (public/'auth.json').write_text(' '*65537)
            (public/'isolation.json').unlink();(public/'isolation.json').symlink_to(outside)
            (public/'reopen.json').write_text(json.dumps({secret:dict(status='PASS')}))
            (public/(secret+'.log')).write_text(secret)
            (public/'cleanup.json').write_text(json.dumps(dict(lock_released=dict(status='PASS',raw=secret))))
            (public/'resources.json').write_text(secret)
            (root/'staging/resources-runtime.json').write_text(json.dumps(dict(oom=0,oom_kill=0,raw=secret)))
        result,receipt,_ = self.exercise(failed_phase='runtime',mutate_public=mutate)
        self.assertEqual(result,1);self.assertEqual(receipt['result'],'FAIL')
        self.assertEqual(receipt['rejected_evidence'],['auth.json','build.json','isolation.json','reopen.json',
            'unexpected-public-entry','wallet.json','resources-runtime.json'])
        self.assertEqual(receipt['rows']['peer.json']['native_handshake']['status'],'PASS')
        self.assertEqual(receipt['rows']['build.json']['three_production_binaries']['status'],'PASS')
        self.assertEqual(receipt['rows']['cleanup.json']['lock_released'],dict(status='PASS',descriptor_closed=True))
        self.assertNotIn('runtime',receipt['container_counters'])
        self.assertEqual(outside.read_text(),secret)
        self.assertEqual(set(p.name for p in (self.output/'public').iterdir()),set(c.REQUIRED)|{'receipt.json'})

    def test_bounded_reader_rejects_special_hardlinked_and_duplicate_key_files(self):
        path = self.base/'evidence.json'
        os.mkfifo(path)
        with self.assertRaises(ValueError):r.bounded_json(path)
        path.unlink();path.write_text('{}');os.link(path,self.base/'alias')
        with self.assertRaises(ValueError):r.bounded_json(path)
        (self.base/'alias').unlink();path.write_text('{"status":"PASS","status":"FAIL"}')
        with self.assertRaises(ValueError):r.bounded_json(path)

    def producer_rows(self):
        # Evaluate only the producer's row(...) expressions, with public fixture
        # inputs. No RPC, sockets, wallets, frames or native children are run.
        spec = importlib.util.spec_from_file_location('witness_driver',c.HERE/'profile-integration.py')
        driver = importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
        state = dict(height=1,top_block_hash=c.GENESIS,work='0x1',pool_hashes=[])
        scope = dict(row=driver.row,c=c,packet=b'public-fixture',wrong=b'wrong-uuid',fixture='b'*64,
            before=state,state=state,a=None,snapshot=lambda unused:state)
        tree = ast.parse((c.HERE/'profile-integration.py').read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id == 'row':
                keys = c.REQUIRED['wallet.json'] if isinstance(node.args[1],ast.Name) else [None]
                for key in keys:
                    eval(compile(ast.Expression(node),'<frozen public row>','eval'),dict(scope,key=key))
        driver.ROWS['build.json'] = dict(three_production_binaries=dict(status='PASS',binaries={name:dict(sha256='a'*64,
            needed=['libc.so.6','libstdc++.so.6','libwallet-crypto.so']) for name in
            ('monerod','monero-wallet-cli','monero-wallet-rpc')}),
            rpc_translation_unit=dict(status='PASS',object_sha256='b'*64))
        return {filename:values for filename,values in driver.ROWS.items()
            if filename not in ('resources.json','cleanup.json')}

    def test_allowlist_accepts_actual_frozen_driver_row_expressions(self):
        public = self.base/'public';public.mkdir()
        rows = c.empty_rows()
        for filename,values in self.producer_rows().items():
            self.assertTrue(all(row['status'] == 'PASS' for row in values.values()))
            (public/filename).write_text(json.dumps(values))
        self.assertEqual(r.collect_public(self.base,rows),[])
        for filename,values in self.producer_rows().items():self.assertEqual(rows[filename],values)

    def test_pass_rows_require_every_producer_field_recursively(self):
        def paths(value,prefix=()):
            for key,item in value.items():
                if key == 'status':continue
                yield prefix+(key,)
                if isinstance(item,dict):yield from paths(item,prefix+(key,))
        for filename,values in self.producer_rows().items():
            path = self.base/filename
            for key,row in values.items():
                path.write_text(json.dumps({key:dict(status='PASS')}))
                with self.subTest(filename=filename,row=key,missing='all'),self.assertRaises(ValueError):
                    r.read_public_rows(path,r.public_shapes())
                for field in paths(row):
                    with self.subTest(filename=filename,row=key,missing=field):
                        incomplete = copy.deepcopy(row);parent = incomplete
                        for part in field[:-1]:parent = parent[part]
                        del parent[field[-1]]
                        path.write_text(json.dumps({key:incomplete}))
                        with self.assertRaises(ValueError):r.read_public_rows(path,r.public_shapes())

    def test_partial_failure_and_unreached_rows_allow_only_valid_known_fields(self):
        path = self.base/'build.json'
        for status in ('FAIL','NOT_RUN'):
            for witness in ({},dict(binaries={'monerod':dict(sha256='a'*64)})):
                value = dict(three_production_binaries=dict(status=status,**witness))
                path.write_text(json.dumps(value))
                self.assertEqual(r.read_public_rows(path,r.public_shapes()),value)
            for witness in (dict(binaries={'monerod':dict(unknown=True)}),
                            dict(binaries={'monerod':dict(sha256='invalid')})):
                path.write_text(json.dumps(dict(three_production_binaries=dict(status=status,**witness))))
                with self.assertRaises(ValueError):r.read_public_rows(path,r.public_shapes())

    def test_missing_wallet_rpc_binary_hash_prevents_runtime_start(self):
        def mutate(path):
            value = json.loads(path.read_text())
            del value['three_production_binaries']['binaries']['monero-wallet-rpc']['sha256']
            path.write_text(json.dumps(value))
        result,receipt,events = self.exercise(mutate_build=mutate)
        self.assertEqual(result,1);self.assertEqual(events.count('start'),1)
        self.assertEqual(receipt['failure_phase'],'build');self.assertEqual(receipt['result'],'FAIL')
        self.assertEqual(receipt['rejected_evidence'],['build.json'])

    def test_missing_native_witness_cannot_produce_slice_pass(self):
        def mutate(root):
            path = root/'public/peer.json';value = json.loads(path.read_text())
            del value['native_handshake']['request_sha256']
            path.write_text(json.dumps(value))
        result,receipt,events = self.exercise(mutate_public=mutate)
        self.assertEqual(result,1);self.assertEqual(events.count('start'),2)
        self.assertEqual(receipt['result'],'FAIL');self.assertEqual(receipt['rejected_evidence'],['peer.json'])
        self.assertEqual(receipt['rows']['peer.json'],c.empty_rows()['peer.json'])
        self.assertEqual(receipt['rows']['wallet.json']['address_roundtrip']['status'],'PASS')


if __name__ == '__main__':unittest.main()
