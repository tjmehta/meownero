"""Matched loaded 90s-versus-120s P2P probe: transactions, blocks, stale and reorg under load.

Two existing daemons of ONE profile talk through the interruptible TCP proxies
of test-network-p2p.py. A disposable wallet-rpc on node 0 creates real RingCT
transactions at a fixed wall-clock cadence (the offered load), and node 0
generates one block per emulated slot (target_seconds / --accel). Matching
across profiles is by identical --duration, --tx-interval, --outputs, --link,
--accel, --seed, container caps and topology; only target_seconds and reward
differ. Block capacity is NOT normalized: both profiles keep the pinned 300,000
byte penalty-free zone, so 90 s admits 4/3 the bytes per second of 120 s.

Fixed difficulty 1 and generateblocks: no PoW race, native DAA not exercised.
No FCMP integration exists in the pinned source; --outputs only scales
transaction bytes as a size sensitivity, never a proof-cost model. Accelerated
(--accel > 1) results are not target-rate measurements; --accel 1 is.
"""
import argparse
import asyncio
import json
import math
import random
import runpy
import statistics
import subprocess
import time
import urllib.request
from pathlib import Path

WORK = Path('/work')
BIN = Path('/src/build/release/bin')
PROCESSES = {}
EVENTS = []
LINKS = {
    # (per-chunk delay seconds, bytes per second per stream)
    'nominal': (0.020, 65536),
    'slow': (0.150, 16384),
}


def event(label, **fields):
    entry = dict(event=label, monotonic_s=time.monotonic(), **fields)
    EVENTS.append(entry)
    print(json.dumps(entry, default=str), flush=True)


def http(port, path, body, timeout=60):
    req = urllib.request.Request(f'http://127.0.0.1:{port}/{path}', json.dumps(body).encode(),
                                 {'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def request(port, method, params, timeout=60):
    result = http(port, 'json_rpc', dict(jsonrpc='2.0', id='0', method=method, params=params or {}), timeout)
    assert 'error' not in result, (method, result)
    return result['result']


def daemon_port(node):
    return 19081 + node * 100


async def rpc(node, method, params=None):
    return await asyncio.to_thread(request, daemon_port(node), method, params, 30)


async def other(node, path, body=None):
    return await asyncio.to_thread(http, daemon_port(node), path, body or {}, 30)


async def wallet(method, params=None):
    return await asyncio.to_thread(request, 19100, method, params, 120)


async def tip(node):
    h = (await rpc(node, 'get_last_block_header'))['block_header']
    return h['height'], h['hash'], h['wide_cumulative_difficulty']


def alive():
    assert all(p.poll() is None for p in PROCESSES.values()), 'a daemon or wallet process exited'


async def wait_tip(node, wanted, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if await tip(node) == wanted:
            return time.monotonic()
        alive()
        await asyncio.sleep(0.025)
    raise AssertionError(f'node {node} convergence timeout: {await tip(node)} != {wanted}')


class Link:
    def __init__(self, delay, rate):
        self.delay, self.rate = delay, rate
        self.enabled = True
        self.writers = set()
        self.bytes = 0
        self.connections = 0

    def partition(self):
        self.enabled = False
        for writer in list(self.writers):
            writer.close()

    async def accept(self, reader, writer, destination):
        if not self.enabled:
            writer.close()
            await writer.wait_closed()
            return
        self.writers.add(writer)
        peer = None
        try:
            upstream, peer = await asyncio.open_connection('127.0.0.1', destination)
            self.writers.add(peer)
            self.connections += 1

            async def pump(source, target):
                while self.enabled:
                    data = await source.read(16384)
                    if not data:
                        break
                    await asyncio.sleep(self.delay + len(data) / self.rate)
                    if not self.enabled:
                        break
                    target.write(data)
                    await target.drain()
                    self.bytes += len(data)

            tasks = [asyncio.create_task(pump(reader, peer)), asyncio.create_task(pump(upstream, writer))]
            try:
                await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
        except (OSError, ConnectionError):
            pass
        finally:
            for stream in [writer, peer]:
                if stream:
                    self.writers.discard(stream)
                    stream.close()
                    try:
                        await stream.wait_closed()
                    except OSError:
                        pass


async def start_daemon(node):
    with (WORK / f'n{node}.stdout.log').open('a') as log:
        PROCESSES[f'n{node}'] = subprocess.Popen([
            str(BIN / 'monerod'), '--data-dir', str(WORK / f'n{node}'),
            '--regtest', '--keep-fakechain', '--fixed-difficulty', '1',
            '--non-interactive', '--no-igd', '--disable-dns-checkpoints', '--check-updates', 'disabled',
            '--allow-local-ip', '--add-exclusive-node', f'127.0.0.1:{20080 + node * 100}',
            '--p2p-bind-ip', '127.0.0.1', '--p2p-bind-port', str(19080 + node * 100),
            '--rpc-bind-ip', '127.0.0.1', '--rpc-bind-port', str(daemon_port(node)),
            '--zmq-rpc-bind-ip', '127.0.0.1', '--zmq-rpc-bind-port', str(19082 + node * 100),
            '--log-file', str(WORK / f'n{node}.log')], stdout=log, stderr=subprocess.STDOUT)
    for _ in range(120):
        assert PROCESSES[f'n{node}'].poll() is None, 'daemon exited at startup'
        try:
            await rpc(node, 'get_info')
            return
        except OSError:
            await asyncio.sleep(0.25)
    raise AssertionError('daemon startup timeout')


async def start_wallet():
    (WORK / 'wallet').mkdir()
    with (WORK / 'wallet.stdout.log').open('a') as log:
        PROCESSES['wallet'] = subprocess.Popen([
            str(BIN / 'monero-wallet-rpc'), '--rpc-bind-ip', '127.0.0.1', '--rpc-bind-port', '19100',
            '--disable-rpc-login', '--wallet-dir', str(WORK / 'wallet'),
            '--daemon-address', 'http://127.0.0.1:19081', '--trusted-daemon',
            '--log-file', str(WORK / 'wallet.log')], stdout=log, stderr=subprocess.STDOUT)
    for _ in range(240):
        assert PROCESSES['wallet'].poll() is None, 'wallet-rpc exited at startup'
        try:
            await wallet('get_version')
            return
        except OSError:
            await asyncio.sleep(0.25)
    raise AssertionError('wallet-rpc startup timeout')


async def wait_core_ready():
    deadline = time.monotonic() + 30
    initial = {}
    while time.monotonic() < deadline:
        infos = [await rpc(n, 'get_info') for n in (0, 1)]
        if not initial:
            initial = {str(n): infos[n] for n in (0, 1)}
            event('initial_core_readiness', get_info=initial)
        if all(info.get('synchronized') for info in infos):
            event('core_ready')
            return
        await asyncio.sleep(0.1)
    raise AssertionError(f'core readiness timeout: {json.dumps(initial, sort_keys=True)}')


async def generate(node, count, address):
    result = await rpc(node, 'generateblocks', dict(wallet_address=address, amount_of_blocks=count))
    if 'blocks' not in result:
        raise AssertionError(f'generateblocks returned no blocks: {json.dumps(result, sort_keys=True)}')
    return result['blocks']


async def header(node, block_hash):
    h = (await rpc(node, 'get_block_header_by_hash', {'hash': block_hash}))['block_header']
    return {k: h[k] for k in ('height', 'hash', 'num_txes', 'block_weight', 'block_size', 'timestamp',
                              'orphan_status', 'prev_hash')}


async def main(args):
    rng = random.Random(args.seed)
    target, reward = args.target_seconds, args.reward_atomic
    interval = target / args.accel
    delay, rate = LINKS[args.link]
    link = Link(delay, rate)
    servers = [await asyncio.start_server(lambda r, w: link.accept(r, w, 19180), '127.0.0.1', 20080),
               await asyncio.start_server(lambda r, w: link.accept(r, w, 19080), '127.0.0.1', 20180)]
    txs = {}          # tx_hash -> record
    blocks = []       # per-slot records
    competing = []    # induced competing-block records
    wallet_errors = []
    seen_n1 = {}      # tx_hash -> monotonic first seen in node 1 pool
    result = dict(result='FAIL', profile=args.profile, target_seconds=target, reward_atomic=reward,
                  seed=args.seed, link=args.link, link_delay_s=delay, link_bytes_per_s=rate,
                  accel=args.accel, emulated_interval_s=interval, duration_s=args.duration,
                  tx_interval_s=args.tx_interval, outputs_per_tx=args.outputs,
                  competing_every=args.competing_every, target_rate=args.accel == 1,
                  capacity_normalization_enforced=False, fcmp_integration='unavailable in pinned source',
                  difficulty='fixed 1; native DAA not exercised', events=EVENTS)
    try:
        await start_daemon(0)
        await start_daemon(1)
        await wait_core_ready()
        await start_wallet()
        await wallet('create_wallet', dict(filename='miner', password='disposable', language='English'))
        miner = (await wallet('get_address'))['address']
        assert miner.startswith('M'), miner
        destinations = [(await wallet('create_address', dict(account_index=0)))['address']
                        for _ in range(max(1, args.outputs - 1))]
        event('wallet_ready', miner=miner, destinations=len(destinations))

        # Funding: enough matured coinbase outputs that steady-state transfers never
        # wait on the 10-block spendable age of change outputs.
        planned_txs = math.ceil(args.duration / args.tx_interval) + args.partition_txs
        fund_blocks = 60 + 2 * planned_txs + 20
        begin = time.monotonic()
        while (await tip(0))[0] < fund_blocks:
            await generate(0, min(50, fund_blocks - (await tip(0))[0] + 1), miner)
        funded_tip = await tip(0)
        sync_done = await wait_tip(1, funded_tip, timeout=600)
        event('funded', height=funded_tip[0], generate_and_sync_s=sync_done - begin, proxy_bytes=link.bytes)
        deadline = time.monotonic() + 600
        while True:
            await wallet('refresh')
            balance = await wallet('get_balance')
            if balance['unlocked_balance'] >= (funded_tip[0] - 60) * reward:
                break
            assert time.monotonic() < deadline, balance
            await asyncio.sleep(1)
        event('wallet_funded', balance=balance['balance'], unlocked=balance['unlocked_balance'])

        async def submit_tx(index, phase):
            amount = rng.randint(1, 9) * 100_000_000  # 0.0001-0.0009 MEOW per output
            dests = [dict(address=d, amount=amount) for d in destinations]
            record = dict(index=index, phase=phase, submit_monotonic=time.monotonic())
            try:
                r = await wallet('transfer', dict(destinations=dests, account_index=0, get_tx_key=False))
                record.update(tx_hash=r['tx_hash'], fee=r['fee'], weight=r.get('weight'),
                              amount=r['amount'], created_monotonic=time.monotonic())
                txs[r['tx_hash']] = record
            except Exception as error:  # noqa: BLE001 - recorded as workload evidence, never hidden
                record.update(error=str(error)[:400], failed_monotonic=time.monotonic())
                wallet_errors.append(record)
            return record

        stop_watch = asyncio.Event()

        async def watch_pool():
            while not stop_watch.is_set():
                try:
                    hashes = (await other(1, 'get_transaction_pool_hashes')).get('tx_hashes') or []
                except OSError:
                    hashes = []
                now = time.monotonic()
                for h in hashes:
                    seen_n1.setdefault(h, now)
                await asyncio.sleep(0.05)

        watcher = asyncio.create_task(watch_pool())
        t0 = time.monotonic()
        slots = int(args.duration // interval)
        tx_count = math.ceil(args.duration / args.tx_interval)

        async def generator():
            for j in range(tx_count):
                at = t0 + j * args.tx_interval + rng.uniform(0, 0.2)
                await asyncio.sleep(max(0, at - time.monotonic()))
                await submit_tx(j, 'steady')

        gen = asyncio.create_task(generator())
        for i in range(1, slots + 1):
            await asyncio.sleep(max(0, t0 + i * interval - time.monotonic()))
            alive()
            pool0 = len((await other(0, 'get_transaction_pool_hashes')).get('tx_hashes') or [])
            pool1 = len((await other(1, 'get_transaction_pool_hashes')).get('tx_hashes') or [])
            if args.competing_every and i % args.competing_every == 0:
                begin = time.monotonic()
                a, b = await asyncio.gather(generate(0, 1, miner), generate(1, 1, miner))
                await asyncio.sleep(0.5 + 4 * delay)
                ta, tb = await tip(0), await tip(1)
                competing.append(dict(slot=i, monotonic=begin, block_n0=a[0], block_n1=b[0],
                                      diverged=ta != tb, tip_n0=ta, tip_n1=tb,
                                      pool_before=[pool0, pool1]))
                event('competing_slot', slot=i, diverged=ta != tb)
                continue
            begin = time.monotonic()
            block_hash = (await generate(0, 1, miner))[0]
            generated = time.monotonic()
            observed = await wait_tip(1, await tip(0))
            h = await header(0, block_hash)
            prev_diverged = competing and competing[-1]['slot'] == i - 1 and competing[-1]['diverged']
            rec = dict(slot=i, monotonic=begin, generate_s=generated - begin, relay_s=observed - begin,
                       observed_monotonic=observed, resolves_competing=bool(prev_diverged),
                       pool_before=[pool0, pool1], **h)
            blocks.append(rec)
            event('slot', slot=i, height=h['height'], num_txes=h['num_txes'], weight=h['block_weight'],
                  relay_s=rec['relay_s'], resolves_competing=rec['resolves_competing'])
        await gen
        event('steady_complete', txs=len(txs), wallet_errors=len(wallet_errors), blocks=len(blocks),
              competing=len(competing), proxy_bytes=link.bytes)

        # Partition/reorg under load: node 0 keeps admitting transactions and mining while cut off.
        assert await tip(0) == await tip(1) or (competing and competing[-1]['slot'] == slots), 'tips diverged before partition'
        if await tip(0) != await tip(1):
            block_hash = (await generate(0, 1, miner))[0]
            await wait_tip(1, await tip(0))
            blocks.append(dict(slot=slots + 1, monotonic=time.monotonic(), resolves_competing=True,
                               relay_s=None, generate_s=None, observed_monotonic=time.monotonic(),
                               pool_before=None, **(await header(0, block_hash))))
        before_bytes = link.bytes
        link.partition()
        await asyncio.sleep(0.2 + 2 * delay)
        root = await tip(0)
        assert await tip(1) == root
        part_txs = [await submit_tx(k, 'partition') for k in range(args.partition_txs)]
        part_hashes = [r['tx_hash'] for r in part_txs if 'tx_hash' in r]
        branch_a = await generate(0, 3, miner)
        branch_b = await generate(1, 4, miner)
        a, b = await tip(0), await tip(1)
        await asyncio.sleep(1)
        assert await tip(0) == a and await tip(1) == b and a != b
        assert link.bytes == before_bytes, 'partition forwarded bytes'
        a_headers = [await header(0, x) for x in branch_a]
        event('partition_proven', root=root, a=a, b=b, partition_txs=len(part_hashes),
              branch_a_txes=[x['num_txes'] for x in a_headers])
        begin = time.monotonic()
        link.enabled = True
        rejoined = await wait_tip(0, b, timeout=180)
        rejoin_s = rejoined - begin
        for x in branch_a:
            assert (await header(0, x))['orphan_status'], x
        pool0_after = set((await other(0, 'get_transaction_pool_hashes')).get('tx_hashes') or [])
        returned = [h for h in part_hashes if h in pool0_after]
        event('p2p_rejoin', reorg_depth=3, convergence_s=rejoin_s, tip=await tip(0),
              orphaned_txs_returned_to_pool=len(returned), of=len(part_hashes))
        # Wait (bounded) for the orphaned transactions to reach node 1's pool by re-relay.
        wait_begin = time.monotonic()
        pool1_after = set()
        while time.monotonic() - wait_begin < 20:
            pool1_after = set((await other(1, 'get_transaction_pool_hashes')).get('tx_hashes') or [])
            if all(h in pool1_after for h in part_hashes):
                break
            await asyncio.sleep(0.1)
        rerelay_s = time.monotonic() - wait_begin
        missing_at_n1 = [h for h in part_hashes if h not in pool1_after]
        # Block carrying transactions the receiver may not hold: fluffy-block request path.
        begin = time.monotonic()
        recovery_hash = (await generate(0, 1, miner))[0]
        recovery_observed = await wait_tip(1, await tip(0), timeout=180)
        recovery_header = await header(0, recovery_hash)
        event('post_rejoin_block', relay_s=recovery_observed - begin, num_txes=recovery_header['num_txes'],
              txs_missing_at_receiver_before_block=len(missing_at_n1))
        stop_watch.set()
        await watcher

        # Every submitted transaction must be in the chain on both nodes, none lost.
        final_hash = (await generate(0, 1, miner))[0]
        await wait_tip(1, await tip(0), timeout=180)
        lost = []
        for node in (0, 1):
            status = await other(node, 'get_transactions', dict(txs_hashes=list(txs), decode_as_json=False))
            found = {t['tx_hash']: t for t in status.get('txs', [])}
            for h, rec in txs.items():
                t = found.get(h)
                if not t or t.get('in_pool') or not t.get('block_height'):
                    lost.append(dict(node=node, tx_hash=h, phase=rec['phase']))
                elif node == 0:
                    rec['block_height'] = t['block_height']
        # Confirmation latency from receiver-observed block times.
        observed_by_height = {b['height']: b['observed_monotonic'] for b in blocks}
        k_equal_work = {90: 4, 120: 3}.get(target)
        for rec in txs.values():
            if 'block_height' not in rec or 'created_monotonic' not in rec:
                continue
            rec['first_seen_n1_s'] = (seen_n1[rec['tx_hash']] - rec['created_monotonic']) if rec['tx_hash'] in seen_n1 else None
            h1 = rec['block_height']
            rec['first_confirmation_s'] = observed_by_height[h1] - rec['submit_monotonic'] if h1 in observed_by_height else None
            hk = h1 + (k_equal_work or 1) - 1
            rec['equal_work_confirmation_s'] = observed_by_height[hk] - rec['submit_monotonic'] if hk in observed_by_height else None
            rec['equal_work_k'] = k_equal_work
        info = [await rpc(n, 'get_info') for n in (0, 1)]
        height = (await tip(0))[0]
        for n in (0, 1):
            supply = await rpc(n, 'get_coinbase_tx_sum', {'height': 0, 'count': height + 1})
            assert supply['emission_amount'] == height * reward, (supply['emission_amount'], height, reward)
            assert info[n]['target'] == target, info[n]['target']
        steady = [b for b in blocks if b.get('relay_s') is not None]
        relay = sorted(b['relay_s'] for b in steady)
        txrelay = sorted(v['first_seen_n1_s'] for v in txs.values() if v.get('first_seen_n1_s') is not None)
        result.update(
            result='PASS' if not lost else 'FAIL',
            scope=('actual P2P and wallet-rpc RingCT workload; regtest fixed difficulty 1; '
                   + ('accelerated slots' if args.accel != 1 else 'target-rate slots')
                   + '; empty-block warmup then loaded steady state; no FCMP; no capacity normalization'),
            funded_height=funded_tip[0], steady_slots=slots, steady_blocks=len(steady),
            competing_slots=competing, blocks=blocks, transactions=list(txs.values()),
            wallet_errors=wallet_errors, transactions_submitted=len(txs), transactions_lost=lost,
            block_relay_s=relay, block_relay_median_s=statistics.median(relay) if relay else None,
            block_relay_max_s=relay[-1] if relay else None,
            tx_relay_s=txrelay, tx_relay_median_s=statistics.median(txrelay) if txrelay else None,
            tx_relay_max_s=txrelay[-1] if txrelay else None,
            txs_per_block=[b['num_txes'] for b in steady], weight_per_block=[b['block_weight'] for b in steady],
            offered_bytes=sum(v.get('weight') or 0 for v in txs.values()),
            admitted_weight=sum(b['block_weight'] for b in steady),
            partition=dict(reorg_depth=3, rejoin_s=rejoin_s, partition_txs=len(part_hashes),
                           orphaned_txs_returned_to_pool_n0=len(returned),
                           rerelay_wait_s=rerelay_s, txs_missing_at_n1_before_recovery_block=len(missing_at_n1),
                           recovery_block_relay_s=recovery_observed - begin,
                           recovery_block_num_txes=recovery_header['num_txes'], final_block=final_hash),
            derived_stale_probability_poisson=dict(
                note='1-exp(-relay/target) using the measured block relay median and max at the TARGET interval; '
                     'a propagation-delay model, not a measured natural stale rate',
                median=1 - math.exp(-statistics.median(relay) / target) if relay else None,
                max=1 - math.exp(-relay[-1] / target) if relay else None),
            observed_rpc_weight_limits=[{k: v for k, v in x.items() if 'weight' in k} for x in info],
            proxy_bytes=link.bytes, proxy_connections=link.connections,
            timing='RPC generation start to receiver tip poll; 25 ms block poll; 50 ms pool poll',
            resources='1536MiB container; no swap; 2 CPU quota shared by two daemons, wallet-rpc and proxies')
        (WORK / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        event(result['result'], lost=len(lost))
    finally:
        link.partition()
        receipt = {}
        for name in ['memory.peak', 'memory.events', 'memory.max', 'memory.swap.max', 'cpu.max']:
            path = Path('/sys/fs/cgroup') / name
            if path.exists():
                receipt[name] = path.read_text()
        for server in servers:
            server.close()
            await server.wait_closed()
        if 'wallet' in PROCESSES:
            try:
                await wallet('stop_wallet')
            except Exception:  # noqa: BLE001 - shutdown best effort, exit code recorded below
                pass
        for p in PROCESSES.values():
            p.terminate()
        for p in PROCESSES.values():
            try:
                await asyncio.to_thread(p.wait, timeout=30)
            except subprocess.TimeoutExpired:
                p.kill()
                await asyncio.to_thread(p.wait)
        receipt['exit_codes'] = {k: p.returncode for k, p in PROCESSES.items()}
        (WORK / 'resources.json').write_text(json.dumps(receipt, indent=2) + '\n')
        (WORK / 'events.json').write_text(json.dumps(EVENTS, indent=2, default=str) + '\n')
        if not (WORK / 'result.json').exists():
            (WORK / 'result.json').write_text(json.dumps(result, indent=2, default=str) + '\n')
        assert all(p.returncode == 0 for k, p in PROCESSES.items() if k != 'wallet'), receipt


if __name__ == '__main__':
    profiles = runpy.run_path('/profiles/check-readiness.py')
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--profile', choices=profiles['PROFILES'], required=True)
    parser.add_argument('--seed', type=int, required=True)
    parser.add_argument('--link', choices=LINKS, default='nominal')
    parser.add_argument('--accel', type=float, default=6.0, help='slot = target_seconds / accel; 1 = target rate')
    parser.add_argument('--duration', type=float, default=240.0, help='steady-state wall seconds')
    parser.add_argument('--tx-interval', type=float, default=2.0, help='offered load: one transfer per N wall seconds')
    parser.add_argument('--outputs', type=int, default=2, help='outputs per transaction including change')
    parser.add_argument('--competing-every', type=int, default=4, help='induce competing blocks every Nth slot (0 = never)')
    parser.add_argument('--partition-txs', type=int, default=5)
    args = parser.parse_args()
    profiles['validate_profile'](Path('/src'), args.profile)
    args.target_seconds, args.reward_atomic = profiles['PROFILES'][args.profile]
    asyncio.run(main(args))
