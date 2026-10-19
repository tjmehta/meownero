#!/usr/bin/env python3
"""Prepare the TJS-2504 protocol checkpoint. This program never starts a node."""
import argparse
import difflib
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
MAX_JSON = 65536


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result

    with Path(path).open('rb') as stream:
        raw = stream.read(MAX_JSON + 1)
    require(len(raw) <= MAX_JSON, 'JSON exceeds 64 KiB')
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda value: require(False, 'nonfinite JSON number'))


def profile(path=None):
    expected = read_json(HERE / 'profile.json')
    value = read_json(path) if path else expected
    # Copies supplied by an operator must identify this exact checkpoint, including
    # its unresolved fields. A local hash is a binding, not release authentication.
    require(canonical(value) == canonical(expected), 'foreign or changed network profile')
    bindings = read_json(HERE / 'source-bindings.json')
    lock = (HERE.parent / 'source-lock.json').read_bytes()
    require(sha(lock) == bindings['source_lock_sha256'] == value['source_lock_sha256'],
            'source-lock binding mismatch')
    require(value['upstream_commit'] == bindings['upstream_commit'] ==
            json.loads(lock)['upstream']['commit'], 'upstream binding mismatch')
    require(value['status'] == 'protocol-proposal' and value['launch_ready'] is False,
            'this checkpoint cannot authorize launch')
    identity = value['network']['id_hex']
    require(identity == sha((value['profile_id'] + '/network-id').encode())[:32],
            'network ID derivation mismatch')
    require(value['valueless'] is True and len(value['unresolved']) > 0,
            'checkpoint must retain unresolved gates')
    return value


def profile_hash(value):
    return sha(canonical(value))


def checked_source(source):
    source = Path(source).resolve(strict=True)
    binding = read_json(HERE / 'source-bindings.json')
    pin = read_json(HERE.parent / 'source-lock.json')
    head = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    require(head == binding['upstream_commit'], 'upstream HEAD mismatch')
    originals = {}
    for name, digest in binding['files'].items():
        path = source / name
        require(not path.is_symlink(), 'symlinked source: ' + name)
        raw = path.read_bytes()
        require(sha(raw) == digest, 'changed source: ' + name)
        originals[name] = raw
    cargo = source / pin['rust']['cargo_lock_path']
    require(sha(cargo.read_bytes()) == pin['rust']['cargo_lock_sha256'], 'Cargo.lock mismatch')
    # Inspect read-only; no checkout, cache, toolchain or submodule mutation.
    for name, revision in pin['upstream']['submodules'].items():
        actual = subprocess.check_output(['git', '-C', str(source / name), 'rev-parse', 'HEAD'],
                                         text=True).strip()
        require(actual == revision, 'submodule HEAD mismatch: ' + name)
    return originals


def identity_overlay(original, value):
    text = original.decode()
    start = text.index('  namespace testnet\n')
    end = text.index('  namespace stagenet\n', start)
    before = text[start:end]
    changed = before
    settings = dict(zip(('CRYPTONOTE_PUBLIC_ADDRESS_BASE58_PREFIX',
                         'CRYPTONOTE_PUBLIC_INTEGRATED_ADDRESS_BASE58_PREFIX',
                         'CRYPTONOTE_PUBLIC_SUBADDRESS_BASE58_PREFIX'),
                        (value['network']['address_prefixes'][key]
                         for key in ('standard', 'integrated', 'subaddress'))))
    settings.update(P2P_DEFAULT_PORT=value['network']['ports']['p2p'],
                    RPC_DEFAULT_PORT=value['network']['ports']['daemon_rpc'],
                    ZMQ_RPC_DEFAULT_PORT=value['network']['ports']['zmq_reserved_disabled'],
                    GENESIS_NONCE=value['consensus_proposal']['genesis_nonce'])
    for key, number in settings.items():
        changed, count = re.subn(r'(\b' + key + r' = )\d+(;)',
                                 lambda match: match[1] + str(number) + match[2], changed)
        require(count == 1, 'ambiguous native constant: ' + key)
    octets = ', '.join('0x' + value['network']['id_hex'][i:i+2] for i in range(0, 32, 2))
    changed, count = re.subn(r'(NETWORK_ID = \{ \{)\s*.*?(\}\s*\};)',
                             lambda match: match[1] + '\n        ' + octets + '\n      ' + match[2],
                             changed, flags=re.S)
    require(count == 1, 'ambiguous native network ID')
    return (text[:start] + changed + text[end:]).encode()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def fresh_directory(path):
    path = Path(path).absolute()
    require(not any(char in str(path) for char in '\r\n#'), 'unsafe configuration path')
    # Reject symlink aliases and paths inside a source checkout. Only a new leaf
    # below an existing owned scratch directory can be prepared.
    parent = path.parent.resolve(strict=True)
    require(parent == path.parent, 'symlinked parent directory')
    require(not path.exists() and not path.is_symlink(), 'fresh output directory required')
    require(not path.is_relative_to(ROOT), 'output must be outside the source checkout')
    require(not any((directory / '.git').exists() for directory in (parent, *parent.parents)),
            'output must not be inside a Git checkout')
    require(parent.stat().st_uid == os.getuid(), 'output parent must belong to this user')
    require(parent.stat().st_mode & 0o022 == 0, 'output parent must not be writable by others')
    path.mkdir(mode=0o700)
    return path


def overlay(source, out, value):
    originals = checked_source(source)
    name = 'src/cryptonote_config.h'
    changed = identity_overlay(originals[name], value)
    patch = ''.join(difflib.unified_diff(originals[name].decode().splitlines(True),
                                       changed.decode().splitlines(True),
                                       fromfile='a/' + name, tofile='b/' + name, n=1))
    out = fresh_directory(out)
    (out / 'identity-only.patch').write_text(patch)
    receipt = {'schema': 'meownero-vanguard-network-identity-overlay/1',
               'profile_sha256': profile_hash(value), 'upstream_commit': value['upstream_commit'],
               'result': 'IDENTITY_ONLY_NOT_LAUNCHABLE', 'native_network_proof': 'NOT_RUN',
               'files': {name: {'original_sha256': sha(originals[name]),
                                'changed_sha256': sha(changed)}},
               'patch_sha256': sha(patch.encode()), 'unresolved': value['unresolved']}
    write_json(out / 'overlay.json', receipt)
    return receipt


def topology(path, value):
    data = read_json(path)
    require(set(data) == {'schema', 'primary', 'recovery'}, 'unexpected topology fields')
    require(data['schema'] == 'meownero-vanguard-private-bootstrap/1', 'foreign bootstrap schema')
    for role in ('primary', 'recovery'):
        row = data[role]
        require(set(row) == {'node_id', 'operator_id', 'endpoint', 'profile_sha256'},
                'unexpected bootstrap fields')
        for key in ('node_id', 'operator_id'):
            require(isinstance(row[key], str) and re.fullmatch(r'[a-z][a-z0-9-]{0,47}', row[key]),
                    'unassigned or invalid ' + role + ' ' + key)
        require(row['profile_sha256'] == profile_hash(value), 'foreign bootstrap profile')
        require(isinstance(row['endpoint'], str), 'unassigned bootstrap endpoint')
        host, port = row['endpoint'].rsplit(':', 1)
        require(str(ipaddress.IPv4Address(host)) == '127.0.0.1', 'only contained loopback endpoints allowed')
        require(port.isdecimal() and 1024 <= int(port) <= 65535, 'invalid bootstrap port')
        require(int(port) not in {18080, 19080, 28080, 29080, 38080, 39080}, 'foreign default bootstrap port')
    for key in ('node_id', 'operator_id', 'endpoint'):
        require(data['primary'][key] != data['recovery'][key], 'primary and recovery share ' + key)
    return data


def prepare(out, node_id, bootstrap_path, role, value):
    require(re.fullmatch(r'[a-z][a-z0-9-]{0,47}', node_id), 'invalid node_id')
    peers = topology(bootstrap_path, value)
    require(node_id not in {peers[key]['node_id'] for key in ('primary', 'recovery')},
            'client node_id conflicts with seed identity')
    # Use one explicit exclusive native P2P destination. Never use wallet/daemon
    # bootstrap RPC or silently fall back to a foreign seed.
    peer = peers[role]['endpoint']
    ports = value['network']['ports']
    require(int(peer.rsplit(':', 1)[1]) not in ports.values(), 'peer would target this node or a local RPC port')
    out = fresh_directory(out)
    data = out / value['profile_id'] / node_id
    data.mkdir(mode=0o700, parents=True)
    (data.parent).chmod(0o700)
    # Proposal filenames and the absence of a launch subcommand are intentional.
    # These are review inputs until native protocol and package bindings exist.
    daemon = [f'data-dir={data}', 'testnet=1', 'non-interactive=1', 'no-igd=1',
              'allow-local-ip=1', 'disable-dns-checkpoints=1', 'check-updates=disabled',
              'hide-my-port=1', 'max-concurrency=1', 'no-zmq=1', 'rpc-ssl=disabled',
              'restricted-rpc=1', 'p2p-bind-ip=127.0.0.1', f'p2p-bind-port={ports["p2p"]}',
              'rpc-bind-ip=127.0.0.1', f'rpc-bind-port={ports["daemon_rpc"]}',
              'add-exclusive-node=' + peer]
    wallet = ['testnet=1', 'rpc-bind-ip=127.0.0.1', f'rpc-bind-port={ports["wallet_rpc"]}',
              'restricted-rpc=1', f'daemon-address=127.0.0.1:{ports["daemon_rpc"]}']
    (out / 'daemon.conf.proposal').write_text('\n'.join(daemon) + '\n')
    (out / 'wallet-rpc.conf.proposal').write_text('\n'.join(wallet) + '\n')
    receipt = {'schema': 'meownero-vanguard-private-preparation/1',
               'result': 'PREPARED_NOT_STARTED', 'launch_ready': False,
               'profile_sha256': profile_hash(value), 'bootstrap_role': role,
               'bootstrap': peers[role], 'node_id': node_id,
               'data_directory': str(data), 'native_database': str(data / 'testnet/lmdb'),
               'daemon_auth_requirement': 'RPC_LOGIN runtime environment required; no unauthenticated daemon default',
               'wallet_auth_requirement': 'native generated login, never disable-rpc-login',
               'limits': value['containment'], 'unresolved': value['unresolved']}
    write_json(out / 'profile-binding.json', receipt)
    for path in out.iterdir():
        if path.is_file():
            path.chmod(0o600)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('validate')
    check = sub.add_parser('check-source')
    check.add_argument('--source', type=Path, required=True)
    make = sub.add_parser('identity-overlay')
    make.add_argument('--source', type=Path, required=True)
    make.add_argument('--out', type=Path, required=True)
    prep = sub.add_parser('prepare')
    prep.add_argument('--out', type=Path, required=True)
    prep.add_argument('--node-id', required=True)
    prep.add_argument('--bootstrap', type=Path, required=True)
    prep.add_argument('--role', choices=['primary', 'recovery'], default='primary')
    sub.add_parser('readiness')
    args = parser.parse_args()
    try:
        value = profile(args.profile)
        if args.command == 'validate':
            result = {'result': 'PASS_PROFILE_CHECKPOINT', 'profile_sha256': profile_hash(value),
                      'launch_ready': False, 'native_network_proof': 'NOT_RUN'}
        elif args.command == 'check-source':
            originals = checked_source(args.source)
            result = {'result': 'PASS_PINNED_SOURCE_PATHS',
                      'files': {name: sha(raw) for name, raw in originals.items()},
                      'scope': 'listed files and submodule HEADs only; not full-tree or executable provenance'}
        elif args.command == 'identity-overlay':
            result = overlay(args.source, args.out, value)
        elif args.command == 'prepare':
            result = prepare(args.out, args.node_id, args.bootstrap, args.role, value)
        else:
            print(json.dumps({'result': 'BLOCKED_PROTOCOL_AND_NATIVE_GATES',
                              'launch_ready': False, 'unresolved': value['unresolved']}, indent=2))
            return 3
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print('REFUSED: ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
