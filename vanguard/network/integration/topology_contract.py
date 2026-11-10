"""Closed TJS-3920 persistent-topology contract; no native effects on import.

Binds the Security limits L1-L6 from the TJS-2504 formal review into code:
every native argv is checked before launch (L1/L2/L5), public witnesses use a
private per-topology salt (L3), and every exported/receipt file is 0600 (L6).
"""
import hashlib
import hmac
import re

WORKLOAD = 'persistent-three-node-topology'
ISSUE = '2f885568-8394-4bb1-a590-9dea32971ce2'  # TJS-3920
UPTIME_SECONDS = 86400
SAMPLE_SECONDS = 300
WALL_SECONDS = 100800  # 28 h: about 45 min of rows, the cycle, 24 h steady, slack.
# Lead-selectable rehearsal: same code and rows, 1 h steady inside a 4 h wall. Its
# verdict is labelled rehearsal and can never satisfy the 24 h row.
REHEARSAL_UPTIME_SECONDS = 3600
REHEARSAL_WALL_SECONDS = 14400
MODES = {UPTIME_SECONDS: WALL_SECONDS, REHEARSAL_UPTIME_SECONDS: REHEARSAL_WALL_SECONDS}
MAX_COUNT = 2400       # Chain block count N including genesis; ~90 s blocks for 28 h is ~1120.
MAX_SPREAD = 2         # Steady samples: node heights may differ by at most this many blocks.
ATOMIC = 10**12

NODES = ('A', 'B', 'C')           # A primary seed + miner, B recovery seed, C late client.
P2P = {'A': 48080, 'B': 48180, 'C': 48280}
RPC = {name: port+1 for name, port in P2P.items()}
WALLET_PORT = 48083                # One-time miner-address signer; never a service.
PEERS = {'A': ('B',), 'B': ('A',), 'C': ('A', 'B')}
LOOPBACK = {'127.0.0.1', '::1'}

# L2: send_raw_transaction/submit_block stay mapped under --restricted-rpc, so the
# daemon RPC remains a private loopback service even when restricted.
DAEMON_REQUIRED = ('--testnet', '--non-interactive', '--no-igd', '--no-zmq', '--restricted-rpc',
    '--disable-dns-checkpoints', '--hide-my-port')
FORBIDDEN = ('--confirm-external-bind', '--disable-rpc-login', '--public-node', '--rpc-restricted-bind-ip',
    '--rpc-restricted-bind-port', '--rpc-restricted-bind-ipv6-address', '--zmq-rpc-bind-ip',
    '--zmq-pub', '--add-peer', '--add-priority-node', '--seed-node', '--bootstrap-daemon-address',
    '--igd', '--rpc-ssl-allow-any-cert', '--trusted-daemon', '--untrusted-daemon', '--proxy',
    '--tx-proxy', '--anonymous-inbound', '--rpc-access-control-origins', '--daemon-ssl-allow-any-cert',
    '--rpc-login', '--daemon-login')  # L4: credentials reach a child only through its environment.
# Exact allowlist of full option names (True = takes one value). Boost's
# command_line_parser accepts any unique prefix ('--public-nod' is --public-node),
# so a denylist alone is not a boundary; every name outside this table refuses.
# Each name is an arg_descriptor of the pinned fork (monero-fcmp e151643c).
ALLOWED = {
    'monerod': {'--testnet': False, '--data-dir': True, '--non-interactive': False, '--no-igd': False,
        '--allow-local-ip': False, '--disable-dns-checkpoints': False, '--check-updates': True,
        '--hide-my-port': False, '--max-concurrency': True, '--no-zmq': False, '--rpc-ssl': True,
        '--restricted-rpc': False, '--p2p-bind-ip': True, '--p2p-bind-ipv6-address': True,
        '--p2p-bind-port': True, '--rpc-bind-ip': True, '--rpc-bind-port': True,
        '--max-connections-per-ip': True, '--log-level': True, '--log-file': True, '--offline': False,
        '--add-exclusive-node': True, '--in-peers': True, '--start-mining': True, '--mining-threads': True},
    'monero-wallet-rpc': {'--testnet': False, '--config-file': True, '--daemon-address': True,
        '--wallet-dir': True, '--rpc-bind-ip': True, '--rpc-bind-port': True, '--rpc-ssl': True,
        '--log-file': True, '--restricted-rpc': False},
}
REPEATABLE = ('--add-exclusive-node',)
BIND_OPTIONS = ('--p2p-bind-ip', '--p2p-bind-ipv6-address', '--rpc-bind-ip', '--rpc-bind-ipv6-address')


class PolicyRefusal(ValueError):
    """Raised before any process start; the message names only the option."""


def _require(ok, message):
    if not ok:
        raise PolicyRefusal(message)


def options(argv):
    """Map '--name value' and '--name=value' forms; repeated options are kept in order."""
    result = []
    index = 1
    while index < len(argv):
        item = argv[index]
        _require(type(item) is str and item.startswith('--'), 'positional or non-string argv item')
        if '=' in item:
            name, value = item.split('=', 1)
        elif index+1 < len(argv) and not argv[index+1].startswith('--'):
            name, value = item, argv[index+1]
            index += 1
        else:
            name, value = item, None
        result.append((name, value))
        index += 1
    return result


def allowlisted(parsed, allowed, forbidden=FORBIDDEN):
    """Refuse forbidden, unknown or abbreviated names, value/flag misuse and repeats."""
    names = [name for name, _ in parsed]
    for name in forbidden:
        _require(name not in names, 'forbidden option '+name)
    for name, value in parsed:
        _require(name in allowed, 'unknown or abbreviated option '+name)
        _require((value is not None) == allowed[name], 'option value shape '+name)
        _require(name in REPEATABLE or names.count(name) == 1, 'repeated option '+name)
    return names


def check_argv(kind, argv, *, mining=False, offline=False, signer=False):
    """L1/L2/L5 launcher refusal. Returns the parsed options when acceptable."""
    _require(kind in ('monerod', 'monero-wallet-rpc'), 'unknown native kind')
    _require(argv and str(argv[0]).endswith('/'+kind), 'executable/kind mismatch')
    parsed = options([str(x) for x in argv])
    names = allowlisted(parsed, ALLOWED[kind])
    for name, value in parsed:
        if name in BIND_OPTIONS:
            _require(value in LOOPBACK, 'non-loopback bind '+name)  # L5 plaintext loopback only
        if name in ('--add-exclusive-node', '--daemon-address'):
            _require(value is not None and re.fullmatch(r'127\.0\.0\.1:[0-9]{4,5}', value) is not None,
                     'non-loopback peer/daemon '+name)
        _require(value is None or '0.0.0.0' not in value and '[::]' not in value, 'wildcard address')
    values = dict(parsed)
    _require(values.get('--rpc-ssl') == 'disabled' and values.get('--rpc-bind-ip') == '127.0.0.1',
             'plaintext RPC must bind 127.0.0.1')  # L5
    if kind == 'monerod':
        for name in DAEMON_REQUIRED:
            _require(name in names, 'required daemon option '+name)  # L2
        _require(values.get('--p2p-bind-ip') == '127.0.0.1' and values.get('--p2p-bind-ipv6-address') == '::1',
                 'P2P must bind loopback')
        _require(('--offline' in names) == offline, 'offline flag mismatch')
        peers = [v for n, v in parsed if n == '--add-exclusive-node']
        _require(offline or peers, 'online daemon needs explicit exclusive loopback peers')
        _require(not offline or (not peers and '--offline' in names), 'offline daemon must not name peers')
        _require(('--start-mining' in names) == mining and (not mining or values.get('--mining-threads') == '1'),
                 'mining flag/thread mismatch')
    else:
        # L1: get_tx_key/get_tx_proof/get_spend_proof/get_reserve_proof are served even
        # restricted; every wallet RPC is a loopback-only private full-key service.
        _require('--restricted-rpc' in names or signer, 'observer wallet must be restricted')
        _require(not signer or '--restricted-rpc' not in names, 'signer flag mismatch')
        # The F1-accepted restore-signer shape: empty --wallet-dir server, private 0600
        # cli.conf daemon-login, loopback daemon; the password only in the RPC body.
        _require('--wallet-dir' in names and '--password-file' not in names and '--config-file' in names and
                 '--daemon-address' in names and '--offline' not in names,
                 'topology wallet is the wallet-dir address signer only')
    return parsed


def salted(salt, value):
    """L3: shared-chain witnesses are HMAC-SHA256 under a private per-topology salt."""
    _require(type(salt) is bytes and len(salt) == 32, 'private salt')
    _require(type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None, 'native hash shape')
    return hmac.new(salt, value.encode('ascii'), hashlib.sha256).hexdigest()


REQUIRED = {
    'topology.json': ['third_seed_client', 'client_detach_rejoin'],
    'recovery.json': ['cold_backup', 'primary_loss_recovery', 'recovery_seed_continuity', 'fail_closed_both_down'],
    'backup.json': ['corrupt_incomplete_refusal', 'crashed_root_refusal', 'foreign_root_refusal'],
    'reorg.json': ['partition_reorg'],
    'persistence.json': ['full_cycle', 'manager_cycle', 'manager_restart'],
    'uptime.json': ['uptime_24h'],
    'isolation.json': ['launcher_policy', 'auth_controls', 'native_mining_bounds'],
    'resources.json': ['parent_enclosure', 'deadlines', 'disk', 'no_oom'],
    'cleanup.json': ['owned_pids_absent', 'owned_cid_absent', 'owned_staging_removed', 'lock_released',
                     'persistent_root_owner_only'],
}
DRIVER_FILES = ('topology.json', 'recovery.json', 'backup.json', 'reorg.json', 'uptime.json', 'isolation.json')
DRIVER_PERSISTENCE = ('full_cycle',)
EXCLUDED = ['wallet_payment_on_topology', 'native_L1_proof_methods', 'public_transport_tls',
    'multi_host_topology', 'operator_route_installed_custody']


def empty_rows():
    return {file: {key: {'status': 'NOT_RUN'} for key in keys} for file, keys in REQUIRED.items()}


def verdict(rows, uptime=UPTIME_SECONDS):
    if uptime == REHEARSAL_UPTIME_SECONDS:
        rest = [rows.get(file, {}).get(key, {}).get('status', 'NOT_RUN')
                for file, keys in REQUIRED.items() for key in keys if key != 'uptime_24h']
        if 'FAIL' in rest or rows['uptime.json']['uptime_24h'].get('status') != 'NOT_RUN':
            return 'FAIL'
        return 'REHEARSAL_PASS_UPTIME_NOT_RUN' if all(x == 'PASS' for x in rest) else 'INCOMPLETE'
    return _full_verdict(rows)


def _full_verdict(rows):
    states = [rows.get(file, {}).get(key, {}).get('status', 'NOT_RUN')
              for file, keys in REQUIRED.items() for key in keys]
    if 'FAIL' in states:
        return 'FAIL'
    return 'PASS_PERSISTENT_ISOLATED_TOPOLOGY_ONLY' if all(x == 'PASS' for x in states) else 'INCOMPLETE'


def shapes():
    sha = lambda x: type(x) is str and re.fullmatch('[0-9a-f]{64}', x) is not None
    integer = lambda low, high: lambda x: type(x) is int and low <= x <= high
    count = integer(2, MAX_COUNT)
    return dict(
        third_seed_client=dict(nodes=3, seeds=2, client_late_join_count=count, client_from_genesis=True,
            edges=3, client_peers=2, foreign_connections=0, tip_salted=sha),
        client_detach_rejoin=dict(detached_count=count, rejoined_count=count, advanced_blocks=integer(2, 50),
            changed_process=True, tip_salted=sha),
        cold_backup=dict(node='A', stopped_saved=True, files=integer(2, 64), count=count,
            work_bound=True, tip_salted=sha),
        primary_loss_recovery=dict(lost='A', forced_kill=True, quarantined=True, erased=False,
            lost_count=count, restored_backup_count=count, offline_attested=True, caught_up_count=count,
            missing_blocks=integer(1, 200), tip_salted=sha),
        recovery_seed_continuity=dict(seed='B', client_followed=True, mined_blocks=integer(3, 50),
            primary_down=True, tip_salted=sha),
        fail_closed_both_down=dict(seconds=integer(60, 600), client_peer_connections=0,
            foreign_connections=0, height_frozen=True, fallback=False),
        corrupt_incomplete_refusal=dict(cases=integer(8, 32), refused=integer(8, 32), started=0,
            intact_control_accepted=True, original_unchanged=True),
        crashed_root_refusal=dict(node='A', unsealed_refused=True, started=0),
        foreign_root_refusal=dict(cases=integer(3, 8), refused=integer(3, 8), started=0),
        partition_reorg=dict(isolated='A', depth=integer(2, 20), isolated_blocks=integer(2, 20),
            majority_blocks=integer(3, 40), majority_work_greater=True, alt_block_retained=True,
            majority_never_saw_isolated=True, final_agreement=3, tip_salted=sha),
        full_cycle=dict(nodes=3, offline_attested=3, manifests_verified=3, container_restarted=True,
            changed_processes=3, resumed_count=count, tip_salted=sha),
        uptime_24h=dict(seconds=integer(UPTIME_SECONDS, 2*UPTIME_SECONDS), samples=integer(280, 1000),
            faults=0, retried_samples=integer(0, 1000), max_spread=integer(0, MAX_SPREAD), blocks=integer(100, MAX_COUNT),
            node_restarts=0, final_agreement=3, tip_salted=sha),
        launcher_policy=dict(launches=integer(10, 400), refused_before_start=0, loopback_only=True,
            restricted_daemon_rpc=True, adverse_argv_refused=integer(10, 64), census_samples=integer(280, 50000)),
        auth_controls=dict(daemons=3, missing_wrong_rejected=True, fresh_login_per_launch=True),
        native_mining_bounds=dict(threads=1, light_mode=True, max_count=MAX_COUNT, final_count=count,
            external_funding=False, loopback_only=True, transactions=0),
    )
