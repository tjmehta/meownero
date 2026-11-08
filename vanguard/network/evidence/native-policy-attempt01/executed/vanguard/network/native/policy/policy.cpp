// Bounded policy/API witness at e151643c5269c83bf24a83b2548e2493876026b2.
// Source APIs: cryptonote_basic_impl.{h,cpp}, cryptonote_tx_utils.{h,cpp},
// cryptonote_core.h, blockchain.cpp, common/base58.h. No P2P or RPC listener.
#include "cryptonote_basic/account.h"
#include "cryptonote_basic/cryptonote_basic_impl.h"
#include "cryptonote_basic/cryptonote_format_utils.h"
#include "cryptonote_core/cryptonote_core.h"
#include "cryptonote_core/cryptonote_tx_utils.h"
#include "common/base58.h"
#include "common/util.h"

#include <algorithm>
#include <filesystem>
#include <iostream>
#include <limits>
#include <stdexcept>

using namespace cryptonote;
namespace {
void require(bool ok, const char* message)
{
  if (!ok) throw std::runtime_error(message);
}
uint64_t reward_reference(network_type net, uint8_t version, uint64_t supply)
{
  if (net == TESTNET) return 9000000000000;
  const int minutes = version < 2 ? 1 : 2;
  return std::max((MONEY_SUPPLY - supply) >> (EMISSION_SPEED_FACTOR_PER_MINUTE - (minutes - 1)),
                  uint64_t(FINAL_SUBSIDY_PER_MINUTE * minutes));
}
size_t zone_reference(uint8_t version)
{
  return version < 2 ? 20000 : version < 5 ? 60000 : version < 17 ? 300000 : 625000;
}
unsigned reward_vectors()
{
  unsigned count = 0;
  constexpr uint64_t max = std::numeric_limits<uint64_t>::max();
  for (auto net : {MAINNET, TESTNET, STAGENET, FAKECHAIN})
    for (uint8_t version = 1; version <= 18; ++version)
    {
      require(cryptonote::get_difficulty_target(net, version) ==
        (net == TESTNET ? 90 : version < 2 ? 60 : 120), "target/selector disagreement");
      for (size_t median : {size_t(0), zone_reference(version), zone_reference(version) * 7})
      {
        const size_t m = std::max(median, zone_reference(version));
        for (size_t weight : {size_t(0), m, m + 1, m * 9 / 8, m * 3 / 2, m * 15 / 8, 2*m - 1, 2*m, 2*m + 1})
          for (uint64_t supply : {uint64_t(0), uint64_t(1), max - 9000000000001, max - 9000000000000,
                                  max - 8999999999999, max - 1, max})
          {
            uint64_t reward = 0;
            const bool ok = get_block_reward(median, weight, supply, reward, version, net);
            require(ok == (weight <= 2*m), "overweight rejection differs");
            if (ok)
            {
              const uint64_t base = reward_reference(net, version, supply);
              const uint64_t expected = weight <= m ? base :
                uint64_t(static_cast<unsigned __int128>(base) * weight * (2*m - weight) / m / m);
              require(reward == expected, "reward/penalty/selector mismatch");
            }
            ++count;
          }
      }
    }
  return count;
}
unsigned address_vectors(const account_public_address& address)
{
  unsigned count = 0;
  crypto::hash8 payment{};
  for (unsigned form = 0; form < 3; ++form)
  {
    const auto encoded = form == 2 ? get_account_integrated_address_as_str(TESTNET, address, payment) :
      get_account_address_as_str(TESTNET, form == 1, address);
    address_parse_info own{};
    require(get_account_address_from_str(own, TESTNET, encoded) && own.address == address &&
      own.is_subaddress == (form == 1) && own.has_payment_id == (form == 2), "same-profile address failed");
    ++count;
    for (auto foreign : {MAINNET, STAGENET, FAKECHAIN})
    {
      address_parse_info other{};
      require(!get_account_address_from_str(other, foreign, encoded), "foreign selector decoded dedicated address");
      const auto wrong = form == 2 ? get_account_integrated_address_as_str(foreign, address, payment) :
        get_account_address_as_str(foreign, form == 1, address);
      require(!get_account_address_from_str(other, TESTNET, wrong), "dedicated selector decoded foreign address");
      count += 2;
    }
    uint64_t prefix{};
    std::string payload;
    require(tools::base58::decode_addr(encoded, prefix, payload), "native address decode failed");
    // Upstream TESTNET and historical Candidate M identities are adverse data.
    for (uint64_t foreign : {uint64_t(53), uint64_t(54), uint64_t(63), uint64_t(120), uint64_t(121), uint64_t(123)})
    {
      address_parse_info other{};
      require(!get_account_address_from_str(other, TESTNET, tools::base58::encode_addr(foreign, payload)),
        "dedicated selector decoded upstream/historical prefix");
      ++count;
    }
  }
  return count;
}
}
int main(int argc, char** argv)
{
  try
  {
    require(argc == 2 && !std::filesystem::exists(argv[1]), "fresh task-owned data root required");
    tools::set_max_concurrency(1);
    const auto rewards = reward_vectors();
    account_base miner;
    miner.generate(); // In-memory valueless fixture. Never export keys or seed.
    const auto& address = miner.get_keys().m_account_address;
    const auto addresses = address_vectors(address);
    unsigned constructions = 0;
    for (uint64_t supply : {uint64_t(0), uint64_t(1), std::numeric_limits<uint64_t>::max()})
      for (uint64_t fee : {uint64_t(0), uint64_t(12345)})
        for (size_t weight : {size_t(0), size_t(625000), size_t(937500), size_t(1250000)})
        {
          transaction tx{};
          require(construct_miner_tx(1, 625000, supply, weight, fee, address, tx, {}, 1, 18, TESTNET),
            "height-one native CARROT construction failed");
          const uint64_t expected = weight <= 625000 ? 9000000000000 :
            uint64_t(static_cast<unsigned __int128>(9000000000000) * weight * (1250000 - weight) / 625000 / 625000);
          require(tx.vout.size() == 1 && tx.vout[0].amount == expected + fee &&
            tx.vout[0].target.type() == typeid(txout_to_carrot_v1), "height-one zero-supply/fee/penalty mismatch");
          ++constructions;
        }
    transaction genesis{};
    require(construct_miner_tx(0, 0, 0, 0, 0, address, genesis, {}, 1, 1, TESTNET) &&
      genesis.vout.size() == 1 && genesis.vout[0].amount == 0, "explicit native genesis construction failed");
    transaction denied{};
    require(!construct_miner_tx(0, 0, 0, 0, 1, address, denied, {}, 1, 1, TESTNET), "genesis collected a fee");

    boost::program_options::options_description desc("policy-core");
    core::init_options(desc);
    const std::vector<std::string> args{std::string("--data-dir=") + argv[1], "--testnet", "--offline",
      "--disable-dns-checkpoints", "--fast-block-sync=0"};
    boost::program_options::variables_map vm;
    boost::program_options::store(boost::program_options::command_line_parser(args).options(desc).run(), vm);
    boost::program_options::notify(vm);
    core c(nullptr);
    require(c.init(vm, nullptr, nullptr, false) && c.get_nettype() == TESTNET, "genuine TESTNET core init failed");
    auto& chain = c.get_blockchain_storage();
    require(chain.get_difficulty_target() == 90 && chain.get_current_hard_fork_version() == 18,
      "native chain policy mismatch");
    block b{};
    difficulty_type difficulty{};
    uint64_t height{}, expected{}, weight{}, seed_height{};
    crypto::hash seed{};
    require(c.get_block_template(b, address, difficulty, height, expected, weight, {}, seed_height, seed),
      "native height-one template failed");
    require(height == 1 && expected == 9000000000000 && b.major_version == 18 &&
      b.miner_tx.vout.size() == 1 && b.miner_tx.vout[0].amount == expected, "native template reward/fork mismatch");
    const auto admitted = chain.get_db().get_block_from_height(0);
    require(chain.reset_and_set_genesis_block(admitted) && chain.get_db().height() == 1,
      "same-boundary positive reset failed; prior adverse reset results remain non-specific");
    c.deinit();
    std::cout << "{\"result\":\"PASS_NATIVE_POLICY_HELPERS_AND_TEMPLATE_ONLY\",\"launch_ready\":false,"
      << "\"reward_vectors\":" << rewards << ",\"address_vectors\":" << addresses
      << ",\"constructions\":" << constructions << ",\"positive_reset\":true,"
      << "\"admitted_non_genesis_blocks\":0,\"two_peer_network\":\"NOT_RUN\",\"mature_root\":\"NOT_RUN\"}\n";
    return 0;
  }
  catch (const std::exception& e) { std::cerr << "FAIL_NATIVE_POLICY " << e.what() << '\n'; return 1; }
}
