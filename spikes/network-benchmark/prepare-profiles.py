#!/usr/bin/env python3
"""Copy tracked current15 source into two disposable, unbuilt selected profiles.

Reads the coordinator's selected-issuance overlays directly. Never copies build
outputs, untracked files or Git metadata, and never edits the input source.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


def digest(path):
    if path.is_symlink():
        return hashlib.sha256(os.readlink(path).encode()).hexdigest()
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def git(source, *args):
    return subprocess.check_output(['git', '-C', str(source), *args])


def prepare(source, overlays, output):
    if output.is_relative_to(source) or output.is_relative_to(overlays):
        raise ValueError('output must be outside source and overlay inputs')
    lock_path = overlays / 'source-lock.json'
    lock = json.loads(lock_path.read_text())
    if git(source, 'rev-parse', 'HEAD').decode().strip() != lock['source_commit']:
        raise ValueError('source commit mismatch')
    if git(source, 'status', '--porcelain', '--untracked-files=no'):
        raise ValueError('tracked source or submodules are dirty')
    submodules = git(source, 'submodule', 'status', '--recursive').decode()
    if any(line and line[0] != ' ' for line in submodules.splitlines()):
        raise ValueError('submodules missing or mismatched')
    for name, expected in lock['sha256'].items():
        if digest(source / name) != expected:
            raise ValueError('source hash mismatch: ' + name)
    paths = [Path(p.decode()) for p in git(source, 'ls-files', '--recurse-submodules', '-z').split(b'\0') if p]
    for path in paths:
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('unsupported tracked source path: ' + str(path))
        if (source / path).is_symlink() and not (source / path).resolve().is_relative_to(source):
            raise ValueError('source symlink escapes snapshot: ' + str(path))
    # Capturing every tracked file prevents inherited binaries and untracked wallet
    # fixtures from becoming accidental inputs; output must not exist, even empty.
    original_hashes = {str(p): digest(source / p) for p in paths}
    output.mkdir(parents=True, exist_ok=False)
    receipt = dict(scope='tracked source snapshots only; no binaries or capacity normalization',
                   source_commit=lock['source_commit'], source_lock_sha256=digest(lock_path),
                   submodules=submodules, source_file_sha256=original_hashes,
                   symlinks={str(p): os.readlink(source / p) for p in paths if (source / p).is_symlink()},
                   profiles={})
    for name in ('selected-9-90', 'fallback-12-120'):
        target = output / name
        for path in paths:
            dest = target / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            if (source / path).is_symlink():
                dest.symlink_to(os.readlink(source / path))
            else:
                shutil.copyfile(source / path, dest)
                shutil.copymode(source / path, dest)
        patch = overlays / (name + '.patch')
        # Copy the exact overlay into the receipt directory before application.
        frozen_patch = output / patch.name
        shutil.copyfile(patch, frozen_patch)
        patch_env = dict(os.environ, GIT_CEILING_DIRECTORIES=str(target.parent))
        changed_paths = subprocess.check_output(['git', 'apply', '--numstat', str(frozen_patch)],
                                                cwd=target, env=patch_env, text=True)
        allowed = {'src/cryptonote_config.h', 'src/cryptonote_basic/cryptonote_basic_impl.cpp'}
        if {line.split('\t', 2)[2] for line in changed_paths.splitlines()} != allowed:
            raise ValueError('overlay touches unexpected paths')
        subprocess.run(['git', 'apply', '--check', str(frozen_patch)], cwd=target, env=patch_env, check=True)
        subprocess.run(['git', 'apply', str(frozen_patch)], cwd=target, env=patch_env, check=True)
        profile_hashes = {str(p): digest(target / p) for p in paths}
        changed = [p for p in original_hashes if original_hashes[p] != profile_hashes[p]]
        if set(changed) != allowed:
            raise ValueError('unexpected overlay paths: ' + str(changed))
        receipt['profiles'][name] = dict(overlay_sha256=digest(frozen_patch),
                                        changed_sha256={p: profile_hashes[p] for p in changed},
                                        built=False)
    if any(digest(source / p) != h for p, h in original_hashes.items()):
        raise ValueError('input source changed during preparation')
    (output / 'profile-inputs.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--overlays', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.source.resolve(), args.overlays.resolve(), args.output.resolve())
