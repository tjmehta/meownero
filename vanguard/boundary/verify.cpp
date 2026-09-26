#include "verify.h"

#include "cryptonote_config.h"
#include "fcmp_pp/curve_trees.h"

namespace vanguard
{
namespace
{
bool valid_shape(std::size_t inputs, std::size_t claimed_layers, const TreeAnchor &anchor)
{
    // Bound before narrowing to uint8_t or calling Rust size arithmetic.
    return inputs > 0 && inputs <= FCMP_PLUS_PLUS_MAX_INPUTS
        && anchor.layers > 0 && anchor.layers <= FCMP_PLUS_PLUS_MAX_LAYERS
        && claimed_layers == anchor.layers;
}

fcmp_pp::TreeRootShared decode(const TreeAnchor &anchor)
{
    return fcmp_pp::curve_trees::curve_trees_v1()->get_tree_root_from_bytes(anchor.layers, anchor.root);
}
}

bool verify(const crypto::hash &message, const fcmp_pp::FcmpPpProof &proof,
    std::size_t claimed_layers, const TreeAnchor &anchor,
    const std::vector<crypto::ec_point> &pseudo_outs,
    const std::vector<crypto::key_image> &key_images)
{
    if (!valid_shape(pseudo_outs.size(), claimed_layers, anchor) || pseudo_outs.size() != key_images.size())
        return false;
    if (proof.size() != fcmp_pp::fcmp_pp_proof_len(pseudo_outs.size(), static_cast<uint8_t>(anchor.layers)))
        return false;
    try
    {
        const auto root = decode(anchor);
        return root && fcmp_pp::verify(message, proof, anchor.layers, root, pseudo_outs, key_images);
    }
    catch (const std::exception &)
    {
        // Upstream C++ decoding/FFI error codes can throw. Rust panics cannot be
        // caught here; shape and root-curve guards must run before entering it.
        return false;
    }
}

bool verify_membership(const fcmp_pp::FcmpMembershipProof &proof,
    std::size_t claimed_layers, const TreeAnchor &anchor,
    const std::vector<FcmpInputCompressed> &inputs)
{
    if (!valid_shape(inputs.size(), claimed_layers, anchor))
        return false;
    if (proof.size() != fcmp_pp::membership_proof_len(inputs.size(), static_cast<uint8_t>(anchor.layers)))
        return false;
    try
    {
        const auto root = decode(anchor);
        return root && fcmp_pp::verify_membership(proof, anchor.layers, root, inputs);
    }
    catch (const std::exception &)
    {
        return false;
    }
}
}
