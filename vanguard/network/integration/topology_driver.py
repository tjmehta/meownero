#!/usr/bin/env python3
"""TJS-3920 persistent three-node private topology. Requires an exact runtime grant.

Runs inside the accepted network-none container. Imports the accepted genesis
helpers (Digest client, process ownership, census, manifest seal/verify) without
modifying them. /out/private is the persistent owner-only data root and survives
container stop/start; only closed salted witnesses reach /public.

Phases are resumable only at the planned full-cycle boundary. Any other restart
is a fault: it refuses instead of reconstructing eligibility.
"""
import contextlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import profile_contract as c
from integration import topology_contract as t

spec = importlib.util.spec_from_file_location('accepted_genesis_helpers', c.HERE/'profile-integration.py')
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)

STATE = 'topology-state.json'
END_FILE = Path('/out/control/end-unix')


def hex64(value):
    c.require(type(value) is str and len(value) == 64 and all(x in '0123456789abcdef' for x in value),
              'native hash shape')
    return value


def private_write(path, raw):
    temporary = path.with_name(path.name+'.new')
    with contextlib.suppress(FileNotFoundError):
        temporary.unlink()
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        view = memoryview(raw)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(temporary, path)


class Stop(Exception):
    """SIGTERM from docker stop / the manager deadline; never a PASS path."""


class Topology:
    def __init__(self):
        self.private = d.PRIVATE
        self.binaries = {name: c.digest((d.BIN/name).read_bytes()) for name in
                         ('monerod', 'monero-wallet-cli', 'monero-wallet-rpc')}
        self.rpc = {}
        self.launches = 0
        self.adverse_argv = 0
        self.census_samples = 0
        self.light = []
        path = self.private/STATE
        if path.exists():
            self.state = json.loads(c.check_file(path))
            c.require(self.state['schema'] == 'meownero-topology-state/1' and
                      self.state['binaries'] == self.binaries, 'persistent state/binary binding')
            d.SAVED.update(self.state['saved'])
            self.salt = c.check_file(self.private/'salt')
        else:
            self.salt = secrets.token_bytes(32)
            private_write(self.private/'salt', self.salt)
            self.state = dict(schema='meownero-topology-state/1', phase='new', generation=0,
                binaries=self.binaries, saved={}, rows=t.empty_rows(), sealed={}, address=None,
                counters=dict(launches=0, adverse_argv=0, census=0, light=[]))
        counters = self.state['counters']
        self.launches, self.adverse_argv = counters['launches'], counters['adverse_argv']
        self.census_samples, self.light = counters['census'], counters['light']
        self.state['generation'] += 1
        self.save()

    # ---- persistence -------------------------------------------------------------
    def save(self):
        self.state['saved'] = dict(d.SAVED)
        self.state['counters'] = dict(launches=self.launches, adverse_argv=self.adverse_argv,
            census=self.census_samples, light=self.light)
        private_write(self.private/STATE, c.canonical(self.state))

    def row(self, file, key, **witness):
        c.require(key in t.REQUIRED[file] and file in t.DRIVER_FILES+('persistence.json',), 'unknown topology row')
        self.state['rows'][file][key] = dict(status='PASS', **witness)
        self.save()

    def publish(self, phase=None):
        for file in t.DRIVER_FILES:
            (d.PUBLIC/file).write_text(json.dumps(self.state['rows'][file], indent=2)+'\n')
        persistence = {k: v for k, v in self.state['rows']['persistence.json'].items() if k in t.DRIVER_PERSISTENCE}
        (d.PUBLIC/'persistence.json').write_text(json.dumps(persistence, indent=2)+'\n')
        self.heartbeat(phase)

    def heartbeat(self, phase=None, count=0, samples=0):
        value = dict(phase=phase or self.state['phase'], generation=self.state['generation'],
                     count=count, samples=samples, unix=int(time.time()))
        (d.PUBLIC/'heartbeat.json').write_text(json.dumps(value)+'\n')

    def tip(self, value):
        return t.salted(self.salt, hex64(value))

    # ---- native processes --------------------------------------------------------
    def root(self, name):
        return self.private/'nodes'/name

    def daemon_argv(self, name, root, *, peers, mining=False, offline=False, in_peers=None):
        port = t.P2P[name]
        argv = [str(d.BIN/'monerod'), '--testnet', '--data-dir', str(root),
            '--non-interactive', '--no-igd', '--allow-local-ip', '--disable-dns-checkpoints',
            '--check-updates', 'disabled', '--hide-my-port', '--max-concurrency', '1',
            '--no-zmq', '--rpc-ssl', 'disabled', '--restricted-rpc',
            '--p2p-bind-ip', '127.0.0.1', '--p2p-bind-ipv6-address', '::1',
            '--p2p-bind-port', str(port), '--rpc-bind-ip', '127.0.0.1',
            '--rpc-bind-port', str(t.RPC[name]), '--max-connections-per-ip', '4',
            '--log-level', '1', '--log-file', str(root/'native.log')]
        if offline:
            argv.append('--offline')
        for peer in peers:
            argv += ['--add-exclusive-node', f'127.0.0.1:{t.P2P[peer]}']
        if in_peers is not None:
            argv += ['--in-peers', str(in_peers)]
        if mining:
            argv += ['--start-mining', self.state['address'], '--mining-threads', '1']
        return argv

    def start(self, name, *, peers=None, mining=False, offline=False, in_peers=None, fresh=False):
        c.require(name in t.NODES and f'node{name}' not in self.running(), 'node already running')
        root = self.root(name)
        peers = () if offline else (t.PEERS[name] if peers is None else peers)
        argv = self.daemon_argv(name, root, peers=peers, mining=mining, offline=offline, in_peers=in_peers)
        t.check_argv('monerod', argv, mining=mining, offline=offline)  # Refuse before any root/process effect.
        if fresh:
            c.require(not root.exists(), 'fresh node root already exists')
            root.mkdir(mode=0o700)
            manifest = dict(d.creation('daemon', self.binaries), stopped_saved=False)
        else:
            # Missing/changed/unsealed manifest, file drift, alias or mode refuses before Popen.
            c.root_manifest(root, d.SAVED[str(root)])
            d.released(root)
            manifest = dict(d.SAVED[str(root)], stopped_saved=False)
            self.state.setdefault('last_sealed', {})[str(root)] = d.SAVED[str(root)]
        (root/'creation.json').write_bytes(c.canonical(manifest))
        os.chmod(root/'creation.json', 0o600)
        d.SAVED.pop(str(root), None)
        self.save()
        login = 'node:'+secrets.token_hex(24)  # Fresh per launch; memory-only.
        env = dict(d.ENV, RPC_LOGIN=login, MONERO_RANDOMX_UMASK='4')
        c.require(env['MONERO_RANDOMX_UMASK'] == '4', 'RandomX light mode required')
        d.launch(f'node{name}', argv, root, env)
        self.launches += 1
        self.light.append(env['MONERO_RANDOMX_UMASK'] == '4')
        rpc = d.RPC(t.RPC[name], login)
        d.wait(lambda: rpc.call('get_info'), 120)
        self.rpc[name] = rpc
        self.save()
        return rpc

    def running(self):
        return {k for k, (p, _) in d.PROCS.items() if p.poll() is None}

    def stop(self, name):
        identity = d.stop(f'node{name}')
        d.absent(t.P2P[name])
        d.absent(t.RPC[name])
        root = self.root(name)
        d.released(root)
        d.seal(root, 'daemon', self.binaries)
        self.rpc.pop(name, None)
        self.save()
        return identity

    def lose(self, name):
        """Primary loss: SIGKILL with exact PID identity; the root stays unsealed."""
        process, owned = d.PROCS[f'node{name}']
        c.require(process.poll() is None, 'lost node already exited')
        c.stop_identity(owned, d.identity(process.pid))
        process.send_signal(signal.SIGKILL)
        process.wait(timeout=d.budget(10))
        c.require(not Path(f'/proc/{process.pid}').exists(), 'killed PID not absent')
        d.absent(t.P2P[name])
        d.absent(t.RPC[name])
        self.rpc.pop(name, None)
        return owned

    def info(self, name):
        value = self.rpc[name].call('get_info')
        c.require(value['status'] == 'OK' and type(value['height']) is int and
                  1 <= value['height'] < t.MAX_COUNT, 'topology count bound')
        hex64(value['top_block_hash'])
        if value['height'] == 1:
            c.require(value['top_block_hash'] == c.GENESIS, 'topology genesis identity')
        return value['height'], value['top_block_hash'], int(value['wide_cumulative_difficulty'], 0)

    def agree(self, names=t.NODES, count=None):
        states = [self.info(name) for name in names]
        same = all(x == states[0] for x in states)
        return states[0] if same and (count is None or states[0][0] >= count) else None

    def known(self, name, block_hash):
        code, value = self.rpc[name].call('get_block_header_by_hash',
            dict(hash=block_hash, fill_pow_hash=False), raw=True)
        c.require(code == 200, 'header transport')
        if 'error' in value:
            return None
        return value['result']['block_header']['orphan_status']

    def wait(self, check, seconds):
        # Predicate failures propagate; no cap or semantic failure becomes a retry.
        end = time.monotonic()+d.budget(seconds)
        while time.monotonic() < end:
            value = check()
            if value:
                return value
            self.census()
            time.sleep(d.budget(2))
        raise TimeoutError('topology milestone deadline')

    def census(self):
        d.census()
        self.census_samples += 1
        for name in self.rpc:
            c.require(d.PROCS[f'node{name}'][0].poll() is None, 'unexpected native exit')
        return self.edges()

    def edges(self):
        """Peer edges from kernel socket tables; any non-peer remote port is foreign."""
        sockets = {}
        for kind in ('tcp', 'tcp6'):
            for line in Path('/proc/net/'+kind).read_text().splitlines()[1:]:
                parts = line.split()
                if parts[3] != '01':
                    continue
                sockets[parts[9]] = (int(parts[1].split(':')[1], 16), int(parts[2].split(':')[1], 16))
        owner, local = {}, {}
        for name in t.NODES:
            entry = d.PROCS.get(f'node{name}')
            if entry is None or entry[0].poll() is not None:
                continue
            for fd in Path(f'/proc/{entry[0].pid}/fd').iterdir():
                with contextlib.suppress(FileNotFoundError):
                    target = os.readlink(fd)
                    if target.startswith('socket:[') and target[8:-1] in sockets:
                        owner[target[8:-1]] = name
                        local[sockets[target[8:-1]][0], name] = True
        edges, foreign = set(), 0
        by_port = {port: name for name, port in t.P2P.items()}
        for inode, name in owner.items():
            lport, rport = sockets[inode]
            if lport == t.RPC[name]:
                continue  # Driver RPC client.
            if lport == t.P2P[name]:
                peer = next((n for (p, n) in local if p == rport and n != name), None)
            else:
                peer = by_port.get(rport)
            if peer is None or peer == name:
                foreign += 1
            else:
                edges.add(frozenset((name, peer)))
        return edges, foreign

    def miner_address(self):
        """F1's restore-signer shape creates the miner address; the password is RPC-body only."""
        root = self.private/'wallets'/'miner'
        root.mkdir(parents=True, mode=0o700)
        os.chmod(root.parent, 0o700)
        cwd = self.private/'wallets'/'miner-rpc'
        cwd.mkdir(mode=0o700)
        config = self.private/'wallets'/'miner-cli.conf'
        private_write(config, ('daemon-login='+self.rpc['A'].login+'\ndaemon-ssl=disabled\n').encode())
        argv = [str(d.BIN/'monero-wallet-rpc'), '--testnet', '--config-file', str(config),
            '--daemon-address', f'127.0.0.1:{t.RPC["A"]}', '--wallet-dir', str(root),
            '--rpc-bind-ip', '127.0.0.1', '--rpc-bind-port', str(t.WALLET_PORT), '--rpc-ssl', 'disabled',
            '--log-file', str(cwd/'native.log')]
        t.check_argv('monero-wallet-rpc', argv, signer=True)
        d.launch('miner-wallet', argv, cwd)
        self.launches += 1
        login = d.wait(lambda: c.check_file(cwd/f'monero-wallet-rpc.{t.WALLET_PORT}.login',
                       modes=(0o400, 0o600)).decode(), 30)
        rpc = d.RPC(t.WALLET_PORT, login)
        d.wait(lambda: rpc.call('get_version'), 30)
        password = secrets.token_hex(32)
        private_write(root/'password', (password+'\n').encode())
        rpc.call('create_wallet', dict(filename='wallet', password=password, language='English'))
        address = rpc.call('get_address', dict(account_index=0, address_index=[]))['address']
        rpc.call('close_wallet')
        d.stop('miner-wallet')
        d.absent(t.WALLET_PORT)
        config.unlink()  # Its login dies with A's next launch; no credential file is kept.
        self.state['address'] = address
        self.save()

    # ---- adverse launcher policy --------------------------------------------------
    def argv_controls(self):
        root = self.root('A')
        base = self.daemon_argv('A', root, peers=('B',))
        cases = []
        def swap(option, value):
            argv = list(base)
            argv[argv.index(option)+1] = value
            return argv
        cases.append(swap('--rpc-bind-ip', '0.0.0.0'))
        cases.append(swap('--rpc-bind-ip', '192.168.1.2'))
        cases.append(swap('--p2p-bind-ip', '0.0.0.0'))
        cases.append(swap('--p2p-bind-ipv6-address', '::'))
        cases.append(swap('--rpc-ssl', 'enabled'))
        cases.append([x for x in base if x != '--restricted-rpc'])
        cases.append(base+['--confirm-external-bind'])
        cases.append(base+['--disable-rpc-login'])
        cases.append(base+['--rpc-restricted-bind-port', '48089'])
        cases.append(base+['--zmq-pub', 'tcp://127.0.0.1:48090'])
        cases.append(base+['--add-peer', '10.0.0.1:18080'])
        cases.append(base+['--seed-node', '127.0.0.1:18080'])
        cases.append(base+['--add-exclusive-node', '10.0.0.1:48180'])
        cases.append(base+['--bootstrap-daemon-address', '127.0.0.1:18081'])
        cases.append([x for x in base if x != '--add-exclusive-node' and not x.startswith('127.0.0.1:')])
        cases.append(base+['--rpc-bind-ip=0.0.0.0'])
        count = len(d.PROCS)
        for argv in cases:
            try:
                t.check_argv('monerod', argv)
            except t.PolicyRefusal:
                self.adverse_argv += 1
            else:
                raise ValueError('adverse daemon argv accepted')
        wallet = [str(d.BIN/'monero-wallet-rpc'), '--testnet', '--config-file', '/c', '--daemon-address',
            '127.0.0.1:48081', '--wallet-dir', '/x', '--rpc-bind-ip', '127.0.0.1', '--rpc-bind-port', '48083',
            '--rpc-ssl', 'disabled']
        for argv in (wallet[:-4]+['--rpc-bind-ip', '0.0.0.0', '--rpc-ssl', 'disabled'],
                     wallet+['--disable-rpc-login'], wallet+['--confirm-external-bind'],
                     wallet[:4]+['10.0.0.2:48081']+wallet[5:], wallet+['--password-file', '/p']):
            try:
                t.check_argv('monero-wallet-rpc', argv, signer=True)
            except t.PolicyRefusal:
                self.adverse_argv += 1
            else:
                raise ValueError('adverse wallet argv accepted')
        c.require(len(d.PROCS) == count, 'refused argv started a process')
        self.save()

    def refusal(self, fixture, expected):
        """Launcher check only: refusal must precede every native start."""
        before = len(d.PROCS)
        try:
            c.root_manifest(fixture, expected)
        except (OSError, ValueError):
            c.require(len(d.PROCS) == before, 'refused root started a process')
            return True
        return False

    def backup_controls(self, backup):
        expected = d.SAVED[str(backup)]
        original = {str(p.relative_to(backup)): c.digest(p.read_bytes()) for p in backup.rglob('*') if p.is_file()}
        scratch = self.private/'adverse'
        scratch.mkdir(mode=0o700)
        lmdb = next(p for p in sorted(backup.rglob('data.mdb')))
        relative = lmdb.relative_to(backup)
        cases = ['flip-byte', 'truncate', 'missing-data', 'missing-manifest', 'empty-manifest',
                 'unsealed', 'extra-file', 'symlink', 'mode', 'hardlink', 'appended', 'native-log-drift']
        if any(backup.rglob('lock.mdb')):
            cases.append('missing-lock')
        refused = 0
        for case in cases:
            fixture = scratch/case
            shutil.copytree(backup, fixture)
            target = fixture/relative
            if case == 'flip-byte':
                with target.open('r+b') as stream:
                    stream.seek(target.stat().st_size//2)
                    byte = stream.read(1)
                    stream.seek(-1, 1)
                    stream.write(bytes([byte[0] ^ 1]))
            elif case == 'truncate':
                os.truncate(target, target.stat().st_size//2)
            elif case == 'missing-data':
                target.unlink()
            elif case == 'missing-lock':
                next(fixture.rglob('lock.mdb')).unlink()
            elif case == 'missing-manifest':
                (fixture/'creation.json').unlink()
            elif case == 'empty-manifest':
                (fixture/'creation.json').write_text('{}')
            elif case == 'unsealed':
                value = json.loads((fixture/'creation.json').read_text())
                value['stopped_saved'] = False
                (fixture/'creation.json').write_bytes(c.canonical(value))
            elif case == 'extra-file':
                (fixture/'unexpected').write_text('owned adverse fixture')
            elif case == 'symlink':
                (fixture/'alias').symlink_to(backup)
            elif case == 'mode':
                os.chmod(fixture, 0o755)
            elif case == 'hardlink':
                os.link(target, fixture/'second-link')
            elif case == 'appended':
                with target.open('ab') as stream:
                    stream.write(b'\0'*4096)
            elif case == 'native-log-drift':
                with (fixture/'native.log').open('ab') as stream:
                    stream.write(b'x\n')
            refused += self.refusal(fixture, expected)
            shutil.rmtree(fixture)
        intact = scratch/'intact'
        shutil.copytree(backup, intact)
        accepted = not self.refusal(intact, expected)
        shutil.rmtree(intact)
        # Foreign/other-profile roots: same layout, wrong binding.
        foreign = 0
        for field in ('profile', 'overlay', 'binaries', 'kind'):
            fixture = scratch/('foreign-'+field)
            shutil.copytree(backup, fixture)
            value = json.loads((fixture/'creation.json').read_text())
            value[field] = 'foreign'
            (fixture/'creation.json').write_bytes(c.canonical(value))
            os.chmod(fixture/'creation.json', 0o600)
            foreign += self.refusal(fixture, expected)
            shutil.rmtree(fixture)
        scratch.rmdir()
        after = {str(p.relative_to(backup)): c.digest(p.read_bytes()) for p in backup.rglob('*') if p.is_file()}
        c.require(refused == len(cases) and foreign == 4 and accepted and after == original,
                  'backup refusal controls')
        self.row('backup.json', 'corrupt_incomplete_refusal', cases=len(cases), refused=refused, started=0,
                 intact_control_accepted=True, original_unchanged=True)
        self.row('backup.json', 'foreign_root_refusal', cases=4, refused=foreign, started=0)

    # ---- phases ------------------------------------------------------------------
    def genesis(self):
        (self.private/'nodes').mkdir(mode=0o700)
        self.argv_controls()
        self.start('A', fresh=True)
        self.start('B', fresh=True)
        self.wait(lambda: self.agree(('A', 'B'), 1), 120)
        for name in ('A', 'B'):
            self.rpc[name].auth_controls()
        self.miner_address()
        self.stop('A')
        self.start('A', mining=True)
        self.wait(lambda: self.agree(('A', 'B'), 6), 3600)
        late = self.info('A')[0]
        self.start('C', fresh=True)
        self.rpc['C'].auth_controls()
        synced = self.wait(lambda: self.agree(t.NODES, late), 600)
        edges, foreign = self.wait(lambda: (lambda e: e if len(e[0]) == 3 else None)(self.census()), 120)
        c.require(foreign == 0, 'foreign peer connection')
        self.row('topology.json', 'third_seed_client', nodes=3, seeds=2, client_late_join_count=late,
                 client_from_genesis=True, edges=3, client_peers=2, foreign_connections=0,
                 tip_salted=self.tip(synced[1]))
        self.row('isolation.json', 'auth_controls', daemons=3, missing_wrong_rejected=True,
                 fresh_login_per_launch=True)

    def backup(self):
        self.stop('A')
        source = self.root('A')
        backups = self.private/'backups'
        backups.mkdir(mode=0o700)
        target = backups/'A-1'
        d.copy_stopped(source, target)  # The backup is never opened by a writer.
        sealed = self.state['sealed']['A-1'] = list(self.offline_attest('A'))
        files = sum(1 for p in target.rglob('*') if p.is_file())
        self.row('recovery.json', 'cold_backup', node='A', stopped_saved=True, files=files, count=sealed[0],
                 work_bound=True, tip_salted=self.tip(sealed[1]))
        self.backup_controls(target)
        self.start('A', mining=True)
        self.wait(lambda: self.agree(t.NODES, sealed[0]+1), 900)

    def offline_attest(self, name):
        """Start one stopped live root offline, bind saved count/top/work, stop and reseal."""
        self.start(name, offline=True)
        value = self.info(name)
        self.stop(name)
        return value

    def primary_loss(self):
        lost_at = self.wait(lambda: self.agree(), 300)
        self.lose('A')
        root = self.root('A')
        before = len(d.PROCS)
        try:
            # The last sealed manifest of this root must not accept the crashed writer's state.
            c.root_manifest(root, self.state['last_sealed'][str(root)])
        except (OSError, ValueError):
            refused = True
        else:
            refused = False
        c.require(refused and len(d.PROCS) == before, 'crashed unsealed root accepted')
        self.row('backup.json', 'crashed_root_refusal', node='A', unsealed_refused=True, started=0)
        quarantine = self.private/'quarantine'
        quarantine.mkdir(mode=0o700, exist_ok=True)
        os.rename(root, quarantine/'A-lost-1')  # Never erased.
        # Recovery seed B takes over native mining; C follows it.
        self.stop('B')
        self.start('B', peers=('C',), mining=True)  # Dial the synced client, as A dialed B in F1.
        mined = self.wait(lambda: self.agree(('B', 'C'), lost_at[0]+3), 1800)
        self.row('recovery.json', 'recovery_seed_continuity', seed='B', client_followed=True,
                 mined_blocks=mined[0]-lost_at[0], primary_down=True, tip_salted=self.tip(mined[1]))
        # Both seeds unavailable: the client must fail closed with no fallback.
        self.stop('B')
        frozen = self.info('C')
        start = time.monotonic()
        while time.monotonic()-start < 90:
            edges, foreign = self.census()
            c.require(not edges and foreign == 0 and self.info('C') == frozen, 'client fallback or progress')
            time.sleep(d.budget(5))
        self.row('recovery.json', 'fail_closed_both_down', seconds=90, client_peer_connections=0,
                 foreign_connections=0, height_frozen=True, fallback=False)
        self.start('B', peers=('C',), mining=True)
        self.wait(lambda: self.agree(('B', 'C'), frozen[0]+1), 1800)
        # Restore the primary from its cold backup into a new root.
        backup = self.private/'backups'/'A-1'
        d.copy_stopped(backup, root)
        restored = self.offline_attest('A')
        c.require(list(restored) == self.state['sealed']['A-1'], 'restored backup attestation')
        self.start('A')
        caught = self.wait(lambda: self.agree(t.NODES), 900)
        c.require(caught[0] > restored[0], 'restored primary did not catch up')
        self.row('recovery.json', 'primary_loss_recovery', lost='A', forced_kill=True, quarantined=True,
                 erased=False, lost_count=lost_at[0], restored_backup_count=restored[0], offline_attested=True,
                 caught_up_count=caught[0], missing_blocks=caught[0]-restored[0], tip_salted=self.tip(caught[1]))
        # Mining returns to the primary.
        self.stop('B')
        self.start('B')
        self.stop('A')
        self.start('A', mining=True)
        self.wait(lambda: self.agree(t.NODES, caught[0]+1), 900)

    def client_detach(self):
        before = self.wait(lambda: self.agree(), 300)
        self.stop('C')
        old = before[0]
        self.wait(lambda: self.agree(('A', 'B'), old+2), 1800)
        self.start('C')
        after = self.wait(lambda: self.agree(t.NODES, old+2), 600)
        self.row('topology.json', 'client_detach_rejoin', detached_count=old, rejoined_count=after[0],
                 advanced_blocks=after[0]-old, changed_process=True, tip_salted=self.tip(after[1]))

    def partition(self):
        fork = self.wait(lambda: self.agree(), 300)
        # A keeps mining in-process (synchronized state survives losing peers). B refuses
        # inbound and dials only C; C dials only B. A's exclusive peer B refuses it.
        self.stop('C')
        self.stop('B')
        self.start('B', peers=('C',), in_peers=0, mining=True)
        self.start('C', peers=('B',))
        isolated = self.wait(lambda: (lambda a: a if a[0] >= fork[0]+2 else None)(self.info('A')), 2400)
        self.stop('A')
        self.start('A')  # Not synchronized, not mining: frozen isolated tip.
        c.require(self.info('A') == isolated, 'isolated tip changed')
        majority = self.wait(lambda: (lambda b: b if b[0] >= isolated[0]+2 and b[2] > isolated[2] and
                                      self.agree(('B', 'C')) == b else None)(self.info('B')), 3600)
        c.require(self.known('B', isolated[1]) is None and self.known('C', isolated[1]) is None,
                  'majority saw isolated chain')
        self.stop('B')
        self.start('B')  # Default inbound, exclusive A; no mining.
        self.stop('C')
        self.start('C')
        final = self.wait(lambda: self.agree(t.NODES, majority[0]), 900)
        c.require(final[1] == majority[1], 'reorg did not adopt majority chain')
        c.require(self.known('A', isolated[1]) is True, 'isolated block not retained as alternative')
        self.row('reorg.json', 'partition_reorg', isolated='A', depth=isolated[0]-fork[0],
                 isolated_blocks=isolated[0]-fork[0], majority_blocks=majority[0]-fork[0],
                 majority_work_greater=True, alt_block_retained=True, majority_never_saw_isolated=True,
                 final_agreement=3, tip_salted=self.tip(final[1]))
        self.stop('A')
        self.start('A', mining=True)
        self.wait(lambda: self.agree(t.NODES, final[0]+1), 900)

    def cycle_out(self):
        self.stop('A')
        self.start('A')  # Stop mining first so the recorded tip is every node's saved tip.
        tip = self.wait(lambda: self.agree(), 300)
        for name in ('A', 'C', 'B'):
            self.stop(name)
        self.state['cycle'] = dict(sealed={n: list(tip) for n in t.NODES},
            processes={n: d.PROCS[f'node{n}'][1] for n in t.NODES})
        self.state['phase'] = 'cycle'
        self.save()

    def cycle_in(self):
        cycle = self.state['cycle']
        attested = 0
        for name in t.NODES:
            value = self.offline_attest(name)
            c.require(list(value) == cycle['sealed'][name], 'post-cycle saved state differs')
            attested += 1
        self.start('B')
        self.start('C')
        self.start('A', mining=True)
        resumed = self.wait(lambda: self.agree(t.NODES, cycle['sealed']['A'][0]), 600)
        changed = sum(d.PROCS[f'node{n}'][1] != cycle['processes'][n] for n in t.NODES)
        c.require(changed == 3, 'process generations did not change')
        self.row('persistence.json', 'full_cycle', nodes=3, offline_attested=attested, manifests_verified=3,
                 container_restarted=True, changed_processes=3, resumed_count=resumed[0],
                 tip_salted=self.tip(resumed[1]))
        self.state['phase'] = 'steady'
        self.state['steady'] = dict(start_unix=time.time(), start_count=resumed[0])
        self.save()

    def steady(self):
        steady = self.state['steady']
        generations = {n: d.PROCS[f'node{n}'][1] for n in t.NODES}
        samples, spread, last = 0, 0, None
        gaps = 0
        while time.time()-steady['start_unix'] < t.UPTIME_SECONDS:
            for attempt in range(4):
                # A transient reconnect or in-flight block is retried for 30 s, then it is a fault.
                c.require(all(d.PROCS[f'node{n}'][1] == generations[n] and d.PROCS[f'node{n}'][0].poll() is None
                              for n in t.NODES), 'node restarted or exited')
                edges, foreign = self.census()
                c.require(foreign == 0, 'foreign peer connection')
                heights = [self.info(n)[0] for n in t.NODES]
                if len(edges) >= 2 and max(heights)-min(heights) <= t.MAX_SPREAD:
                    break
                c.require(attempt < 3, 'steady connectivity/spread fault')
                gaps += 1
                time.sleep(d.budget(10))
            spread = max(spread, max(heights)-min(heights))
            samples += 1
            last = max(heights)
            self.heartbeat('steady', last, samples)
            self.state['steady'].update(samples=samples, spread=spread, last=last, gaps=gaps)
            self.save()
            remaining = t.UPTIME_SECONDS-(time.time()-steady['start_unix'])
            time.sleep(d.budget(max(1, min(t.SAMPLE_SECONDS, remaining))))
        final = self.wait(lambda: self.agree(), 600)
        blocks = final[0]-steady['start_count']
        c.require(blocks >= 100, 'steady chain did not advance')
        self.row('uptime.json', 'uptime_24h', seconds=int(time.time()-steady['start_unix']), samples=samples,
                 faults=0, retried_samples=gaps, max_spread=spread, blocks=blocks, node_restarts=0, final_agreement=3,
                 tip_salted=self.tip(final[1]))
        for name in ('A', 'C', 'B'):
            self.stop(name)
        c.require(self.light and all(self.light), 'light-mode launch history')
        self.row('isolation.json', 'native_mining_bounds', threads=1, light_mode=True, max_count=t.MAX_COUNT,
                 final_count=final[0], external_funding=False, loopback_only=True, transactions=0)
        self.row('isolation.json', 'launcher_policy', launches=self.launches, refused_before_start=0,
                 loopback_only=True, restricted_daemon_rpc=True, adverse_argv_refused=self.adverse_argv,
                 census_samples=self.census_samples)
        self.state['phase'] = 'complete'
        self.save()

    def run(self):
        phase = self.state['phase']
        if phase == 'new':
            self.state['phase'] = 'rows'
            self.save()
            self.genesis()
            self.backup()
            self.primary_loss()
            self.client_detach()
            self.partition()
            self.cycle_out()
            return 'cycle'
        c.require(phase == 'cycle', 'unplanned restart refuses: phase '+phase)
        self.cycle_in()
        self.steady()
        return 'complete'


def main():
    os.umask(0o077)
    c.require(d.PRIVATE.is_dir() and d.PRIVATE.stat().st_mode & 0o777 == 0o700, 'persistent root owner-only')
    end = int(END_FILE.read_text())
    d.DEADLINE = time.monotonic()+(end-time.time())-120
    d.HARD_END = d.DEADLINE+90
    c.require(d.DEADLINE > time.monotonic()+600, 'topology wall exhausted')
    def stopped(signum, frame):
        raise Stop('termination')
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, stopped)
    topology = None
    try:
        topology = Topology()
        result = topology.run()
        topology.publish(result)
        return 0
    except BaseException as error:
        with contextlib.suppress(Exception):
            private_write(d.PRIVATE/'failure-class', (type(error).__name__+'\n').encode())
            private_write(d.PRIVATE/'failure-traceback', __import__('traceback').format_exc().encode())
        if topology is not None:
            with contextlib.suppress(Exception):
                topology.state['phase'] = 'failed'
                topology.save()
        return 1
    finally:
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            signal.signal(sig, signal.SIG_IGN)
        d.DEADLINE = d.HARD_END
        for name, (process, _) in list(d.PROCS.items()):
            if process.poll() is None and topology is not None and name.startswith('node'):
                with contextlib.suppress(Exception):
                    topology.stop(name[4:])
            if process.poll() is None:
                with contextlib.suppress(Exception):
                    d.stop(name, graceful=False)
        if topology is not None:
            with contextlib.suppress(Exception):
                topology.publish()


if __name__ == '__main__':
    raise SystemExit(main())
