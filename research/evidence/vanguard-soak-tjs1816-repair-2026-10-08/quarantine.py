#!/usr/bin/env python3
"""One authorized build-mac repair. Refuse changed ownership; never signal processes.

This is a mutation receipt source, not a command to replay after this run.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess

ROOT = Path('~/.colima/_lima/colima')
PROFILE = Path('~/.colima/default/colima.yaml')
EXPECTED_PROFILE = '953069eb536626c5b04906c9122d3f35d54e4d3091c50f5bc4adf7cc7f627697'
EXPECTED_INODES = {'ha.pid': 58981407, 'vz.pid': 58981481, 'ha.sock': 58981476}
RECOVERY = ROOT.parent / 'tjs1816-recovery-5a24c6b6-20261008'


def command(argv):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=15)
    row = {'argv': argv, 'exit': result.returncode,
           'stdout': result.stdout, 'stderr': result.stderr}
    print(json.dumps({'command': row}), flush=True)
    return row


def metadata(path):
    s = path.lstat()
    row = {'path': str(path), 'device': s.st_dev, 'inode': s.st_ino,
           'mode': s.st_mode, 'uid': s.st_uid, 'gid': s.st_gid,
           'size': s.st_size, 'mtime_ns': s.st_mtime_ns,
           'ctime_ns': s.st_ctime_ns, 'birthtime': s.st_birthtime}
    if stat.S_ISREG(s.st_mode):
        row['content'] = path.read_text()
        row['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    return row


def gates():
    digest = hashlib.sha256(PROFILE.read_bytes()).hexdigest()
    assert digest == EXPECTED_PROFILE, 'saved profile changed'
    identity = command(['ps', '-p', '75180', '-o', 'pid=,ppid=,user=,lstart=,comm='])
    assert identity['exit'] == 0, 'unrelated simulator missing'
    assert re.search(r'75180\s+74219\s+tjmehta\s+Thu Oct\s+8 02:22:27 2026\s+', identity['stdout']), 'simulator start identity changed'
    assert identity['stdout'].rstrip().endswith('/usr/libexec/deviceaccessd'), 'PID owner changed'
    processes = command(['ps', '-axo', 'pid=,ppid=,user=,lstart=,comm='])
    assert processes['exit'] == 0
    active = [line for line in processes['stdout'].splitlines()
              if re.search(r'/(?:colima|limactl|qemu[^/\s]*|lima-hostagent|hostagent)(?:\s|$)', line)]
    assert not active, 'live runtime process: ' + repr(active)
    for p in [ROOT / 'ha.sock', ROOT / 'disk', ROOT.parent / '_disks/colima/datadisk']:
        held = command(['lsof', '-n', '-a', str(p)])
        assert held['exit'] == 1 and not held['stdout'] and not held['stderr'], 'file ownership uncertain: ' + str(p)
    if (ROOT / 'ha.sock').exists():
        sock = socket.socket(socket.AF_UNIX)
        sock.settimeout(2)
        try:
            sock.connect(str(ROOT / 'ha.sock'))
        except ConnectionRefusedError:
            pass
        else:
            raise AssertionError('socket listener or uncertain failure')
        finally:
            sock.close()
    return identity['stdout'], digest


def main():
    assert not RECOVERY.exists(), 'repair directory already exists; do not replay'
    initial = {name: metadata(ROOT / name) for name in EXPECTED_INODES}
    print(json.dumps({'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      'initial': initial, 'recovery': str(RECOVERY)}), flush=True)
    for name, row in initial.items():
        assert row['inode'] == EXPECTED_INODES[name], 'entry replaced: ' + name
        assert row['uid'] == os.getuid(), 'entry owner changed'
        assert datetime.datetime.fromtimestamp(row['mtime_ns'] / 1e9).date() == datetime.date(2026, 9, 16), 'staleness changed'
        if name.endswith('.pid'):
            assert stat.S_ISREG(row['mode']) and row['content'] == '75180\n', 'PID entry changed'
        else:
            assert stat.S_ISSOCK(row['mode']), 'socket type changed'
    identity, digest = gates()
    command(['tail', '-n', '12', str(ROOT / 'ha.stderr.log')])
    RECOVERY.mkdir(mode=0o700)
    receipt = {'initial': initial, 'profile_sha256': digest,
               'simulator_identity': identity, 'moved': [], 'complete': False}
    receipt_path = RECOVERY / 'receipt.json'
    receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
    try:
        for name in EXPECTED_INODES:
            gates()
            assert metadata(ROOT / name) == initial[name], 'entry changed mid-operation'
            assert not (RECOVERY / name).exists(), 'destination exists'
            os.rename(ROOT / name, RECOVERY / name)
            moved = metadata(RECOVERY / name)
            assert moved['inode'] == initial[name]['inode'] and moved['device'] == initial[name]['device']
            receipt['moved'].append({'original': str(ROOT / name), 'quarantined': moved})
            receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
        receipt['complete'] = True
    finally:
        receipt_path.write_text(json.dumps(receipt, indent=2) + '\n')
        print(json.dumps({'receipt': receipt, 'receipt_path': str(receipt_path)}), flush=True)


if __name__ == '__main__':
    main()
