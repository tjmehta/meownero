// Two independent FAKECHAIN cores, fed serialized blocks and transactions in a
// controlled order. All accounts and outputs are synthetic and valueless.
#include "fcmp_pp.h"
#include "chaingen.h"
#include "common/util.h"
#include "cryptonote_core/tx_verification_utils.h"
#include "cryptonote_core/cryptonote_tx_utils.h"

#include <fstream>
#include <memory>
#include <stdexcept>
#include <sys/resource.h>
#include <unistd.h>

using namespace cryptonote;
namespace {
std::ofstream checks;
std::ofstream states;

void require(bool ok, const std::string& name)
{
  checks << name << '\t' << (ok ? "pass" : "FAIL") << '\n';
  if (!ok) throw std::runtime_error(name);
}

std::string hex(const crypto::hash& h) { return epee::string_tools::pod_to_hex(h); }
std::string hex(const crypto::ec_point& p) { return epee::string_tools::pod_to_hex(p); }

struct Node
{
  std::unique_ptr<core> value;
  std::string dir;
  const test_options* options;

  Node(std::string path, const test_options* opts): dir(std::move(path)), options(opts) { start(); }
  void start()
  {
    boost::program_options::options_description desc("core");
    core::init_options(desc);
    const std::vector<std::string> args{"--data-dir=" + dir, "--offline", "--keep-fakechain",
      "--disable-dns-checkpoints", "--fast-block-sync=0"};
    boost::program_options::variables_map vm;
    boost::program_options::store(boost::program_options::command_line_parser(args).options(desc).run(), vm);
    boost::program_options::notify(vm);
    value.reset(new core(nullptr));
    require(value->init(vm, options, nullptr, false), "node_init");
    require(value->get_nettype() == FAKECHAIN, "node_fakechain");
  }
  void restart()
  {
    value->deinit();
    value.reset();
    start();
  }
  ~Node() { if (value) value->deinit(); }
  core& c() { return *value; }
};

bool send_tx(core& c, const transaction& source)
{
  const auto blob = t_serializable_object_to_blob(source);
  transaction tx{};
  crypto::hash id{};
  tx_verification_context tvc{};
  if (!parse_and_validate_tx_from_blob(blob, tx, id)) return false;
  return c.handle_incoming_tx(blob, tx, id, tvc, relay_method::fluff, false) && !tvc.m_verifivation_failed;
}

block_verification_context send_block(core& c, const block& source, const transaction* supplement = nullptr)
{
  const auto blob = t_serializable_object_to_blob(source);
  block_complete_entry entry{};
  entry.pruned = false;
  entry.block = blob;
  if (supplement) entry.txs.push_back(t_serializable_object_to_blob(*supplement));
  std::vector<block> prepared;
  block_verification_context bvc{};
  if (!c.prepare_handle_incoming_blocks({entry}, prepared))
  {
    bvc.m_verifivation_failed = true;
    return bvc;
  }
  pool_supplement ps{};
  if (supplement) ps.add_tx(get_transaction_hash(*supplement), transaction(*supplement),
                            t_serializable_object_to_blob(*supplement));
  c.handle_incoming_block(blob, &source, bvc, ps, false);
  c.cleanup_handle_incoming_blocks();
  return bvc;
}

void accepted(core& c, const block& b, const std::string& name, const transaction* tx = nullptr)
{
  const auto result = send_block(c, b, tx);
  require(!result.m_verifivation_failed && c.get_tail_id() == get_block_hash(b), name);
}

struct Anchor { crypto::ec_point root{}; uint8_t depth{}; };
Anchor anchor(core& c, uint64_t reference)
{
  Anchor result;
  result.depth = c.get_blockchain_storage().get_db().get_tree_root_at_blk_idx(reference, result.root);
  return result;
}

void snapshot(const std::string& label, core& c, const transaction& tx)
{
  const auto a = anchor(c, tx.rct_signatures.p.reference_block);
  states << label << '\t' << c.get_current_blockchain_height() << '\t'
         << hex(c.get_tail_id()) << '\t' << hex(a.root) << '\t' << unsigned(a.depth) << '\t'
         << c.get_blockchain_storage().have_tx_keyimges_as_spent(tx) << '\t'
         << c.get_blockchain_storage().have_tx(get_transaction_hash(tx)) << '\t'
         << c.pool_has_tx(get_transaction_hash(tx)) << '\n';
}

bool same(core& a, core& b, const transaction& tx)
{
  const auto x = anchor(a, tx.rct_signatures.p.reference_block);
  const auto y = anchor(b, tx.rct_signatures.p.reference_block);
  return a.get_current_blockchain_height() == b.get_current_blockchain_height()
    && a.get_tail_id() == b.get_tail_id() && x.root == y.root && x.depth == y.depth
    && a.get_blockchain_storage().have_tx_keyimges_as_spent(tx) == b.get_blockchain_storage().have_tx_keyimges_as_spent(tx)
    && a.get_blockchain_storage().have_tx(get_transaction_hash(tx)) == b.get_blockchain_storage().have_tx(get_transaction_hash(tx));
}

block empty_block(core& c, const block& prev, const account_base& miner, uint64_t fee = 0,
                  const transaction* tx = nullptr)
{
  block b{};
  const auto height = get_block_height(prev) + 1;
  b.major_version = HF_VERSION_FCMP_PLUS_PLUS;
  b.minor_version = HF_VERSION_FCMP_PLUS_PLUS;
  b.timestamp = prev.timestamp + DIFFICULTY_BLOCKS_ESTIMATE_TIMESPAN * 2;
  b.prev_id = get_block_hash(prev);
  if (tx) b.tx_hashes.push_back(get_transaction_hash(*tx));
  const auto generated = c.get_blockchain_storage().get_db().get_block_already_generated_coins(height - 1);
  if (!construct_miner_tx(height, 300000, generated, tx ? get_transaction_weight(*tx) : 0,
        fee, miner.get_keys().m_account_address, b.miner_tx, blobdata(), 6, b.major_version))
    throw std::runtime_error("construct alternate miner transaction");
  const auto index = get_default_last_locked_block_index(height - 1);
  b.fcmp_pp_n_tree_layers = c.get_blockchain_storage().get_db().get_tree_root_at_blk_idx(index, b.fcmp_pp_tree_root);
  test_generator{}.fill_nonce(b, get_test_difficulty(b.major_version), height);
  return b;
}
}

int main(int argc, char** argv)
{
  if (argc != 2) return 2;
  struct rlimit limit{0, 0};
  setrlimit(RLIMIT_CORE, &limit);
  alarm(900);
  checks.open("checks.tsv");
  states.open("states.tsv");
  try
  {
    tools::on_startup();
    tools::set_max_concurrency(2);
    mlog_configure("core.log", false);
    mlog_set_log_level(0);
    std::vector<test_event_entry> events;
    require(gen_fcmp_pp_tx_from_bpp{}.generate(events), "generated_valueless_chain");
    std::vector<block> original;
    transaction spend{};
    for (const auto& event : events)
    {
      if (event.type() == typeid(block)) original.push_back(boost::get<block>(event));
      if (event.type() == typeid(std::vector<transaction>)) spend = boost::get<std::vector<transaction>>(event).front();
    }
    require(original.size() == 140 && spend.rct_signatures.type == rct::RCTTypeFcmpPlusPlus,
      "fixture_shape");
    require(spend.rct_signatures.p.reference_block == 138, "reference_height");
    const auto txid = get_transaction_hash(spend);
    get_test_options<gen_fcmp_pp_tx_from_bpp> opts;
    Node a(std::string(argv[1]) + "/a", &opts.test_options);
    Node b(std::string(argv[1]) + "/b", &opts.test_options);
    require(a.c().set_genesis_block(original[0]) && b.c().set_genesis_block(original[0]), "same_genesis");

    // Relay each serialized prerequisite transaction before its containing block.
    // Deliver block 137 early to B and then retry it after 136 arrives.
    for (const auto& event : events)
    {
      if (event.type() == typeid(transaction))
      {
        const auto& tx = boost::get<transaction>(event);
        require(send_tx(a.c(), tx) && send_tx(b.c(), tx), "prerequisite_tx_relay");
      }
      else if (event.type() == typeid(std::vector<transaction>))
      {
        require(send_tx(a.c(), spend), "source_tx_admitted");
        require(send_tx(b.c(), spend), "peer_tx_admitted");
        require(a.c().pool_has_tx(txid) && b.c().pool_has_tx(txid), "propagated_pool_state");
      }
      else if (event.type() == typeid(block))
      {
        const auto& blk = boost::get<block>(event);
        const auto height = get_block_height(blk);
        if (height == 0) continue;
        accepted(a.c(), blk, "source_block_accepted");
        if (height == 136)
        {
          const auto tip = b.c().get_tail_id();
          const auto early = send_block(b.c(), original[137]);
          require(!early.m_added_to_main_chain && b.c().get_tail_id() == tip, "reordered_block_not_applied");
        }
        accepted(b.c(), blk, "peer_block_accepted");
      }
    }
    require(same(a.c(), b.c(), spend), "initial_convergence");
    require(a.c().get_blockchain_storage().have_tx_keyimges_as_spent(spend), "initial_key_image_spent");
    snapshot("before_a", a.c(), spend);
    snapshot("before_b", b.c(), spend);
    b.restart();
    require(same(a.c(), b.c(), spend), "restart_catchup_convergence");
    snapshot("restart_b", b.c(), spend);

    account_base miner;
    miner.generate();
    // B builds a competing branch from 79. The changed miner output unlocks
    // before reference block 138, changing that trusted tree root.
    b.c().get_blockchain_storage().pop_blocks(61, true);
    require(b.c().get_tail_id() == get_block_hash(original[78]), "peer_branch_split");
    std::vector<block> fork;
    for (unsigned h = 79; h <= 138; ++h)
    {
      auto next = original[h];
      if (h == 79)
      {
        next.miner_tx.vout.front().target = original[78].miner_tx.vout.front().target;
        next.miner_tx.invalidate_hashes();
      }
      if (h > 79) next.prev_id = get_block_hash(fork.back());
      next.invalidate_hashes();
      test_generator{}.fill_nonce(next, get_test_difficulty(next.major_version), h);
      accepted(b.c(), next, "peer_fork_block_accepted");
      fork.push_back(next);
    }
    const auto before = anchor(a.c(), 138);
    const auto after = anchor(b.c(), 138);
    require(before.root != after.root, "trusted_root_changed");
    require(before.depth == after.depth, "trusted_depth_recorded");
    snapshot("fork_prefix_b", b.c(), spend);
    auto prev = fork.back();
    for (unsigned h = 139; h <= 141; ++h)
    {
      auto next = empty_block(b.c(), prev, miner);
      accepted(b.c(), next, "peer_fork_tip_accepted");
      fork.push_back(next);
      prev = next;
    }
    require(!b.c().get_blockchain_storage().have_tx_keyimges_as_spent(spend), "peer_key_image_rolled_back");
    require(!b.c().get_blockchain_storage().have_tx(txid), "peer_old_tx_disconnected");

    // A sees the competing branch through its ordinary alternate-chain path.
    for (const auto& next : fork)
    {
      const auto outcome = send_block(a.c(), next);
      require(!outcome.m_verifivation_failed, "source_fork_block_accepted");
    }
    require(same(a.c(), b.c(), spend), "fork_convergence");
    require(!a.c().get_blockchain_storage().have_tx_keyimges_as_spent(spend), "source_key_image_rolled_back");
    require(!a.c().pool_has_tx(txid) && !b.c().pool_has_tx(txid), "stale_pool_entry_removed");
    snapshot("fork_a", a.c(), spend);
    snapshot("fork_b", b.c(), spend);

    // An explicit block supplement avoids a mere missing-pool-tx rejection.
    // This must fail even though the same tx was already verified on the old root.
    uint64_t fee = 0;
    require(get_tx_fee(spend, fee), "original_fee_available");
    const auto invalid = empty_block(b.c(), fork.back(), miner, fee, &spend);
    const auto a_bad = send_block(a.c(), invalid, &spend);
    const auto b_bad = send_block(b.c(), invalid, &spend);
    require(a_bad.m_verifivation_failed && b_bad.m_verifivation_failed, "stale_proof_block_rejected");
    require(same(a.c(), b.c(), spend), "invalid_block_state_unchanged");

    require(bool(checks) && bool(states), "receipt_streams_ok");
    tools::threadpool::getInstanceForCompute().recycle();
    return 0;
  }
  catch (const std::exception& e)
  {
    std::cerr << e.what() << '\n';
    return 1;
  }
}
