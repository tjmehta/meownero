#!/usr/bin/env python3
"""One future grant-bound production build and genesis-only attempt.

No resource provisioning or implicit grant. Platform must launch this process and
its dedicated Docker daemon below the frozen common parent before entry. Current
source-only authorization does not permit invoking this entry point for runtime.
"""
import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
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


def group(pid):
    lines = Path(f'/proc/{pid}/cgroup').read_text().splitlines()
    return next(line[3:] for line in lines if line.startswith('0::'))


def pid_identity(pid):
    return [pid, Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[19]]


def command(argv, deadline, **kwargs):
    left = deadline - time.monotonic()
    c.require(left > 0, 'deadline exhausted')
    return subprocess.run(argv, check=True, timeout=left, **kwargs)


def admission(docker, image, fs):
    snap = g.admission(image)  # Uses the existing host socket only for collision detection.
    snap['free_disk_bytes'] = shutil.disk_usage(fs).free
    snap['load'] = list(os.getloadavg())
    # The dedicated attempt daemon must have no container before creation.
    c.require(not subprocess.check_output(docker + ['ps','-aq'],text=True,timeout=10).strip(),
              'dedicated attempt daemon has preexisting containers')
    c.admit(snap)
    return snap


def read_enclosure(value):
    e = value['enclosure']
    parent = e['cgroup_parent']
    cg = Path('/sys/fs/cgroup' + parent)
    c.require(c.no_alias(cg) == cg, 'cgroup path alias')
    counters = {key:(cg/key).read_text().strip() for key in
                ['cpu.max','memory.max','memory.swap.max','memory.oom.group','pids.max','cgroup.procs']}
    daemon = e['docker_pid_identity']
    c.stop_identity(daemon, pid_identity(daemon[0]))
    c.enclosure(counters, group('self'), group(daemon[0]), parent)
    root = c.no_alias(e['fixed_filesystem'])
    c.require(root.is_mount() and root.stat().st_dev == e['filesystem_device'], 'fixed filesystem mount differs')
    # Capacity is enforced by the filesystem, independent of the sampling interval.
    usage = shutil.disk_usage(root)
    c.require(usage.total <= c.LIMITS['disk_hard_bytes'], 'writable filesystem exceeds 15 GiB hard bound')
    c.require(root.stat().st_uid == os.getuid() and root.stat().st_mode & 0o077 == 0, 'enclosure owner/mode')
    docker = ['docker','--host',e['docker_socket']]
    c.require(e['docker_socket'].startswith('unix://' + str(root) + '/'), 'Docker socket outside bounded root')
    info = json.loads(subprocess.check_output(docker+['info','--format','{{json .}}'],text=True,timeout=10))
    c.require(info['CgroupVersion'] == '2' and info['CgroupDriver'] == 'cgroupfs', 'requires cgroupfs v2')
    c.require(Path(info['DockerRootDir']).is_relative_to(root), 'Docker writable store outside bounded root')
    c.require(e['attempt_started_monotonic'] <= time.monotonic() < e['attempt_started_monotonic'] + 60,
              'enclosure startup took more than 60s or invalid host clock')
    # Platform's launcher starts its independent hard watchdog at the same origin,
    # covering provisioning/image import and a controller killed before finally.
    c.require(e['watchdog']['deadline_monotonic'] == e['attempt_started_monotonic'] + 4500 and
              e['watchdog']['cleanup_owner'] == c.PLATFORM and e['watchdog']['kill_parent_at_deadline'] is True,
              'independent deadline and cleanup owner missing')
    return root,cg,docker


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,default=c.HERE/'integration/inputs.json')
    parser.add_argument('--grant-comment',required=True)
    parser.add_argument('--artifact-sha256',required=True)
    args = parser.parse_args()
    os.umask(0o077)
    # Refuse consumed/random identifiers before any resource or native operation.
    c.require(re.fullmatch(r'[0-9a-f-]{36}',args.grant_comment) and args.grant_comment not in c.CONSUMED,
              'new exact grant required')
    commit = subprocess.check_output(['git','-C',str(n.ROOT),'rev-parse','HEAD'],text=True).strip()
    c.require(not subprocess.check_output(['git','-C',str(n.ROOT),'status','--porcelain'],text=True).strip(),
              'commit exact candidate first')
    manifest = check_inputs(args.inputs)
    # Concrete prerequisite: Platform must source-freeze the outer launcher that
    # performs admission/ledger BEFORE provisioning and owns cleanup after death.
    # This candidate cannot authorize or invent that platform implementation.
    c.require(manifest.get('platform_bootstrap_sha256') is not None,
              'Platform pre-admission enclosure bootstrap is not yet frozen')
    inputs_hash = c.digest(args.inputs.read_bytes())
    comment = json.loads(api('/api/issues/'+c.ISSUE+'/comments/'+args.grant_comment))
    grant = c.grant_payload(comment,commit=commit,inputs_hash=inputs_hash,
                            artifact_hash=args.artifact_sha256,now=time.time())
    c.require(c.digest(api('/api/attachments/'+grant['artifact_attachment_id']+'/content')) == args.artifact_sha256,
              'authenticated candidate artifact readback mismatch')
    root,cg,docker = read_enclosure(grant)
    start = grant['enclosure']['attempt_started_monotonic']
    build_deadline,runtime_deadline,end = start+3600,start+4200,start+4500
    out = root/'attempt'
    public = root/'public'
    c.require(not out.exists() and not public.exists(), 'fresh attempt paths required')
    rows = c.empty_rows()
    receipt = dict(result='NOT_STARTED',launch_ready=False,grant=args.grant_comment,
                   candidate_commit=commit,inputs_sha256=inputs_hash,rows=rows,
                   exclusions={key:'NOT_RUN' for key in c.EXCLUDED})
    fd = None
    cid = None
    consumed = False
    def interrupted(signum,frame):
        raise RuntimeError('supervisor interrupted')
    for sig in (signal.SIGINT,signal.SIGHUP,signal.SIGTERM): signal.signal(sig,interrupted)
    def sample():
        c.require(time.monotonic() < runtime_deadline, 'work deadline exhausted')
        c.require(shutil.disk_usage(root.parent).free >= c.LIMITS['disk_abort_free'], 'backing disk below 4 GiB')
        counters = dict(line.split() for line in (cg/'cpu.stat').read_text().splitlines())
        c.require(int(counters['usage_usec']) <= 9000*1000000, 'aggregate CPU budget exhausted')
        events = dict(line.split() for line in (cg/'memory.events').read_text().splitlines())
        c.require(int(events['oom']) == int(events['oom_kill']) == 0, 'aggregate OOM')
        return dict(at=time.monotonic()-start,cpu=counters,memory_events=events,
                    memory_peak=int((cg/'memory.peak').read_text()),disk=shutil.disk_usage(root)._asdict())
    def supervised(argv,deadline,log):
        with log.open('wb') as stream:
            proc = subprocess.Popen(argv,stdout=stream,stderr=subprocess.STDOUT,
                env={'PATH':os.environ['PATH'],'HOME':str(out),'TMPDIR':str(out/'tmp'),
                     'PYTHONDONTWRITEBYTECODE':'1','LC_ALL':'C'})
            try:
                while proc.poll() is None:
                    c.require(time.monotonic() < deadline, 'phase deadline exhausted')
                    observed = sample()
                    with (public/'resource-samples.jsonl').open('a') as evidence:
                        evidence.write(json.dumps(observed)+'\n')
                    time.sleep(1)
                c.require(proc.returncode == 0, 'phase failed; private diagnostics retained until cleanup')
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    try: proc.wait(timeout=min(5,max(0.1,end-time.monotonic())))
                    except subprocess.TimeoutExpired: proc.kill(); proc.wait(timeout=2)
    try:
        fd = os.open(c.LOCK,os.O_RDWR|os.O_NOFOLLOW)
        c.check_lock(os.fstat(fd),os.getuid())
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        receipt['admission'] = admission(docker,manifest['builder_image'],root.parent)
        # Durable one-use ledger is outside disposable staging. Never erase it.
        ledger = c.no_alias(grant['ledger_directory'])
        c.require(ledger.stat().st_uid == os.getuid() and ledger.stat().st_mode & 0o077 == 0, 'ledger ownership')
        ledger_fd = os.open(ledger/(args.grant_comment+'.json'),os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(ledger_fd,'w') as stream:
            json.dump(dict(grant=args.grant_comment,candidate=commit,state='CONSUMED',start=start),stream)
            stream.flush(); os.fsync(stream.fileno())
        consumed = True
        out.mkdir(mode=0o700);public.mkdir(mode=0o700);(out/'tmp').mkdir()
        receipt['result'] = 'INCOMPLETE'
        source = out/'source';source.mkdir()
        pin = c.json_file(n.HERE.parent/'source-lock.json')
        # Export and Cargo copy are descendants of this already-contained controller.
        for name,revision in [('',pin['upstream']['commit']),*pin['upstream']['submodules'].items()]:
            archive = out/('source-'+(name.replace('/','-') or 'root')+'.tar')
            command(['git','-C',str(g.BASE/'monero-fcmp'/name),'archive','-o',str(archive),revision],
                    build_deadline,env={'PATH':os.environ['PATH'],'GIT_NO_LAZY_FETCH':'1'})
            target = source/name;target.mkdir(parents=True,exist_ok=True)
            command(['tar','-xf',str(archive),'-C',str(target)],build_deadline)
            archive.unlink();sample()
        overlay = policy.prepare(g.BASE/'monero-fcmp',out/'overlay',n.profile())
        c.require(overlay['overlay_id'] == manifest['reference']['overlay_sha256'], 'overlay drift')
        command(['git','apply',str(out/'overlay/selected-9-90.patch')],build_deadline,cwd=source)
        for name,sha in manifest['reference']['overlay_changed_files'].items():
            c.require(c.digest((source/name).read_bytes()) == sha, 'applied overlay drift')
        cargo = out/'cargo-home';cargo.mkdir()
        for name in ('registry','git'):
            shutil.copytree(g.BASE/'cargo-home'/name,cargo/name,symlinks=True)
            c.require(c.tree_fingerprint(cargo/name)==manifest['cargo_inputs'][name],'copied Cargo inputs differ');sample()
        shutil.copytree(c.HERE,out/'harness',ignore=shutil.ignore_patterns('evidence','__pycache__','core-review'))
        shutil.copyfile(args.inputs,out/'inputs.json')
        receipt['admission_before_create'] = admission(docker,manifest['builder_image'],root.parent)
        c.check_lock(os.stat(c.LOCK,follow_symlinks=False),os.getuid())
        image = json.loads(subprocess.check_output(docker+['image','inspect',manifest['builder_image']],text=True,timeout=10))[0]
        c.require(image['Id'] == manifest['builder_image'] and image['Architecture'] == 'amd64' and image['Os'] == 'linux','builder identity')
        create = docker+['create','--pull=never','--network=none','--read-only','--log-driver=none',
          '--cgroup-parent='+grant['enclosure']['cgroup_parent'],'--cap-drop=ALL','--security-opt=no-new-privileges',
          '--cpus=2','--memory=4g','--memory-swap=4g','--pids-limit=256','--ulimit','core=0',
          '--user',f'{os.getuid()}:{os.getgid()}','--label','meownero.task=TJS-2504',
          '--cidfile',str(out/'container.cid'),
          '--mount',f'type=bind,src={out},dst=/out',
          '--mount',f'type=bind,src={out}/tmp,dst=/tmp',
          '--mount',f'type=bind,src={public},dst=/public',
          '--mount',f'type=bind,src={g.RUST},dst=/opt/rust,readonly',
          '--env','PATH=/opt/rust/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
          '--env','CARGO_HOME=/out/cargo-home','--env','CARGO_NET_OFFLINE=true','--env','CARGO_BUILD_JOBS=1',
          '--env','HOME=/out/tmp','--env','LC_ALL=C','--env','PYTHONDONTWRITEBYTECODE=1',
          manifest['builder_image'],'bash','/out/harness/integration/build.sh']
        cid = command(create,build_deadline,capture_output=True,text=True).stdout.strip()
        c.require(re.fullmatch('[0-9a-f]{64}',cid),'exact CID')
        inspect = json.loads(subprocess.check_output(docker+['inspect',cid],text=True,timeout=10))[0]
        hc=inspect['HostConfig']
        c.require(hc['CgroupParent'] == grant['enclosure']['cgroup_parent'] and hc['NetworkMode']=='none' and
                  hc['ReadonlyRootfs'] and hc['LogConfig']['Type']=='none' and not hc['PortBindings'] and
                  hc['Memory']==hc['MemorySwap']==4*1024**3 and hc['NanoCpus']==2_000_000_000 and hc['PidsLimit']==256,
                  'created containment mismatch')
        receipt['container_id']=cid
        supervised(docker+['start','-a',cid],build_deadline,out/'build-console.log')
        state=json.loads(subprocess.check_output(docker+['inspect',cid],text=True,timeout=5))[0]['State']
        c.require(state['ExitCode']==0 and not state['OOMKilled'],'build failed or OOM')
        build=c.json_file(public/'build.json');rows['build.json']=build
        # Restart this exact container with a frozen entrypoint that dispatches by sentinel.
        (out/'BUILD_COMPLETE').write_text('runtime\n')
        c.require(time.monotonic()+600 <= runtime_deadline,'full 600s runtime allowance unavailable')
        supervised(docker+['start','-a',cid],min(time.monotonic()+600,runtime_deadline),out/'runtime-console.log')
        for name in c.REQUIRED:
            if name not in ('build.json','resources.json','cleanup.json'):
                rows[name]=c.json_file(public/name)
        sample()
        rows['resources.json']={key:dict(status='PASS') for key in c.REQUIRED['resources.json']}
    except Exception as error:
        # Exception strings may contain process output. Export the class only.
        receipt['failure_class']=type(error).__name__
        receipt['result']='FAIL' if consumed else 'REFUSED_BEFORE_ATTEMPT'
    finally:
        for sig in (signal.SIGINT,signal.SIGHUP,signal.SIGTERM): signal.signal(sig,signal.SIG_IGN)
        cleanup={key:dict(status='NOT_RUN') for key in c.REQUIRED['cleanup.json']}
        try:
            if cid is None and (out/'container.cid').exists():
                cid=(out/'container.cid').read_text().strip()
            if cid:
                c.require(re.fullmatch('[0-9a-f]{64}',cid),'cleanup CID')
                inspected=json.loads(subprocess.check_output(docker+['inspect',cid],text=True,timeout=5))[0]
                c.require(inspected['Config']['Labels'].get('meownero.task')=='TJS-2504' and
                          any(m.get('Source')==str(out) for m in inspected['Mounts']),'CID not owned')
                command(docker+['rm','-f',cid],end,capture_output=True)
                probe=subprocess.run(docker+['inspect',cid],capture_output=True,text=True,timeout=5)
                c.require(probe.returncode != 0 and 'no such' in probe.stderr.lower(),'container absence unconfirmed')
                cleanup['owned_cid_absent']=dict(status='PASS')
                # Kernel population is verified by Platform's independent watchdog too.
                c.require(not any('docker-'+cid in p.name for p in cg.rglob('*')),'container cgroup remains')
                cleanup['owned_pids_absent']=dict(status='PASS')
            if out.exists():
                shutil.rmtree(out)
                c.require(not out.exists(),'staging removal failed')
                cleanup['owned_staging_removed']=dict(status='PASS')
        except Exception as error:
            receipt['cleanup_failure_class']=type(error).__name__
            receipt['result']='FAIL'
        finally:
            if fd is not None:
                os.close(fd)
                # Independent open plus nonblocking flock proves release, while retaining original inode.
                probe=os.open(c.LOCK,os.O_RDWR|os.O_NOFOLLOW)
                try:
                    c.check_lock(os.fstat(probe),os.getuid());fcntl.flock(probe,fcntl.LOCK_EX|fcntl.LOCK_NB)
                    cleanup['lock_released']=dict(status='PASS')
                finally: os.close(probe)
        rows['cleanup.json']=cleanup
        receipt['wall_seconds']=time.monotonic()-start
        if receipt['result']=='INCOMPLETE': receipt['result']=c.verdict(rows)
        if public.exists():
            for name,data in rows.items(): n.write_json(public/name,data)
            n.write_json(public/'receipt.json',receipt)
        print(json.dumps(dict(result=receipt['result'],launch_ready=False,consumed=consumed)))
    return 0 if receipt['result'].startswith('PASS_') else (3 if not consumed else 124 if time.monotonic()>=runtime_deadline else 1)


if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as error:
        print('REFUSED: '+type(error).__name__,file=sys.stderr)
        raise SystemExit(3)
