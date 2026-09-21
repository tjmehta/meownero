#!/usr/bin/env python3
"""TJS-230: solo-funded native-network payment, seed recovery and reopen journey."""
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
import urllib.request

import launch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
WALLET_SHA = '5782abee489e8b245b42fd237ece34d6df1c67929c552960755fab41de3a921a'
RECIPE_MANIFEST = ROOT / 'research/evidence/testnet-v0-launch-tjs229-2026-09-20/launch/INPUTS.sha256'
RECIPE_MANIFEST_SHA = '1e3b8a784828b05634abd4b4ac22ba7cc83652b32af023c71c146f3216a5e59f'
COIN = 10**12
WORK = Path('/work')
save, require, digest, drpc = launch.save, launch.require, launch.digest, launch.rpc
# Run-03 execution budget (TJS-230). Method unchanged: native RandomX/DAA, one mining thread,
# 100 funding blocks. Run-02 showed the DAA holding ~86 s/block against the 90 s target by
# height 10, so the 1,500 s funding wait was the failing bound, not the thread count.
TARGET_SECONDS = 90
RUN_LIMIT_SECONDS = 24000


def phase_limit(count):
    """Twice the DAA-expected phase time plus fixed slack; a timeout is still an incomplete journey."""
    return 120 + 2*count*TARGET_SECONDS


def wrpc(port, method, params=None):
    request = urllib.request.Request(f'http://127.0.0.1:{port}/json_rpc',
        json.dumps({'jsonrpc': '2.0', 'id': '0', 'method': method, 'params': params or {}}).encode(),
        {'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=120) as response:
        result = json.load(response)
    # Wallet errors and request/response bodies can contain keys. Never log them.
    require('error' not in result, f'wallet RPC failed: {method}')
    return result['result']


def inside():
    procs, commands, cases = {}, {}, []
    started = time.monotonic()
    result = {'result': 'FAIL', 'funding': 'solo', 'cases': cases}

    def event(name, **fields):
        row = {'case': name, **fields}
        cases.append(row)
        save(WORK / 'progress.json', cases)
        print(json.dumps(row), flush=True)

    def wait(check, label, seconds=120):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            require(all(p.poll() is None for p in procs.values()), 'owned process exited early')
            try:
                if check():
                    return
            except (OSError, ValueError, KeyError):
                pass
            time.sleep(0.25)
        raise TimeoutError(label)

    def start(name, command, private=False):
        commands[name] = command
        save(WORK / 'process-commands.json', commands)
        logdir = WORK / 'data' if private else WORK
        with (logdir / f'{name}.stdout.log').open('w') as log:
            procs[name] = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)

    def balance(port):
        wrpc(port, 'refresh')
        b = wrpc(port, 'get_balance')
        return {'balance': b['balance'], 'unlocked_balance': b['unlocked_balance']}

    def incoming(port):
        wrpc(port, 'refresh')
        return sorted([t['txid'], t['amount']] for t in wrpc(port, 'get_transfers', {'in': True}).get('in', []))

    def snapshot(port):
        return {'balance': balance(port), 'incoming': incoming(port),
                'outgoing': sorted([t['txid'], t['amount'], t['fee']] for t in
                    wrpc(port, 'get_transfers', {'out': True}).get('out', []))}

    def tip(n):
        h = drpc(n, 'get_last_block_header')['block_header']
        return [h['height'], h['hash'], h['wide_cumulative_difficulty']]

    def converge():
        wait(lambda: tip(0) == tip(1), 'P2P tip convergence')
        return tip(0)

    def pool(n):
        return sorted(t['id_hash'] for t in drpc(n, 'get_transaction_pool', endpoint=True).get('transactions', []))

    def mine(count, address, label):
        before = drpc(0, 'get_info')['height']
        # Only the address is omitted from the public command receipt.
        params = {'miner_address': address, 'threads_count': 1,
                  'do_background_mining': False, 'ignore_battery': True}
        event('mining_started', phase=label, start_rpc_height=before,
              minimum_blocks=count, method='start_mining', node=0, threads=1, limit_seconds=phase_limit(count))
        drpc(0, 'start_mining', params, endpoint=True)
        try:
            wait(lambda: drpc(0, 'get_info')['height'] >= before + count,
                 f'native mining: {label}', seconds=phase_limit(count))
        finally:
            drpc(0, 'stop_mining', endpoint=True)
        t = converge()
        event('mining_stopped', phase=label, tip=t)
        return t

    def transfer(port, origin, destination, amount, label):
        sent = wrpc(port, 'transfer', {'destinations': [{'address': destination, 'amount': amount}]})
        txid, fee = sent['tx_hash'], sent['fee']
        require(sent['amount'] == amount and fee > 0, 'transfer amount/fee mismatch')
        require(txid in pool(origin), 'transaction absent from origin mempool')
        wait(lambda: txid in pool(1-origin), 'P2P transaction relay')
        decoded = []
        for n in (0, 1):
            tx = drpc(n, 'get_transactions', {'txs_hashes': [txid], 'decode_as_json': True}, endpoint=True)['txs'][0]
            j = json.loads(tx['as_json'])
            rings = [len(v['key']['key_offsets']) for v in j['vin']]
            require(j['version'] == 2 and j['rct_signatures']['type'] == 6 and
                    rings and all(r == 16 for r in rings), 'expected type-6/ring-16 transaction')
            require(j['rct_signatures']['txnFee'] == fee, 'decoded transaction fee mismatch')
            decoded.append({'node': n, 'in_pool': tx['in_pool'], 'version': j['version'],
                            'rct_type': j['rct_signatures']['type'], 'ring_sizes': rings, 'fee': fee})
            require(tx['in_pool'], 'peer transaction not pooled')
        event(label + '_relay', txid=txid, amount=amount, fee=fee, origin=origin,
              pools=[pool(n) for n in (0, 1)], decoded=decoded)
        return txid, fee

    def confirmed(txid):
        rows = []
        for n in (0, 1):
            tx = drpc(n, 'get_transactions', {'txs_hashes': [txid]}, endpoint=True)['txs'][0]
            require(not tx['in_pool'] and txid not in pool(n), 'transaction still unconfirmed')
            h = drpc(n, 'get_block_header_by_height', {'height': tx['block_height']})['block_header']
            rows.append({'node': n, 'txid': txid, 'height': tx['block_height'], 'block_hash': h['hash']})
        require(rows[0]['height'] == rows[1]['height'] and rows[0]['block_hash'] == rows[1]['block_hash'],
                'confirmation differs across peers')
        return rows

    def interrupted(signum, frame):
        raise RuntimeError('owned run interrupted')

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        require(sorted(p.name for p in Path('/sys/class/net').iterdir()) == ['lo'], 'only loopback allowed')
        require(digest(Path('/binary/monerod')) == launch.BINARY_SHA, 'daemon pin mismatch')
        require(digest(Path('/binary/monero-wallet-rpc')) == WALLET_SHA, 'wallet pin mismatch')
        launch.validate_profile(json.loads((WORK / 'profile.json').read_text()))
        (WORK / 'data').mkdir(mode=0o700)
        for n in (0, 1):
            data = WORK / 'data' / f'peer{n}'
            data.mkdir()
            config = WORK / f'peer{n}.conf'
            config.write_text('')
            # Same daemon command as recipe v1, with fresh owned directories.
            start(f'peer{n}', ['/binary/monerod', '--config-file', str(config), '--data-dir', str(data),
                '--non-interactive', '--no-igd', '--disable-dns-checkpoints', '--check-updates', 'disabled',
                '--max-concurrency', '1', '--allow-local-ip', '--hide-my-port',
                '--add-exclusive-node', f'127.0.0.1:{28080+(1-n)*100}',
                '--p2p-bind-ip', '127.0.0.1', '--p2p-bind-port', str(28080+n*100),
                '--rpc-bind-ip', '127.0.0.1', '--rpc-bind-port', str(28081+n*100),
                '--rpc-ssl', 'disabled', '--no-zmq', '--log-level', '1',
                '--log-file', str(WORK / f'peer{n}.log')])
        wait(lambda: all(drpc(n, 'get_info')['synchronized'] for n in (0, 1)), 'daemon startup')
        profiles = []
        for n in (0, 1):
            info = drpc(n, 'get_info')
            genesis = drpc(n, 'get_block_header_by_height', {'height': 0})['block_header']
            fork = drpc(n, 'hard_fork_info', {'version': 16})
            template = drpc(n, 'get_block_template', {'wallet_address': launch.ADDRESS})
            require(info['height'] == 1 and info['nettype'] == 'mainnet' and info['target'] == 90,
                    'fresh native selected profile required')
            require(genesis['hash'] == launch.EXPECTED['genesis_hash'] and genesis['reward'] == 0
                    and genesis['major_version'] == 1, 'genesis mismatch')
            require(fork['version'] == 16 and fork['earliest_height'] == 1 and template['height'] == 1
                    and template['expected_reward'] == 9*COIN and bytes.fromhex(template['blocktemplate_blob'])[0] == 16,
                    'fork/reward mismatch')
            profiles.append({'info': info, 'genesis': genesis, 'fork': fork, 'template': template})
        save(WORK / 'profile-readback.json', profiles)
        wait(lambda: all(drpc(n, 'get_connections').get('connections') for n in (0, 1)), 'P2P handshake')
        save(WORK / 'peers-before.json', [drpc(n, 'get_connections') for n in (0, 1)])
        event('profile_and_p2p_verified', funding='solo', network='isolated-mainnet', native_daa=True)

        addresses = {}
        for name, port, node in [('A', 28090, 0), ('S', 28091, 0), ('B', 28190, 1), ('D', 28191, 1)]:
            directory = WORK / 'data' / name
            directory.mkdir(mode=0o700)
            config = directory / 'wallet.conf'
            config.write_text('')
            start(name, ['/binary/monero-wallet-rpc', '--config-file', str(config),
                '--rpc-bind-ip', '127.0.0.1', '--rpc-bind-port', str(port), '--disable-rpc-login',
                '--wallet-dir', str(directory), '--daemon-address', f'http://127.0.0.1:{28081+node*100}',
                '--trusted-daemon', '--allow-mismatched-daemon-version', '--max-concurrency', '1',
                '--log-level', '0', '--log-file', str(directory / 'wallet.log')], private=True)
            wait(lambda: wrpc(port, 'get_version')['version'] > 0, 'wallet startup')
            if name != 'D':
                wrpc(port, 'create_wallet', {'filename': name, 'password': '', 'language': 'English'})
                addresses[name] = wrpc(port, 'get_address')['address']
                require(addresses[name].startswith('M'), 'selected address prefix mismatch')
        seed = wrpc(28190, 'query_key', {'key_type': 'mnemonic'})['key']
        require(len(seed.split()) == 25, 'unexpected mnemonic length')
        funded_tip = mine(100, addresses['A'], 'fund_solo_A')
        a0 = balance(28090)
        require(a0['balance'] == funded_tip[0]*9*COIN and a0['unlocked_balance'] > 0, 'solo funding mismatch')
        event('solo_funded', tip=funded_tip, sender=a0)

        tx1, fee1 = transfer(28090, 0, addresses['B'], 5*COIN, 'payment')
        mine(12, addresses['S'], 'confirm_payment')
        a1, b1 = balance(28090), balance(28190)
        require(a1['balance'] == a0['balance']-5*COIN-fee1, 'sender debit mismatch')
        require(b1['balance'] == 5*COIN and [tx1, 5*COIN] in incoming(28190), 'recipient credit mismatch')
        event('payment_confirmed', txid=tx1, sender_before=a0, sender_after=a1,
              recipient=b1, incoming=incoming(28190), confirmations=confirmed(tx1))

        restored = wrpc(28191, 'restore_deterministic_wallet', {'seed': seed, 'restore_height': 0,
                    'filename': 'D', 'password': '', 'autosave_current': True})
        del seed
        require(restored['address'] == addresses['B'], 'restored address mismatch')
        original, recovered = snapshot(28190), snapshot(28191)
        require(original == recovered, 'restored balance/history mismatch')
        event('seed_restored', node=1, address_matches=True, original=original, restored=recovered)

        tx2, fee2 = transfer(28191, 1, addresses['A'], 2*COIN, 'recovered_spend')
        mine(12, addresses['S'], 'confirm_recovered_spend')
        a2, d2 = balance(28090), balance(28191)
        require(a2['balance'] == a1['balance']+2*COIN and [tx2, 2*COIN] in incoming(28090), 'return credit mismatch')
        require(d2['balance'] == recovered['balance']['balance']-2*COIN-fee2, 'restored spend debit mismatch')
        event('recovered_spend_confirmed', txid=tx2, sender=d2, recipient=a2, confirmations=confirmed(tx2))
        before = snapshot(28191)
        wrpc(28191, 'store')
        wrpc(28191, 'close_wallet')
        wrpc(28191, 'open_wallet', {'filename': 'D', 'password': ''})
        require(wrpc(28191, 'get_address')['address'] == addresses['B'], 'reopened address mismatch')
        after = snapshot(28191)
        require(before == after and [tx2, 2*COIN, fee2] in after['outgoing'], 'reopen state mismatch')
        event('wallet_reopened', address_matches=True, before=before, after=after)

        t = converge()
        headers = [[drpc(n, 'get_block_header_by_height', {'height': h})['block_header']
                    for h in range(t[0]+1)] for n in (0, 1)]
        final = [{'info': drpc(n, 'get_info'), 'sum': drpc(n, 'get_coinbase_tx_sum',
                 {'height': 0, 'count': t[0]+1})} for n in (0, 1)]
        for n in (0, 1):
            sums = final[n]['sum']
            require(sums['emission_amount'] == t[0]*9*COIN and sums['fee_amount'] == fee1+fee2, 'aggregate mismatch')
            require(sum(h['difficulty'] for h in headers[n]) == int(t[2], 16), 'native cumulative work mismatch')
            require(sum(h['reward'] for h in headers[n]) == sums['emission_amount']+sums['fee_amount'], 'header reward sum mismatch')
            require(all(h['major_version'] == 16 for h in headers[n][1:]), 'mined fork mismatch')
        save(WORK / 'headers.json', headers)
        save(WORK / 'rpc-final.json', final)
        save(WORK / 'peers-after.json', [drpc(n, 'get_connections') for n in (0, 1)])
        result.update(result='PASS', tip=t, fee_total=fee1+fee2, emission=t[0]*9*COIN,
                      txids=[tx1, tx2], scope='solo-funded native RandomX/DAA; recipe v1 two peers; disposable wallet RPC')
    except Exception as error:
        # Do not stringify arbitrary wallet/transport exceptions into public receipts.
        result.update(result='FAIL', error_type=type(error).__name__, last_case=cases[-1]['case'] if cases else None)
        print(json.dumps({'result': 'FAIL', 'error_type': type(error).__name__, 'last_case': result['last_case']}), flush=True)
    finally:
        for p in procs.values():
            if p.poll() is None:
                p.terminate()
        exits = {}
        for name, p in procs.items():
            try:
                p.wait(timeout=20)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()
            exits[name] = p.returncode
        resources = {p.name: p.read_text() for p in (Path('/sys/fs/cgroup') / name for name in
                     ('memory.peak', 'memory.events', 'memory.max', 'memory.swap.max', 'cpu.max')) if p.exists()}
        resources.update(exit_codes=exits, elapsed_seconds=time.monotonic()-started)
        save(WORK / 'resources.json', resources)
        if len(exits) != 6 or any(exits.values()):
            result.update(result='FAIL', shutdown_error=exits)
        save(WORK / 'result.json', result)
    return 0 if result['result'] == 'PASS' else 1


def outside(args):
    binary, wallet, work = args.binary.resolve(), args.wallet.resolve(), args.work.absolute()
    require(not work.exists() and not work.is_symlink(), 'work directory must be fresh')
    baseline = launch.preflight(binary, HERE / 'profile.json')
    require(digest(wallet) == WALLET_SHA, 'wallet pin mismatch')
    require(digest(RECIPE_MANIFEST) == RECIPE_MANIFEST_SHA, 'accepted recipe manifest mismatch')
    inputs = {}
    for line in RECIPE_MANIFEST.read_text().splitlines():
        expected, name = line.split('  ', 1)
        require(digest(ROOT / name) == expected, f'accepted recipe input differs: {name}')
        inputs[name] = expected
    for path in [RECIPE_MANIFEST, Path(__file__).resolve(), HERE / 'verify-payment.py',
                 HERE / 'payment-journey.md', ROOT / 'chain/test-network-payment.py']:
        inputs[str(path.relative_to(ROOT))] = digest(path)
    if args.check_only:
        print('PASS_ADMISSION: accepted recipe manifest, daemon, wallet and profile pinned')
        return 0
    work.mkdir(parents=True, mode=0o700)
    save(work / 'launcher-command.json', [sys.executable, *sys.argv])
    save(work / 'baseline.json', baseline)
    shutil.copyfile(HERE / 'profile.json', work / 'profile.json')
    (work / 'INPUTS.sha256').write_text(''.join(f'{v}  {k}\n' for k, v in sorted(inputs.items())))
    (work / 'BINARY.sha256').write_text(f'{digest(binary)}  {binary}\n{digest(wallet)}  {wallet}\n')
    try:
        with open('/tmp/meownero-swarm-20260912-heavy.lock', 'a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                save(work / 'result.json', {'result': 'BLOCKED', 'reason': 'shared heavy lock busy', 'funding': 'solo'})
                return 75
            available = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                                 if line.startswith('MemAvailable:')))*1024
            free = shutil.disk_usage(work).free
            save(work / 'preflight-resources.json', {'available_ram_bytes': available, 'free_disk_bytes': free})
            require(min(available, free) >= 5*1024**3, 'need 5 GiB available RAM and disk')
            name = f'meow-tjs230-{os.getpid()}'
            command = ['docker', 'run', '--rm', '--pull=never', '--name', name, '--network', 'none',
                '--memory=4g', '--memory-swap=4g', '--cpus=2', '--pids-limit=256',
                '--user', f'{os.getuid()}:{os.getgid()}', '--cap-drop=ALL', '--security-opt=no-new-privileges',
                '--read-only', '--tmpfs', '/tmp:rw,nosuid,nodev,size=64m', '-e', 'PYTHONDONTWRITEBYTECODE=1',
                '-v', f'{binary}:/binary/monerod:ro', '-v', f'{wallet}:/binary/monero-wallet-rpc:ro',
                '-v', f'{HERE}:/recipe:ro', '-v', f'{work}:/work', launch.IMAGE,
                'timeout', '--signal=TERM', '--kill-after=150', str(RUN_LIMIT_SECONDS), 'python3', '-B', '-u', '/recipe/payment.py', '--inside']
            save(work / 'container-command.json', command)
            try:
                with (work / 'run.log').open('w') as log:
                    process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
                    code = process.wait()
                (work / 'container.exit').write_text(str(code)+'\n')
                return code
            finally:
                cleanup = subprocess.run(['docker', 'rm', '-f', name], capture_output=True, text=True)
                save(work / 'cleanup.json', {'exit': cleanup.returncode, 'stdout': cleanup.stdout, 'stderr': cleanup.stderr})
    finally:
        public = sorted(p for p in work.iterdir() if p.is_file() and p.name != 'EVIDENCE.sha256')
        (work / 'EVIDENCE.sha256').write_text(''.join(f'{digest(p)}  {p.name}\n' for p in public))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    bindir = ROOT / 'build/repro-selected-20260918/selected-9-90/first/source/build/release/bin'
    parser.add_argument('--binary', type=Path, default=bindir / 'monerod')
    parser.add_argument('--wallet', type=Path, default=bindir / 'monero-wallet-rpc')
    parser.add_argument('--work', type=Path)
    parser.add_argument('--check-only', action='store_true')
    parser.add_argument('--inside', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.inside:
        return inside()
    if args.work is None:
        parser.error('--work requires a fresh path')
    try:
        return outside(args)
    except (OSError, ValueError, KeyError) as error:
        print(f'REFUSED: {error}', file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == '__main__':
    sys.exit(main())
