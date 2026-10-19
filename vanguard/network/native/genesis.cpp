// Public, zero-value fixture recipe approved for implementation in consultation
// 3b6c0197-43f9-4c30-a90c-399f82fc0b57. This is not a wallet or signing key.
// API/serialization source: seraphis-migration/monero at
// e151643c5269c83bf24a83b2548e2493876026b2, src/crypto/crypto.{h,cpp},
// src/cryptonote_core/{cryptonote_tx_utils,tx_verification_utils}.cpp,
// src/cryptonote_basic/cryptonote_format_utils.cpp and src/ringct/rctSigs.cpp.
// This helper never opens a database, starts a daemon or admits a block.
#include "crypto/crypto.h"
#include "common/util.h"
#include "cryptonote_basic/cryptonote_format_utils.h"
#include "cryptonote_core/cryptonote_tx_utils.h"
#include "cryptonote_core/tx_verification_utils.h"
#include "fcmp_pp/curve_trees.h"
#include "ringct/rctSigs.h"
#include "string_tools.h"

#include <functional>
#include <iostream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <vector>

namespace
{
void require(bool condition, const char *message)
{
  if (!condition) throw std::runtime_error(message);
}

// The three public recovery inputs are canonical little-endian scalars 1,2,3.
// generate_keys(recover=true) uses the pinned native scalar reduction/basepoint
// path. No random key, owner seed or release signing material is accessed.
void public_fixture_key(unsigned char number, crypto::public_key &pub, crypto::secret_key &sec)
{
  crypto::secret_key recovery{};
  static_assert(sizeof(recovery) == 32);
  reinterpret_cast<unsigned char *>(&recovery)[0] = number;
  crypto::generate_keys(pub, sec, recovery, true);
  require(sec == recovery, "public recovery scalar changed");
  require(crypto::check_key(pub), "public fixture key cannot decode");
  require(rct::verPointsForTorsion({rct::pk2rct(pub)}), "public fixture key has torsion");
}

rct::key point(const std::string &hex)
{
  rct::key result{};
  require(epee::string_tools::hex_to_pod(hex, result), "bad negative fixture encoding");
  return result;
}
}

int main()
{
  try
  {
    tools::set_max_concurrency(1);
    crypto::public_key spend_pub{}, view_pub{}, tx_pub{}, output_pub{};
    crypto::secret_key spend_sec{}, view_sec{}, tx_sec{};
    public_fixture_key(1, spend_pub, spend_sec);
    public_fixture_key(2, view_pub, view_sec);
    public_fixture_key(3, tx_pub, tx_sec);
    crypto::key_derivation derivation{};
    require(crypto::generate_key_derivation(view_pub, tx_sec, derivation), "native derivation failed");
    require(crypto::derive_public_key(derivation, 0, spend_pub, output_pub), "native output derivation failed");
    require(crypto::check_key(output_pub), "output key cannot decode");

    // Ordinary construct_miner_tx(v1, reward0) decomposes to no outputs and
    // chooses tx v1. Explicitly build this height-zero-only fixture instead.
    cryptonote::transaction tx{};
    tx.version = 2;
    tx.unlock_time = CRYPTONOTE_MINED_MONEY_UNLOCK_WINDOW;
    tx.vin.push_back(cryptonote::txin_gen{0});
    cryptonote::tx_out out{};
    out.amount = 0;
    out.target = cryptonote::txout_to_key{output_pub};
    tx.vout.push_back(out);
    require(cryptonote::add_tx_pub_key_to_extra(tx, tx_pub), "native extra failed");
    tx.rct_signatures.type = rct::RCTTypeNull;
    tx.invalidate_hashes();
    const auto blob = cryptonote::tx_to_blob(tx);
    cryptonote::transaction parsed{};
    require(cryptonote::parse_and_validate_tx_from_blob(blob, parsed), "native transaction parse failed");
    require(cryptonote::tx_to_blob(parsed) == blob, "native transaction roundtrip differs");
    require(parsed.version == 2 && parsed.rct_signatures.type == rct::RCTTypeNull &&
            parsed.vin.size() == 1 && parsed.vin[0].type() == typeid(cryptonote::txin_gen) &&
            boost::get<cryptonote::txin_gen>(parsed.vin[0]).height == 0 &&
            parsed.unlock_time == 60 && parsed.vout.size() == 1 &&
            parsed.vout[0].amount == 0 && parsed.vout[0].target.type() == typeid(cryptonote::txout_to_key),
            "native genesis transaction shape differs");
    require(cryptonote::get_tx_pub_key_from_extra(parsed) == tx_pub, "native extra key differs");

    std::unordered_map<uint64_t, rct::key> amounts;
    cryptonote::collect_transparent_amount_commitments({std::cref(parsed)}, amounts);
    const auto G = point("5866666666666666666666666666666666666666666666666666666666666666");
    require(amounts.size() == 1 && amounts.at(0) == G, "native amount-zero map entry is not G");
    rct::key commitment{};
    require(cryptonote::get_commitment(parsed, 0, amounts, commitment) && commitment == G,
            "native coinbase commitment is not G");
    std::vector<rct::key> collected;
    require(cryptonote::collect_pubkeys_and_commitments(parsed, amounts, collected) && collected.size() == 2,
            "native output/commitment collection failed");
    require(rct::verPointsForTorsion(collected), "native genesis output/commitment has torsion");
    const auto identity = point("0100000000000000000000000000000000000000000000000000000000000000");
    const auto small_order = point(std::string(64, '0'));
    const auto malformed = point(std::string(64, 'f'));
    // Valid curve encoding with torsion, inherited historical genesis key.
    // It is a rejection control only and never used to construct the new tx.
    const auto historical = point("9b2e4c0281c0b02e7c53291a94d1d0cbff8883f8024f5142ee494ffbbd088071");
    require(crypto::check_key(rct::rct2pk(historical)), "torsion control cannot decode");
    for (const auto &bad : {identity, small_order, malformed, historical})
    {
      require(!rct::verPointsForTorsion({bad, commitment}), "bad output accepted by native torsion helper");
      require(!rct::verPointsForTorsion({rct::pk2rct(output_pub), bad}), "bad commitment accepted by native torsion helper");
    }
    fcmp_pp::LegacyOutputPair pair;
    pair.output_pubkey = output_pub;
    pair.commitment = rct::rct2pt(commitment);
    const auto leaf = fcmp_pp::curve_trees::output_to_tuple(pair);

    // Use the native genesis builder, including its actual nonce selection.
    // Its pinned block versions are v1/0, not the v18 activation at height one.
    cryptonote::block block{};
    const auto tx_hex = epee::string_tools::buff_to_hex_nodelimer(blob);
    require(cryptonote::generate_genesis_block(block, tx_hex, 424001), "native genesis builder failed");
    require(block.major_version == 1 && block.minor_version == 0 && block.timestamp == 0 &&
            block.prev_id == crypto::null_hash && block.tx_hashes.empty(), "genesis header shape differs");
    const auto block_blob = cryptonote::block_to_blob(block);
    cryptonote::block parsed_block{};
    require(cryptonote::parse_and_validate_block_from_blob(block_blob, parsed_block), "native block parse failed");
    require(cryptonote::block_to_blob(parsed_block) == block_blob &&
            cryptonote::get_block_hash(parsed_block) == cryptonote::get_block_hash(block), "native block roundtrip differs");

    std::cout << "{\n  \"schema\":\"meownero-vanguard-native-genesis-recipe/1\",\n"
      << "  \"result\":\"PASS_NATIVE_RECIPE_HELPERS_ONLY\",\n"
      << "  \"testnet_admission\":\"NOT_RUN\",\n  \"persisted_commitment_and_tree_root\":\"NOT_RUN\",\n"
      << "  \"upstream_commit\":\"e151643c5269c83bf24a83b2548e2493876026b2\",\n"
      << "  \"public_recovery_scalars_le\":[1,2,3],\n"
      << "  \"spend_public_key\":\"" << epee::string_tools::pod_to_hex(spend_pub) << "\",\n"
      << "  \"view_public_key\":\"" << epee::string_tools::pod_to_hex(view_pub) << "\",\n"
      << "  \"tx_public_key\":\"" << epee::string_tools::pod_to_hex(tx_pub) << "\",\n"
      << "  \"output_public_key\":\"" << epee::string_tools::pod_to_hex(output_pub) << "\",\n"
      << "  \"amount_zero_commitment\":\"" << epee::string_tools::pod_to_hex(commitment) << "\",\n"
      << "  \"legacy_leaf_O_I_C\":\"" << epee::string_tools::pod_to_hex(leaf) << "\",\n"
      << "  \"genesis_tx_hex\":\"" << tx_hex << "\",\n"
      << "  \"genesis_tx_hash\":\"" << epee::string_tools::pod_to_hex(cryptonote::get_transaction_hash(parsed)) << "\",\n"
      << "  \"genesis_block_hex\":\"" << epee::string_tools::buff_to_hex_nodelimer(block_blob) << "\",\n"
      << "  \"genesis_block_hash\":\"" << epee::string_tools::pod_to_hex(cryptonote::get_block_hash(block)) << "\",\n"
      << "  \"actual_nonce\":" << block.nonce << ",\n"
      << "  \"helper_controls\":{\"valid_pair\":true,\"identity\":false,\"small_order\":false,\"malformed\":false,\"historical_torsion\":false}\n}\n";
    return 0;
  }
  catch (const std::exception &error)
  {
    std::cerr << "NATIVE_RECIPE_FAILED: " << error.what() << '\n';
    return 1;
  }
}
