// Meownero Candidate M control — emission unit tests.
// Replaces Monero's tests/unit_tests/block_reward.cpp (which encodes the Monero curve).
// Invariants under test (PLAN.md rev 4 §8.1, §8.2):
//   E1  reward is exactly MEOW_BLOCK_REWARD = 0.9 * COIN at every already_generated_coins value
//   E2  reward is independent of hard-fork version and of the 60s/120s target distinction
//   E3  block-weight penalty math is unchanged and is denominated in the constant
//   E4  supply(h) == h * MEOW_BLOCK_REWARD; the uint64 supply tally saturates (never wraps) at the
//       upstream MONEY_SUPPLY cap — horizon computed and asserted, not assumed
//   E5  dilution: year-N inflation of a flat schedule is 1/(N-1); no deflation exists at any height
#include "gtest/gtest.h"
#include "cryptonote_basic/cryptonote_basic_impl.h"
#include "cryptonote_config.h"

using namespace cryptonote;

namespace
{
  const uint64_t R = MEOW_BLOCK_REWARD;
  const size_t small_block = CRYPTONOTE_BLOCK_GRANTED_FULL_REWARD_ZONE_V1 / 2;

  uint64_t reward_at(uint64_t already_generated, uint8_t version = 1, size_t median = 0, size_t weight = small_block)
  {
    uint64_t r = 0;
    bool ok = get_block_reward(median, weight, already_generated, r, version);
    EXPECT_TRUE(ok);
    return r;
  }

  // ---------------------------------------------------------------- E1
  TEST(meow_emission, constant_is_0_9_meow)
  {
    ASSERT_EQ(R, UINT64_C(900000000000));
    ASSERT_EQ(R, (COIN * 9) / 10);
    ASSERT_EQ(CRYPTONOTE_DISPLAY_DECIMAL_POINT, 12);
  }

  TEST(meow_emission, reward_independent_of_supply)
  {
    const uint64_t probes[] = { 0, 1, R, R * 1000, UINT64_C(2756434948434199641),
                                MONEY_SUPPLY - R - 1, MONEY_SUPPLY - R, MONEY_SUPPLY - 1, MONEY_SUPPLY };
    for (uint64_t agc : probes)
      ASSERT_EQ(reward_at(agc), R) << "already_generated_coins=" << agc;
  }

  // ---------------------------------------------------------------- E2
  TEST(meow_emission, reward_independent_of_version)
  {
    for (uint8_t v = 1; v <= 16; ++v)
      ASSERT_EQ(reward_at(0, v), R) << "version " << int(v);
    ASSERT_EQ(reward_at(0, 1), reward_at(0, 2)); // V1 (60 s) vs V2 (120 s) target no longer matters
  }

  // ---------------------------------------------------------------- E3
  TEST(meow_emission, penalty_math_unchanged)
  {
    const size_t Z = CRYPTONOTE_BLOCK_GRANTED_FULL_REWARD_ZONE_V1;
    ASSERT_EQ(reward_at(0, 1, 0, Z), R);
    ASSERT_LT(reward_at(0, 1, 0, Z + 1), R);
    ASSERT_EQ(reward_at(0, 1, 0, 2 * Z), 0u);
    uint64_t r; ASSERT_FALSE(get_block_reward(0, 2 * Z + 1, 0, r, 1));

    // exact fractions against a median of 8 * Z (from upstream calculates_correctly)
    const size_t M = 8 * Z;
    ASSERT_EQ(reward_at(0, 1, M, M * 9 / 8),  R * 63 / 64);
    ASSERT_EQ(reward_at(0, 1, M, M * 3 / 2),  R * 3 / 4);
    ASSERT_EQ(reward_at(0, 1, M, M * 15 / 8), R * 15 / 64);
  }

  // ---------------------------------------------------------------- E4
  // Mirrors Blockchain::handle_block_to_main_chain's tally update:
  //   agc = (reward < MONEY_SUPPLY - agc) ? agc + reward : MONEY_SUPPLY
  uint64_t tally_step(uint64_t agc, uint64_t reward)
  {
    return (reward < (MONEY_SUPPLY - agc)) ? agc + reward : MONEY_SUPPLY;
  }

  TEST(meow_emission, supply_is_height_times_reward)
  {
    uint64_t agc = 0; // genesis pays 0 by consensus (construct_miner_tx / validate_miner_transaction)
    const uint64_t blocks_per_year = (365 * 24 * 3600) / DIFFICULTY_TARGET_V2; // 262,800
    ASSERT_EQ(blocks_per_year, UINT64_C(262800));
    for (uint64_t h = 1; h <= 10 * blocks_per_year; ++h)
    {
      agc = tally_step(agc, reward_at(agc));
      if (h % blocks_per_year == 0)
        ASSERT_EQ(agc, h * R) << "height " << h;
    }
    ASSERT_EQ(agc, UINT64_C(10) * 262800 * R); // 2,365,200 MEOW after 10 years
  }

  TEST(meow_emission, tally_saturates_and_never_wraps)
  {
    // Horizon: first height whose cumulative subsidy would exceed uint64::max.
    const uint64_t horizon = MONEY_SUPPLY / R; // 20,496,382 blocks ≈ 78.0 years at 120 s
    ASSERT_EQ(horizon, UINT64_C(20496382));
    ASSERT_GT(horizon * R, MONEY_SUPPLY - R); // last representable full step
    uint64_t agc = (horizon - 1) * R;         // tally just before the edge
    ASSERT_EQ(reward_at(agc), R);              // reward unaffected by the tally
    agc = tally_step(agc, R);                  // step onto the edge
    ASSERT_EQ(agc, horizon * R);
    agc = tally_step(agc, R);                  // one past: saturates
    ASSERT_EQ(agc, MONEY_SUPPLY);
    ASSERT_EQ(reward_at(agc), R);              // and emission continues at 0.9 forever
    ASSERT_EQ(tally_step(agc, R), MONEY_SUPPLY);
    // Recorded finding for ADR-001: with 12 decimal places the on-chain supply counter saturates after
    // ~78 years while emission continues correctly; atomic-unit choice must be decided with this number.
  }

  // ---------------------------------------------------------------- E5
  TEST(meow_emission, dilution_is_one_over_n_minus_one)
  {
    // inflation during year N == issuance_N / cumulative_{N-1} == 1/(N-1) for a flat schedule
    const long double year = 262800.0L * R;
    for (int n = 2; n <= 101; ++n)
    {
      long double infl = year / (year * (n - 1));
      ASSERT_NEAR((double)infl, 1.0 / (n - 1), 1e-12) << "year " << n;
    }
    // no height has negative issuance: nothing is ever burned by consensus
    for (uint64_t agc : { UINT64_C(0), R * 262800, R * 262800 * 50 })
      ASSERT_GT(reward_at(agc), 0u);
  }
}
