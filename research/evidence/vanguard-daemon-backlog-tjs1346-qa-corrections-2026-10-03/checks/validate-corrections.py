import json,subprocess,time,hashlib
from pathlib import Path
run=Path(__file__).parent
scratch=run/'scratch'
repo=Path.cwd()
src=scratch/'vanguard-src'
bundle=repo/'research/evidence/vanguard-daemon-backlog-tjs1346-2026-10-03'
checks=run/'correction-checks';checks.mkdir()
commands=[
 ('baseline',['python3','-B','vanguard/verify-daemon-backlog.py',str(bundle),'--src',str(src)]),
 ('refusals',['python3','-B','vanguard/test-daemon-backlog-refusals.py',str(bundle),'--src',str(src),'--scratch',str(scratch)]),
 ('qa-regressions',['python3','-B',str(run/'qa-evidence/qa-backlog.py'),'--repo',str(repo),'--bundle',str(bundle),'--src',str(src),'--out',str(scratch/'qa-regressions')]),
 ('load',['python3','-B','vanguard/verify-daemon-load.py',str(repo/'research/evidence/vanguard-daemon-load-tjs1171-2026-10-01'),'--src',str(src)]),
 ('p2p',['python3','-B','vanguard/verify-daemon-p2p.py',str(repo/'research/evidence/vanguard-daemon-p2p-tjs996-2026-09-29')]),
 ('diff-check',['git','diff','--check']),
]
results=[]
for name,cmd in commands:
 began=time.monotonic()
 p=subprocess.run(cmd,capture_output=True,text=True,timeout=300)
 (checks/(name+'.stdout')).write_text(p.stdout);(checks/(name+'.stderr')).write_text(p.stderr)
 row={'name':name,'command':cmd,'exit':p.returncode,'wall_seconds':time.monotonic()-began}
 results.append(row);(checks/'commands.json').write_text(json.dumps(results,indent=2)+'\n')
 print(name,'exit',p.returncode,p.stdout[-1000:],p.stderr[-1000:],flush=True)
 if p.returncode:raise SystemExit(p.returncode)
qa=json.loads((scratch/'qa-regressions/counterexamples.json').read_text())
assert len(qa)==11 and all(row['exit']!=0 and row['rehash_verified'] for row in qa),qa
(checks/'qa-regression-assertions.json').write_text(json.dumps({'result':'PASS_WRITER_RERUN_OF_QA_RECIPE','refused':len(qa),'all_rehashed':True,'independent_acceptance':False},indent=2)+'\n')
print('PASS_QA_REGRESSIONS refused=11',flush=True)
