# E3 — Monetary policy: emission schedule and supply

**Exploration:** What emission/supply policy should Meownero adopt, is it safe, and what does it cost per lineage? · **Status:** Draft (rev 2) · **Date:** 2026-08-22, revised 2026-09-04

> **Rev 2 changelog (2026-09-04):** the title and verdict are reframed. Rev 1 recorded a settled **"Adopt"** for flat perpetual emission with **"PLAN.md impact: none."** A substantial group philosophy discussion on **2026-09-04** reopened monetary policy as a genuine two-sided question — **hard cap / fixed supply** versus **perpetual (linear/tail) emission** — so the honest status is **OPEN: a human ADR-001 decision, not a technical default.** This revision preserves both positions, fact-checks their empirical/technical claims against primary sources, quantifies the security-budget and dilution trade-offs, separates technical fact from product/marketing philosophy, proposes decision criteria and candidate schedules (including 9-themed options for both camps), and marks the choice as TJ+the whitepaper author's to make. **PLAN.md is not edited; the tie is not decided here.**
>
> **Evidence gap to close:** the raw 2026-09-04 chat window (reported as ~256 messages) could **not** be read this session — the `wa-bridge` CLI named in the steering note is not installed on this machine. The two positions below are reconstructed from TJ's steering summary, **not** from the primary transcript, and are labelled accordingly. Faithful side-by-side capture of who argued what, with quotes, remains an open task (§8) pending that tool.

## 1. Verdict (rev 2 — reframed to OPEN)

**Monetary policy is now an open product-and-security decision for ADR-001, not a settled technical adopt.** Two facts coexist and must not be collapsed into each other:

1. **On the narrow technical question rev 1 actually answered, flat perpetual emission remains safe and cheap to implement.** It has two long-horizon production precedents (Dogecoin, Monero tail), a coherent theoretical defense (Todd), a small consensus delta on either candidate, and essentially no new security assumptions beyond arithmetic. Nothing in rev 2 overturns that. If the group chooses perpetual emission, E3 passes §2.2 comfortably.
2. **But "which monetary policy" is a different question, and it is genuinely contested.** The 2026-09-04 discussion put **hard cap / fixed supply** back on the table on product, narrative, and monetary-philosophy grounds. That is a values decision with real technical consequences (terminal security budget, holder dilution, launch-fairness optics) — it cannot be closed by a dossier, and it is not closed by the January whitepaper or by rev 1.

So rev 2's verdict is deliberately **not** a recommendation between the two. It is: *here are both positions stated fairly, here is what is empirically true vs. marketing on each side, here is the quantified trade-off, here are decision criteria and concrete schedules — you (TJ + the whitepaper author, and the group) decide, and ADR-001 records it.*

**PLAN.md impact (MATERIAL — changed from rev 1's "none"):** §8.1 currently presents "1 MEOW per 2-minute block, forever" as the **working default** and §3's whitepaper-audit table lists linear emission among "what the whitepaper gets right and we keep." After 2026-09-04 that can no longer be presented as ratified. Proposed for the amendment queue (not applied): (i) relabel §8.1 as **one of two candidate policies under an open ADR-001 monetary-policy decision**, not the default; (ii) add the hard-cap alternative with its own evidence and trade-offs; (iii) cross-reference open-questions.md — this needs a **new group question** (there is currently no monetary-policy question in the 11; it was assumed decided). This is the one place where rev 2 changes what PLAN.md claims, so it is flagged prominently per the discrepancy rule.

## 2. The two positions (from TJ's 2026-09-04 steering summary — NOT the raw transcript)

Stated as evenly as the summary allows; neither is endorsed. Raw-transcript attribution is an open task (§8).

**Position A — Hard cap / fixed supply.**
- *Holder value:* a known, finite terminal supply supports a scarcity/store-of-value narrative and holder confidence.
- *Social narrative:* "there will only ever be N MEOW" is a simple, powerful, Bitcoin-shaped story.
- *Security philosophy:* a chain "should survive on fees or die" — if the chain cannot eventually sustain security from a fee market, that is information, not a problem to paper over with perpetual issuance.
- *Cat/9-lives framing:* compatible — a fixed, 9-themed cap (see §5) carries the brand.

**Position B — Perpetual emission (linear or tail).**
- *Miner security budget:* a predictable, non-zero block subsidy funds security **forever**, avoiding a fee-only terminal regime.
- *Adaptive block size:* a standing base reward is what Monero's dynamic-block-size penalty math is denominated in; perpetual emission supports that mechanism directly (relevant on Candidate M).
- *Fairer late-entry distribution:* pure linear emission is the *least* front-loaded schedule; the coins available the day you join keep coming at the same rate, so late entrants are not structurally disadvantaged the way they are under a front-loaded cap.
- *Cat/9-lives / long-tail framing:* also compatible — a "long tail" / "same meow forever" narrative, 9-themed rate (see §5).

**The narrative point cuts both ways:** the cat / nine-lives / long-tail brand can be told as *scarcity* (nine lives, no more) **or** as *endurance* (nine lives, always another block) — so brand does not settle the question. Keep marketing framing out of the security argument (§4a).

## 3. Production precedents & maturity evidence

- **Perpetual — Dogecoin:** block subsidy fixed at **10,000 DOGE/block** since the reward went flat at **block 600,000** (early 2015); ~11 years in production on a top-tier PoW chain, ~5.256B DOGE/year, linear. `[SECONDARY — code-pinnable]` — dogecoin/dogecoin `GetDogecoinBlockSubsidy` (the pre-600k epochs halve every 100k blocks: 1M→500k→250k→125k→62.5k, then a constant 10,000). Exact source ref still to pin (§8).
- **Perpetual — Monero tail:** 0.6 XMR per 2-minute block since ~May 2022, explicitly to fund security forever and to denominate the dynamic-block-size penalty. `[VERIFIED-PRIMARY]` — getmonero.org Moneropedia tail-emission page.
- **Perpetual — theory:** Peter Todd, "Surprisingly, Tail Emission Is Not Inflationary" (2022) — constant absolute emission plus ongoing coin loss drives *circulating* supply to a finite steady state (§4b quantifies this). `[VERIFIED-PRIMARY]` — petertodd.org. Endorsed in our own chat history by the whitepaper author (2026-01-15).
- **Hard cap — Bitcoin:** 21,000,000 BTC via geometric halvings every 210,000 blocks; the canonical fixed-supply precedent and the source of the scarcity narrative. Subsidy trends to zero (~2140), after which miners are paid by fees only. `[VERIFIED-PRIMARY — uncontroversial; pin Bitcoin GetBlockSubsidy for the record]`
- **Hard cap — security-budget counter-evidence:** Carlsten, Kalodner, Narayanan, Weinberg, *"On the Instability of Bitcoin Without the Block Reward"* (ACM CCS 2016). Formal result: in a **fee-only** regime the exponentially-distributed block-arrival time makes fee rewards high-variance, which makes it attractive to **fork a "wealthy" block to steal its fees**, yielding undesirable equilibria (and enabling profitable selfish mining at arbitrarily low hashpower). This is the strongest *technical* evidence bearing on Position A's "survive on fees or die" claim — the academic literature says a fee-only steady state is **less** stable, not neutrally stable. `[VERIFIED-PRIMARY]` — dl.acm.org/doi/10.1145/2976749.2978408; CITP summary (blog.citp.princeton.edu, 2016-10-21).
- **Negative precedent both sides cite differently — Pirate Chain:** ~90% of 200M mined early by its own FAQ. Position B reads this as the front-loaded-cap failure to avoid; Position A must show its cap schedule is *not* front-loaded (achievable, but it is a design constraint, not automatic). `[SECONDARY]` — piratechain.com FAQ.
- **Meownero linear arithmetic (unchanged):** 1 MEOW/2 min = 720/day = 262,800/year; year-N inflation = 1/(N−1) → 100% (yr 2), 11.1% (yr 10), 1% (yr 100). `[VERIFIED-PRIMARY]` — arithmetic.

## 4. Technical fact vs. marketing — the claims that must be checked

### 4a. Separating fact from philosophy

| Claim (as argued) | Status | Basis |
|---|---|---|
| "Hard cap guarantees holder value" | **Marketing, not technical.** Cap fixes *quantity*, not price; scarcity is necessary-not-sufficient for value. | economics, not consensus |
| "Perpetual emission is inflationary forever" | **Technically false in the circulating sense.** With coin loss, circulating supply converges (§4b). Nominal supply is unbounded; *effective* supply is not. | Todd; §4b arithmetic |
| "A chain should survive on fees or die" | **Legitimate philosophy with a technical cost.** Carlsten et al. show fee-only mining is *less* stable, so "or die" may mean literal security degradation, not a clean market test. | Carlsten 2016 |
| "Perpetual subsidy = predictable security budget" | **Technically true**, in units of coin; value still tracks price. | Monero precedent |
| "Linear is fairer to late entrants" | **Technically true** re: distribution front-loading; it is the least front-loaded schedule. | arithmetic |
| "Perpetual emission supports adaptive block size" | **True on Candidate M** (penalty math denominated in base reward); N/A as stated on Z. | getmonero.org; E3 §5 M-extras |
| "9-lives ⇒ hard cap" / "9-lives ⇒ long tail" | **Pure narrative**, works both ways; must not enter the security argument. | brand track |

### 4b. Quantified trade-off (the numbers to decide against)

**Perpetual linear (1 MEOW/block), circulating-supply convergence.** Annual emission E = 262,800 MEOW. With annual lost-coin fraction λ, steady-state circulating supply S* ≈ E/λ:
- λ = 1% → S* ≈ **26.3M MEOW**; λ = 2% → **13.1M**; λ = 3% → **8.8M**.
So "infinite emission" produces a *finite* circulating supply whose size the loss rate sets — Todd's point, made concrete. Annual *nominal* inflation falls as 1/(years): ~10% at year 10, ~1% at year 100, asymptotically 0 but never a hard stop.

**Hard cap (geometric, Bitcoin-shaped), security-budget decay.** Under halvings, the block subsidy after k halvings is S₀/2^k. The security budget (in coin) halves each epoch toward zero; the crossover where a capped schedule's subsidy drops **below** the flat 1 MEOW/block line happens after log₂(S₀) halvings, after which perpetual emission pays miners strictly more per block in coin terms. Terminal state = fee-only = the Carlsten instability regime. **Dilution** under a cap trends to 0 as the cap is approached — good for the scarcity narrative, and (if the early schedule is steep) worse for late-entry fairness; a *linear-to-a-cap* or *slow* cap can soften this but cannot remove the terminal fee-only problem.

**The core trade, stated once:** perpetual emission buys a permanent, predictable security budget at the cost of no hard-cap scarcity story and faster early dilution; a hard cap buys the scarcity story and zero terminal dilution at the cost of a fee-only terminal security budget that the academic literature says is unstable. **Neither side gets both.** That is why this is an ADR decision, not a dossier verdict.

## 5. Decision criteria and candidate schedules (for ADR-001)

**Proposed decision criteria (for TJ/the whitepaper author to weight):**
1. **Terminal security budget** — is a fee-only endgame acceptable given Carlsten et al.? (Weighs toward B.)
2. **Distribution fairness** — how much early-holder concentration is tolerable vs. §1.1 #4/#5 fair-launch goals? (Weighs toward B / a non-front-loaded cap.)
3. **Narrative priority** — is a fixed-cap scarcity story worth more than a "sound-money-forever" endurance story to the brand? (Product call.)
4. **Lineage fit** — Candidate M's dynamic block size wants a standing base reward (weighs toward B on M); Candidate Z is agnostic.
5. **Reversibility** — emission policy is effectively irreversible after launch; favor the choice whose failure mode is least catastrophic (a mild-perpetual schedule can be argued as the lower-regret option, but that is a judgment, not a fact).

**Candidate schedules — Perpetual camp (9-themed options):**
- **P0 (whitepaper canon):** 1 MEOW / 2-min block, forever. Simplest; §3 arithmetic.
- **P9-rate:** **0.9 MEOW/block** (or 9 MEOW/block) — a 9-themed constant tail. Same properties as P0, different steady-state (S* scales with the rate).
- **P-decay-then-tail:** Monero-shaped smooth decline into a **0.9 MEOW/block** perpetual tail — keeps a predictable floor while front-loading less than a pure cap.

**Candidate schedules — Hard-cap camp (9-themed options):**
- **C-999,999,999:** cap of **999,999,999 MEOW** (nine nines) — on-narrative, large enough for fine-grained pricing.
- **C-9^9 family:** e.g., **387,420,489** (9^9) or **900,000,000** — 9-themed caps at different scales.
- **C-linear-to-cap:** linear issuance until a 9-themed cap, then fee-only — least front-loaded *capped* option, directly addressing Position B's fairness objection while accepting the terminal fee-only regime (and its Carlsten risk).

Atomic-unit/decimal-places choice (§8) interacts with all of these and should be fixed alongside the policy.

## 6. Consensus/crypto delta (per candidate)

- **Both candidates:** replace the subsidy function with the chosen schedule; define atomic units and overflow-safe accumulation; emission test vectors across genesis, adjacent blocks, halving/cap boundaries, and far-future heights. A hard cap adds a **terminal-subsidy = 0 / fee-only** code path and its own edge-case vectors (last-satoshi rounding, post-cap coinbase = fees only).
- **Candidate M extras:** Monero's dynamic-block-size **penalty** math is denominated in base reward and must be re-derived for whatever schedule is chosen — *more* delicate for a hard cap (base reward → 0 makes the penalty term degenerate) than for a constant tail. `[OPEN — derivation task; now schedule-dependent]`
- **Candidate Z extras:** remove the consensus dev-fund/NU6-lockbox streams (no-dev-tax requirement) regardless of schedule; decide fee policy (ZIP-317-style proportional fees under an all-shielded mempool — interacts with E2 §4a DoS analysis, and becomes *load-bearing* under any capped/fee-only endgame). `[OPEN — enumerate funding-stream code in the target Zebra tag]`
- **Block time:** 120 s (whitepaper canon) vs upstream (Monero 120 s free; Zcash 75 s — a parameter change to justify and test). `[OPEN on Z]`

## 7. Security assumptions introduced

Beyond arithmetic correctness (overflow, rounding at atomic scale): **schedule-dependent.** Perpetual emission adds essentially nothing. A **hard cap adds a terminal-security assumption** — that a fee market can secure the chain once subsidy → 0 — which Carlsten et al. give reason to doubt and which therefore must be treated as an explicit, disclosed assumption, not assumed away. Economic assumptions (any subsidy sustains security *value*) depend on price under all schedules — disclosed, not assumed.

## 8. Open verification tasks

Reframed in rev 2:

- [ ] **Read the raw 2026-09-04 chat window and capture both sides faithfully with attribution/quotes** — *blocked this session: `wa-bridge` CLI not installed.* Highest priority for E3 rev 3; §2 is currently a second-hand reconstruction from TJ's steering summary.
- [ ] Pin Dogecoin's subsidy constant and flat-start height from dogecoin/dogecoin source (`GetDogecoinBlockSubsidy`). *(carried from rev 1)*
- [ ] Pin Bitcoin's `GetBlockSubsidy` and 21M mechanics as the hard-cap primary reference. *(new)*
- [ ] Read Carlsten et al. 2016 in full (not just abstract) and extract the precise conditions under which fee-only mining destabilizes — needed to weight decision criterion 1 fairly. *(new)*
- [ ] Enumerate Monero's penalty-math dependency on base reward for the M-path derivation — now schedule-dependent (esp. hard-cap degeneracy). *(sharpened)*
- [ ] Enumerate the funding-stream/lockbox code paths in the target Zebra tag for the Z-path removal. *(carried)*
- [ ] Decide atomic units / decimal places (proposal for ADR-001), jointly with the schedule. *(carried)*
- [ ] ZIP-317 fee-mechanism evaluation under an all-shielded mempool (joint with E2) — becomes critical under any capped/fee-only endgame. *(sharpened)*
- [ ] Draft the new monetary-policy question for open-questions.md (there is none today). *(new — group-blocking)*

## 9. Kill criteria

Unchanged for the *perpetual* option (none realistic). For a *hard-cap* option, a soft kill criterion emerges: if analysis (criterion 1) concludes the terminal fee-only security budget is unacceptable for a young privacy chain and no mitigation (e.g., a residual tail) is adopted, the pure-cap schedule fails on security grounds — which would itself be a finding, not a foregone conclusion.

## 10. Safest fallback

There is no risk-free default here; the fallback depends on which risk the group least wants. The lowest-technical-regret option is a **perpetual or decay-to-tail** schedule (keeps a security budget, avoids the fee-only endgame), but choosing it *because* it is the safe technical default would be deciding the tie — which is TJ+the whitepaper author's call, not this dossier's.

## 11. Sources

**Primary (read/verified):** getmonero.org/resources/moneropedia/tail-emission.html (Monero tail) · petertodd.org/2022/surprisingly-tail-emission-is-not-inflationary (convergence theory) · dl.acm.org/doi/10.1145/2976749.2978408 — Carlsten, Kalodner, Narayanan, Weinberg, "On the Instability of Bitcoin Without the Block Reward," ACM CCS 2016 (fee-only instability; read 2026-09-04, abstract + CITP summary — full-text read is an open task) · blog.citp.princeton.edu/2016/10/21/bitcoin-is-unstable-without-the-block-reward/ · zips.z.cash/zip-0317 (all-shielded fee policy) · whitepaper v1.1 (`assets/Meownero updated.pdf`).

**Secondary / to pin:** github.com/dogecoin/dogecoin (`GetDogecoinBlockSubsidy` — flat 10,000 from block 600,000; pin exact ref) · github.com/bitcoin/bitcoin (`GetBlockSubsidy` — 21M/halvings; pin) · piratechain.com/faq (front-loaded-cap negative precedent).

**Provenance note:** §2's two-position summary derives from TJ's 2026-09-04 steering message, **not** from the primary WhatsApp transcript (the `wa-bridge` tool to read it was unavailable this session). Treat §2 as reconstructed context to be verified against the raw thread in rev 3.

**Cross-references:** PLAN.md §3 (whitepaper-keeps list), §8.1 (emission default — proposed relabel), §5 E3 · E2 §4a (all-shielded mempool DoS, load-bearing under a fee-only endgame) · open-questions.md (needs a new monetary-policy question).
