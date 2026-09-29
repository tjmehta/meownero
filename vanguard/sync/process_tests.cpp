// Two FAKECHAIN cores in separate processes. The parent delivers serialized
// transactions and blocks over pipes; neither core shares a database or pool.
#include "fcmp_pp.h"
#include "chaingen.h"
#include "common/util.h"
#include "cryptonote_core/tx_verification_utils.h"
#include "cryptonote_core/cryptonote_tx_utils.h"

#include <cerrno>
#include <cstring>
#include <fstream>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <sys/resource.h>
#include <sys/wait.h>
#include <unistd.h>

using namespace cryptonote;
namespace {
std::ofstream checks, states, controls;
void require(bool ok, const std::string& name)
{
  checks << name << '\t' << (ok ? "pass" : "FAIL") << '\n';
  if (!ok) throw std::runtime_error(name);
}
std::string hex(const crypto::hash& h) { return epee::string_tools::pod_to_hex(h); }
std::string hex(const crypto::ec_point& p) { return epee::string_tools::pod_to_hex(p); }

constexpr uint64_t fork_height = 80;
struct V17Options
{
  const std::pair<uint8_t, uint64_t> forks[5] = {{1, 0}, {2, 1},
    {HF_VERSION_BULLETPROOF_PLUS, 78}, {HF_VERSION_FCMP_PLUS_PLUS, fork_height}, {0, 0}};
  const test_options value{forks, 0};
};
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
    if (!value->init(vm, options, nullptr, false) || value->get_nettype() != FAKECHAIN)
      throw std::runtime_error("node init");
  }
  void restart() { value->deinit(); value.reset(); start(); }
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
struct State
{
  uint64_t height{};
  std::string tip, root;
  unsigned depth{};
  bool spent{}, chain{}, pool{};
  std::string str() const
  {
    std::ostringstream out;
    out << height << ' ' << tip << ' ' << root << ' ' << depth << ' '
        << spent << ' ' << chain << ' ' << pool;
    return out.str();
  }
};
State state(core& c, const transaction& spend)
{
  State s;
  s.height = c.get_current_blockchain_height();
  s.tip = hex(c.get_tail_id());
  crypto::ec_point root{};
  s.depth = c.get_blockchain_storage().get_db().get_tree_root_at_blk_idx(
    spend.rct_signatures.p.reference_block, root);
  s.root = hex(root);
  s.spent = c.get_blockchain_storage().have_tx_keyimges_as_spent(spend);
  s.chain = c.get_blockchain_storage().have_tx(get_transaction_hash(spend));
  s.pool = c.pool_has_tx(get_transaction_hash(spend));
  return s;
}
State parse_state(const std::string& line)
{
  std::istringstream in(line);
  State s;
  if (!(in >> s.height >> s.tip >> s.root >> s.depth >> s.spent >> s.chain >> s.pool))
    throw std::runtime_error("peer state parse");
  return s;
}
void snapshot(const std::string& name, const State& s)
{
  states << name << '\t' << s.height << '\t' << s.tip << '\t' << s.root << '\t'
         << s.depth << '\t' << s.spent << '\t' << s.chain << '\t' << s.pool << '\n';
}
void context(const std::string& name, const block_verification_context& bvc, const State& s)
{
  controls << name << '\t' << bvc.m_verifivation_failed << '\t'
           << bvc.m_added_to_main_chain << '\t' << bvc.m_missing_txs << '\t'
           << s.pool << '\t' << s.spent << '\n';
}

void write_all(int fd, const void* data, size_t size)
{
  const auto* ptr = static_cast<const char*>(data);
  while (size)
  {
    const auto count = write(fd, ptr, size);
    if (count < 0 && errno == EINTR) continue;
    if (count <= 0) throw std::runtime_error("pipe write");
    ptr += count;
    size -= count;
  }
}
bool read_all(int fd, void* data, size_t size)
{
  auto* ptr = static_cast<char*>(data);
  bool first = true;
  while (size)
  {
    const auto count = read(fd, ptr, size);
    if (count < 0 && errno == EINTR) continue;
    if (count < 0 || (count == 0 && !first)) throw std::runtime_error("pipe read");
    if (count == 0) return false;
    first = false;
    ptr += count;
    size -= count;
  }
  return true;
}
void write_frame(int fd, const std::string& data)
{
  if (data.size() > 16 * 1024 * 1024) throw std::runtime_error("pipe frame too large");
  const uint32_t size = data.size();
  write_all(fd, &size, sizeof(size));
  write_all(fd, data.data(), data.size());
}
std::string read_frame(int fd)
{
  uint32_t size = 0;
  if (!read_all(fd, &size, sizeof(size))) return {};
  if (!size || size > 16 * 1024 * 1024) throw std::runtime_error("bad pipe frame");
  std::string data(size, '\0');
  if (!read_all(fd, data.data(), size)) throw std::runtime_error("short pipe frame");
  return data;
}
void append_blob(std::string& out, const std::string& blob)
{
  const uint32_t size = blob.size();
  out.append(reinterpret_cast<const char*>(&size), sizeof(size));
  out.append(blob);
}
std::string take_blob(const std::string& input, size_t& pos)
{
  if (pos + sizeof(uint32_t) > input.size()) throw std::runtime_error("short blob size");
  uint32_t size;
  std::memcpy(&size, input.data() + pos, sizeof(size));
  pos += sizeof(size);
  if (pos + size > input.size()) throw std::runtime_error("short blob");
  std::string blob = input.substr(pos, size);
  pos += size;
  return blob;
}
std::string block_message(const block& b, const transaction* tx = nullptr)
{
  std::string data(1, 'B');
  append_blob(data, t_serializable_object_to_blob(b));
  append_blob(data, tx ? t_serializable_object_to_blob(*tx) : std::string{});
  return data;
}
block_verification_context parse_context(const std::string& line)
{
  std::istringstream in(line);
  block_verification_context bvc{};
  if (!(in >> bvc.m_verifivation_failed >> bvc.m_added_to_main_chain >> bvc.m_missing_txs))
    throw std::runtime_error("peer block context parse");
  return bvc;
}
int worker(int input, int output, const std::string& dir)
{
  try
  {
    tools::on_startup();
    tools::set_max_concurrency(2);
    mlog_configure("core-b.log", false);
    mlog_set_log("*:WARNING,global:INFO,blockchain:INFO,verify:DEBUG,txpool:DEBUG");
    V17Options opts;
    Node node(dir, &opts.value);
    transaction spend{};
    bool have_spend = false;
    write_frame(output, "O" + std::to_string(getpid()));
    for (std::string request; !(request = read_frame(input)).empty(); )
    {
      try
      {
        const char command = request[0];
        std::string result;
        if (command == 'X') { write_frame(output, "Oexit"); break; }
        if (command == 'G')
        {
          block b{};
          if (!parse_and_validate_block_from_blob(request.substr(1), b) || !node.c().set_genesis_block(b))
            throw std::runtime_error("peer genesis");
          result = "1";
        }
        else if (command == 'T' || command == 'S')
        {
          transaction tx{};
          crypto::hash id{};
          if (!parse_and_validate_tx_from_blob(request.substr(1), tx, id))
            throw std::runtime_error("peer transaction parse");
          if (command == 'S') { spend = tx; have_spend = true; }
          result = send_tx(node.c(), tx) ? "1" : "0";
        }
        else if (command == 'B')
        {
          size_t pos = 1;
          const auto blob = take_blob(request, pos);
          const auto extra = take_blob(request, pos);
          if (pos != request.size()) throw std::runtime_error("peer block trailing bytes");
          block b{};
          if (!parse_and_validate_block_from_blob(blob, b)) throw std::runtime_error("peer block parse");
          transaction tx{};
          const transaction* supplement = nullptr;
          if (!extra.empty())
          {
            crypto::hash id{};
            if (!parse_and_validate_tx_from_blob(extra, tx, id)) throw std::runtime_error("peer supplement parse");
            supplement = &tx;
          }
          const auto bvc = send_block(node.c(), b, supplement);
          std::ostringstream out;
          out << bvc.m_verifivation_failed << ' ' << bvc.m_added_to_main_chain << ' ' << bvc.m_missing_txs;
          result = out.str();
        }
        else if (command == 'R') { node.restart(); result = "1"; }
        else if (command == 'Q')
        {
          if (!have_spend) throw std::runtime_error("peer spend absent");
          result = state(node.c(), spend).str();
        }
        else throw std::runtime_error("unknown peer command");
        write_frame(output, "O" + result);
      }
      catch (const std::exception& error)
      {
        write_frame(output, "E" + std::string(error.what()));
        return 1;
      }
    }
    tools::threadpool::getInstanceForCompute().recycle();
    return 0;
  }
  catch (const std::exception& error)
  {
    std::cerr << "peer: " << error.what() << '\n';
    return 1;
  }
}
struct Peer
{
  int input, output;
  pid_t pid;
  Peer(int read_fd, int write_fd, pid_t child): input(read_fd), output(write_fd), pid(child) {}
  ~Peer()
  {
    if (output >= 0) close(output);
    if (input >= 0) close(input);
    if (pid > 0) { int status; waitpid(pid, &status, 0); }
  }
  std::string call(const std::string& data)
  {
    write_frame(output, data);
    const auto reply = read_frame(input);
    if (reply.empty()) throw std::runtime_error("peer exited");
    if (reply[0] != 'O') throw std::runtime_error("peer: " + reply.substr(1));
    return reply.substr(1);
  }
  bool tx(const transaction& t, bool spend = false)
  { return call(std::string(1, spend ? 'S' : 'T') + t_serializable_object_to_blob(t)) == "1"; }
  block_verification_context block(const cryptonote::block& b, const transaction* tx = nullptr)
  { return parse_context(call(block_message(b, tx))); }
  State state() { return parse_state(call("Q")); }
  bool finish()
  {
    if (call("X") != "exit") return false;
    close(output); output = -1;
    close(input); input = -1;
    int status = 0;
    if (waitpid(pid, &status, 0) != pid) return false;
    pid = -1;
    return WIFEXITED(status) && WEXITSTATUS(status) == 0;
  }
};
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
  b.fcmp_pp_n_tree_layers = c.get_blockchain_storage().get_db().get_tree_root_at_blk_idx(
    get_default_last_locked_block_index(height - 1), b.fcmp_pp_tree_root);
  test_generator{}.fill_nonce(b, get_test_difficulty(b.major_version), height);
  return b;
}
block v17_block(core& c, block b, const block& prev, uint64_t height)
{
  b.major_version = HF_VERSION_FCMP_PLUS_PLUS;
  b.minor_version = HF_VERSION_FCMP_PLUS_PLUS;
  b.prev_id = get_block_hash(prev);
  b.fcmp_pp_n_tree_layers = c.get_blockchain_storage().get_db().get_tree_root_at_blk_idx(
    get_default_last_locked_block_index(height - 1), b.fcmp_pp_tree_root);
  b.invalidate_hashes();
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
  int to_peer[2], from_peer[2];
  if (pipe(to_peer) || pipe(from_peer)) return 2;
  const pid_t child = fork();
  if (child < 0) return 2;
  if (child == 0)
  {
    close(to_peer[1]); close(from_peer[0]);
    const int code = worker(to_peer[0], from_peer[1], std::string(argv[1]) + "/b");
    close(to_peer[0]); close(from_peer[1]);
    return code;
  }
  close(to_peer[0]); close(from_peer[1]);
  Peer peer(from_peer[0], to_peer[1], child);
  checks.open("checks.tsv"); states.open("states.tsv"); controls.open("controls.tsv");
  try
  {
    const auto ready = read_frame(peer.input);
    require(ready.size() > 1 && ready[0] == 'O', "peer_process_ready");
    const auto peer_pid = std::stol(ready.substr(1));
    require(peer_pid == child && peer_pid != getpid(), "distinct_process_ids");
    std::ofstream processes("processes.tsv");
    processes << "source\t" << getpid() << "\npeer\t" << peer_pid << '\n';
    require(bool(processes), "process_receipt_written");
    tools::on_startup();
    tools::set_max_concurrency(2);
    mlog_configure("core-a.log", false);
    mlog_set_log("*:WARNING,global:INFO,blockchain:INFO,verify:DEBUG,txpool:DEBUG");
    std::vector<test_event_entry> events;
    require(gen_fcmp_pp_tx_from_bpp{}.generate(events), "generated_valueless_chain");
    std::vector<block> original;
    transaction spend{};
    for (const auto& event : events)
    {
      if (event.type() == typeid(block)) original.push_back(boost::get<block>(event));
      if (event.type() == typeid(std::vector<transaction>))
        spend = boost::get<std::vector<transaction>>(event).front();
    }
    require(original.size() == 142 && spend.rct_signatures.type == rct::RCTTypeFcmpPlusPlus,
      "fixture_shape");
    require(spend.rct_signatures.p.reference_block == 140 &&
      spend.rct_signatures.p.reference_block >= fork_height + 60, "reference_after_v17_fork_60");
    const auto txid = get_transaction_hash(spend);
    V17Options opts;
    Node a(std::string(argv[1]) + "/a", &opts.value);
    require(a.c().set_genesis_block(original[0]) &&
      peer.call("G" + t_serializable_object_to_blob(original[0])) == "1", "same_genesis");

    // Every transaction and block crosses the pipe before entering the peer.
    // Block 137 arrives before 136 there, then is retried after its parent.
    for (const auto& event : events)
    {
      if (event.type() == typeid(transaction))
      {
        const auto& tx = boost::get<transaction>(event);
        require(send_tx(a.c(), tx) && peer.tx(tx), "prerequisite_tx_delivered");
      }
      else if (event.type() == typeid(std::vector<transaction>))
      {
        require(send_tx(a.c(), spend) && peer.tx(spend, true), "spend_delivered_to_both_processes");
        require(a.c().pool_has_tx(txid), "source_pool_admitted");
      }
      else if (event.type() == typeid(block))
      {
        const auto height = get_block_height(boost::get<block>(event));
        if (height == 0) continue;
        if (height >= fork_height && height != 137)
          original[height] = v17_block(a.c(), original[height], original[height - 1], height);
        const auto& blk = original[height];
        const auto local = send_block(a.c(), blk);
        require(!local.m_verifivation_failed && a.c().get_tail_id() == get_block_hash(blk),
          "source_block_accepted");
        if (height == 136)
        {
          original[137] = v17_block(a.c(), original[137], blk, 137);
          const auto early = peer.block(original[137]);
          require(!early.m_added_to_main_chain, "peer_reordered_block_not_applied");
        }
        const auto remote = peer.block(blk);
        require(!remote.m_verifivation_failed, "peer_block_delivered");
      }
    }
    const auto initial = state(a.c(), spend);
    require(initial.str() == peer.state().str() && initial.spent && initial.chain,
      "initial_cross_process_convergence");
    snapshot("before_a", initial); snapshot("before_b", peer.state());
    require(peer.call("R") == "1", "peer_restart");
    require(initial.str() == peer.state().str(), "restart_cross_process_catchup");
    snapshot("restart_b", peer.state());

    account_base miner;
    miner.generate();
    std::vector<block> old_extension;
    auto old_tip = original.back();
    for (unsigned h = 142; h <= 144; ++h)
    {
      auto next = empty_block(a.c(), old_tip, miner);
      const auto outcome = send_block(a.c(), next);
      require(!outcome.m_verifivation_failed && a.c().get_tail_id() == get_block_hash(next),
        "old_extension_prepared");
      old_extension.push_back(next);
      old_tip = next;
    }
    a.c().get_blockchain_storage().pop_blocks(old_extension.size(), true);
    require(state(a.c(), spend).str() == peer.state().str(), "old_extension_builder_restored");

    // A builds the competing branch; B receives those serialized blocks as
    // alternatives and switches only when the branch overtakes its old tip.
    a.c().get_blockchain_storage().pop_blocks(62, true);
    require(a.c().get_tail_id() == get_block_hash(original[79]), "source_branch_split");
    std::vector<block> fork;
    for (unsigned h = fork_height; h <= 140; ++h)
    {
      auto next = original[h];
      if (h == fork_height)
      {
        const auto generated = a.c().get_blockchain_storage().get_db().get_block_already_generated_coins(h - 1);
        require(construct_miner_tx(h, 300000, generated, 0, 0,
          miner.get_keys().m_account_address, next.miner_tx, blobdata(), 6, HF_VERSION_FCMP_PLUS_PLUS),
          "fork_v17_miner_created");
      }
      next = v17_block(a.c(), next, h == fork_height ? original[79] : fork.back(), h);
      const auto local = send_block(a.c(), next);
      require(!local.m_verifivation_failed && a.c().get_tail_id() == get_block_hash(next),
        "source_fork_block_accepted");
      require(!peer.block(next).m_verifivation_failed, "peer_fork_block_delivered");
      fork.push_back(next);
    }
    const auto prefix = state(a.c(), spend);
    const auto old = peer.state();
    require(prefix.root != old.root && prefix.depth == old.depth,
      "trusted_root_changed_across_processes");
    snapshot("fork_prefix_a", prefix);
    auto prev = fork.back();
    for (unsigned h = 141; h <= 143; ++h)
    {
      auto next = empty_block(a.c(), prev, miner);
      const auto local = send_block(a.c(), next);
      require(!local.m_verifivation_failed && a.c().get_tail_id() == get_block_hash(next),
        "source_fork_tip_accepted");
      require(!peer.block(next).m_verifivation_failed, "peer_fork_tip_delivered");
      fork.push_back(next);
      prev = next;
    }
    const auto fork_a = state(a.c(), spend), fork_b = peer.state();
    require(fork_a.str() == fork_b.str() && !fork_a.spent && !fork_a.chain && fork_a.pool,
      "fork_cross_process_convergence_and_rollback");
    snapshot("fork_a", fork_a); snapshot("fork_b", fork_b);

    uint64_t fee = 0;
    require(get_tx_fee(spend, fee), "original_fee_available");
    const auto invalid = empty_block(a.c(), fork.back(), miner, fee, &spend);
    const auto a_bad = send_block(a.c(), invalid, &spend);
    const auto b_bad = peer.block(invalid, &spend);
    context("stale_root_a", a_bad, state(a.c(), spend));
    context("stale_root_b", b_bad, peer.state());
    require(a_bad.m_verifivation_failed && b_bad.m_verifivation_failed &&
      !a_bad.m_missing_txs && !b_bad.m_missing_txs, "stale_root_supplement_rejected_both_processes");
    const auto a_pool_bad = send_block(a.c(), invalid);
    const auto b_pool_bad = peer.block(invalid);
    context("stale_root_pool_a", a_pool_bad, state(a.c(), spend));
    context("stale_root_pool_b", b_pool_bad, peer.state());
    require(a_pool_bad.m_verifivation_failed && b_pool_bad.m_verifivation_failed &&
      !a_pool_bad.m_missing_txs && !b_pool_bad.m_missing_txs,
      "stale_root_pool_rejected_both_processes");
    require(fork_a.str() == state(a.c(), spend).str() && fork_b.str() == peer.state().str(),
      "invalid_blocks_leave_both_processes_unchanged");

    // A popped the original prefix. Flush its retained spend immediately
    // before old 141, so the alternative-block supplement must admit it.
    for (unsigned h = fork_height; h < original.size(); ++h)
    {
      if (h == 141)
      {
        require(a.c().pool_has_tx(txid), "source_alt_spend_present_before_flush");
        require(a.c().get_blockchain_storage().flush_txes_from_pool({txid}) &&
          !a.c().pool_has_tx(txid), "source_alt_spend_flushed");
      }
      const auto outcome = send_block(a.c(), original[h], h == 141 ? &spend : nullptr);
      if (h == 141)
      {
        context("reverse_spend_alt_a", outcome, state(a.c(), spend));
        require(!outcome.m_missing_txs && a.c().pool_has_tx(txid),
          "source_alt_supplement_admitted");
      }
      require(!outcome.m_verifivation_failed, "source_old_alternative_accepted");
    }
    for (const auto& next : old_extension)
    {
      const auto a_reverse = send_block(a.c(), next);
      const auto b_reverse = peer.block(next);
      context("reverse_extension_a", a_reverse, state(a.c(), spend));
      context("reverse_extension_b", b_reverse, peer.state());
      require(!a_reverse.m_verifivation_failed && !b_reverse.m_verifivation_failed,
        "reverse_extension_delivered_to_both_processes");
    }
    const auto reverse_a = state(a.c(), spend), reverse_b = peer.state();
    require(reverse_a.str() == reverse_b.str() && reverse_a.tip == hex(get_block_hash(old_extension.back())) &&
      reverse_a.root == initial.root && reverse_a.spent && reverse_a.chain && !reverse_a.pool,
      "reverse_cross_process_convergence_and_key_image_reapplication");
    snapshot("reverse_a", reverse_a); snapshot("reverse_b", reverse_b);
    require(peer.finish(), "peer_clean_exit");
    require(bool(checks) && bool(states) && bool(controls), "receipt_streams_ok");
    tools::threadpool::getInstanceForCompute().recycle();
    return 0;
  }
  catch (const std::exception& error)
  {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
