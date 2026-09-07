# Emission specification v1 (provisional — Candidate M lineage)

**Status:** fixed perpetual shape, fair launch / zero premine and honest claims agreed 2026-09-07. Final spacing/subsidy pair, precision/display details and ADR-001 signatures remain open. **Governing text:** PLAN.md rev 5 §8.1–§8.2. **Implementation:** M1 patch series under `chain/patches/`; the current consensus default remains 0.9 MEOW / 120 s. **Tests:** `spikes/candidate-m/tests/block_reward.cpp` (source of patch 0005).

## 1. Parameters

| Parameter | Value | Where |
|---|---|---|
| Block subsidy | **0.9 MEOW per block, every block, forever** | `MEOW_BLOCK_REWARD = 900_000_000_000` atomic units |
| Atomic units | 10^12 per MEOW (`COIN`, `CRYPTONOTE_DISPLAY_DECIMAL_POINT = 12`) — inherited; **open parameter**, see §4 | `cryptonote_config.h` |
| Target block time | 120 s (`DIFFICULTY_TARGET_V2`) — working value pending M2 benchmarks | inherited |
| Genesis subsidy | **0** (coinbase has one output of amount 0; v2 tx, RCTTypeNull) | `construct_miner_tx` height-0 rule; `validate_miner_transaction` height-0 rule; `GENESIS_TX` blob |
| Premine / founder reward / dev tax | none; no protocol allocation exists | by construction |
| Burn | none; no consensus rule destroys value | by construction (PLAN §8.1 item 5) |
| Fees | miner receives base reward + fees; dynamic fee inherited (denominated in base reward) | inherited |
| Block-weight penalty | inherited unchanged; denominated in the 0.9 constant | `get_block_reward` |

### Matched-issuance benchmark candidates (2026-09-07)

| Target spacing | Fixed subsidy | Atomic subsidy at 12 dp | Expected blocks / 365 days | Expected MEOW / 365 days |
|---|---|---|---|---|
| 120 s (current implementation) | 0.9 | 900,000,000,000 | 262,800 | 236,520 |
| 90 s (benchmark only) | 0.675 | 675,000,000,000 | 350,400 | 236,520 |

The nine theme motivates testing 90 s, not selecting it in advance. Compare propagation, proof validation, competing blocks/orphans and reorgs without weakening release gates. **0.9 / 90 s is not approved:** it would increase expected annual issuance to 315,360 MEOW. Actual calendar issuance varies with realized block timing and any block-weight penalties. Neither candidate establishes an adoption advantage; use measured payment completion, conversion and retention evidence rather than monetary-policy preference polling.

## 2. Invariants (current 120 s / 0.9 implementation; each has a test)

1. `get_block_reward(...)` returns exactly `MEOW_BLOCK_REWARD` for every `already_generated_coins` value, every hard-fork version, and every target spacing. (E1, E2)
2. Penalty math for oversize blocks is unchanged from upstream and scales the constant. (E3)
3. Cumulative supply after height h is exactly `h × 0.9 MEOW`; genesis contributes 0. (E4, devnet check)
4. The u64 supply tally saturates at `MONEY_SUPPLY` (2^64−1) after **20,496,382** blocks (≈ 78.0 years at 120 s) and never wraps; emission continues correctly past that point. (E4)
5. Issuance is never negative at any height. (E5)

## 3. Honest dilution table (publishable; PLAN §8.1)

Percentage inflation during year N of a flat schedule with zero genesis supply is `1/(N−1)`, independent of the rate.

| Year | Issued that year (MEOW) | Cumulative (MEOW) | Inflation during year |
|---|---|---|---|
| 1 | 236,520 | 236,520 | undefined (from 0) |
| 2 | 236,520 | 473,040 | 100% |
| 3 | 236,520 | 709,560 | 50% |
| 5 | 236,520 | 1,182,600 | 25% |
| 11 | 236,520 | 2,601,720 | 10% |
| 21 | 236,520 | 4,966,920 | 5% |
| 34 | 236,520 | 8,041,680 | 3.03% |
| 51 | 236,520 | 12,062,520 | 2% |
| 101 | 236,520 | 23,888,520 | 1% |

**Claims that must not be made:** "deflationary", "initial deflation", "below USD inflation" in early years, "fixed supply". Any such target is mathematically incompatible with zero-genesis positive issuance and no premine (PLAN §8.1 audit). Todd's convergence (circulating supply → issuance ÷ loss rate) is a long-run statement and must not be marketed as early low inflation.

## 4. Precision and wallet display

**Agreed 2026-09-07:** retain sufficient decimal precision for small payments and simplify wallet display. Keep inherited 12 dp for now; display changes must not alter consensus/RPC atomic values, silently round payment inputs, or render a nonzero balance as zero. Prefer existing formatting paths and exact-amount disclosure; wallet display implementation and usability tests remain work to do. Denomination has no effect on percentage supply growth.

### Remaining parameter: exact atomic units

The tally horizon (invariant 4) is set by `MONEY_SUPPLY / MEOW_BLOCK_REWARD`. With 12 dp it is 78 years; with 10 dp (`COIN = 10^10`, reward 9×10^9) it is ~7,800 years. Changing decimals touches wallet display, RPC amount parsing, fee constants (`DYNAMIC_FEE_*`, `FEE_PER_KB`), and every test vector — a small but wide delta. Decision belongs to ADR-001 / open-questions #13; **default if undecided: keep 12 dp and document the 78-year tally saturation** (emission itself is unaffected).

## 5. Consensus delta summary (for the audit scope)

| File | Change | Invariant touched |
|---|---|---|
| `src/cryptonote_config.h` | `MEOW_BLOCK_REWARD`; genesis blob | emission constant; genesis |
| `src/cryptonote_basic/cryptonote_basic_impl.cpp` | `get_block_reward` base reward = constant | subsidy schedule |
| `src/cryptonote_core/cryptonote_tx_utils.cpp` | height-0 reward = 0 (template) | genesis |
| `src/cryptonote_core/blockchain.cpp` | height-0 base reward = 0 (validation) | genesis; coinbase validation |

Everything else in the emission path (`already_generated_coins` tally update, penalty, fee derivation, coinbase decomposition rules) is inherited unchanged and stays inside the re-review scope of PLAN §2.3 because its assumptions (a declining curve) changed.
