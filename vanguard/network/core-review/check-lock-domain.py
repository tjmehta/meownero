#!/usr/bin/env python3
"""Read-only pinned-source and arithmetic evidence for the Core consultation.

Does not compile C++, run consensus/wallet code, or prove native acceptance.
"""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import policy

PIN = 'e151643c5269c83bf24a83b2548e2493876026b2'
CANDIDATE = 'ebb953530ecfc3bf712e9cb08e042cf11b7f272c'
OVERLAY = '0f971c34e3401f2faf85fa98862f7f28698af3b5ee28765c17657f8bee5eb044'
PATHS = [
    'src/cryptonote_config.h',
    'src/hardforks/hardforks.cpp',
    'src/cryptonote_basic/cryptonote_format_utils.cpp',
    'src/cryptonote_basic/cryptonote_format_utils.h',
    'src/cryptonote_core/tx_verification_utils.cpp',
    'src/cryptonote_core/tx_verification_utils.h',
    'src/cryptonote_core/blockchain.cpp',
    'src/cryptonote_core/tx_pool.cpp',
    'src/blockchain_db/blockchain_db.cpp',
    'src/blockchain_db/lmdb/db_lmdb.cpp',
    'src/wallet/wallet2.cpp',
    'src/wallet/tx_builder.cpp',
    'src/wallet/wallet_rpc_server.cpp',
    'src/wallet/pending_tx_validation.cpp',
    'src/carrot_impl/format_utils.cpp',
    'contrib/epee/include/misc_language.h',
]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def source_rule_present(text):
    rule = text.split('// Rule 8\n', 1)[1].split('// Rule 9\n', 1)[0]
    return all(part in rule for part in [
        'hf_version >= HF_VERSION_REJECT_UNLOCK_TIME && tx.unlock_time != 0',
        'tvc.m_verifivation_failed = true;', 'tvc.m_nonzero_unlock_time = true;',
        'return false;',
    ])


def adjusted(timestamps, target):
    # The pinned median sorts its vector in place, before timestamps.back().
    ordered = sorted(timestamps)
    median = (ordered[29] + ordered[30]) // 2
    return min(median + 61 * target // 2, ordered[-1] + target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    sources = {}
    bindings = {}
    for name in PATHS:
        raw = subprocess.check_output(['git', '-C', str(args.source), 'show', PIN + ':' + name], timeout=10)
        require((args.source / name).read_bytes() == raw, 'source drift: ' + name)
        sources[name] = raw.decode()
        bindings[name] = hashlib.sha256(raw).hexdigest()

    originals = policy.checked_source(args.source)
    changed = policy.changes(originals, policy.n.profile())
    patch = ''.join(''.join(difflib.unified_diff(
        originals[name].decode().splitlines(True), raw.decode().splitlines(True),
        fromfile='a/' + name, tofile='b/' + name, n=3)) for name, raw in sorted(changed.items()))
    require(hashlib.sha256(patch.encode()).hexdigest() == OVERLAY, 'overlay drift')
    config = sources['src/cryptonote_config.h']
    require('#define HF_VERSION_REJECT_UNLOCK_TIME           17' in config, 'fork threshold drift')
    verifier = sources['src/cryptonote_core/tx_verification_utils.cpp']
    require(source_rule_present(verifier), 'missing upstream nonzero-unlock rule')
    known_bad = verifier.replace('tx.unlock_time != 0', 'false', 1)
    require(not source_rule_present(known_bad), 'known-bad missing-rule control passed')
    require('src/cryptonote_core/tx_verification_utils.cpp' not in changed, 'verifier changed')
    require('src/cryptonote_basic/cryptonote_format_utils.cpp' not in changed, 'mapping changed')
    require('{ 18, 1, 0, 1341378001 }' in changed['src/hardforks/hardforks.cpp'].decode(), 'activation drift')
    wallet_rpc = sources['src/wallet/wallet_rpc_server.cpp']
    require(wallet_rpc.count('if (req.unlock_time)') == 4, 'wallet request guard drift')
    require('tx.unlock_time = 0;' in sources['src/carrot_impl/format_utils.cpp'], 'CARROT construction drift')

    unlock_values = [0, 1, 499999999, 500000000, 1656629117, 1656629118,
                     1656629119, 1700000000, 18446744073709551615]
    # These are explicit acceptance expectations, not native verifier results.
    domain = [{'unlock_time': u, 'v18_rule8_rejects': u != 0} for u in unlock_values]
    ages = [{'created_index': h, 'ordinary_unlock_time': 0,
             'ordinary_last_locked_index': h + 9, 'ordinary_wallet_height': h + 10,
             'coinbase_unlock_time': h + 60, 'coinbase_last_locked_index': h + 59,
             'coinbase_wallet_height': h + 60} for h in [0, 1, 49, 50, 59, 60, 255]]
    rows = []
    for target in [90, 120]:
        timestamps = [1700000000 + i * target for i in range(60)]
        result = adjusted(timestamps, target)
        require(result == 1700000000 + 60 * target, 'regular projection error')
        require(adjusted(timestamps[1:] + timestamps[:1], target) == result, 'median sorting error')
        rows.append({'target': target, 'regular_adjusted_time': result,
                     'rotated_window_adjusted_time': result})
    require(adjusted([1700000000] * 60, 90) == 1700000090, 'flat window error')
    require(adjusted([1700000000] * 59 + [1700001000], 90) == 1700001090, 'maximum timestamp branch error')
    require(adjusted([1700000000] * 59 + [1700010000], 90) == 1700002745, 'median branch error')
    foreign_window = [1700000000 + i * 60 for i in range(60)]
    foreign_before, foreign_after = adjusted(foreign_window, 120), adjusted(foreign_window, 60)
    require(foreign_before == 1700003660 and foreign_after == 1700003600, 'foreign v1 regression expectation error')
    receipt = {
        'schema': 'meownero-core-lock-consultation/1', 'candidate': CANDIDATE,
        'upstream_commit': PIN, 'overlay_sha256': OVERLAY,
        'result': 'PASS_SOURCE_AND_ARITHMETIC_ONLY', 'native_execution': 'NOT_RUN',
        'source_bindings': bindings, 'known_bad_rule_removal_detected': True,
        'v18_unlock_domain_expectations': domain, 'height_lock_arithmetic': ages,
        'regular_projection_arithmetic': rows,
        'flat_projection_90': 1700000090,
        'maximum_branch_projection_90': 1700001090,
        'median_branch_projection_90': 1700002745,
        'foreign_v1_adjusted_time_regression': {'upstream': foreign_before, 'overlay': foreign_after},
        'coinbase_height_domain': {'last_height_before_timestamp_interpretation': 499999939,
                                   'first_height_requiring_separate_review': 499999940},
        'limits': ['No compiled verifier, wallet, proof, DB or P2P execution.',
                   'Expectation rows do not claim whole-transaction acceptance.',
                   'Source inspection is scoped to the listed files, not full-tree provenance.'],
    }
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
