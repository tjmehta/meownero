import fcntl,os,subprocess,time,json
from pathlib import Path
scratch=Path(__file__).parent
up=scratch/'vanguard-src/monero-fcmp'
rust=Path.home()/'.rustup/toolchains/stable-x86_64-unknown-linux-gnu'
image=json.loads(Path('vanguard/source-lock.json').read_text())['builder']['image_id']
name='vanguard-tjs1346-prepare-'+str(os.getpid())
cmd=['docker','run','--rm','--name',name,'--pull=never','--network=none','--cap-drop=ALL','--security-opt=no-new-privileges','--cpus=2','--memory=4g','--memory-swap=4g','--pids-limit=256','--ulimit','core=0','-u',f'{os.getuid()}:{os.getgid()}','-v',str(up)+':/src','-v',str(scratch/'vanguard-src/cargo-home')+':/cargo-home','-v',str(rust)+':/opt/rust:ro','-v',str(scratch)+':/out','-e','CARGO_HOME=/cargo-home','-e','CARGO_NET_OFFLINE=true','-e','PATH=/opt/rust/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin','-w','/src/build/vanguard',image,'bash','-euc',"trap 'cat /sys/fs/cgroup/memory.peak > /out/prepare.memory; cat /sys/fs/cgroup/memory.events > /out/prepare.memory-events; cat /sys/fs/cgroup/cpu.stat > /out/prepare.cpu' EXIT\ntimeout 1700 make -j1 daemon wallet_rpc_server"]
with open('/tmp/meownero-swarm-20260912-heavy.lock','a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 if int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:'))) < 5*1024**2:raise SystemExit('low available memory')
 began=time.monotonic(); code=124
 try:
  with (scratch/'prepare.log').open('w') as log: code=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=1800).returncode
 finally:
  subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  (scratch/'prepare.json').write_text(json.dumps({'command':cmd,'exit':code,'wall_seconds':time.monotonic()-began,'origin':'private copy of pinned existing primitive source/cache; daemon targets rebuilt'},indent=2)+'\n')
 print('native preparation exit',code)
 raise SystemExit(code)
