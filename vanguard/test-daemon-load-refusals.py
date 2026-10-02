#!/usr/bin/env python3
"""Hash-consistent load receipt controls; never edits the source bundle."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
VERIFIER = ROOT / 'vanguard/verify-daemon-load.py'


def manifest(out):
    (out / 'MANIFEST.sha256').write_text(''.join(
        f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(out)}\n'
        for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'MANIFEST.sha256'))


def check(out, src):
    return subprocess.run(['python3', '-B', str(VERIFIER), str(out), '--src', str(src)],
                          capture_output=True, text=True)


def copy_public(source, target):
    target.mkdir()
    for line in (source / 'MANIFEST.sha256').read_text().splitlines():
        _, relative = line.split('  ', 1)
        dest = target / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / relative, dest)
    shutil.copy2(source / 'MANIFEST.sha256', target / 'MANIFEST.sha256')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out', type=Path)
    parser.add_argument('--src', type=Path, required=True)
    parser.add_argument('--scratch', type=Path, required=True)
    args = parser.parse_args()
    source, src = args.out.resolve(), args.src.resolve()
    args.scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='vanguard-load-refusals-', dir=args.scratch) as temp:
        base = Path(temp)
        clean = check(source, src)
        assert clean.returncode == 0, clean.stderr

        forged_binary = base / 'forged-src/monero-fcmp/build/vanguard/bin'
        forged_binary.mkdir(parents=True)
        (forged_binary / 'monerod').write_bytes(b'wrong executable')
        shutil.copy2(src / 'monero-fcmp/build/vanguard/bin/monero-wallet-rpc',
                     forged_binary / 'monero-wallet-rpc')
        invalid = check(source, base / 'forged-src')
        assert invalid.returncode != 0 and 'local executable bytes: monerod' in invalid.stderr
        print('REFUSED wrong executable bytes: local executable bytes: monerod')

        tampered = base / 'invalid-proof-response'
        copy_public(source, tampered)
        result_path = tampered / 'run1/public/result.json'
        result = json.loads(result_path.read_text())
        result['controls']['invalid_proof']['responses'][0]['status'] = 'OK'
        result_path.write_text(json.dumps(result, indent=2) + '\n')
        manifest(tampered)
        invalid = check(tampered, src)
        assert invalid.returncode != 0 and 'invalid_proof refusal' in invalid.stderr
        print('REFUSED hash-consistent invalid-proof acceptance: invalid_proof refusal')

        def refuse(name, label, mutate):
            tampered = base / name
            copy_public(source, tampered)
            result_path = tampered / 'run1/public/result.json'
            event_path = tampered / 'run1/public/events.jsonl'
            receipt_path = tampered / 'receipt.json'
            result = json.loads(result_path.read_text())
            events = [json.loads(line) for line in event_path.read_text().splitlines()]
            receipt = json.loads(receipt_path.read_text())
            mutate(result, events, receipt)
            result_path.write_text(json.dumps(result, indent=2) + '\n')
            event_path.write_text(''.join(json.dumps(row) + '\n' for row in events))
            receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
            manifest(tampered)
            invalid = check(tampered, src)
            assert invalid.returncode != 0 and label in invalid.stderr, (name, invalid.stderr)
            print(f'REFUSED {name}: {label}')

        # Each immutable output field must survive receipt reconciliation at
        # both restore and post-spend checkpoints, even with a valid manifest.
        for checkpoint in ('original', 'post-spend'):
            for field, wrong in (('key_image', '0' * 64), ('tx_hash', '0' * 64),
                                 ('pubkey', '0' * 64), ('amount', 1), ('block_height', 999)):
                def mutate(result, events, receipt):
                    wallet = (result['restore']['original'] if checkpoint == 'original'
                              else result['restored_spend']['wallet'])
                    wallet['outputs'][0][field] = wrong
                refuse(f'{checkpoint}-output-{field}', 'restore output identity reconciliation', mutate)

        refuse('spent-input-absent-from-original', 'restored spend original key image',
               lambda result, events, receipt:
               result['restored_spend'].update(key_image='0' * 64))

        for name, field, wrong, label in (
                ('duplicate-unrelated-input', 'key_image', '0' * 64,
                 'duplicate key image input identity'),
                ('duplicate-same-candidate', 'alternate_txid', None,
                 'duplicate key image distinct candidate')):
            def mutate(result, events, receipt):
                duplicate = result['controls']['duplicate_key_image']
                value = wrong if wrong is not None else duplicate['confirmed_txid']
                duplicate[field] = value
                next(row for row in events if row['event'] ==
                     'duplicate_key_image_refused')[field] = value
            refuse(name, label, mutate)
        refuse('duplicate-event-unrelated-input', 'duplicate key image event/result mismatch',
               lambda result, events, receipt:
               next(row for row in events if row['event'] ==
                    'duplicate_key_image_refused').update(key_image='0' * 64))

        for field, wrong in (('upstream_commit', '0' * 40), ('rustc', 'wrong toolchain'),
                             ('builder_image', 'bash')):
            refuse('receipt-' + field, 'receipt lineage: ' + field,
                   lambda result, events, receipt: receipt.update({field: wrong}))
        refuse('wrong-selected-image', 'build selected builder image',
               lambda result, events, receipt: receipt['commands'][0].__setitem__(35, 'bash'))

        # Mutations are command data only. Test each stage separately so a bad
        # trial cannot hide behind a correctly contained build command.
        for index, stage in enumerate(('build', 'run1', 'run2')):
            for option in ('--privileged', '--cap-add=SYS_ADMIN', '--network=host',
                           '--cpus=8', '--memory=8g', '--memory-swap=8g',
                           '--pids-limit=-1', '--security-opt=seccomp=unconfined'):
                refuse(f'{stage}-{option[2:]}', f'{stage} container containment',
                       lambda result, events, receipt: receipt['commands'][index].insert(5, option))

        # This intentionally demonstrates the post-run authenticity limit.
        tampered = base / 'equal-wrong-tips'
        copy_public(source, tampered)
        result_path = tampered / 'run1/public/result.json'
        event_path = tampered / 'run1/public/events.jsonl'
        result = json.loads(result_path.read_text())
        wrong = list(result['baseline']['tips'][0])
        wrong[1] = '0' * 64 if wrong[1] != '0' * 64 else '1' * 64
        result['baseline']['tips'] = [wrong, list(wrong)]
        result_path.write_text(json.dumps(result, indent=2) + '\n')
        rows = [json.loads(line) for line in event_path.read_text().splitlines()]
        next(row for row in rows if row['event'] == 'idle_baseline')['metric'] = result['baseline']
        event_path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        manifest(tampered)
        unverified = check(tampered, src)
        assert unverified.returncode == 0 and 'UNVERIFIED_LIVE_TIPS' in unverified.stdout
        print('UNVERIFIED hash-consistent equal-wrong idle tips pass receipt checks')


if __name__ == '__main__':
    main()
