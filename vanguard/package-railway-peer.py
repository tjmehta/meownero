#!/usr/bin/env python3
"""Create an allowlisted, database-free private Railway upload on build-mac."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile


def runtime_rootfs(source, destination):
    """Keep the installed Python runtime and shared libraries, excluding build tools."""
    with tarfile.open(source, 'r:gz') as original, tarfile.open(destination, 'w:gz') as output:
        for member in original:
            name = member.name.lstrip('./')
            keep = name in {'bin', 'lib', 'lib64', 'usr/bin/python3', 'usr/bin/python3.12',
                            'etc/nsswitch.conf', 'etc/passwd', 'etc/group'}
            keep |= name.startswith('usr/lib/python3.12/') and '__pycache__' not in name
            keep |= name.startswith(('usr/lib/x86_64-linux-gnu/', 'usr/lib64/')) and '.so' in Path(name).name
            keep |= name.startswith('usr/lib/locale/C.utf8/')
            if keep:
                output.addfile(member, original.extractfile(member) if member.isfile() else None)
        for name, mode in [('data', 0o700), ('app', 0o755)]:
            member = tarfile.TarInfo(name)
            member.type = tarfile.DIRTYPE
            member.mode = mode
            member.uid = member.gid = 1000
            output.addfile(member)


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
    receipt_path = root / 'amd64/preparation/daemon-resume.json'
    if not receipt_path.exists():
        receipt_path = root / 'amd64/preparation/receipt.json'
    receipt = json.loads(receipt_path.read_text())
    assert receipt['result'] in {'PASS_EMULATED_BUILD', 'PASS_EMULATED_DAEMON_BUILD'}
    binary = root / 'amd64/monero-fcmp/build/vanguard/bin/monerod'
    data = binary.read_bytes()
    assert data[:4] == b'\x7fELF' and int.from_bytes(data[18:20], 'little') == 62, 'AMD64 ELF required'
    assert sha(binary) == receipt['binary']['monerod']['sha256']
    archive = root / 'builder-rootfs-amd64.tar.gz'
    assert sha(archive) == receipt['rootfs']['rootfs_sha256']
    out.mkdir(mode=0o700)
    runtime_rootfs(archive, out / 'runtime-rootfs-amd64.tar.gz')
    for source, name in ((binary, 'monerod'),
                         (root / 'railway-peer.py', 'railway-peer.py')):
        shutil.copy2(source, out / name)
    (out / 'Dockerfile').write_text('''FROM scratch
ADD runtime-rootfs-amd64.tar.gz /
COPY monerod railway-peer.py /app/
USER 1000:1000
EXPOSE 19080 8080
ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["/usr/bin/python3.12", "-B", "/app/railway-peer.py"]
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
