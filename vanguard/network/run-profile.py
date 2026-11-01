#!/usr/bin/env python3
"""One future grant-bound production build and genesis-only attempt.

Direct controller: one nonblocking host lock, two admissions and one container.
Host staging is measured and abort bounded; only the container has kernel limits.
No native work is permitted without a fresh exact Platform grant.
"""
import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import resource
import stat
import shutil
import signal
import subprocess
import sys
import time
import urllib.request

import network as n
import policy
import profile_contract as c

spec = importlib.util.spec_from_file_location('genesis', c.HERE / 'run-genesis.py')
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)


def api(path):
    request = urllib.request.Request(os.environ['PAPERCLIP_API_URL'] + path,
        headers={'Authorization': 'Bearer ' + os.environ['PAPERCLIP_API_KEY']})
    with urllib.request.urlopen(request, timeout=15) as response:
        return response.read()


def pid_identity(pid):
    return [pid, Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[19]]


def controller_create(helper, staging_sha256, *, deadline):
    """Legacy off-path receipt validator retained for the retired helper tests."""
    value=helper.observe_and_create(staging_sha256,deadline=deadline)
    c.require(re.fullmatch('[0-9a-f]{64}',value['container_id']) and
        value['observation']['started_at']<=value['completed_at']<=value['observation']['started_at']+5 and
        value['completed_at']<deadline, 'exact timely atomic-create receipt')
    return value


def check_inputs(path):
    manifest = c.json_file(path)
    c.require(manifest['limits'] == c.LIMITS and manifest['source_candidate_state'] == 'SOURCE_ONLY_NOT_NATIVE_ACCEPTED',
              'input contract mismatch')
    for name,sha in manifest['candidate_files'].items():
        target = n.ROOT / name
        c.require(not target.is_symlink() and c.digest(target.read_bytes()) == sha, 'candidate drift: '+name)
    for name,sha in manifest['reference']['repository_files'].items():
        c.require(c.digest((n.ROOT/name).read_bytes()) == sha, 'preserved baseline drift: '+name)
    c.require(n.profile_hash(n.profile()) == manifest['reference']['profile_canonical_sha256'], 'profile drift')
    originals = policy.checked_source(g.BASE/'monero-fcmp')
    changed = policy.changes(originals,n.profile())
    for name,sha in manifest['reference']['overlay_changed_files'].items():
        c.require(c.digest(changed[name]) == sha, 'overlay changed bytes drift: '+name)
    for name,sha in manifest['reference']['upstream_files'].items():
        path = g.BASE/'monero-fcmp'/name
        raw = path.read_bytes()
        c.require(c.digest(raw) == sha and raw == subprocess.check_output(
            ['git','-C',str(g.BASE/'monero-fcmp'),'show',manifest['reference']['upstream']+':'+name],timeout=10),
            'pinned source drift: '+name)
    for name,inventory in manifest['cargo_inputs'].items():
        c.require(c.tree_fingerprint(g.BASE/'cargo-home'/name)==inventory,'offline Cargo input drift')
    c.require(c.tree_fingerprint(g.RUST)==manifest['rust_inputs'],'mounted toolchain input drift')
    return manifest


CONTAINER_FLAGS = ['--pull=never', '--network=none', '--cap-drop=ALL',
    '--security-opt=no-new-privileges', '--cpus=2', '--memory=4g',
    '--memory-swap=4g', '--pids-limit=256', '--ulimit', 'core=0']
GiB = 1024**3


def grant_payload(comment, *, commit, inputs_hash, artifact_hash, runner_hash, output, now):
    """The direct grant deliberately cannot be confused with a legacy v2 grant."""
    c.require(comment['issueId'] == c.ISSUE and comment.get('authorAgentId') == c.PLATFORM
              and comment.get('authorUserId') is None, 'Platform-authored grant required')
    blocks = re.findall(r'```meownero-direct-profile-grant\s*\n(.*?)\n```', comment['body'], re.S)
    c.require(len(blocks) == 1, 'one direct grant block required')
    value = json.loads(blocks[0])
    expected = dict(schema='meownero-direct-profile-grant/1', authorized=True,
        candidate_commit=commit, inputs_sha256=inputs_hash, artifact_sha256=artifact_hash,
        runner_sha256=runner_hash, output_root=str(output), attempts=1, retry=False,
        wall_seconds=4500, build_seconds=3600, runtime_seconds=600, cleanup_seconds=300,
        container_flags=CONTAINER_FLAGS, workload='three-production-binaries-genesis-only',
        non_genesis_blocks=0, transactions=0)
    c.require(all(type(value.get(k)) is type(v) and value[k] == v for k,v in expected.items()),
              'direct grant binding mismatch')
    c.require(value['valid_from_unix'] <= now < value['valid_until_unix']
              and now+4500 <= value['valid_until_unix'], 'grant validity window')
    c.require(re.fullmatch(r'[0-9a-f-]{36}', value['artifact_attachment_id']), 'artifact attachment ID')
    rule = value['load_rule']
    c.require(rule['metric'] == 'host-load-1-5-15' and len(rule['maximum']) == 3 and
              all(type(x) in (int,float) and 0 < x < 1000 for x in rule['maximum']), 'explicit load rule')
    overhead = value['host_overhead_allowance']
    c.require(overhead['mode'] == 'measured-controller-and-descendants-not-kernel-enforced' and
              all(type(overhead[k]) is int and overhead[k] > 0 for k in
                  ('peak_rss_bytes','cpu_seconds','peak_pids')), 'explicit host overhead allocation')
    return value


def acquire_lock():
    """Never unlink or replace an existing lock, including an unheld one."""
    created = False
    try:
        fd = os.open(g.LOCK, os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
    except FileNotFoundError:
        fd = os.open(g.LOCK, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        created = True
    try:
        info = os.fstat(fd)
        c.require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and
                  info.st_mode & 0o777 == 0o600 and info.st_nlink == 1, 'unsafe lock metadata')
        c.require(created or (info.st_dev,info.st_ino) == g.LOCK_ID, 'existing lock identity changed')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        current = g.LOCK.stat(follow_symlinks=False)
        c.require((current.st_dev,current.st_ino) == (info.st_dev,info.st_ino), 'lock path changed')
        return fd, dict(device=info.st_dev,inode=info.st_ino,created=created,mode='0600')
    except BaseException:
        os.close(fd)
        raise


def admit(image, root, grant):
    observed = g.admission(image)
    observed.update(free_disk_bytes=shutil.disk_usage(root).free, load=list(os.getloadavg()))
    c.require(observed['available_memory_bytes'] >= 5*GiB, 'requires 5 GiB available memory')
    c.require(observed['free_disk_bytes'] >= 20*GiB, 'requires 20 GiB free disk')
    c.require(not observed['native_processes'] and not observed['native_containers'], 'native collision')
    c.require(all(x <= y for x,y in zip(observed['load'],grant['load_rule']['maximum'])), 'load admission')
    return observed


class Controller:
    def __init__(self, root, grant, start):
        self.root,self.grant,self.start = root,grant,start
        self.build_end,self.work_end,self.end = start+3600,start+4200,start+4500
        self.children = []
        self.last_sample = 0
        self.peak = dict(peak_rss_bytes=0,cpu_seconds=0,peak_pids=0,disk_bytes=0)
        self.samples = 0
        self.cleaning = False
        self.cpu_origin = resource.getrusage(resource.RUSAGE_SELF)
        self.children_origin = resource.getrusage(resource.RUSAGE_CHILDREN)

    def remember(self, child):
        process,identity,members = child
        for path in Path('/proc').iterdir():
            if path.name.isdigit():
                try:
                    fields = (path/'stat').read_text().rsplit(')',1)[1].split()
                    if int(fields[3]) == process.pid and int(fields[19]) >= int(identity[1]):
                        members[int(path.name)] = fields[19]
                except (FileNotFoundError,ProcessLookupError): pass

    def stop(self, child):
        process,identity,members = child
        self.remember(child)
        def alive():
            result = []
            for pid,start in members.items():
                try:
                    fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
                    if fields[19] == start and fields[0] != 'Z': result.append(pid)
                except (FileNotFoundError,ProcessLookupError): pass
            return result
        if alive():
            try: os.killpg(process.pid,signal.SIGTERM)
            except ProcessLookupError: pass
            grace = min(time.monotonic()+5,self.end)
            while alive() and time.monotonic() < grace: time.sleep(.05)
            if alive():
                try: os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError: pass
        process.wait(timeout=min(5,max(.01,self.end-time.monotonic())))
        grace = min(time.monotonic()+1,self.end)
        while alive() and time.monotonic() < grace: time.sleep(.01)
        c.require(not alive(), 'owned host process remains')

    def run(self, argv, deadline, *, check=True, monitor=True, **kwargs):
        c.require(deadline > time.monotonic(), 'command deadline exhausted')
        # No API token, RPC login, Docker config or unrelated environment enters a child.
        env = dict(PATH=os.environ['PATH'],LC_ALL='C',GIT_NO_LAZY_FETCH='1',
                   HOME=str(self.root/'staging/tmp'))
        process = subprocess.Popen(argv, env=env, start_new_session=True, close_fds=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
        child = (process,pid_identity(process.pid),{});self.children.append(child)
        try:
            while True:
                self.remember(child)
                left = deadline-time.monotonic()
                c.require(left > 0, 'command deadline exhausted')
                if monitor and not self.cleaning: self.sample()
                try:
                    out,err = process.communicate(timeout=min(1,left))
                    break
                except subprocess.TimeoutExpired: pass
            if check and process.returncode:
                raise subprocess.CalledProcessError(process.returncode,argv)
            return subprocess.CompletedProcess(argv,process.returncode,out,err)
        finally:
            try: self.stop(child)
            finally:
                process.stdout.close();process.stderr.close()

    def sample(self, force=False):
        now = time.monotonic()
        c.require(now < self.work_end, 'work deadline exhausted')
        if not force and now-self.last_sample < 2: return
        self.last_sample = now
        c.require(shutil.disk_usage(self.root).free >= 4*GiB, 'backing free disk below 4 GiB')
        # du counts allocated blocks in the single owned directory, including evidence.
        result = self.run(['du','-sx','-B1',str(self.root)],min(now+10,self.work_end),monitor=False)
        used = int(result.stdout.split()[0]);self.peak['disk_bytes'] = max(self.peak['disk_bytes'],used)
        c.require(used <= 15*GiB, 'owned directory exceeds 15 GiB')
        processes = {}
        for path in Path('/proc').iterdir():
            if path.name.isdigit():
                try: processes[int(path.name)] = (path/'stat').read_text().rsplit(')',1)[1].split()
                except (FileNotFoundError,ProcessLookupError): pass
        owned = {os.getpid()}
        while True:
            expanded = owned | {pid for pid,fields in processes.items() if int(fields[1]) in owned}
            if expanded == owned: break
            owned = expanded
        ticks,page = os.sysconf('SC_CLK_TCK'),os.sysconf('SC_PAGE_SIZE')
        rss = sum(int(processes[pid][21])*page for pid in owned if pid in processes)
        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        rss = max(rss,resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024+usage.ru_maxrss*1024)
        cpu = (usage.ru_utime+usage.ru_stime-self.children_origin.ru_utime-self.children_origin.ru_stime+
               sum((int(processes[pid][11])+int(processes[pid][12]))/ticks for pid in owned if pid in processes)-
               self.cpu_origin.ru_utime-self.cpu_origin.ru_stime)
        for key,value in dict(peak_rss_bytes=rss,cpu_seconds=cpu,peak_pids=len(owned)).items():
            self.peak[key] = max(self.peak[key],value)
            c.require(value <= self.grant['host_overhead_allowance'][key], 'host overhead allowance exceeded')
        self.samples += 1

    def copy(self, source, destination):
        self.sample()
        return shutil.copy2(source,destination)


def stage_inputs(control, inputs, manifest):
    out = control.root/'staging'
    out.mkdir(mode=0o700);(out/'tmp').mkdir();(out/'private').mkdir(mode=0o700)
    source = out/'source';source.mkdir()
    pin = c.json_file(n.HERE.parent/'source-lock.json')
    for name,revision in [('',pin['upstream']['commit']),*pin['upstream']['submodules'].items()]:
        archive = out/('source-'+(name.replace('/','-') or 'root')+'.tar')
        control.run(['git','-C',str(g.BASE/'monero-fcmp'/name),'archive','-o',str(archive),revision],control.build_end)
        target = source/name;target.mkdir(parents=True,exist_ok=True)
        control.run(['tar','-xf',str(archive),'-C',str(target)],control.build_end)
        archive.unlink()
    overlay = policy.prepare(g.BASE/'monero-fcmp',out/'overlay',n.profile())
    c.require(overlay['overlay_id'] == manifest['reference']['overlay_sha256'], 'overlay drift')
    control.run(['git','apply',str(out/'overlay/selected-9-90.patch')],control.build_end,cwd=source)
    for name,sha in manifest['reference']['overlay_changed_files'].items():
        c.require(c.digest((source/name).read_bytes()) == sha, 'applied overlay drift')
    cargo = out/'cargo-home';cargo.mkdir()
    for name in ('registry','git'):
        shutil.copytree(g.BASE/'cargo-home'/name,cargo/name,symlinks=True,copy_function=control.copy)
        c.require(c.tree_fingerprint(cargo/name) == manifest['cargo_inputs'][name], 'copied Cargo drift')
    shutil.copytree(c.HERE,out/'harness',copy_function=control.copy,
        ignore=shutil.ignore_patterns('evidence','__pycache__','core-review'))
    control.copy(inputs,out/'inputs.json');control.sample(force=True)


def container_command(root, name, image):
    out = root/'staging'
    return g.DOCKER+['create','--name',name,'--label','meownero.profile.attempt='+name,
        '--cidfile',str(root/'container.cid'),*CONTAINER_FLAGS,'--user',f'{os.getuid()}:{os.getgid()}',
        '-v',str(out)+':/out','-v',str(root/'public')+':/public',
        '-v',str(g.RUST)+':/opt/rust:ro','--workdir','/out',image,
        '/bin/bash','/out/harness/integration/build.sh']


def inspect_owned(control, name, image, deadline):
    result = control.run(g.DOCKER+['inspect',name],deadline,check=False,monitor=False)
    if result.returncode:
        c.require(b'No such' in result.stderr, 'container absence unconfirmed')
        return None
    value, = json.loads(result.stdout)
    c.require(value['Name'] == '/'+name and value['Image'] == image and
        value['Config']['Labels'].get('meownero.profile.attempt') == name and
        any(m['Source'] == str(control.root/'staging') and m['Destination'] == '/out'
            for m in value['Mounts']), 'owned container identity mismatch')
    c.require(re.fullmatch('[0-9a-f]{64}',value['Id']), 'invalid container identity')
    return value


def verify_limits(value):
    h = value['HostConfig']
    c.require(h['NetworkMode'] == 'none' and h['NanoCpus'] == 2_000_000_000 and
        h['Memory'] == h['MemorySwap'] == 4*GiB and h['PidsLimit'] == 256 and
        h['CapDrop'] == ['ALL'] and 'no-new-privileges' in h['SecurityOpt'] and
        not h['Privileged'] and not h.get('PortBindings') and
        any(x['Name'] == 'core' and x['Soft'] == x['Hard'] == 0 for x in h['Ulimits']) and
        value['Config']['User'] == f'{os.getuid()}:{os.getgid()}', 'container limit mismatch')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,default=c.HERE/'integration/inputs.json')
    parser.add_argument('--grant-comment',required=True)
    parser.add_argument('--artifact-sha256',required=True)
    parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args()
    os.umask(0o077)
    c.require(re.fullmatch(r'[0-9a-f-]{36}',args.grant_comment) and
        args.grant_comment not in c.CONSUMED and re.fullmatch('[0-9a-f]{64}',args.artifact_sha256),
        'new exact grant and artifact digest required')
    c.require(args.out.is_absolute() and args.out == args.out.resolve() and
        args.out.parent.is_dir() and not args.out.exists(), 'fresh absolute output root required')
    commit = subprocess.check_output(['git','-C',str(n.ROOT),'rev-parse','HEAD'],text=True,timeout=10).strip()
    c.require(not subprocess.check_output(['git','-C',str(n.ROOT),'status','--porcelain'],text=True,timeout=10).strip(),
              'commit exact candidate first')
    manifest = check_inputs(args.inputs)
    comment = json.loads(api('/api/issues/'+c.ISSUE+'/comments/'+args.grant_comment))
    c.require(comment['id'] == args.grant_comment, 'grant comment identity')
    grant = grant_payload(comment,commit=commit,inputs_hash=c.digest(args.inputs.read_bytes()),
        artifact_hash=args.artifact_sha256,runner_hash=c.digest(Path(__file__).read_bytes()),
        output=args.out,now=time.time())
    c.require(c.digest(api('/api/attachments/'+grant['artifact_attachment_id']+'/content')) == args.artifact_sha256,
              'authenticated artifact digest mismatch')
    fd,lock = acquire_lock()
    start = time.monotonic()
    control = Controller(args.out,grant,start)
    image = manifest['builder_image']
    name = 'meownero-profile-'+args.grant_comment
    rows = c.empty_rows()
    receipt = dict(schema='meownero-direct-profile-attempt/1',result='INCOMPLETE',launch_ready=False,
        grant=args.grant_comment,candidate_commit=commit,runner_sha256=c.digest(Path(__file__).read_bytes()),
        lock=lock,exclusions={key:'NOT_RUN' for key in c.EXCLUDED})
    created = False
    create_intent = False
    prior = {}
    def interrupted(signum,frame): raise TimeoutError('controller watchdog or termination')
    try:
        for sig in (signal.SIGALRM,signal.SIGINT,signal.SIGTERM,signal.SIGHUP):
            prior[sig] = signal.signal(sig,interrupted)
        signal.setitimer(signal.ITIMER_REAL,4200)
        receipt['first_admission'] = admit(image,args.out.parent,grant)
        # mkdir is the durable one-use marker. The grant binds this exact path;
        # even a crash before receipt publication leaves it non-reusable.
        n.fresh_directory(args.out);created = True
        parent = os.open(args.out.parent,os.O_RDONLY|os.O_DIRECTORY)
        try: os.fsync(parent)
        finally: os.close(parent)
        (args.out/'public').mkdir(mode=0o700)
        n.write_json(args.out/'consumed.json',dict(grant=args.grant_comment,commit=commit))
        stage_inputs(control,args.inputs,manifest)
        info = control.run(g.DOCKER+['image','inspect',image],control.build_end)
        c.require(json.loads(info.stdout)[0]['Id'] == image, 'local pinned image required')
        control.sample(force=True)
        current = g.LOCK.stat(follow_symlinks=False)
        c.require((current.st_dev,current.st_ino) == (lock['device'],lock['inode']), 'lock replaced')
        receipt['second_admission'] = admit(image,args.out,grant)
        create_intent = True
        control.run(container_command(args.out,name,image),min(time.monotonic()+30,control.build_end))
        value = inspect_owned(control,name,image,control.build_end)
        c.require(value is not None, 'created container missing');verify_limits(value)
        receipt['container_id'] = value['Id']
        control.run(g.DOCKER+['start','-a',value['Id']],control.build_end)
        value = inspect_owned(control,name,image,control.build_end)
        c.require(value['State']['ExitCode'] == 0 and not value['State']['OOMKilled'], 'native build failed')
        rows['build.json'] = c.json_file(args.out/'public/build.json')
        c.require(time.monotonic()+600 <= control.work_end, 'full runtime allowance unavailable')
        (args.out/'staging/BUILD_COMPLETE').write_text('runtime\n')
        control.run(g.DOCKER+['start','-a',value['Id']],time.monotonic()+600)
        value = inspect_owned(control,name,image,control.work_end)
        c.require(value['State']['ExitCode'] == 0 and not value['State']['OOMKilled'], 'native runtime failed')
        for filename in c.REQUIRED:
            if filename not in ('resources.json','cleanup.json'):
                rows[filename] = c.json_file(args.out/'public'/filename)
        control.sample(force=True)
        receipt['work_complete'] = True
    except Exception as error:
        receipt.update(result='FAIL' if created else 'REFUSED_BEFORE_ATTEMPT',failure_class=type(error).__name__)
    finally:
        control.cleaning = True
        # Cleanup has its own exclusive reserve, still inside the 4500s wall cap.
        signal.setitimer(signal.ITIMER_REAL,max(.01,control.end-time.monotonic()))
        for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP): signal.signal(sig,signal.SIG_IGN)
        cleanup = rows['cleanup.json']
        try:
            for child in control.children: control.stop(child)
            value = inspect_owned(control,name,image,control.end) if create_intent else None
            if value:
                if value['State']['Running']:
                    control.run(g.DOCKER+['stop','--time','10',value['Id']],min(time.monotonic()+20,control.end),check=False)
                    value = inspect_owned(control,name,image,control.end)
                    if value and value['State']['Running']:
                        control.run(g.DOCKER+['kill',value['Id']],control.end)
                if value: control.run(g.DOCKER+['rm','-f',value['Id']],control.end)
            c.require(not create_intent or inspect_owned(control,name,image,control.end) is None,'owned CID remains')
            cleanup['owned_cid_absent'] = dict(status='PASS',create_intent=create_intent)
            counters = {}
            if created:
                for phase in ('build','runtime'):
                    path = args.out/'staging'/('resources-'+phase+'.json')
                    if path.is_file(): counters[phase] = c.json_file(path)
            receipt['container_counters'] = counters
            no_oom = len(counters) == 2 and all(x['oom_kill'] == x['oom'] == 0 for x in counters.values())
            rows['resources.json'] = dict(
                parent_enclosure=dict(status='PASS' if 'container_id' in receipt else 'NOT_RUN',
                    mode='container-kernel-limits; host-overhead-measured-only',flags=CONTAINER_FLAGS,
                    host_overhead_allowance=grant['host_overhead_allowance'],measured=control.peak,samples=control.samples,
                    sampling='2s and copy/phase boundaries; RSS includes conservative per-process lifetime high-water marks'),
                deadlines=dict(status='PASS' if time.monotonic() < control.end else 'FAIL',
                    wall_seconds=4500,build_seconds=3600,runtime_seconds=600,cleanup_seconds=300),
                disk=dict(status='PASS' if control.samples else 'NOT_RUN',peak_bytes=control.peak['disk_bytes'],
                    abort_bytes=15*GiB,minimum_free_bytes=4*GiB,mode='sampled-abort-not-quota'),
                no_oom=dict(status='PASS' if no_oom else 'NOT_RUN',counters=counters))
            if created and (args.out/'staging').exists(): shutil.rmtree(args.out/'staging')
            cleanup['owned_staging_removed'] = dict(status='PASS' if created else 'NOT_RUN')
        except Exception as error:
            receipt.update(result='FAIL',cleanup_failure_class=type(error).__name__)
        finally:
            try:
                for child in control.children: control.stop(child)
                cleanup['owned_pids_absent'] = dict(status='PASS',count=len(control.children))
            except Exception as error:
                receipt.update(result='FAIL',pid_cleanup_failure_class=type(error).__name__)
            finally:
                signal.setitimer(signal.ITIMER_REAL,0)
                os.close(fd)  # The sole lock descriptor; no child inherits it.
                cleanup['lock_released'] = dict(status='PASS',descriptor_closed=True)
                for sig,handler in prior.items(): signal.signal(sig,handler)
        receipt['wall_seconds'] = time.monotonic()-start
        receipt['rows'] = rows
        if receipt['result'] == 'INCOMPLETE': receipt['result'] = c.verdict(rows)
        if created:
            for filename,data in rows.items(): n.write_json(args.out/'public'/filename,data)
            n.write_json(args.out/'public/receipt.json',receipt)
        print(json.dumps(dict(result=receipt['result'],launch_ready=False,consumed=created)))
    return 0 if receipt['result'].startswith('PASS_') else 1


if __name__ == '__main__':
    try: raise SystemExit(main())
    except Exception as error:
        print('REFUSED: '+type(error).__name__,file=sys.stderr)
        raise SystemExit(3)
