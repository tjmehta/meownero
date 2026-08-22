# E3 — Fair linear emission (1 MEOW / 2-minute block, forever)

**Exploration:** Is the whitepaper's flat perpetual emission safe to adopt, and what does it cost per lineage? · **Status:** Draft · **Date:** 2026-08-22

## 1. Draft verdict (DRAFT)

**Adopt.** This is the best-evidenced exploration in Phase 0. Flat perpetual block subsidy has two long-horizon production precedents — Dogecoin (fixed 10,000 DOGE/block since 2015, ~11 years) and Monero tail emission (0.6 XMR per 2-minute block since 2022) — and a coherent theoretical defense (Peter Todd: with lost coins, constant absolute emission converges to stable supply in practice). The consensus delta is small on either candidate, introduces essentially no new security assumptions beyond arithmetic correctness, and directly serves three hard requirements (fair launch, no premine advantage, perpetual security budget). No realistic kill scenario surfaced.

**PLAN.md impact:** none — confirms §5 E3 and §8.1 as written.

## 2. Production precedents & maturity evidence

- **Dogecoin:** block subsidy fixed at 10,000 DOGE/block since the final halving (early 2015); ~5.2B DOGE/year linear, ~11 years in production on a top-10-by-usage PoW chain. `[SECONDARY]` — uncontroversial; pin the constant in the Dogecoin source (`GetBlockSubsidy`) for the record.
- **Monero:** tail emission of 0.6 XMR per 2-minute block active since ~May 2022 (after the smooth-decline main curve), explicitly to fund security forever and support the dynamic block size. `[VERIFIED-PRIMARY]` — getmonero.org Moneropedia tail-emission page.
- **Theory:** Peter Todd, "Surprisingly, Tail Emission Is Not Inflationary" (2022) — constant absolute emission + ongoing coin loss → supply converges; endorsed in our own chat history by the whitepaper author (2026-01-15) with the Todd link. `[VERIFIED-PRIMARY]` — petertodd.org.
- **Negative precedent (what we avoid):** Pirate Chain's front-loaded curve (~90% of 200M mined by its own account) — the early-holder concentration failure. `[SECONDARY]` — piratechain.com FAQ.
- **Meownero schedule arithmetic:** 1 MEOW/2 min = 720/day = 262,800/year; year-N inflation = 1/(N−1) → 100% (yr 2), 11.1% (yr 10), 1% (yr 100). `[VERIFIED-PRIMARY]` — arithmetic, whitepaper v1.1 table checked.

## 3. Consensus/crypto delta

- **Both candidates:** replace the subsidy function with a constant; define atomic units and overflow-safe accumulation; emission test vectors across the schedule (genesis, adjacent blocks, far-future heights).
- **Candidate M extras:** Monero's dynamic-block-size *penalty* math assumes its emission curve — must be re-derived for a constant subsidy, not copy-pasted (the penalty divides by base reward; a constant makes this simpler but changes incentives at the margin). `[OPEN — derivation task]`
- **Candidate Z extras:** remove the consensus funding streams (dev fund / NU6 lockbox disbursements) — parameter/logic removal aligned with the no-dev-tax requirement, but a consensus delta needing test vectors like any other; also decide fee policy (ZIP-317-style proportional fees under an all-shielded mempool — interacts with E2's DoS analysis). `[OPEN — enumerate the exact funding-stream code in the target Zebra tag]`
- Block time: 120 s (whitepaper canon) vs. upstream (Monero 120 s — free; Zcash 75 s — a parameter change to justify and test, incl. difficulty and proof-propagation checks). `[OPEN on Z]`

## 4. Security assumptions introduced

Essentially none beyond arithmetic correctness (overflow, rounding at atomic-unit scale) and the second-order interactions named above. Economic assumptions (perpetual subsidy sustains security *value*) depend on price, as for Monero and Dogecoin — disclosed, not assumed away.

## 5. Audit burden

Low. Emission test vectors in CI; overflow/edge review; on M, review of the re-derived penalty math; on Z, review of funding-stream removal.

## 6. Kill criteria (unchanged from PLAN.md §5 E3)

None realistic. If somehow forced: fall back to upstream's native schedule — which would forfeit a core fairness goal and is flagged to TJ/the whitepaper author as a last resort only.

## 7. Safest fallback

Upstream-native schedule (see above; effectively "do not use").

## 8. Open verification tasks

- [ ] Pin Dogecoin's subsidy constant and the year it became flat, from the dogecoin/dogecoin source.
- [ ] Enumerate Monero's penalty-math dependency on base reward (source refs) for the M-path derivation.
- [ ] Enumerate the funding-stream/lockbox code paths in the target Zebra tag for the Z-path removal.
- [ ] Decide atomic units / decimal places (proposal needed for ADR-001).
- [ ] ZIP-317 fee-mechanism evaluation under an all-shielded mempool (joint with E2).

## 9. Sources

Primary: getmonero.org/resources/moneropedia/tail-emission.html · petertodd.org/2022/surprisingly-tail-emission-is-not-inflationary · whitepaper v1.1 (`assets/Meownero updated.pdf`) · zips.z.cash/zip-0317
Secondary (to upgrade): github.com/dogecoin/dogecoin (subsidy code — pin exact ref) · piratechain.com/faq
