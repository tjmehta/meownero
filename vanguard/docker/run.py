#!/usr/bin/env python3
"""Launch one fresh offline disposable tester and remove its exact container."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time
import uuid

from docker_support import cleanup_named, cleanup_signals, proof, query, save as save_receipt


def docker(*argv):
    return query(*argv, timeout=120 if argv[0] == 'stop' else 30)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True, help='Exact locally built sha256 image ID')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--deadline-seconds', type=int, default=1200)
    parser.add_argument('--interrupt-after', type=int, help='Verification only: TERM after a live native child exists')
    args = parser.parse_args()
    assert 1 <= args.deadline_seconds <= 1200 and (args.interrupt_after is None or 1 <= args.interrupt_after <= 120)
    assert args.image.startswith('sha256:') and len(args.image) == 71
    image = json.loads(docker('image', 'inspect', args.image))[0]
    assert image['Id'] == args.image and image['Architecture'] == 'amd64' and image['Os'] == 'linux'
    out = args.out.absolute()
    assert out.parent.is_dir() and not out.exists() and not any(p.is_symlink() for p in (out, *out.parents))
    assert os.getuid() != 0 and shutil.disk_usage(out.parent).free >= 5 * 1024**3
    out.mkdir(mode=0o700)
    invocation = uuid.uuid4().hex
    name = 'meownero-tjs1882-runtime-' + invocation
    receipt = {'schema': 'meownero-docker-runtime-attempt/1', 'image': args.image,
               'invocation': invocation, 'result': 'INCOMPLETE', 'cleanup': {'removed': False}}
    cid = None
    def save():
        save_receipt(out / 'runtime.json', receipt)
    def owned():
        return proof(cid, 'meownero.invocation', invocation, name=name, image=args.image)
    def cancelled(signum, frame):
        # Cleanup recovers by exact UUID name even if create never returned a CID.
        raise KeyboardInterrupt('owned runtime interrupted')
    previous = {s: signal.signal(s, cancelled) for s in (signal.SIGTERM, signal.SIGINT)}
    try:
        save()
        cid = docker('create', '--name', name, '--label', 'meownero.invocation=' + invocation,
            '--pull=never', '--network=none', '--read-only', '--cpus=2', '--memory=2g', '--memory-swap=2g',
            '--pids-limit=256', '--cap-drop=ALL', '--security-opt=no-new-privileges', '--ulimit', 'core=0',
            '--stop-timeout=90', '--user', f'{os.getuid()}:{os.getgid()}',
            '--tmpfs', '/state:rw,nosuid,nodev,noexec,size=1g,mode=1777',
            '--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=64m,mode=1777',
            '--mount', f'type=bind,src={out},dst=/output', args.image,
            '--deadline-seconds', str(args.deadline_seconds))
        proof = owned()
        receipt['cid'] = cid
        receipt['policy'] = {k: proof['HostConfig'][k] for k in ('NetworkMode', 'ReadonlyRootfs', 'Memory', 'MemorySwap', 'NanoCpus', 'PidsLimit', 'CapDrop', 'SecurityOpt', 'Tmpfs')}
        assert receipt['policy']['NetworkMode'] == 'none' and receipt['policy']['ReadonlyRootfs']
        save()
        docker('start', cid)
        began = time.monotonic()
        if args.interrupt_after is not None:
            # Only scalar live-child evidence leaves the private tmpfs.
            code = "from pathlib import Path; names={'monerod','monero-wallet-cli','monero-wallet-rpc'}; print(sum(p.resolve().name in names for p in Path('/proc').glob('[0-9]*/exe') if p.exists()))"
            live = False
            while time.monotonic() - began < 120 and owned()['State']['Running']:
                if int(docker('exec', cid, 'python3', '-c', code)) > 0:
                    live = True
                    break
                time.sleep(1)
            assert live, 'signal fixture never reached live native state'
            time.sleep(args.interrupt_after)
            assert owned()['State']['Running'], 'signal fixture exited before interruption'
            receipt['live_native_children_at_signal'] = int(docker('exec', cid, 'python3', '-c', code))
            assert receipt['live_native_children_at_signal'] > 0
            receipt['interrupted_live_fixture'] = True
            docker('stop', '--time', '90', cid)
        while owned()['State']['Running'] and time.monotonic() - began < args.deadline_seconds + 180:
            time.sleep(2)
        proof = owned()
        if proof['State']['Running']:
            docker('stop', '--time', '90', cid)
            proof = owned()
        receipt.update(exit=proof['State']['ExitCode'], oom_killed=proof['State']['OOMKilled'],
                       wall_seconds=time.monotonic() - began)
        public = out / 'result.json'
        assert public.is_file() and not public.is_symlink() and public.stat().st_nlink == 1 and public.stat().st_size < 256 * 1024
        receipt['public_result_sha256'] = hashlib.sha256(public.read_bytes()).hexdigest()
        result = json.loads(public.read_text())
        receipt['result'] = result['result']
        if args.interrupt_after is None and args.deadline_seconds == 1200:
            assert receipt['exit'] == 0 and result['result'] == 'PASS_NATIVE_JOURNEY'
        else:
            assert receipt['exit'] != 0 and result['result'] == 'FAIL_NATIVE_JOURNEY'
            assert result['journey']['cleanup'] and all(row['removed'] for row in result['journey']['cleanup'])
    except BaseException as error:
        receipt.update(result='FAILED_RUNTIME_ATTEMPT', failure_type=type(error).__name__)
        raise
    finally:
        try:
            with cleanup_signals():
                try:
                    receipt['cleanup'] = cleanup_named(name, args.image, invocation)
                    if not receipt['cleanup']['removed']:
                        receipt['result'] = 'UNRESOLVED_RUNTIME_CLEANUP'
                finally:
                    save()
        finally:
            for s, handler in previous.items():
                signal.signal(s, handler)
    assert receipt['cleanup']['removed'], 'owned runtime cleanup unresolved; receipt retained'
    print(receipt['result'], flush=True)


if __name__ == '__main__':
    main()
