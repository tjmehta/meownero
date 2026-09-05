# E5 — Proof-of-work: RandomX and the honest ASIC posture

**Exploration:** Which PoW, and what ASIC posture can we honestly commit to? · **Status:** Draft (rev 2) · **Date:** 2026-08-22, revised 2026-09-05

## 1. Draft verdict (DRAFT)

**RandomX is the evidence-backed default; Equihash fails the desideratum today; the difficulty algorithm needs as much care as the hash function.** RandomX has ~7 years securing Monero plus a live multi-chain ecosystem (Zephyr and Salvium run stock RandomX; Tari runs a variant; Wownero runs RandomWOW), and remains CPU-viable — the "everyone in the group mines it" story is real on RandomX. Equihash is fully ASIC-dominated (Antminer Z15 Pro-class hardware; GPU/CPU mining on ZEC is economically dead), so keeping it on Candidate Z would fail the ASIC desideratum on day one while passing the pure security bar. The sleeper finding is the **difficulty-adjustment incident record**: LWMA-family algorithms on small chains have documented, exploited failures — a >50% selfish-mine that produced ~4,800 blocks in 5 hours via a negative-solvetime bug in early LWMA, and Verge's 2018 collapse (difficulty 117,320 → 0.0015 via two-hour timestamp drift) — with concrete, published mitigations (FTL ≈ T×N/20, ±6·T solvetime clamp, ~N=45–120 window, never feed LWMA from lagged MTP, per-block timestamp sanity window). Our launch difficulty design must adopt these numbers, and the young-chain launch window is exactly when these attacks are cheapest. ASIC posture to publish stays as PLAN.md wrote it: "ASIC-unfriendly today, re-evaluated at every scheduled upgrade" — never "ASIC-proof."

**PLAN.md impact:** none structural — confirms §5 E5. The LWMA mitigation numbers should flow into §8.3's launch-difficulty language at amendment time.

## 2. Production precedents & maturity evidence

- **RandomX:** Monero's PoW since November 2019 (~7 years securing a top-tier privacy coin). `[VERIFIED-PRIMARY]` — tevador/RandomX repo + Monero release history.
- **Other RandomX-family production chains (mid-2026):** Zephyr Protocol (stock RandomX), Salvium (stock RandomX), Tari (TariRandomX variant, mainnet 2025), Wownero (RandomWOW variant); assorted niche chains. `[SECONDARY]` — mining-ecosystem aggregators; sufficient for "ecosystem exists," pin per-chain specifics only if load-bearing.
- **Equihash ASIC state:** ZEC mining exclusively ASIC-dominated (Antminer Z15 Pro ~840 kSol/s reference machine; institutional farm deployments); GPU/CPU non-competitive. `[SECONDARY]` — consistent across mining guides/calculators; adequate for a desideratum judgment.
- **LWMA incident record** `[VERIFIED-PRIMARY]` — zawy12/difficulty-algorithms GitHub issues (the algorithm author's own postmortems):
  - Issue #24: successful >50% selfish-mine exploiting mishandled negative solvetimes in early LWMA — ~4,800 blocks in 5 hours.
  - Issue #23: measured timestamp-attack pattern across 10 coins (sustained solvetime ≈ 0.68·T; e.g., 500 blocks in 35 minutes).
  - Issue #73: recommended FTL = T×N/20 (bounds manipulation to ~5%), peer-time bound = FTL/2.
- **Verge, April 2018:** timestamp attack — 2-hour allowed drift + retarget bug drove difficulty from ~117,320 to ~0.0015; effective 51% on one algo of a multi-algo chain; fixed by tightening drift to 10 minutes. `[SECONDARY]` — incident write-ups (dn.institute, apriorit); well-documented, upgrade if load-bearing.
- **Monero's own LWMA hardening:** monero-project PR #2887 added N=60 window, 20-minute future limit, 12-block timestamp check window citing a potential exploit. `[VERIFIED-PRIMARY]` — the PR.

## 3. Consensus/crypto delta

- **Candidate M:** zero (RandomX inherent, difficulty algorithm inherited and battle-tested at Monero's scale — though our *young-chain* hashrate profile differs from Monero's; the launch-floor question remains ours).
- **Candidate Z:** replace Equihash validation with RandomX in Zebra — no new cryptography (RandomX itself proven), but a **novel integration**: seed/key-block schedule, dataset/VM memory management in a Rust node, verification-cost DoS surface, plus a from-scratch difficulty algorithm choice where the LWMA record above sets the spec. No production precedent for RandomX in a Zcash-derived node. `[VERIFIED as negative result]`

## 4. Security assumptions introduced

- Correctness of the integration (Z-path) under adversarial load; verification performance bounds.
- Difficulty-algorithm robustness during the low-hashrate launch window — the highest-risk period per every incident above.
- ASIC posture is a *maintenance commitment*, not a property: RandomX's CPU-hardness assumptions hold today; we re-evaluate each scheduled upgrade.

## 5. Audit burden

Z-path: integration review + fuzzing of the validation path + difficulty simulation under hashrate whiplash and timestamp attack (zawy12's simulation methodology is reusable). M-path: difficulty-parameter review only (launch floor, window) since algorithm and integration are inherited.

## 6. Kill criteria (unchanged from PLAN.md §5 E5)

Z-path: RandomX integration intractable or un-reviewable in scope → either keep Equihash with an honest public ASIC disclosure (desideratum dropped), or weigh Candidate M where RandomX is free.

## 7. Safest fallback

Lineage-native PoW with honest ASIC disclosure.

## 8. Open verification tasks

- [x] Pin Zephyr/Salvium RandomX usage from their own repos. *(rev 2, 2026-09-05)* Zephyr: github.com/ZephyrProtocol/zephyr — Monero-derived, stock RandomX (standard XMRig `rx/0`); Salvium: github.com/salvium (docs.salvium.io: "RandomX, inherited from Monero", 120 s blocks); Wownero: RandomWOW fork (github.com/wownero/RandomWOW — 1 MiB scratchpad, 16 chained VM executions, active since height 114,969 on 2019-06-14). Stock-RandomX adopters therefore exist beyond Monero; a RandomX *variant* (Wownero-style) is a deliberate divergence we do not make (§2.1). `[VERIFIED-PRIMARY repo URLs; parameter claims from Wownero release notes]`
- [ ] Spec draft: our difficulty algorithm with citations into zawy12's issues. *(rev 2 note: under ADR-001's provisional Candidate M the inherited Monero DAA — 720-block window, 15-block lag, 60-timestamp cut, 2 h future-time limit, PR #2887 hardening — is the baseline; the open design item narrows to the **launch floor** and whether a LWMA-style tighter FTL is adopted for the young-chain window. Decide in M1 with a whiplash simulation; do not swap the algorithm without evidence.)*
- [ ] Z-path: locate Zebra's PoW abstraction boundary (how Equihash validation is modularized) to size the integration honestly — Stage 2 control-prototype input.
- [ ] RandomX seed/key-block schedule implications for a chain that is *not* Monero — *(rev 2)* solo mode is inherent on Candidate M: `rx_seedheight` keys the dataset from Meownero's own block at the seed height (2048-block epochs, 64-block lag), as the control's own-chain genesis+mining confirms. Merge-mined mode would require validating Monero-keyed hashes (Tari `MoneroPowData` pattern, E6 rev 2) — deferred with E6.
- [ ] Verify Verge incident details from a primary postmortem if the number is quoted anywhere public-facing.

## 9. Sources

Primary: github.com/tevador/RandomX · github.com/zawy12/difficulty-algorithms (issues #3, #23, #24, #73) · github.com/monero-project/monero PR #2887
Secondary (to upgrade or accept): dn.institute + apriorit Verge 2018 write-ups · whattomine/poolbay/minerstat RandomX coin lists · Z15 Pro mining guides · bydfi/valuehash "Equihash ASIC-only" state pieces
