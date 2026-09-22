#!/usr/bin/env python3
"""Re-derive every per-step claim of a journey.py output directory with the accepted per-step verifiers, then the cross-step invariants."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
GENESIS = '20ce111b9a74c7ce79fbaafd053afb71b2f2335e208fa7e993fb46c8c91964d8'
IMAGE = 'sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e'
BINARY_SHA = 'b79cb49dbea95c0eeff7dca8c945d65f4fab3d49fb626fcbe7a9343569d4a2c1'
WALLET_SHA = '5782abee489e8b245b42fd237ece34d6df1c67929c552960755fab41de3a921a'
POOL_SHA = 'bbc3240607bf40bd3db7e13f011ccf9eda431dddd751918a3ebf4e3aaf129fad'
ADDRESS = 'M9Lds8CcBgCJbqSiUvYfS3BfhEdxZmv8pDt25oW1LzxrZv9Uq6ARagiFViMGUE3gJk5VPWingCXVf1p2tyAy6SUeSLMMvfc'
REWARD = 9000000000000
COIN = 10**12
# step, accepted verifier, its pass marker, minimum top index the accepted recipe guarantees, pinned executables
STEPS = [
    ('01-launch', 'verify.py', 'PASS_RECEIPT_RECONCILIATION', 3, {'monerod': BINARY_SHA}),
    ('02-payment', 'verify-payment.py', 'PASS_PAYMENT_RECEIPT_RECONCILIATION', 124, {'monerod': BINARY_SHA, 'monero-wallet-rpc': WALLET_SHA}),
    ('03-sync', 'verify-sync.py', 'PASS_RECEIPT_RECONCILIATION', 9, {'monerod': BINARY_SHA}),
    ('04-recover', 'verify-recover.py', 'PASS_RECEIPT_RECONCILIATION', 7, {'monerod': BINARY_SHA, 'monero-wallet-rpc': WALLET_SHA}),
    ('05-pool-restart', 'verify-pool-restart.py', 'PASS_RECEIPT_RECONCILIATION', 7, {'monerod': BINARY_SHA, 'p2pool': POOL_SHA}),
]
JOURNEY_FILES = ['chain/testnet-v0/journey.py', 'chain/testnet-v0/verify-journey.py',
                 'chain/testnet-v0/test-journey-refusals.py', 'chain/testnet-v0/journey.md']


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest(path):
    return dict(line.split('  ', 1)[::-1] for line in path.read_text().splitlines())


def main():
    work = Path(sys.argv[1])
    names = [s[0] for s in STEPS]

    def read(name):
        return json.loads((work / name).read_text())

    # 1. The single public manifest covers every step's public receipts, byte for byte, and nothing private.
    evidence = manifest(work / 'EVIDENCE.sha256')
    for name, sha in evidence.items():
        parts = Path(name).parts
        require(len(parts) <= 2 and (len(parts) == 1 or parts[0] in names) and 'data' not in parts, f'unexpected manifest path: {name}')
        require(sha256(work / name) == sha, f'changed receipt: {name}')
    for step in names:
        for name, sha in manifest(work / step / 'EVIDENCE.sha256').items():
            require(Path(name).name == name and evidence.get(f'{step}/{name}') == sha, f'{step}: receipt missing from the journey manifest: {name}')
        require(f'{step}/EVIDENCE.sha256' in evidence, f'{step}: step manifest not covered')

    # 2. Journey-level exits, sequencing and admission receipts.
    require((work / 'launcher.exit').read_text().strip() == '0', 'journey launcher exit')
    result = read('result.json')
    require(result['result'] == 'PASS', 'journey did not pass')
    steps = read('steps.json')
    require([s['step'] for s in steps] == names and result['steps'] == steps, 'five steps in freeze order')
    previous = None
    for row in steps:
        require(row['exit'] == 0 and row['result'] == 'PASS' and row['container_exit'] == '0', f"{row['step']}: step exit")
        require((work / f"{row['step']}.exit").read_text().strip() == '0', f"{row['step']}: exit receipt")
        require(row['seconds'] > 0 and row['started_utc'] < row['finished_utc'], f"{row['step']}: timeline")
        require(previous is None or previous['finished_utc'] <= row['started_utc'], f"{row['step']}: steps must not overlap")
        require(json.loads((work / row['step'] / 'resources.json').read_text())['elapsed_seconds'] <= row['seconds'], f"{row['step']}: container time")
        previous = row
    require(len({row['container'] for row in steps}) == 5, 'five distinct owned containers')
    require(result['elapsed_seconds'] >= sum(row['seconds'] for row in steps) == result['total_step_seconds'], 'journey time accounting')
    admissions = read('admission.json')
    require([a['step'] for a in admissions] == names and all(a['exit'] == 0 and '--check-only' in a['command'] for a in admissions),
            'five recipe admissions before any process')
    image = read('image-check.json')
    require(image['exit'] == 0 and image['stdout'].strip() == IMAGE, 'builder image pin at admission')
    require(read('lock-probe.json')['busy'] is False, 'heavy lock probe')
    resources = read('preflight-resources.json')
    require(min(resources['available_ram_bytes'], resources['free_disk_bytes']) >= resources['minimum_bytes'] == 5 * 1024**3, 'resource gate')
    pins = manifest(work / 'BINARY.sha256')
    require({Path(p).name: s for p, s in pins.items()} == {'monerod': BINARY_SHA, 'monero-wallet-rpc': WALLET_SHA, 'p2pool': POOL_SHA}, 'journey binary pins')
    inputs = manifest(work / 'INPUTS.sha256')
    require(all(name in inputs for name in JOURNEY_FILES), 'journey files pinned')

    # 3. Every per-step claim, re-derived by the accepted verifier for that milestone.
    verified = {}
    for step, verifier, marker, _, _ in STEPS:
        proc = subprocess.run([sys.executable, '-B', str(HERE / verifier), str(work / step)], capture_output=True, text=True, timeout=600)
        require(proc.returncode == 0 and marker in proc.stdout, f'{step}: {verifier} failed: {(proc.stderr or proc.stdout).strip()[-400:]}')
        verified[step] = json.loads(proc.stdout)
        require(verified[step]['result'] == marker, f'{step}: verifier result')

    # 4. Cross-step invariants over the five chains.
    baseline = read('baseline.json')
    profile = sha256(work / 'profile.json')
    genesis, summary = None, []
    for step, _, _, minimum_top, executables in STEPS:
        step_inputs = manifest(work / step / 'INPUTS.sha256')
        require(all(inputs.get(name) == sha for name, sha in step_inputs.items()), f'{step}: step pins differ from the journey manifest')
        require(read(f'{step}/baseline.json') == baseline and sha256(work / step / 'profile.json') == profile, f'{step}: baseline or profile differs')
        require({Path(p).name: s for p, s in manifest(work / step / 'BINARY.sha256').items()} == executables, f'{step}: executable pins')
        command = read(f'{step}/container-command.json')
        require(IMAGE in command and command[command.index('--network') + 1] == 'none', f'{step}: image pin and isolation')
        headers = read(f'{step}/headers.json')
        chain = headers[0]
        require(all(peer == chain for peer in headers), f'{step}: peers hold different headers')
        head = {k: v for k, v in chain[0].items() if k != 'depth'}
        require(head['hash'] == GENESIS and head['reward'] == 0 and head['major_version'] == 1, f'{step}: genesis')
        require(genesis is None or head == genesis, f'{step}: genesis header differs from the first step')
        genesis = head
        readback = read(f'{step}/profile-readback.json')
        for n in ('0', '1'):
            row = readback[n]
            require(row['info']['height'] == 1 and row['info']['nettype'] == 'mainnet' and row['info']['target'] == 90, f'{step}: fresh readback')
            require(row['genesis']['hash'] == GENESIS and row['fork']['version'] == 16 and row['fork']['earliest_height'] == 1, f'{step}: fork readback')
            require(row['template']['height'] == 1 and row['template']['expected_reward'] == REWARD, f'{step}: reward readback')
        work_sum = 0
        for height, h in enumerate(chain):
            require(h['height'] == height and (height == 0 or h['prev_hash'] == chain[height - 1]['hash']), f'{step}: header link')
            require(int(h['wide_cumulative_difficulty'], 16) > work_sum or height == 0, f'{step}: cumulative work must increase')
            work_sum = int(h['wide_cumulative_difficulty'], 16)
        top = chain[-1]
        require(top['height'] >= minimum_top, f'{step}: top index {top["height"]} below the accepted minimum {minimum_top}')
        final = read(f'{step}/rpc-final.json')
        emission = final[0]['sum']['emission_amount']
        fees = final[0]['sum']['fee_amount']
        require(all(f['sum']['emission_amount'] == emission and f['sum']['fee_amount'] == fees for f in final), f'{step}: peers disagree on supply')
        require(emission == top['height'] * REWARD, f'{step}: emission is not top index times the flat subsidy')
        require(sum(h['reward'] for h in chain) == emission + fees, f'{step}: header rewards must equal subsidy plus fees')
        require(min(h['reward'] for h in chain[1:]) == REWARD and all(h['major_version'] == 16 for h in chain[1:]), f'{step}: mined reward/fork')
        summary.append({'step': step, 'top_index': top['height'], 'tip': top['hash'], 'cumulative_work': top['wide_cumulative_difficulty'],
                        'emission_atomic': emission, 'fees_atomic': fees, 'num_txes': sum(h['num_txes'] for h in chain),
                        'memory_peak_bytes': verified[step]['memory_peak_bytes'] if 'memory_peak_bytes' in verified[step]
                        else int(json.loads((work / step / 'resources.json').read_text())['memory.peak'])})
    # Wallet and payout accounting under the one subsidy, from the funded payment through recovery and the pool restart.
    payment = {r['case']: r for r in read('02-payment/result.json')['cases']}
    funded = payment['solo_funded']
    require(funded['tip'][0] >= 100 and funded['sender']['balance'] == funded['tip'][0] * REWARD, 'payment: solo funding equals mined subsidy')
    paid, spent = payment['payment_relay'], payment['recovered_spend_relay']
    require(paid['amount'] == 5 * COIN and spent['amount'] == 2 * COIN, 'payment: amounts')
    require(payment['wallet_reopened']['after']['balance']['balance'] == paid['amount'] - spent['amount'] - spent['fee'],
            'payment: restored wallet balance after reopen')
    require(payment['recovered_spend_confirmed']['recipient']['balance'] == funded['sender']['balance'] - paid['amount'] - paid['fee'] + spent['amount'],
            'payment: sender balance after payment and return')
    require(summary[1]['fees_atomic'] == paid['fee'] + spent['fee'] and summary[1]['num_txes'] == 2, 'payment: chain fees are the two transaction fees')
    require(all(s['fees_atomic'] == 0 and s['num_txes'] == 0 for i, s in enumerate(summary) if i != 1), 'empty-block steps carry no transactions')
    recovery = read('04-recover/wallet-restart.json')
    payout = read('04-recover/result.json')['payout_tip']
    require(recovery['wallet_before']['balance']['balance'] == payout['height'] * REWARD
            and recovery['wallet_after_cold_restore'] == recovery['wallet_before'], 'recover: payout wallet equals mined subsidy across restore')
    pool = read('05-pool-restart/pool-restart.json')
    commands = read('05-pool-restart/process-commands.json')['pool']
    require(pool['final_api']['pool']['pool_statistics']['totalBlocksFound'] == 0 and commands[commands.index('--wallet') + 1] == ADDRESS,
            'pool restart: no pool-attributed block and the public fixture payout address')
    print(json.dumps({'result': 'PASS_JOURNEY_RECEIPT_RECONCILIATION', 'steps': summary,
                      'per_step': {step: {k: v for k, v in verified[step].items() if k not in ('scope',)} for step in names},
                      'journey_wall_seconds': result['elapsed_seconds'], 'total_step_seconds': result['total_step_seconds'],
                      'memory_peak_bytes_max': max(s['memory_peak_bytes'] for s in summary),
                      'chains': 'five fresh two-peer chains from one genesis, one per accepted recipe; tips are per step, not cumulative',
                      'scope': 'saved receipt consistency across the sequenced accepted recipes; not an independent operator run, audit, '
                               'FCMP/F3, share or payout clearance, 90-second GO or mainnet readiness'}, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, IndexError, TypeError) as error:
        print(f'FAIL: {error}', file=sys.stderr)
        sys.exit(1)
