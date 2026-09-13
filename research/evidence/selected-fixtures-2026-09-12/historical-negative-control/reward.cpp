#include <cassert>
#include "cryptonote_config.h"
#include "int-util.h"
#define MERROR(x) do {} while (0)
namespace cryptonote {
size_t get_min_block_weight(uint8_t version)
  {
    if (version < 2)
      return CRYPTONOTE_BLOCK_GRANTED_FULL_REWARD_ZONE_V1;
    if (version < 5)
      return CRYPTONOTE_BLOCK_GRANTED_FULL_REWARD_ZONE_V2;
    return CRYPTONOTE_BLOCK_GRANTED_FULL_REWARD_ZONE_V5;
  }
bool get_block_reward(size_t median_weight, size_t current_block_weight, uint64_t already_generated_coins, uint64_t &reward, uint8_t version) {
    static_assert(DIFFICULTY_TARGET_V2%60==0&&DIFFICULTY_TARGET_V1%60==0,"difficulty targets must be a multiple of 60");
    // Meownero: perpetual flat subsidy. Independent of already_generated_coins, hard-fork
    // version, and target spacing (PLAN.md rev 4 §8.1). The block-weight penalty below is
    // retained unchanged and is denominated in this constant.
    (void)already_generated_coins;
    uint64_t base_reward = MEOW_BLOCK_REWARD;

    uint64_t full_reward_zone = get_min_block_weight(version);

    //make it soft
    if (median_weight < full_reward_zone) {
      median_weight = full_reward_zone;
    }

    if (current_block_weight <= median_weight) {
      reward = base_reward;
      return true;
    }

    if(current_block_weight > 2 * median_weight) {
      MERROR("Block cumulative weight is too big: " << current_block_weight << ", expected less than " << 2 * median_weight);
      return false;
    }

    uint64_t product_hi;
    // BUGFIX: 32-bit saturation bug (e.g. ARM7), the result was being
    // treated as 32-bit by default.
    uint64_t multiplicand = 2 * median_weight - current_block_weight;
    multiplicand *= current_block_weight;
    uint64_t product_lo = mul128(base_reward, multiplicand, &product_hi);

    uint64_t reward_hi;
    uint64_t reward_lo;
    div128_64(product_hi, product_lo, median_weight, &reward_hi, &reward_lo, NULL, NULL);
    div128_64(reward_hi, reward_lo, median_weight, &reward_hi, &reward_lo, NULL, NULL);
    assert(0 == reward_hi);
    assert(reward_lo < base_reward);

    reward = reward_lo;
    return true;
  }
}
