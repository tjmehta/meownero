import subprocess,json,hashlib,pathlib,time,shlex
out=pathlib.Path('/out');rows=[]
cc='/llvm/bin/aarch64-w64-mingw32-clang'
version=subprocess.run([cc,'--version'],capture_output=True,text=True,timeout=10)
flags=dict(row.split(' = ',1) for row in pathlib.Path('/prior-flags.make').read_text().splitlines() if ' = ' in row)
for name,source,march in [('baseline','/input/slow-hash.original.c','armv8-a+crypto'),('candidate-crypto','/input/slow-hash.candidate.c','armv8-a+crypto'),('candidate-no-crypto','/input/slow-hash.candidate.c','armv8-a')]:
 argv=[cc,*shlex.split(flags['C_DEFINES']),*shlex.split(flags['C_FLAGS'].replace('-march=armv8-a+crypto','-march='+march)),'-I/source/src/crypto','-I/source/contrib/epee/include','-isystem','/depends/include','-c',source,'-o',str(out/(name+'.o'))]
 started=time.monotonic();p=subprocess.run(argv,capture_output=True,text=True,timeout=30)
 (out/(name+'.log')).write_text(p.stdout+p.stderr)
 row={'case':name,'argv':argv,'exit':p.returncode,'seconds':time.monotonic()-started,'log_sha256':hashlib.sha256((p.stdout+p.stderr).encode()).hexdigest()}
 obj=out/(name+'.o')
 if obj.exists():
  row['object_sha256']=hashlib.sha256(obj.read_bytes()).hexdigest();row['coff_machine']=obj.read_bytes()[:2].hex()
 rows.append(row)
result={'compiler':version.stdout,'compiler_exit':version.returncode,'cases':rows,'scope':'CROSS_COMPILE_DIAGNOSTIC_ONLY_NO_NATIVE_WINDOWS_EXECUTION'}
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
for name in ['memory.peak','memory.events','pids.peak']:
 p=pathlib.Path('/sys/fs/cgroup')/name
 if p.exists():(out/name).write_bytes(p.read_bytes())
raise SystemExit(0 if rows[0]['exit']!=0 and all(x['exit']==0 for x in rows[1:]) else 1)
