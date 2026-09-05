#!/usr/bin/env python3
"""Candidate M control: apply the Meownero delta to a pristine Monero v0.18.5.1 tree.

Feasibility only, never security (PLAN.md §2.3). Every edit is an exact-string
replacement that fails loudly if the upstream text has drifted, so the script
doubles as a touched-surface inventory. Run: python3 apply.py <monero-src-dir>

Consensus parameters (PLAN.md rev 4 §8.1, §8.2):
  * MEOW_BLOCK_REWARD = 0.9 MEOW per block, perpetual, flat (9e11 atomic @ 12 dp)
  * genesis pays 0 (zero spendable outputs); supply(h) == h * 0.9 MEOW exactly
  * DIFFICULTY_TARGET_V2 = 120 s (inherited unchanged; working value)
  * fresh hard-fork table v1..v16 at heights 1..16 (chain runs v16 rules from height 16)
Network identity: name, ports, network IDs, address prefixes, empty seed lists,
no upstream checkpoints/DNS/update checks.
"""
import re, sys, pathlib

root = pathlib.Path(sys.argv[1])
touched = []

def edit(rel, pairs):
    p = root / rel
    s = p.read_text()
    for old, new in pairs:
        assert s.count(old) == 1, f"{rel}: anchor not unique/missing: {old[:70]!r}"
        s = s.replace(old, new)
    p.write_text(s)
    touched.append(rel)

# ---------------------------------------------------------------- config
edit("src/cryptonote_config.h", [
    ('#define FINAL_SUBSIDY_PER_MINUTE                        ((uint64_t)300000000000) // 3 * pow(10, 11)',
     '#define FINAL_SUBSIDY_PER_MINUTE                        ((uint64_t)300000000000) // 3 * pow(10, 11) (unused by Meownero; kept for upstream diff hygiene)\n'
     '// Meownero: perpetual flat subsidy, 0.9 MEOW per block (PLAN.md rev 4 §8.1). Genesis pays 0.\n'
     '#define MEOW_BLOCK_REWARD                               ((uint64_t)900000000000) // 9 * pow(10, 11) = 0.9 * COIN'),
    ('#define CRYPTONOTE_NAME                         "bitmonero"',
     '#define CRYPTONOTE_NAME                         "meownero"'),
    # mainnet identity
    ('''  uint64_t const CRYPTONOTE_PUBLIC_ADDRESS_BASE58_PREFIX = 18;
  uint64_t const CRYPTONOTE_PUBLIC_INTEGRATED_ADDRESS_BASE58_PREFIX = 19;
  uint64_t const CRYPTONOTE_PUBLIC_SUBADDRESS_BASE58_PREFIX = 42;
  uint16_t const P2P_DEFAULT_PORT = 18080;
  uint16_t const RPC_DEFAULT_PORT = 18081;
  uint16_t const ZMQ_RPC_DEFAULT_PORT = 18082;
  boost::uuids::uuid const NETWORK_ID = { {
      0x12 ,0x30, 0xF1, 0x71 , 0x61, 0x04 , 0x41, 0x61, 0x17, 0x31, 0x00, 0x82, 0x16, 0xA1, 0xA1, 0x10
    } }; // Bender's nightmare
  std::string const GENESIS_TX = "013c01ff0001ffffffffffff03029b2e4c0281c0b02e7c53291a94d1d0cbff8883f8024f5142ee494ffbbd08807121017767aafcde9be00dcfd098715ebcf7f410daebc582fda69d24a28e9d0bc890d1";
  uint32_t const GENESIS_NONCE = 10000;''',
     '''  // Meownero mainnet: single-byte base58 prefixes 120/121/123 -> addresses start with "M" (M5..ME / ME..MQ / Ma..Mj)
  uint64_t const CRYPTONOTE_PUBLIC_ADDRESS_BASE58_PREFIX = 120;
  uint64_t const CRYPTONOTE_PUBLIC_INTEGRATED_ADDRESS_BASE58_PREFIX = 121;
  uint64_t const CRYPTONOTE_PUBLIC_SUBADDRESS_BASE58_PREFIX = 123;
  uint16_t const P2P_DEFAULT_PORT = 19080;
  uint16_t const RPC_DEFAULT_PORT = 19081;
  uint16_t const ZMQ_RPC_DEFAULT_PORT = 19082;
  boost::uuids::uuid const NETWORK_ID = { {
      0x88, 0x7D, 0x7D, 0x6E, 0x82, 0xAB, 0x5C, 0x03, 0x63, 0x92, 0xF4, 0xDB, 0xA8, 0x94, 0x9B, 0x11
    } }; // sha256("meownero-mainnet-network-id-v1")[0:16]
  // Genesis coinbase: v1 tx, unlock 60, txin_gen height 0, ONE OUTPUT OF AMOUNT 0 (zero spendable outputs, PLAN.md §8.2).
  // Output key and tx pubkey are Monero's well-known genesis keys; with amount 0 nothing is claimable.
  std::string const GENESIS_TX = "013c01ff000100029b2e4c0281c0b02e7c53291a94d1d0cbff8883f8024f5142ee494ffbbd08807121017767aafcde9be00dcfd098715ebcf7f410daebc582fda69d24a28e9d0bc890d1";
  uint32_t const GENESIS_NONCE = 90000;'''),
    # testnet identity
    ('''    uint64_t const CRYPTONOTE_PUBLIC_ADDRESS_BASE58_PREFIX = 53;
    uint64_t const CRYPTONOTE_PUBLIC_INTEGRATED_ADDRESS_BASE58_PREFIX = 54;
    uint64_t const CRYPTONOTE_PUBLIC_SUBADDRESS_BASE58_PREFIX = 63;
    uint16_t const P2P_DEFAULT_PORT = 28080;
    uint16_t const RPC_DEFAULT_PORT = 28081;
    uint16_t const ZMQ_RPC_DEFAULT_PORT = 28082;
    boost::uuids::uuid const NETWORK_ID = { {
        0x12 ,0x30, 0xF1, 0x71 , 0x61, 0x04 , 0x41, 0x61, 0x17, 0x31, 0x00, 0x82, 0x16, 0xA1, 0xA1, 0x11
      } }; // Bender's daydream
    std::string const GENESIS_TX = "013c01ff0001ffffffffffff03029b2e4c0281c0b02e7c53291a94d1d0cbff8883f8024f5142ee494ffbbd08807121017767aafcde9be00dcfd098715ebcf7f410daebc582fda69d24a28e9d0bc890d1";
    uint32_t const GENESIS_NONCE = 10001;''',
     '''    // Meownero testnet: two-byte prefixes 156/157/158 -> "T6.." / "TG.." / "TR.."
    uint64_t const CRYPTONOTE_PUBLIC_ADDRESS_BASE58_PREFIX = 156;
    uint64_t const CRYPTONOTE_PUBLIC_INTEGRATED_ADDRESS_BASE58_PREFIX = 157;
    uint64_t const CRYPTONOTE_PUBLIC_SUBADDRESS_BASE58_PREFIX = 158;
    uint16_t const P2P_DEFAULT_PORT = 29080;
    uint16_t const RPC_DEFAULT_PORT = 29081;
    uint16_t const ZMQ_RPC_DEFAULT_PORT = 29082;
    boost::uuids::uuid const NETWORK_ID = { {
        0x36, 0xA4, 0xBF, 0x5F, 0xA0, 0x1C, 0xA0, 0xB6, 0xC3, 0xBB, 0x7F, 0x95, 0x06, 0xD1, 0x40, 0x53
      } }; // sha256("meownero-testnet-network-id-v1")[0:16]
    std::string const GENESIS_TX = "013c01ff000100029b2e4c0281c0b02e7c53291a94d1d0cbff8883f8024f5142ee494ffbbd08807121017767aafcde9be00dcfd098715ebcf7f410daebc582fda69d24a28e9d0bc890d1";
    uint32_t const GENESIS_NONCE = 90001;'''),
])

# stagenet identity (its upstream GENESIS_TX differs from mainnet's, so match the block by regex)
p = root / "src/cryptonote_config.h"
s = p.read_text()
m = re.search(r'  namespace stagenet\n  \{\n(.*?)\n  \}\n', s, re.S)
assert m, "stagenet block"
stagenet = '''    // Meownero stagenet: two-byte prefixes 150/151/152 -> "S6.." / "SF.." / "SR.."
    uint64_t const CRYPTONOTE_PUBLIC_ADDRESS_BASE58_PREFIX = 150;
    uint64_t const CRYPTONOTE_PUBLIC_INTEGRATED_ADDRESS_BASE58_PREFIX = 151;
    uint64_t const CRYPTONOTE_PUBLIC_SUBADDRESS_BASE58_PREFIX = 152;
    uint16_t const P2P_DEFAULT_PORT = 39080;
    uint16_t const RPC_DEFAULT_PORT = 39081;
    uint16_t const ZMQ_RPC_DEFAULT_PORT = 39082;
    boost::uuids::uuid const NETWORK_ID = { {
        0x9E, 0x6E, 0x05, 0x5F, 0x00, 0xF0, 0xAC, 0x1B, 0xD8, 0xCA, 0x74, 0x90, 0xF0, 0xA4, 0x25, 0x2A
      } }; // sha256("meownero-stagenet-network-id-v1")[0:16]
    std::string const GENESIS_TX = "013c01ff000100029b2e4c0281c0b02e7c53291a94d1d0cbff8883f8024f5142ee494ffbbd08807121017767aafcde9be00dcfd098715ebcf7f410daebc582fda69d24a28e9d0bc890d1";
    uint32_t const GENESIS_NONCE = 90002;'''
assert "CRYPTONOTE_PUBLIC_ADDRESS_BASE58_PREFIX = 24;" in m.group(1)
s = s[:m.start(1)] + stagenet + s[m.end(1):]
p.write_text(s)

# ---------------------------------------------------------------- emission
edit("src/cryptonote_basic/cryptonote_basic_impl.cpp", [
    ('''    const int target = version < 2 ? DIFFICULTY_TARGET_V1 : DIFFICULTY_TARGET_V2;
    const int target_minutes = target / 60;
    const int emission_speed_factor = EMISSION_SPEED_FACTOR_PER_MINUTE - (target_minutes-1);

    uint64_t base_reward = (MONEY_SUPPLY - already_generated_coins) >> emission_speed_factor;
    if (base_reward < FINAL_SUBSIDY_PER_MINUTE*target_minutes)
    {
      base_reward = FINAL_SUBSIDY_PER_MINUTE*target_minutes;
    }
''',
     '''    // Meownero: perpetual flat subsidy. Independent of already_generated_coins, hard-fork
    // version, and target spacing (PLAN.md rev 4 §8.1). The block-weight penalty below is
    // retained unchanged and is denominated in this constant.
    (void)already_generated_coins;
    uint64_t base_reward = MEOW_BLOCK_REWARD;
'''),
])

# genesis pays nothing: block template side ...
edit("src/cryptonote_core/cryptonote_tx_utils.cpp", [
    ('''    uint64_t block_reward;
    if(!get_block_reward(median_weight, current_block_weight, already_generated_coins, block_reward, hard_fork_version))
    {
      LOG_PRINT_L0("Block is too big");
      return false;
    }
''',
     '''    uint64_t block_reward;
    if(!get_block_reward(median_weight, current_block_weight, already_generated_coins, block_reward, hard_fork_version))
    {
      LOG_PRINT_L0("Block is too big");
      return false;
    }
    // Meownero: the genesis block pays nothing (zero spendable outputs, PLAN.md §8.2),
    // so cumulative supply at height h is exactly h * MEOW_BLOCK_REWARD.
    if (height == 0)
      block_reward = 0;
'''),
])
# ... and validation side
edit("src/cryptonote_core/blockchain.cpp", [
    ('''  if (!get_block_reward(median_weight, cumulative_block_weight, already_generated_coins, base_reward, version))
  {
    MERROR_VER("block weight " << cumulative_block_weight << " is bigger than allowed for this blockchain");
    return false;
  }
  if(base_reward + fee < money_in_use)''',
     '''  if (!get_block_reward(median_weight, cumulative_block_weight, already_generated_coins, base_reward, version))
  {
    MERROR_VER("block weight " << cumulative_block_weight << " is bigger than allowed for this blockchain");
    return false;
  }
  // Meownero: genesis subsidy is 0 by consensus (mirrors construct_miner_tx).
  if (get_block_height(b) == 0)
    base_reward = 0;
  if(base_reward + fee < money_in_use)'''),
])

# ---------------------------------------------------------------- hard forks
p = root / "src/hardforks/hardforks.cpp"
s = p.read_text()
start = s.index("const hardfork_t mainnet_hard_forks[] = {")
end = s.index("const uint64_t mainnet_hard_fork_version_1_till = 1009826;")
table = "const hardfork_t mainnet_hard_forks[] = {\n  // Meownero: fresh chain. Genesis is v1; every upstream rule set activates one block apart so the\n  // chain runs current (v16) consensus from height 16. Times are 2026-09-05 UTC + version, strictly increasing.\n"
for v in range(1, 17):
    table += f"  {{ {v}, {v}, 0, {1757030400 + v} }},\n"
table += "};\nconst size_t num_mainnet_hard_forks = sizeof(mainnet_hard_forks) / sizeof(mainnet_hard_forks[0]);\n"
s = s[:start] + table + "const uint64_t mainnet_hard_fork_version_1_till = 1;" + s[end + len("const uint64_t mainnet_hard_fork_version_1_till = 1009826;"):]
p.write_text(s); touched.append("src/hardforks/hardforks.cpp")

# ---------------------------------------------------------------- checkpoints: none inherited
p = root / "src/checkpoints/checkpoints.cpp"
s = p.read_text()
a = s.index('    ADD_CHECKPOINT2(1,     "771fbcd656ec1464d3a02ead5e18644030007a0fc664c0a964d30922821a8148", "0x2");')
b = s.index("    return true;\n  }\n", a)
s = s[:a] + "    // Meownero: no inherited mainnet checkpoints (fresh chain).\n" + s[b:]
# testnet/stagenet lists are Monero's; blank them too
s = re.sub(r'(if \(nettype == TESTNET\)\n    \{\n)(?:.*?\n)*?(      return true;)', r'\1      // Meownero: none\n\2', s, count=1)
s = re.sub(r'(if \(nettype == STAGENET\)\n    \{\n)(?:.*?\n)*?(      return true;)', r'\1      // Meownero: none\n\2', s, count=1)
old = "  bool checkpoints::load_checkpoints_from_dns(network_type nettype)\n  {\n    std::vector<std::string> records;\n"
assert s.count(old) == 1
s = s.replace(old, old + "    // Meownero: no DNS checkpoint authority exists; upstream MoneroPulse records must never be consulted.\n    (void)nettype; return true;\n")
p.write_text(s); touched.append("src/checkpoints/checkpoints.cpp")

# embedded block-hash blobs are Monero's chain: disable
edit("src/blocks/blocks.cpp", [
    ('''    {cryptonote::network_type::MAINNET, {checkpoints, checkpoints_len}},
    {cryptonote::network_type::STAGENET, {stagenet_blocks, stagenet_blocks_len}},
    {cryptonote::network_type::TESTNET, {testnet_blocks, testnet_blocks_len}}
  };''',
     '''    // Meownero: no embedded block-hash blobs (they describe Monero's chain).
  };'''),
])

# ---------------------------------------------------------------- seeds: none hardcoded
edit("src/p2p/net_node.inl", [
    ('''    else
    {
      full_addrs.insert("176.9.0.187:18080");
      full_addrs.insert("88.198.163.90:18080");
      full_addrs.insert("192.99.8.110:18080");
      full_addrs.insert("37.187.74.171:18080");
      full_addrs.insert("88.99.195.15:18080");
      full_addrs.insert("5.104.84.64:18080");
    }
    return full_addrs;''',
     '''    else
    {
      // Meownero: no hardcoded mainnet seeds yet; operators pass --seed-node / --add-peer (PLAN.md §9.5 seed policy TBD).
    }
    return full_addrs;'''),
    ('''    if (m_nettype == cryptonote::TESTNET)
    {
      full_addrs.insert("176.9.0.187:28080");
      full_addrs.insert("192.99.8.110:28080");
      full_addrs.insert("37.187.74.171:28080");
      full_addrs.insert("88.99.195.15:28080");
      full_addrs.insert("5.104.84.64:28080");
    }
    else if (m_nettype == cryptonote::STAGENET)
    {
      full_addrs.insert("176.9.0.187:38080");
      full_addrs.insert("192.99.8.110:38080");
      full_addrs.insert("37.187.74.171:38080");
      full_addrs.insert("88.99.195.15:38080");
      full_addrs.insert("5.104.84.64:38080");
    }''',
     '''    if (m_nettype == cryptonote::TESTNET)
    {
      // Meownero: none
    }
    else if (m_nettype == cryptonote::STAGENET)
    {
      // Meownero: none
    }'''),
])
p = root / "src/p2p/net_node.inl"
s = p.read_text()
s = re.sub(r'(case epee::net_utils::zone::tor:\n      if \(m_nettype == cryptonote::MAINNET\)\n      \{\n        return \{\n)(?:.*?\n)*?(        \};)', r'\1          // Meownero: none\n\2', s, count=1)
s = re.sub(r'(case epee::net_utils::zone::i2p:\n      if \(m_nettype == cryptonote::MAINNET\)\n      \{\n        return \{\n)(?:.*?\n)*?(        \};)', r'\1          // Meownero: none\n\2', s, count=1)
p.write_text(s)
# DNS seed hostnames list lives in the header
p = root / "src/p2p/net_node.h"
s = p.read_text()
m = re.search(r'const std::vector<std::string> m_seed_nodes_list =\s*\{[^}]*\};', s)
assert m, "seed list anchor"
s = s[:m.start()] + "const std::vector<std::string> m_seed_nodes_list = { /* Meownero: no DNS seed hostnames */ };" + s[m.end():]
p.write_text(s); touched.append("src/p2p/net_node.h")

# ---------------------------------------------------------------- update checks off by default
edit("src/cryptonote_core/cryptonote_core.cpp", [
    ('''    "check-updates"
  , "Check for new versions of monero: [disabled|notify|download|update]"
  , "notify"''',
     '''    "check-updates"
  , "Check for new versions: [disabled|notify|download|update] (Meownero: no update authority; default disabled)"
  , "disabled"'''),
])

print("touched:")
for t in touched:
    print("  ", t)
