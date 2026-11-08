"""Closed, separate F1 workload; no native effects or authorization on import."""
import re

WORKLOAD = 'funded-two-peer-journey'
WORK_SECONDS = 14700
WALL_SECONDS = 15000
MAX_COUNT = 80  # Chain block count N, including genesis; block indexes are b=N-1.
MAX_TRANSACTIONS = 10
ATOMIC = 10**12
AUTHORITY_COMMENT = '3eedebc0-7ccc-4f4e-a35c-529b5013f02e'
RETAINED_SHA256 = '1b2815e21fb4c41ccd269e73f3eca3f905c872900e69d5a6d1c24537406275d6'
RETAINED_ROOT = '<agent-scratch>'
REQUIRED = {
    'build.json': ['three_production_binaries', 'rpc_translation_unit'],
    'peer.json': ['non_genesis_agreement', 'restart_catchup', 'final_block_72'],
    'wallet.json': ['persisted_height_zero', 'coinbase_maturity', 'funded_seed_rescan', 'received_output_spend'],
    'auth.json': ['private_signer_auth', 'wrong_network_payment_refusal'],
    'isolation.json': ['native_mining_bounds'],
    'reopen.json': ['funded_save_exit_release'],
    'resources.json': ['parent_enclosure', 'deadlines', 'disk', 'no_oom'],
    'cleanup.json': ['owned_pids_absent', 'owned_cid_absent', 'owned_staging_removed', 'lock_released'],
}
EXCLUDED = ['offline_wallet_fork_agreement', 'rule8_unlock_vectors',
    'pool_supplement_cache_guard_routes', 'projection_controls', 'roots_reorg',
    'foreign_differential', 'backup_corruption', 'full_remaining_matrix']


def empty_rows():
    return {file: {key: {'status': 'NOT_RUN'} for key in keys} for file, keys in REQUIRED.items()}


def verdict(rows):
    states = [rows.get(file, {}).get(key, {}).get('status', 'NOT_RUN')
              for file, keys in REQUIRED.items() for key in keys]
    if 'FAIL' in states:
        return 'FAIL'
    return 'PASS_FUNDED_TWO_PEER_JOURNEY_ONLY' if all(x == 'PASS' for x in states) else 'INCOMPLETE'


def shapes():
    sha = lambda x: type(x) is str and re.fullmatch('[0-9a-f]{64}', x) is not None
    integer = lambda low, high: lambda x: type(x) is int and low <= x <= high
    return dict(
        non_genesis_agreement=dict(count=62, tip_sha256=sha, peers=2),
        restart_catchup=dict(before_count=integer(2, 59), after_count=integer(3, 59),
            changed_process=True, mining_during_restart=True, tip_sha256=sha),
        final_block_72=dict(count=73, block_index=72, peers=2, tip_sha256=sha),
        persisted_height_zero=dict(wallets=2, fresh_process_readback=True),
        coinbase_maturity=dict(block_index=1, amount_atomic=9*ATOMIC, unlock_time=61,
            early_count=60, early_refusal_code=-4, eligible_count=61, after_count=62,
            early_balance_positive=True, early_unlocked_balance=0, early_no_tx_result=True,
            early_unchanged_pool=True, early_unchanged_chain=True, output_lineage_matches=True,
            payment_block_index=61, txid_sha256=sha, fee_atomic=integer(1, 8*ATOMIC-1),
            confirmations=1, peers=2, input_matches_coinbase=True),
        funded_seed_rescan=dict(restore_height=0, payment_block_index=61, amount_atomic=ATOMIC,
            txid_sha256=sha, output_sha256=sha, key_image_sha256=sha,
            identity_matches=True, fresh_process_readback=True),
        received_output_spend=dict(submitted_count=71, block_index=71, confirmed_count=72,
            txid_sha256=sha, amount_atomic=ATOMIC//10, fee_atomic=integer(1, ATOMIC-1),
            input_matches_received=True, input_key_image_sha256=sha, confirmations=1, peers=2),
        private_signer_auth=dict(signers=3, missing_wrong_credentials_rejected=True, restricted=False),
        wrong_network_payment_refusal=dict(code=-2, unchanged_pool=True),
        native_mining_bounds=dict(count=73, transaction_count=2, max_count=MAX_COUNT,
            max_transactions=MAX_TRANSACTIONS, threads=1, light_mode=True,
            external_funding=False, loopback_only=True),
        funded_save_exit_release=dict(daemons=2, wallets=2, forced_kill=False))
