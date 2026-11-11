"""Closed TJS-4238 operator-package contract; no native effects on import.

Milestone 4 builds what activation needs without activating anything: a public
seed launch shape, a supervised restart that keeps the seal, cold backups with
retention, a timed rollback with absence checks, an outside monitor, and a
host-namespace reach test. The rehearsal runs the public seed shape on the
milestone-3 owned `--internal` bridge (no published port).

Fork facts this contract relies on (monero-fcmp e151643c):
- An online daemon with no exclusive peer dials the five hard-coded upstream
  testnet seed IPs whenever its white peer list is empty, whatever --out-peers is
  (`net_node.inl:836-842,2016`; the identity overlay changes only the port and
  NETWORK_ID). Every outbound attempt, seed dials included, returns before the
  connect when the out-peer count equals --out-peers (`net_node.inl:1541`), so a
  single public seed runs --out-peers 0 and never contacts third-party hosts.
- A peer that advertises its P2P port is pinged back (`net_node.inl:2735-2740`);
  that is an outbound connect outside --out-peers (runbook item).
- monerod has no connection-rate option (`net_node.cpp:145-165`: in/out peers,
  per-IP count and bandwidth only). The rate bound is a host firewall rule, so it
  is declared in the activation plan as an owned object with a removal command.
- Restricted RPC zeroes every connection count (`core_rpc_server.cpp:316-321`), so
  an outside monitor cannot read the seed's peer count on the public path.
- add_host_fail blocks live in memory only (`net_node.inl:266-281,346-356`); a
  supervised restart clears them. --ban-list entries are permanent per launch.
- Tiny blocks sync in batches of BLOCKS_MAX_WINDOW (100) (`cryptonote_core.cpp:929-940`),
  and every added span logs `Synced H/T` (`cryptonote_protocol_handler.inl:1821`).
"""
import ipaddress
import re

from integration import exposure_contract as x
from integration import topology_contract as t

WORKLOAD = 'operator-package-public-seed-shape'
ISSUE = '91dea72e-edd6-4632-a0f8-dc9eea683bde'  # TJS-4238
SUBNET, GATEWAY = x.SUBNET, x.GATEWAY
SEED_IP, CLIENT_IP, MONITOR_IP = x.SEED_IP, x.CLIENT_IP, '10.231.77.5'
ROLES = {'seed': SEED_IP, 'client': CLIENT_IP, 'monitor': MONITOR_IP}
# Seed S: public seed shape and the only miner. Client: K (first client) and N (the
# newcomer that joins at depth). Monitor: M, the monitor's own validating follower.
NODES = {'seed': ('S',), 'client': ('K', 'N'), 'monitor': ('M',)}
P2P = {'S': 48080, 'K': 48280, 'N': 48380, 'M': 48580}
RPC = {name: port+1 for name, port in P2P.items()}
WALLET_PORT = x.WALLET_PORT
SEED = f'{SEED_IP}:{P2P["S"]}'

# Public seed bounds (Security note 2). One public seed never dials out (see above).
IN_PEERS = (1, 64)
OUT_PEERS = 0
PER_IP = (1, 4)
RATE_PER_MINUTE = (1, 120)
BURST = (1, 60)
REHEARSAL_PEERS = dict(in_peers=16, out_peers=0, max_connections_per_ip=4)

# Supervised restart and cold backups.
BACKUPS = 3                   # Scheduled cold backups taken in a run (each one is a planned restart).
RETAIN = 2                    # Newest backups kept; older ones are pruned after each backup.
BACKUP_EVERY = 3              # Rehearsal schedule: one cold backup every 3 blocks.
LOST_BLOCKS = 2               # The crash happens at least this many blocks after the newest backup.

# Newcomer depth (Core note 1): more than one 100-block batch beyond genesis.
SYNC_BATCH = 100
NEWCOMER_COUNT = SYNC_BATCH+21
LATE_JOIN_COUNT = 6

UPTIME_SECONDS = 1800             # Full: 30 min outside-monitor window after the newcomer row.
REHEARSAL_UPTIME_SECONDS = 600    # Rehearsal: same code, 10 min window, the newcomer row stays NOT_RUN.
MODES = {UPTIME_SECONDS: 28800, REHEARSAL_UPTIME_SECONDS: 10800}
MONITOR_SAMPLE_SECONDS = 60
STATUS_MAX_AGE = 180
MAX_COUNT = t.MAX_COUNT
MAX_SPREAD = t.MAX_SPREAD
HOST_PROBE_HOLD = 5               # Seconds the host-reach probe holds an open socket for the seed census.
# Seed-log witness for --out-peers 0: at --log-level 1 (`*:INFO`, mlog.cpp:106) an attempted dial
# that fails logs `Connect failed to <addr>` (net_node.inl:1505); a seed pass that dials nobody logs
# `continuing without seeds` (net_node.inl:1984,1992). The upstream seed IPs (net_node.inl:836-842).
UPSTREAM_SEEDS = ('176.9.0.187', '192.99.8.110', '37.187.74.171', '88.99.195.15', '5.104.84.64')
DIAL_ATTEMPTED = b'Connect failed to '
SEED_PASS = b'continuing without seeds'
# Loading the seed list logs each upstream address at INFO without connecting (append_net_address,
# net_node.inl:804,819; numeric hosts, no lookup). Native rehearsal 1 (grant 716f3d3c) logged these
# lines once per launch; an upstream address anywhere else counts as a dial.
SEED_LIST = (b'Resolving node address: ', b'Added node: ')


def seed_log_witness(raw):
    """(dial attempts, upstream lines outside seed-list loading, seed passes, seed-list lines)."""
    upstream = listed = 0
    for line in raw.splitlines():
        if any(ip.encode() in line for ip in UPSTREAM_SEEDS):
            if any(marker in line for marker in SEED_LIST):
                listed += 1
            else:
                upstream += 1
    return raw.count(DIAL_ATTEMPTED), upstream, raw.count(SEED_PASS), listed

PUBLIC_FORBIDDEN = tuple(n for n in t.FORBIDDEN if n != '--confirm-external-bind')+(
    '--allow-local-ip', '--hide-my-port', '--add-exclusive-node', '--offline', '--ban-list',
    '--rpc-bind-ipv6-address', '--rpc-use-ipv6', '--p2p-use-ipv6')
PUBLIC_ALLOWED = dict({k: v for k, v in t.ALLOWED['monerod'].items() if k not in PUBLIC_FORBIDDEN},
                      **{'--out-peers': True, '--confirm-external-bind': False})
PUBLIC_REQUIRED = ('--testnet', '--non-interactive', '--no-igd', '--no-zmq', '--restricted-rpc',
                   '--disable-dns-checkpoints', '--in-peers', '--out-peers', '--max-connections-per-ip')
RPC_VARIANTS = ('private', 'operator-tls')  # A login-less public RPC needs its own Privacy decision.
_INTEGER = re.compile('[0-9]{1,5}')


def _require(ok, message):
    if not ok:
        raise t.PolicyRefusal(message)


def _bounded(value, bounds):
    return type(value) is int and bounds[0] <= value <= bounds[1]


def bind_address(value):
    """A specific unicast IPv4 interface address: never wildcard, loopback, link-local or multicast."""
    _require(type(value) is str, 'bind address shape')
    try:
        address = ipaddress.IPv4Address(value)
    except (ipaddress.AddressValueError, TypeError, ValueError):
        raise t.PolicyRefusal('bind address shape') from None
    _require(not (address.is_unspecified or address.is_loopback or address.is_link_local or
                  address.is_multicast or address.is_reserved), 'bind address class')
    return str(address)


# ---- owned objects that only activation creates ------------------------------------------
# Each class has a recorded removal command and an absence check run from outside the
# seed. The check fails closed: without a vantage it returns UNVERIFIED, never ABSENT.
OBJECT_CLASSES = {
    'port-rule': dict(
        create=['nft', '-f', '<reviewed-rule-file>'],
        rule=('table inet meownero_seed { chain input { type filter hook input priority 0; policy accept; '
              'iifname "<interface>" tcp dport 48080 ct state new limit rate over <rate>/minute burst <burst> '
              'packets drop; } }'),
        removal=['nft', 'delete', 'table', 'inet', 'meownero_seed'],
        absence='outside-tcp-connect'),
    'dns-record': dict(
        create=['<dns-provider>', 'create', '<name>', 'A', '<public-ip>', '<ttl>'],
        removal=['<dns-provider>', 'delete', '<name>', 'A'],
        absence='outside-resolver-lookup'),
}
ABSENCE = ('ABSENT', 'PRESENT', 'UNVERIFIED')


def plan(bind_ip, *, rpc='operator-tls', in_peers=16, max_connections_per_ip=4, rate=30, burst=10,
         objects=None):
    """The activation plan a public seed launch is checked against (no native effect)."""
    return dict(schema='meownero-public-seed-plan/1', bind_ip=bind_ip, p2p_port=P2P['S'], rpc_port=RPC['S'],
                rpc=rpc, in_peers=in_peers, out_peers=OUT_PEERS, max_connections_per_ip=max_connections_per_ip,
                connection_rate=dict(new_per_minute=rate, burst=burst, owner='port-rule'),
                objects=objects if objects is not None else {k: dict(created=False) for k in OBJECT_CLASSES})


def check_plan(value):
    _require(type(value) is dict and value.get('schema') == 'meownero-public-seed-plan/1', 'plan schema')
    _require(set(value) == {'schema', 'bind_ip', 'p2p_port', 'rpc_port', 'rpc', 'in_peers', 'out_peers',
                            'max_connections_per_ip', 'connection_rate', 'objects'}, 'plan keys')
    bind_address(value['bind_ip'])
    _require(value['p2p_port'] == P2P['S'] and value['rpc_port'] == RPC['S'], 'plan ports')
    _require(value['rpc'] in RPC_VARIANTS, 'plan RPC variant')
    _require(_bounded(value['in_peers'], IN_PEERS) and value['out_peers'] == OUT_PEERS and
             _bounded(value['max_connections_per_ip'], PER_IP), 'plan peer bounds')
    rate = value['connection_rate']
    _require(type(rate) is dict and set(rate) == {'new_per_minute', 'burst', 'owner'} and
             _bounded(rate['new_per_minute'], RATE_PER_MINUTE) and _bounded(rate['burst'], BURST) and
             rate['owner'] == 'port-rule', 'plan connection-rate bound')
    objects = value['objects']
    _require(type(objects) is dict and set(objects) == set(OBJECT_CLASSES), 'plan owned-object classes')
    for item in objects.values():
        _require(type(item) is dict and set(item) == {'created'} and item['created'] is False,
                 'this candidate creates no port rule or DNS record')
    return value


def check_public_seed(argv, value, *, mining=False):
    """Refuse every public-seed daemon argv that does not match the checked activation plan."""
    check_plan(value)
    _require(argv and str(argv[0]).endswith('/monerod'), 'executable/kind mismatch')
    parsed = t.options([str(a) for a in argv])
    names = t.allowlisted(parsed, PUBLIC_ALLOWED, forbidden=PUBLIC_FORBIDDEN)
    for name, item in parsed:
        _require(item is None or '0.0.0.0' not in item and '[::]' not in item and item != '::', 'wildcard address')
    values = dict(parsed)
    for name in PUBLIC_REQUIRED:
        _require(name in names, 'required public seed option '+name)
    for name in ('--in-peers', '--out-peers', '--max-connections-per-ip'):
        _require(_INTEGER.fullmatch(values[name]) is not None, 'integer option '+name)
    _require(int(values['--in-peers']) == value['in_peers'] and int(values['--out-peers']) == value['out_peers'] and
             int(values['--max-connections-per-ip']) == value['max_connections_per_ip'], 'peer bounds differ from plan')
    _require(values.get('--p2p-bind-ip') == value['bind_ip'] and values.get('--p2p-bind-port') == str(P2P['S']),
             'P2P binds the planned interface')
    _require(values.get('--p2p-bind-ipv6-address') == '::1', 'IPv6 P2P stays loopback')
    _require(values.get('--rpc-bind-port') == str(RPC['S']), 'RPC port')
    if value['rpc'] == 'private':  # Recommended: operators reach RPC over their own tunnel.
        _require(values.get('--rpc-bind-ip') == '127.0.0.1' and values.get('--rpc-ssl') == 'disabled' and
                 '--confirm-external-bind' not in names, 'private RPC binds loopback in plaintext')
    else:
        _require(values.get('--rpc-bind-ip') == value['bind_ip'] and values.get('--rpc-ssl') == 'enabled' and
                 '--confirm-external-bind' in names, 'operator RPC is TLS on the planned interface')
    _require(('--start-mining' in names) == mining and (not mining or values.get('--mining-threads') == '1'),
             'mining flag/thread mismatch')
    return parsed


def absence(kind, probe):
    """Fail-closed absence verdict for one owned object class.

    probe() returns True when the object is observed present, False when an outside
    vantage observed it absent, and None when no vantage exists. Any error is UNVERIFIED.
    """
    _require(kind in OBJECT_CLASSES, 'unknown owned object class')
    try:
        seen = probe()
    except Exception:
        return 'UNVERIFIED'
    return {True: 'PRESENT', False: 'ABSENT'}.get(seen, 'UNVERIFIED') if type(seen) is bool or seen is None \
        else 'UNVERIFIED'


REQUIRED = {
    'seed.json': ['public_seed_shape', 'owner_namespace_auth', 'planned_restart', 'cold_backup_retention',
                  'crash_refused_root', 'crash_recovery'],
    'seed-isolation.json': ['launcher_policy', 'native_mining_bounds'],
    'client.json': ['cold_bootstrap', 'follows_restarts', 'newcomer_depth'],
    'client-isolation.json': ['launcher_policy'],
    'monitor.json': ['outside_pin', 'outside_tip', 'outside_peer_count'],
    'monitor-isolation.json': ['launcher_policy'],
    'host.json': ['network_internal', 'no_published_ports', 'distinct_namespaces', 'host_reach'],
    'rollback.json': ['seed_sealed_on_stop', 'owned_objects_absent', 'future_objects_fail_closed',
                      'rollback_timing'],
    'resources.json': ['parent_enclosure', 'deadlines', 'disk', 'no_oom'],
    'cleanup.json': ['owned_pids_absent', 'owned_cid_absent', 'owned_network_absent', 'owned_staging_removed',
                     'lock_released', 'persistent_root_owner_only'],
}
DRIVER_FILES = {'seed': ('seed.json', 'seed-isolation.json'), 'client': ('client.json', 'client-isolation.json'),
                'monitor': ('monitor.json', 'monitor-isolation.json')}
REHEARSAL_NOT_RUN = (('client.json', 'newcomer_depth'),)
EXCLUDED = {  # NOT_RUN by design, with the reason recorded in every receipt.
    'monitor_different_uid': 'needs a second uid; this issue creates no uid (the monitor runs in its own namespace as the same uid)',
    'monitor_different_host': 'needs a second host; no rented or second host on this issue',
    'dedicated_seed_uid': 'needs a dedicated uid; this issue creates no uid',
    'published_host_port': 'no host port is published to the internet on this issue',
    'public_dns_or_router': 'no DNS, router or firewall change on this issue',
    'port_rule_created': 'the port rule (connection-rate bound) is an activation object; only its removal and absence check are built',
    'dns_record_created': 'the DNS record is an activation object; only its removal and absence check are built',
    'wallet_payment_on_exposed_topology': 'excluded by the issue; F1 covers payment',
    'p2p_tls_unsupported_by_fork': 'P2P TLS is hard-disabled in the fork (net_node.inl:1090)',
    'login_less_public_rpc': 'a separate Privacy/Cryptography decision',
}


def empty_rows():
    return {file: {key: {'status': 'NOT_RUN'} for key in keys} for file, keys in REQUIRED.items()}


def verdict(rows, uptime=UPTIME_SECONDS):
    states = {(file, key): rows.get(file, {}).get(key, {}).get('status', 'NOT_RUN')
              for file, keys in REQUIRED.items() for key in keys}
    if 'FAIL' in states.values():
        return 'FAIL'
    if uptime == REHEARSAL_UPTIME_SECONDS:
        if any(states[k] != 'NOT_RUN' for k in REHEARSAL_NOT_RUN):
            return 'FAIL'
        rest = [v for k, v in states.items() if k not in REHEARSAL_NOT_RUN]
        return 'REHEARSAL_PASS_NEWCOMER_DEPTH_NOT_RUN' if all(v == 'PASS' for v in rest) else 'INCOMPLETE'
    return 'PASS_OPERATOR_PACKAGE_DEV_HOST_ONLY' if all(v == 'PASS' for v in states.values()) else 'INCOMPLETE'


def shapes():
    sha = lambda v: type(v) is str and re.fullmatch('[0-9a-f]{64}', v) is not None
    integer = lambda low, high: lambda v: type(v) is int and low <= v <= high
    count = integer(2, MAX_COUNT)
    flag = lambda v: type(v) is bool
    return dict(
        public_seed_shape=dict(rpc='operator-tls', in_peers=REHEARSAL_PEERS['in_peers'], out_peers=0,
            max_connections_per_ip=REHEARSAL_PEERS['max_connections_per_ip'], allow_local_ip=False,
            hide_my_port=False, exclusive_peers=0, wildcard_listeners=0, plan_checked=True, launches=integer(2, 16),
            dial_attempt_lines=0, upstream_dial_lines=0, seed_pass_lines=integer(1, 10**8),
            seed_list_lines=integer(0, 10**6)),
        owner_namespace_auth=dict(correct_login_accepted=True, missing_rejected=True, wrong_rejected=True,
            pinned=True),
        planned_restart=dict(sealed=True, attested_against_seal=True, changed_process=True, new_certificate=True,
            peers_reconnected=True, stopped_count=count, resumed_count=count, restarts=integer(BACKUPS, 16)),
        cold_backup_retention=dict(backups_taken=BACKUPS, retained=RETAIN, pruned=BACKUPS-RETAIN,
            source_attested=True, copy_attested=True, owner_only=True, schedule_blocks=BACKUP_EVERY),
        crash_refused_root=dict(killed='SIGKILL-exact-identity', root_attest='refused', reopen_refused=True,
            launches_unchanged=True, quarantined=True, quarantine_owner_only=True, reopened_from_quarantine=False),
        crash_recovery=dict(restored_backup='newest', restore_attested=True, changed_process=True,
            backup_count=count, crash_count=count, recovered_count=count, lost_blocks=integer(LOST_BLOCKS, 50),
            peers_reconnected=True, tip_salted=sha),
        launcher_policy=dict(launches=integer(1, 64), refused_before_start=0, adverse_argv_refused=integer(8, 128),
            census_samples=integer(10, 100000), foreign_connections=0, planned_edges=lambda v: type(v) is dict and
            set(v) <= {'client', 'monitor', 'host', 'K', 'N', 'M'} and all(type(n) is int and 0 <= n <= 64
                                                                       for n in v.values())),
        native_mining_bounds=dict(threads=1, light_mode=True, max_count=MAX_COUNT, final_count=count,
            external_funding=False, transactions=0),
        cold_bootstrap=dict(client_from_genesis=True, late_join_count=integer(LATE_JOIN_COUNT, MAX_COUNT),
            synced_count=count, client_initiated=True, other_namespace=True, peer_connections=1, tip_salted=sha),
        follows_restarts=dict(seed_launches_followed=integer(BACKUPS+2, 32), client_process_unchanged=True,
            recovered_tip_followed=True, tip_salted=sha),
        newcomer_depth=dict(join_count=integer(NEWCOMER_COUNT, MAX_COUNT), batch_size=SYNC_BATCH,
            batches_needed=integer(2, 64), synced_log_lines=integer(2, 10000), synced_count=count,
            other_namespace=True, tip_salted=sha),
        outside_pin=dict(out_of_band=True, exchange_mounted=False, matched_samples=integer(2, 1000),
            wrong_pin_alarm=True, request_bytes_before_pin=0, credential_held=False),
        outside_tip=dict(follower_validated=True, samples=integer(2, 1000), max_spread=integer(0, MAX_SPREAD),
            agreeing_samples=integer(1, 1000), tip_salted=sha),
        outside_peer_count=dict(public_path_count='unavailable-restricted-rpc', source='operator-status-channel',
            inbound_peak=integer(1, 64), in_peers_bound=REHEARSAL_PEERS['in_peers'], own_edge_seen=True,
            status_max_age=integer(0, STATUS_MAX_AGE)),
        network_internal=dict(internal=True, subnet_prefix=29, attached=3, external_route=False),
        no_published_ports=dict(containers=3, port_bindings=0, publish_all=False),
        distinct_namespaces=dict(namespaces=3, role_ips_match=True),
        host_reach=dict(p2p=lambda v: v in ('connected', 'refused', 'unreachable', 'timeout'),
            rpc=lambda v: v in ('connected', 'refused', 'unreachable', 'timeout'), bytes_sent=0,
            same_uid_boundary=flag, probe='host-namespace-tcp-connect'),
        seed_sealed_on_stop=dict(stopped_saved=True, manifest_matches=True, attested_offline=True),
        owned_objects_absent=dict(containers=3, network=True, route=True, listener_from_host=True),
        # Nothing was created and no outside vantage exists on the dev host: both checks must
        # fail closed (UNVERIFIED), never claim ABSENT.
        future_objects_fail_closed=dict(classes=2, created=0, port_rule='UNVERIFIED', dns_record='UNVERIFIED',
            removal_commands_recorded=True),
        rollback_timing=dict(seconds=lambda v: type(v) in (int, float) and 0 < v < 600, steps=integer(4, 16)),
    )
