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
import profile_dispatch as dispatcher

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


def read_enclosure(value):
    # The privileged daemon and its socket are never exposed to this uid1000
    # controller. Host/mount/descendant observations belong to the helper.
    e=value['enclosure']
    c.require(os.getuid()==os.getgid()==1000, 'task controller uid/gid1000')
    root=c.no_alias(e['work_directory'])
    info=root.stat()
    c.require(info.st_uid==info.st_gid==1000 and info.st_mode & 0o777==0o700 and
        [info.st_dev,info.st_ino]==e['work_directory_identity'], 'owned writable user directory')
    cg=Path('/sys/fs/cgroup'+e['workload_cgroup'])
    c.require(group('self').startswith(e['workload_cgroup']+'/'), 'controller work placement')
    c.require('docker_socket' not in e and 'docker_pid_identity' not in e, 'private helper boundary')
    return root,cg


def controller_create(helper, staging_sha256, *, deadline):
    """The only create path: authenticated helper observes AND creates atomically."""
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,default=c.HERE/'integration/inputs.json')
    parser.add_argument('--grant-comment',required=True)
    parser.add_argument('--artifact-sha256',required=True)
    parser.add_argument('--context-fd',type=int)
    parser.add_argument('--lock-fd',type=int)
    parser.add_argument('--ledger-fd',type=int)
    parser.add_argument('--helper-fd',type=int)
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
    c.require(type(args.helper_fd) is int and args.helper_fd>2 and args.helper_fd not in
        (args.context_fd,args.lock_fd,args.ledger_fd), 'distinct inherited helper channel')
    import socket
    endpoint=socket.socket(fileno=args.helper_fd)
    peer=context['helper']['credentials']
    def check_helper():c.stop_identity(context['helper']['pid_identity'],pid_identity(peer[0]))
    helper=dispatcher.Client(endpoint,peer,context['helper']['contract'],check_peer=check_helper)
    root,cg = read_enclosure(context)
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
        # The independent helper enforces backing admission/abort and all aggregate limits.
        counters = dict(line.split() for line in (cg/'cpu.stat').read_text().splitlines())
        c.require(int(counters['usage_usec']) <= 9000*1000000, 'aggregate CPU budget exhausted')
        events = dict(line.split() for line in (cg/'memory.events').read_text().splitlines())
        c.require(int(events['oom']) == int(events['oom_kill']) == 0, 'aggregate OOM')
        return dict(at=time.monotonic()-start,cpu=counters,memory_events=events,
                    memory_peak=int((cg/'memory.peak').read_text()),disk=shutil.disk_usage(root)._asdict())
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
        helper.request('inspect_image',{},deadline=build_deadline)
        staged=c.digest(c.canonical(c.tree_fingerprint(out)))
        created=controller_create(helper,staged,deadline=build_deadline)
        receipt['atomic_create']=created
        cid=created['container_id']
        receipt['container_id']=cid
        state=helper.start_and_wait(cid,'build',deadline=build_deadline)
        c.require(state['exit_code']==0 and state['oom_killed'] is False, 'build failed or OOM')
        build=c.json_file(public/'build.json');rows['build.json']=build
        # Restart this exact container with a frozen entrypoint that dispatches by sentinel.
        (out/'BUILD_COMPLETE').write_text('runtime\n')
        c.require(time.monotonic()+600 <= runtime_deadline,'full 600s runtime allowance unavailable')
        state=helper.start_and_wait(cid,'runtime',deadline=min(time.monotonic()+600,runtime_deadline))
        c.require(state['exit_code']==0 and state['oom_killed'] is False, 'runtime failed or OOM')
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
            if cid:
                # Unknown or late create outcomes remain in the root helper's
                # durable ownership journal even if no CID reply reached us.
                removed=helper.remove_owned(cid,deadline=end)
                c.require(removed['absent'] is True, 'owned CID absence unconfirmed')
                cleanup['owned_cid_absent']=dict(status='PASS')
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
