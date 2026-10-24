#!/usr/bin/env python3
"""Export the exact Linux38 Docker source kit. This command launches no workload."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent.parent
INPUTS = ROOT / 'research/evidence/vanguard-linux38-docker-correction2-tjs1882-2026-10-24/inputs.json'


def sha(path):
    assert path.is_file() and not path.is_symlink()
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def stage(out):
    value = json.loads(INPUTS.read_text())
    origin = value['docker_successor_origin']
    frozen = ROOT / origin['base_inputs']
    assert sha(frozen) == origin['base_inputs_sha256']
    base = json.loads(frozen.read_text())
    patch = ROOT / origin['patch']
    assert sha(patch) == origin['patch_sha256']
    for name, digest in base['source_files'].items():
        assert sha(ROOT / name) == digest, 'frozen source changed: ' + name
    out = out.absolute()
    assert out.parent.is_dir() and not out.exists() and not any(p.is_symlink() for p in (out, *out.parents))
    # Verify all unpatched additions before creating output.
    changed = {'vanguard/run-portable-linux-docker.py', 'vanguard/portable-build.py', 'vanguard/run-portable-check.py', 'vanguard/portable-prepare-old-linux.py'}
    for name, digest in value['source_files'].items():
        if name not in changed:
            assert sha(ROOT / name) == digest, 'successor source changed: ' + name
    out.mkdir(mode=0o700)
    for name in set(base['source_files']) | (set(value['source_files']) - changed):
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        shutil.copyfile(ROOT / name, target)
    (out / 'vanguard/run-portable-linux-ci.py').rename(out / 'vanguard/run-portable-linux-docker.py')
    result = subprocess.run(['patch', '--batch', '--fuzz=0', '--no-backup-if-mismatch', '-p1', '-i', str(patch)],
                            cwd=out, check=True, capture_output=True, text=True, timeout=20)
    assert 'offset' not in result.stdout and 'fuzz' not in result.stdout
    for name, digest in value['source_files'].items():
        assert sha(out / name) == digest, 'patched output differs: ' + name
    shutil.copyfile(INPUTS, out / 'inputs.json')
    receipt = {'schema': 'meownero-linux38-docker-source-export/1', 'result': 'PASS_SOURCE_BINDINGS_ONLY',
               'inputs_sha256': sha(INPUTS), 'source_files': value['source_files'],
               'patch_sha256': sha(patch), 'base_inputs_sha256': sha(frozen),
               'platform_acceptance': 'NONE', 'live_execution': 'REQUIRES_INDEPENDENT_SOURCE_CLEARANCE'}
    (out / 'source-export.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    print(json.dumps(stage(parser.parse_args().out), indent=2))
