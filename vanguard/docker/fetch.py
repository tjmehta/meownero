"""Fetch verified public inputs; never read a host cache or credentials."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request

ROOT = Path('/recipe')
BUILD = Path('/build')


def command(argv, cwd=None):
    return subprocess.check_output(argv, cwd=cwd, text=True, timeout=900).strip()


def download(url, path, digest):
    with urllib.request.urlopen(url, timeout=120) as response, path.open('xb') as output:
        shutil.copyfileobj(response, output)
    assert hashlib.file_digest(path.open('rb'), 'sha256').hexdigest() == digest, 'download checksum mismatch'


def main():
    pin = json.loads((ROOT / 'vanguard/source-lock.json').read_text())
    inputs = json.loads((ROOT / 'vanguard/docker/inputs.json').read_text())
    assert command(['dpkg', '--print-architecture']) == inputs['architecture'] == 'amd64', 'native x64 required'
    assert inputs['upstream_commit'] == pin['upstream']['commit']
    BUILD.mkdir()
    source = BUILD / 'monero-fcmp'
    command(['git', 'init', str(source)])
    command(['git', '-C', str(source), 'remote', 'add', 'origin', pin['upstream']['url']])
    command(['git', '-C', str(source), 'fetch', '--depth=1', 'origin', pin['upstream']['commit']])
    command(['git', '-C', str(source), 'checkout', '--detach', pin['upstream']['commit']])
    for relative, revision in pin['upstream']['submodules'].items():
        assert command(['git', '-C', str(source), 'ls-tree', 'HEAD', relative]).split()[2] == revision
        repository = source / relative
        command(['git', 'init', str(repository)])
        command(['git', '-C', str(repository), 'remote', 'add', 'origin', inputs['submodule_urls'][relative]])
        command(['git', '-C', str(repository), 'fetch', '--depth=1', 'origin', revision])
        command(['git', '-C', str(repository), 'checkout', '--detach', revision])
        assert command(['git', '-C', str(repository), 'rev-parse', 'HEAD']) == revision
    assert hashlib.sha256((source / pin['rust']['cargo_lock_path']).read_bytes()).hexdigest() == inputs['cargo_lock_sha256'] == pin['rust']['cargo_lock_sha256']
    for dotgit in sorted(source.rglob('.git'), reverse=True):
        if dotgit.is_dir():
            shutil.rmtree(dotgit)
        else:
            dotgit.unlink()
    archive = BUILD / 'rust.tar.xz'
    download(inputs['rust']['url'], archive, inputs['rust']['sha256'])
    with tarfile.open(archive) as stream:
        stream.extractall(BUILD / 'rust-install', filter='data')
    installer = next((BUILD / 'rust-install').glob('*/install.sh'))
    command(['sh', str(installer), '--prefix=/build/rust', '--disable-ldconfig', '--without=rust-docs'])
    assert command(['/build/rust/bin/rustc', '-V']) == pin['builder']['rustc']
    archive.unlink()
    shutil.rmtree(BUILD / 'rust-install')
    depends = source / 'contrib/depends'
    (depends / 'sources').mkdir(exist_ok=True)
    for name, row in inputs['depends'].items():
        assert hashlib.sha256((depends / 'packages' / (name + '.mk')).read_bytes()).hexdigest() == row['recipe_sha256']
        download(row['url'], depends / 'sources' / row['file'], row['sha256'])
    import os
    os.environ.update(CARGO_HOME='/build/cargo-home', PATH='/build/rust/bin:' + os.environ['PATH'])
    command(['cargo', 'fetch', '--locked', '--manifest-path', str(source / 'src/fcmp_pp/fcmp_pp_rust/Cargo.toml')])
    (BUILD / 'inputs.json').write_text(json.dumps(inputs, indent=2) + '\n')


if __name__ == '__main__':
    main()
