#!/usr/bin/env python3
"""TJS-242: late-peer P2P sync and restart catch-up on the accepted testnet v0 launch recipe."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

import launch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
WORK = Path('/work')
RECIPE_MANIFEST = ROOT / 'research/evidence/testnet-v0-launch-tjs229-2026-09-20/launch/INPUTS.sha256'
RECIPE_MANIFEST_SHA = '1e3b8a784828b05634abd4b4ac22ba7cc83652b32af023c71c146f3216a5e59f'
REWARD = launch.EXPECTED['reward_atomic']
# Minimum new blocks per seam. Native DAA reaches roughly one block per 90 s after
# the first eight blocks under one mining thread, so the seams stay small.
PHASES = {'two_peer_min_top': 5, 'three_peer_blocks': 2, 'offline_blocks': 2}
POLL_SECONDS = 0.1
NEW_FILES = ['sync.py', 'verify-sync.py', 'test-sync-refusals.py', 'sync-journey.md']
save, require, digest = launch.save, launch.require, launch.digest


def daemon_command(n, peers):
    """Recipe v1 daemon arguments plus one loopback admission flag.

    monerod admits one inbound connection per IP by default (net_node.inl:239). Three
    loopback peers need a higher limit, so every daemon gets --max-connections-per-ip 3.
    This is a P2P admission limit for the isolated testbed, not a consensus change.
    """
    cmd = ['/binary/monerod', '--config-file', str(WORK / f'peer{n}.conf'), '--data-dir', str(WORK / 'data' / f'peer{n}'),
           '--non-interactive', '--no-igd', '--disable-dns-checkpoints', '--check-updates', 'disabled',
           '--max-concurrency', '1', '--allow-local-ip', '--hide-my-port', '--max-connections-per-ip', '3']
    for p in peers:
        cmd += ['--add-exclusive-node', f'127.0.0.1:{28080 + p * 100}']
    return cmd + ['--p2p-bind-ip', '127.0.0.1', '--p2p-bind-port', str(28080 + n * 100),
                  '--rpc-bind-ip', '127.0.0.1', '--rpc-bind-port', str(28081 + n * 100),
                  '--rpc-ssl', 'disabled', '--no-zmq', '--log-level', '1', '--log-file', str(WORK / f'peer{n}.log')]


def inside():
    procs, commands, exits, calls, seen, usage = {}, {}, {}, {}, {}, {}
    started = time.monotonic()
    clk = os.sysconf('SC_CLK_TCK')
    result = {'result': 'FAIL', 'scope': 'three local P2P peers; late join; clean restart; native miner and DAA; empty blocks'}

    def elapsed():
        return time.monotonic() - started

    def event(label, **fields):
        print(json.dumps({'event': label, 'elapsed_s': elapsed(), **fields}), flush=True)

    def rpc(node, method, params=None, endpoint=False):
        # Every RPC call is counted per node so receipts show no block injection.
        calls.setdefault(f'peer{node}', {})[method] = calls.setdefault(f'peer{node}', {}).get(method, 0) + 1
        return launch.rpc(node, method, params, endpoint)

    def wait(check, label, seconds=120):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            require(all(p.poll() is None for p in procs.values()), 'daemon exited early')
            try:
                if check():
                    return
            except (OSError, ValueError, KeyError):
                pass
            time.sleep(POLL_SECONDS)
        raise TimeoutError(label)

    def start(name, n, peers):
        commands[name] = daemon_command(n, peers)
        save(WORK / 'daemon-commands.json', commands)
        with (WORK / f'{name}.stdout.log').open('w') as log:
            procs[name] = subprocess.Popen(commands[name], stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)

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

    def observe(nodes):
        heights = {}
        for n in nodes:
            try:
                heights[n] = rpc(n, 'get_info')['height']
            except (OSError, ValueError, KeyError):
                continue
            seen.setdefault(f'{n}:{heights[n]}', elapsed())
        return heights

    def converged(nodes):
        return len({json.dumps(state(n), sort_keys=True) for n in nodes}) == 1

    def sample(name, n, label):
        pid = procs[name].pid
        status = dict(line.split(':', 1) for line in Path(f'/proc/{pid}/status').read_text().splitlines())
        stat = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        files = [p.stat() for p in (WORK / 'data' / f'peer{n}').rglob('*') if p.is_file()]
        row = {'elapsed_s': elapsed(), 'vm_hwm_kib': int(status['VmHWM'].split()[0]), 'vm_rss_kib': int(status['VmRSS'].split()[0]),
               'threads': int(status['Threads']), 'cpu_user_s': int(stat[11]) / clk, 'cpu_system_s': int(stat[12]) / clk,
               'data_dir_allocated_bytes': sum(s.st_blocks * 512 for s in files),
               'data_dir_apparent_bytes': sum(s.st_size for s in files), 'data_dir_files': len(files)}
        try:
            io = dict(line.split(': ') for line in Path(f'/proc/{pid}/io').read_text().splitlines())
            row.update(io_read_bytes=int(io['read_bytes']), io_write_bytes=int(io['write_bytes']))
        except (OSError, KeyError, ValueError):
            pass
        usage.setdefault(name, {})[label] = row
        save(WORK / 'process-usage.json', usage)
        return row

    def mine(min_blocks, nodes, label):
        start_top = state(0)['height']
        rpc(0, 'start_mining', mining, endpoint=True)
        event('mining_started', phase=label, start_top=start_top, minimum_blocks=min_blocks, live=[f'peer{n}' for n in nodes])
        try:
            wait(lambda: observe(nodes).get(0, 0) - 1 >= start_top + min_blocks, f'native mining: {label}', seconds=600)
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

    def interrupted(signum, frame):
        raise RuntimeError(f'interrupted by signal {signum}')

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    mining = {'miner_address': launch.ADDRESS, 'threads_count': 1, 'do_background_mining': False, 'ignore_battery': True}
    try:
        require(sorted(p.name for p in Path('/sys/class/net').iterdir()) == ['lo'],
                'inside mode requires an isolated network namespace with only loopback')
        launch.validate_profile(json.loads((WORK / 'profile.json').read_text()))
        require(digest(Path('/binary/monerod')) == launch.BINARY_SHA, 'mounted binary SHA-256 mismatch')
        (WORK / 'data').mkdir()  # Exclusive creation: never adopt stale node state.
        for n in (0, 1):
            (WORK / 'data' / f'peer{n}').mkdir()
            (WORK / f'peer{n}.conf').write_text('')
            start(f'peer{n}', n, [1 - n])
        wait(lambda: all(rpc(n, 'get_info')['synchronized'] for n in (0, 1)), 'core startup timeout')
        initial = {}
        for n in (0, 1):
            info, genesis = rpc(n, 'get_info'), header(n, 0)
            fork = rpc(n, 'hard_fork_info', {'version': 16})
            template = rpc(n, 'get_block_template', {'wallet_address': launch.ADDRESS})
            initial[str(n)] = {'info': info, 'genesis': genesis, 'fork': fork, 'template': template}
            require(info['height'] == 1 and info['nettype'] == 'mainnet', 'wrong fresh network mode')
            require(info['target'] == launch.EXPECTED['target_seconds'], 'wrong live target profile')
            require(genesis['hash'] == launch.EXPECTED['genesis_hash'] and genesis['reward'] == 0
                    and genesis['major_version'] == 1, 'wrong live genesis profile')
            require(fork['version'] == 16 and fork['earliest_height'] == 1, 'wrong live fork profile')
            require(template['expected_reward'] == REWARD and template['height'] == 1
                    and bytes.fromhex(template['blocktemplate_blob'])[0] == 16, 'wrong live reward/template fork')
        save(WORK / 'profile-readback.json', initial)
        wait(lambda: all(rpc(n, 'get_connections').get('connections') for n in (0, 1)), 'P2P handshake timeout')
        save(WORK / 'peers-before.json', [rpc(n, 'get_connections') for n in (0, 1)])
        save(WORK / 'mining-command.json', {'node': 0, 'endpoint': '/start_mining', 'params': mining})
        event('two_peer_profile_verified')

        # Seam 1: accepted two-peer chain (recipe v1 behaviour, reused not re-accepted).
        two_peer = mine(PHASES['two_peer_min_top'], [0, 1], 'two_peer')
        for n in (0, 1):
            sample(f'peer{n}', n, 'after_two_peer')

        # Seam 2: fresh late peer receives the chain through P2P only.
        (WORK / 'data' / 'peer2').mkdir()
        (WORK / 'peer2.conf').write_text('')
        joined_at = elapsed()
        start('peer2', 2, [0, 1])
        first = {}
        wait(lambda: first.update(rpc(2, 'get_info')) or True, 'late peer startup timeout')
        first = {k: first[k] for k in ('height', 'top_block_hash', 'synchronized', 'incoming_connections_count',
                                        'outgoing_connections_count')}
        wait(lambda: state(2) == two_peer, 'late peer sync timeout', seconds=180)
        synced_at = elapsed()
        late = {'peer2_started_elapsed_s': joined_at, 'first_rpc_info': first, 'synced_elapsed_s': synced_at,
                'sync_seconds_from_start': synced_at - joined_at, 'target_state': two_peer, 'peer2_state': state(2),
                'sync_info': rpc(2, 'sync_info'), 'connections': rpc(2, 'get_connections')}
        rows = connections(2)
        late['p2p_bytes_received'] = sum(c['recv_count'] for c in rows)
        late['p2p_bytes_sent'] = sum(c['send_count'] for c in rows)
        require(late['p2p_bytes_received'] > 0, 'late peer received no P2P bytes')
        save(WORK / 'late-peer-sync.json', late)
        sample('peer2', 2, 'after_late_sync')
        event('late_peer_synced', sync_seconds=late['sync_seconds_from_start'], bytes_received=late['p2p_bytes_received'], tip=two_peer)

        # Seam 3: all three connected peers converge on new blocks.
        three_peer = mine(PHASES['three_peer_blocks'], [0, 1, 2], 'three_peer')
        save(WORK / 'peers-three.json', [rpc(n, 'get_connections') for n in (0, 1, 2)])

        # Seam 4: clean shutdown, mining continues, restart on the same data directory.
        before_restart = state(1)
        sample('peer1', 1, 'before_shutdown')
        code = stop('peer1')
        stopped_at = elapsed()
        require(code == 0, f'peer1 clean shutdown exit {code}')
        event('peer1_stopped', exit_code=code, tip=before_restart)
        offline = mine(PHASES['offline_blocks'], [0, 2], 'peer1_offline')
        restarted_at = elapsed()
        start('peer1-restart', 1, [0])
        require(commands['peer1-restart'] == commands['peer1'], 'restart must reuse the exact daemon command')
        first = {}
        wait(lambda: first.update(rpc(1, 'get_info')) or True, 'restart startup timeout')
        first = {k: first[k] for k in ('height', 'top_block_hash', 'synchronized')}
        require(first['height'] >= before_restart['height'] + 1, 'restarted peer lost stored blocks')
        require(header(1, before_restart['height'])['hash'] == before_restart['hash'], 'restarted peer changed its stored tip')
        wait(lambda: converged([0, 1, 2]), 'restart catch-up timeout', seconds=180)
        caught_up_at = elapsed()
        restart = {'tip_before_shutdown': before_restart, 'shutdown_exit_code': code, 'stopped_elapsed_s': stopped_at,
                   'tip_mined_while_offline': offline, 'blocks_missed': offline['height'] - before_restart['height'],
                   'restarted_elapsed_s': restarted_at, 'first_rpc_info_after_restart': first,
                   'caught_up_elapsed_s': caught_up_at, 'catch_up_seconds_from_restart': caught_up_at - restarted_at,
                   'peer1_state_after_catch_up': state(1), 'sync_info': rpc(1, 'sync_info'), 'connections': rpc(1, 'get_connections')}
        connections(1)
        save(WORK / 'restart-catchup.json', restart)
        event('peer1_restarted_caught_up', catch_up_seconds=restart['catch_up_seconds_from_restart'],
              blocks_missed=restart['blocks_missed'], tip=restart['peer1_state_after_catch_up'])

        # Final reconciliation across all three peers.
        states = [state(n) for n in (0, 1, 2)]
        wanted = states[0]
        require(all(s == wanted for s in states), 'tip/work/emission mismatch across peers')
        require(wanted['height'] >= sum(PHASES.values()), 'chain shorter than the phase minimum')
        require(wanted['emission_atomic'] == wanted['height'] * REWARD, 'wrong total emission')
        require(wanted['fees_atomic'] == 0, 'unexpected fees in empty-block witness')
        headers = [[header(n, h) for h in range(wanted['height'] + 1)] for n in (0, 1, 2)]
        for chain in headers:
            require(chain == headers[0], 'header sets differ across peers')
            require(all(h['major_version'] == 16 and h['reward'] == REWARD for h in chain[1:]), 'wrong mined reward/fork profile')
        save(WORK / 'headers.json', headers)
        save(WORK / 'rpc-final.json', [
            {'info': rpc(n, 'get_info'), 'tip': rpc(n, 'get_last_block_header'),
             'sum': rpc(n, 'get_coinbase_tx_sum', {'height': 0, 'count': wanted['height'] + 1})} for n in (0, 1, 2)])
        save(WORK / 'peers-after.json', [rpc(n, 'get_connections') for n in (0, 1, 2)])
        relay = {}
        for key, at in seen.items():
            n, height = key.split(':')
            relay.setdefault(height, {})[f'peer{n}'] = at
        arrivals = {h: {'first_seen_elapsed_s': v, 'spread_s': max(v.values()) - min(v.values())}
                    for h, v in sorted(relay.items(), key=lambda kv: int(kv[0])) if len(v) > 1}
        save(WORK / 'relay.json', {'poll_interval_s': POLL_SECONDS, 'rpc_height_first_seen': arrivals,
                                   'note': 'coarse RPC-height polling; bounded by poll cadence and RPC latency, not wire timing'})
        for name in list(procs):
            sample(name, int(name[4]), 'final')
        result.update(result='PASS', peers=states, phases=PHASES, late_peer_sync_s=late['sync_seconds_from_start'],
                      restart_catch_up_s=restart['catch_up_seconds_from_restart'], blocks_missed=restart['blocks_missed'],
                      delivery='native mining on peer0 only; peer1, peer2 and the restarted peer1 receive through TCP P2P only')
        event('converged', peers=states)
    except Exception as error:
        result.update(result='FAIL', error=str(error))
        event('failure', error=str(error))
    finally:
        for name in list(procs):
            stop(name, timeout=30)
        resources = {p.name: p.read_text() for p in (Path('/sys/fs/cgroup') / name for name in
                     ('memory.peak', 'memory.events', 'memory.max', 'memory.swap.max', 'cpu.max', 'cpu.stat')) if p.exists()}
        resources.update(daemon_exit_codes=exits, elapsed_seconds=elapsed())
        save(WORK / 'resources.json', resources)
        save(WORK / 'rpc-methods.json', calls)
        if sorted(exits) != ['peer0', 'peer1', 'peer1-restart', 'peer2'] or any(exits.values()):
            result.update(result='FAIL', shutdown_error=exits)
        save(WORK / 'result.json', result)
    return 0 if result['result'] == 'PASS' else 1


def admission(binary, profile):
    manifest = launch.preflight(binary, profile)
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
    binary, profile, work = args.binary.resolve(), args.profile.resolve(), args.work.absolute()
    require(not work.exists() and not work.is_symlink(), f'stale data/output directory refused: {work}; choose a new path')
    manifest, inputs = admission(binary, profile)
    if args.check_only:
        print('PASS: accepted recipe manifest, profile, binary and baseline inputs verified; no process started')
        return 0
    work.mkdir(parents=True)
    save(work / 'launcher-command.json', [sys.executable, *sys.argv])
    save(work / 'baseline.json', manifest)
    shutil.copyfile(profile, work / 'profile.json')
    (work / 'INPUTS.sha256').write_text(''.join(f'{v}  {k}\n' for k, v in sorted(inputs.items())))
    (work / 'BINARY.sha256').write_text(f'{digest(binary)}  {binary}\n')
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
            name = f'meow-tjs242-{os.getpid()}'
            command = ['docker', 'run', '--rm', '--pull=never', '--name', name, '--network', 'none',
                       '--memory=4g', '--memory-swap=4g', '--cpus=2', '--pids-limit=256',
                       '--user', f'{os.getuid()}:{os.getgid()}', '--cap-drop=ALL', '--security-opt=no-new-privileges',
                       '--read-only', '--tmpfs', '/tmp:rw,nosuid,nodev,size=64m',
                       '-e', 'PYTHONDONTWRITEBYTECODE=1', '-e', 'HOME=/tmp',
                       '-v', f'{binary}:/binary/monerod:ro', '-v', f'{HERE}:/recipe:ro', '-v', f'{work}:/work', launch.IMAGE,
                       'timeout', '--signal=TERM', '--kill-after=75', '1500', 'python3', '-B', '-u', '/recipe/sync.py', '--inside']
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
    parser.add_argument('--binary', type=Path, default=ROOT / 'build/repro-selected-20260918/selected-9-90/first/source/build/release/bin/monerod')
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
