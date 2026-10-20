#!/usr/bin/env python3
"""One future grant-bound production build and genesis-only attempt.

No resource provisioning or implicit grant. No qualified outer implementation is
supplied. The source-frozen handoff is conditional and this entry point refuses
even a manually populated bootstrap hash until a reviewed implementation exists.
"""
import argparse
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
import profile_handoff as handoff

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
    # The prior shared-socket observer cannot perform an enclosed second admission.
    # The qualified outer must supply the exact live collision/admission channel.
    raise ValueError('qualified second-admission channel is not supplied')


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
    c.require({'cpu','memory','pids'} <= set((cg/'cgroup.controllers').read_text().split()) and
              {'cpu','memory','pids'} <= set((cg/'cgroup.subtree_control').read_text().split()),
              'aggregate controllers not active')
    work = Path('/sys/fs/cgroup' + e['workload_cgroup'])
    recovery = value['recovery']['pid_identity']
    c.stop_identity(recovery,pid_identity(recovery[0]))
    c.require(group(recovery[0]).startswith(parent+'/recovery/') and
              group('self').startswith(e['workload_cgroup']+'/') and
              group(daemon[0]).startswith(e['workload_cgroup']+'/'), 'recovery/work placement')
    c.require((work/'memory.oom.group').read_text().strip() == '1', 'workload OOM grouping')
    # Daemon/containerd/shims, mount topology, recovery immunity and image import
    # still require a qualified outer implementation and its authoritative receipt.
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
    parser.add_argument('--context-fd',type=int)
    parser.add_argument('--lock-fd',type=int)
    parser.add_argument('--ledger-fd',type=int)
    args = parser.parse_args()
    os.umask(0o077)
    # Refuse consumed/random identifiers before any resource or native operation.
    c.require(re.fullmatch(r'[0-9a-f-]{36}',args.grant_comment) and args.grant_comment not in c.CONSUMED,
              'new exact grant required')
    commit = subprocess.check_output(['git','-C',str(n.ROOT),'rev-parse','HEAD'],text=True).strip()
    c.require(not subprocess.check_output(['git','-C',str(n.ROOT),'status','--porcelain'],text=True).strip(),
              'commit exact candidate first')
    manifest = check_inputs(args.inputs)
    # No source-table entry exists. JSON/hash edits cannot enable native work.
    handoff.require_bootstrap(manifest)
    inputs_hash = c.digest(args.inputs.read_bytes())
    comment = json.loads(api('/api/issues/'+c.ISSUE+'/comments/'+args.grant_comment))
    grant = c.grant_payload(comment,commit=commit,inputs_hash=inputs_hash,
                            artifact_hash=args.artifact_sha256,bootstrap_hash=manifest['platform_bootstrap_sha256'],now=time.time())
    c.require(c.digest(api('/api/attachments/'+grant['artifact_attachment_id']+'/content')) == args.artifact_sha256,
              'authenticated candidate artifact readback mismatch')
    context = handoff.read_inherited(args.context_fd,args.lock_fd,args.ledger_fd,
        bindings=dict(grant_id=args.grant_comment,grant_sha256=c.digest(c.canonical(grant)),
                      candidate_commit=commit,inputs_sha256=inputs_hash,
                      artifact_sha256=args.artifact_sha256,bootstrap_sha256=manifest['platform_bootstrap_sha256']),
        now=time.monotonic(),identity=pid_identity)
    root,cg,docker = read_enclosure(context)
    start = context['origin']
    build_deadline,runtime_deadline,end = start+3600,start+4200,start+4500
    out = root/'attempt'
    public = root/'public'
    c.require(not out.exists() and not public.exists(), 'fresh attempt paths required')
    rows = c.empty_rows()
    receipt = dict(result='NOT_STARTED',launch_ready=False,grant=args.grant_comment,
                   candidate_commit=commit,inputs_sha256=inputs_hash,rows=rows,
                   exclusions={key:'NOT_RUN' for key in c.EXCLUDED})
    cid = None
    consumed = True  # Existing durable receipt; never consume again here.
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
        receipt['admission'] = context['first_admission']
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
          '--cgroup-parent='+context['enclosure']['workload_cgroup'],'--cap-drop=ALL','--security-opt=no-new-privileges',
          '--cpus=2','--memory=3840m','--memory-swap=3840m','--pids-limit=224','--ulimit','core=0',
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
        c.require(hc['CgroupParent'] == context['enclosure']['workload_cgroup'] and hc['NetworkMode']=='none' and
                  hc['ReadonlyRootfs'] and hc['LogConfig']['Type']=='none' and not hc['PortBindings'] and
                  hc['Memory']==hc['MemorySwap']==3840*1024**2 and hc['NanoCpus']==2_000_000_000 and hc['PidsLimit']==224,
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
        # Samples are provisional; only the outer can finalize aggregate status.
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
                # CID absence alone says nothing about daemon/helper/PID absence.
            # The outer preserves allowlisted evidence, then removes private staging,
            # daemon/helpers, filesystem and backing image within the cleanup reserve.
        except Exception as error:
            receipt['cleanup_failure_class']=type(error).__name__
            receipt['result']='FAIL'
        # Closing the inner copy never releases the supervisor's retained copy.
        # Never call LOCK_UN or probe acquisition while the outer still holds it.
        os.close(args.lock_fd)
        rows = handoff.inner_rows(rows)
        receipt['outer_completion'] = 'NOT_RUN'
        receipt['provisional_cid_cleanup'] = cleanup
        receipt['wall_seconds']=time.monotonic()-start
        if receipt['result']=='INCOMPLETE': receipt['result']='PENDING_OUTER_COMPLETION'
        if public.exists():
            for name,data in rows.items(): n.write_json(public/name,data)
            n.write_json(public/'receipt.json',receipt)
        print(json.dumps(dict(result=receipt['result'],launch_ready=False,consumed=consumed)))
    return 0 if receipt['result']=='PENDING_OUTER_COMPLETION' else (124 if time.monotonic()>=runtime_deadline else 1)


if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as error:
        print('REFUSED: '+type(error).__name__,file=sys.stderr)
        raise SystemExit(3)
