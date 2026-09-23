// Vanguard V1 (TJS-356): positive and negative vectors over the pinned upstream FCMP++ and
// CARROT primitives. Every call below goes to the upstream library code (src/fcmp_pp,
// src/carrot_core, src/cryptonote_basic); this file only drives it and records verdicts.
//
// results.json holds only run-independent facts (vector ids, expected/observed verdicts,
// sizes, deterministic addresses) so two runs must be byte-identical. Timings and peak
// RSS go to metrics.json.

#include "carrot_core/account_secrets.h"
#include "carrot_core/destination.h"
#include "carrot_core/device_ram_borrowed.h"
#include "carrot_core/enote_utils.h"
#include "carrot_core/payment_proposal.h"
#include "carrot_core/scan.h"
#include "crypto/crypto.h"
#include "crypto/generators.h"
#include "cryptonote_basic/cryptonote_basic_impl.h"
#include "curve_trees.h"
#include "fcmp_pp/curve_trees.h"
#include "fcmp_pp/fcmp_pp_types.h"
#include "fcmp_pp/prove.h"
#include "fcmp_pp/tower_cycle.h"
#include "ringct/rctOps.h"
#include "string_tools.h"
#include "unit_tests_utils.h"

#include <sys/resource.h>
#include <sys/wait.h>
#include <unistd.h>

#include <chrono>
#include <cstring>
#include <fstream>
#include <functional>
#include <iostream>
#include <set>
#include <sstream>
#include <string>
#include <vector>

namespace
{
//----------------------------------------------------------------------------------------------------------------------
// Verdict recording
//----------------------------------------------------------------------------------------------------------------------
struct Vector
{
    std::string id;
    std::string expect;   // "accept" | "reject"
    std::string observed; // "accept" | "reject_false" | "reject_exception" | "reject_abort_signal_<n>"
                          // | "reject" (verdict class only, for random-input vectors)
    std::string detail;
    std::string finding;  // non-empty when observed differs from expect in a documented way
};

// Observed deviations from the ideal verdict that are documented in the Vanguard report,
// keyed by FCMP++ vector id suffix. A vector is marked with the finding only when the exact
// observed verdict reproduces; otherwise it is judged against its expectation as usual.
struct KnownDeviation
{
    const char *suffix;
    const char *observed;
    const char *finding;
};
const KnownDeviation KNOWN_DEVIATIONS[] = {
    // fcmp_pp_rust fcmp_pp_verify_input_new only debug_asserts the proof length; consensus
    // enforces it separately in is_canonical_fcmp_plus_plus_layout.
    {".extended_1_byte", "accept", "VG-F1"},
    // Rust panic "claimed root is on a distinct layer than tree root" aborts the process;
    // consensus binds n_tree_layers to the stored root before verifying.
    {".wrong_n_layers_minus_1", "reject_abort_signal_6", "VG-F2"},
};

// Vectors whose proofs and keys are generated per run from fresh randomness. Which reject path
// upstream takes can depend on those bytes (VG-F2's panic is reached only when misaligned
// commitments still decode as points), so results.json records just the verdict class for them
// and metrics.json keeps the raw observation.
const char *const RANDOM_INPUT_PREFIXES[] = {"fcmp_pp.fresh", "sal."};

std::vector<Vector> g_vectors;
std::vector<std::pair<std::string, double>> g_timings;
std::vector<std::pair<std::string, std::string>> g_random_input_observed;

bool random_input(const std::string &id)
{
    for (const char *prefix : RANDOM_INPUT_PREFIXES)
        if (id.rfind(prefix, 0) == 0)
            return true;
    return false;
}

std::string observe(const std::function<bool()> &check)
{
    try
    {
        return check() ? "accept" : "reject_false";
    }
    catch (const std::exception &e)
    {
        std::cout << "  (exception: " << e.what() << ")" << std::endl;
        return "reject_exception";
    }
    catch (...)
    {
        return "reject_exception";
    }
}

// Negative vectors run in a forked child so that a panic or abort inside the upstream code is
// recorded as a verdict instead of ending the run.
std::string observe_isolated(const std::function<bool()> &check)
{
    std::cout << std::flush;
    std::cerr << std::flush;
    const pid_t pid = fork();
    if (pid < 0)
        return observe(check);
    if (pid == 0)
    {
        const rlimit no_core{0, 0};
        setrlimit(RLIMIT_CORE, &no_core);
        const std::string o = observe(check);
        std::cout << std::flush;
        _exit(o == "accept" ? 10 : o == "reject_false" ? 11 : 12);
    }
    int status = 0;
    if (waitpid(pid, &status, 0) != pid)
        return "child_wait_failed";
    if (WIFSIGNALED(status))
        return "reject_abort_signal_" + std::to_string(WTERMSIG(status));
    switch (WIFEXITED(status) ? WEXITSTATUS(status) : -1)
    {
    case 10: return "accept";
    case 11: return "reject_false";
    case 12: return "reject_exception";
    default: return "child_exit_" + std::to_string(WIFEXITED(status) ? WEXITSTATUS(status) : -1);
    }
}

bool verdict_matches(const Vector &v)
{
    return v.expect == "accept" ? v.observed == "accept" : v.observed.rfind("reject", 0) == 0;
}

bool passed(const Vector &v)
{
    return v.finding.empty() ? verdict_matches(v) : true;
}

void record(const std::string &id, const std::string &expect, const std::function<bool()> &check,
    const std::string &detail = "")
{
    const std::string raw = expect == "reject" ? observe_isolated(check) : observe(check);
    Vector v{id, expect, raw, detail, ""};
    if (random_input(id))
    {
        g_random_input_observed.emplace_back(id, raw);
        if (raw.rfind("reject", 0) == 0)
            v.observed = "reject";
    }
    for (const KnownDeviation &d : KNOWN_DEVIATIONS)
    {
        const std::string suffix = d.suffix;
        if (id.rfind("fcmp_pp.", 0) == 0 && id.size() >= suffix.size()
            && id.compare(id.size() - suffix.size(), suffix.size(), suffix) == 0 && v.observed == d.observed)
            v.finding = d.finding;
    }
    std::cout << (passed(v) ? (v.finding.empty() ? "PASS " : "KNOWN ") : "FAIL ") << v.id
        << " expect=" << v.expect << " observed=" << v.observed << (raw == v.observed ? "" : " raw=" + raw)
        << (v.finding.empty() ? "" : " finding=" + v.finding) << (detail.empty() ? "" : " " + detail) << std::endl;
    g_vectors.push_back(std::move(v));
}

template <typename F>
auto timed(const std::string &label, F &&f)
{
    const auto start = std::chrono::steady_clock::now();
    auto r = f();
    const auto end = std::chrono::steady_clock::now();
    g_timings.emplace_back(label, std::chrono::duration<double>(end - start).count());
    return r;
}

std::string json_escape(const std::string &s)
{
    std::string o;
    for (const char c : s)
    {
        if (c == '"' || c == '\\') o += '\\';
        o += c;
    }
    return o;
}

template <typename T>
std::string hex(const T &pod)
{
    return epee::string_tools::pod_to_hex(pod);
}

std::vector<std::size_t> flip_offsets(const std::size_t size)
{
    return {0, size / 2, size - 1};
}

//----------------------------------------------------------------------------------------------------------------------
// Section A: upstream fixed FCMP++ verify vectors (tests/data/fcmp_pp_verify_inputs_*in.bin at the pin)
//----------------------------------------------------------------------------------------------------------------------
void fixed_fcmp_pp_vectors()
{
    const auto curve_trees = fcmp_pp::curve_trees::curve_trees_v1();

    for (const std::size_t n_inputs : {1, 2, 4, 8, 128})
    {
        const std::string p = "fcmp_pp.fixed_" + std::to_string(n_inputs) + "in.";

        crypto::hash signable_tx_hash;
        fcmp_pp::FcmpPpProof proof;
        uint8_t n_layers = 0;
        fcmp_pp::TreeRootShared tree_root;
        std::vector<crypto::ec_point> pseudo_outs;
        std::vector<crypto::key_image> key_images;
        if (!unit_test::read_fcmp_pp_verify_input_from_file(n_inputs, signable_tx_hash, proof, n_layers,
                tree_root, pseudo_outs, key_images))
        {
            record(p + "load", "accept", [] { return false; }, "upstream vector file missing or malformed");
            continue;
        }

        const std::size_t membership_len = fcmp_pp::membership_proof_len(n_inputs, n_layers);
        const std::size_t sal_region = (FCMP_PP_INPUT_TUPLE_SIZE_V1 + FCMP_PP_SAL_PROOF_SIZE_V1) * n_inputs;
        std::ostringstream shape;
        shape << "proof_bytes=" << proof.size() << " n_layers=" << unsigned(n_layers)
              << " membership_bytes=" << membership_len << " per_input_region_bytes=" << sal_region
              << " layout_ok=" << (proof.size() == sal_region + membership_len ? "true" : "false");

        const auto verify = [&](const crypto::hash &h, const fcmp_pp::FcmpPpProof &pr, const uint8_t nl,
            const fcmp_pp::TreeRootShared &root, const std::vector<crypto::ec_point> &po,
            const std::vector<crypto::key_image> &ki)
        {
            return [=] { return fcmp_pp::verify(h, pr, nl, root, po, ki); };
        };

        record(p + "valid", "accept",
            [&, check = verify(signable_tx_hash, proof, n_layers, tree_root, pseudo_outs, key_images)]
            { return timed(p + "verify_seconds", check); },
            shape.str());

        // one-bit flips: input tuple of input 0, SA/L proof of input 0, and the membership proof
        const std::vector<std::pair<std::string, std::size_t>> flips = {
            {"flip_input_tuple_byte0", 0},
            {"flip_sal_proof_byte0", FCMP_PP_INPUT_TUPLE_SIZE_V1},
            {"flip_membership_first_byte", sal_region},
            {"flip_membership_middle_byte", sal_region + membership_len / 2},
            {"flip_membership_last_byte", proof.size() - 1}};
        for (const auto &f : flips)
        {
            fcmp_pp::FcmpPpProof mutated = proof;
            mutated.at(f.second) ^= 0x01;
            record(p + f.first, "reject", verify(signable_tx_hash, mutated, n_layers, tree_root, pseudo_outs, key_images),
                "offset=" + std::to_string(f.second));
        }

        fcmp_pp::FcmpPpProof truncated(proof.begin(), proof.end() - 1);
        record(p + "truncated_1_byte", "reject", verify(signable_tx_hash, truncated, n_layers, tree_root, pseudo_outs, key_images));

        fcmp_pp::FcmpPpProof extended = proof;
        extended.push_back(0);
        record(p + "extended_1_byte", "reject", verify(signable_tx_hash, extended, n_layers, tree_root, pseudo_outs, key_images));

        // A valid curve point that is not this tree's root: the hash-init point of the root's curve
        const fcmp_pp::TreeRootShared wrong_root = n_layers % 2 == 0
            ? fcmp_pp::helios_tree_root(curve_trees->m_c2->hash_init_point())
            : fcmp_pp::selene_tree_root(curve_trees->m_c1->hash_init_point());
        record(p + "wrong_tree_root", "reject", verify(signable_tx_hash, proof, n_layers, wrong_root, pseudo_outs, key_images));

        record(p + "wrong_n_layers_plus_1", "reject",
            verify(signable_tx_hash, proof, n_layers + 1, tree_root, pseudo_outs, key_images));
        record(p + "wrong_n_layers_minus_1", "reject",
            verify(signable_tx_hash, proof, n_layers - 1, tree_root, pseudo_outs, key_images));

        crypto::hash wrong_hash = signable_tx_hash;
        wrong_hash.data[0] ^= 0x01;
        record(p + "wrong_signable_tx_hash", "reject", verify(wrong_hash, proof, n_layers, tree_root, pseudo_outs, key_images));

        std::vector<crypto::key_image> wrong_ki = key_images;
        wrong_ki[0] = rct::rct2ki(rct::scalarmultBase(rct::d2h(7)));
        record(p + "wrong_key_image", "reject", verify(signable_tx_hash, proof, n_layers, tree_root, pseudo_outs, wrong_ki));

        std::vector<crypto::ec_point> wrong_po = pseudo_outs;
        wrong_po[0] = rct::rct2pt(rct::scalarmultBase(rct::d2h(11)));
        record(p + "wrong_pseudo_out", "reject", verify(signable_tx_hash, proof, n_layers, tree_root, wrong_po, key_images));

        if (n_inputs >= 2)
        {
            std::vector<crypto::key_image> swapped_ki = key_images;
            std::swap(swapped_ki[0], swapped_ki[1]);
            record(p + "swapped_key_images", "reject", verify(signable_tx_hash, proof, n_layers, tree_root, pseudo_outs, swapped_ki));

            std::vector<crypto::ec_point> swapped_po = pseudo_outs;
            std::swap(swapped_po[0], swapped_po[1]);
            record(p + "swapped_pseudo_outs", "reject", verify(signable_tx_hash, proof, n_layers, tree_root, swapped_po, key_images));
        }
    }
}

//----------------------------------------------------------------------------------------------------------------------
// Section B: fresh membership proofs over a fresh in-memory curve tree (mirrors upstream
// TEST(fcmp_pp, membership_completeness) at the pin, with added negative cases)
//----------------------------------------------------------------------------------------------------------------------
struct FreshInput
{
    fcmp_pp::FcmpPpProveMembershipInput provable;
    FcmpInputCompressed raw;
    fcmp_pp::OutputTuple tuple;
};

FreshInput make_fresh_input(const CurveTreesGlobalTree &tree, CurveTreesV1 &curve_trees, const std::size_t leaf_idx,
    const std::vector<fcmp_pp::SeleneBranchBlind> &selene_branch_blinds,
    const std::vector<fcmp_pp::HeliosBranchBlind> &helios_branch_blinds)
{
    const auto path = tree.get_path_at_leaf_idx(leaf_idx);
    const std::size_t output_idx = leaf_idx % curve_trees.m_c1_width;

    const fcmp_pp::OutputPair output_pair = fcmp_pp::LegacyOutputPair{{
        (crypto::public_key&)path.leaves[output_idx].O,
        (crypto::ec_point&)path.leaves[output_idx].C}};
    const auto output_tuple = fcmp_pp::curve_trees::output_to_tuple(output_pair);
    const auto path_for_proof = curve_trees.path_for_proof(path, output_tuple);

    const auto helios_scalar_chunks = fcmp_pp::tower_cycle::scalar_chunks_to_chunk_vector<fcmp_pp::HeliosT>(
        path_for_proof.c2_scalar_chunks);
    const auto selene_scalar_chunks = fcmp_pp::tower_cycle::scalar_chunks_to_chunk_vector<fcmp_pp::SeleneT>(
        path_for_proof.c1_scalar_chunks);

    const auto path_rust = fcmp_pp::path_new({path_for_proof.leaves.data(), path_for_proof.leaves.size()},
        path_for_proof.output_idx,
        {helios_scalar_chunks.data(), helios_scalar_chunks.size()},
        {selene_scalar_chunks.data(), selene_scalar_chunks.size()});

    const FcmpRerandomizedOutputCompressed rerandomized_output = fcmp_pp::rerandomize_output(output_tuple);

    const auto output_blinds = fcmp_pp::output_blinds_new(
        fcmp_pp::blind_o_blind(fcmp_pp::o_blind(rerandomized_output)),
        fcmp_pp::blind_i_blind(fcmp_pp::i_blind(rerandomized_output)),
        fcmp_pp::blind_i_blind_blind(fcmp_pp::i_blind_blind(rerandomized_output)),
        fcmp_pp::blind_c_blind(fcmp_pp::c_blind(rerandomized_output)));

    return FreshInput{
        fcmp_pp::fcmp_pp_prove_input_new(path_rust, output_blinds, selene_branch_blinds, helios_branch_blinds),
        rerandomized_output.input,
        output_tuple};
}

void fresh_membership_vectors()
{
    static const std::size_t selene_chunk_width = fcmp_pp::curve_trees::SELENE_CHUNK_WIDTH;
    static const std::size_t helios_chunk_width = fcmp_pp::curve_trees::HELIOS_CHUNK_WIDTH;
    static const std::size_t tree_depth = 3;
    static const std::size_t n_layers = 1 + tree_depth;

    uint64_t n_leaves = 0;
    const auto curve_trees = test::init_curve_trees_test(selene_chunk_width, helios_chunk_width, tree_depth, n_leaves);

    CurveTreesGlobalTree global_tree(*curve_trees);
    const bool grown = timed("fresh.tree_build_seconds", [&] {
        return global_tree.grow_tree(0, n_leaves, test::generate_random_outputs(0, n_leaves));
    });
    record("fcmp_pp.fresh.tree_build", "accept", [&] { return grown; },
        "leaves=" + std::to_string(n_leaves) + " depth=" + std::to_string(tree_depth));
    if (!grown)
        return;
    const fcmp_pp::TreeRootShared tree_root = global_tree.get_tree_root();

    std::vector<fcmp_pp::SeleneBranchBlind> selene_branch_blinds;
    for (std::size_t i = 0; i < (tree_depth + 1) / 2; ++i)
        selene_branch_blinds.emplace_back(fcmp_pp::gen_selene_branch_blind());
    std::vector<fcmp_pp::HeliosBranchBlind> helios_branch_blinds;
    for (std::size_t i = 0; i < tree_depth / 2; ++i)
        helios_branch_blinds.emplace_back(fcmp_pp::gen_helios_branch_blind());

    for (const std::size_t n_inputs : {1, 2})
    {
        const std::string p = "fcmp_pp.fresh_" + std::to_string(n_inputs) + "in.";

        std::set<std::size_t> used;
        std::vector<fcmp_pp::FcmpPpProveMembershipInput> provable;
        std::vector<FcmpInputCompressed> raw;
        std::vector<fcmp_pp::OutputTuple> tuples;
        while (used.size() < n_inputs)
        {
            const std::size_t leaf_idx = crypto::rand_idx(global_tree.get_n_leaf_tuples());
            if (!used.insert(leaf_idx).second)
                continue;
            FreshInput in = make_fresh_input(global_tree, *curve_trees, leaf_idx, selene_branch_blinds, helios_branch_blinds);
            provable.push_back(std::move(in.provable));
            raw.push_back(in.raw);
            tuples.push_back(in.tuple);
        }

        const fcmp_pp::FcmpMembershipProof proof = timed(p + "prove_seconds",
            [&] { return fcmp_pp::prove_membership(provable, n_layers); });
        const std::size_t expected_len = fcmp_pp::membership_proof_len(n_inputs, n_layers);

        const auto verify = [&](const fcmp_pp::FcmpMembershipProof &pr, const std::size_t nl,
            const fcmp_pp::TreeRootShared &root, const std::vector<FcmpInputCompressed> &ins)
        {
            return [=] { return fcmp_pp::verify_membership(pr, nl, root, ins); };
        };

        record(p + "valid", "accept",
            [&, check = verify(proof, n_layers, tree_root, raw)] { return timed(p + "verify_seconds", check); },
            "proof_bytes=" + std::to_string(proof.size()) + " expected_bytes=" + std::to_string(expected_len)
            + " n_layers=" + std::to_string(n_layers));

        for (const std::size_t off : flip_offsets(proof.size()))
        {
            fcmp_pp::FcmpMembershipProof mutated = proof;
            mutated.at(off) ^= 0x01;
            record(p + "flip_byte_" + std::to_string(off), "reject", verify(mutated, n_layers, tree_root, raw));
        }

        record(p + "truncated_1_byte", "reject",
            verify(fcmp_pp::FcmpMembershipProof(proof.begin(), proof.end() - 1), n_layers, tree_root, raw));
        fcmp_pp::FcmpMembershipProof extended = proof;
        extended.push_back(0);
        record(p + "extended_1_byte", "reject", verify(extended, n_layers, tree_root, raw));

        record(p + "wrong_n_layers_plus_1", "reject", verify(proof, n_layers + 1, tree_root, raw));
        record(p + "wrong_n_layers_minus_1", "reject", verify(proof, n_layers - 1, tree_root, raw));

        // Same output, fresh rerandomization: a different (but honest) input the proof was not made for
        std::vector<FcmpInputCompressed> rererandomized = raw;
        rererandomized[0] = fcmp_pp::rerandomize_output(tuples[0]).input;
        record(p + "rererandomized_input", "reject", verify(proof, n_layers, tree_root, rererandomized));

        // Rerandomization of an output that is not in the tree
        std::vector<FcmpInputCompressed> non_member = raw;
        const auto outsider = test::generate_random_outputs(0, 1).at(0);
        non_member[0] = fcmp_pp::rerandomize_output(fcmp_pp::curve_trees::output_to_tuple(outsider.output_pair)).input;
        record(p + "non_member_input", "reject", verify(proof, n_layers, tree_root, non_member));

        std::vector<FcmpInputCompressed> flipped_input = raw;
        flipped_input[0].C_tilde[0] ^= 0x01;
        record(p + "flip_input_C_tilde_byte0", "reject", verify(proof, n_layers, tree_root, flipped_input));

        if (n_inputs >= 2)
        {
            std::vector<FcmpInputCompressed> swapped = raw;
            std::swap(swapped[0], swapped[1]);
            record(p + "swapped_inputs", "reject", verify(proof, n_layers, tree_root, swapped));
        }
    }

    // Grow the tree by one leaf; a proof for the old root must not verify against the new root
    const std::size_t old_n = global_tree.get_n_leaf_tuples();
    FreshInput leaf0 = make_fresh_input(global_tree, *curve_trees, 0, selene_branch_blinds, helios_branch_blinds);
    std::vector<fcmp_pp::FcmpPpProveMembershipInput> provable_one;
    provable_one.push_back(std::move(leaf0.provable));
    const fcmp_pp::FcmpMembershipProof proof_old_root = fcmp_pp::prove_membership(provable_one, n_layers);
    const bool regrown = global_tree.grow_tree(old_n, 1, test::generate_random_outputs(old_n, 1));
    const fcmp_pp::TreeRootShared new_root = global_tree.get_tree_root();
    record("fcmp_pp.fresh_1in.old_root_proof_vs_old_root", "accept",
        [&] { return fcmp_pp::verify_membership(proof_old_root, n_layers, tree_root, {leaf0.raw}); });
    record("fcmp_pp.fresh_1in.old_root_proof_vs_grown_root", "reject",
        [&] { return regrown && fcmp_pp::verify_membership(proof_old_root, n_layers, new_root, {leaf0.raw}); },
        std::string("grew_by=1 grow_ok=") + (regrown ? "true" : "false"));
}

//----------------------------------------------------------------------------------------------------------------------
// Section C: spend-authorization + linkability (SA/L) proofs
//----------------------------------------------------------------------------------------------------------------------
void sal_vectors()
{
    const rct::key x = rct::skGen();
    const rct::key y = rct::skGen();
    rct::key O;
    rct::addKeys2(O, x, y, rct::pk2rct(crypto::get_T())); // O = x G + y T
    crypto::ec_point I;
    crypto::derive_key_image_generator(rct::rct2pk(O), true, I);
    const rct::key C = rct::pkGen();
    crypto::key_image L;
    crypto::generate_key_image(rct::rct2pk(O), rct::rct2sk(x), L);

    const auto output = fcmp_pp::output_tuple_from_bytes(rct::rct2pt(O), I, rct::rct2pt(C));
    const FcmpRerandomizedOutputCompressed rerandomized_output{fcmp_pp::rerandomize_output(output)};
    const crypto::hash h = crypto::rand<crypto::hash>();

    const auto sal = timed("sal.prove_seconds", [&] {
        return fcmp_pp::prove_sal(h, rct::rct2sk(x), rct::rct2sk(y), rerandomized_output);
    });

    const auto verify = [&](const crypto::hash &hh, const FcmpInputCompressed &in, const crypto::key_image &ki,
        const fcmp_pp::FcmpPpSalProof &pr)
    {
        return [=] { return fcmp_pp::verify_sal(hh, in, ki, pr); };
    };

    record("sal.valid", "accept", verify(h, rerandomized_output.input, L, sal.first),
        std::string("proof_bytes=") + std::to_string(sal.first.size())
        + " key_image_matches_legacy=" + (sal.second == L ? "true" : "false"));

    crypto::hash wrong_h = h;
    wrong_h.data[31] ^= 0x01;
    record("sal.wrong_signable_tx_hash", "reject", verify(wrong_h, rerandomized_output.input, L, sal.first));

    crypto::key_image other_L;
    crypto::generate_key_image(rct::rct2pk(O), rct::rct2sk(rct::skGen()), other_L);
    record("sal.wrong_key_image", "reject", verify(h, rerandomized_output.input, other_L, sal.first));

    for (const std::size_t off : flip_offsets(sal.first.size()))
    {
        fcmp_pp::FcmpPpSalProof mutated = sal.first;
        mutated.at(off) ^= 0x01;
        record("sal.flip_byte_" + std::to_string(off), "reject", verify(h, rerandomized_output.input, L, mutated));
    }

    const FcmpRerandomizedOutputCompressed other_rerandomization{fcmp_pp::rerandomize_output(output)};
    record("sal.other_rerandomization_of_same_output", "reject",
        verify(h, other_rerandomization.input, L, sal.first));

    // Wrong spend key: the prover is handed x' with O != x' G + y T
    record("sal.prove_with_wrong_x", "reject", [&] {
        const auto bad = fcmp_pp::prove_sal(h, rct::rct2sk(rct::skGen()), rct::rct2sk(y), rerandomized_output);
        return fcmp_pp::verify_sal(h, rerandomized_output.input, bad.second, bad.first)
            || fcmp_pp::verify_sal(h, rerandomized_output.input, L, bad.first);
    });
}

//----------------------------------------------------------------------------------------------------------------------
// Section D/E: CARROT key hierarchy, address encode/decode, and receiver scanning
//----------------------------------------------------------------------------------------------------------------------
struct CarrotAccount
{
    crypto::secret_key s_master, k_prove_spend, s_view_balance, s_generate_image_preimage, k_generate_image,
        k_view_incoming, s_generate_address;
    crypto::public_key partial_spend_pubkey, account_spend_pubkey, account_view_pubkey, primary_view_pubkey;
};

// Deterministic, valueless test accounts: s_master = H_keccak("meownero-vanguard-tjs356/" + name)
CarrotAccount make_account(const std::string &name)
{
    CarrotAccount a;
    const std::string label = "meownero-vanguard-tjs356/" + name;
    crypto::hash h;
    crypto::cn_fast_hash(label.data(), label.size(), h);
    memcpy(a.s_master.data, h.data, sizeof(h.data));

    carrot::make_carrot_provespend_key(a.s_master, a.k_prove_spend);
    carrot::make_carrot_partial_spend_pubkey(a.k_prove_spend, a.partial_spend_pubkey);
    carrot::make_carrot_viewbalance_secret(a.s_master, a.s_view_balance);
    carrot::make_carrot_generateimage_preimage(a.s_view_balance, a.s_generate_image_preimage);
    carrot::make_carrot_generateimage_key(a.s_generate_image_preimage, a.partial_spend_pubkey, a.k_generate_image);
    carrot::make_carrot_viewincoming_key(a.s_view_balance, a.k_view_incoming);
    carrot::make_carrot_generateaddress_secret(a.s_view_balance, a.s_generate_address);
    carrot::make_carrot_spend_pubkey(a.k_generate_image, a.k_prove_spend, a.account_spend_pubkey);
    a.account_view_pubkey = rct::rct2pk(rct::scalarmultKey(rct::pk2rct(a.account_spend_pubkey), rct::sk2rct(a.k_view_incoming)));
    crypto::secret_key_to_public_key(a.k_view_incoming, a.primary_view_pubkey);
    return a;
}

carrot::CarrotDestinationV1 main_address(const CarrotAccount &a)
{
    carrot::CarrotDestinationV1 d;
    carrot::make_carrot_main_address_v1(a.account_spend_pubkey, a.primary_view_pubkey, d);
    return d;
}

carrot::CarrotDestinationV1 subaddress(const CarrotAccount &a, const uint32_t major, const uint32_t minor)
{
    carrot::generate_address_secret_ram_borrowed_device s_ga_dev(a.s_generate_address);
    carrot::CarrotDestinationV1 d;
    carrot::make_carrot_subaddress_v1(a.account_spend_pubkey, a.account_view_pubkey, s_ga_dev, major, minor, d);
    return d;
}

std::string encode(const cryptonote::network_type net, const carrot::CarrotDestinationV1 &d)
{
    cryptonote::account_public_address adr{d.address_spend_pubkey, d.address_view_pubkey};
    if (d.payment_id != carrot::null_payment_id)
    {
        crypto::hash8 pid;
        memcpy(pid.data, d.payment_id.bytes, sizeof(pid.data));
        return cryptonote::get_account_integrated_address_as_str(net, adr, pid);
    }
    return cryptonote::get_account_address_as_str(net, d.is_subaddress, adr);
}

bool decodes_to(const cryptonote::network_type net, const std::string &s, const carrot::CarrotDestinationV1 &d)
{
    cryptonote::address_parse_info info;
    if (!cryptonote::get_account_address_from_str(info, net, s))
        return false;
    const bool has_pid = d.payment_id != carrot::null_payment_id;
    return info.address.m_spend_public_key == d.address_spend_pubkey
        && info.address.m_view_public_key == d.address_view_pubkey
        && info.is_subaddress == d.is_subaddress
        && info.has_payment_id == has_pid
        && (!has_pid || memcmp(info.payment_id.data, d.payment_id.bytes, sizeof(info.payment_id.data)) == 0);
}

const char *net_name(const cryptonote::network_type net)
{
    switch (net)
    {
    case cryptonote::MAINNET: return "mainnet";
    case cryptonote::TESTNET: return "testnet";
    case cryptonote::STAGENET: return "stagenet";
    default: return "other";
    }
}

void carrot_address_vectors(const CarrotAccount &alice)
{
    carrot::payment_id_t pid;
    for (std::size_t i = 0; i < sizeof(pid.bytes); ++i)
        pid.bytes[i] = static_cast<unsigned char>(0xa0 + i);
    carrot::CarrotDestinationV1 integrated;
    carrot::make_carrot_integrated_address_v1(alice.account_spend_pubkey, alice.primary_view_pubkey, pid, integrated);

    const std::vector<std::pair<std::string, carrot::CarrotDestinationV1>> destinations = {
        {"main", main_address(alice)},
        {"subaddress_1_0", subaddress(alice, 1, 0)},
        {"subaddress_2_7", subaddress(alice, 2, 7)},
        {"integrated", integrated}};
    const std::vector<cryptonote::network_type> nets = {cryptonote::MAINNET, cryptonote::TESTNET, cryptonote::STAGENET};

    // Key-hierarchy consistency: the main address view key is k_v G, and a subaddress re-derived
    // from s_ga matches the one derived earlier
    record("carrot.keys.main_view_pubkey_is_kv_G", "accept",
        [&] { return destinations[0].second.address_view_pubkey == alice.primary_view_pubkey; },
        "K_s=" + hex(alice.account_spend_pubkey) + " K0_v=" + hex(alice.primary_view_pubkey));
    record("carrot.keys.subaddress_rederivation_stable", "accept",
        [&] { return subaddress(alice, 2, 7) == destinations[2].second && !(destinations[1].second == destinations[2].second); });

    for (const auto &nd : destinations)
    {
        for (const auto net : nets)
        {
            const std::string p = std::string("carrot.address.") + nd.first + "." + net_name(net) + ".";
            const std::string s = encode(net, nd.second);
            record(p + "round_trip", "accept", [&] { return decodes_to(net, s, nd.second); }, "address=" + s);

            for (const auto other : nets)
                if (other != net)
                    record(p + "decoded_as_" + net_name(other), "reject", [&] { return decodes_to(other, s, nd.second); });

            // Corrupt the final base58 character (checksum block)
            static const std::string alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";
            std::string corrupted = s;
            corrupted.back() = alphabet[(alphabet.find(s.back()) + 1) % alphabet.size()];
            record(p + "checksum_char_changed", "reject", [&] { return decodes_to(net, corrupted, nd.second); });
            record(p + "truncated_1_char", "reject", [&] { return decodes_to(net, s.substr(0, s.size() - 1), nd.second); });
        }
    }

    // An address whose spend key bytes are not a valid ed25519 point must not decode
    std::size_t idx = 0;
    crypto::public_key not_a_point;
    for (;; ++idx)
    {
        const std::string label = "meownero-vanguard-tjs356/non-point/" + std::to_string(idx);
        crypto::hash h;
        crypto::cn_fast_hash(label.data(), label.size(), h);
        memcpy(not_a_point.data, h.data, sizeof(h.data));
        if (!crypto::check_key(not_a_point))
            break;
    }
    carrot::CarrotDestinationV1 bad = destinations[0].second;
    bad.address_spend_pubkey = not_a_point;
    const std::string bad_s = encode(cryptonote::TESTNET, bad);
    record("carrot.address.main.testnet.invalid_spend_point", "reject",
        [&] { return decodes_to(cryptonote::TESTNET, bad_s, bad); },
        "non_point_index=" + std::to_string(idx) + " spend_bytes=" + hex(not_a_point));
}

struct ScanOutcome
{
    bool ok = false;
    crypto::public_key address_spend_pubkey;
    rct::xmr_amount amount = 0;
    crypto::secret_key amount_blinding_factor;
};

ScanOutcome scan_as(const CarrotAccount &a, const carrot::CarrotEnoteV1 &enote,
    const carrot::encrypted_payment_id_t &encrypted_payment_id)
{
    ScanOutcome r;
    carrot::view_incoming_key_ram_borrowed_device k_view_dev(a.k_view_incoming);
    mx25519_pubkey s_sender_receiver;
    if (!carrot::try_make_carrot_shared_key_receiver(k_view_dev, enote.enote_ephemeral_pubkey, s_sender_receiver))
        return r;
    crypto::secret_key ext_g, ext_t;
    carrot::payment_id_t pid;
    carrot::CarrotEnoteType type;
    r.ok = carrot::try_scan_carrot_enote_external_receiver(enote, encrypted_payment_id, s_sender_receiver,
        {&a.account_spend_pubkey, 1}, k_view_dev, ext_g, ext_t, r.address_spend_pubkey, r.amount,
        r.amount_blinding_factor, pid, type);
    return r;
}

void carrot_scan_vectors(const CarrotAccount &alice, const CarrotAccount &bob)
{
    const rct::xmr_amount amount = 1234567;
    const crypto::key_image tx_first_key_image = rct::rct2ki(rct::scalarmultBase(rct::d2h(12345)));

    for (const auto &nd : std::vector<std::pair<std::string, carrot::CarrotDestinationV1>>{
             {"main", main_address(alice)}, {"subaddress_1_0", subaddress(alice, 1, 0)}})
    {
        const std::string p = "carrot.scan." + nd.first + ".";
        carrot::janus_anchor_t anchor;
        for (std::size_t i = 0; i < sizeof(anchor.bytes); ++i)
            anchor.bytes[i] = static_cast<unsigned char>(0x10 + i);
        const carrot::CarrotPaymentProposalV1 proposal{nd.second, amount, anchor};

        carrot::RCTOutputEnoteProposal enote_proposal;
        carrot::encrypted_payment_id_t encrypted_payment_id;
        carrot::get_output_proposal_normal_v1(proposal, tx_first_key_image, enote_proposal, encrypted_payment_id);
        const carrot::CarrotEnoteV1 &enote = enote_proposal.enote;

        record(p + "recipient_view_key", "accept", [&] {
            const ScanOutcome s = scan_as(alice, enote, encrypted_payment_id);
            return s.ok && s.address_spend_pubkey == nd.second.address_spend_pubkey && s.amount == amount
                && carrot::commit_carrot_amount(s.amount, s.amount_blinding_factor) == enote.amount_commitment;
        }, "amount=" + std::to_string(amount));

        record(p + "other_account_view_key", "reject", [&] { return scan_as(bob, enote, encrypted_payment_id).ok; });

        carrot::CarrotEnoteV1 tag = enote;
        tag.view_tag.bytes[0] ^= 0x01;
        record(p + "view_tag_flipped", "reject", [&] { return scan_as(alice, tag, encrypted_payment_id).ok; });

        carrot::CarrotEnoteV1 ctx = enote;
        ctx.tx_first_key_image = rct::rct2ki(rct::scalarmultBase(rct::d2h(54321)));
        record(p + "input_context_changed", "reject", [&] { return scan_as(alice, ctx, encrypted_payment_id).ok; });

        carrot::CarrotEnoteV1 commit = enote;
        const rct::key other_commitment = rct::scalarmultBase(rct::d2h(99));
        memcpy(commit.amount_commitment.data, other_commitment.bytes, sizeof(other_commitment.bytes));
        record(p + "amount_commitment_replaced", "reject", [&] { return scan_as(alice, commit, encrypted_payment_id).ok; });

        carrot::CarrotEnoteV1 amt = enote;
        amt.amount_enc.bytes[0] ^= 0x01;
        record(p + "encrypted_amount_flipped", "reject", [&] { return scan_as(alice, amt, encrypted_payment_id).ok; });
    }
}

//----------------------------------------------------------------------------------------------------------------------
void write_results(const std::string &path)
{
    std::size_t n_pass = 0, n_known = 0;
    std::ofstream o(path);
    o << "{\n  \"schema\": \"meownero-vanguard-results/1\",\n  \"vectors\": [\n";
    for (std::size_t i = 0; i < g_vectors.size(); ++i)
    {
        const Vector &v = g_vectors[i];
        n_pass += passed(v);
        n_known += !v.finding.empty();
        o << "    {\"id\": \"" << json_escape(v.id) << "\", \"expect\": \"" << v.expect << "\", \"observed\": \""
          << v.observed << "\", \"pass\": " << (passed(v) ? "true" : "false") << ", \"finding\": \"" << v.finding
          << "\", \"detail\": \"" << json_escape(v.detail) << "\"}" << (i + 1 < g_vectors.size() ? "," : "") << "\n";
    }
    o << "  ],\n  \"summary\": {\"total\": " << g_vectors.size() << ", \"passed\": " << n_pass
      << ", \"known_findings\": " << n_known << ", \"failed\": " << g_vectors.size() - n_pass << "}\n}\n";
}

void write_metrics(const std::string &path, const double total_seconds)
{
    rusage ru{}, children{};
    getrusage(RUSAGE_SELF, &ru);
    getrusage(RUSAGE_CHILDREN, &children);
    std::ofstream o(path);
    o << "{\n  \"schema\": \"meownero-vanguard-metrics/1\",\n  \"total_wall_seconds\": " << total_seconds
      << ",\n  \"peak_rss_kib\": " << ru.ru_maxrss << ",\n  \"isolated_children_peak_rss_kib\": "
      << children.ru_maxrss << ",\n  \"timings_seconds\": {";
    for (std::size_t i = 0; i < g_timings.size(); ++i)
        o << (i ? ", " : "") << "\"" << json_escape(g_timings[i].first) << "\": " << g_timings[i].second;
    o << "},\n  \"random_input_observed\": {";
    for (std::size_t i = 0; i < g_random_input_observed.size(); ++i)
        o << (i ? ", " : "") << "\"" << json_escape(g_random_input_observed[i].first) << "\": \""
          << g_random_input_observed[i].second << "\"";
    o << "}\n}\n";
}
} // namespace

int main(int argc, char **argv)
{
    std::string results = "results.json", metrics = "metrics.json";
    unit_test::data_dir = "tests/data";
    for (int i = 1; i < argc; ++i)
    {
        const std::string a = argv[i];
        if (a.rfind("--data-dir=", 0) == 0) unit_test::data_dir = a.substr(11);
        else if (a.rfind("--results=", 0) == 0) results = a.substr(10);
        else if (a.rfind("--metrics=", 0) == 0) metrics = a.substr(10);
        else { std::cerr << "unknown argument " << a << std::endl; return 2; }
    }

    const auto start = std::chrono::steady_clock::now();
    timed("section.fixed_fcmp_pp_seconds", [] { fixed_fcmp_pp_vectors(); return 0; });
    timed("section.fresh_membership_seconds", [] { fresh_membership_vectors(); return 0; });
    timed("section.sal_seconds", [] { sal_vectors(); return 0; });
    const CarrotAccount alice = make_account("alice");
    const CarrotAccount bob = make_account("bob");
    timed("section.carrot_address_seconds", [&] { carrot_address_vectors(alice); return 0; });
    timed("section.carrot_scan_seconds", [&] { carrot_scan_vectors(alice, bob); return 0; });
    const double total = std::chrono::duration<double>(std::chrono::steady_clock::now() - start).count();

    write_results(results);
    write_metrics(metrics, total);

    std::size_t failed = 0;
    for (const Vector &v : g_vectors)
        failed += !passed(v);
    std::cout << "vectors=" << g_vectors.size() << " failed=" << failed << std::endl;
    return failed == 0 ? 0 : 1;
}
