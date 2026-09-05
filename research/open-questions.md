# Open questions for the group

**Date:** 2026-08-22, updated 2026-09-05 · **Status:** #1–#4 and #12 answered 2026-09-05 (council pass + group decision; applied to PLAN.md rev 4). Remaining answers unblock ADR-001. Answer inline or in the chat; decisions get recorded in ADR-001.

1. **Ratify the security doctrine (PLAN.md §2)?** Includes the "prefer subtraction" tie-breaker and the ≥2-years production-history bar. — Yes as written / amend (state changes).
2. **Approve the PLAN.md amendment pass from dossier evidence?** (a) orchard license blocker resolved; (b) Orchard pool sealed July 2026 → maturity re-scoring; (c) no adaptor-signature precedent → interop defers. — Approve / review dossiers first.
3. **Maturity bar for new upstream cryptography** (decides both candidates): months of incident-free mainnet history required before we build on it?
   - FCMP++ (Candidate M): not on mainnet — fork only after v0.20 + N months?
   - Ironwood (Candidate Z): activated ~2026-07-28 — same bar?
   - Or accept Sapling-only (8 yrs production, Pirate precedent) as Candidate Z's pool despite older crypto?
4. **Any launch-blocking desiderata?** Plan default: none — Bitcoin interop defers, merge-mining decided at ADR-001. — Confirm default / name exceptions.
5. **Merge-mining posture if RandomX chosen:** launch merge-mined / launch solo, add merge-mining later (Dogecoin added AuxPoW at month 10) / decide after pool soundings.
6. **Deep-reorg protection for the young chain:** accept naked 51% risk / bounded checkpoint-finality with sunset date / decide at ADR-001 with E6 evidence.
7. **Ticker:** keep MEOW despite collisions (incl. Solana squatter) / pick a cleaner ticker.
8. **Public identities:** are TJ and the whitepaper author willing to be publicly identifiable founders of a mandatory-privacy coin? (Gates counsel questions, PLAN.md §9.2.)
9. **Money:** who funds counsel, the external audit (5–6 figures), and the E4 cryptographer consult — donation fund / out of pocket / launch-waits-until-funded.
10. **the whitepaper author's role:** second maintainer with release-signing keys? (Two-person release rule needs its second person named.)
11. **TJ:** the 2026-08-22 message cut off after "Let me know if" — was there more?
12. **Monetary policy** (added 2026-09-04 from E3 rev 2): hard cap / fixed supply vs perpetual (linear or tail) emission?
13. **Exact emission schedule and rate** (new, from PLAN.md §8.1 audit): P-flat 0.9 MEOW/block · decay-to-tail (illustrative 9→0.9) · keep flat and restate the inflation constraint honestly. Note: any "below fiat inflation early" or "initial deflation" target is mathematically incompatible with zero-genesis positive issuance and no premine; a 999,999,999 genesis supply is a premine and was rejected. Are the early-inflation targets withdrawn?
14. **Block time:** 120 s working value — ratify after Stage 2 propagation/orphan benchmarks, or change now?
15. **Pool scoping on Candidate Z** (Sapling-only vs Ironwood-only): decided at ADR-001 after the §7 Ironwood gates (Pirate activation 2026-10-03 + exact review). No answer needed yet — listed so it is not forgotten.

## Answers (fill in)

| # | Answer | Decided by | Date |
|---|---|---|---|
| 1 | Ratified as amended: calendar bar → non-waivable §2.2 readiness rubric, no timeline minimum; §2.3 gadget-layer controls | Group (TJ) | 2026-09-05 |
| 2 | Approved: clerical packet then dependency-ordered normative commits (PLAN.md rev 4) | Group | 2026-09-05 |
| 3 | No calendar floor; mainnet-first via rubric; Ironwood not approved before Pirate 2026-10-03 + exact gadget/encoding/integration review; FCMP++ monitored, not awaited | Group (TJ) | 2026-09-05 |
| 4 | None. Mainnet quality is the only launch priority; interop defers to reviewed production precedent | Group | 2026-09-05 |
| 5 | | | |
| 6 | | | |
| 7 | | | |
| 8 | | | |
| 9 | | | |
| 10 | | | |
| 11 | | | |
| 12 | Perpetual subsidy, in principle; 0.9 MEOW/120 s current candidate; hard cap/fee-only rejected on security grounds | Group | 2026-09-05 |
| 13 | | | |
| 14 | | | |
| 15 | (ADR-001) | | |
