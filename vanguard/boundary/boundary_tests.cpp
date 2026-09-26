// Deterministic reproducer using the upstream tests/data FCMP++ files unchanged.
// Raw calls preserve VG-F1/VG-F2; guarded calls must return false, never abort.
#include "verify.h"
#include "fcmp_pp/curve_trees.h"
#include "serialization/binary_utils.h"
#include "serialization/containers.h"
#include "serialization/crypto.h"
#include <sys/resource.h>
#include <sys/wait.h>
#include <unistd.h>
#include <cerrno>
#include <csignal>
#include <cstring>
#include <fstream>
#include <functional>
#include <iostream>
#include <limits>

// Same serialized fields as upstream unit_tests_utils.cpp SerializableFcmpPpVerify.
struct Fixture
{
    crypto::hash message;
    uint8_t layers;
    fcmp_pp::FcmpPpProof proof;
    crypto::ec_point root;
    std::vector<crypto::ec_point> pseudo_outs;
    std::vector<crypto::key_image> key_images;
    BEGIN_SERIALIZE_OBJECT()
        FIELD(message) FIELD(layers) FIELD(proof) FIELD(root) FIELD(pseudo_outs) FIELD(key_images)
    END_SERIALIZE()
};

std::string observe(const std::function<bool()> &call)
{
    // A failed fork is a test failure, never an unsafe fallback into this process.
    std::cout.flush(); std::cerr.flush();
    const auto pid = fork();
    if (pid < 0) return "fork_failed";
    if (pid == 0)
    {
        const rlimit no_core{0, 0};
        if (setrlimit(RLIMIT_CORE, &no_core) != 0) _exit(13);
        alarm(45);
        try { _exit(call() ? 10 : 11); }
        catch (...) { _exit(12); }
    }
    int status = 0;
    pid_t waited;
    do { waited = waitpid(pid, &status, 0); } while (waited < 0 && errno == EINTR);
    if (waited != pid) return "wait_failed";
    if (WIFSIGNALED(status)) return "signal_" + std::to_string(WTERMSIG(status));
    if (WIFEXITED(status))
    {
        if (WEXITSTATUS(status) == 10) return "true";
        if (WEXITSTATUS(status) == 11) return "false";
        if (WEXITSTATUS(status) == 12) return "exception";
    }
    return "child_failed";
}

int main(int argc, char **argv)
{
    if (argc != 2) return 2;
    unsigned failures = 0;
    const auto trees = fcmp_pp::curve_trees::curve_trees_v1();
    for (const std::size_t count : {1, 2, 4, 8, 128})
    {
        std::ifstream file(std::string(argv[1]) + "/fcmp_pp_verify_inputs_" + std::to_string(count) + "in.bin", std::ios::binary);
        const std::string blob{std::istreambuf_iterator<char>(file), std::istreambuf_iterator<char>()};
        Fixture f{};
        if (!file || !serialization::parse_binary(blob, f) || f.pseudo_outs.size() != count
            || f.key_images.size() != count || f.layers != 7) return 3;
        const vanguard::TreeAnchor anchor{f.root, f.layers};
        const auto raw_root = trees->get_tree_root_from_bytes(f.layers, f.root);
        fcmp_pp::FcmpMembershipProof membership;
        std::vector<fcmp_pp::FcmpPpSalProof> sal;
        std::vector<FcmpInputCompressed> inputs;
        fcmp_pp::fcmp_pp_parts_from_proof_v1(f.proof, f.pseudo_outs, f.layers, membership, sal, inputs);
        const auto record = [&](const std::string &id, const std::string &expected, const std::function<bool()> &call)
        {
            const auto actual = observe(call);
            std::cout << count << "." << id << '\t' << expected << '\t' << actual << std::endl;
            failures += expected != actual;
        };
        for (const bool member : {false, true})
        {
            const std::string kind = member ? "membership." : "full.";
            const auto original = member ? membership : f.proof;
            auto proof = original;
            std::size_t layers = f.layers;
            auto root = anchor;
            auto po = f.pseudo_outs;
            auto ki = f.key_images;
            auto ins = inputs;
            const auto raw = [&] {
                return member ? fcmp_pp::verify_membership(proof, layers, raw_root, ins)
                    : fcmp_pp::verify(f.message, proof, layers, raw_root, po, ki);
            };
            const auto guarded = [&] {
                return member ? vanguard::verify_membership(proof, layers, root, ins)
                    : vanguard::verify(f.message, proof, layers, root, po, ki);
            };
            record(kind + "raw.valid", "true", raw);
            proof.push_back(0);
            record(kind + "raw.trailing", "true", raw);
            proof = original;
            if (!member)
            {
                layers = f.layers - 1;
                record(kind + "raw.layer_minus_1", count == 2 ? "false" : "signal_6", raw);
                layers = f.layers;
            }
            record(kind + "guard.valid", "true", guarded);
            proof.push_back(0);
            record(kind + "guard.trailing", "false", guarded);
            proof = original; proof.pop_back();
            record(kind + "guard.truncated", "false", guarded);
            proof = original; proof.back() ^= 1;
            record(kind + "guard.flip_last", "false", guarded);
            proof = original;
            for (const auto delta : {-2, -1, 1, 2})
            {
                layers = f.layers + delta;
                record(kind + "guard.layer_delta_" + std::to_string(delta), "false", guarded);
            }
            for (const std::size_t bad : {std::size_t(0), std::size_t(13), std::size_t(256), std::numeric_limits<std::size_t>::max()})
            {
                layers = bad;
                record(kind + "guard.claim_" + std::to_string(bad), "false", guarded);
                root.layers = bad;
                record(kind + "guard.anchor_" + std::to_string(bad), "false", guarded);
                root = anchor;
            }
            layers = f.layers;
            po.clear(); ki.clear(); ins.clear();
            record(kind + "guard.empty_inputs", "false", guarded);
            po.resize(129); ki.resize(129); ins.resize(129);
            record(kind + "guard.excess_inputs", "false", guarded);
            po = f.pseudo_outs; ki = f.key_images; ins = inputs;
            if (!member)
            {
                ki.pop_back();
                record(kind + "guard.mismatched_key_images", "false", guarded);
                ki = f.key_images;
            }
            // A valid point on the correct curve, but not the fixture's root.
            root.root = trees->m_c1->to_bytes(trees->m_c1->hash_init_point());
            record(kind + "guard.wrong_root", "false", guarded);
            std::memset(&root.root, 0xff, sizeof(root.root));
            record(kind + "guard.invalid_root", "false", guarded);
            root = anchor;
            record(kind + "guard.valid_after_rejections", "true", guarded);
        }
    }
    rusage children{};
    if (getrusage(RUSAGE_CHILDREN, &children) != 0) return 4;
    std::cerr << "children_max_rss_kib=" << children.ru_maxrss << '\n';
    return failures ? 1 : 0;
}
