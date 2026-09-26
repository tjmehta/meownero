#pragma once

#include "fcmp_pp/prove.h"

namespace vanguard
{
// The caller must obtain BOTH fields from trusted tree state for the reference
// block. Neither field authenticates itself. Do not populate this from a proof.
// Keep the compressed point: decoding here binds its curve to the stored depth.
struct TreeAnchor
{
    crypto::ec_point root;
    std::size_t layers;
};

bool verify(const crypto::hash &message, const fcmp_pp::FcmpPpProof &proof,
    std::size_t claimed_layers, const TreeAnchor &anchor,
    const std::vector<crypto::ec_point> &pseudo_outs,
    const std::vector<crypto::key_image> &key_images);

bool verify_membership(const fcmp_pp::FcmpMembershipProof &proof,
    std::size_t claimed_layers, const TreeAnchor &anchor,
    const std::vector<FcmpInputCompressed> &inputs);
}
