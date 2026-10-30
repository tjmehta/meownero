"""Declared-layout regression; all effects are injected and native work NOT_RUN."""
import json
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import profile_contract as c


# This runs under -I in disposable cwd. Its only non-stdlib path is staged.
PROBE=r'''
import importlib.util,io,json,sys
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock,patch
root=Path(sys.argv[1]);action=sys.argv[2]
sys.path.insert(0,str(root))
import profile_executor as e,profile_packet as p,profile_contract as c
def load(path):
    spec=importlib.util.spec_from_file_location('fixture_'+path.stem.replace('-','_'),path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module
if action=='imports':
    inventory=json.loads((root/'installation-inventory.json').read_bytes())
    for name in inventory['entry_points']['root_helper']:load(root/name)
    child=root/'runtime/vanguard/network'
    # A second interpreter proves child imports independently of root modules.
    import subprocess
    code="import importlib.util,sys;from pathlib import Path;root=Path(sys.argv[1]);sys.path.insert(0,str(root));"+\
        "names="+repr(inventory['entry_points']['child_runtime'])+";"+\
        "[(lambda s: s.loader.exec_module(importlib.util.module_from_spec(s)))(importlib.util.spec_from_file_location('entry'+str(i),root/Path(n).name)) for i,n in enumerate(names)];"+\
        "import network;assert network.HERE==root;network.profile();print('CHILD_IMPORTS_AND_DATA_OK')"
    result=subprocess.run([sys.executable,'-I','-B','-c',code,str(child)],cwd=root,capture_output=True,text=True,timeout=10)
    assert result.returncode==0,(result.stdout,result.stderr)
    print(result.stdout.strip())
else:
    effects=[]
    class Boundary:
        def authenticate_root_entry(self):return p.source_plan()
        def authenticated_installation_inputs(self):
            raw=(root/'runtime/vanguard/network/integration/inputs.json').read_bytes()
            assert c.digest(raw)==sys.argv[3],'modeled independent authority index authentication'
            return raw
        def authenticate_executor(self,plan):return {}
        def receive_authenticated_record_request(self):return dict(operation='verify_inherited_authority',record=0,deadline=200)
        def admit_record(self,*args):effects.append('admit')
        def verify_bound_record(self,*args):effects.append('verify')
        def syscall(self,*args):effects.append('modeled_syscall')
        def complete_record(self,*args):effects.append('complete')
        def quarantine_record_uncertainty(self,*args):effects.append('quarantine')
    entry=load(root/'profile-root-helper.py');boundary=Boundary()
    table={c.digest((root/'profile-root-helper.py').read_bytes()):e.RootEntry(boundary,clock=lambda:100,run=Mock(side_effect=AssertionError('host effect')))}
    out=io.StringIO()
    with redirect_stdout(out):status=entry.main([],qualified=table if action!='default' else None)
    print(json.dumps(dict(status=status,effects=effects,output=json.loads(out.getvalue()),
        empty_registry=e.QUALIFIED_ROOT=={})))
'''


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='TJS2504-declared-layout-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.root.chmod(0o700)

    def stage(self):
        source=c.HERE.parent.parent
        inventory=c.json_file(c.HERE/'integration/installation-inventory.json')
        for group in inventory['groups'].values():
            for name,destination in group.items():
                path=self.root/destination;path.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(source/name,path)
        shutil.copyfile(c.HERE/'integration/inputs.json',self.root/'runtime/vanguard/network/integration/inputs.json')
        return inventory

    def probe(self,action):
        result=subprocess.run([sys.executable,'-I','-B','-c',PROBE,str(self.root),action,
            c.digest((c.HERE/'integration/inputs.json').read_bytes())],
            cwd=self.root,capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(result.stderr,'')
        return result.stdout.strip()

    def test_known_bad_exact_21_member_closure_fails_without_checkout(self):
        base='202eedfcfb535e342034488ce86a71598faa279b'
        source=c.HERE.parent.parent
        manifest=json.loads(subprocess.check_output(['git','-C',str(source),'show',
            base+':vanguard/network/integration/manager-source-manifest.json']))
        for name in manifest['source_sha256']:
            (self.root/Path(name).name).write_bytes(subprocess.check_output(['git','-C',str(source),'show',base+':'+name]))
        code='import sys;sys.path.insert(0,sys.argv[1]);import profile_executor'
        result=subprocess.run([sys.executable,'-I','-B','-c',code,str(self.root)],cwd=self.root,capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,1)
        self.assertIn("No module named 'profile_contract'",result.stderr)

    def test_all_named_entries_and_native_recipe_data_in_declared_layout(self):
        self.stage()
        self.assertEqual(self.probe('imports'),'CHILD_IMPORTS_AND_DATA_OK')

    def test_default_root_refuses_in_staged_layout(self):
        self.stage();result=json.loads(self.probe('default'))
        self.assertEqual(result['status'],3);self.assertEqual(result['effects'],[])
        self.assertEqual(result['output']['result'],'REFUSED_UNQUALIFIED')

    def test_real_main_rootentry_recordexecutor_reachable_in_declared_layout(self):
        self.stage();result=json.loads(self.probe('success'))
        self.assertEqual(result['status'],0)
        self.assertEqual(result['effects'],['admit','verify','modeled_syscall','complete'])
        self.assertTrue(result['empty_registry'])

    def test_each_missing_or_altered_declared_member_refuses_before_effects(self):
        inventory=self.stage()
        # Root imports must exist to reach main. Other root members are covered
        # by child copies; isolated import failures are also pre-effect refusal.
        for destination in [d for group in inventory['groups'].values() for d in group.values()]:
            with self.subTest(destination=destination):
                path=self.root/destination;original=path.read_bytes()
                for damage in ('missing','altered'):
                    if damage=='missing':path.unlink()
                    else:path.write_bytes(original+b'\n# altered installed bytes\n')
                    result=subprocess.run([sys.executable,'-I','-B','-c',PROBE,str(self.root),'success',
                        c.digest((c.HERE/'integration/inputs.json').read_bytes())],
                        cwd=self.root,capture_output=True,text=True,timeout=10)
                    if result.returncode==0:
                        value=json.loads(result.stdout)
                        self.assertEqual(value['status'],3)
                        self.assertEqual(value['effects'],[])
                    else:
                        self.assertIn(result.returncode,(1,))
                        self.assertIn('Error',result.stderr)
                    path.write_bytes(original)

    def test_symlink_and_changed_authority_index_refuse_before_effects(self):
        self.stage()
        path=self.root/'runtime/vanguard/network/network.py'
        original=path.read_bytes();path.unlink();path.symlink_to(c.HERE/'network.py')
        value=json.loads(self.probe('success'));self.assertEqual(value['status'],3);self.assertEqual(value['effects'],[])
        path.unlink();path.write_bytes(original)
        path=self.root/'runtime/vanguard/network/integration/inputs.json'
        # A coherent local index/source rewrite still cannot replace the
        # independently authenticated expected digest supplied by the fixture.
        index=json.loads(path.read_bytes())
        altered=original+b'\n# coherent local rewrite\n'
        (self.root/'runtime/vanguard/network/network.py').write_bytes(altered)
        index['reference']['repository_files']['vanguard/network/network.py']=c.digest(altered)
        path.write_text(json.dumps(index))
        value=json.loads(self.probe('success'));self.assertEqual(value['status'],3);self.assertEqual(value['effects'],[])

    def test_child_entry_defaults_refuse_without_host_calls(self):
        self.stage();child=self.root/'runtime/vanguard/network'
        code=r'''
import importlib.util,sys
from pathlib import Path
from unittest.mock import patch
root=Path(sys.argv[1]);sys.path.insert(0,str(root))
def load(name):
    s=importlib.util.spec_from_file_location('fixture_'+name,root/name)
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
with patch('subprocess.run',side_effect=AssertionError('host effect')),patch('subprocess.check_output',side_effect=AssertionError('host effect')):
    outer=load('run-outer.py');sys.argv=['run-outer.py'];assert outer.main()==3
    helper=load('profile-helper.py');assert helper.main(['dispose','--spec',str(root/'integration/source-plan.json')])==3
    runner=load('run-profile.py');assert Path(runner.g.__file__)==root/'run-genesis.py'
    sys.argv=['run-profile.py','--grant-comment',next(iter(runner.c.CONSUMED)),'--artifact-sha256','a'*64]
    try:runner.main()
    except ValueError:pass
    else:raise AssertionError('consumed grant accepted')
print('CHILD_DEFAULT_REFUSALS_OK')
'''
        result=subprocess.run([sys.executable,'-I','-B','-c',code,str(child)],cwd=self.root,
            capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stderr,'');self.assertTrue(result.stdout.endswith('CHILD_DEFAULT_REFUSALS_OK\n'))

    def test_frozen_source_command_proposal_bindings_agree(self):
        import profile_executor as e
        import profile_packet as p
        self.assertEqual(e.proposal(p.source_plan()),c.json_file(c.HERE/'integration/root-executor-proposal.json'))
        self.assertEqual(p.render(p.source_plan()),c.json_file(c.HERE/'integration/lifecycle-packet.json'))
        self.assertEqual(p.render(p.source_plan())['units'],c.json_file(c.HERE/'integration/unit-manifest.json'))
        source=c.HERE.parent.parent
        manifest=c.json_file(c.HERE/'integration/manager-source-manifest.json')
        for name,sha in manifest['source_sha256'].items():
            self.assertEqual(hashlib.sha256((source/name).read_bytes()).hexdigest(),sha,name)


if __name__=='__main__':unittest.main(verbosity=2)
