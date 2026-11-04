"""Source-only adverse cases. No original lock, resource snapshot or native child."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import stat
import struct
import subprocess
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

import profile_contract as c

spec=importlib.util.spec_from_file_location('native_driver',c.HERE/'profile-integration.py')
driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
spec=importlib.util.spec_from_file_location('profile_freezer',c.HERE/'freeze-profile.py')
freezer=importlib.util.module_from_spec(spec);spec.loader.exec_module(freezer)


class BuiltLayoutTests(unittest.TestCase):
    # Exact retained d9a6559b compiler line; ELF stand-ins are inspected, never run.
    compile_line='[ 87%] Building CXX object src/rpc/CMakeFiles/obj_rpc.dir/core_rpc_server.cpp.o'
    object_name='src/rpc/CMakeFiles/obj_rpc.dir/core_rpc_server.cpp.o'

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.out=self.root/'out';self.out.mkdir()
        (self.root/'public').mkdir();self.build=self.out/'build'
        (self.build/'bin').mkdir(parents=True)
        for name in ('monerod','monero-wallet-cli','monero-wallet-rpc'):
            path=self.build/'bin'/name;path.write_bytes(Path('/bin/true').read_bytes());path.chmod(0o700)
        self.obj=self.build/self.object_name;self.obj.parent.mkdir(parents=True)
        self.obj.write_bytes(b'disposable RPC object fixture')
        (self.out/'build.log').write_text(self.compile_line+'\n')
        (self.out/'rustc.txt').write_text('fixture rustc\n')
        (self.out/'inputs.json').write_text(json.dumps(dict(builder_rustc='fixture rustc',reference=dict(
            overlay_sha256='32c40224dcd618995ef4d846cab411a85783314da79a803ed16074241780312c'))))

    def mapped(self,name):
        path=Path(name)
        return self.root/str(path).lstrip('/') if path.is_absolute() else path

    def built(self):
        with patch.object(freezer,'Path',side_effect=self.mapped),patch.object(freezer.c,'json_file',
                side_effect=lambda name:json.loads(self.mapped(name).read_text())):
            freezer.built(self.build)

    def refused(self):
        with self.assertRaisesRegex(ValueError,'RPC object missing'):self.built()
        self.assertFalse((self.root/'public/build.json').exists())

    def test_real_cmake_layout_and_log_line(self):
        self.built();result=json.loads((self.root/'public/build.json').read_text())
        self.assertEqual(result['rpc_translation_unit'],dict(status='PASS',object_sha256=c.digest(self.obj.read_bytes())))
        self.assertEqual(set(result['three_production_binaries']['binaries']),
                         {'monerod','monero-wallet-cli','monero-wallet-rpc'})
        for value in result['three_production_binaries']['binaries'].values():
            self.assertEqual(value['sha256'],c.digest(Path('/bin/true').read_bytes()))
            self.assertIsInstance(value['needed'],list)

    def test_old_rpc_dir_only_is_refused(self):
        old=self.build/'src/rpc/CMakeFiles/rpc.dir/core_rpc_server.cpp.o'
        old.parent.mkdir(parents=True);self.obj.rename(old);self.refused()

    def test_object_without_exact_compile_line_is_refused(self):
        for line in ('','core_rpc_server.cpp.o',self.compile_line+' trailing',
                     'unrelated '+self.compile_line,self.compile_line.replace('Building','Removing'),
                     self.compile_line.replace('obj_rpc.dir','rpc.dir')):
            with self.subTest(line=line):
                (self.out/'build.log').write_text(line+'\n');self.refused()

    def test_compile_line_without_object_is_refused(self):
        self.obj.unlink();self.refused()

    def test_each_production_binary_is_required(self):
        for name in ('monerod','monero-wallet-cli','monero-wallet-rpc'):
            with self.subTest(name=name):
                path=self.build/'bin'/name;path.chmod(0o600)
                with self.assertRaisesRegex(ValueError,'missing production binary'):self.built()
                path.chmod(0o700)

    def test_freezer_failure_appends_stdout_and_stderr_to_build_log(self):
        harness=self.out/'harness';harness.mkdir()
        # Only dependency paths are redirected; execute the actual final shell call.
        (harness/'freeze-profile.py').write_text(
            'import sys\nprint("freezer stdout",flush=True)\nprint("freezer stderr",file=sys.stderr,flush=True)\nraise RuntimeError("fixture freezer failure")\n')
        command=(c.HERE/'integration/build.sh').read_text().splitlines()[-1]
        command=command.replace('/out/',str(self.out)+'/')
        result=subprocess.run(['bash','-eu','-c',command],capture_output=True,text=True,timeout=5)
        self.assertNotEqual(result.returncode,0)
        log=(self.out/'build.log').read_text()
        self.assertTrue(log.startswith(self.compile_line+'\n'))
        for witness in ('freezer stdout','freezer stderr','RuntimeError: fixture freezer failure'):
            self.assertIn(witness,log)
        self.assertEqual(result.stdout,'');self.assertEqual(result.stderr,'')


def grant():
    value=dict(schema='meownero-platform-grant/2',issue_id=c.ISSUE,candidate_commit='candidate',
        inputs_sha256='inputs',artifact_sha256='artifact',limits=c.LIMITS,attempts=1,retry=False,
        workload='three-production-binaries-genesis-only',authorized=True,not_before_unix=10,expires_unix=20,
        bootstrap_sha256='b'*64)
    comment=dict(id='new',issueId=c.ISSUE,authorAgentId=c.PLATFORM,authorType='agent')
    return comment,value


def check_grant(comment,value,now=15):
    comment=dict(comment,body='```meownero-platform-grant\n'+json.dumps(value)+'\n```')
    return c.grant_payload(comment,commit='candidate',inputs_hash='inputs',artifact_hash='artifact',bootstrap_hash='b'*64,now=now)


class SourceBoundaryTests(unittest.TestCase):
    def test_grant_requires_attributed_platform_author(self):
        comment,value=grant();check_grant(comment,value)
        for key,bad in [('authorAgentId','different'),('authorType','user'),('issueId','other')]:
            with self.subTest(key=key):
                with self.assertRaises(ValueError):check_grant(dict(comment,**{key:bad}),value)
    def test_consumed_and_expired_grants(self):
        comment,value=grant()
        for consumed in c.CONSUMED:
            with self.assertRaises(ValueError):check_grant(dict(comment,id=consumed),value)
        for now in [9,20,21]:
            with self.assertRaises(ValueError):check_grant(comment,value,now)
    def test_grant_binds_every_workload_input(self):
        comment,value=grant()
        for key,bad in [('candidate_commit','other'),('inputs_sha256','other'),('artifact_sha256','other'),
                        ('authorized',False),('retry',True),('attempts',2),('limits',dict(c.LIMITS,wall_seconds=4501))]:
            with self.subTest(key=key):
                with self.assertRaises(ValueError):check_grant(comment,dict(value,**{key:bad}))
    def test_uuid_alone_is_not_a_grant(self):
        comment,value=grant();comment['body']='approved '+comment['id']
        with self.assertRaises(ValueError):c.grant_payload(comment,commit='candidate',inputs_hash='inputs',artifact_hash='artifact',bootstrap_hash='b'*64,now=15)
    def test_original_lock_replacements_are_refused(self):
        info=SimpleNamespace(st_mode=stat.S_IFREG|0o600,st_dev=c.LOCK_ID[0],st_ino=c.LOCK_ID[1],st_uid=os.getuid())
        c.check_lock(info,os.getuid())
        for field,value in [('st_ino',info.st_ino+1),('st_dev',info.st_dev+1),('st_uid',info.st_uid+1),('st_mode',stat.S_IFREG|0o644)]:
            with self.assertRaises(ValueError):c.check_lock(SimpleNamespace(**{**vars(info),field:value}),os.getuid())
    def test_admission_floor_load_collision(self):
        valid=dict(available_memory_bytes=5*1024**3,free_disk_bytes=20*1024**3,
                   load=[6.,6.,6.],native_processes=[],native_containers=[])
        c.admit(valid)
        for key,bad in [('available_memory_bytes',5*1024**3-1),('free_disk_bytes',20*1024**3-1),
                        ('load',[6.01,0.,0.]),('load',[0.,6.01,0.]),('load',[0.,0.,6.01]),
                        ('load',[float('nan'),0,0]),('native_processes',[1]),('native_containers',['cid'])]:
            with self.subTest(key=key,bad=bad):
                with self.assertRaises(ValueError):c.admit(dict(valid,**{key:bad}))
    def test_container_only_containment_never_satisfies_aggregate(self):
        counters={'cpu.max':'200000 100000','memory.max':str(4*1024**3),'memory.swap.max':'0',
                  'memory.oom.group':'0','pids.max':'256','cgroup.procs':''}
        c.enclosure(counters,'/owned/controller','/owned/docker','/owned')
        for self_group,daemon in [('/other/controller','/owned/docker'),('/owned/controller','/system/docker')]:
            with self.assertRaises(ValueError):c.enclosure(counters,self_group,daemon,'/owned')
        for key,bad in [('memory.max','max'),('memory.swap.max','max'),('cpu.max','max 100000'),('pids.max','max'),('cgroup.procs','123')]:
            with self.assertRaises(ValueError):c.enclosure(dict(counters,**{key:bad}),'/owned/controller','/owned/docker','/owned')
    def root(self,base):
        root=base/'owned';root.mkdir(mode=0o700);(root/'wallet').write_bytes(b'disposable empty fixture')
        os.chmod(root/'wallet',0o600)
        manifest=dict(profile='profile',overlay='overlay',binaries={'wallet':'binary'},stopped_saved=True,
                      saved_files={'wallet':c.digest((root/'wallet').read_bytes())})
        (root/'creation.json').write_bytes(c.canonical(manifest));os.chmod(root/'creation.json',0o600)
        return root,manifest
    def test_saved_bundle_tampering_refused_without_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            root,manifest=self.root(Path(temp));c.root_manifest(root,manifest)
            for corruption in ['file','profile','missing','unexpected']:
                with self.subTest(corruption=corruption):
                    if corruption=='file':(root/'wallet').write_bytes(b'corrupt')
                    if corruption=='profile':(root/'creation.json').write_text('{}')
                    if corruption=='missing':(root/'creation.json').unlink()
                    if corruption=='unexpected':(root/'unexpected').write_text('not in saved bundle')
                    before={p.name:p.read_bytes() for p in root.iterdir() if p.is_file()}
                    with self.assertRaises((ValueError,OSError)):c.root_manifest(root,manifest)
                    self.assertEqual(before,{p.name:p.read_bytes() for p in root.iterdir() if p.is_file()})
                    (root/'wallet').write_bytes(b'disposable empty fixture')
                    (root/'creation.json').write_bytes(c.canonical(manifest));os.chmod(root/'creation.json',0o600)
    def test_alias_hardlink_and_wrong_owner_are_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);root,manifest=self.root(base)
            alias=base/'alias';alias.symlink_to(root)
            with self.assertRaises(ValueError):c.root_manifest(alias,manifest)
            os.link(root/'wallet',root/'alias')
            with self.assertRaises(ValueError):c.root_manifest(root,manifest)
            (root/'alias').unlink()
            with self.assertRaises(ValueError):c.check_file(root/'wallet',uid=os.getuid()+1)
    def test_read_only_login_mode_and_alias_refusal(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'login';path.write_bytes(b'private-fixture');os.chmod(path,0o400)
            self.assertEqual(c.check_file(path,modes=(0o400,0o600)),b'private-fixture')
            os.chmod(path,0o644)
            with self.assertRaises(ValueError):c.check_file(path,modes=(0o400,0o600))
    def test_pid_reuse_never_receives_a_signal(self):
        proc=Mock();proc.pid=123;proc.poll.return_value=None
        with patch.dict(driver.PROCS,{'fixture':(proc,[123,'old'])},clear=True),patch.object(driver,'identity',return_value=[123,'new']):
            with self.assertRaises(ValueError):driver.stop('fixture')
            proc.send_signal.assert_not_called();proc.kill.assert_not_called()
    def test_forced_kill_cannot_pass_save_or_handoff(self):
        proc=Mock();proc.pid=123;proc.poll.return_value=None
        proc.wait.side_effect=[subprocess.TimeoutExpired('fixture',20),0]
        with patch.dict(driver.PROCS,{'fixture':(proc,[123,'same'])},clear=True),patch.object(driver,'identity',return_value=[123,'same']),patch.object(driver,'budget',return_value=1):
            with self.assertRaises(ValueError):driver.stop('fixture')
            proc.kill.assert_called_once()
    def test_partial_rows_never_get_slice_pass(self):
        rows=c.empty_rows();self.assertEqual(c.verdict(rows),'INCOMPLETE')
        for name,keys in c.REQUIRED.items():
            for key in keys:rows[name][key]={'status':'PASS'}
        self.assertTrue(c.verdict(rows).startswith('PASS_'))
        for name,keys in c.REQUIRED.items():
            for key in keys:
                rows[name][key]={'status':'NOT_RUN'};self.assertEqual(c.verdict(rows),'INCOMPLETE')
                rows[name][key]={'status':'FAIL'};self.assertEqual(c.verdict(rows),'FAIL')
                rows[name][key]={'status':'PASS'}
    def test_exact_portable_chain_fixture(self):
        # Decode with an independent narrow schema reader, including the real header.
        good=c.chain_request(c.GENESIS);bad=c.chain_request('00'*32)
        self.assertEqual(c.HEADER.unpack(good[:33]),(c.SIGNATURE,len(good)-33,0,2006,0,1,1))
        payload=good[33:];self.assertEqual(payload[:9],bytes.fromhex('011101010101020101'))
        self.assertEqual(payload[9:22],b'\x08\x09block_ids\x0a\x80')
        self.assertEqual(payload[22:54],bytes.fromhex(c.GENESIS))
        self.assertEqual(payload[54:],b'\x05prune\x0b\x00')
        self.assertEqual(good[:55],bad[:55]);self.assertEqual(good[87:],bad[87:])
        self.assertNotEqual(good,bad)
    def test_uuid_mutation_changes_only_16_byte_native_field(self):
        payload=b'\x0anetwork_id\x0a\x40'+c.UUID
        head=c.HEADER.pack(c.SIGNATURE,len(payload),1,1001,0,1,1);raw=head+payload
        mutated=c.mutate_uuid(raw)
        self.assertEqual(len(raw),len(mutated));self.assertEqual(sum(a!=b for a,b in zip(raw,mutated)),1)
        with self.assertRaises(ValueError):c.mutate_uuid(head+b'no native UUID')
    def test_ungranted_direct_runner_refuses_before_any_resource_operation(self):
        spec=importlib.util.spec_from_file_location('profile_runner_test',c.HERE/'run-profile.py')
        runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
        with patch.object(runner.subprocess,'check_output',side_effect=['candidate\n','']), \
             patch.object(runner,'check_inputs',return_value={'platform_bootstrap_sha256':None}), \
             patch.object(runner,'api') as api,patch.object(runner.os,'open') as opened, \
             patch.object(runner,'controller_create') as admission,patch.object(runner.sys,'argv',
                 ['run-profile.py','--grant-comment','11111111-1111-4111-8111-111111111111','--artifact-sha256','pending',
                  '--out','/tmp/not-an-authorized-native-attempt']):
            with self.assertRaisesRegex(ValueError,'new exact grant'):runner.main()
            api.assert_not_called();opened.assert_not_called();admission.assert_not_called()
    def test_network_census_rejects_wildcard_or_external_sockets(self):
        good='header\n0: 0100007F:BB21 00000000:0000 0A\n'
        self.assertEqual(c.loopback_census([(False,good)]),1)
        for bad in [good.replace('0100007F','00000000'),good.replace('00000000:0000','08080808:0035')]:
            with self.assertRaises(ValueError):c.loopback_census([(False,bad)])
    def test_no_raw_native_output_has_been_claimed(self):
        inputs=c.json_file(c.HERE/'integration/inputs.json')
        self.assertEqual(inputs['proposed_native_outputs'],c.empty_rows())
        self.assertTrue(all(v=='NOT_RUN' for v in inputs['exclusions'].values()))
        self.assertIsNone(inputs['platform_bootstrap_sha256'])


if __name__=='__main__':unittest.main()
