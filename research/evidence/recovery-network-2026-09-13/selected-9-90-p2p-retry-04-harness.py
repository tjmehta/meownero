"""Bounded actual P2P partition/rejoin and malformed transport probe.

Uses the fixture address and generateblocks flow from test-reorg.py. RPC creates
blocks locally; the harness never submits/copies a block into the other daemon.
This is accelerated, empty-block regtest correctness evidence, not FCMP or DAA
performance. TCP shaping is per chunk/connection, not a calibrated WAN emulator.
"""
import argparse
import asyncio
import json
from pathlib import Path
import statistics
import runpy
import subprocess
import time
import urllib.request

WORK = Path('/work')
PROFILE = None
TARGET_SECONDS = None
REWARD_ATOMIC = None
ADDRESS = 'M9Lds8CcBgCJbqSiUvYfS3BfhEdxZmv8pDt25oW1LzxrZv9Uq6ARagiFViMGUE3gJk5VPWingCXVf1p2tyAy6SUeSLMMvfc'
PROCESSES = {}
EVENTS = []


def event(label, **fields):
    entry = dict(event=label, monotonic_s=time.monotonic(), **fields)
    EVENTS.append(entry)
    print(json.dumps(entry), flush=True)


def request(node, method, params):
    body = dict(jsonrpc='2.0', id='0', method=method, params=params or {})
    req = urllib.request.Request(f'http://127.0.0.1:{19081 + node * 100}/json_rpc',
                                 json.dumps(body).encode(), {'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=10) as response:
        result = json.load(response)
    assert 'error' not in result, result
    return result['result']


async def rpc(node, method, params=None):
    return await asyncio.to_thread(request, node, method, params)


async def tip(node):
    h = (await rpc(node, 'get_last_block_header'))['block_header']
    return h['height'], h['hash'], h['wide_cumulative_difficulty']


async def wait_tip(node, wanted, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if await tip(node) == wanted:
            return
        assert all(p.poll() is None for p in PROCESSES.values()), 'daemon exited'
        await asyncio.sleep(0.025)
    raise AssertionError(f'node {node} convergence timeout: {await tip(node)} != {wanted}')


class Link:
    def __init__(self):
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
                    # Fixed per-chunk delay plus 64 KiB/s per-stream serialization.
                    await asyncio.sleep(0.020 + len(data) / 65536)
                    if not self.enabled:
                        break
                    target.write(data)
                    await target.drain()
                    self.bytes += len(data)

            tasks = [asyncio.create_task(pump(reader, peer)),
                     asyncio.create_task(pump(upstream, writer))]
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


async def start(node):
    with (WORK / f'n{node}.stdout.log').open('a') as log:
        PROCESSES[node] = subprocess.Popen([
            '/src/build/release/bin/monerod', '--data-dir', str(WORK / f'n{node}'),
            '--regtest', '--keep-fakechain', '--fixed-difficulty', '1',
            '--non-interactive', '--no-igd', '--disable-dns-checkpoints', '--check-updates', 'disabled',
            '--allow-local-ip', '--add-exclusive-node', f'127.0.0.1:{20080 + node * 100}',
            '--p2p-bind-ip', '127.0.0.1', '--p2p-bind-port', str(19080 + node * 100),
            '--rpc-bind-ip', '127.0.0.1', '--rpc-bind-port', str(19081 + node * 100),
            '--zmq-rpc-bind-ip', '127.0.0.1', '--zmq-rpc-bind-port', str(19082 + node * 100),
            '--log-file', str(WORK / f'n{node}.log')], stdout=log, stderr=subprocess.STDOUT)
    for _ in range(120):
        assert PROCESSES[node].poll() is None, 'daemon exited at startup'
        try:
            await rpc(node, 'get_info')
            return
        except OSError:
            await asyncio.sleep(0.25)
    raise AssertionError('startup timeout')


async def generate(node, count):
    result = await rpc(node, 'generateblocks', dict(wallet_address=ADDRESS, amount_of_blocks=count))
    if 'blocks' not in result:
        raise AssertionError(f'generateblocks returned no blocks: {json.dumps(result, sort_keys=True)}')
    return result['blocks']


async def wait_core_ready():
    """Wait only after both daemons launched; CHECK_CORE_READY returns BUSY otherwise."""
    deadline = time.monotonic() + 30
    initial = {}
    while time.monotonic() < deadline:
        infos = [await rpc(n, 'get_info') for n in (0, 1)]
        if not initial:
            initial = {str(n): infos[n] for n in (0, 1)}
            event('initial_core_readiness', get_info=initial)
        if all(info.get('synchronized') for info in infos):
            event('core_ready', synchronized=[info.get('synchronized') for info in infos])
            return
        await asyncio.sleep(0.1)
    raise AssertionError(f'core readiness timeout: {json.dumps(initial, sort_keys=True)}')


async def main():
    link = Link()
    servers = [await asyncio.start_server(lambda r, w: link.accept(r, w, 19180), '127.0.0.1', 20080),
               await asyncio.start_server(lambda r, w: link.accept(r, w, 19080), '127.0.0.1', 20180)]
    try:
        await start(0)
        await start(1)
        await wait_core_ready()
        await generate(0, 65)
        await wait_tip(1, await tip(0))
        event('warmup_complete', tip=await tip(0), proxy_connections=link.connections)
        assert link.bytes > 0 and link.connections > 0
        samples = []
        for _ in range(12):
            begin = time.monotonic()
            await generate(0, 1)
            await wait_tip(1, await tip(0))
            samples.append(time.monotonic() - begin)
        event('connected_relay', samples_s=samples)
        before_bytes = link.bytes
        link.partition()
        await asyncio.sleep(0.2)
        root = await tip(0)
        assert await tip(1) == root
        branch_a = await generate(0, 3)
        await generate(1, 4)
        a, b = await tip(0), await tip(1)
        await asyncio.sleep(1)
        assert await tip(0) == a and await tip(1) == b and a != b
        assert link.bytes == before_bytes, 'partition forwarded bytes'
        event('partition_proven', root=root, a=a, b=b, forwarded_bytes=0)
        begin = time.monotonic()
        link.enabled = True
        await wait_tip(0, b)
        rejoin = time.monotonic() - begin
        for block_hash in branch_a:
            assert (await rpc(0, 'get_block_header_by_hash', {'hash': block_hash}))['block_header']['orphan_status']
        event('p2p_rejoin', reorg_depth=3, convergence_s=rejoin, tip=await tip(0))
        # A malformed inbound transport frame exercises the actual TCP P2P parser.
        # This is NOT an invalid-consensus-block-with-valid-PoW relay test (#11283).
        reader, writer = await asyncio.open_connection('127.0.0.1', 19080)
        writer.write(b'\x00' * 64)
        await writer.drain()
        try:
            rejected = await asyncio.wait_for(reader.read(1), timeout=5) == b''
            close_mode = 'EOF'
        except ConnectionResetError:
            rejected = True
            close_mode = 'TCP reset'
        writer.close()
        try:
            await writer.wait_closed()
        except ConnectionResetError:
            pass
        assert rejected, 'malformed P2P connection was not closed'
        assert await tip(0) == b and await tip(1) == b
        await generate(1, 1)
        await wait_tip(0, await tip(1))
        event('malformed_transport_closed_healthy_relay_survives', close_mode=close_mode)
        info = [await rpc(n, 'get_info') for n in (0, 1)]
        height = (await tip(0))[0]
        for n in (0, 1):
            supply = await rpc(n, 'get_coinbase_tx_sum', {'height': 0, 'count': height + 1})
            assert supply['emission_amount'] == height * REWARD_ATOMIC
            assert info[n]['target'] == TARGET_SECONDS, info[n]['target']
        result = dict(result='PASS', scope='actual P2P; accelerated empty-block regtest; fixed difficulty 1; no FCMP',
                      warmup_blocks=65, samples_s=samples, median_s=statistics.median(samples),
                      p95_nearest_rank_s=sorted(samples)[-1], p99_nearest_rank_s=sorted(samples)[-1],
                      timing='RPC generation start to receiver tip poll; includes mining/RPC; 25ms polling',
                      reorg_depth=3, rejoin_s=rejoin, malformed_transport_closed=rejected,
                      proxy_bytes=link.bytes, proxy_connections=link.connections,
                      shaping='20ms/chunk plus 64KiB/s/stream; up to two bidirectional connections',
                      cache='fresh daemon databases; 65-block warmup; host page cache uncontrolled, no purge',
                      resources='1536MiB total container; no swap; 2 CPU quota shared by both daemons and proxy',
                      profile=PROFILE, target_seconds=TARGET_SECONDS, reward_atomic=REWARD_ATOMIC,
                      configured_weight_budget=None, capacity_enforcement_tested=False, observed_rpc_weight_limits=[{k:v for k,v in x.items() if 'weight' in k} for x in info],
                      matched_90_comparison='BLOCKED: no paired loaded workload or enforced scaled dynamic capacity',
                      transactions=0, proofs=0, events=EVENTS)
        (WORK / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        event('PASS')
    finally:
        link.partition()
        resource_receipt = {}
        for name in ['memory.peak', 'memory.events', 'memory.max', 'memory.swap.max', 'cpu.max']:
            path = Path('/sys/fs/cgroup') / name
            if path.exists():
                resource_receipt[name] = path.read_text()
        for server in servers:
            server.close()
            await server.wait_closed()
        for p in PROCESSES.values():
            p.terminate()
        for p in PROCESSES.values():
            try:
                await asyncio.to_thread(p.wait, timeout=20)
            except subprocess.TimeoutExpired:
                p.kill()
                await asyncio.to_thread(p.wait)
        resource_receipt['daemon_exit_codes'] = {str(n): p.returncode for n, p in PROCESSES.items()}
        (WORK / 'resources.json').write_text(json.dumps(resource_receipt, indent=2) + '\n')
        (WORK / 'events.json').write_text(json.dumps(EVENTS, indent=2) + '\n')
        assert all(p.returncode == 0 for p in PROCESSES.values()), resource_receipt


if __name__ == '__main__':
    profiles = runpy.run_path('/profiles/check-readiness.py')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=profiles['PROFILES'], default='historical-0.9-120')
    PROFILE = parser.parse_args().profile
    profiles['validate_profile'](Path('/src'), PROFILE)
    TARGET_SECONDS, REWARD_ATOMIC = profiles['PROFILES'][PROFILE]
    asyncio.run(main())
