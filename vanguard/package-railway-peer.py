#!/usr/bin/env python3
"""Create an allowlisted, database-free private Railway upload on build-mac."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    assert platform.system() == 'Darwin' and platform.machine() == 'arm64'
    assert subprocess.check_output(['hostname'], text=True).strip().split('.')[0] == 'build-mac'
    root = args.stage.resolve()
    out = args.out.resolve()
    assert not out.exists(), 'fresh upload package required'
    receipt = json.loads((root / 'amd64/preparation/receipt.json').read_text())
    assert receipt['result'] == 'PASS_EMULATED_BUILD'
    binary = root / 'amd64/monero-fcmp/build/vanguard/bin/monerod'
    data = binary.read_bytes()
    assert data[:4] == b'\x7fELF' and int.from_bytes(data[18:20], 'little') == 62, 'AMD64 ELF required'
    assert sha(binary) == receipt['binary']['monerod']['sha256']
    archive = root / 'builder-rootfs-amd64.tar.gz'
    assert sha(archive) == receipt['rootfs']['rootfs_sha256']
    out.mkdir(mode=0o700)
    for source, name in ((binary, 'monerod'), (archive, archive.name),
                         (root / 'railway-peer.py', 'railway-peer.py')):
        shutil.copy2(source, out / name)
    (out / 'Dockerfile').write_text('''FROM scratch
ADD builder-rootfs-amd64.tar.gz /
COPY monerod railway-peer.py /app/
RUN mkdir -p /data && chown -R 1000:1000 /app /data && chmod 700 /data
USER 1000:1000
EXPOSE 19080 8080
ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["/usr/bin/python3", "-B", "/app/railway-peer.py"]
''')
    (out / 'railway.json').write_text(json.dumps({'build': {'builder': 'DOCKERFILE'},
        'deploy': {'restartPolicyType': 'NEVER', 'numReplicas': 1}}, indent=2) + '\n')
    manifest = {'schema': 'tjs1856-private-peer-upload/1', 'architecture': 'linux/amd64',
        'source_pins': receipt['source_pins'], 'base_rootfs': receipt['rootfs'],
        'binary': receipt['binary']['monerod'],
        'files': {path.name: {'sha256': sha(path), 'bytes': path.stat().st_size} for path in sorted(out.iterdir())},
        'exclusions': ['wallet executable/files', 'chain databases', 'keys', 'runtime credentials'],
        'runtime_control_token': 'provider runtime variable only', 'result': 'PACKAGED_NOT_DEPLOYED'}
    (root / 'upload-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('PACKAGED_NOT_DEPLOYED', sum(row['bytes'] for row in manifest['files'].values()))


if __name__ == '__main__':
    main()
