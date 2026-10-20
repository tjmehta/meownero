"""Pure contract checks shared by source tests and the future native attempt.

These functions never acquire resources, launch a process or contact a daemon.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct

HERE = Path(__file__).resolve().parent
BASE = 'cb95cc036000a70bc688deeba6bff1b384b27eb3'
PLATFORM = '92a7b4f2-787b-4cbb-954e-46831397ab09'
ISSUE = '06902067-3d17-4ccf-a6e4-c39d631f4ad2'
LOCK = Path('/tmp/meownero-swarm-20260912-heavy.lock')
LOCK_ID = (66306, 657237)
GENESIS = '885cb43cf51086063f15c94d2fb7f327e34c447de53c9c6291b1a86d6510dab6'
UUID = bytes.fromhex('e16d7839ed4d3ec8363d078df18fff6d')
HEADER = struct.Struct('<QQBIiII')
SIGNATURE = 0x0101010101012101
LIMITS = dict(wall_seconds=4500, build_seconds=3600, runtime_seconds=600,
              cleanup_seconds=300, cpus=2, cpu_seconds=9000, memory_bytes=4*1024**3,
              swap_bytes=0, pids=256, compile_jobs=1, memory_floor=5*1024**3,
              disk_floor=20*1024**3, disk_hard_bytes=15*1024**3,
              disk_abort_free=4*1024**3, load_1_5_15_max=[6.0, 6.0, 6.0],
              non_genesis_blocks=0, transactions=0, attempts=1)
CONSUMED = {'0ae5446a-0da7-4f75-9604-50b4e7b090c8',
            '2d70177d-b7a7-4ef6-8079-242320bdcb1f',
            '15414082-2a53-4872-8d19-b87f302f0bae',
            '3127e4f4-46ae-4e8d-9732-128640aca67a'}
REQUIRED = {
 'build.json': ['three_production_binaries', 'rpc_translation_unit'],
 'peer.json': ['native_handshake', 'genesis_state', 'daemon_fork_table'],
 'wallet.json': ['persisted_height_zero', 'address_roundtrip', 'foreign_prefix_refusal'],
 'auth.json': ['http_auth', 'seventeen_denials', 'rotated_login'],
 'isolation.json': ['uuid_guard', 'chain_genesis_guard', 'launcher_refusals', 'no_fallback'],
 'reopen.json': ['wallet_save_exit_release', 'wallet_cold_restore', 'daemon_reopen_restore'],
 'resources.json': ['parent_enclosure', 'deadlines', 'disk', 'no_oom'],
 'cleanup.json': ['owned_pids_absent', 'owned_cid_absent', 'owned_staging_removed', 'lock_released']}
EXCLUDED = ['native_foreign_db_identity_refusal', 'native_checkpoint_rejection',
            'native_offline_wallet_fork_agreement', 'seed_restore_funded_rescan',
            'full_remaining_matrix']


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def tree_inputs(root):
    root=Path(root)
    result={}
    for path in sorted(root.rglob('*')):
        name=str(path.relative_to(root))
        if path.is_symlink():
            require(path.resolve(strict=True).is_relative_to(root), 'external input symlink')
            result[name]={'symlink':os.readlink(path)}
        elif path.is_file():
            with path.open('rb') as stream:
                sha=hashlib.file_digest(stream,'sha256').hexdigest()
            result[name]={'sha256':sha,'mode':stat.S_IMODE(path.stat().st_mode)}
        else:require(path.is_dir(),'special input file')
    return result


def tree_fingerprint(root):
    inventory=tree_inputs(root)
    return {'tree_sha256':digest(canonical(inventory)),'files':len(inventory)}


def loopback_census(tables):
    count=0
    for ipv6,lines in tables:
        allowed='00000000000000000000000001000000' if ipv6 else '0100007F'
        for line in lines.splitlines()[1:]:
            parts=line.split()
            local,remote,state=parts[1:4]
            local_ip,local_port=local.split(':');remote_ip,remote_port=remote.split(':')
            require(local_ip==allowed,'non-loopback local socket')
            if remote_port!='0000':require(remote_ip==allowed,'non-loopback remote socket')
            count+=1
    return count


def json_file(path):
    return json.loads(Path(path).read_text())


def check_file(path, modes=(0o600,), uid=None):
    path = Path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and
                info.st_uid == (os.getuid() if uid is None else uid) and
                stat.S_IMODE(info.st_mode) in modes, 'private regular file identity/mode')
        return os.read(fd, 1024*1024)
    finally:
        os.close(fd)


def no_alias(path):
    path = Path(path).absolute()
    require(path.resolve(strict=True) == path, 'path alias or symlink')
    return path


def check_lock(info, uid):
    require(stat.S_ISREG(info.st_mode) and (info.st_dev, info.st_ino) == LOCK_ID and
            info.st_uid == uid and stat.S_IMODE(info.st_mode) == 0o600,
            'original heavy-lock identity/owner/mode')


def admit(snapshot):
    require(snapshot['available_memory_bytes'] >= LIMITS['memory_floor'], 'requires 5 GiB available')
    require(snapshot['free_disk_bytes'] >= LIMITS['disk_floor'], 'requires 20 GiB free disk')
    require(len(snapshot['load']) == 3 and all(0 <= x <= y for x,y in
            zip(snapshot['load'], LIMITS['load_1_5_15_max'])), 'load admission exceeds proposal')
    require(not snapshot['native_processes'] and not snapshot['native_containers'], 'workload collision')


def grant_payload(comment, *, commit, inputs_hash, artifact_hash, now):
    require(comment['id'] not in CONSUMED and not comment.get('deletedAt') and
            comment['issueId'] == ISSUE and comment['authorAgentId'] == PLATFORM and
            comment.get('authorType') == 'agent', 'not a new attributed Platform grant')
    blocks = re.findall(r'```meownero-platform-grant\n(.*?)\n```', comment['body'], re.S)
    require(len(blocks) == 1, 'exact structured grant required')
    value = json.loads(blocks[0])
    expected = dict(schema='meownero-platform-grant/1', issue_id=ISSUE,
                    candidate_commit=commit, inputs_sha256=inputs_hash,
                    artifact_sha256=artifact_hash, limits=LIMITS,
                    attempts=1, retry=False, workload='three-production-binaries-genesis-only')
    require(all(value.get(k) == v for k,v in expected.items()), 'grant binding mismatch')
    require(value.get('authorized') is True and value['not_before_unix'] <= now < value['expires_unix'],
            'grant absent, premature or expired')
    require(value['enclosure']['mechanism'] == 'common-cgroup-v2-dedicated-docker-fixed-filesystem/1',
            'whole-attempt enclosure missing')
    return value


def enclosure(counters, self_group, daemon_group, parent):
    require(parent.startswith('/') and '..' not in Path(parent).parts and parent != '/', 'unsafe parent')
    require(all(group.startswith(parent + '/') for group in (self_group, daemon_group)),
            'controller or Docker daemon outside aggregate parent')
    require(counters['cpu.max'] == '200000 100000' and
            counters['memory.max'] == str(LIMITS['memory_bytes']) and
            counters['memory.swap.max'] == '0' and counters['pids.max'] == '256' and
            counters['cgroup.procs'] == '' and counters['memory.oom.group'] == '1',
            'aggregate limits/topology differ')


def stop_identity(owned, observed):
    require(owned == observed, 'PID reuse; signal refused')


def root_manifest(root, expected):
    root = no_alias(root)
    require(root.stat().st_uid == os.getuid() and stat.S_IMODE(root.stat().st_mode) == 0o700,
            'root owner/mode')
    actual = json.loads(check_file(root / 'creation.json'))
    require(actual == expected and actual['stopped_saved'] is True, 'launcher manifest refusal')
    # A manifest binds ownership/history, not arbitrary LMDB chain identity.
    for path in root.rglob('*'):
        info = path.lstat()
        require(not path.is_symlink() and info.st_uid == os.getuid() and
                (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode) and info.st_nlink == 1),
                'retained root alias/type/owner')
    saved = actual['saved_files']
    files = {str(p.relative_to(root)): digest(p.read_bytes()) for p in root.rglob('*')
             if p.is_file() and p != root / 'creation.json'}
    require(files == saved, 'saved bundle digest or membership changed')
    return root


def empty_rows():
    return {name: {row: {'status': 'NOT_RUN'} for row in rows} for name,rows in REQUIRED.items()}


def verdict(rows):
    states = [rows.get(name, {}).get(row, {}).get('status', 'NOT_RUN')
              for name,keys in REQUIRED.items() for row in keys]
    if 'FAIL' in states:
        return 'FAIL'
    return ('PASS_COMPLETE_BINARIES_GENESIS_PEER_WALLET_BOUNDARY_ONLY'
            if all(s == 'PASS' for s in states) else 'INCOMPLETE')


def portable_varint(value):
    require(0 <= value < 2**62, 'portable length out of range')
    for size,mark,bits in [(1,0,6), (2,1,14), (4,2,30), (8,3,62)]:
        if value < 2**bits:
            return ((value << 2) | mark).to_bytes(size,'little')


def chain_request(last_hash):
    # Pinned portable-storage map order is lexicographic, block_ids then prune.
    payload = struct.pack('<IIB', 0x01011101, 0x01020101, 1) + portable_varint(2)
    payload += b'\x09block_ids\x0a' + portable_varint(32) + bytes.fromhex(last_hash)
    payload += b'\x05prune\x0b\x00'
    return HEADER.pack(SIGNATURE,len(payload),0,2006,0,1,1) + payload


def mutate_uuid(packet):
    payload = packet[HEADER.size:]
    needle = b'\x0anetwork_id\x0a' + portable_varint(16) + UUID
    require(payload.count(needle) == 1, 'one native UUID field required')
    wrong = bytes([UUID[0] ^ 1]) + UUID[1:]
    return packet[:HEADER.size] + payload.replace(needle, needle[:-16] + wrong,1)


def denial_requests(address, seed):
    # Valid native JSON schemas; the restricted guard precedes semantic spending.
    dest = dict(destinations=[dict(amount=1,address=address)],account_index=0,subaddr_indices=[],
                priority=0,ring_size=0,unlock_time=0,payment_id='',get_tx_key=False,get_tx_keys=False,do_not_relay=True)
    split=dict(dest);split.pop('get_tx_key')
    transfer=dict(dest);transfer.pop('get_tx_keys')
    return dict(transfer=transfer, transfer_split=split,
        sweep_all=dict(address=address,account_index=0,subaddr_indices=[],priority=0,
                       ring_size=0,unlock_time=0,payment_id='',get_tx_keys=False,below_amount=0,do_not_relay=True),
        sweep_single=dict(address=address,key_image='00'*32,priority=0,ring_size=0,unlock_time=0,
                          payment_id='',get_tx_key=False,do_not_relay=True),
        sign=dict(data='restriction-control',account_index=0,address_index=0,signature_type='spend'),
        sign_transfer=dict(unsigned_txset='00',export_raw=False,get_tx_keys=False),
        query_key=dict(key_type='view_key'),
        set_daemon=dict(address='127.0.0.1:48081',trusted=True,ssl_support='disabled',username='',password='',ssl_private_key_path='',
                        ssl_certificate_path='',ssl_ca_file='',ssl_allowed_fingerprints=[]),
        store={},stop_wallet={},close_wallet={},create_address=dict(account_index=0,label='refused',count=1),
        create_account=dict(label='refused'),create_wallet=dict(filename='refused',password='',language='English'),
        open_wallet=dict(filename='refused',password=''),
        restore_deterministic_wallet=dict(filename='refused',password='',seed=seed,seed_offset='',
                                          restore_height=0,language='English',autosave_current=False),
        refresh=dict(start_height=0))
