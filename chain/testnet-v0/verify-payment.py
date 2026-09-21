#!/usr/bin/env python3
"""Reconcile TJS-230 saved public receipts without starting any processes."""
import hashlib
import json
from pathlib import Path
import sys


def check(ok, message):
    if not ok:
        raise ValueError(message)


def verify(work):
    def read(name):
        return json.loads((work / name).read_text())

    for line in (work / 'EVIDENCE.sha256').read_text().splitlines():
        expected, name = line.split('  ', 1)
        check(Path(name).name == name, 'public manifest must contain only top-level files')
        check(hashlib.sha256((work / name).read_bytes()).hexdigest() == expected, f'checksum mismatch: {name}')
    result = read('result.json')
    check(result['result'] == 'PASS' and result['funding'] == 'solo', 'journey did not pass with solo funds')
    cases = {r['case']: r for r in result['cases'] if r['case'] not in ('mining_started', 'mining_stopped')}
    a = cases['solo_funded']['sender']['balance']
    payment, returned = cases['payment_relay'], cases['recovered_spend_relay']
    check(payment['amount'] == 5*10**12 and returned['amount'] == 2*10**12, 'unexpected payment amounts')
    for tx, origin in ((payment, 0), (returned, 1)):
        check(tx['origin'] == origin and tx['fee'] > 0, 'origin or fee mismatch')
        check(len(tx['pools']) == 2 and all(tx['txid'] in pool for pool in tx['pools']), 'missing cross-peer pool witness')
        check(len(tx['decoded']) == 2 and {d['node'] for d in tx['decoded']} == {0, 1}, 'missing peer decode')
        for d in tx['decoded']:
            check(d['in_pool'] and d['version'] == 2 and d['rct_type'] == 6 and d['ring_sizes']
                  and all(r == 16 for r in d['ring_sizes']) and d['fee'] == tx['fee'], 'private tx/fee mismatch')
    confirmed = cases['payment_confirmed']
    check(confirmed['sender_before']['balance'] == a, 'funding baseline mismatch')
    check(confirmed['sender_after']['balance'] == a-payment['amount']-payment['fee'], 'sender debit mismatch')
    check(confirmed['recipient']['balance'] == payment['amount'] and
          [payment['txid'], payment['amount']] in confirmed['incoming'], 'recipient credit mismatch')
    restored = cases['seed_restored']
    check(restored['node'] == 1 and restored['address_matches'] and restored['original'] == restored['restored'],
          'restore state differs')
    check(restored['restored']['balance'] == confirmed['recipient'] and
          restored['restored']['incoming'] == confirmed['incoming'], 'restore unbound to received funds')
    spent = cases['recovered_spend_confirmed']
    check(spent['sender']['balance'] == payment['amount']-returned['amount']-returned['fee'], 'restored debit mismatch')
    check(spent['recipient']['balance'] == confirmed['sender_after']['balance']+returned['amount'], 'return credit mismatch')
    reopened = cases['wallet_reopened']
    check(reopened['address_matches'] and reopened['before'] == reopened['after'], 'reopen differs')
    check(reopened['after']['balance'] == spent['sender'] and
          [returned['txid'], returned['amount'], returned['fee']] in reopened['after']['outgoing'], 'reopen spend history missing')
    headers, final = read('headers.json'), read('rpc-final.json')
    check(len(headers) == len(final) == 2, 'expected two peers')
    hashes = []
    fees = payment['fee']+returned['fee']
    for n in (0, 1):
        chain = headers[n]
        check(chain[0]['height'] == 0 and chain[0]['reward'] == 0 and
              chain[0]['hash'] == '20ce111b9a74c7ce79fbaafd053afb71b2f2335e208fa7e993fb46c8c91964d8', 'genesis mismatch')
        for height, h in enumerate(chain[1:], 1):
            check(h['height'] == height and h['prev_hash'] == chain[height-1]['hash'] and h['major_version'] == 16,
                  'broken header chain/fork')
        info, sums = final[n]['info'], final[n]['sum']
        check(info['height'] == len(chain) and info['top_block_hash'] == chain[-1]['hash'], 'tip mismatch')
        check(info['cumulative_difficulty'] == sum(h['difficulty'] for h in chain) == int(result['tip'][2], 16),
              'native work mismatch')
        check(sums['emission_amount'] == (len(chain)-1)*9*10**12 == result['emission'], 'emission mismatch')
        check(sums['fee_amount'] == fees == result['fee_total'], 'aggregate fee mismatch')
        check(sum(h['reward'] for h in chain) == sums['emission_amount']+fees, 'header reward mismatch')
        hashes.append([h['hash'] for h in chain])
        for row, tx in ((confirmed, payment), (spent, returned)):
            check(row['txid'] == tx['txid'] and len(row['confirmations']) == 2, 'confirmation tx mismatch')
            c = row['confirmations'][n]
            check(c['node'] == n and c['txid'] == tx['txid'] and c['block_hash'] == chain[c['height']]['hash'],
                  'confirmation does not match canonical chain')
    check(hashes[0] == hashes[1] and result['tip'][:2] == [len(hashes[0])-1, hashes[0][-1]], 'peers differ')
    command = read('container-command.json')
    for flag, value in [('--network', 'none'), ('--memory=4g', None), ('--memory-swap=4g', None),
                        ('--cpus=2', None), ('--pids-limit=256', None), ('--read-only', None)]:
        check(flag in command and (value is None or command[command.index(flag)+1] == value), 'isolation/cap missing')
    check(not any(x in command for x in ('-p', '--publish', '--privileged', '--network=host')), 'unsafe container option')
    resources = read('resources.json')
    check(set(resources['exit_codes']) == {'peer0', 'peer1', 'A', 'S', 'B', 'D'} and
          not any(resources['exit_codes'].values()), 'owned process exit failure')
    events = dict(line.split() for line in resources['memory.events'].splitlines())
    check(all(int(events.get(k, 0)) == 0 for k in ('oom', 'oom_kill', 'max')), 'memory limit event')
    check((work / 'container.exit').read_text().strip() == '0', 'container failed')
    return {'result': 'PASS_PAYMENT_RECEIPT_RECONCILIATION', 'funding': 'solo', 'fees_atomic': fees,
            'top_index': len(hashes[0])-1, 'scope': 'saved receipt consistency, not independent execution'}


if __name__ == '__main__':
    try:
        print(json.dumps(verify(Path(sys.argv[1])), indent=2))
    except (OSError, ValueError, KeyError, IndexError, TypeError) as error:
        print(f'FAIL: {error}', file=sys.stderr)
        sys.exit(1)
