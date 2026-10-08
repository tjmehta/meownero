"""The frozen soak protocol exports text receipts, never wallet or chain state."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

PREPARATION_LOGS = ('build', 'cargo-fetch', 'checkout', 'clone', 'configure',
                    'container-baseline', 'image', 'native-versions', 'rust-install',
                    'rust-version', 'submodules', 'vm-memory')
PUBLIC_FILES = frozenset(
    ['receipt.json', 'source-lock.json', 'preparation/receipt.json'] +
    ['preparation/build.' + suffix for suffix in ('cpu', 'memory', 'memory-events')] +
    [f'preparation/{label}.{stream}.log' for label in PREPARATION_LOGS for stream in ('stdout', 'stderr')] +
    [f'run{trial}/{name}' for trial in (1, 2) for name in (
        'container-live.jsonl', 'docker.exit', 'docker.stderr.log', 'docker.stdout.log',
        'final.cpu', 'final.memory', 'final.memory-events', 'vm-memory-before.txt',
        'public/events.jsonl', 'public/result.json', 'public/rpc.jsonl',
        'public/samples.jsonl', 'public/wire.jsonl')])
PUBLIC_DIRS = {str(parent) for name in PUBLIC_FILES for parent in Path(name).parents if str(parent) != '.'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def public_text(path):
    # Every permitted receipt/log is UTF-8 text. This also rejects renamed LMDB,
    # wallet caches and keys placed under a permitted receipt filename.
    raw = path.read_bytes()
    if b'\0' in raw:
        raise AssertionError('binary/database public evidence: ' + str(path))
    try:
        raw.decode('utf-8')
    except UnicodeDecodeError as error:
        raise AssertionError('non-text public evidence: ' + str(path)) from error


def validate_public_tree(out):
    files = set()
    for path in out.rglob('*'):
        name = str(path.relative_to(out))
        if path.is_symlink():
            raise AssertionError('symlink public evidence: ' + name)
        if path.is_dir():
            if name not in PUBLIC_DIRS:
                raise AssertionError('non-public evidence directory: ' + name)
        elif path.is_file():
            if name not in PUBLIC_FILES | {'MANIFEST.sha256'}:
                raise AssertionError('non-public evidence file: ' + name)
            public_text(path)
            files.add(name)
        else:
            raise AssertionError('non-regular public evidence: ' + name)
    if files != PUBLIC_FILES | {'MANIFEST.sha256'}:
        raise AssertionError('incomplete public evidence set')


def export(source, out):
    if source == out or source in out.parents:
        raise AssertionError('export must be outside original evidence')
    original = {}
    for line in (source / 'MANIFEST.sha256').read_text().splitlines():
        value, name = line.split('  ', 1)
        path = Path(name)
        if path.is_absolute() or '..' in path.parts or name in original:
            raise AssertionError('unsafe original manifest')
        original[name] = value
    if not PUBLIC_FILES <= original.keys():
        raise AssertionError('original manifest missing public evidence')
    out.mkdir(parents=True, exist_ok=False)
    retained = {}
    for name in sorted(PUBLIC_FILES):
        path = source / name
        if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
            raise AssertionError('non-regular original evidence: ' + name)
        public_text(path)
        if digest(path) != original[name]:
            raise AssertionError('original raw evidence changed: ' + name)
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        retained[name] = digest(target)
        if retained[name] != original[name]:
            raise AssertionError('export copy changed: ' + name)
    (out / 'MANIFEST.sha256').write_text(''.join(f'{value}  {name}\n' for name, value in retained.items()))
    validate_public_tree(out)
    return {'result': 'PASS_DATABASE_FREE_PUBLIC_EXPORT',
            'original_manifest_sha256': digest(source / 'MANIFEST.sha256'),
            'public_manifest_sha256': digest(out / 'MANIFEST.sha256'),
            'retained_files': len(retained), 'retained_raw_bytes_unchanged': True,
            'excluded_original_manifest_entries': sorted(original.keys() - PUBLIC_FILES),
            'retained_sha256': retained}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--archive', type=Path, required=True)
    args = parser.parse_args()
    source, out = args.source.resolve(), args.out.resolve()
    result = export(source, out)
    # Deterministic regular-file archive; no recursive directory discovery.
    with args.archive.open('xb') as raw, gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode='w') as archive:
            for name in sorted(PUBLIC_FILES | {'MANIFEST.sha256'}):
                path = out / name
                info = tarfile.TarInfo(name)
                info.size, info.mode, info.mtime = path.stat().st_size, 0o644, 0
                with path.open('rb') as stream:
                    archive.addfile(info, stream)
    result['archive_sha256'] = digest(args.archive)
    result['archive_bytes'] = args.archive.stat().st_size
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
