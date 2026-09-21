#!/usr/bin/env python3
"""TJS-297: restart the F4 candidate pool against a running two-peer chain; work must resume at the common tip."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time

import launch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
WORK = Path('/work')
RECIPE_MANIFEST = ROOT / 'research/evidence/testnet-v0-launch-tjs229-2026-09-20/launch/INPUTS.sha256'
RECIPE_MANIFEST_SHA = '1e3b8a784828b05634abd4b4ac22ba7cc83652b32af023c71c146f3216a5e59f'
# TJS-187 candidate p2pool, rebuilt byte-identically from the pinned sources in TJS-224. Light mode, no dataset.
POOL_SHA = 'bbc3240607bf40bd3db7e13f011ccf9eda431dddd751918a3ebf4e3aaf129fad'
POOL_INPUTS = {  # pinned by docs/testnet-v0-freeze-tjs223-2026-09-20.md, "Exact baseline"
    'spikes/p2pool/full-source-lock.json': '62354e6535323f07a9d3ece27335cd1df2da730a39cf32e1b3f782333c7cfb3c',
    'spikes/p2pool/meownero-local.patch': '0b28c5d96d33de90436ec7cdce2d58bf5af8c29d2a3f0c98202d57bde89dede6',
}
REWARD = launch.EXPECTED['reward_atomic']
TARGET_SECONDS = launch.EXPECTED['target_seconds']
# Minimum new blocks per seam; the whole chain stays inside the fast first-eight-block DAA window.
PHASES = {'initial_blocks': 3, 'live_blocks': 2, 'down_blocks': 2}
POLL_SECONDS = 0.1
RUN_LIMIT_SECONDS = 1800
NEW_FILES = ['pool-restart.py', 'verify-pool-restart.py', 'test-pool-restart-refusals.py', 'pool-restart-journey.md']
ZMQ_RPC_PORT, ZMQ_PUB_PORT, POOL_P2P_PORT, STRATUM_PORT = 28182, 28183, 28185, 28186  # peer 1 side, container loopback
save, require, digest = launch.save, launch.require, launch.digest


def phase_limit(count):
    """Twice the DAA-expected phase time plus fixed slack; a timeout is still an incomplete journey."""
    return 120 + 2 * count * TARGET_SECONDS


def daemon_command(n):
    """The accepted recipe v1 daemon command; peer 1 publishes ZMQ for the pool instead of --no-zmq."""
    zmq = (['--no-zmq'] if n == 0 else
           ['--zmq-rpc-bind-ip', '127.0.0.1', '--zmq-rpc-bind-port', str(ZMQ_RPC_PORT), '--zmq-pub', f'tcp://127.0.0.1:{ZMQ_PUB_PORT}'])
    return ['/binary/monerod', '--config-file', str(WORK / f'peer{n}.conf'), '--data-dir', str(WORK / 'data' / f'peer{n}'),
            '--non-interactive', '--no-igd', '--disable-dns-checkpoints', '--check-updates', 'disabled',
            '--max-concurrency', '1', '--allow-local-ip', '--hide-my-port',
            '--add-exclusive-node', f'127.0.0.1:{28080 + (1 - n) * 100}',
            '--p2p-bind-ip', '127.0.0.1', '--p2p-bind-port', str(28080 + n * 100),
            '--rpc-bind-ip', '127.0.0.1', '--rpc-bind-port', str(28081 + n * 100),
            '--rpc-ssl', 'disabled', *zmq, '--log-level', '1', '--log-file', str(WORK / f'peer{n}.log')]


def pool_command():
    """F4 candidate pool on peer 1 only: public fixture payout address, loopback listeners, no built-in miner, no cache."""
    return ['/pool/p2pool', '--wallet', launch.ADDRESS, '--host', '127.0.0.1', '--rpc-port', '28181', '--zmq-port', str(ZMQ_PUB_PORT),
            '--p2p', f'127.0.0.1:{POOL_P2P_PORT}', '--stratum', f'127.0.0.1:{STRATUM_PORT}', '--no-dns',
            '--in-peers', '10', '--out-peers', '10', '--data-dir', str(WORK / 'data' / 'pool'),
            '--data-api', str(WORK / 'data' / 'pool-api'), '--local-api', '--light-mode', '--full-validation',
            '--no-cache', '--no-color', '--loglevel', '4', '--log-file', str(WORK / 'pool.log')]


def stratum_job():
    """Log in once on the pool's stratum port and return the public fields of its current job."""
    with socket.create_connection(('127.0.0.1', STRATUM_PORT), timeout=30) as sock:
        sock.sendall(json.dumps({'id': 1, 'method': 'login', 'params': {
            'login': 'pool-restart-witness', 'pass': 'x', 'agent': 'meownero-testnet-v0-pool-restart'}}).encode() + b'\n')
        with sock.makefile('rb') as stream:
            reply = json.loads(stream.readline())
    require(reply.get('result', {}).get('status') == 'OK', 'stratum login failed')
    job = reply['result']['job']
    blob, offset = bytes.fromhex(job['blob']), 0
    for _ in range(3):  # major version, minor version, timestamp varints precede the 32-byte previous block id
        while blob[offset] & 128:
            offset += 1
        offset += 1
    return {'height': job['height'], 'algo': job['algo'], 'seed_hash': job['seed_hash'], 'job_id': job['job_id'],
            'target': job['target'], 'blob_bytes': len(blob), 'major_version': blob[0], 'minor_version': blob[1],
            'prev_hash': blob[offset:offset + 32].hex()}


def pool_api():
    """The pool's own JSON data API: its mainchain view and pool statistics."""
    api = WORK / 'data' / 'pool-api'
    return {'network': json.loads((api / 'network' / 'stats').read_text()), 'pool': json.loads((api / 'pool' / 'stats').read_text())}


def inside():
    procs, commands, exits, calls, usage = {}, {}, {}, {}, {}
    started = time.monotonic()
    clk = os.sysconf('SC_CLK_TCK')
    result = {'result': 'FAIL', 'scope': 'two local P2P peers; F4 candidate pool on peer 1 (light mode, no miner); '
                                         'pool stopped and restarted with the identical command; native miner and DAA; empty blocks'}

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

    def start(name, command):
        commands[name] = command
        save(WORK / 'process-commands.json', commands)
        with (WORK / f'{name}.stdout.log').open('w') as log:
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

    def sample(name, datadir, label):
        pid = procs[name].pid
        status = dict(line.split(':', 1) for line in Path(f'/proc/{pid}/status').read_text().splitlines())
        stat = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        files = [p.stat() for p in datadir.rglob('*') if p.is_file()]
        row = {'elapsed_s': elapsed(), 'vm_hwm_kib': int(status['VmHWM'].split()[0]), 'vm_rss_kib': int(status['VmRSS'].split()[0]),
               'threads': int(status['Threads']), 'cpu_user_s': int(stat[11]) / clk, 'cpu_system_s': int(stat[12]) / clk,
               'data_dir_allocated_bytes': sum(s.st_blocks * 512 for s in files),
               'data_dir_apparent_bytes': sum(s.st_size for s in files), 'data_dir_files': len(files)}
        usage.setdefault(name, {})[label] = row
        save(WORK / 'process-usage.json', usage)
        return row

    def mine(min_blocks, label):
        start_top = state(0)['height']
        params = {'miner_address': launch.ADDRESS, 'threads_count': 1, 'do_background_mining': False, 'ignore_battery': True}
        rpc(0, 'start_mining', params, endpoint=True)
        event('mining_started', phase=label, start_top=start_top, minimum_blocks=min_blocks, limit_seconds=phase_limit(min_blocks))
        try:
            wait(lambda: rpc(0, 'get_info')['height'] - 1 >= start_top + min_blocks, f'native mining: {label}',
                 seconds=phase_limit(min_blocks))
        finally:
            rpc(0, 'stop_mining', endpoint=True)
        wait(lambda: converged([0, 1]), f'P2P convergence: {label}', seconds=120)
        tip = state(0)
        event('mining_stopped_converged', phase=label, tip=tip)
        return tip

    def connections(n):
        rows = rpc(n, 'get_connections').get('connections', [])
        require(rows and all(c['ip'] == '127.0.0.1' for c in rows), f'peer{n} needs local P2P connections')
        return rows

    def job_at(tip):
        """The pool's current stratum job must build on exactly this tip; returns job plus the pool's API view."""
        job = stratum_job()
        require(job['height'] == tip['height'] + 1 and job['prev_hash'] == tip['hash'], 'pool job is not on the common tip')
        require(job['algo'] == 'rx/0' and job['major_version'] == 16, 'pool job algorithm or fork mismatch')
        api = pool_api()
        require(api['network']['hash'] == tip['hash'] and api['network']['height'] == tip['height'], 'pool API tip disagrees with the daemons')
        require(api['pool']['pool_statistics']['totalBlocksFound'] == 0, 'the pool must not have submitted blocks')
        return {'job': job, 'api': api, 'elapsed_s': elapsed()}

    def start_pool(name):
        """Start (or restart) the pool with the exact same command and wait until it serves a job on the current tip."""
        start(name, pool_command())
        require(commands[name] == commands['pool'], 'restart must reuse the exact pool command')
        tip = state(1)
        found = {}
        wait(lambda: found.update(job_at(tip)) or True, f'{name} did not serve a job on the common tip', seconds=240)
        return tip, found

    def interrupted(signum, frame):
        raise RuntimeError(f'interrupted by signal {signum}')

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        require(sorted(p.name for p in Path('/sys/class/net').iterdir()) == ['lo'],
                'inside mode requires an isolated network namespace with only loopback')
        launch.validate_profile(json.loads((WORK / 'profile.json').read_text()))
        require(digest(Path('/binary/monerod')) == launch.BINARY_SHA, 'mounted binary SHA-256 mismatch')
        require(digest(Path('/pool/p2pool')) == POOL_SHA, 'mounted pool SHA-256 mismatch')
        (WORK / 'data').mkdir(mode=0o700)  # Exclusive creation: never adopt stale node or pool state.
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
        save(WORK / 'mining-command.json', {'node': 0, 'endpoint': '/start_mining', 'miner_address': launch.ADDRESS,
                                            'params': {'threads_count': 1, 'do_background_mining': False, 'ignore_battery': True}})
        event('two_peer_profile_verified', pool='F4 candidate on peer1', daemon_rpc='127.0.0.1:28181', zmq_pub=f'tcp://127.0.0.1:{ZMQ_PUB_PORT}')

        # Seam 1: a short chain exists before the pool attaches; the pool's first job must build on that common tip.
        initial_tip = mine(PHASES['initial_blocks'], 'before_pool')
        (WORK / 'data' / 'pool').mkdir()
        (WORK / 'data' / 'pool-api').mkdir()
        pool_started_at = elapsed()
        tip_attach, attach = start_pool('pool')
        require(tip_attach == initial_tip, 'chain moved before the pool attached')
        witness = {'tip_at_attach': tip_attach, 'pool_started_elapsed_s': pool_started_at, 'attach': attach,
                   'attach_seconds_from_start': attach['elapsed_s'] - pool_started_at}
        event('pool_attached_at_common_tip', tip=tip_attach, job_height=attach['job']['height'], seconds=witness['attach_seconds_from_start'])

        # Seam 2: the running pool follows new blocks that reach peer 1 only through P2P from peer 0.
        live_tip = mine(PHASES['live_blocks'], 'pool_live')
        found = {}
        wait(lambda: found.update(job_at(live_tip)) or True, 'live pool did not follow the new tip', seconds=120)
        witness.update(tip_after_live=live_tip, live=found, live_blocks=live_tip['height'] - tip_attach['height'])
        sample('pool', WORK / 'data' / 'pool', 'before_stop')
        event('pool_followed_live_blocks', tip=live_tip, job_height=found['job']['height'])

        # Seam 3: stop the pool cleanly, mine on without it, restart it with the identical command; it must resume on the new tip.
        tip_stop = state(1)
        code = stop('pool')
        require(code == 0, f'pool clean shutdown exit {code}')
        stopped_at = elapsed()
        event('pool_stopped', exit_code=code, tip=tip_stop)
        down_tip = mine(PHASES['down_blocks'], 'pool_down')
        restarted_at = elapsed()
        tip_restart, resumed = start_pool('pool-restart')
        require(tip_restart == down_tip, 'chain moved between the down phase and the restart readback')
        connections(1)
        witness.update(tip_at_stop=tip_stop, pool_exit_code=code, stopped_elapsed_s=stopped_at, tip_mined_while_down=down_tip,
                       blocks_missed=down_tip['height'] - tip_stop['height'], restarted_elapsed_s=restarted_at, resumed=resumed,
                       resume_seconds_from_restart=resumed['elapsed_s'] - restarted_at, state_after_restart=state(1),
                       connections=rpc(1, 'get_connections'))
        save(WORK / 'pool-restart.json', witness)
        event('pool_restarted_resumed_at_common_tip', tip=down_tip, job_height=resumed['job']['height'],
              blocks_missed=witness['blocks_missed'], resume_seconds=witness['resume_seconds_from_restart'])

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
        for n in (0, 1):
            sample(f'peer{n}', WORK / 'data' / f'peer{n}', 'final')
        sample('pool-restart', WORK / 'data' / 'pool', 'final')
        final_api = pool_api()
        require(final_api['network']['hash'] == wanted['hash'] and final_api['pool']['pool_statistics']['totalBlocksFound'] == 0,
                'final pool view disagrees with the daemons')
        witness['final_api'] = final_api
        save(WORK / 'pool-restart.json', witness)
        result.update(result='PASS', peers=states, phases=PHASES, tip_at_stop=tip_stop, blocks_missed_while_down=witness['blocks_missed'],
                      resume_seconds_from_restart=witness['resume_seconds_from_restart'], pool_sha256=POOL_SHA,
                      delivery='native mining on peer0 only; peer1 and the pool receive through TCP P2P and peer1 RPC/ZMQ only; '
                               'no stratum miner, no pool share, no block submitted by the pool')
        event('converged', peers=states)
    except Exception as error:
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
        if sorted(exits) != ['peer0', 'peer1', 'pool', 'pool-restart'] or any(exits.values()):
            result.update(result='FAIL', shutdown_error=exits)
        save(WORK / 'result.json', result)
    return 0 if result['result'] == 'PASS' else 1


def admission(binary, pool, profile):
    manifest = launch.preflight(binary, profile)
    require(digest(pool) == POOL_SHA, f'pool binary SHA-256 mismatch: expected {POOL_SHA}')
    require(digest(RECIPE_MANIFEST) == RECIPE_MANIFEST_SHA, 'accepted recipe manifest mismatch')
    inputs = {}
    for line in RECIPE_MANIFEST.read_text().splitlines():
        expected, name = line.split('  ', 1)
        require(digest(ROOT / name) == expected, f'accepted recipe input differs: {name}')
        inputs[name] = expected
    for name, expected in POOL_INPUTS.items():
        require(digest(ROOT / name) == expected, f'pinned pool source input differs: {name}')
        inputs[name] = expected
    for path in [RECIPE_MANIFEST, *(HERE / name for name in NEW_FILES)]:
        inputs[str(path.relative_to(ROOT))] = digest(path)
    return manifest, inputs


def outside(args):
    binary, pool, profile, work = args.binary.resolve(), args.pool.resolve(), args.profile.resolve(), args.work.absolute()
    require(not work.exists() and not work.is_symlink(), f'stale data/output directory refused: {work}; choose a new path')
    manifest, inputs = admission(binary, pool, profile)
    if args.check_only:
        print('PASS: accepted recipe manifest, profile, binary, pool and baseline inputs verified; no process started')
        return 0
    work.mkdir(parents=True, mode=0o700)
    save(work / 'launcher-command.json', [sys.executable, *sys.argv])
    save(work / 'baseline.json', manifest)
    shutil.copyfile(profile, work / 'profile.json')
    (work / 'INPUTS.sha256').write_text(''.join(f'{v}  {k}\n' for k, v in sorted(inputs.items())))
    (work / 'BINARY.sha256').write_text(f'{digest(binary)}  {binary}\n{digest(pool)}  {pool}\n')
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
            name = f'meow-tjs297-{os.getpid()}'
            command = ['docker', 'run', '--rm', '--pull=never', '--name', name, '--network', 'none',
                       '--memory=4g', '--memory-swap=4g', '--cpus=2', '--pids-limit=256',
                       '--user', f'{os.getuid()}:{os.getgid()}', '--cap-drop=ALL', '--security-opt=no-new-privileges',
                       '--read-only', '--tmpfs', '/tmp:rw,nosuid,nodev,size=64m',
                       '-e', 'PYTHONDONTWRITEBYTECODE=1', '-e', 'HOME=/tmp',
                       '-v', f'{binary}:/binary/monerod:ro', '-v', f'{pool}:/pool/p2pool:ro',
                       '-v', f'{HERE}:/recipe:ro', '-v', f'{work}:/work', launch.IMAGE,
                       'timeout', '--signal=TERM', '--kill-after=75', str(RUN_LIMIT_SECONDS),
                       'python3', '-B', '-u', '/recipe/pool-restart.py', '--inside']
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
    parser.add_argument('--pool', type=Path, default=ROOT / 'build/tjs187-port-20260920/source/build-local/p2pool')
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
