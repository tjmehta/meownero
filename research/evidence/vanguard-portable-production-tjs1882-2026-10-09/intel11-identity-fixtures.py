import ast,hashlib,json,shlex
from pathlib import Path
from types import SimpleNamespace
root=Path(__file__).resolve().parents[3];p=root/'vanguard/run-portable-ci.py';tree=ast.parse(p.read_text());outer=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='mac_check');code=compile(ast.Module(body=[n for n in outer.body if isinstance(n,ast.FunctionDef) and n.name=='remember_identity'],type_ignores=[]),str(p),'exec')
cases=[];bind=(1,2,0o104755,'bound-sha');start=('Fri','Oct','9','15:00:00','2026');row=(1000,501,0,start,'/bin/ps -axo pid=,ppid=,rss=');ident=row[1:]
def run(name,row,expected,known=None,bindings=None,states=None,binding=bind):
 receipt={'helper_observations':[],'unverified_observations':[]};original=dict(known or {});namespace={'os':SimpleNamespace(getuid=lambda:501,geteuid=lambda:501),'process':SimpleNamespace(pid=1000),'states':states or {},'known':dict(original),'helper_bindings':dict(bindings or {}),'unverified_zombies':set(),'rejected_live':{},'pid_absent':lambda pid,rows:False,'receipt':receipt,'platform':SimpleNamespace(system=lambda:'Darwin'),'shlex':shlex,'helper_binding':lambda pid:binding,'helper_file_binding':lambda:binding}
 def reject(reason,observation=None):raise AssertionError(reason)
 namespace['reject']=reject;exec(code,namespace);actual='PASS'
 try:namespace['remember_identity'](1001,row)
 except AssertionError as e:actual=str(e)
 assert actual==expected,(name,actual,expected)
 if name.startswith('root-to-normal') or name=='reused-helper-start':assert namespace['known']==original
 accounted=1001 in namespace['unverified_zombies']
 if expected=='UNVERIFIED_FIRST_ZOMBIE':assert accounted and 1001 in namespace['known'] and receipt['unverified_observations'][0]['role']=='UNVERIFIED_OWNED_ZOMBIE'
 cases.append({'case':name,'observed':actual,'expected':expected,'first_zombie_accounted_for_cleanup':accounted})
run('exact-observer',row,'PASS');run('exact-process-query',(1000,501,0,start,'ps -p 1234'),'PASS');run('exact-command-query',(1000,501,0,start,'ps -p 1234 -o command='),'PASS')
run('ordinary-owned-descendant',(1000,501,501,start,'python owned-worker.py'),'PASS')
run('foreign-real-uid',(1000,502,0,start,row[4]),'REAL_UID_MISMATCH');run('other-effective-uid',(1000,501,502,start,row[4]),'EFFECTIVE_UID_NOT_ALLOWLISTED');run('wrong-parent',(999,501,0,start,row[4]),'EFFECTIVE_UID_NOT_ALLOWLISTED');run('wrong-helper',(1000,501,0,start,'/usr/bin/other -axo pid=,ppid=,rss='),'EFFECTIVE_UID_NOT_ALLOWLISTED');run('wrong-arguments',(1000,501,0,start,'/bin/ps -axo command='),'EFFECTIVE_UID_NOT_ALLOWLISTED')
run('unknown-exit-display',(1000,501,0,start,'(ps)'),'EFFECTIVE_UID_NOT_ALLOWLISTED');run('known-exit-display',(1000,501,0,start,'(ps)'),'PASS',{1001:ident},{1001:bind});run('reused-helper-start',(1000,501,0,('different',)*5,row[4]),'REMEMBERED_IMMUTABLE_PROCESS_IDENTITY_CHANGED',{1001:ident},{1001:bind});run('changed-helper-kernel-file',row,'REMEMBERED_HELPER_SYSTEM_FILE_CHANGED',{1001:ident},{1001:bind},binding=(1,3,0o104755,'other-sha'))
run('known-zombie',(1000,501,0,start,'(ps)'),'PASS',{1001:ident},{1001:bind},{1001:'Z'});run('zombie-reused-start',(1000,501,0,('different',)*5,'(ps)'),'REMEMBERED_IMMUTABLE_PROCESS_IDENTITY_CHANGED',{1001:ident},{1001:bind},{1001:'Z'})
run('root-to-normal-euid-reuse',(1000,501,501,('different',)*5,'python owned-worker.py'),'REMEMBERED_IMMUTABLE_PROCESS_IDENTITY_CHANGED',{1001:ident},{1001:bind});run('root-to-normal-euid-same-start',(1000,501,501,start,row[4]),'REMEMBERED_IMMUTABLE_PROCESS_IDENTITY_CHANGED',{1001:ident},{1001:bind})
run('first-unverified-root-zombie',(1000,501,0,start,'(ps)'),'UNVERIFIED_FIRST_ZOMBIE',states={1001:'Z'});run('first-unverified-normal-zombie',(1000,501,501,start,'(python)'),'UNVERIFIED_FIRST_ZOMBIE',states={1001:'Z'})
proof={'schema':'meownero-intel11-immutable-identity-fixtures/1','result':'PASS_BEFORE_BRANCH_IDENTITY_AND_FIRST_ZOMBIE_ACCOUNTING','source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'cases':cases,'allow_case_count':sum(c['observed']=='PASS' for c in cases),'reject_case_count':sum(c['observed']!='PASS' for c in cases),'native_Intel_journey':'UNTESTED_BY_FIXTURES'}
(root/'research/evidence/vanguard-portable-production-tjs1882-2026-10-09/intel11-identity-fixtures.json').write_text(json.dumps(proof,indent=2)+'\n');print(proof['result'],len(cases),proof['allow_case_count'],proof['reject_case_count'])
