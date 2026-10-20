#!/usr/bin/env python3
"""Prepare a source-bound TESTNET 9/90 overlay. Never build or launch a node."""
import argparse
import difflib
import json
from pathlib import Path
import re
import subprocess
import sys

import network as n

BINDINGS = n.HERE / 'policy-bindings.json'


def replace(text, old, new, count=1):
    n.require(text.count(old) == count, 'changed or ambiguous policy anchor: ' + old)
    return text.replace(old, new)


def checked_source(source):
    originals = n.checked_source(source)
    binding = n.read_json(BINDINGS)
    n.require(binding['upstream_commit'] == n.read_json(n.HERE / 'source-bindings.json')['upstream_commit'],
              'foreign policy source binding')
    for name, digest in binding['files'].items():
        path = Path(source) / name
        n.require(not path.is_symlink(), 'symlinked policy source: ' + name)
        raw = path.read_bytes()
        n.require(n.sha(raw) == digest, 'changed policy source: ' + name)
        committed = subprocess.check_output(['git', '-C', str(source), 'show',
            binding['upstream_commit'] + ':' + name], timeout=10)
        n.require(raw == committed, 'policy source differs from pinned Git object: ' + name)
        originals[name] = raw
    return originals


def changes(originals, value):
    p = value['consensus_proposal']
    n.require((p['reward_atomic'], p['target_seconds']) == (9000000000000, 90),
              'only the settled selected 9/90 policy is implemented')
    result = n.genesis_admission_changes(originals)
    config = 'src/cryptonote_config.h'
    text = n.identity_overlay(originals[config], value).decode()
    start = text.index('  namespace testnet\n')
    end = text.index('  namespace stagenet\n', start)
    section, count = re.subn(r'(GENESIS_TX = ")[0-9a-f]+(";)',
        lambda m: m[1] + n.native_recipe(value)['genesis_tx_hex'] + m[2], text[start:end])
    n.require(count == 1, 'ambiguous TESTNET genesis')
    section = replace(section, '  namespace testnet\n  {\n',
        '  namespace testnet\n  {\n'
        '    // Dedicated valueless profile; fallback requires a separate reviewed network.\n'
        '    constexpr uint64_t MEOWNERO_BLOCK_REWARD = 9000000000000;\n'
        '    constexpr uint64_t MEOWNERO_TARGET_SECONDS = 90;\n')
    result[config] = (text[:start] + section + text[end:]).encode()

    name = 'src/cryptonote_basic/cryptonote_basic_impl.h'
    text = originals[name].decode()
    text = replace(text, 'uint64_t &reward, uint8_t version);',
                   'uint64_t &reward, uint8_t version, network_type nettype = MAINNET);')
    text = replace(text, '  size_t get_max_tx_size();',
        '  size_t get_max_tx_size();\n'
        '  uint64_t get_difficulty_target(network_type nettype, uint8_t version);')
    result[name] = text.encode()

    name = 'src/cryptonote_basic/cryptonote_basic_impl.cpp'
    text = originals[name].decode()
    text = replace(text, 'uint64_t &reward, uint8_t version) {',
                   'uint64_t &reward, uint8_t version, network_type nettype) {')
    start = text.index('    const int target = version < 2 ?')
    end = text.index('\n\n    uint64_t full_reward_zone', start)
    original_emission = replace(text[start:end], 'uint64_t base_reward =', 'base_reward =')
    text = text[:start] + '''    uint64_t base_reward;
    if (nettype == TESTNET)
      base_reward = config::testnet::MEOWNERO_BLOCK_REWARD;
    else
    {
''' + '\n'.join('  ' + line if line else '' for line in original_emission.splitlines()) + '''
    }''' + text[end:]
    anchor = '  bool get_block_reward('
    target = '''  uint64_t get_difficulty_target(network_type nettype, uint8_t version)
  {
    if (nettype == TESTNET)
      return config::testnet::MEOWNERO_TARGET_SECONDS;
    return version < 2 ? DIFFICULTY_TARGET_V1 : DIFFICULTY_TARGET_V2;
  }
  //-----------------------------------------------------------------------------------------------
'''
    text = replace(text, anchor, target + anchor)
    result[name] = text.encode()

    # Default MAINNET preserves existing upstream test/helper call semantics.
    # Every production reward/constructor caller below supplies its real selector.
    name = 'src/cryptonote_core/cryptonote_tx_utils.h'
    result[name] = replace(originals[name].decode(), 'uint8_t hard_fork_version = 1);',
        'uint8_t hard_fork_version = 1, network_type nettype = MAINNET);').encode()
    name = 'src/cryptonote_core/cryptonote_tx_utils.cpp'
    text = replace(originals[name].decode(), 'uint8_t hard_fork_version) {',
                   'uint8_t hard_fork_version, network_type nettype) {')
    text = replace(text, 'block_reward, hard_fork_version))', 'block_reward, hard_fork_version, nettype))')
    # Genesis construction returns the already-bound native recipe, with one
    # output. Never infer height zero from the generated-coins balance.
    text = replace(text, '    uint64_t block_reward;\n', '''    if (nettype == TESTNET && height == 0)
    {
      CHECK_AND_ASSERT_MES(fee == 0, false, "genesis cannot collect fees");
      blobdata genesis;
      CHECK_AND_ASSERT_MES(epee::string_tools::parse_hexstr_to_binbuff(get_config(TESTNET).GENESIS_TX, genesis),
        false, "invalid configured TESTNET genesis encoding");
      return parse_and_validate_tx_from_blob(genesis, tx);
    }

    uint64_t block_reward;
''')
    result[name] = text.encode()

    name = 'src/cryptonote_core/blockchain.h'
    result[name] = replace(originals[name].decode(), '    uint64_t get_difficulty_target() const;',
        '    uint64_t get_difficulty_target() const;\n'
        '    network_type get_nettype() const { return m_nettype; }').encode()
    name = 'src/cryptonote_core/blockchain.cpp'
    text = result[name].decode()
    for old in ('base_reward, version))', 'b.miner_tx, ex_nonce, max_outs, hf_version);'):
        new = old.replace('version))', 'version, m_nettype))') if old.startswith('base') else old.replace('hf_version);', 'hf_version, m_nettype);')
        text = replace(text, old, new, 3 if old.startswith('base') else 2)
    for version in ('get_ideal_hard_fork_version(height)', 'get_ideal_hard_fork_version(bei.height)',
                    'get_current_hard_fork_version()'):
        text = replace(text, version + ' < 2 ? DIFFICULTY_TARGET_V1 : DIFFICULTY_TARGET_V2',
                       'cryptonote::get_difficulty_target(m_nettype, ' + version + ')')
    text = replace(text, '(get_current_hard_fork_version() < 2 ? CRYPTONOTE_LOCKED_TX_ALLOWED_DELTA_SECONDS_V1 : CRYPTONOTE_LOCKED_TX_ALLOWED_DELTA_SECONDS_V2)',
        '(get_difficulty_target() * CRYPTONOTE_LOCKED_TX_ALLOWED_DELTA_BLOCKS)')
    text = replace(text, ' * DIFFICULTY_TARGET_V2 / 2;', ' * get_difficulty_target() / 2;')
    text = replace(text, 'timestamps.back() + DIFFICULTY_TARGET_V2;', 'timestamps.back() + get_difficulty_target();')
    result[name] = text.encode()
    name = 'src/cryptonote_core/tx_pool.cpp'
    text = originals[name].decode()
    for reward in ('best_coinbase', 'block_reward'):
        text = replace(text, reward + ', version))', reward + ', version, m_blockchain.get_nettype()))')
    result[name] = text.encode()
    name = 'src/rpc/core_rpc_server.cpp'
    text = replace(originals[name].decode(),
        'm_core.get_blockchain_storage().get_current_hard_fork_version() < 2 ? DIFFICULTY_TARGET_V1 : DIFFICULTY_TARGET_V2',
        'm_core.get_blockchain_storage().get_difficulty_target()')
    result[name] = text.encode()
    return result


def prepare(source, out, value):
    originals = checked_source(source)
    changed = changes(originals, value)
    patch = ''.join(''.join(difflib.unified_diff(
        originals[name].decode().splitlines(True), raw.decode().splitlines(True),
        fromfile='a/' + name, tofile='b/' + name, n=3)) for name, raw in sorted(changed.items()))
    receipt = {'schema': 'meownero-vanguard-selected-policy-overlay/1',
        'result': 'PREPARED_NOT_NATIVE_VERIFIED', 'launch_ready': False,
        'profile_sha256': n.profile_hash(value), 'upstream_commit': value['upstream_commit'],
        'source_lock_sha256': value['source_lock_sha256'],
        'overlay_id': n.sha(patch.encode()),
        'files': {name: {'original_sha256': n.sha(originals[name]), 'changed_sha256': n.sha(raw)}
                  for name, raw in sorted(changed.items())},
        'policy': {'selector': 'TESTNET', 'reward_atomic': 9000000000000, 'target_seconds': 90,
                   'fallback_enabled': False, 'genesis_height': 0, 'genesis_reward_atomic': 0},
        'native_policy': 'NOT_RUN', 'native_network_separation': 'NOT_RUN',
        'remaining': ['native-policy-construction-and-validation', 'native-height-one-maturity-payment',
                      'timestamp-lock-conversion-review', 'wallet-target-and-fork-integration',
                      'native-peer-bootstrap-persistence-recovery', 'independent-core-security-acceptance']}
    out = n.fresh_directory(out)
    (out / 'selected-9-90.patch').write_text(patch)
    n.write_json(out / 'policy-overlay.json', receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.source, args.out, n.profile()), indent=2))
        return 0
    except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print('REFUSED: ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
