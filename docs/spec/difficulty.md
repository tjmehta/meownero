# Difficulty and launch-window policy (provisional — Candidate M)

**Status:** design note with simulation evidence; the launch floor is an M1 decision that needs the guaranteed genesis hashrate (a launch-planning input, PLAN §8.3/§8.5), not a code default. **Simulator:** `spikes/candidate-m/difficulty_sim.py` (ports `next_difficulty` from Monero v0.18.5.1 exactly; feasibility only).

## Inherited algorithm (unchanged)

Monero DAA: last 735 blocks, newest 15 ignored (lag), timestamps sorted, 60 cut from each end, `difficulty = ceil(work × 120 / time_span)`; a block's timestamp must be at least the median of the previous 60 and may be at most 2 h (`CRYPTONOTE_BLOCK_FUTURE_TIME_LIMIT`) ahead of the validator's clock. Six years of production on Monero; incident record in E5 (timestamp attacks on *other* LWMA-family chains, none on this DAA at Monero's scale).

**2026-09-12 correction and new evidence:** the native timestamp check accepts
**equality** with the median; the older simulator instead required strictly
exceeding it. That simulator also included genesis in DAA samples and
counted an out-of-horizon final draw. Its numbers below remain historical.
[Native-DAA benchmark and daemon tests](../../research/verification-2026-09-12-m2.md)
now cover 720 paired scenario runs and real reorganization beyond the 720/735
boundaries. Launch-time forward-stamp scenarios show substantial modeled issuance
distortion; the older warmed-up attack result does not close launch timestamp
risk. No timing, minimum value or lifetime decision follows from these results.

## What the simulation shows (H = 5 MH/s assumed steady launch hashrate, one seed)

| Scenario | No floor | Floor = 0.25 × steady-state (150 M) | Floor = 1 × steady-state (600 M) |
|---|---|---|---|
| A: H present from genesis, first hour | 37 blocks (target 30) | 25 | 18 |
| A: first 24 h total | 712 (target 720) | 723 | 707 |
| E: 10 kH/s for 1 h, then H arrives (×500) | h0 32, **h1 208**, h2 50, h3 48 … 12 h total 616 (target 360) | **chain stalls 7 h** (h0 1, h1–h7 0), then 73/128/107/117 | stalls 2 h, then 18–46/h; 12 h total 291 |
| C: ×10 hashrate for 2 h then back | 144.5 blocks/h during; **11/h for the 6 h after** | same | — |
| D: attacker share 20–50 % stamps at +FTL (2 h or 20 min) | difficulty **rises** 10–13 % (the median-of-60 rule drags honest stamps forward; no drop observed) | — | — |

Readings:

1. **A fresh chain with a constant hashrate is fine without a floor**: the DAA adapts from block 2, and the first hour overshoots by ~25 %.
2. **The launch hazard is the ramp (E), not the constant case**: if hashrate arrives after a slow start, one hour of ~7× block rate happens before the window catches up. With a flat 0.9 reward that hour is ~180 extra blocks ≈ **160 MEOW**, i.e. the "premine-like" effect is economically bounded (a day's issuance is 648 MEOW) but it is the optics PLAN §8.3 item 3 warns about.
3. **A floor is a bet on the genesis hashrate.** Set above what actually shows up, the chain stalls for hours (E, 150 M floor) — worse than the burst. Set at the hashrate the launch procedure can *guarantee* (founders' committed CPUs + committed pools, PLAN §8.5), it removes the difficulty-1 start without stall risk.
4. **After a whiplash the DAA overshoots the other way** (11/h for 6 h after a 2 h ×10 burst): the 735-block window is slow on a young chain. This is the argument for an LWMA-style shorter window; it is also a consensus delta with its own review cost.
5. **Forward-timestamp attacks did not lower difficulty in this model**; the sorted-cut plus median rule absorbed them. The model does not include withholding or selfish-mining strategies (E5 records real incidents on chains with *different* algorithms); treat as "no easy win observed", not proof.

## Decision (proposed for M1; §2.1 "prefer subtraction")

- **Keep the inherited DAA unchanged.** No LWMA swap in v1: it would be a consensus delta on the PoW path with no production precedent on this exact lineage, for a benefit (faster recovery after whiplash) that confirmation guidance can cover.
- **Add a launch floor** as a single constant, `MEOW_MIN_DIFFICULTY`, inside the shared `next_difficulty` function so main- and alternative-chain callers use the same rule, with the value computed at parameter freeze (T−4 weeks) as `guaranteed_genesis_hashrate × 120 / 2`. Until the guaranteed hashrate is known the constant is **1** (no floor) and this note is the record of why. **Implementation status (2026-09-07):** patch 0008 also clamps the ≤1-sample startup path. Genesis remains difficulty 1 at the two callers that see it (main-chain validation and recalculation); the shared DAA cannot distinguish genesis from block 1 because sample collection skips genesis. Eight tests plus the inherited hash check pass with the shipped floor 1 and a separately compiled 150M-floor DAA. Core integration covers initialization on all three networks, post-genesis difficulty, cumulative-work recalculation and the intentionally floor-free `--fixed-difficulty` override; rounding and overflow sentinel 0 remain unchanged. Run `bash chain/test-difficulty.sh <built-source>`. Alt-chain code shares the DAA; adversarial alt-chain/reorg integration remains M2 work. These tests do not authorize raising the launch constant.
- **Keep FTL at 2 h** (upstream value; the simulation gives no reason to tighten, and tightening changes peer-clock tolerance).
- **Publish confirmation guidance** for the first week scaled to observed hashrate (PLAN §6.4 item 4) instead of a checkpoint mechanism (open-questions #6 remains the group's call).
- **Re-run the simulator with the real guaranteed hashrate** before freezing parameters; record the chosen floor in `docs/spec/network-identity.md`.

### Open design decision — floor lifetime and calibration (2026-09-07)

Design advice relayed by TJ from session `meownero-2f`; **not authorization to change code or the shipped floor of 1**. The current implementation is a **permanent minimum**, not a temporary launch setting. Raising it therefore requires resolving lifetime/liveness as well as its numeric value. This discussion does not reopen fair launch, zero premine or the agreed fixed perpetual subsidy.

1. **Permanent-floor liveness risk:** if hashrate later falls far below the assumed commitment, block production can become arbitrarily slow. Lowering a consensus minimum requires an upgrade; hashrate returning can also restore progress. Positive hashrate does not imply a literal permanent halt, but the operational risk can outweigh the modeled ~160 MEOW launch-ramp excess. The relayed historical comparison points to Dash's delayed retarget/instamine; its specific 3,396-block / 10% figures are unverified here and are not evidence that Meownero cannot have other launch failures.
2. **Precedents to assess, not yet adopted:** [zawy12's LWMA discussion](https://github.com/zawy12/difficulty-algorithms/issues/3) reportedly uses `difficulty_guess` for the initial N blocks; Zcash used a reward slow-start. These are different mechanisms/algorithms, not proof of safety for this DAA. Pin and review exact implementations before treating either as an adopted precedent.
3. **Proposed bounded startup floor:** apply the clamp in the shared DAA only while `timestamps.size() < DIFFICULTY_WINDOW`, retaining the two caller-level genesis exemptions. With current genesis-skipping collection, the intended startup range is blocks 1–720. Verify main/alt/recalculation sample-count equivalence, cache transitions and reorganizations at the boundary before adopting it. **This bounds blocks, not elapsed time:** it may last far longer than one day if hashrate is low. It changes the meaning of existing tests and remains an unapproved consensus delta.
4. **Proposed calibration alternative:** at parameter freeze use `floor = 0.25 × measured_testnet_hashrate × target_spacing`, measured with the real binaries. If actual launch hashrate is exactly one quarter of that measurement, the floor's mean interval equals the target; a larger shortfall still slows blocks. This proposal replaces neither the existing proposed `guaranteed_hashrate × target / 2` formula nor the need to assess representativeness, variance and hashrate disappearance. Use the spacing selected by the matched-issuance benchmark decision, not an assumed 90 s.
5. **Unapproved alternative for the group:** a first-day reward ramp avoids an added minimum-difficulty liveness constraint, but does not guarantee zero stall risk from the underlying DAA or absent miners. It changes the agreed flat issuance schedule and the `height × constant` accounting invariant (a ramp is not itself a premine). It is not selected here; any reconsideration belongs to the group and must preserve mainnet-quality gates.

Required before any floor increase: compare permanent versus block-bounded behavior under measured hashrate shortfalls, disappearances and recovery; test activation/expiry/reorg/recalculation boundaries; record the selected lifetime and calibration in an ADR. No value or lifetime choice is made by this note.

## Not covered

Merge-mined difficulty (E6 deferred), RandomX seed schedule during the first 2048-block epoch (inherent; the control mined through it), difficulty behaviour under 51 % adversaries (threat model T5; policy question).
