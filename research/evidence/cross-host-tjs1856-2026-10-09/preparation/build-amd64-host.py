from pathlib import Path
import subprocess,json,fcntl,hashlib,time,shutil
r=Path('~/Developer/tjs1856-d779915e');o=r/'amd64';o.mkdir();log=o/'preparation';log.mkdir()
def run(label,argv,timeout=600):
 b=time.monotonic()
 with (log/(label+'.log')).open('wb') as f:p=subprocess.run(argv,stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
 row={'label':label,'argv':argv,'exit':p.returncode,'wall_seconds':time.monotonic()-b};receipt['commands'].append(row);(log/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(label,p.returncode,flush=True);assert p.returncode==0,label
 return (log/(label+'.log')).read_text().strip()
receipt={'schema':'tjs1856-amd64-preparation/1','commands':[],'scope':'x86 preparation emulated on build-mac ARM64','result':'INCOMPLETE'}
with open('/tmp/meownero-swarm-20260912-heavy.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 mem=subprocess.check_output(['colima','ssh','--','cat','/proc/meminfo'],text=True);assert int(next(x.split()[1] for x in mem.splitlines() if x.startswith('MemAvailable:')))>=5*1024**2
 assert shutil.disk_usage(r).free>=5*1024**3
 run('extract',['tar','-xzf',str(r/'build-cache-amd64.tar.gz'),'-C',str(o)])
 pin=json.loads((r/'source-lock.json').read_text());up=o/'monero-fcmp'
 assert subprocess.check_output(['git','-C',str(up),'rev-parse','HEAD'],text=True).strip()==pin['upstream']['commit']
 run('remove-prior-harness-injection',['git','-C',str(up),'restore','--source=HEAD','tests/CMakeLists.txt'])
 assert not subprocess.check_output(['git','-C',str(up),'status','--porcelain','--untracked-files=no'],text=True).strip()
 for path,rev in pin['upstream']['submodules'].items():assert subprocess.check_output(['git','-C',str(up/path),'rev-parse','HEAD'],text=True).strip()==rev
 assert hashlib.sha256((up/pin['rust']['cargo_lock_path']).read_bytes()).hexdigest()==pin['rust']['cargo_lock_sha256']
 rootfs=json.loads((r/'rootfs-receipt.json').read_text());assert hashlib.sha256((r/'builder-rootfs-amd64.tar.gz').read_bytes()).hexdigest()==rootfs['rootfs_sha256']
 image=run('import-builder',['docker','--context','colima','import','--platform=linux/amd64',str(r/'builder-rootfs-amd64.tar.gz'),'tjs1856-builder:amd64'])
 receipt['image_id']=image;receipt['source_pins']=pin;receipt['rootfs']=rootfs
 argv=['docker','--context','colima','run','--rm','--platform=linux/amd64','--name','tjs1856-amd64-build','--pull=never','--network=none','--cap-drop=ALL','--security-opt=no-new-privileges','--cpus=2','--memory=4g','--memory-swap=4g','--pids-limit=256','--ulimit','core=0','-v',str(up)+':/src','-v',str(o)+':/work','-e','CARGO_HOME=/work/cargo-home','-e','CARGO_NET_OFFLINE=true','-e','PATH=/work/rust-x86/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin','-w','/src/build/vanguard',image,'bash','-euc',"trap 'cat /sys/fs/cgroup/memory.peak > /work/preparation/build.memory; cat /sys/fs/cgroup/memory.events > /work/preparation/build.memory-events' EXIT; rustc -V; uname -m; cmake -D CMAKE_BUILD_TYPE=Release -D ARCH=default -D BUILD_TESTS=OFF -D USE_DEVICE_TREZOR=OFF -D BUILD_GUI_DEPS=OFF ../..; timeout 3500 make -j1 daemon wallet_rpc_server"]
 try:run('build',argv,3600)
 finally:subprocess.run(['docker','--context','colima','rm','-f','tjs1856-amd64-build'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 receipt['binary']={n:{'sha256':hashlib.sha256((up/'build/vanguard/bin'/n).read_bytes()).hexdigest(),'bytes':(up/'build/vanguard/bin'/n).stat().st_size} for n in ['monerod','monero-wallet-rpc']}
 receipt['result']='PASS_EMULATED_BUILD';(log/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(receipt['binary'],flush=True)
