#!/usr/bin/env python3
"""TJS-4238 operator-package driver. Requires an exact runtime grant.

Runs once per container on the owned `--internal` bridge, in role `seed`, `client`
or `monitor` (read from /out/control/role).

- seed: node S in the public seed shape (no --allow-local-ip, --hide-my-port or
  exclusive peer; explicit --in-peers, --out-peers 0, --max-connections-per-ip;
  TLS operator RPC on the bridge IP). Its driver is the supervisor: every
  scheduled cold backup is a planned restart (stop and seal, attest the root
  against the seal, copy and attest the backup, prune to the retention, reopen).
  A crash (SIGKILL) leaves an unsealed root: the supervisor refuses it, refuses a
  reopen, quarantines it, restores the newest attested backup and reopens.
- client: K (first client) follows every seed launch; N, the newcomer, joins at
  depth (full mode: more than one 100-block sync batch).
- monitor: M, the monitor's own validating follower, plus the outside-monitor
  checks. The monitor container has no exchange mount: the pin and the seed's
  operator status reach it only through the manager (the operator channel).

On SIGTERM in the `serving` step every role stops and seals its nodes, writes
its last rows and exits 0: that is the planned rollback. Any other stop fails.
"""
import contextlib
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import profile_contract as c
from integration import exposure_contract as x
from integration import exposure_driver as ed
from integration import operator_contract as o
from integration import outside_monitor as om
from integration import topology_contract as t
from integration import topology_driver as td

d = td.d
CONTROL = Path('/out/control')
STATE = 'operator-state.json'
STEPS = {'seed': ('new', 'exposed', 'restarted', 'recovered', 'serving'),
         'client': ('new', 'bootstrapped', 'newcomer', 'serving'),
         'monitor': ('new', 'following', 'serving')}
SYNCED = b'Synced '


def classify(role, owned, routes):
    """Pure census rules for one namespace. owned: [(node or None, socket tuple)].

    Seed P2P accepts from the client, monitor and (planned host-reach probe) gateway
    addresses; seed RPC from the monitor (pin handshakes) and the gateway probe.
    Client and monitor nodes connect out to the seed P2P only. Same-namespace
    driver RPC is ignored; every other socket, and any UDP socket, is foreign.
    """
    ed.classify(role if role == 'seed' else 'client', [], routes)  # Route rules only.
    if role == 'seed':
        listen = {(o.SEED_IP, o.P2P['S']), (o.SEED_IP, o.RPC['S']), ('127.0.0.1', o.P2P['S']),
                  ('127.0.0.1', o.RPC['S']), ('127.0.0.1', o.WALLET_PORT)}  # Loopback: the private signer launch.
    else:
        listen = {('127.0.0.1', port) for n in o.NODES[role] for port in (o.P2P[n], o.RPC[n])}
    p2p_from = {o.CLIENT_IP: 'client', o.MONITOR_IP: 'monitor', o.GATEWAY: 'host'}
    rpc_from = {o.MONITOR_IP: None, o.GATEWAY: 'host'}
    edges, foreign = {}, 0
    for node, (kind, state, lip, lport, rip, rport) in owned:
        if kind.startswith('udp'):
            foreign += 1
        elif state == '0A':
            foreign += (lip, lport) not in listen and lip != '::1'
        elif state != '01':
            continue
        elif role == 'seed' and (lip, lport) == (o.SEED_IP, o.P2P['S']) and rip in p2p_from:
            edges[p2p_from[rip]] = edges.get(p2p_from[rip], 0)+1
        elif role == 'seed' and (lip, lport) == (o.SEED_IP, o.RPC['S']) and rip in rpc_from:
            if rpc_from[rip]:
                edges['host'] = edges.get('host', 0)+1
        elif role != 'seed' and lip == o.ROLES[role] and (rip, rport) == (o.SEED_IP, o.P2P['S']) and \
                lport not in o.P2P.values():
            edges[node] = edges.get(node, 0)+1
        elif lip == rip or lip in ('127.0.0.1', '::1') and rip in ('127.0.0.1', '::1'):
            continue
        else:
            foreign += 1
    return edges, foreign


def pid_absent(pid):
    return not Path(f'/proc/{pid}').exists()


def owner_only(root):
    for path in [root, *root.rglob('*')]:
        info = path.lstat()
        c.require(info.st_uid == os.getuid() and not path.is_symlink() and
                  (stat.S_ISDIR(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o700 or
                   stat.S_ISREG(info.st_mode) and not stat.S_IMODE(info.st_mode) & 0o077), 'owner-only tree')
    return True


class Operator(ed.Exposure):
    """Milestone-3 node lifecycle with the public seed shape, supervision and the monitor."""
    def __init__(self, role, private=None, public=None, control=None, exchange=None):
        c.require(role in o.ROLES, 'unknown operator role')
        self.role = role
        self.private, self.public = private or d.PRIVATE, public or d.PUBLIC
        self.control, self.exchange = control or CONTROL, exchange or ed.EXCHANGE
        self.binaries = {name: c.digest((d.BIN/name).read_bytes()) for name in
                         ('monerod', 'monero-wallet-cli', 'monero-wallet-rpc')}
        c.require(not (self.private/STATE).exists(), 'unplanned restart refuses')
        self.rpc, self.pins, self.bound, self.light = {}, {}, {}, []
        self.launches = self.adverse_argv = self.census_samples = self.foreign_peak = 0
        self.public_launches = 0
        self.last = {}
        self.planned = {}
        self.plan = o.check_plan(o.plan(o.SEED_IP, **{k: v for k, v in o.REHEARSAL_PEERS.items()
                                                      if k != 'out_peers'}))
        self.salt = os.urandom(32)
        td.private_write(self.private/'salt', self.salt)
        self.state = dict(schema='meownero-operator-state/1', role=role, phase='new', address=None,
                          rows={f: o.empty_rows()[f] for f in o.DRIVER_FILES[role]}, seals={})
        self.step = 'new'
        self.save()

    # ---- persistence, rows and exchange ------------------------------------------
    def save(self):
        self.state['counters'] = dict(launches=self.launches, adverse_argv=self.adverse_argv,
            census=self.census_samples, foreign=self.foreign_peak, light=self.light, planned=self.planned)
        td.private_write(self.private/STATE, c.canonical(self.state))

    def row(self, file, key, **witness):
        c.require(file in o.DRIVER_FILES[self.role] and key in o.REQUIRED[file], 'unknown operator row')
        self.state['rows'][file][key] = dict(status='PASS', **witness)
        self.save()

    def publish(self, phase=None):
        for file in o.DRIVER_FILES[self.role]:
            (self.public/file).write_text(json.dumps(self.state['rows'][file], indent=2)+'\n')
        self.heartbeat(phase)

    def say(self, step, **data):
        order = STEPS[self.role]
        c.require(step == 'failed' or step in order and order.index(step) >= order.index(self.step), 'step order')
        self.step = step if step != 'failed' else self.step
        value = dict(role=self.role, step=step, unix=time.time(), **data)
        if self.role == 'seed':
            if 'S' in self.rpc and self.public_launches:
                height, top, _ = self.info('S')
                self.last = dict(count=height, top=top, launch=self.public_launches)
            value.update(self.last)  # While S is down (restart, crash) the last published tip stands.
        if self.role == 'client' and 'K' in self.rpc:
            height, top, _ = self.info('K')
            value.update(k_count=height, k_top=top)
        if self.role != 'monitor':  # The monitor has no exchange mount.
            td.private_write(self.exchange/(self.role+'.json'), (json.dumps(value)+'\n').encode())
        self.heartbeat(step, value.get('count', value.get('k_count', 0)))

    def hear(self, role):
        c.require(self.role != 'monitor', 'the monitor never reads the exchange')
        try:
            value = json.loads((self.exchange/(role+'.json')).read_bytes())
        except FileNotFoundError:
            return None
        c.require(value.get('role') == role, 'exchange identity')
        c.require(value['step'] != 'failed', 'peer role failed')
        return value

    def reached(self, role, step):
        value = self.hear(role)
        return value if value and STEPS[role].index(value['step']) >= STEPS[role].index(step) else None

    def until(self, role, step, seconds):
        end = time.monotonic()+d.budget(seconds)
        while time.monotonic() < end:
            value = self.reached(role, step)
            if value:
                return value
            for other in ('seed', 'client'):
                if other != self.role:
                    self.hear(other)
            self.census()
            self.say(self.step, **self.state.get('said', {}))
            time.sleep(d.budget(2))
        raise TimeoutError('operator step deadline '+step)

    def wait(self, check, seconds):
        """Topology.wait, also republishing this role's tip so the other roles can follow it."""
        end = time.monotonic()+d.budget(seconds)
        while time.monotonic() < end:
            value = check()
            if value:
                return value
            self.census()
            self.say(self.step, **self.state.get('said', {}))
            time.sleep(d.budget(2))
        raise TimeoutError('operator milestone deadline')

    def status(self, edges):
        """The seed supervisor's operator status (the manager relays it; never public)."""
        height, top, _ = self.info('S')
        value = dict(count=height, top=top, inbound=dict(edges), launch=self.public_launches, step=self.step,
                     unix=int(time.time()))
        td.private_write(self.control/'status.json', (json.dumps(value)+'\n').encode())

    # ---- native processes --------------------------------------------------------
    def daemon_argv(self, name, root, *, mining=False, private=False):
        argv = [str(d.BIN/'monerod'), '--testnet', '--data-dir', str(root), '--non-interactive', '--no-igd']
        if name == 'S' and not private:  # The public seed shape.
            argv += ['--disable-dns-checkpoints', '--check-updates', 'disabled', '--max-concurrency', '1',
                '--no-zmq', '--rpc-ssl', 'enabled', '--restricted-rpc', '--confirm-external-bind',
                '--p2p-bind-ip', o.SEED_IP, '--p2p-bind-ipv6-address', '::1', '--p2p-bind-port', str(o.P2P['S']),
                '--rpc-bind-ip', o.SEED_IP, '--rpc-bind-port', str(o.RPC['S']),
                '--in-peers', str(self.plan['in_peers']), '--out-peers', str(self.plan['out_peers']),
                '--max-connections-per-ip', str(self.plan['max_connections_per_ip']),
                '--log-level', '1', '--log-file', str(root/'native.log')]
        else:  # Milestone-2 private launch, or the milestone-3 client shape toward the seed.
            argv += ['--allow-local-ip', '--disable-dns-checkpoints', '--check-updates', 'disabled',
                '--hide-my-port', '--max-concurrency', '1', '--no-zmq', '--rpc-ssl', 'disabled', '--restricted-rpc',
                '--p2p-bind-ip', '127.0.0.1', '--p2p-bind-ipv6-address', '::1', '--p2p-bind-port', str(o.P2P[name]),
                '--rpc-bind-ip', '127.0.0.1', '--rpc-bind-port', str(o.RPC[name]), '--max-connections-per-ip', '4',
                '--log-level', '1', '--log-file', str(root/'native.log')]
            argv += ['--offline'] if private else ['--add-exclusive-node', o.SEED]
        if mining:
            argv += ['--start-mining', self.state['address'], '--mining-threads', '1']
        return argv

    def check(self, name, argv, *, mining=False, private=False):
        if private:
            return t.check_argv('monerod', argv, offline=True)
        if name == 'S':
            return o.check_public_seed(argv, self.plan, mining=mining)
        return x.check_exposed('client', argv, mining=mining)

    def attest(self, root, seal):
        """Offline attestation: the stopped root equals its last seal (manifest, digests, modes)."""
        c.root_manifest(root, seal)
        d.released(root)
        return True

    def start(self, name, *, mining=False, private=False, fresh=False):
        c.require(name in o.NODES[self.role], 'node/role mismatch')
        c.require(f'node{name}' not in self.running(), 'node already running')
        root = self.root(name)
        argv = self.daemon_argv(name, root, mining=mining, private=private)
        self.check(name, argv, mining=mining, private=private)  # Refuse before any root/process effect.
        if fresh:
            c.require(not root.exists(), 'fresh node root already exists')
            root.mkdir(mode=0o700)
            manifest = dict(d.creation('daemon', self.binaries), stopped_saved=False)
        else:
            seal = d.SAVED[str(root)]
            self.attest(root, seal)
            self.state['seals'][name] = seal
            manifest = dict(seal, stopped_saved=False)
        (root/'creation.json').write_bytes(c.canonical(manifest))
        os.chmod(root/'creation.json', 0o600)
        d.SAVED.pop(str(root), None)
        login = 'node:'+os.urandom(24).hex()  # Fresh per launch; memory and child environment only.
        env = dict(d.ENV, RPC_LOGIN=login, MONERO_RANDOMX_UMASK='4')
        d.launch(f'node{name}', argv, root, env)
        exposed = name == 'S' and not private
        self.bound[name] = o.SEED_IP if exposed else '127.0.0.1'
        self.launches += 1
        self.light.append(env['MONERO_RANDOMX_UMASK'] == '4')
        if exposed:
            def listening():
                sock, presented = ed.peer_pin(o.SEED_IP, o.RPC['S'])
                sock.close()
                return presented
            self.pins['S'] = d.wait(listening, 120)
            rpc = ed.TLSRPC(o.SEED_IP, o.RPC['S'], self.pins['S'], login)
        else:
            rpc = d.RPC(o.RPC[name], login)
        d.wait(lambda: rpc.call('get_info'), 120)
        self.rpc[name] = rpc
        self.save()
        return rpc

    def absent(self, name):
        host = self.bound[name]
        for port in (o.P2P[name], o.RPC[name]):
            with ed.socket.socket() as sock:
                sock.settimeout(d.budget(1))
                c.require(sock.connect_ex((host, port)) != 0, 'listener remains')

    def lose(self, name):
        """Crash: SIGKILL with exact PID identity; the root stays unsealed."""
        process, owned = d.PROCS[f'node{name}']
        c.require(process.poll() is None, 'lost node already exited')
        c.stop_identity(owned, d.identity(process.pid))
        process.send_signal(signal.SIGKILL)
        process.wait(timeout=d.budget(10))
        c.require(pid_absent(process.pid), 'killed PID not absent')
        self.absent(name)
        self.rpc.pop(name, None)
        self.save()
        return owned

    # ---- census ------------------------------------------------------------------
    def census(self):
        self.census_samples += 1
        table = ed.socket_table()
        owned = []
        for name, (process, _) in list(d.PROCS.items()):
            if process.poll() is not None:
                continue
            for fd in Path(f'/proc/{process.pid}/fd').iterdir():
                with contextlib.suppress(FileNotFoundError):
                    target = os.readlink(fd)
                    if target.startswith('socket:[') and target[8:-1] in table:
                        owned.append((name[4:] if name.startswith('node') else None, table[target[8:-1]]))
        edges, foreign = classify(self.role, owned, Path('/proc/net/route').read_text().splitlines()[1:])
        for node in self.rpc:
            c.require(d.PROCS[f'node{node}'][0].poll() is None, 'unexpected native exit')
        self.foreign_peak = max(self.foreign_peak, foreign)
        for key, value in edges.items():
            self.planned[key] = max(self.planned.get(key, 0), value)
        return edges, foreign

    # ---- adverse launcher policy --------------------------------------------------
    def argv_controls(self):
        name = o.NODES[self.role][0]
        saved, self.state['address'] = self.state['address'], '9'*95  # Policy fixtures only.
        base = self.daemon_argv(name, self.root(name), mining=name == 'S')
        self.state['address'] = saved
        def swap(option, value):
            argv = list(base)
            argv[argv.index(option)+1] = value
            return argv
        cases = [swap('--rpc-bind-ip', '0.0.0.0'), swap('--p2p-bind-ip', '0.0.0.0'),
            swap('--p2p-bind-ipv6-address', '::'), base+['--public-node'], base+['--public-nod'],
            [a for a in base if a != '--restricted-rpc'], base+['--rpc-login', 'a:b'], base+['--seed-node', o.SEED],
            base+['--disable-rpc-login'], base+['--rpc-restricted-bind-port', '48089'], base+['--add-peer', o.SEED],
            base+['--rpc-ssl-allow-any-cert'], base+['--add-priority-node', o.SEED]]
        if name == 'S':
            check = lambda argv: o.check_public_seed(argv, self.plan, mining=True)
            cases += [swap('--rpc-ssl', 'disabled'), swap('--rpc-bind-ip', o.CLIENT_IP),
                swap('--p2p-bind-ip', o.GATEWAY), swap('--p2p-bind-ip', '127.0.0.1'),
                [a for a in base if a != '--confirm-external-bind'], base+['--allow-local-ip'], base+['--hide-my-port'],
                base+['--add-exclusive-node', o.SEED], swap('--out-peers', '8'), swap('--in-peers', '-1'),
                swap('--in-peers', '65'), swap('--max-connections-per-ip', '9'), base+['--ban-list', '/out/x'],
                base+['--offline'], swap('--mining-threads', '2'),
                [a for a in base if a not in ('--out-peers', str(self.plan['out_peers']))]]
        else:
            check = lambda argv: x.check_exposed('client', argv)
            cases += [swap('--add-exclusive-node', '10.0.0.1:18080'), swap('--p2p-bind-ip', o.ROLES[self.role]),
                swap('--rpc-ssl', 'enabled'), base+['--start-mining', '9'*95, '--mining-threads', '1'],
                base+['--confirm-external-bind'], base+['--add-exclusive-node', o.SEED]]
        count = len(d.PROCS)
        for argv in cases:
            try:
                check(argv)
            except t.PolicyRefusal:
                self.adverse_argv += 1
            else:
                raise ValueError('adverse operator argv accepted')
        private = self.daemon_argv(name, self.root(name), private=True)
        for argv in (private+['--confirm-external-bind'], [a if a != '127.0.0.1' else o.SEED_IP for a in private]):
            try:
                t.check_argv('monerod', argv, offline=True)
            except t.PolicyRefusal:
                self.adverse_argv += 1
            else:
                raise ValueError('adverse private argv accepted')
        c.require(len(d.PROCS) == count, 'refused argv started a process')
        self.save()

    # ---- seed role: public shape and supervisor ---------------------------------------
    def open_public(self):
        before = self.pins.get('S')
        self.start('S', mining=True)
        self.listeners()
        self.confirm_pin()
        c.require(self.pins['S'] != before, 'seed certificate did not change')
        self.public_launches += 1
        td.private_write(self.control/'pin', (self.pins['S']+'\n').encode())  # Operator channel only.
        return self.pins['S']

    def reconnected(self, client=1):
        edges = self.census()[0]
        return edges if edges.get('client', 0) >= client and edges.get('monitor', 0) >= 1 else None

    def planned_restart(self, number):
        root = self.root('S')
        stopped = self.info('S')
        process = d.PROCS['nodeS'][1]
        self.stop('S')                                   # Graceful stop, then d.seal().
        seal = d.SAVED[str(root)]
        self.attest(root, seal)                          # The root equals the seal it just got.
        backups = self.private/'backups'
        target = backups/f'{number:04d}'
        target.mkdir(mode=0o700)
        d.copy_stopped(root, target/'S')                 # Attests the source and the copy.
        kept = sorted(p for p in backups.iterdir() if p.is_dir())
        for old in kept[:-o.RETAIN]:
            d.SAVED.pop(str(old/'S'), None)
            shutil.rmtree(old)
        retained = sorted(p.name for p in backups.iterdir())
        c.require(retained == [f'{n:04d}' for n in range(max(1, number-o.RETAIN+1), number+1)], 'backup retention')
        owner_only(backups)
        self.open_public()                               # start() attests the root against the seal again.
        resumed = self.info('S')
        c.require(d.PROCS['nodeS'][1] != process and resumed[0] >= stopped[0] and
                  self.known('S', stopped[1]) is False, 'planned restart identity')
        self.wait(self.reconnected, 600)
        self.state.setdefault('backups', []).append(dict(number=number, count=stopped[0]))
        return stopped[0], resumed[0]

    def crash_and_recover(self):
        root = self.root('S')
        crashed = self.info('S')
        newest = self.state['backups'][-1]
        c.require(crashed[0]-newest['count'] >= o.LOST_BLOCKS, 'crash precedes the lost-block margin')
        launches = self.launches
        self.lose('S')                                   # SIGKILL: the root stays unsealed.
        seal = self.state['seals']['S']
        try:
            self.attest(root, seal)
        except ValueError:
            refused = True
        else:
            raise ValueError('crashed root attested')
        d.SAVED[str(root)] = seal                        # A reopen attempt uses the last seal record...
        try:
            self.start('S', mining=True)
        except ValueError:
            reopen_refused = 'nodeS' not in self.running()
        else:
            raise ValueError('crashed root reopened')
        finally:
            d.SAVED.pop(str(root), None)
        c.require(self.launches == launches, 'refused reopen launched a process')
        quarantine = self.private/'quarantine'/'S-0001'
        os.rename(root, quarantine)                      # Never opened again; kept owner-only for review.
        owner_only(self.private/'quarantine')
        backup = self.private/'backups'/f'{newest["number"]:04d}'/'S'
        d.copy_stopped(backup, root)                     # Attests the backup and the restored copy.
        self.open_public()
        def caught_up():
            edges = self.reconnected()
            client = self.hear('client')
            seed = self.info('S')
            return seed if edges and client and client.get('k_count') == seed[0] and \
                client.get('k_top') == seed[1] and seed[0] >= crashed[0] else None
        recovered = self.wait(caught_up, 1800)
        self.row('seed.json', 'crash_refused_root', killed='SIGKILL-exact-identity', root_attest='refused',
                 reopen_refused=refused and reopen_refused, launches_unchanged=True, quarantined=True,
                 quarantine_owner_only=True, reopened_from_quarantine=False)
        self.row('seed.json', 'crash_recovery', restored_backup='newest', restore_attested=True,
                 changed_process=True, backup_count=newest['count'], crash_count=crashed[0],
                 recovered_count=recovered[0], lost_blocks=crashed[0]-newest['count'], peers_reconnected=True,
                 tip_salted=self.tip(recovered[1]))

    def seed(self, uptime):
        for sub in ('nodes', 'backups', 'quarantine'):
            (self.private/sub).mkdir(mode=0o700)
        self.argv_controls()
        self.start('S', private=True, fresh=True)        # Offline loopback launch for the signer only.
        self.miner_address()
        self.stop('S')
        self.open_public()
        self.rpc['S'].auth_controls()
        self.row('seed.json', 'owner_namespace_auth', correct_login_accepted=True, missing_rejected=True,
                 wrong_rejected=True, pinned=True)
        self.announce('exposed')
        self.until('client', 'bootstrapped', 3600)
        restarts = []
        for number in range(1, o.BACKUPS+1):             # The schedule: one cold backup every BACKUP_EVERY blocks.
            due = self.info('S')[0]+o.BACKUP_EVERY
            self.wait(lambda: self.info('S')[0] >= due, 3600)
            restarts.append(self.planned_restart(number))
            self.announce('restarted', backups=number)
        self.row('seed.json', 'planned_restart', sealed=True, attested_against_seal=True, changed_process=True,
                 new_certificate=True, peers_reconnected=True, stopped_count=restarts[0][0],
                 resumed_count=restarts[0][1], restarts=len(restarts))
        self.row('seed.json', 'cold_backup_retention', backups_taken=o.BACKUPS, retained=o.RETAIN,
                 pruned=o.BACKUPS-o.RETAIN, source_attested=True, copy_attested=True, owner_only=True,
                 schedule_blocks=o.BACKUP_EVERY)
        due = self.state['backups'][-1]['count']+o.LOST_BLOCKS
        self.wait(lambda: self.info('S')[0] >= due, 3600)
        self.crash_and_recover()
        self.announce('recovered')
        self.until('client', 'newcomer', 6*3600 if uptime == o.UPTIME_SECONDS else 3600)
        # Every public launch's log: the current root plus the quarantined one (the crash took its lines).
        logs = b''.join(p.read_bytes() for p in (self.root('S')/'native.log',
                                                 self.private/'quarantine'/'S-0001'/'native.log'))
        attempted = logs.count(o.DIAL_ATTEMPTED)
        upstream = sum(logs.count(ip.encode()) for ip in o.UPSTREAM_SEEDS)
        passes = logs.count(o.SEED_PASS)
        c.require(attempted == upstream == 0 and passes >= 1, 'public seed dialled out')
        self.row('seed.json', 'public_seed_shape', rpc='operator-tls', in_peers=self.plan['in_peers'], out_peers=0,
                 max_connections_per_ip=self.plan['max_connections_per_ip'], allow_local_ip=False,
                 hide_my_port=False, exclusive_peers=0, wildcard_listeners=0, plan_checked=True,
                 launches=self.public_launches, dial_attempt_lines=0, upstream_seed_lines=0, seed_pass_lines=passes)
        self.serve()

    def serve(self):
        """Serve until the rollback's SIGTERM; publish the status the monitor reads."""
        self.announce('serving')
        while True:
            edges, foreign = self.census()
            c.require(foreign == 0, 'foreign connection while serving')
            if self.role == 'seed':
                self.status(edges)
            self.say('serving', **self.state.get('said', {}))
            time.sleep(d.budget(2))

    def rolled_back(self):
        """SIGTERM in the serving step: stop and seal every node, then the last rows."""
        c.require(self.step == 'serving', 'stopped before serving')
        final = self.info(o.NODES[self.role][0])
        for name in o.NODES[self.role]:
            if f'node{name}' in self.running():
                self.stop(name)
        rows = dict(launches=self.launches, refused_before_start=0, adverse_argv_refused=self.adverse_argv,
                    census_samples=self.census_samples, foreign_connections=self.foreign_peak,
                    planned_edges=dict(self.planned))
        if self.role == 'seed':
            c.require(self.light and all(self.light), 'light-mode launch history')
            self.row('seed-isolation.json', 'native_mining_bounds', threads=1, light_mode=True,
                     max_count=o.MAX_COUNT, final_count=final[0], external_funding=False, transactions=0)
        self.row(o.DRIVER_FILES[self.role][1], 'launcher_policy', **rows)

    # ---- client role -------------------------------------------------------------
    def seed_tip(self):
        value = self.hear('seed')
        return value['count'], value['top'], value['launch']

    def follow(self, names, count=0):
        count_, top, launch = self.seed_tip()
        states = [self.info(n)[:2] for n in names]
        return (count_, top, launch) if count_ >= count and all(s == (count_, top) for s in states) else None

    def synced_lines(self, name):
        return (self.root(name)/'native.log').read_bytes().count(SYNCED)

    def client(self, uptime):
        (self.private/'nodes').mkdir(mode=0o700)
        self.argv_controls()
        self.until('seed', 'exposed', 3600)
        self.wait(lambda: self.seed_tip()[0] >= o.LATE_JOIN_COUNT, 3600)
        late = self.seed_tip()[0]
        self.start('K', fresh=True)
        synced = self.wait(lambda: self.follow(('K',), late), 900)
        edges = self.wait(lambda: (lambda e: e if e[0] == {'K': 1} else None)(self.census()), 120)
        c.require(edges[1] == 0, 'foreign connection')
        self.row('client.json', 'cold_bootstrap', client_from_genesis=True, late_join_count=late,
                 synced_count=synced[0], client_initiated=True, other_namespace=True, peer_connections=1,
                 tip_salted=self.tip(synced[1]))
        self.announce('bootstrapped')
        process = d.PROCS['nodeK'][1]
        followed = {synced[2]}
        full = uptime == o.UPTIME_SECONDS
        def through_recovery():
            value = self.follow(('K',))
            if value:
                followed.add(value[2])
            seed = self.hear('seed')
            done = STEPS['seed'].index(seed['step']) >= STEPS['seed'].index('recovered')
            return value if done and value and value[2] == seed['launch'] and \
                (not full or value[0] >= o.NEWCOMER_COUNT) else None
        recovered = self.wait(through_recovery, 8*3600 if full else 3600)
        c.require(d.PROCS['nodeK'][1] == process, 'client process changed')
        self.row('client.json', 'follows_restarts', seed_launches_followed=len(followed), client_process_unchanged=True,
                 recovered_tip_followed=True, tip_salted=self.tip(recovered[1]))
        join = self.seed_tip()[0]
        self.start('N', fresh=True)
        caught = self.wait(lambda: self.follow(('K', 'N'), join), 1800)
        self.wait(lambda: (lambda e: e if e[0] == {'K': 1, 'N': 1} else None)(self.census()), 120)
        lines = self.synced_lines('N')
        batches = -(-(join-1)//o.SYNC_BATCH)
        if full:  # A rehearsal leaves the depth row NOT_RUN.
            c.require(join >= o.NEWCOMER_COUNT and batches >= 2 and lines >= 2, 'newcomer depth')
            self.row('client.json', 'newcomer_depth', join_count=join, batch_size=o.SYNC_BATCH, batches_needed=batches,
                     synced_log_lines=lines, synced_count=caught[0], other_namespace=True,
                     tip_salted=self.tip(caught[1]))
        self.announce('newcomer')
        self.serve()

    # ---- monitor role ------------------------------------------------------------
    def relayed(self):
        try:
            return json.loads((self.control/'seed-status.json').read_bytes())
        except (FileNotFoundError, ValueError):
            return None

    def monitor(self, uptime):
        (self.private/'nodes').mkdir(mode=0o700)
        c.require(not self.exchange.exists(), 'the monitor never mounts the exchange')
        self.argv_controls()
        self.start('M', fresh=True)
        self.say('following')
        self.wait(lambda: (lambda s: s if s and s.get('step') == 'serving' else None)(self.relayed()),
                  10*3600 if uptime == o.UPTIME_SECONDS else 3*3600)
        pin_file, status_file = self.control/'pin', self.control/'seed-status.json'
        good = om.read_pin(pin_file)
        wrong = c.digest(good.encode())
        try:
            om.check_pin(wrong, om.presented_pin(o.SEED_IP, o.RPC['S']))
        except om.Alert:
            alarm = True
        else:
            raise ValueError('wrong pin raised no alarm')
        follower = lambda: self.info('M')[:2]
        start = time.time()
        samples = agreeing = spread = inbound = age = 0
        tip = None
        while time.time()-start < uptime:
            for attempt in range(4):
                result = om.evaluate(seed_host=o.SEED_IP, pin_file=pin_file, status_file=status_file,
                                     follower=follower, in_peers=self.plan['in_peers'], max_age=o.STATUS_MAX_AGE,
                                     max_spread=o.MAX_SPREAD)
                edges, foreign = self.census()
                c.require(foreign == 0, 'foreign connection')
                status = self.relayed()
                if result['state'] == 'OK' and edges == {'M': 1} and status['inbound'].get('monitor', 0) >= 1:
                    break
                c.require(attempt < 3 and result['state'] != 'UNVERIFIED', 'outside monitor: '+repr(result))
                time.sleep(d.budget(10))
            height = self.info('M')[0]
            spread = max(spread, abs(height-status['count']))
            agreeing += bool(result['tip'])
            inbound = max(inbound, result['inbound'])
            age = max(age, result['status_age'])
            tip = self.info('M')[1]
            samples += 1
            self.heartbeat('following', height, samples)
            time.sleep(d.budget(max(1, min(o.MONITOR_SAMPLE_SECONDS, uptime-(time.time()-start)))))
        c.require(samples >= 2 and agreeing >= 1, 'outside monitor samples')
        self.row('monitor.json', 'outside_pin', out_of_band=True, exchange_mounted=False, matched_samples=samples,
                 wrong_pin_alarm=alarm, request_bytes_before_pin=0, credential_held=False)
        self.row('monitor.json', 'outside_tip', follower_validated=True, samples=samples, max_spread=spread,
                 agreeing_samples=agreeing, tip_salted=self.tip(tip))
        self.row('monitor.json', 'outside_peer_count', public_path_count='unavailable-restricted-rpc',
                 source='operator-status-channel', inbound_peak=inbound, in_peers_bound=self.plan['in_peers'],
                 own_edge_seen=True, status_max_age=age)
        self.serve()

    def run(self, uptime=None):
        uptime = uptime if uptime is not None else int(td.UPTIME_FILE.read_text())
        c.require(uptime in o.MODES, 'grant-bound uptime mode')
        self.state['phase'] = 'rows'
        self.save()
        try:
            dict(seed=self.seed, client=self.client, monitor=self.monitor)[self.role](uptime)
        except td.Stop:
            for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
                signal.signal(sig, signal.SIG_IGN)
            self.rolled_back()
        self.state['phase'] = 'complete'
        self.save()
        return 'complete'


def main():
    os.umask(0o077)
    c.require(d.PRIVATE.is_dir() and d.PRIVATE.stat().st_mode & 0o777 == 0o700, 'persistent root owner-only')
    role = ed.ROLE_FILE.read_text().strip()
    c.require(role in o.ROLES, 'unknown operator role')
    if role != 'monitor':
        c.require(ed.EXCHANGE.is_dir() and ed.EXCHANGE.stat().st_mode & 0o777 == 0o700, 'exchange owner-only')
    end = int(td.END_FILE.read_text())
    d.DEADLINE = time.monotonic()+(end-time.time())-120
    d.HARD_END = d.DEADLINE+90
    c.require(d.DEADLINE > time.monotonic()+600, 'operator wall exhausted')
    def stopped(signum, frame):
        raise td.Stop('termination')
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, stopped)
    operator = None
    try:
        operator = Operator(role)
        result = operator.run()
        operator.publish(result)
        return 0
    except BaseException as error:
        with contextlib.suppress(Exception):
            td.private_write(d.PRIVATE/'failure-class', (type(error).__name__+'\n').encode())
            td.private_write(d.PRIVATE/'failure-traceback', __import__('traceback').format_exc().encode())
        if operator is not None:
            with contextlib.suppress(Exception):
                operator.state['phase'] = 'failed'
                operator.save()
            if role != 'monitor':
                with contextlib.suppress(Exception):
                    td.private_write(operator.exchange/(role+'.json'),
                                     (json.dumps(dict(role=role, step='failed', unix=time.time()))+'\n').encode())
        return 1
    finally:
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            signal.signal(sig, signal.SIG_IGN)
        d.DEADLINE = d.HARD_END
        for name, (process, _) in list(d.PROCS.items()):
            if process.poll() is None and operator is not None and name.startswith('node'):
                with contextlib.suppress(Exception):
                    operator.stop(name[4:])
            if process.poll() is None:
                with contextlib.suppress(Exception):
                    d.stop(name, graceful=False)
        if operator is not None:
            with contextlib.suppress(Exception):
                operator.publish()


if __name__ == '__main__':
    raise SystemExit(main())
