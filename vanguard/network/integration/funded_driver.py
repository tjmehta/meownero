#!/usr/bin/env python3
"""F1 private native journey. Requires a separately reviewed exact runtime grant.

Imports the accepted genesis helper without modifying its CLI, Digest, redactor,
process ownership or private-file machinery. Native responses stay in memory or
private staging. Only the funded contract's fixed witnesses reach /public.
"""
import contextlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import profile_contract as c
from integration import funded_contract as f

spec = importlib.util.spec_from_file_location('accepted_genesis_helpers', c.HERE/'profile-integration.py')
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


def hex64(value):
    c.require(type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None,
              'native hash shape')
    return value


def fingerprint(value):
    return c.digest(hex64(value).encode('ascii'))


class Journey:
    def __init__(self):
        self.rows = f.empty_rows()
        self.nodes = {}
        self.wallets = {}
        self.auth = {}
        self.binaries = {name: c.digest((d.BIN/name).read_bytes()) for name in
                         ('monerod', 'monero-wallet-cli', 'monero-wallet-rpc')}

    def row(self, file, key, **witness):
        c.require(key in f.REQUIRED[file], 'unknown funded row')
        self.rows[file][key] = dict(status='PASS', **witness)

    def state(self, index):
        info = self.nodes[index][0].call('get_info')
        c.require(info['status'] == 'OK' and type(info['height']) is int and
                  1 <= info['height'] <= f.MAX_COUNT, 'funded count bound')
        hex64(info['top_block_hash'])
        if info['height'] == 1:
            c.require(info['top_block_hash'] == c.GENESIS, 'funded genesis identity')
        # N includes genesis. No mining path may carry on at N=80.
        c.require(info['height'] < f.MAX_COUNT, 'funded block ceiling reached')
        return info['height'], info['top_block_hash'], info['wide_cumulative_difficulty']

    def agree(self, count=None):
        a, b = self.state(0), self.state(1)
        return a if a == b and (count is None or a[0] == count) else None

    def wait(self, check, seconds=None):
        # Failures in predicates propagate. Never turn a cap/semantic failure into a retry.
        end = time.monotonic() + d.budget(seconds if seconds is not None else f.WORK_SECONDS)
        while time.monotonic() < end:
            value = check()
            if value:
                return value
            d.census()
            time.sleep(d.budget(.1))
        raise TimeoutError('funded milestone deadline')

    def node(self, index, mining=None):
        port = 48080 + index*100
        root = d.PRIVATE/f'node{index}'
        if root.exists():
            c.root_manifest(root, d.SAVED[str(root)])
            d.released(root)
        else:
            root.mkdir(mode=0o700)
        login = self.auth.setdefault(index, 'node:'+secrets.token_hex(24))
        argv = [str(d.BIN/'monerod'), '--testnet', '--data-dir', str(root),
            '--non-interactive', '--no-igd', '--allow-local-ip', '--disable-dns-checkpoints',
            '--check-updates', 'disabled', '--hide-my-port', '--max-concurrency', '1',
            '--no-zmq', '--rpc-ssl', 'disabled', '--restricted-rpc',
            '--p2p-bind-ip', '127.0.0.1', '--p2p-bind-ipv6-address', '::1',
            '--p2p-bind-port', str(port), '--rpc-bind-ip', '127.0.0.1',
            '--rpc-bind-port', str(port+1), '--add-exclusive-node',
            f'127.0.0.1:{48180 if index == 0 else 48080}',
            '--log-level', '1', '--log-file', str(root/'native.log')]
        if mining is not None:
            c.require(index == 0, 'only node A may mine')
            argv += ['--start-mining', mining, '--mining-threads', '1']
        (root/'creation.json').write_bytes(c.canonical(dict(d.creation('daemon', self.binaries), stopped_saved=False)))
        os.chmod(root/'creation.json', 0o600)
        d.launch(f'node{index}', argv, root, dict(d.ENV, RPC_LOGIN=login))
        rpc = d.RPC(port+1, login)
        d.wait(lambda: rpc.call('get_info'), 30)
        self.nodes[index] = (rpc, root)
        self.state(index)
        return rpc

    def stop_node(self, index):
        return d.save_node(index, self.nodes[index][1], self.binaries)

    def mine_to(self, count, address):
        c.require(1 < count < f.MAX_COUNT and self.state(0)[0] < count, 'mining target')
        self.stop_node(0)
        self.node(0, address)
        self.wait(lambda: self.state(0)[0] >= count)
        self.stop_node(0)
        # Native restart without mining freezes this exact height for wallet controls.
        self.node(0)
        c.require(self.state(0)[0] == count, 'mining target overshot')
        self.wait(lambda: self.agree(count), 60)

    def wallet_root(self, name, daemon):
        root = d.PRIVATE/name
        root.mkdir(mode=0o700)
        (root/'password').write_text(secrets.token_hex(32)+'\n')
        (root/'cli.conf').write_text('daemon-login='+self.auth[daemon]+'\ndaemon-ssl=disabled\n')
        for name in ('password', 'cli.conf'):
            os.chmod(root/name, 0o600)
        return root

    def signer(self, name, root, daemon, port, *, restore=False, generation=1):
        d.released(root)
        if not restore:
            c.root_manifest(root, d.SAVED[str(root)])
        cwd = d.PRIVATE/f'{name}-rpc{generation}'
        cwd.mkdir(mode=0o700)
        argv = [str(d.BIN/'monero-wallet-rpc'), '--testnet', '--config-file', str(root/'cli.conf'),
            '--daemon-address', f'127.0.0.1:{48081+daemon*100}',
            '--rpc-bind-ip', '127.0.0.1', '--rpc-bind-port', str(port), '--rpc-ssl', 'disabled',
            '--log-file', str(cwd/'native.log')]
        # Pinned main rejects password-file together with wallet-dir (5039-5043).
        # The empty restore server receives the new password only in its RPC body.
        argv += ['--wallet-dir', str(root)] if restore else [
            '--wallet-file', str(root/'wallet'), '--password-file', str(root/'password')]
        # Authentication remains enabled: native generates a private per-process login.
        d.launch(name, argv, cwd)
        login = d.wait(lambda: c.check_file(cwd/f'monero-wallet-rpc.{port}.login', modes=(0o400, 0o600)).decode(), 15)
        rpc = d.RPC(port, login)
        d.wait(lambda: rpc.call('get_version') if restore else rpc.healthy(True), 30)
        self.wallets[name] = (rpc, root, port)
        return rpc

    def stop_wallet(self, name):
        rpc, root, port = self.wallets[name]
        rpc.call('store')
        d.stop(name)
        d.absent(port)
        d.released(root)
        d.seal(root, 'wallet', self.binaries)

    def refresh(self, rpc):
        rpc.call('refresh', dict(start_height=0))

    def outputs(self, rpc):
        return rpc.call('incoming_transfers', dict(transfer_type='all', account_index=0,
            subaddr_indices=[])).get('transfers', [])

    def output(self, rpc, txid, amount):
        matches = [x for x in self.outputs(rpc) if x['tx_hash'] == txid and x['amount'] == amount]
        c.require(len(matches) == 1, 'one exact received output')
        value = matches[0]
        hex64(value['key_image'])
        hex64(value['pubkey'])
        return value

    def transfer(self, rpc, address, amount, *, refusal=None, fee_ceiling=None):
        params = dict(destinations=[dict(amount=amount, address=address)], account_index=0,
            subaddr_indices=[], subtract_fee_from_outputs=[], priority=0, ring_size=0,
            unlock_time=0, payment_id='', get_tx_key=False, do_not_relay=refusal is not None,
            get_tx_hex=False, get_tx_metadata=False)
        code, value = rpc.call('transfer', params, raw=True)
        c.require(code == 200, 'transfer transport')
        if refusal is not None:
            c.require(value.get('error', {}).get('code') == refusal and 'result' not in value,
                      'expected native transfer refusal')
            return refusal
        c.require('error' not in value, 'native funded transfer failed')
        tx = value['result']
        hex64(tx['tx_hash'])
        c.require(type(tx['fee']) is int and 0 < tx['fee'] < (fee_ceiling or amount) and tx['amount'] == amount,
                  'native estimator fee/amount')
        keys = tx['spent_key_images']['key_images']
        c.require(len(keys) == 1, 'single native input required')
        hex64(keys[0])
        return tx

    def confirmed(self, txid, block, count, expected):
        c.require(self.agree(count) is not None, 'confirmation peer count/tip')
        entries, block_hashes = [], []
        for index in (0, 1):
            value = self.nodes[index][0].call('', dict(txs_hashes=[txid], decode_as_json=True,
                prune=False, split=False), path='get_transactions')
            txs = value.get('txs', [])
            c.require(value['status'] == 'OK' and not value.get('missed_tx') and len(txs) == 1,
                      'missing native confirmation')
            tx = txs[0]
            c.require(tx['tx_hash'] == txid and tx['in_pool'] is False and
                      tx['block_height'] == block and tx['confirmations'] == count-block,
                      'wrong native confirmation')
            entries.append(tx)
            admitted = self.nodes[index][0].call('get_block', dict(height=block, hash='', fill_pow_hash=False))
            header = admitted['block_header']
            c.require(header['orphan_status'] is False and header['height'] == block and
                json.loads(admitted['json'])['tx_hashes'].count(txid) == 1,
                'confirmation block membership')
            block_hashes.append(hex64(header['hash']))
        c.require(block_hashes[0] == block_hashes[1], 'confirmation block disagreement')
        c.require(entries[0]['as_json'] == entries[1]['as_json'], 'confirmed transaction disagreement')
        decoded = json.loads(entries[0]['as_json'])
        c.require(decoded['rct_signatures']['type'] == 7 and decoded['unlock_time'] == 0 and
            bool(decoded['vout']) and all('carrot_v1' in x['target'] for x in decoded['vout']) and
            bool(decoded['vin']) and all(x['key']['key_offsets'] == [] for x in decoded['vin']),
            'native FCMP CARROT transaction format')
        c.require(int(decoded['rct_signatures']['txnFee']) == expected['fee'] and
            [x['key']['k_image'] for x in decoded['vin']] == expected['spent_key_images']['key_images'],
            'confirmed fee/input lineage')
        return decoded

    def pool(self):
        return [self.nodes[i][0].call('', path='get_transaction_pool_hashes').get('tx_hashes', [])
                for i in (0, 1)]

    def run(self):
        self.node(0)
        self.node(1)
        self.wait(lambda: self.agree(1), 60)
        for i in (0, 1):
            self.nodes[i][0].auth_controls()
        roots = [self.wallet_root(f'wallet{i}', i) for i in (0, 1)]
        for i, root in enumerate(roots):
            d.cli(root, 48081+i*100, True)
            d.cli(root, 48081+i*100)
        self.row('wallet.json', 'persisted_height_zero', wallets=2, fresh_process_readback=True)
        a = self.signer('signer-a', roots[0], 0, 48083)
        b = self.signer('signer-b', roots[1], 1, 48183)
        addresses = [rpc.call('get_address', dict(account_index=0, address_index=[]))['address']
                     for rpc in (a, b)]
        for rpc in (a, b):
            rpc.auth_controls(True)
        seed = b.call('query_key', dict(key_type='mnemonic'))['key']
        c.require(type(seed) is str and len(seed.split()) == 25, 'private recovery material')

        # Actual B restart/catch-up while A continues native single-thread mining.
        self.stop_node(0)
        self.node(0, addresses[0])
        # Initial low-difficulty blocks may arrive quickly; only the maturity
        # checkpoints require exact targets. Do not demand an exact early N3.
        self.wait(lambda: self.agree() if self.state(0)[0] >= 3 else None)
        before = self.state(1)[0]
        c.require(2 <= before < 58, 'restart funding headroom')
        old = self.stop_node(1)
        self.wait(lambda: self.state(0)[0] >= before+2)
        self.node(1)
        caught = self.wait(lambda: self.agree(), 120)
        c.require(caught[0] >= before+2 and caught[0] < 60 and d.PROCS['node1'][1] != old,
                  'non-genesis restart catchup')
        self.stop_node(0)
        self.node(0)
        self.wait(lambda: self.agree(), 60)
        self.row('peer.json', 'restart_catchup', before_count=before, after_count=caught[0],
            changed_process=True, mining_during_restart=True, tip_sha256=fingerprint(caught[1]))

        self.mine_to(60, addresses[0])
        block = self.nodes[0][0].call('get_block', dict(height=1, hash='', fill_pow_hash=False))
        coinbase = json.loads(block['json'])['miner_tx']
        coinbase_id = hex64(block['miner_tx_hash'])
        c.require(coinbase['unlock_time'] == 61 and sum(x['amount'] for x in coinbase['vout']) == 9*f.ATOMIC,
                  'native b1 reward/unlock')
        self.refresh(a)
        original = self.output(a, coinbase_id, 9*f.ATOMIC)
        c.require(original['block_height'] == 1 and original['unlocked'] is False,
                  'N60 coinbase unexpectedly unlocked')
        self.transfer(a, addresses[1], f.ATOMIC, refusal=-37)
        pool = self.pool()
        c.require(pool == [[], []], 'early spend changed pool')
        self.transfer(a, d.FOREIGN, f.ATOMIC, refusal=-2)
        c.require(self.pool() == pool, 'wrong-network payment changed pool')
        self.row('auth.json', 'wrong_network_payment_refusal', code=-2, unchanged_pool=True)

        self.mine_to(61, addresses[0])
        self.refresh(a)
        eligible = self.output(a, coinbase_id, 9*f.ATOMIC)
        c.require(eligible['unlocked'] is True and eligible['key_image'] == original['key_image'],
                  'N61 coinbase eligibility')
        payment = self.transfer(a, addresses[1], f.ATOMIC, fee_ceiling=8*f.ATOMIC)
        c.require(payment['spent_key_images']['key_images'] == [original['key_image']],
                  'payment did not spend b1 coinbase')
        self.mine_to(62, addresses[0])
        self.confirmed(payment['tx_hash'], 61, 62, payment)
        self.refresh(a)
        self.refresh(b)
        c.require(self.output(a, coinbase_id, 9*f.ATOMIC)['spent'] is True, 'coinbase not spent at N62')
        received = self.output(b, payment['tx_hash'], f.ATOMIC)
        c.require(received['block_height'] == 61 and received['spent'] is False, 'received payment lineage')
        self.row('peer.json', 'non_genesis_agreement', count=62,
            tip_sha256=fingerprint(self.state(0)[1]), peers=2)
        self.row('wallet.json', 'coinbase_maturity', block_index=1, amount_atomic=9*f.ATOMIC,
            unlock_time=61, early_count=60, early_refusal_code=-37, eligible_count=61,
            after_count=62, payment_block_index=61, txid_sha256=fingerprint(payment['tx_hash']),
            fee_atomic=payment['fee'], confirmations=1, peers=2, input_matches_coinbase=True)

        self.stop_wallet('signer-b')
        restored_root = self.wallet_root('wallet-restored', 1)
        restored = self.signer('signer-restored', restored_root, 1, 48183, restore=True)
        value = restored.call('restore_deterministic_wallet', dict(filename='wallet',
            password=c.check_file(restored_root/'password').decode().strip(), seed=seed,
            seed_offset='', restore_height=0, language='English', autosave_current=False,
            enable_multisig_experimental=False))
        seed = None
        c.require(value['address'] == addresses[1], 'restored wallet identity')
        del value  # Native response contains private seed; never serialize it.
        self.refresh(restored)
        recovered = self.output(restored, payment['tx_hash'], f.ATOMIC)
        fields = ('amount', 'tx_hash', 'pubkey', 'key_image', 'global_index', 'block_height', 'spent')
        c.require(all(recovered[k] == received[k] for k in fields), 'seed rescan output/key image differs')
        self.stop_wallet('signer-restored')
        d.cli(restored_root, 48181)  # Separate native process reads persisted restore height0.
        restored = self.signer('signer-restored', restored_root, 1, 48183, generation=2)
        restored.auth_controls(True)
        output_digest = c.digest(c.canonical({key: recovered[key] for key in fields}))
        self.row('wallet.json', 'funded_seed_rescan', restore_height=0, payment_block_index=61,
            amount_atomic=f.ATOMIC, txid_sha256=fingerprint(payment['tx_hash']),
            output_sha256=output_digest, key_image_sha256=fingerprint(recovered['key_image']),
            identity_matches=True, fresh_process_readback=True)
        self.row('auth.json', 'private_signer_auth', signers=3,
            missing_wrong_credentials_rejected=True, restricted=False)

        self.mine_to(71, addresses[0])
        self.refresh(restored)
        c.require(self.output(restored, payment['tx_hash'], f.ATOMIC)['unlocked'] is True,
                  'received output not eligible at N71')
        spend = self.transfer(restored, addresses[0], f.ATOMIC//10, fee_ceiling=9*f.ATOMIC//10)
        c.require(spend['spent_key_images']['key_images'] == [recovered['key_image']],
                  'later spend did not consume received output')
        self.mine_to(72, addresses[0])
        self.confirmed(spend['tx_hash'], 71, 72, spend)
        self.refresh(restored)
        c.require(self.output(restored, payment['tx_hash'], f.ATOMIC)['spent'] is True,
                  'received output not spent')
        self.row('wallet.json', 'received_output_spend', submitted_count=71, block_index=71,
            confirmed_count=72, txid_sha256=fingerprint(spend['tx_hash']), amount_atomic=f.ATOMIC//10,
            fee_atomic=spend['fee'], input_matches_received=True,
            input_key_image_sha256=fingerprint(recovered['key_image']), confirmations=1, peers=2)
        # The lead also requires b72 confirmed; N73 makes that literal bound explicit.
        self.mine_to(73, addresses[0])
        final = self.agree(73)
        self.confirmed(spend['tx_hash'], 71, 73, spend)
        self.row('peer.json', 'final_block_72', count=73, block_index=72, peers=2,
            tip_sha256=fingerprint(final[1]))
        txids = []
        for height in range(1, 73):
            value = self.nodes[0][0].call('get_block', dict(height=height, hash='', fill_pow_hash=False))
            txids += json.loads(value['json']).get('tx_hashes', [])
            c.require(len(txids) <= f.MAX_TRANSACTIONS, 'funded transaction ceiling')
        c.require(sorted(txids) == sorted([payment['tx_hash'], spend['tx_hash']]),
                  'unexpected native transaction inventory')
        d.census()
        self.row('isolation.json', 'native_mining_bounds', count=73, transaction_count=2,
            max_count=f.MAX_COUNT, max_transactions=f.MAX_TRANSACTIONS, threads=1, light_mode=True,
            external_funding=False, loopback_only=True)
        self.stop_wallet('signer-a')
        self.stop_wallet('signer-restored')
        self.stop_node(0)
        self.stop_node(1)
        self.row('reopen.json', 'funded_save_exit_release', daemons=2, wallets=2, forced_kill=False)


def main():
    os.umask(0o077)
    d.PRIVATE.mkdir(mode=0o700)
    d.DEADLINE = time.monotonic()+f.WORK_SECONDS-30
    d.HARD_END = d.DEADLINE+30
    journey = None
    try:
        journey = Journey()
        journey.run()
        return 0
    except Exception as error:
        (d.PRIVATE/'failure-class').write_text(type(error).__name__+'\n')
        (d.PRIVATE/'failure-traceback').write_text(__import__('traceback').format_exc())
        return 1
    finally:
        d.DEADLINE = d.HARD_END
        for name, (process, _) in d.PROCS.items():
            if process.poll() is None:
                with contextlib.suppress(Exception):
                    d.stop(name, graceful=False)
        rows = journey.rows if journey is not None else f.empty_rows()
        for file in f.REQUIRED:
            if file not in ('build.json', 'resources.json', 'cleanup.json'):
                (d.PUBLIC/file).write_text(json.dumps(rows[file], indent=2)+'\n')


if __name__ == '__main__':
    raise SystemExit(main())
