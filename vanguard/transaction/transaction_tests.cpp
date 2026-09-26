// Local, valueless integration of the pinned upstream wallet builder and core.
// The upstream generator and core implementation are compiled unchanged.
#include "fcmp_pp.h"
#include "verify.h"
#include "common/util.h"
#include "cryptonote_core/tx_verification_utils.h"
#include "fcmp_pp/curve_trees.h"
#include "ringct/rctSigs.h"
#include "device/device.hpp"

#include <chrono>
#include <fstream>
#include <stdexcept>
#include <sys/resource.h>
#include <unistd.h>

using namespace cryptonote;
namespace {
std::ofstream results;
std::ofstream observations;

void require(bool ok, const std::string& name)
{
  results << name << '\t' << (ok ? "pass" : "FAIL") << std::endl;
  if (!ok) throw std::runtime_error(name);
}

void save(const std::string& name, const blobdata& bytes)
{
  std::ofstream out(name, std::ios::binary);
  out.write(bytes.data(), bytes.size());
  if (!out) throw std::runtime_error("cannot write " + name);
}

struct VanguardAdmission : gen_fcmp_pp_tx_validation_base
{
  VanguardAdmission()
  {
    REGISTER_CALLBACK_METHOD(VanguardAdmission, probe_invalid);
    REGISTER_CALLBACK_METHOD(VanguardAdmission, check_pool);
    REGISTER_CALLBACK_METHOD(VanguardAdmission, check_chain);
  }

  bool probe_invalid(core& c, size_t index, const std::vector<test_event_entry>& events)
  {
    const auto& txs = boost::get<std::vector<transaction>>(events.at(index + 1));
    require(txs.size() == 1, "one_constructed_transaction");
    const auto& tx = txs.front();
    require(tx.version == 2 && tx.rct_signatures.type == rct::RCTTypeFcmpPlusPlus,
      "constructed_fcmp_transaction");
    require(!tx.vout.empty() && std::all_of(tx.vout.begin(), tx.vout.end(),
      [](const tx_out& out) { return out.target.type() == typeid(txout_to_carrot_v1); }),
      "constructed_carrot_outputs");
    require(tx.rct_signatures.p.bulletproofs_plus.size() == 1, "constructed_range_proof");
    require(c.get_pool_transactions_count() == 0, "initial_pool_empty");
    const auto height = c.get_current_blockchain_height();
    const auto tip = c.get_tail_id();
    auto& db = c.get_blockchain_storage().get_db();
    vanguard::TreeAnchor anchor{};
    anchor.layers = db.get_tree_root_at_blk_idx(tx.rct_signatures.p.reference_block, anchor.root);
    require(anchor.layers == tx.rct_signatures.p.n_tree_layers, "database_anchor_matches_claim");

    auto expanded = tx;
    const auto root = fcmp_pp::curve_trees::curve_trees_v1()->get_tree_root_from_bytes(anchor.layers, anchor.root);
    require(Blockchain::expand_transaction_2(expanded, get_transaction_prefix_hash(tx), {}, root),
      "expand_constructed_transaction");
    const auto& rv = expanded.rct_signatures;
    const auto message = rct::rct2hash(rct::get_pre_mlsag_hash(rv, hw::get_device("default")));
    std::vector<crypto::ec_point> pseudo_outs;
    for (const auto& po : rv.p.pseudoOuts) pseudo_outs.push_back(rct::rct2pt(po));
    const auto& images = rv.p.fcmp_ver_helper_data.key_images;
    const auto verify = [&](const fcmp_pp::FcmpPpProof& proof, size_t claimed) {
      return vanguard::verify(message, proof, claimed, anchor, pseudo_outs, images);
    };
    require(verify(rv.p.fcmp_pp, anchor.layers), "boundary_valid_transaction");
    auto proof = rv.p.fcmp_pp;
    proof.push_back(0);
    require(!verify(proof, anchor.layers), "boundary_trailing_proof_byte");
    proof = rv.p.fcmp_pp;
    proof.pop_back();
    require(!verify(proof, anchor.layers), "boundary_truncated_proof");
    require(!verify(rv.p.fcmp_pp, anchor.layers + 1), "boundary_wrong_depth");
    proof = rv.p.fcmp_pp;
    proof.back() ^= 1;
    require(!verify(proof, anchor.layers), "boundary_corrupt_proof");

    const auto valid_blob = t_serializable_object_to_blob(tx);
    require(!valid_blob.empty(), "serialize_valid_transaction");
    save("valid.tx.bin", valid_blob);
    observations << "tx_bytes\t" << valid_blob.size() << '\n'
                 << "proof_bytes\t" << rv.p.fcmp_pp.size() << '\n'
                 << "inputs\t" << tx.vin.size() << '\n'
                 << "outputs\t" << tx.vout.size() << '\n'
                 << "reference_block\t" << rv.p.reference_block << '\n'
                 << "anchor_layers\t" << anchor.layers << '\n';

    const auto reject = [&](const std::string& name, const blobdata& blob, bool parses) {
      save(name + ".tx.bin", blob);
      transaction parsed{};
      crypto::hash id{};
      tx_verification_context tvc{};
      const bool parsed_ok = parse_and_validate_tx_from_blob(blob, parsed, id);
      require(parsed_ok == parses, name + ".parse");
      if (parsed_ok)
      {
        const bool accepted = c.handle_incoming_tx(blob, parsed, id, tvc, relay_method::fluff, false);
        require(!accepted && tvc.m_verifivation_failed && !c.pool_has_tx(id), name + ".core_reject");
      }
      require(c.get_pool_transactions_count() == 0 && c.get_current_blockchain_height() == height &&
        c.get_tail_id() == tip, name + ".state_unchanged");
    };
    reject("blob_suffix", valid_blob + char(0), false);
    reject("blob_truncated", valid_blob.substr(0, valid_blob.size() - 1), false);
    const auto reject_tx = [&](const std::string& name, transaction bad) {
      bad.invalidate_hashes();
      const auto blob = t_serializable_object_to_blob(bad);
      require(!blob.empty() && blob != valid_blob, name + ".serialized_mutation");
      reject(name, blob, true);
    };
    auto bad = tx;
    bad.rct_signatures.p.fcmp_pp.back() ^= 1;
    reject_tx("proof_corrupt", bad);
    bad = tx;
    ++bad.rct_signatures.txnFee;
    reject_tx("fee_changed", bad);
    bad = tx;
    bad.rct_signatures.p.bulletproofs_plus.front().r1.bytes[0] ^= 1;
    reject_tx("range_proof_corrupt", bad);
    bad = tx;
    boost::get<txout_to_carrot_v1>(bad.vout.front().target).view_tag.bytes[0] ^= 1;
    reject_tx("carrot_view_tag_changed", bad);
    bad = tx;
    bad.rct_signatures.p.reference_block = height + 100;
    reject_tx("unknown_reference_block", bad);
    bad = tx;
    ++bad.rct_signatures.p.n_tree_layers;
    bad.rct_signatures.p.fcmp_pp.resize(fcmp_pp::fcmp_pp_proof_len(bad.vin.size(), bad.rct_signatures.p.n_tree_layers));
    reject_tx("wrong_depth_exact_size", bad);
    require(verify(rv.p.fcmp_pp, anchor.layers), "boundary_valid_after_rejections");
    return true;
  }

  bool check_pool(core& c, size_t index, const std::vector<test_event_entry>& events)
  {
    const auto& tx = boost::get<std::vector<transaction>>(events.at(index - 1)).front();
    require(c.get_pool_transactions_count() == 1 && c.pool_has_tx(get_transaction_hash(tx)),
      "valid_transaction_in_pool");
    return true;
  }

  bool check_chain(core& c, size_t index, const std::vector<test_event_entry>& events)
  {
    const auto& block = boost::get<cryptonote::block>(events.at(index - 1));
    const auto& tx = boost::get<std::vector<transaction>>(events.at(index - 3)).front();
    require(c.get_tail_id() == get_block_hash(block), "valid_block_is_tip");
    require(c.get_blockchain_storage().have_tx(get_transaction_hash(tx)), "valid_transaction_in_chain");
    require(c.get_pool_transactions_count() == 0, "confirmed_pool_empty");
    require(c.get_blockchain_storage().have_tx_keyimges_as_spent(tx), "confirmed_key_image_spent");
    observations << "final_height\t" << c.get_current_blockchain_height() << '\n';
    return true;
  }
};
}

int main(int argc, char** argv)
{
  if (argc != 2) return 2;
  struct rlimit no_core{0, 0};
  setrlimit(RLIMIT_CORE, &no_core);
  alarm(900);
  results.open("results.tsv");
  observations.open("observations.tsv");
  try
  {
    tools::on_startup();
    tools::set_max_concurrency(2);
    mlog_configure("core.log", false);
    mlog_set_log_level(0);
    const auto start = std::chrono::steady_clock::now();
    std::vector<test_event_entry> events;
    require(gen_fcmp_pp_tx_from_bpp{}.generate(events), "generate_wallet_transaction_and_chain");
    // Preserve the generated transaction and confirmation block. Add probes just
    // before admission, then explicit pool and confirmed-chain assertions.
    require(events.size() > 2 && events[events.size() - 2].type() == typeid(std::vector<transaction>) &&
      events.back().type() == typeid(block), "upstream_event_shape");
    events.insert(events.end() - 2, callback_entry{"probe_invalid"});
    events.insert(events.end() - 1, callback_entry{"check_pool"});
    events.push_back(callback_entry{"check_chain"});
    const auto generated = std::chrono::steady_clock::now();
    observations << "generation_seconds\t" << std::chrono::duration<double>(generated - start).count() << '\n';

    boost::program_options::options_description desc("core");
    core::init_options(desc);
    const std::vector<std::string> args{"--data-dir=" + std::string(argv[1]), "--offline", "--disable-dns-checkpoints", "--fast-block-sync=0"};
    boost::program_options::variables_map vm;
    boost::program_options::store(boost::program_options::command_line_parser(args).options(desc).run(), vm);
    boost::program_options::notify(vm);
    get_test_options<gen_fcmp_pp_tx_from_bpp> options;
    core c(nullptr);
    require(c.init(vm, &options.test_options, nullptr, false), "initialize_isolated_core");
    require(c.get_nettype() == FAKECHAIN, "core_is_fakechain");
    c.get_blockchain_storage().get_db().set_batch_transactions(true);
    VanguardAdmission validator;
    const bool replayed = replay_events_through_core(c, events, validator);
    c.deinit();
    tools::threadpool::getInstanceForCompute().recycle();
    require(replayed, "replay_through_core");
    observations << "replay_seconds\t" << std::chrono::duration<double>(std::chrono::steady_clock::now() - generated).count() << '\n';
    require(bool(results) && bool(observations), "receipt_streams_ok");
    return 0;
  }
  catch (const std::exception& error)
  {
    std::cerr << error.what() << std::endl;
    return 1;
  }
}
