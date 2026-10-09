import hashlib,importlib.util,json,subprocess,sys,tempfile
from pathlib import Path
from unittest.mock import patch
root=Path(__file__).resolve().parents[3]
base=Path(tempfile.mkdtemp(prefix='tjs1882-controls09-'));package=base/'package';package.mkdir(mode=0o700);(package/'bin').mkdir();(package/'bin/monerod').write_bytes(b'fixture');(package/'tester.py').write_text('# no native execution\n');(package/'release.json').write_text(json.dumps({'architecture':'i686','upstream_commit':'e'*40}))
private='PRIVATE_WALLET_LOG_OR_SEED_SENTINEL'
reasons={'wrong-pin':'wrong source pin','wrong-target':'wrong architecture','changed-binary':'package hash mismatch','unlisted-private-file':'package file set mismatch','symlink-directory':'package symlink refused','hardlink':'hard-linked input refused'}
rows=[]
for case,expected,completed in [('clean-nonzero','clean-preflight',0),('wrong-target-mismatch','wrong-target',1),('symlink-os-error','symlink-directory',4),('invoke-timeout','wrong-pin',0)]:
 spec=importlib.util.spec_from_file_location('controls_'+case,root/'vanguard/test-portable-refusals.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);out=base/case
 def invoke(argv,**kw):
  name=Path(argv[2]).parent.name
  if case=='invoke-timeout' and name=='wrong-pin':raise subprocess.TimeoutExpired([private],60,output=private,stderr=private)
  rc=0 if name=='package' else 1
  if case=='clean-nonzero' and name=='package':rc=1
  if case=='wrong-target-mismatch' and name=='wrong-target':rc=0
  return subprocess.CompletedProcess(argv,rc,stdout=private,stderr=reasons.get(name,'')+' '+private)
 original=Path.symlink_to
 def link(self,*a,**kw):
  if case=='symlink-os-error':
   error=PermissionError(1,private);error.winerror=1314;raise error
  return original(self,*a,**kw)
 error=None
 with patch.object(sys,'argv',['controls','--package',str(package),'--out',str(out)]),patch.object(m.subprocess,'run',invoke),patch.object(Path,'symlink_to',link):
  try:m.main()
  except BaseException as e:error=type(e).__name__
 receipt=json.loads((out/'controls.json').read_text());assert receipt['result']=='FAIL_REFUSALS' and receipt['first_failed_case']['case']==expected and len(receipt['cases'])==completed
 raw=(out/'controls.json').read_text();assert private not in raw and 'stdout' not in raw and 'stderr' not in raw and 'argv' not in raw
 assert receipt['first_failed_case']['failure_type']==error
 if case=='symlink-os-error':assert receipt['first_failed_case']['winerror']==1314 and receipt['first_failed_case']['phase']=='MUTATE_PACKAGE'
 rows.append({'case':case,'first_failed_case':receipt['first_failed_case'],'completed_case_count':completed,'private_output_exported':False,'result':'PASS_SCALAR_FAILURE_RECEIPT_FIXTURE'})
proof={'schema':'meownero-i68609-control-failure-receipt-fixtures/1','result':'PASS_FIRST_FAILURE_COMPLETED_SUMMARIES_AND_PRIVACY','helper_sha256':hashlib.sha256((root/'vanguard/test-portable-refusals.py').read_bytes()).hexdigest(),'cases':rows,'native_controls':'UNTESTED_BY_MOCKED_PREFIX_FIXTURES'}
(root/'research/evidence/vanguard-portable-production-tjs1882-2026-10-09/i68609-control-receipt-fixtures.json').write_text(json.dumps(proof,indent=2)+'\n');print(proof['result'],len(rows))
