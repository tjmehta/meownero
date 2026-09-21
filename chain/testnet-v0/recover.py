#!/usr/bin/env python3
"""TJS-287: cold backup/restore of a node data directory and payout-wallet reopen across daemon restarts."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import time
import urllib.request

import launch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
WORK = Path('/work')
RECIPE_MANIFEST = ROOT / 'research/evidence/testnet-v0-launch-tjs229-2026-09-20/launch/INPUTS.sha256'
RECIPE_MANIFEST_SHA = '1e3b8a784828b05634abd4b4ac22ba7cc83652b32af023c71c146f3216a5e59f'
WALLET_SHA = '5782abee489e8b245b42fd237ece34d6df1c67929c552960755fab41de3a921a'  # accepted TJS-40/TJS-44 monero-wallet-rpc
REWARD = launch.EXPECTED['reward_atomic']
TARGET_SECONDS = launch.EXPECTED['target_seconds']
# Minimum new blocks per seam. Native DAA approaches one block per 90 s after the first
# eight blocks under one mining thread, so both seams stay small.
PHASES = {'payout_min_top': 5, 'offline_blocks': 2}
POLL_SECONDS = 0.1
RUN_LIMIT_SECONDS = 1800
NEW_FILES = ['recover.py', 'verify-recover.py', 'test-recover-refusals.py', 'recover-journey.md']
WALLET_PORT = 28190  # wallet RPC on container loopback, bound to peer 1's daemon RPC
INITIALIZED = re.compile(r'Blockchain initialized\. last block: (\d+),')
save, require, digest = launch.save, launch.require, launch.digest


def phase_limit(count):
    """Twice the DAA-expected phase time plus fixed slack; a timeout is still an incomplete journey."""
    return 120 + 2 * count * TARGET_SECONDS


def daemon_command(n):
    """The accepted recipe v1 daemon command with fresh owned directories; two peers only."""
    return ['/binary/monerod', '--config-file', str(WORK / f'peer{n}.conf'), '--data-dir', str(WORK / 'data' / f'peer{n}'),
            '--non-interactive', '--no-igd', '--disable-dns-checkpoints', '--check-updates', 'disabled',
            '--max-concurrency', '1', '--allow-local-ip', '--hide-my-port',
            '--add-exclusive-node', f'127.0.0.1:{28080 + (1 - n) * 100}',
            '--p2p-bind-ip', '127.0.0.1', '--p2p-bind-port', str(28080 + n * 100),
            '--rpc-bind-ip', '127.0.0.1', '--rpc-bind-port', str(28081 + n * 100),
            '--rpc-ssl', 'disabled', '--no-zmq', '--log-level', '1', '--log-file', str(WORK / f'peer{n}.log')]


def wrpc(method, params=None):
    request = urllib.request.Request(f'http://127.0.0.1:{WALLET_PORT}/json_rpc',
                                     json.dumps({'jsonrpc': '2.0', 'id': '0', 'method': method, 'params': params or {}}).encode(),
                                     {'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=120) as response:
        result = json.load(response)
    # Wallet errors and request/response bodies can contain keys. Never log them.
    require('error' not in result, f'wallet RPC failed: {method}')
    return result['result']


def file_manifest(directory):
    """Relative path, size and SHA-256 of every file below a stopped node's data directory."""
    return {str(p.relative_to(directory)): {'bytes': p.stat().st_size, 'sha256': digest(p)}
            for p in sorted(directory.rglob('*')) if p.is_file()}


def inside():
    procs, commands, exits, calls, usage = {}, {}, {}, {}, {}
    started = time.monotonic()
    clk = os.sysconf('SC_CLK_TCK')
    result = {'result': 'FAIL', 'scope': 'two local P2P peers; payout wallet on peer 1; plain daemon restart; '
                                         'cold backup/destroy/restore of peer 1 data; native miner and DAA; empty blocks'}

    def elapsed():
        return time.monotonic() - started

    def event(label, **fields):
        print(json.dumps({'event': label, 'elapsed_s': elapsed(), **fields}), flush=True)

    def rpc(node, method, params=None, endpoint=False):
        # Every daemon RPC call is counted per node so receipts show no block injection.
        calls.setdefault(f'peer{node}', {})[method] = calls.setdefault(f'peer{node}', {}).get(method, 0) + 1
        return launch.rpc(node, method, params, endpoint)

    def wait(check, label, seconds=120):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            require(all(p.poll() is None for p in procs.values()), 'owned process exited early')
            try:
                if check():
                    return
            except (OSError, ValueError, KeyError):
                pass
            time.sleep(POLL_SECONDS)
        raise TimeoutError(label)

    def start(name, command, private=False):
        commands[name] = command
        save(WORK / 'process-commands.json', commands)
        logdir = WORK / 'data' if private else WORK
        with (logdir / f'{name}.stdout.log').open('w') as log:
            procs[name] = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)

    def stop(name, timeout=60):
        process = procs.pop(name)
        process.terminate()
        try:
            exits[name] = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            exits[name] = process.wait()
        return exits[name]

    def header(node, height):
        return rpc(node, 'get_block_header_by_height', {'height': height})['block_header']

    def state(node):
        tip = rpc(node, 'get_last_block_header')['block_header']
        sums = rpc(node, 'get_coinbase_tx_sum', {'height': 0, 'count': tip['height'] + 1})
        return {'height': tip['height'], 'hash': tip['hash'], 'cumulative_work': tip['wide_cumulative_difficulty'],
                'emission_atomic': sums['emission_amount'], 'fees_atomic': sums['fee_amount']}

    def converged(nodes):
        return len({json.dumps(state(n), sort_keys=True) for n in nodes}) == 1

    def info(node, keys=('height', 'top_block_hash', 'synchronized')):
        row = rpc(node, 'get_info')
        return {k: row[k] for k in keys}

    def sample(name, n, label):
        pid = procs[name].pid
        status = dict(line.split(':', 1) for line in Path(f'/proc/{pid}/status').read_text().splitlines())
        stat = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        files = [p.stat() for p in (WORK / 'data' / f'peer{n}').rglob('*') if p.is_file()]
        row = {'elapsed_s': elapsed(), 'vm_hwm_kib': int(status['VmHWM'].split()[0]), 'vm_rss_kib': int(status['VmRSS'].split()[0]),
               'threads': int(status['Threads']), 'cpu_user_s': int(stat[11]) / clk, 'cpu_system_s': int(stat[12]) / clk,
               'data_dir_allocated_bytes': sum(s.st_blocks * 512 for s in files),
               'data_dir_apparent_bytes': sum(s.st_size for s in files), 'data_dir_files': len(files)}
        usage.setdefault(name, {})[label] = row
        save(WORK / 'process-usage.json', usage)
        return row

    def mine(min_blocks, address, nodes, label):
        start_top = state(0)['height']
        params = {'miner_address': address, 'threads_count': 1, 'do_background_mining': False, 'ignore_battery': True}
        rpc(0, 'start_mining', params, endpoint=True)
        event('mining_started', phase=label, start_top=start_top, minimum_blocks=min_blocks,
              live=[f'peer{n}' for n in nodes], limit_seconds=phase_limit(min_blocks))
        try:
            wait(lambda: rpc(0, 'get_info')['height'] - 1 >= start_top + min_blocks, f'native mining: {label}',
                 seconds=phase_limit(min_blocks))
        finally:
            rpc(0, 'stop_mining', endpoint=True)
        wait(lambda: converged(nodes), f'P2P convergence: {label}', seconds=120)
        tip = state(0)
        event('mining_stopped_converged', phase=label, tip=tip, live=[f'peer{n}' for n in nodes])
        return tip

    def connections(n):
        rows = rpc(n, 'get_connections').get('connections', [])
        require(rows and all(c['ip'] == '127.0.0.1' for c in rows), f'peer{n} needs local P2P connections')
        return rows

    def wallet_snapshot():
        """Comparable payout-wallet state: balances and normalised history. The address itself stays private."""
        wrpc('refresh')
        balance = wrpc('get_balance')
        transfers = wrpc('get_transfers', {'in': True, 'out': True, 'pending': True, 'pool': True, 'failed': True})
        return {'address_matches': wrpc('get_address')['address'] == address,
                'balance': {'balance': balance['balance'], 'unlocked_balance': balance['unlocked_balance']},
                'incoming': sorted([t['txid'], t['amount'], t['height'], t['type']] for t in transfers.get('in', [])),
                'outgoing': sorted([t['txid'], t['amount'], t['fee']] for t in transfers.get('out', [])),
                'other': sum(len(transfers.get(k, [])) for k in ('pending', 'pool', 'failed'))}

    def wallet_close():
        wrpc('store')
        wrpc('close_wallet')

    def wallet_open():
        wrpc('open_wallet', {'filename': 'W', 'password': ''})
        require(wrpc('get_address')['address'] == address, 'reopened payout wallet address mismatch')

    def restart_peer1(name):
        """Restart peer 1 with the exact accepted command and return its first readback."""
        start(name, daemon_command(1))
        require(commands[name] == commands['peer1'], 'restart must reuse the exact daemon command')
        first = {}
        wait(lambda: first.update(info(1)) or True, f'{name} startup timeout')
        return first

    def initialized_height(name):
        """The daemon's own 'Blockchain initialized. last block: N' line: the stored tip at database open."""
        found = INITIALIZED.findall((WORK / f'{name}.stdout.log').read_text(errors='replace'))
        require(found, f'{name} did not log its stored tip at open')
        return int(found[-1])

    def interrupted(signum, frame):
        raise RuntimeError(f'interrupted by signal {signum}')

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    address = None
    try:
        require(sorted(p.name for p in Path('/sys/class/net').iterdir()) == ['lo'],
                'inside mode requires an isolated network namespace with only loopback')
        launch.validate_profile(json.loads((WORK / 'profile.json').read_text()))
        require(digest(Path('/binary/monerod')) == launch.BINARY_SHA, 'mounted binary SHA-256 mismatch')
        require(digest(Path('/binary/monero-wallet-rpc')) == WALLET_SHA, 'mounted wallet SHA-256 mismatch')
        (WORK / 'data').mkdir(mode=0o700)  # Exclusive creation: never adopt stale node or wallet state.
        for n in (0, 1):
            (WORK / 'data' / f'peer{n}').mkdir()
            (WORK / f'peer{n}.conf').write_text('')
            start(f'peer{n}', daemon_command(n))
        wait(lambda: all(rpc(n, 'get_info')['synchronized'] for n in (0, 1)), 'core startup timeout')
        initial = {}
        for n in (0, 1):
            row, genesis = rpc(n, 'get_info'), header(n, 0)
            fork = rpc(n, 'hard_fork_info', {'version': 16})
            template = rpc(n, 'get_block_template', {'wallet_address': launch.ADDRESS})
            initial[str(n)] = {'info': row, 'genesis': genesis, 'fork': fork, 'template': template}
            require(row['height'] == 1 and row['nettype'] == 'mainnet', 'wrong fresh network mode')
            require(row['target'] == TARGET_SECONDS, 'wrong live target profile')
            require(genesis['hash'] == launch.EXPECTED['genesis_hash'] and genesis['reward'] == 0
                    and genesis['major_version'] == 1, 'wrong live genesis profile')
            require(fork['version'] == 16 and fork['earliest_height'] == 1, 'wrong live fork profile')
            require(template['expected_reward'] == REWARD and template['height'] == 1
                    and bytes.fromhex(template['blocktemplate_blob'])[0] == 16, 'wrong live reward/template fork')
        save(WORK / 'profile-readback.json', initial)
        wait(lambda: all(rpc(n, 'get_connections').get('connections') for n in (0, 1)), 'P2P handshake timeout')
        save(WORK / 'peers-before.json', [rpc(n, 'get_connections') for n in (0, 1)])

        # Payout wallet W on peer 1: disposable keys, created in memory, never on a command line or receipt.
        wdir = WORK / 'data' / 'W'
        wdir.mkdir(mode=0o700)
        (wdir / 'wallet.conf').write_text('')
        start('W', ['/binary/monero-wallet-rpc', '--config-file', str(wdir / 'wallet.conf'),
                    '--rpc-bind-ip', '127.0.0.1', '--rpc-bind-port', str(WALLET_PORT), '--disable-rpc-login',
                    '--wallet-dir', str(wdir), '--daemon-address', 'http://127.0.0.1:28181',
                    '--trusted-daemon', '--allow-mismatched-daemon-version', '--max-concurrency', '1',
                    '--log-level', '0', '--log-file', str(wdir / 'wallet.log')], private=True)
        wait(lambda: wrpc('get_version')['version'] > 0, 'wallet startup timeout')
        wrpc('create_wallet', {'filename': 'W', 'password': '', 'language': 'English'})
        address = wrpc('get_address')['address']
        require(address.startswith('M'), 'selected address prefix mismatch')
        # The payout address is omitted from the public mining receipt; the offline phase uses the public fixture.
        save(WORK / 'mining-command.json', {
            'payout': {'node': 0, 'endpoint': '/start_mining', 'miner_address': 'payout wallet W on peer 1 (omitted)',
                       'params': {'threads_count': 1, 'do_background_mining': False, 'ignore_battery': True}},
            'offline': {'node': 0, 'endpoint': '/start_mining', 'miner_address': launch.ADDRESS,
                        'params': {'threads_count': 1, 'do_background_mining': False, 'ignore_battery': True}}})
        event('two_peer_profile_verified', wallet='W on peer1', daemon_rpc='127.0.0.1:28181')

        # Seam 1: short chain paid out to W; both peers converge; W sees every coinbase through peer 1.
        payout = mine(PHASES['payout_min_top'], address, [0, 1], 'payout')
        for n in (0, 1):
            sample(f'peer{n}', n, 'after_payout')
        before = wallet_snapshot()
        wallet_height = wrpc('get_height')['height']
        require(before['address_matches'] and before['other'] == 0 and not before['outgoing'], 'unexpected payout wallet state')
        require(before['balance']['balance'] == payout['height'] * REWARD and before['balance']['unlocked_balance'] == 0,
                'payout balance does not equal mined rewards')
        require(sorted(t[2] for t in before['incoming']) == list(range(1, payout['height'] + 1))
                and all(t[1] == REWARD and t[3] == 'block' for t in before['incoming']), 'payout history mismatch')
        require(all(t[0] == header(1, t[2])['miner_tx_hash'] for t in before['incoming']), 'payout txids are not the coinbase hashes')
        event('payout_wallet_funded', tip=payout, balance=before['balance'], coinbase_entries=len(before['incoming']),
              wallet_height=wallet_height)

        # Seam 2: close W, cleanly restart peer 1 on its own data directory with no new blocks, reopen W.
        wallet_close()
        sample('peer1', 1, 'before_shutdown')
        tip_before = state(1)
        code = stop('peer1')
        require(code == 0, f'peer1 clean shutdown exit {code}')
        event('peer1_stopped', exit_code=code, tip=tip_before)
        restarted_at = elapsed()
        first = restart_peer1('peer1-restart')
        require(first['height'] == tip_before['height'] + 1 and first['top_block_hash'] == tip_before['hash'],
                'restarted peer did not open at its stored tip')
        wait(lambda: converged([0, 1]), 'plain restart convergence timeout', seconds=180)
        connections(1)
        wallet_open()
        after_restart = wallet_snapshot()
        require(after_restart == before, 'payout wallet state changed across the plain daemon restart')
        restart = {'tip_before_shutdown': tip_before, 'shutdown_exit_code': code, 'restarted_elapsed_s': restarted_at,
                   'stored_tip_at_open': initialized_height('peer1-restart'), 'first_rpc_info_after_restart': first,
                   'state_after_restart': state(1), 'blocks_missed': state(1)['height'] - tip_before['height'],
                   'wallet_height_before': wallet_height, 'wallet_height_after': wrpc('get_height')['height'],
                   'wallet_before': before, 'wallet_after': after_restart}
        require(restart['stored_tip_at_open'] == tip_before['height'], 'daemon log disagrees with the stored tip')
        save(WORK / 'wallet-restart.json', restart)
        event('wallet_reopened_after_restart', address_matches=True, balance=after_restart['balance'],
              coinbase_entries=len(after_restart['incoming']), blocks_missed=restart['blocks_missed'])

        # Seam 3: cold backup of peer 1's data directory with the daemon stopped, destroy, mine on, restore, rejoin.
        wallet_close()
        sample('peer1-restart', 1, 'before_cold_shutdown')
        tip_backup = state(1)
        code = stop('peer1-restart')
        require(code == 0, f'peer1-restart clean shutdown exit {code}')
        event('peer1_stopped_for_backup', exit_code=code, tip=tip_backup)
        data = WORK / 'data' / 'peer1'
        archive = WORK / 'data' / 'peer1-backup.tar'
        source = file_manifest(data)
        require('lmdb/data.mdb' in source, 'no LMDB database in the stopped data directory')
        with tarfile.open(archive, 'w') as tar:
            tar.add(data, arcname='peer1')
        backup = {'tip_at_backup': tip_backup, 'shutdown_exit_code': code, 'source_manifest': source,
                  'archive': {'path_relative_to_work': 'data/peer1-backup.tar', 'bytes': archive.stat().st_size, 'sha256': digest(archive)},
                  'backed_up_elapsed_s': elapsed()}
        shutil.rmtree(data)
        backup['data_dir_absent_after_destroy'] = not data.exists()
        require(backup['data_dir_absent_after_destroy'], 'peer1 data directory still present after destroy')
        event('cold_backup_taken_and_destroyed', tip=tip_backup, files=len(source), archive_bytes=backup['archive']['bytes'])
        offline = mine(PHASES['offline_blocks'], launch.ADDRESS, [0], 'peer1_destroyed')
        backup['tip_mined_while_destroyed'] = offline
        with tarfile.open(archive) as tar:
            tar.extractall(WORK / 'data', filter='data')
        restored = file_manifest(data)
        require(restored == source, 'restored data directory differs from the cold backup')
        backup.update(restored_manifest_equal=True, restored_elapsed_s=elapsed())
        event('cold_backup_restored', files=len(restored))
        restarted_at = elapsed()
        first = restart_peer1('peer1-restore')
        require(first['height'] >= tip_backup['height'] + 1, 'restored peer lost stored blocks')
        require(header(1, tip_backup['height'])['hash'] == tip_backup['hash'], 'restored peer changed its stored tip')
        wait(lambda: converged([0, 1]), 'restore rejoin timeout', seconds=180)
        caught_up_at = elapsed()
        backup.update(restarted_elapsed_s=restarted_at, stored_tip_at_open=initialized_height('peer1-restore'),
                      first_rpc_info_after_restore=first, caught_up_elapsed_s=caught_up_at,
                      rejoin_seconds_from_restart=caught_up_at - restarted_at, state_after_rejoin=state(1),
                      blocks_missed=offline['height'] - tip_backup['height'], sync_info=rpc(1, 'sync_info'),
                      connections=rpc(1, 'get_connections'))
        require(backup['stored_tip_at_open'] == tip_backup['height'], 'restored database did not open at the backup tip')
        connections(1)
        save(WORK / 'cold-restore.json', backup)
        event('peer1_restored_rejoined', rejoin_seconds=backup['rejoin_seconds_from_restart'], blocks_missed=backup['blocks_missed'],
              tip=backup['state_after_rejoin'])
        wallet_open()
        after_restore = wallet_snapshot()
        require(after_restore == before, 'payout wallet state changed across the cold restore')
        restart.update(wallet_after_cold_restore=after_restore, wallet_height_after_cold_restore=wrpc('get_height')['height'])
        save(WORK / 'wallet-restart.json', restart)
        event('wallet_reopened_after_restore', address_matches=True, balance=after_restore['balance'],
              coinbase_entries=len(after_restore['incoming']))

        # Final reconciliation across both peers.
        states = [state(n) for n in (0, 1)]
        wanted = states[0]
        require(all(s == wanted for s in states), 'tip/work/emission mismatch across peers')
        require(wanted['height'] >= sum(PHASES.values()), 'chain shorter than the phase minimum')
        require(wanted['emission_atomic'] == wanted['height'] * REWARD, 'wrong total emission')
        require(wanted['fees_atomic'] == 0, 'unexpected fees in empty-block witness')
        headers = [[header(n, h) for h in range(wanted['height'] + 1)] for n in (0, 1)]
        for chain in headers:
            require(chain == headers[0], 'header sets differ across peers')
            require(all(h['major_version'] == 16 and h['reward'] == REWARD for h in chain[1:]), 'wrong mined reward/fork profile')
        save(WORK / 'headers.json', headers)
        save(WORK / 'rpc-final.json', [
            {'info': rpc(n, 'get_info'), 'tip': rpc(n, 'get_last_block_header'),
             'sum': rpc(n, 'get_coinbase_tx_sum', {'height': 0, 'count': wanted['height'] + 1})} for n in (0, 1)])
        save(WORK / 'peers-after.json', [rpc(n, 'get_connections') for n in (0, 1)])
        sample('peer0', 0, 'final')
        sample('peer1-restore', 1, 'final')
        result.update(result='PASS', peers=states, phases=PHASES, payout_tip=payout, restore_rejoin_s=backup['rejoin_seconds_from_restart'],
                      blocks_missed_while_destroyed=backup['blocks_missed'], backup_archive_sha256=backup['archive']['sha256'],
                      delivery='native mining on peer0 only; peer1, the restarted peer1 and the restored peer1 receive through TCP P2P only')
        event('converged', peers=states)
    except Exception as error:
        # Wallet/transport exceptions could carry keys: the type and a fixed message only.
        message = str(error) if isinstance(error, (ValueError, TimeoutError, RuntimeError)) else 'see logs'
        result.update(result='FAIL', error_type=type(error).__name__, error=message)
        event('failure', error_type=type(error).__name__, error=message)
    finally:
        for name in list(procs):
            stop(name, timeout=30)
        resources = {p.name: p.read_text() for p in (Path('/sys/fs/cgroup') / name for name in
                     ('memory.peak', 'memory.events', 'memory.max', 'memory.swap.max', 'cpu.max', 'cpu.stat')) if p.exists()}
        resources.update(daemon_exit_codes=exits, elapsed_seconds=elapsed())
        save(WORK / 'resources.json', resources)
        save(WORK / 'rpc-methods.json', calls)
        if sorted(exits) != ['W', 'peer0', 'peer1', 'peer1-restart', 'peer1-restore'] or any(exits.values()):
            result.update(result='FAIL', shutdown_error=exits)
        save(WORK / 'result.json', result)
    return 0 if result['result'] == 'PASS' else 1


def admission(binary, wallet, profile):
    manifest = launch.preflight(binary, profile)
    require(digest(wallet) == WALLET_SHA, f'wallet SHA-256 mismatch: expected {WALLET_SHA}')
    require(digest(RECIPE_MANIFEST) == RECIPE_MANIFEST_SHA, 'accepted recipe manifest mismatch')
    inputs = {}
    for line in RECIPE_MANIFEST.read_text().splitlines():
        expected, name = line.split('  ', 1)
        require(digest(ROOT / name) == expected, f'accepted recipe input differs: {name}')
        inputs[name] = expected
    for path in [RECIPE_MANIFEST, *(HERE / name for name in NEW_FILES)]:
        inputs[str(path.relative_to(ROOT))] = digest(path)
    return manifest, inputs


def outside(args):
    binary, wallet, profile, work = args.binary.resolve(), args.wallet.resolve(), args.profile.resolve(), args.work.absolute()
    require(not work.exists() and not work.is_symlink(), f'stale data/output directory refused: {work}; choose a new path')
    manifest, inputs = admission(binary, wallet, profile)
    if args.check_only:
        print('PASS: accepted recipe manifest, profile, binary, wallet and baseline inputs verified; no process started')
        return 0
    work.mkdir(parents=True, mode=0o700)
    save(work / 'launcher-command.json', [sys.executable, *sys.argv])
    save(work / 'baseline.json', manifest)
    shutil.copyfile(profile, work / 'profile.json')
    (work / 'INPUTS.sha256').write_text(''.join(f'{v}  {k}\n' for k, v in sorted(inputs.items())))
    (work / 'BINARY.sha256').write_text(f'{digest(binary)}  {binary}\n{digest(wallet)}  {wallet}\n')
    code = 2
    try:
        # This is the existing shared resource lock, not a scratch directory.
        with open('/tmp/meownero-swarm-20260912-heavy.lock', 'a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                save(work / 'result.json', {'result': 'BLOCKED', 'reason': 'shared heavy lock busy; wait for its owner and rerun with a fresh path'})
                print('BLOCKED: shared heavy lock busy', file=sys.stderr)
                code = 75
                return code
            available = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                                 if line.startswith('MemAvailable:'))) * 1024
            free = shutil.disk_usage(work).free
            save(work / 'preflight-resources.json', {'available_ram_bytes': available, 'free_disk_bytes': free,
                                                   'minimum_bytes': 5 * 1024**3})
            require(min(available, free) >= 5 * 1024**3, 'need at least 5 GiB available RAM and disk')
            name = f'meow-tjs287-{os.getpid()}'
            command = ['docker', 'run', '--rm', '--pull=never', '--name', name, '--network', 'none',
                       '--memory=4g', '--memory-swap=4g', '--cpus=2', '--pids-limit=256',
                       '--user', f'{os.getuid()}:{os.getgid()}', '--cap-drop=ALL', '--security-opt=no-new-privileges',
                       '--read-only', '--tmpfs', '/tmp:rw,nosuid,nodev,size=64m',
                       '-e', 'PYTHONDONTWRITEBYTECODE=1', '-e', 'HOME=/tmp',
                       '-v', f'{binary}:/binary/monerod:ro', '-v', f'{wallet}:/binary/monero-wallet-rpc:ro',
                       '-v', f'{HERE}:/recipe:ro', '-v', f'{work}:/work', launch.IMAGE,
                       'timeout', '--signal=TERM', '--kill-after=75', str(RUN_LIMIT_SECONDS),
                       'python3', '-B', '-u', '/recipe/recover.py', '--inside']
            save(work / 'container-command.json', command)
            process = None
            try:
                with (work / 'run.log').open('w') as log:
                    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                    for line in process.stdout:
                        print(line, end='', flush=True)
                        log.write(line)
                        log.flush()
                    code = process.wait()
                (work / 'container.exit').write_text(str(code) + '\n')
                return code
            finally:
                if process is not None and process.poll() is None:
                    stopped = subprocess.run(['docker', 'stop', '--time', '65', name], capture_output=True, text=True)
                    save(work / 'interrupted-stop.json', {'exit': stopped.returncode, 'stdout': stopped.stdout, 'stderr': stopped.stderr})
                    process.wait(timeout=15)
                    (work / 'container.exit').write_text(str(process.returncode) + '\n')
                cleanup = subprocess.run(['docker', 'rm', '-f', name], capture_output=True, text=True)
                save(work / 'cleanup.json', {'command': ['docker', 'rm', '-f', name], 'exit': cleanup.returncode,
                                             'stdout': cleanup.stdout, 'stderr': cleanup.stderr})
    finally:
        (work / 'launcher.exit').write_text(str(code) + '\n')
        public = sorted(p for p in work.iterdir() if p.is_file() and p.name != 'EVIDENCE.sha256')
        (work / 'EVIDENCE.sha256').write_text(''.join(f'{digest(p)}  {p.name}\n' for p in public))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    bindir = ROOT / 'build/repro-selected-20260918/selected-9-90/first/source/build/release/bin'
    parser.add_argument('--binary', type=Path, default=bindir / 'monerod')
    parser.add_argument('--wallet', type=Path, default=bindir / 'monero-wallet-rpc')
    parser.add_argument('--profile', type=Path, default=HERE / 'profile.json')
    parser.add_argument('--work', type=Path)
    parser.add_argument('--check-only', action='store_true')
    parser.add_argument('--inside', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.inside:
        return inside()
    if args.work is None:
        parser.error('--work requires a fresh directory path')
    try:
        return outside(args)
    except KeyboardInterrupt:
        print('Interrupted; owned container stopped', file=sys.stderr)
        return 130
    except (OSError, ValueError, KeyError) as error:
        print(f'REFUSED: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
