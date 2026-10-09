#!/usr/bin/env python3
"""Meaningful admission/export controls. Native proof requires a separate rehearsal."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('tester', Path(__file__).with_name('tester.py'))
tester = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tester)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--public', type=Path)
    p.add_argument('--src', type=Path, default=Path(tester.PROFILE['cache']))
    args = p.parse_args()
    work = tester.fresh(args.work)
    work.mkdir(mode=0o700)
    results = []

    def refuse(label, action, expected):
        try:
            action()
        except Exception as error:
            tester.require(expected in str(error), label + ': wrong refusal ' + str(error))
            results.append({'control': label, 'result': 'PASS_REFUSAL', 'reason': str(error)})
        else:
            raise RuntimeError(label + ': accepted forbidden input')

    with patch.object(tester.platform, 'machine', return_value='unsupported'):
        refuse('unsupported architecture', tester.supported_host, 'unsupported profile')
    existing = work / 'existing'
    existing.mkdir()
    (existing / 'sentinel').write_text('preserve me\n')
    refuse('existing output', lambda: tester.fresh(existing), 'existing output')
    tester.require((existing / 'sentinel').read_text() == 'preserve me\n', 'existing output mutated')
    bad = work / 'bad-cache'
    (bad / 'preparation').mkdir(parents=True)
    (bad / 'preparation/receipt.json').write_text('{}\n')
    refuse('wrong preparation pin', lambda: tester.cached_inputs(bad), 'preparation pin mismatch')
    if tester.platform.system() == 'Darwin':
        tester.supported_host()
        baseline = tester.cached_inputs(args.src)
        tester.require(baseline == tester.PROFILE['binary'], 'accepted cache baseline')
        original = tester.sha
        binary_path = args.src / 'monero-fcmp/build/vanguard/bin/monerod'
        # Inject only the hash observation. Accepted cache bytes stay read-only.
        with patch.object(tester, 'sha', side_effect=lambda path: '0' * 64 if path == binary_path else original(path)):
            refuse('wrong executable hash', lambda: tester.cached_inputs(args.src), 'binary pin mismatch')
    else:
        results.append({'control': 'real cache baseline/wrong executable hash', 'result': 'NOT_RUN', 'reason': 'requires build-mac'})
    # A distinct process owns the real shared lock while admission must refuse it.
    lock_script = 'import fcntl,sys; f=open(sys.argv[1],"rb"); fcntl.flock(f,fcntl.LOCK_EX); print("HELD",flush=True); sys.stdin.read()'
    if tester.LOCK.exists():
        proc = subprocess.Popen([sys.executable, '-c', lock_script, str(tester.LOCK)],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        try:
            tester.require(proc.stdout.readline().strip() == 'HELD', 'control lock not acquired')
            def acquire():
                with tester.heavy_lock():
                    pass
            refuse('busy shared heavy lock', acquire, 'heavy lock busy')
        finally:
            proc.stdin.close()
            proc.wait(timeout=10)
    else:
        results.append({'control': 'busy shared heavy lock', 'result': 'NOT_RUN', 'reason': 'shared lock absent'})
    evil = work / 'allowed.json'
    evil.write_text(json.dumps({'seed': 'DO_NOT_EXPORT'}))
    refuse('seed-bearing JSON', lambda: tester.public_bytes(evil, 'result.json'), 'secret-bearing')
    evil.write_text(json.dumps({'authorization': 'DO_NOT_EXPORT'}))
    refuse('credential-bearing JSON', lambda: tester.public_bytes(evil, 'result.json'), 'secret-bearing')
    evil.write_bytes(b'\x00wallet database\xff')
    refuse('database renamed JSON', lambda: tester.public_bytes(evil, 'result.json'), '')
    refuse('database renamed frame', lambda: tester.public_bytes(evil, 'frames/malformed-block.bin'), 'non-Levin')
    fifo = work / 'fifo'
    import os
    os.mkfifo(fifo)
    refuse('FIFO', lambda: tester.public_bytes(fifo, 'result.json'), 'regular file required')
    link = work / 'symlink'
    link.symlink_to(evil)
    refuse('allowed-name symlink', lambda: tester.public_bytes(link, 'result.json'), 'symlink')
    hard = work / 'hardlink'
    os.link(evil, hard)
    refuse('hard link', lambda: tester.public_bytes(hard, 'result.json'), 'hard-linked')
    hard.unlink()
    evil.write_text('arbitrary credential text\nFailed to parse block from blob\n')
    tester.require(tester.public_bytes(evil, 'daemon1.log') == b'Failed to parse block from blob\n', 'raw log payload exported')
    results.append({'control': 'free-form log payload excluded', 'result': 'PASS'})
    if args.public:
        import shutil
        tester.verify(args.public)
        public_copy = work / 'public-copy'
        shutil.copytree(args.public, public_copy)
        extra = public_copy / '.shared-ringdb'
        extra.mkdir()
        refuse('extra empty ring directory', lambda: tester.validate_public(public_copy), 'unlisted export directory')
        extra.rmdir()
        extra = public_copy / 'wallet.keys'
        extra.write_text('DO_NOT_EXPORT')
        refuse('unlisted private file', lambda: tester.validate_public(public_copy), 'unlisted export file')
        extra.unlink()
        inputs = public_copy / 'inputs.json'
        raw = inputs.read_bytes()
        inputs.unlink(); inputs.symlink_to(args.public.resolve() / 'inputs.json')
        refuse('public member symlink', lambda: tester.validate_public(public_copy), 'symlink')
        inputs.unlink(); inputs.write_bytes(raw)
        # Export only a known allowlist; an arbitrary unlisted file remains excluded.
        private_source = work / 'export-source'
        shutil.copytree(args.public, private_source)
        (private_source / 'export.json').unlink()
        tester.manifest(private_source, tester.PUBLIC, 'EVIDENCE.sha256')
        (private_source / 'seed.txt').write_text('DO_NOT_EXPORT')
        tester.export(private_source, work / 'export', work / 'export.tar.gz')
        tester.require(not (work / 'export/seed.txt').exists(), 'unlisted seed exported')
        results.append({'control': 'unlisted input excluded from export', 'result': 'PASS'})
    tester.write(work / 'controls.json', results)
    print('PASS_TESTER_REFUSALS', sum(row['result'].startswith('PASS') for row in results),
          'NOT_RUN', sum(row['result'] == 'NOT_RUN' for row in results))


if __name__ == '__main__':
    main()
