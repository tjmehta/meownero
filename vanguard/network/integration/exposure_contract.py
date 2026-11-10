"""Closed TJS-4177 exposure-candidate contract; no native effects on import.

Milestone 3 moves one seed's P2P listener and a TLS restricted daemon RPC off
loopback, onto an owned Docker `--internal` bridge with no published host port,
and proves a client in a second network namespace against it. Every other
launch keeps the milestone-2 rules of `topology_contract.py` (L1-L6).

Fork facts this contract relies on (monero-fcmp e151643c):
- P2P TLS is hard-disabled (`net_node.inl:1090`); P2P stays plaintext Levin.
- `--rpc-ssl enabled` without key/certificate paths generates an in-memory
  RSA-4096 self-signed certificate per launch (`net_ssl.cpp:265-290`).
- A non-loopback `--rpc-bind-ip` needs `--confirm-external-bind` even with TLS
  (`rpc_args.cpp:159`); it is accepted only on the exposed seed shape below.
"""
import re

from integration import topology_contract as t

WORKLOAD = 'exposure-candidate-internal-bridge'
ISSUE = 'ee4de63c-f7ae-416f-94d6-52eea96bf3ce'  # TJS-4177
SUBNET, GATEWAY = '10.231.77.0/29', '10.231.77.1'
SEED_IP, CLIENT_IP, FOREIGN_IP = '10.231.77.2', '10.231.77.3', '10.231.77.4'
# One network namespace (container) per role. The foreign peer has its own address:
# the seed blocks a host after more than P2P_IP_FAILS_BEFORE_BLOCK (10) wrong-network
# handshakes for 24 h (net_node.inl:2687 add_host_fail), which must never hit the clients.
ROLES = {'seed': SEED_IP, 'client': CLIENT_IP, 'foreign': FOREIGN_IP}
NODES = {'seed': ('S',), 'client': ('K', 'N'), 'foreign': ('F',)}

# Seed S: exposed seed and the only miner. Client: K (first client) and N (cold
# newcomer from genesis). Foreign: F (--stagenet).
P2P = {'S': 48080, 'K': 48280, 'N': 48380, 'F': 48480}
RPC = {name: port+1 for name, port in P2P.items()}
WALLET_PORT = 48083
SEED = f'{SEED_IP}:{P2P["S"]}'
# The seed names only the client address, where nothing listens (client P2P binds
# loopback): the seed never dials beyond the owned subnet and every seed/client
# connection is client-initiated to the exposed listener.
SEED_EXCLUSIVE = f'{CLIENT_IP}:{P2P["K"]}'

UPTIME_SECONDS = 21600            # Full: 6 h exposed steady window.
REHEARSAL_UPTIME_SECONDS = 1800   # Rehearsal: same code, 30 min steady, row stays NOT_RUN.
MODES = {UPTIME_SECONDS: 32400, REHEARSAL_UPTIME_SECONDS: 10800}
SAMPLE_SECONDS = 300
MAX_COUNT = t.MAX_COUNT
MAX_SPREAD = t.MAX_SPREAD
LATE_JOIN_COUNT = 6
FOREIGN_SECONDS = 90

SEED_ALLOWED = dict(t.ALLOWED['monerod'], **{'--confirm-external-bind': False})
CLIENT_ALLOWED = dict(t.ALLOWED['monerod'])
FOREIGN_ALLOWED = {('--stagenet' if k == '--testnet' else k): v for k, v in t.ALLOWED['monerod'].items()}
SEED_FORBIDDEN = tuple(x for x in t.FORBIDDEN if x != '--confirm-external-bind')
COMMON = ('--non-interactive', '--no-igd', '--no-zmq', '--restricted-rpc', '--disable-dns-checkpoints',
          '--hide-my-port')
PIN = re.compile('[0-9a-f]{64}')


def _require(ok, message):
    if not ok:
        raise t.PolicyRefusal(message)


def check_exposed(role, argv, *, mining=False):
    """Refuse every daemon argv outside the three exposure shapes before any start.

    role 'seed': the one off-loopback shape (P2P and TLS restricted RPC on the exact
    seed bridge IP). role 'client': milestone-2 loopback client whose only exclusive
    peer is the exposed seed. role 'foreign': the client shape on --stagenet.
    """
    _require(role in ('seed', 'client', 'foreign'), 'unknown exposure role')
    _require(argv and str(argv[0]).endswith('/monerod'), 'executable/kind mismatch')
    parsed = t.options([str(x) for x in argv])
    allowed = {'seed': SEED_ALLOWED, 'client': CLIENT_ALLOWED, 'foreign': FOREIGN_ALLOWED}[role]
    names = t.allowlisted(parsed, allowed, forbidden=SEED_FORBIDDEN if role == 'seed' else t.FORBIDDEN)
    for name, value in parsed:
        _require(value is None or '0.0.0.0' not in value and '[::]' not in value and value != '::',
                 'wildcard address')
    values = dict(parsed)
    for name in COMMON+(('--stagenet',) if role == 'foreign' else ('--testnet',)):
        _require(name in names, 'required daemon option '+name)
    _require('--offline' not in names and '--in-peers' not in names, 'exposure daemons are online')
    peers = [v for n, v in parsed if n == '--add-exclusive-node']
    _require(values.get('--p2p-bind-ipv6-address') == '::1', 'IPv6 P2P stays loopback')
    if role == 'seed':
        _require(values.get('--p2p-bind-ip') == SEED_IP and values.get('--rpc-bind-ip') == SEED_IP,
                 'seed binds only its owned bridge IP')
        _require(values.get('--rpc-ssl') == 'enabled' and '--confirm-external-bind' in names,
                 'off-loopback RPC requires TLS')
        _require(values.get('--p2p-bind-port') == str(P2P['S']) and values.get('--rpc-bind-port') == str(RPC['S']),
                 'seed ports')
        _require(peers == [SEED_EXCLUSIVE], 'seed exclusive list is the owned client address only')
        _require(('--start-mining' in names) == mining and (not mining or values.get('--mining-threads') == '1'),
                 'mining flag/thread mismatch')
    else:
        _require(values.get('--p2p-bind-ip') == '127.0.0.1' and values.get('--rpc-bind-ip') == '127.0.0.1' and
                 values.get('--rpc-ssl') == 'disabled', 'client binds loopback with plaintext loopback RPC')
        _require(peers == [SEED], 'client exclusive peer is the exposed seed only')
        _require('--start-mining' not in names and '--mining-threads' not in names and not mining,
                 'clients never mine')
    return parsed


def pin(value):
    _require(type(value) is str and PIN.fullmatch(value) is not None, 'SHA-256 certificate pin shape')
    return value


REQUIRED = {
    'seed.json': ['exposed_listener', 'owner_namespace_auth', 'foreign_network_refused', 'seed_restart'],
    'seed-isolation.json': ['launcher_policy', 'native_mining_bounds'],
    'client.json': ['cold_bootstrap', 'wrong_tls_refused', 'missing_auth_refused', 'wrong_auth_refused',
                    'seed_restart_catch_up', 'client_restart_catch_up', 'steady_exposed'],
    'client-isolation.json': ['launcher_policy'],
    'foreign.json': ['foreign_peer_isolated'],
    'foreign-isolation.json': ['launcher_policy'],
    'host.json': ['network_internal', 'no_published_ports', 'distinct_namespaces'],
    'resources.json': ['parent_enclosure', 'deadlines', 'disk', 'no_oom'],
    'cleanup.json': ['owned_pids_absent', 'owned_cid_absent', 'owned_network_absent', 'owned_staging_removed',
                     'lock_released', 'persistent_root_owner_only'],
}
DRIVER_FILES = {'seed': ('seed.json', 'seed-isolation.json'), 'client': ('client.json', 'client-isolation.json'),
                'foreign': ('foreign.json', 'foreign-isolation.json')}
EXCLUDED = ['wallet_payment_on_exposed_topology', 'native_L1_proof_methods', 'p2p_tls_unsupported_by_fork',
    'second_host', 'published_host_port', 'public_dns_or_router', 'operator_route_installed_custody']


def empty_rows():
    return {file: {key: {'status': 'NOT_RUN'} for key in keys} for file, keys in REQUIRED.items()}


def verdict(rows, uptime=UPTIME_SECONDS):
    states = {(file, key): rows.get(file, {}).get(key, {}).get('status', 'NOT_RUN')
              for file, keys in REQUIRED.items() for key in keys}
    if 'FAIL' in states.values():
        return 'FAIL'
    if uptime == REHEARSAL_UPTIME_SECONDS:
        rest = [v for k, v in states.items() if k != ('client.json', 'steady_exposed')]
        if states[('client.json', 'steady_exposed')] != 'NOT_RUN':
            return 'FAIL'
        return 'REHEARSAL_PASS_STEADY_NOT_RUN' if all(x == 'PASS' for x in rest) else 'INCOMPLETE'
    return 'PASS_EXPOSURE_CANDIDATE_DEV_HOST_ONLY' if all(x == 'PASS' for x in states.values()) else 'INCOMPLETE'


def shapes():
    sha = lambda x: type(x) is str and re.fullmatch('[0-9a-f]{64}', x) is not None
    integer = lambda low, high: lambda x: type(x) is int and low <= x <= high
    count = integer(2, MAX_COUNT)
    return dict(
        exposed_listener=dict(p2p_bind='owned-bridge-ip', rpc_bind='owned-bridge-ip', rpc_tls=True,
            restricted_rpc=True, login_env_only=True, wildcard_listeners=0, loopback_listeners_only_signer=True,
            default_route=False, launches=integer(2, 8)),
        owner_namespace_auth=dict(correct_login_accepted=True, missing_rejected=True, wrong_rejected=True,
            pinned=True),
        foreign_network_refused=dict(network='stagenet', wrong_network_logged=True, seed_count_unchanged_by_foreign=True,
            foreign_connections_after=0, clients_undisturbed=2),
        seed_restart=dict(changed_process=True, sealed_and_reopened=True, new_certificate=True,
            stopped_count=count, resumed_count=count),
        launcher_policy=dict(launches=integer(1, 64), refused_before_start=0, adverse_argv_refused=integer(8, 64),
            census_samples=integer(10, 50000), foreign_connections=0),
        native_mining_bounds=dict(threads=1, light_mode=True, max_count=MAX_COUNT, final_count=count,
            external_funding=False, transactions=0),
        cold_bootstrap=dict(client_from_genesis=True, late_join_count=integer(LATE_JOIN_COUNT, MAX_COUNT),
            synced_count=count, client_initiated=True, other_namespace=True, peer_connections=1, tip_salted=sha),
        wrong_tls_refused=dict(wrong_pin_refused=True, stale_pin_refused=True, plaintext_no_http_response=True,
            request_bytes_on_refusal=0),
        missing_auth_refused=dict(status_code=401, over_pinned_tls=True, other_namespace=True),
        wrong_auth_refused=dict(status_code=401, over_pinned_tls=True, other_namespace=True),
        foreign_peer_isolated=dict(network='stagenet', foreign_count=1, foreign_genesis_differs=True,
            seconds=integer(FOREIGN_SECONDS, 600)),
        seed_restart_catch_up=dict(clients=2, reconnected=True, new_pin_accepted=True, advanced_blocks=integer(2, 50),
            tip_salted=sha),
        client_restart_catch_up=dict(detached_count=count, rejoined_count=count, advanced_blocks=integer(2, 50),
            changed_process=True, tip_salted=sha),
        steady_exposed=dict(seconds=integer(UPTIME_SECONDS, 2*UPTIME_SECONDS), samples=integer(60, 1000),
            faults=0, retried_samples=integer(0, 1000), max_spread=integer(0, MAX_SPREAD),
            blocks=integer(30, MAX_COUNT), foreign_connections=0, tip_salted=sha),
    )
