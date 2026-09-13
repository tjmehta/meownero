# Open questions for the group

**Date:** 2026-08-22, updated 2026-09-13 · **Status:** #1–#4 and #12 answered 2026-09-05; #13/#14 superseded by the [September 12 selected-policy decision](decision-2026-09-12-issuance.md); #8–#10 answered by TJ on September 13 below. Fixed perpetual 9/90 is selected behind engineering gates, with 12/120 fallback. Do not re-ask the cap, premine, subsidy shape or branding-number vote.

## Useful questions now

TJ answered the proposed group questions directly on September 13:

- **Operators:** anyone can participate; no named operator roster is required
  before continuing. Hardware and sustained hashrate are measurements to collect
  during testing, not another staffing decision for the group.
- **Maintainers and identities (#8/#10):** anonymous/pseudonymous participation;
  contributors with repository access can contribute under their existing
  permissions. TJ is doing most of the work. No named second maintainer or
  mandatory the whitepaper author co-signature is required.
- **Review approach (#9):** use agents for review and research. Paid external
  audit/counsel procurement is not a prerequisite in the current plan. Agent
  findings need evidence and disposition; this does not establish a completed
  third-party audit or legal opinion.
- **Testing help:** ask the WhatsApp group for volunteers when there are concrete
  tasks, starting with a real iPhone Safari signup check and later node/miner
  instructions. The draft below has not been sent.

No staffing or review-funding question is pending for the group. Ticker (#7)
remains unanswered here and does not block local work. Merge-mining/checkpoint choices
(#5/#6) need a concrete evidence/architecture packet before a useful group vote;
the current P2Pool probes do not establish a working pool or mining protection.
This update records TJ's direct answers in the agent conversation; no new
WhatsApp messages were inspected or sent.

[Ready-to-paste short draft](whatsapp-questions-2026-09-12.md).

## Historical question wording

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
13. **Answered principles (2026-09-07):** fair launch / zero premine, small fixed perpetual subsidy, no initially ultra-low percentage inflation or deflation claims. Retain precision for small payments and simplify wallet display. Remaining implementation parameters: exact precision/presentation, fees, and final spacing/subsidy pair; do not re-ask the settled shape or claims.
14. **Benchmark instruction agreed (2026-09-07), selection pending evidence:** compare 90 s / 0.675 MEOW with 120 s / 0.9 MEOW using propagation, proof validation, competing blocks/orphans and reorgs. Both target 236,520 MEOW per 365 days. 0.9 MEOW / 90 s is not approved; 90 s is not locked.
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
| 8 | Anonymous/pseudonymous participation; no public-founder identity requirement | TJ | 2026-09-13 |
| 9 | Use agents for review and research; no paid audit/counsel procurement prerequisite | TJ | 2026-09-13 |
| 10 | TJ is the primary active contributor; existing repository access governs contributions; no named second maintainer or mandatory the whitepaper author co-signature | TJ | 2026-09-13 |
| 11 | | | |
| 12 | Perpetual subsidy, in principle; 0.9 MEOW/120 s current candidate; hard cap/fee-only rejected on security grounds | Group | 2026-09-05 |
| 13 | Fixed perpetual subsidy, zero premine, adequate precision / simpler display; misleading early-inflation and deflation claims withdrawn. No demonstrated issuance-model adoption advantage; use measured payment/conversion/retention evidence. Final implementation parameters remain open. | Group update relayed by TJ | 2026-09-07 |
| 14 | Compare matched-issuance 90 s / 0.675 and 120 s / 0.9 candidates; choose only after benchmarks, without weakening mainnet-quality gates | Group update relayed by TJ | 2026-09-07 |
| 15 | (ADR-001) | | |

September 12 supersedes the original #13/#14 values: 9 MEOW/90 s selected,
12 MEOW/120 s gated fallback, each 3,153,600 MEOW per 365 days before penalties;
zero premine, perpetual, no halvings/cap/sunset, no developer/transfer tax or
artificial burns, fees to miners. Retain 12-decimal atomic precision for current
engineering; simplify presentation separately. The earlier pairs remain
historical controls. No final benchmark, launch or cryptography gate is passed
by this policy choice.
