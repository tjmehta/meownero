// Real TESTNET initialization and LMDB reopen, without listeners or test_options.
// API sources at e151643c5269c83bf24a83b2548e2493876026b2:
// src/cryptonote_core/{cryptonote_core.h,blockchain.cpp},
// src/blockchain_db/{blockchain_db.h,lmdb/db_lmdb.cpp}.
#include "cryptonote_core/cryptonote_core.h"
#include "cryptonote_basic/cryptonote_format_utils.h"
#include "common/util.h"
#include "string_tools.h"

#include <filesystem>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <sstream>

using namespace cryptonote;
namespace {
void require(bool ok, const char* message)
{
  if (!ok) throw std::runtime_error(message);
}
template<class T> std::string hex(const T& value)
{
  return epee::string_tools::pod_to_hex(value);
}
struct Node
{
  std::unique_ptr<core> value;
  explicit Node(const std::string& dir)
  {
    boost::program_options::options_description desc("core");
    core::init_options(desc);
    const std::vector<std::string> args{"--data-dir=" + dir, "--testnet", "--offline",
      "--disable-dns-checkpoints", "--fast-block-sync=0"};
    boost::program_options::variables_map vm;
    boost::program_options::store(boost::program_options::command_line_parser(args).options(desc).run(), vm);
    boost::program_options::notify(vm);
    value.reset(new core(nullptr));
    // A non-null test_options pointer silently selects FAKECHAIN upstream.
    require(value->init(vm, nullptr, nullptr, false), "TESTNET core init failed");
    require(value->get_nettype() == TESTNET, "core did not select genuine TESTNET");
  }
  ~Node() { if (value) value->deinit(); }
};
std::string snapshot(core& c)
{
  auto& chain = c.get_blockchain_storage();
  auto& db = chain.get_db();
  require(c.get_current_blockchain_height() == 1 && db.height() == 1, "genesis height differs");
  const auto b = db.get_block_from_height(0);
  const auto blob = db.get_block_blob_from_height(0);
  require(t_serializable_object_to_blob(b) == blob, "stored genesis serialization differs");
  require(hex(c.get_tail_id()) == "885cb43cf51086063f15c94d2fb7f327e34c447de53c9c6291b1a86d6510dab6",
          "stored genesis hash differs");
  std::string expected_tx;
  require(epee::string_tools::parse_hexstr_to_binbuff(get_config(TESTNET).GENESIS_TX, expected_tx),
          "configured genesis hex failed to decode");
  require(tx_to_blob(b.miner_tx) == expected_tx,
          "stored genesis transaction differs");
  require(db.get_block_already_generated_coins(0) == 0, "genesis generated coins are not zero");
  require(db.num_outputs() == 1 && db.get_num_outputs(0) == 1, "stored output count differs");
  const auto out = db.get_output_key(0, 0);
  const auto origin = db.get_output_tx_and_index(0, 0);
  require(hex(out.data.pubkey) == "5aeaf0562ffc3ae8b12bb4cfc3f07bf56916dd1e3b2e9cbf2674e54c5ba6dfe4",
          "stored output key differs");
  require(hex(out.data.commitment) == "5866666666666666666666666666666666666666666666666666666666666666",
          "stored amount-zero commitment differs");
  require(out.data.unlock_time == 60 && out.data.height == 0, "stored output maturity differs");
  require(origin.first == get_transaction_hash(b.miner_tx) && origin.second == 0, "output origin differs");
  const auto leaves = db.get_n_leaf_tuples();
  const auto scheduled_leaves = db.get_block_n_leaf_tuples(0);
  crypto::ec_point root{};
  const auto depth = db.get_tree_root_at_blk_idx(0, root);
  // Height zero's output is immature. Never label a zero-layer root trusted.
  require(scheduled_leaves == 0 && depth == 0 && root == crypto::ec_point{}, "immature root differs");
  require(chain.get_current_hard_fork_version() == 18 && chain.get_ideal_hard_fork_version(1) == 18,
          "next-block v18 fork state differs");
  std::ostringstream s;
  s << "{\"network\":\"TESTNET\",\"test_options\":null,\"height\":1,\"generated_coins\":0,"
    << "\"tip\":\"" << hex(c.get_tail_id()) << "\",\"genesis_block_hex\":\""
    << epee::string_tools::buff_to_hex_nodelimer(blob) << "\",\"output_key\":\"" << hex(out.data.pubkey)
    << "\",\"commitment\":\"" << hex(out.data.commitment) << "\",\"output_unlock_height\":60,"
    << "\"output_height\":0,\"output_tx\":\"" << hex(origin.first) << "\",\"output_index\":" << origin.second
    << ",\"unified_id\":" << out.unified_id << ",\"stored_tree_leaves\":" << leaves
    << ",\"scheduled_tree_leaves_at_genesis\":" << scheduled_leaves << ",\"tree_depth\":" << unsigned(depth)
    << ",\"tree_root\":\"" << hex(root) << "\",\"mature_root_available\":false,\"next_block_version\":18}";
  return s.str();
}
}
int main(int argc, char** argv)
{
  try
  {
    require(argc == 3, "usage: witness fresh-data-root positive|negative-case");
    tools::set_max_concurrency(1);
    const std::string dir = argv[1], mode = argv[2];
    require(!std::filesystem::exists(dir), "fresh database root required");
    if (mode == "positive")
    {
      std::string fresh, reopened, independent;
      { Node n(dir); fresh = snapshot(*n.value); }
      { Node n(dir); reopened = snapshot(*n.value); }
      { Node n(dir + "-independent"); independent = snapshot(*n.value); }
      require(fresh == reopened && fresh == independent, "reopen or independent database differs");
      std::cout << "{\"result\":\"PASS_NATIVE_TESTNET_GENESIS_ONLY\",\"launch_ready\":false,"
        << "\"selected_policy\":\"NOT_INTEGRATED\",\"two_peer_network\":\"NOT_RUN\","
        << "\"fresh\":" << fresh << ",\"reopened\":" << reopened << ",\"independent\":" << independent << "}\n";
    }
    else
    {
      Node n(dir);
      auto& chain = n.value->get_blockchain_storage();
      auto b = chain.get_db().get_block_from_height(0);
      if (mode == "positive-reward") b.miner_tx.vout[0].amount = 1;
      else if (mode == "wrong-height") boost::get<txin_gen>(b.miner_tx.vin[0]).height = 1;
      else if (mode == "wrong-unlock") b.miner_tx.unlock_time = 59;
      else if (mode == "empty-outputs") b.miner_tx.vout.clear();
      else if (mode == "wrong-version") b.miner_tx.version = 1;
      else
      {
        std::string point;
        if (mode == "identity") point = "01" + std::string(62, '0');
        else if (mode == "small-order") point = std::string(64, '0');
        else if (mode == "malformed") point = std::string(64, 'f');
        else if (mode == "historical-torsion") point = "9b2e4c0281c0b02e7c53291a94d1d0cbff8883f8024f5142ee494ffbbd088071";
        else throw std::runtime_error("unknown negative case");
        crypto::public_key key{};
        require(epee::string_tools::hex_to_pod(point, key), "negative fixture encoding failed");
        b.miner_tx.vout[0].target = txout_to_key{key};
      }
      b.miner_tx.invalidate_hashes();
      b.invalidate_hashes();
      // Native public reset/admission API, separate fresh DB per case. This is
      // not a modified get_config/init negative. Exceptions are failures.
      const bool accepted = chain.reset_and_set_genesis_block(b);
      const auto height = chain.get_db().height();
      require(!accepted && height == 0, "native admission accepted an adverse genesis");
      std::cout << "{\"case\":\"" << mode << "\",\"boundary\":\"reset_and_set_genesis_block\","
        << "\"accepted\":false,\"height_after\":0,\"result\":\"PASS_NATIVE_REJECTION\"}\n";
    }
    return 0;
  }
  catch (const std::exception& e) { std::cerr << "FAIL_NATIVE_TESTNET_ADMISSION " << e.what() << '\n'; return 1; }
}
