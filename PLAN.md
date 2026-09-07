# Meownero Engineering Plan

**Status:** Rev 5 — 2026-09-07 group update: fixed perpetual subsidy, honest claims, matched-issuance 90 s / 120 s benchmark candidates (§8.1); builds on rev 4 (2026-09-05). · **Date:** 2026-08-22, rev 5 2026-09-07 · **Scope:** End-to-end local implementation and verification authorized (`docs/milestones.md`); no public mainnet launch, spending, external push or runtime changes. Reviewable local commits authorized; ADR-001 signatures and mainnet-quality gates remain required.

**Steer status (2026-08-22, per TJ).** the whitepaper author's latest ideas — Zcash/Zebra derivation, Bitcoin interoperability, ASIC-resistant mining — are **promising hypotheses and desiderata, not requirements**. They are explored seriously and adopted where they can be done safely; none of them pre-selects an architecture. **Security is the overriding non-negotiable** (§2): where a desideratum and security conflict, the feature is dropped or the less novel path is chosen. The architecture decision is evidence-led and happens at the end of Phase 0 (§5), not before it.

**Steer status (2026-09-05, group decision after the council pass).** **Mainnet quality is the only launch priority.** No desideratum may bypass the §2 doctrine, be promoted past its own kill criterion, or be named a launch exception (open-questions #4: *none*). Bitcoin interoperability remains desirable and stays on the roadmap, but it **defers until reviewed, production-quality precedent exists** for a swap construction over the spend-authorization scheme we actually ship (E4 rev 2 found none; §5 E4). Crypto-eligibility and monetary-policy decisions from the same session are recorded in §7 and §8.1.

This plan turns the January 2026 whitepaper and the chat history into a credible first engineering phase. It is deliberately blunt where the source material is wrong, and deliberately conservative where cryptography or consensus questions are unresolved. Much Meow, but measured meow.

---

## 1. Product thesis, hard requirements, and desiderata

**Thesis.** Meownero (MEOW) is a full, independent, proof-of-work cryptocurrency where privacy is mandatory for every transaction, launched honestly with no insider advantage, built strictly from battle-tested components, and wrapped in a meme-worthy cat brand that makes strong privacy approachable.

### 1.1 Hard requirements (stable across steers; from the chat record and TJ's brief)

1. **Security first.** No novel cryptography, no unproven consensus constructions, no security regression accepted for the sake of differentiation. The acceptance framework in §2 governs every technical choice. When in doubt: drop the feature or choose the less novel architecture.
2. **Independent coin, not a token.** Its own chain, own consensus, own P2P network. No Solana/EVM contract.
3. **Mandatory privacy.** No transparent transaction type, ever. This is a *product property* required since the January chat; the *mechanism* that delivers it is evidence-led (§5 E2) — if only one lineage achieves it without material security risk, that fact decides the mechanism.
4. **Fair, honest launch.** Public advance notice ("give everyone a couple weeks, then everyone mines"), reproducible binaries published before genesis, no insta-mine games.
5. **No premine, founder reward, or developer tax.** Zero protocol-level allocation to insiders. Dev funding is out-of-band and disclosed (§8.4).
6. **Meme-worthy brand, "Much Meow" voice.** Fun is a feature, but it lives in the branding track (§11), never in consensus code.
7. **No cosmetic rename.** Meownero must make consensus-meaningful, defensible design changes — not a find-and-replace of any upstream's name (the whitepaper author, 2026-08-22). Differentiation is earned through *safe* deltas; it never outranks requirement #1.

### 1.2 Desiderata (promising hypotheses to explore, not constraints)

Each maps to an exploration in §5 with evidence requirements, kill criteria, and a safest fallback. Any of these can be deferred or dropped without the project failing:

- **Zcash/Zebra/Orchard lineage** (the whitepaper author, 2026-08-22) → E1
- **Perpetual fair emission** (the whitepaper author, January whitepaper: 1 MEOW per 2-minute block) → E3 — *fixed perpetual subsidy agreed 2026-09-07; benchmark 0.9 MEOW/120 s versus 0.675 MEOW/90 s at matched annual issuance (§8.1)*
- **Bitcoin interoperability / atomic swaps** (the whitepaper author, 2026-08-22) → E4 — *deferred post-launch by decision 2026-09-05; desirable, not a launch item; revisit on reviewed production precedent (§5 E4)*
- **ASIC-resistant mining** (the whitepaper author, 2026-08-22) → E5
- **Merge-mining with Monero** (the whitepaper author, January) → E6

Anything that conflicts with §1.1 is out, regardless of how fun it sounds.

---

## 2. Security doctrine and acceptance framework

This section is the project's constitution. Every other section defers to it.

### 2.1 Doctrine

- **No novel cryptography.** We are integrators of audited primitives, never authors of new ones. A construction with no reviewed production precedent does not ship, however elegant.
- **No unproven consensus constructions.** Consensus rules we write must be minimal deltas on rules that have already secured real value, or they do not ship.
- **No security regression for differentiation.** A feature that makes Meownero more distinctive but less safe is rejected. Distinctiveness is a marketing asset; security is the product.
- **Prefer subtraction.** When evidence is inconclusive, drop the feature or choose the less novel architecture. A boring chain that keeps its promises beats an interesting chain that loses someone's money.

### 2.2 What "battle-tested" means (acceptance checklist)

A component, construction, or design pattern is *battle-tested* — and therefore adoptable — only when **all** of the following hold:

1. **Written assurance/readiness record (non-waivable).** *Amended 2026-09-05 by group decision; replaces the former "≥2 years production history" bar. TJ explicitly chose **no timeline minimum**: production time is evidence, never a pass/fail clock, and no sign-off exception exists for any line.* Rationale (E1 §10 item 2): the calendar bar would have passed Orchard in May 2026 while it carried a four-year-latent counterfeiting bug, and fails Ironwood today despite the strongest assurance artifact in the field — it measured elapsed time, not what anyone had checked. A component is eligible only when a written record exists covering **every** line below with primary-source citations, and no line reads "unknown":
   - **(a) Exact shipped mechanism.** The precise protocol version, circuit, consensus rules and parameters we would inherit, pinned to an implementation tag (node release + crate versions), not to spec text — NU6.3's ZIPs were Draft/Proposed while live (E1 §3).
   - **(b) Inherited gadgets and libraries.** Every proof-system and cryptographic dependency (gadget libraries such as `halo2_gadgets`, curve arithmetic, hash-to-curve, signature crates) enumerated and placed inside review scope. The June 2026 bug lived in a shared gadget library, not pool code (E1 §2a).
   - **(c) Encodings, transcripts, and FFI boundaries.** Byte-level serialization, transcript domain prefixes, hash instantiations, and cross-language interfaces enumerated, each marked as proof-covered, audit-covered, or review-only. (Ironwood: encodings/BLAKE2b external to the proof; FCMP++: a fragile Rust FFI layout flagged by Trail of Bits.)
   - **(d) Proof-to-implementation correspondence.** For any formal artifact: what is mechanically tied to deployed code (e.g. CI-pinned verifying-key/layout fixtures), what is hand-modeled, and what is *not composed* (e.g. Ironwood's ledger balance games vs. its circuit soundness proof — E1 §4). Credit only what is actually mechanized; headline claims are not evidence.
   - **(e) Independent audits.** Firm, scope, commit range, date, and report actually read — not "audited" in a press release.
   - **(f) Unresolved findings.** Zero critical/high; every open medium/low/informational item listed with its disposition and rationale.
   - **(g) Upstream maintenance.** Active maintainer organization, security-advisory channel we subscribe to, observed release and incident-response cadence.
   - **(h) Incident history from primary sources.** Advisories, CVEs, postmortems read and summarized — including *how* each issue was found, which is the evidence about discovery economics — never "no news is good news."
   - **(i) Production time and value secured, as evidence.** Recorded and weighed for what operational history can actually catch (implementation, networking, DoS, wallet paths) and explicitly *not* as a proxy for proof soundness, which undetectable-by-design failures have twice shown it cannot measure (CVE-2019-7167 ~2 yrs latent; CVE-2026-54496 ~4 yrs latent).
   The record is reviewed at every gate (§9.6, §10) and re-opened whenever the pinned implementation changes. An "unknown" on any line blocks adoption.
2. **Maintained upstream:** an active maintainer organization exists, with a security-advisory channel we can subscribe to (rubric line (g), kept here as a gate check).
3. **Incident history reviewed from primary sources:** advisories, CVEs, and postmortems read and summarized in the evidence dossier — not "no news is good news" (rubric line (h)).
4. **Minimal consensus delta:** our usage stays as close as possible to the audited baseline; every divergence is enumerated and justified.
5. **Reproducible test vectors** exist (or are written by us) for any behavior we change, checked in CI.
6. **Adversarial testing:** changed surfaces get fuzzing and adversarial tests, not just happy-path tests.
7. **Independent expert review/audit before mainnet** for every consensus or cryptographic delta, however small it looks.
8. **No unresolved critical or high findings** at any launch gate. Ship dates move; this bar does not.

### 2.3 Three principles that prevent self-deception

- **Copying audited code does not preserve its security.** An audit certifies a whole system under its stated assumptions. The moment we change an invariant — a value-balance rule, a proof statement, a serialization, an emission function — the audit's coverage is void on every path that touches the changed assumption. Re-review scope is therefore *the delta plus everything whose assumptions the delta touches*, not the delta alone.
- **A prototype demonstrates feasibility, never security.** Phase 0 prototypes exist to answer "can this work at all?" Nothing is security-approved because it ran on a devnet. Security approval comes only from the checklist above, applied at the M1–M3 gates (§10).
- **Inherited gadget layers get audited as if we wrote them** (*adopted 2026-09-05; from E1 §10 item 6, derived from Hornby's June 2026 work log, E1 §2a*). Four launch-blocking controls: (1) a full-stack, AI-assisted soundness audit of the inherited gadget/proof layer, not only pool or consensus code; (2) targeted, multi-trial, design-document-fed prompting rather than a single generic pass — the Orchard bug was found in only one of four generic-prompt runs; (3) a named human retained to defend low-signal-but-real findings against model skepticism; (4) balance-integrity audits re-run on each major new model release before every gate. One clean pass proves nothing; the controls exist because discovery was fragile.

---

## 3. Blunt audit of the January whitepaper

`assets/Meownero updated.pdf` (v1.1, "Merge-Mined Edition") is product vision and comedy, not a specification. Treat it as historical context. Specific defects that must not leak into engineering:

| # | Whitepaper claim | Reality |
|---|---|---|
| 1 | Monero miners solve "CryptoNight" puzzles | Monero abandoned CryptoNight for **RandomX** in November 2019. Every mining-related number and mechanism in the paper is built on a PoW that no longer exists. |
| 2 | "Kovri integration — the gold standard" | Kovri is **dead** (abandoned ~2019). Monero's actual network-layer stack is Dandelion++ (since 2020) plus optional Tor/I2P transaction relay. |
| 3 | "Meownero mandates a fixed ring size" / ring-signature framing | Monero's FCMP++ work **replaces ring signatures entirely** with full-chain membership proofs (anonymity set = the whole output set, ~10^8, instead of 16). Freezing 2022-era ring language into a new chain would ship obsolete privacy on day one. |
| 4 | "Attackers would need to defeat both networks simultaneously"; "instant, massive security from genesis" | **False.** A merge-mined chain inherits only the hashrate of miners who opt in, and attacking the aux chain costs a Monero miner nothing on Monero. A single large pool could reorg young Meownero at near-zero marginal cost (see §6.3). |
| 5 | "Monero nodes validate AuxPoW submissions, providing distributed verification" | **False.** Monero neither knows nor cares about aux chains. All AuxPoW validation happens on the aux chain's own nodes. Monero's only role is that its coinbase `tx_extra` can carry a commitment. |
| 6 | "~2 GH/s as of 2026" hashrate figure | Unverified; treat every quantitative claim in the paper as unchecked. |
| 7 | "1 MEOW/block reward is distributed to the Monero miner's AuxPoW coinbase address" | Sloppy. The aux reward goes to a Meownero address the miner configures in the merge-mining proxy; there is no such thing as paying a Meownero reward to a Monero coinbase. |
| 8 | References list | Thin and partly wrong — it cites the "Dogechain Whitepaper" (an unrelated EVM sidechain project), not Dogecoin. None of the load-bearing claims are sourced. |
| 9 | "ASIC resistance (complementary)" section | Hand-waves the actual constraint: to merge-mine with Monero, the PoW must **be RandomX** (same VM, same key schedule), not merely "ASIC resistant." |

**What the whitepaper gets right and we keep as working defaults:** mandatory privacy; no premine/dev tax; two-minute blocks (working value, pending benchmarks); fixed perpetual block subsidy as the monetary *shape* — agreed 2026-09-07, with matched-issuance benchmark candidates in §8.1 (the whitepaper's 1 MEOW/block is historical, not a current benchmark rate); community governance posture; and the jokes.

---

## 4. Candidate architectures (no preference — the evidence decides)

Two derivation candidates satisfy the hard requirements in principle. Neither is preferred today; ADR-001 selects at the end of Phase 0 by the rule in §5.4. Each candidate's honest strengths and open risks:

### 4.1 Candidate M — modern Monero-derived fork (FCMP++-era)

Fork `monero-project/monero`; change emission to linear; rebrand; re-genesis.

- **Inherent fit:** mandatory privacy by construction (zero delta for requirement #3); RandomX inherent (E5 delta = zero); merge-mining has a production template (Tari, §6).
- **Open risks to evidence:** FCMP++ is **not yet deployed** — stressnet-only as of 2026-09 (beta stressnet since 2026-05-06, `v0.19.0.0-alpha` builds; no fork date or height published; Trail of Bits cryptography audit 2026-08-17: six informational findings, zero low/medium/high — E6 §2, council pass 2026-09-05) — so at fork time its production history may be months, not years, and §2.2 applies to it exactly as it applies to anything else; the pre-FCMP++ ring construction is battle-tested but being replaced upstream. Large legacy C++ tree mid-transition through Monero's biggest-ever upgrade. Most exposed to the "cosmetic rename" criticism, so its deltas (emission, launch, possibly merge-mining) must be real and documented.
- **License:** BSD-3-Clause-style; RandomX BSD-3-Clause. Clean.

### 4.2 Candidate Z — Zcash/Zebra-derived, made mandatory-private

Build on Zebra (the Rust consensus node; `zcashd` hit end-of-life July 2026) with a shielded pool from the post-NU6.3 set — **Ironwood** (live since 2026-07-28) or **Sapling** — since **Orchard was sealed on 2026-07-28** (NU6.3, ZIP 258; E1 §2–3); add a consensus rule making shielded-only mandatory; emission to linear; re-genesis.

- **Inherent fit:** Ironwood ships with the strongest assurance artifact any shielded pool has had — a machine-checked Lean proof of circuit knowledge-soundness, CI-pinned to the deployed verifying key (Project Tachyon; ledger-level balance integrity is *not yet composed* with it and byte encodings remain external — E1 §4); Halo 2 has no trusted setup; Sapling has production history since 2018 (Pirate precedent) but upstream intends to restrict it (ZIP 219); modern memory-safe Rust with an active maintainer org whose June 2026 incident response was fast and documented in the ZIPs themselves (E1 §1).
- **Open risks to evidence:** privacy is optional upstream, so requirement #3 needs a consensus delta — its only production precedent (Pirate, Sapling-only since 2018; enforcing rule pinned to released code in E2 §2a) is on Sapling, and an Ironwood-only rule has no production precedent until Pirate's own Ironwood pool activates on 2026-10-03 (E2 §2c); the ASIC desideratum needs a PoW swap (E5); the `orchard` crate's license is **resolved** — MIT OR Apache-2.0 since v0.7.0 (2024), confirmed through the Ironwood-era 0.15.x releases (E1 §5); Zebra ships no wallet (E1); Ironwood carries a forward dependency (ZIP 2005's Recovery Protocol, proof system not yet selected) and its NU6.3 ZIPs were Draft/Proposed while live on mainnet — pin implementation tags, not spec text (E1 §3); upstream is churning (zcashd EOL, June 2026 Orchard vulnerability, NU7, Tachyon in flight); merge-mining would be unprecedented on this lineage (E6).

### 4.3 Pirate Chain — cautionary comparison (not a candidate)

Pirate Chain (ARRR, 2018) is the existence proof that **mandatory shielded transactions work in production** — z-address-only on Sapling, as a Komodo asset chain with delayed proof of work. That precedent is evidence for E2. It is equally the existence proof of what to avoid:

- **Front-loaded emission.** By Pirate's own FAQ, ~90% of the 200M supply is already mined; the schedule began at 256 ARRR/block and collapsed rapidly. Whatever the stated rationale, the outcome is that early miners hold the supply — exactly the "aggressive early emission resembles a premine" failure the whitepaper author flagged on 2026-01-15. Linear emission is the direct antidote.
- **Borrowed security with strings.** dPoW notarization trades 51% resistance for dependence on a notary set — a centralization trade to accept only knowingly, if ever (§6.4). **The strings got pulled:** Komodo v0.9.2 (2025-12-20) sunset notary dPoW in January 2026 in favor of developer-key auto-checkpointing; what Pirate's reduced 6-signature notary scheme anchors to post-sunset is unverified (E2 §2b).
- **Ecosystem fragility.** Dependence on another project's stack, thin dev funding, exchange attrition. Plan for all three.

### 4.4 Clean-room / new chain — rejected on security grounds

Writing new consensus or privacy cryptography from scratch violates §2.1 outright: the failure mode is an unaudited zk implementation guarding real money. Every hard requirement is achievable by deriving from an audited upstream. Rejected.

### 4.5 The honest scorecard (to be filled with evidence, not vibes)

| Axis | Candidate M | Candidate Z |
|---|---|---|
| Mandatory privacy delta | Zero (inherent) | Consensus rule; Sapling-only precedent (Pirate, 2018–); Ironwood-only unprecedented until Pirate's 2026-10-03 activation (E2) |
| Privacy-crypto production maturity | FCMP++: stressnet-only, not on mainnet, no fork date (E6 §2) | Ironwood: live 2026-07-28; circuit soundness machine-checked + CI-pinned, ledger composition not yet mechanized (E1 §4). Sapling: 2018–, upstream restricting (ZIP 219). Orchard: sealed after a 4-year-latent counterfeiting bug (E1 §2) |
| ASIC-resistant PoW delta | Zero (RandomX inherent) | PoW swap in Zebra (E5) |
| Merge-mining delta | Small; Tari template (E6) | Moderate; unprecedented on lineage (E6) |
| Emission delta | Small (E3) | Small; must also remove dev-fund streams (E3) |
| License | Clean | Clean — MIT/Apache-2.0 confirmed through Ironwood era (E1 §5) |
| Codebase | Legacy C++, mid-transition | Modern Rust; no wallet; churning upstream |
| "Not a cosmetic rename" | Must be earned via deltas | Inherent if E2 lands |

The two candidates have *complementary* delta profiles: M starts safe and must earn differentiation; Z starts different and must earn safety. That is a genuinely open question — which is why Phase 0 exists.

---

## 5. Phase 0 — evidence-first feasibility program

Phase 0's mandate, in order: **(1) establish what has already been done safely by others, from primary sources; (2) prototype only what the evidence supports; (3) decide the architecture from the evidence.** Prototypes demonstrate feasibility only — never security (§2.3).

**Rules:**

- **Timebox:** 8 weeks. Stage 1 (weeks 1–4): evidence dossiers E1–E6, desk research from primary sources. Stage 2 (weeks 5–8): feasibility prototypes for constructs that passed Stage 1 screening, plus thin control prototypes on both lineages. Hard stop.
- **Deliverable:** `ADR-001` recording each exploration's outcome and the architecture selection, signed by TJ and the whitepaper author.
- **Spikes are throwaway.** Phase 0 code lives under `spikes/` and is never promoted; this prevents sunk-cost capture.
- **Every dossier uses the same template:** production precedents & maturity evidence to verify · consensus/crypto delta · security assumptions introduced · audit burden · kill criteria · safest fallback. No dossier, no adoption.
- **Amendment process (adopted 2026-09-05).** Dossier findings never silently rewrite this plan. Amendments land as (1) one clearly labeled **clerical packet** per pass containing only source-backed factual corrections, each citing the dossier section that pins it, then (2) **normative changes as separate, dependency-ordered commits**, one decision each, after TJ/the whitepaper author sign-off — so doctrine cannot ride inside factual cleanup. Completed dossier work is not reopened by an amendment; new evidence gets a new dossier revision first.

### E1 — Zcash/Zebra/Orchard lineage viability

- **Precedents & maturity evidence to verify:** Orchard on Zcash mainnet since NU5 (May 2022) — value secured, incident record; Zebra's history as a production consensus node and its status as the sole maintained node post-zcashd-EOL (July 2026); primary-source review of the June 2026 Orchard vulnerability and the CVE-2019-7167 counterfeiting postmortem, including *how* each was found, disclosed, and fixed; maintainer funding/continuity (ECC, Zcash Foundation, Shielded Labs).
- **Consensus/crypto delta:** for lineage adoption itself: fork, re-genesis, network parameters — small. (Mandatory privacy, PoW, and emission deltas are E2/E5/E3.)
- **Security assumptions introduced:** soundness of Halo 2/Orchard circuits as deployed; upstream continuity; our team's competence in Rust consensus code.
- **Audit burden:** inherited audits cover only unmodified paths (§2.3); every delta re-reviewed; wallet path (Zallet/`zingolib` — Zebra ships no wallet) assessed separately.
- **Kill criteria:** ~~`orchard` BOSL license unobtainable/incompatible~~ (closed 2026-08-30 — MIT OR Apache-2.0, E1 §5); upstream maintenance collapse; total delta required by hard requirements exceeds the minimal-delta bar of §2.2.
- **Safest fallback:** Candidate M.

### E2 — Mandatory privacy: mechanism

- **Precedents & maturity evidence to verify:** Monero — mandatory-private by construction since 2014, the strongest precedent, inherited at zero delta by Candidate M; Pirate Chain — z-only enforced on Sapling since 2018 (verify its incident history and *how* enforcement is implemented, noting it runs zcashd-era code, not Zebra); Orchard is sealed (2026-07-28), so the Candidate Z rule is **Sapling-only** (Pirate precedent; enforcing consensus code pinned in E2 §2a — a single non-coinbase transparent-vout predicate, from which "coinbase first spend must shield" is emergent) or **Ironwood-only** (no production precedent; Pirate's Ironwood pool activates 2026-10-03, E2 §2c) — §2 applies with full force to the latter. Pirate's incident record is clean at chain level 2018–2026 (absence-of-evidence caveat), but its reorg resistance leaned on Komodo dPoW, which was sunset in January 2026 (E2 §2b).
- **Consensus/crypto delta:** Candidate M: zero. Candidate Z: consensus rule requiring empty transparent bundles for non-coinbase transactions + shielded coinbase (verified E2 §3a: the ZIP-213 all-zero-ovk rule makes shielded coinbase publicly decryptable, with post-NU6 exact balance equality, so per-block supply auditability and the §9.8 no-premine proof survive with **no transparent-coinbase exception**; Orchard coinbase is prohibited post-NU6.3) + removal/disabling of transparent RPC and mempool paths. Fees are public by construction (sum of `valueBalance` fields); structure counts leak (E2 §3a).
- **Security assumptions introduced (Z path):** our rule must not disturb value-balance accounting across pools, turnstile logic, or fee semantics; an all-shielded mempool changes DoS economics (every transaction carries heavy proof verification) — this needs adversarial analysis, not assumption.
- **Audit burden (Z path):** the rule plus every path whose invariants it touches; mempool DoS review; wallet shielded-only operation.
- **Kill criteria (for the Z mechanism, not the property):** unbounded patch surface, or any indication the rule perturbs audited invariants in ways review cannot bound.
- **Safest fallback:** Candidate M, where the property is inherent. The *product requirement* (§1.1 #3) is never dropped — only the risky mechanism is.
- **Pool scoping (Sapling-only vs. Ironwood-only) is decided at ADR-001** after the Ironwood eligibility gates in §7 are evaluated; not before.

### E3 — Monetary policy: fixed perpetual subsidy (agreed 2026-09-07; final parameters evidence-gated — §8.1)

- **Precedents & maturity evidence to verify:** Dogecoin — fixed 10,000 DOGE/block since 2015, ~11 years of production; Monero — tail emission 0.6 XMR/2-min block since 2022. Flat perpetual emission is among the *best*-evidenced ideas in this plan. Supporting analysis: Peter Todd's tail-emission argument.
- **Consensus/crypto delta:** the subsidy function — small on either lineage. Second-order deltas to map honestly: Candidate M's dynamic-block-size penalty math assumes its emission curve and must be re-derived, not copy-pasted; Candidate Z's consensus carries dev-fund/lockbox funding streams that a no-dev-tax chain must remove — parameter removal, small, but a consensus delta with test vectors like any other.
- **Security assumptions introduced:** essentially none beyond arithmetic correctness (overflow, rounding at atomic-unit scale).
- **Audit burden:** low — emission test vectors across the schedule, overflow/edge review.
- **Kill criteria:** none realistic for a perpetual schedule. A hard cap / fee-only endgame was **rejected on security grounds 2026-09-05** (E3 rev 2 §3–4: Carlsten et al. 2016, Budish 2018, Auer 2019 — fee-only mining is unstable and cannot fund a value-proportional security budget; no production counter-example exists).
- **Safest fallback:** upstream's native schedule (which would, however, forfeit a core fairness goal — flagged for TJ/the whitepaper author if it ever comes to that).

### E4 — Bitcoin interoperability / atomic swaps

- **Precedents & maturity evidence to verify:** COMIT `xmr-btc-swap` — production BTC↔XMR atomic swaps with all script logic on the Bitcoin side and a scriptless Monero side (verify current maintenance status and real usage); Farcaster (verify completion status); plain HTLC swaps on script-bearing chains (long-standing). **Critical evidence items:** whether existing XMR-swap constructions remain compatible with FCMP++'s changed spend authorization (Candidate M), and whether any adaptor-signature construction over RedPallas (Candidate Z's Orchard spend auth) has *any* reviewed precedent — Phase 0 result (E4 rev 2, 2026-09-04): **none exists**. COMIT `xmr-btc-swap` is unmaintained; its successor eigenwallet/core is actively maintained (release 4.14.0, 2026-08-22) but unaudited and silent on FCMP++; Farcaster is dormant at the protocol layer since 2023–24; the only shielded-native attempt (Zwap, Orchard↔EVM, never Bitcoin) was abandoned in 2026 on a structural obstacle — Orchard/Ironwood have no script primitives; and a transparent-HTLC bounce is impossible under mandatory privacy (E2's rule forbids value-bearing transparent vouts, and shielded pools expose no script layer — E4 §2b). Any future swap is therefore scriptless/ZK-binding by necessity, and FCMP++ replaces CLSAG spend-auth with a Generalized Schnorr Protocol, so CLSAG-specific swap code must be rewired (E4 §2). E4 §9 lists the zero-cost prerequisites to preserve.
- **Consensus/crypto delta:** target zero consensus delta — swap logic belongs on Bitcoin's side and in off-chain protocol implementations. The crypto delta (adaptor signatures over our spend-auth scheme) is the risk, and it is real on both candidates post-upstream-changes.
- **Security assumptions introduced:** adaptor-signature security over the specific scheme; swap-implementation correctness. Mitigating scope: swap failures lose swap participants' funds, not chain consensus — bad, but bounded.
- **Audit burden:** external cryptographer review of the construction; audit of any swap implementation we endorse.
- **Kill criteria — met, decision recorded 2026-09-05:** no reviewed construction exists for either lineage (E4 rev 2) → interop is **deferred to post-launch**, preserving the six zero-cost prerequisites in E4 §9 (unmodified spend-auth algebra, documented curves/encodings, upstream-aligned nonce behavior, HTLCs acknowledged as foreclosed, no note/spend-structure deltas, neither mechanism family credited as shippable). **Re-entry condition:** a reviewed, production-quality swap implementation over our shipped spend-auth scheme (M-path: an audited FCMP++-era eigenwallet or equivalent; Z-path: a reviewed scriptless/ZK-binding shielded-pool design with a Bitcoin instance), assessed through the full §2.2 rubric. Never launch-blocking; never fallback-triggering; never architecture-deciding.
- **Safest fallback:** no protocol-level interop at launch; swaps via exchanges/OTC; revisit as the research matures. Explicitly rejected regardless of evidence: custodial bridges, federated pegs, wrapped assets — their trust assumptions fail §2.1 by construction.

### E5 — PoW: RandomX and the honest ASIC posture

- **Precedents & maturity evidence to verify:** RandomX — Monero's PoW since November 2019 (~7 years securing a top-tier privacy coin), plus adoption by other chains (Tari's variant since 2025; others); Equihash — battle-tested for the Zcash lineage but ASIC-dominated (mature commercial ASICs), so it fails the *desideratum* while passing the *security* bar; difficulty algorithms — review LWMA-family incident history across the small-chain ecosystem from primary sources (several small chains suffered difficulty-oscillation and timestamp attacks; learn from their postmortems).
- **Consensus/crypto delta:** Candidate M: zero. Candidate Z: replace Equihash validation with RandomX in Zebra — no new cryptography (RandomX itself is proven), but a **novel integration** with real surface: seed/key-schedule handling, dataset memory management, verification-cost DoS.
- **Security assumptions introduced:** correctness of the integration; verification performance under adversarial load.
- **Audit burden (Z path):** integration review + fuzzing of the validation path + difficulty-algorithm simulation under hashrate whiplash.
- **Kill criteria (Z path):** integration proves intractable or un-reviewable in scope → either keep lineage-native Equihash with an *honest* public ASIC disclosure (dropping the desideratum), or weigh Candidate M where RandomX is free.
- **Safest fallback:** lineage-native PoW with honest disclosure.
- **Honest posture to publish either way:** "ASIC-unfriendly today, re-evaluated at every scheduled upgrade" — permanent ASIC resistance is not a promise anyone can keep, and we will not make it.

### E6 — Merge-mining with Monero

- **Precedents & maturity evidence to verify:** Namecoin — AuxPoW with Bitcoin since 2011, the oldest precedent; Dogecoin — merge-mined with Litecoin since 2014, the strongest *positive* security precedent (majority of parent hashrate participates); Tari — the only RandomX/Monero production precedent, mainnet since May 2025 (**young — ~15 months; weigh accordingly against §2.2 item 1**); CoiledCoin — the canonical *negative* precedent (killed by a single parent-chain pool in 2012 at effectively zero cost). Full technical audit in §6.
- **Consensus/crypto delta:** no new cryptography, but a moderate consensus delta on either candidate: validation of the Monero PoW package (header, coinbase merkle proof, `tx_extra` commitment) including tracking valid Monero RandomX seeds. On Candidate Z this compounds with E5's integration; on Candidate M it follows the Tari template more directly.
- **Security assumptions introduced:** parent-chain miner behavior (the zero-cost-attacker class of §6.3 is *accepted*, not mitigated, by choosing merge-mining); multi-aux coexistence with Tari in the shared coinbase field.
- **Audit burden:** the validation code path is consensus-critical and gets full adversarial review; proxy is non-consensus but supply-chain-relevant.
- **Kill criteria:** the §6.3 security model is judged unacceptable for a young chain; or insufficient pool commitment to make opt-in hashrate meaningful; or the delta fails the minimal-delta bar on the chosen lineage.
- **Safest fallback:** solo-mined launch (Monero itself launched solo; so did nearly everyone). Merge-mining can be added by a later, properly audited upgrade if the evidence improves.

### Control prototypes (Stage 2, both lineages, throwaway)

Boot a minimal private devnet on **each** candidate — Candidate M with the emission patch; Candidate Z stock — documenting every touched file and every surprise. Purpose: calibrate effort honestly and verify tooling paths (including Zebra's configurable custom-network support and a wallet round-trip). Feasibility only; §2.3 applies.

### 5.4 Decision rule (ADR-001, end of week 8)

1. Enumerate, per candidate, the **total consensus + cryptographic delta** required to satisfy the hard requirements (§1.1) plus whichever desiderata survived their kill criteria.
2. Score each delta against the §2.2 checklist using the dossier evidence.
3. **Select the candidate with the smallest total unproven surface.** Desiderata never outvote security: any desideratum whose only path fails §2.2 is deferred or dropped, not forced through. *(Reaffirmed 2026-09-05: no launch-feature exceptions exist; mainnet quality is the only launch priority.)*
4. If the evidence is genuinely inconclusive, §2.1 breaks the tie: the less novel architecture wins.
5. TJ and the whitepaper author sign. Dissent is recorded in the ADR, not litigated on Twitter.

---

## 6. Merge-mining technical audit (evidence annex to E6)

### 6.1 Verdict

**Merge-mining with modern Monero is technically feasible and production-proven in one young instance — and the whitepaper's security story is wrong.** The CryptoNight/AuxPoW framing is obsolete; the working model is the one Tari runs today on RandomX.

### 6.2 How it actually works (Tari precedent)

Tari (mainnet since May 2025, founded by early Monero contributors) merge-mines with Monero with **zero Monero consensus changes** (Tari RFC-0132):

- The aux chain's block-header hash is embedded in the **merge-mining subfield of the Monero coinbase transaction's `tx_extra`**. Because the coinbase hashes into Monero's transaction merkle root, the aux commitment is bound into Monero's RandomX PoW.
- The aux chain's nodes validate a proof package (Monero header fields, RandomX VM key, coinbase merkle proof, coinbase extra) and accept the block if the achieved RandomX difficulty meets the *aux chain's own* target.
- Miners run a merge-mining proxy between their mining software (XMRig) and both daemons; the proxy sets the job difficulty so one solve can satisfy either chain.

Consequences for Meownero:

- **The PoW must be RandomX**, byte-compatible with Monero's parameters — E5 and E6 interlock. Validating Monero-seeded RandomX proofs means the aux chain must track valid Monero key-block seeds (as Tari's `MoneroPowData` does); this is real consensus-critical complexity.
- FCMP++ does not change Monero's PoW, so the mechanism survives the FCMP++ era. (Cannot be verified against shipped hard-fork code until FCMP++ ships — stressnet-only as of 2026-09, E6 §2; merge-mining validation would target 0.18.x mainnet rules and track the eventual release.)
- **The `tx_extra` merge-mining field is a shared, contended resource.** Pools already merge-mining Tari can only add Meownero via an aux-chain merkle tree in that single field. Any proxy and validation we build must support multi-aux from day one, or the largest merge-mining pools cannot carry us.
- **Precedent-maturity caveat:** Tari proved the mechanism for a chain designed around it, and only recently. Namecoin and Dogecoin prove AuxPoW longevity in *other* PoW families. Porting the model to a Zcash-derived node would be a first — priced into E6's kill criteria.

### 6.3 The honest security model

- Day-one security equals **the hashrate of miners who opt in**, not "Monero's hashrate." If 2% of Monero merge-mines Meownero, our security is 2% of Monero — and any pool larger than that can 51% us.
- Attacking the aux chain is **costless on the parent chain**: a Monero pool can double-spend or censor Meownero while continuing to earn full XMR rewards. History has receipts — Eligius killed CoiledCoin in 2012 at effectively zero cost. The whitepaper's "must defeat both networks" claim inverts reality. Dogecoin's counter-example shows the model *can* mature well — once most of the parent's hashrate participates, which took years and an existential fee argument.
- Merge-mining also cuts the other way for fairness: it lowers the cost for honest hashrate to show up — the more pools that adopt at genesis, the smaller any one pool's share.
- Solo-mined launch has the young-chain hashrate problem too — smaller and slower-arriving, but nobody attacks it for free from an adjacent chain. The tradeoff is genuinely two-sided; that is why E6 is a decision with kill criteria, not a default.

### 6.4 Mitigations to evaluate in E6 (none are free)

1. **Maximize pool adoption before genesis** — outreach to major Monero pools and P2Pool, a polished proxy, a mining one-pager. The primary mitigation if merge-mining is chosen.
2. **Deep-reorg dampening** (rolling finality window / checkpoint policy) — effective, but a centralization trade that must be explicit, bounded, and ideally sunset-dated. Pirate's dPoW is the cautionary extreme.
3. **Hybrid solo+merge mining** (Tari-style split) — hedges pool capture but doubles mining-path complexity.
4. **Exchange/merchant confirmation guidance** scaled to observed hashrate, published from day one.

---

## 7. Privacy primitives (evidence annex to E1/E2)

Ground rule from the brief: recommend based on **current upstream reality**, not the draft's Kovri/ring-size language.

- **Candidate M:** FCMP++-era privacy — full-chain membership proofs, RingCT hidden amounts, stealth addresses. Do **not** fork pre-FCMP++ and freeze ring signatures (obsolete on arrival); but note the flip side honestly: forking *at* FCMP++ means adopting cryptography with a short production history — the §2.2 rubric applies to FCMP++ exactly as to any pool. Status 2026-09: stressnet-only, no fork date; Veridise audited the algorithm (2025) and Trail of Bits the cryptography implementation (2026-08-17, six informational, zero severity-rated) and core integration (May 2026, report pending publication); stressnet surfaced and fixed double-spend edge cases (E6 §2; council pass 2026-09-05).
- **Candidate Z:** **Ironwood** (Halo 2, no trusted setup; live since 2026-07-28; Project Tachyon's Lean proof of circuit knowledge-soundness is CI-pinned to the deployed verifying key, but ledger-level balance integrity is not yet composed with it and byte encodings/transcripts/BLAKE2b remain outside the proof — E1 §4, re-verified against tachyon.z.cash and the Ironwood Book 2026-09-05) or **Sapling** (2018–, Groth16 with trusted setup; upstream restricting per ZIP 219). Orchard is sealed. Shielded coinbase per ZIP-213 (verified, E2 §3a); transparent pool removed per E2. Ironwood carries a forward dependency (ZIP 2005 Recovery Protocol, proof system unselected). The June 2026 Orchard vulnerability — a missing copy constraint in the shared `halo2_gadgets` library (CVE-2026-54496), undetected for four years across multiple audits, found in days by a targeted AI-assisted review (E1 §2a) — is the reason inherited gadget libraries sit inside the audit surface for **either** candidate, and why production time is not a soundness proxy (§2.2).
- **Network layer (honest gap either way):** Monero lineage inherits Dandelion++ and Tor/I2P relay; **the Zcash lineage has no Dandelion++ equivalent in production**. On Candidate Z, network-layer privacy work would be a delta to design, build, and review — tracked in the threat model, never claimed before it exists.
- **Crypto eligibility posture (group decision 2026-09-05; governs both candidates until ADR-001).** *Mainnet-first, no calendar floor.* A shielded-pool construction becomes eligible only after it is live on a mainnet securing real value **and** its §2.2 readiness record is complete.
  - **Ironwood: live, not approved today.** Do not reconsider before (i) Pirate Chain's Ironwood-pool activation on **2026-10-03** has been observed — clean activation, no consensus fault, and confirmation that Pirate's `halo2` pins include the June 2026 gadget fix (E2 §2c) — and (ii) the exact gadget-layer, encoding/transcript, and integration review required by §2.2 lines (b)–(d) and §2.3 has been completed against the pinned Zebra tag and `orchard` release. The Tachyon composition gap (ledger ↔ circuit) and external encodings are recorded facts in that review, not blockers by themselves; whether they block is decided by the completed record, not by elapsed time.
  - **Sapling:** eligible for review under the same rubric; its record must weigh ZIP 219 (upstream intent to restrict) under line (g).
  - **FCMP++: do not wait for it** while it remains stressnet-only. Monitor `monero-project/monero` releases and MRL; **if a stable mainnet release lands before ADR-001, reassess Candidate M** under the full rubric (Veridise 2025 + Trail of Bits 2026 audits, the partially-resolved FFI finding, and mainnet incident record from activation). Until then Candidate M's privacy layer is scored as the pre-FCMP++ ring construction it actually ships, with the upstream transition cost counted against it (§4.1).
  - No fixed calendar floor applies to any of the above; "wait" means "wait for the named evidence," not for a date.
- **Non-goals for v1:** §2.1 verbatim — no novel cryptography, no custom curves, no bespoke proof systems. The single adjacent item, E4's adaptor-signature question, ships nothing without reviewed precedent.
- **Supply auditability caveat (must be disclosed honestly):** hidden-amount chains cannot be trivially supply-audited; soundness of the proofs is the backstop, and an undetected inflation bug is the worst-case failure (Zcash CVE-2019-7167; Monero's 2017 key-image bug; Zcash CVE-2026-54496). Precise formulation for anything public (Shielded Labs, June 2026; E1 §10 item 3): a pool turnstile bounds the value that *leaves* a pool, but there is "no definitive way to determine using only cryptography" whether counterfeit value was created inside it. On a mandatory-shielded Zcash-lineage chain, per-block supply auditability nonetheless holds via publicly decryptable shielded coinbase (E2 §3a). Mitigations: minimize deltas to audited upstream code, run duplicate-nullifier/key-image monitors, adopt upstream turnstile/audit tooling as it lands.

---

## 8. Emission and fair launch

### 8.1 Emission schedule — fixed perpetual subsidy agreed; final parameters evidence-gated

**Decision (group update relayed by TJ, 2026-09-07; supersedes the open schedule choices of 2026-09-05).** Fair launch, **zero premine and a small fixed perpetual subsidy** are agreed. The flat shape is settled; decay-to-tail and an initially ultra-low percentage-inflation target are not pending votes. Retain sufficient decimal precision for small payments and simplify wallet display independently of consensus/RPC precision. Mainnet-quality gates remain unchanged.

**Benchmark candidates, not launch promises:** keep the current implementation at **0.9 MEOW / 120 s** and compare **0.675 MEOW / 90 s**. Both preserve candidate time-based issuance of **236,520 MEOW per 365 days** (648/day): 262,800 × 0.9 = 350,400 × 0.675. These are expected issuance rates at target spacing, not guaranteed calendar payouts. **0.9 MEOW / 90 s would issue 315,360/year (+1/3) and is not approved.** 120 s is a working target, not a theoretical limit; 90 s is motivated by the nine theme but must earn selection through propagation, proof-validation, competing-block/orphan and reorg evidence. Do not lock 90 s or weaken release gates to achieve it.

**Adoption evidence:** no demonstrated causal evidence establishes that hard caps or perpetual issuance win adoption. The security-budget rationale for this design is not an adoption result. Use measured payment completion, conversion and retention evidence with denominators, observation periods and confounders disclosed; community preferences and denomination changes are not causal evidence.

Why perpetual (unchanged from E3 rev 1, now decided): a permanent security budget with no fee-only terminal regime (Todd 2022; Carlsten et al. 2016); the least front-loaded distribution available; one constant. Rejected alternatives: Monero-style declining curve *as the only mechanism* (favors early holders — the whitepaper author, 2026-01-15), capped supply (terminal security budget), "divisibility instead of emission."

**Supply-model audit (2026-09-05).** The fair-launch model in §8.2 is exact: genesis carries **zero spendable outputs**, no premine, no allocation, so supply at height *h* is *h* × subsidy and nothing else. Consequences that follow from arithmetic, not policy:

1. **Percentage inflation is undefined at genesis and, for any flat schedule, equals 1/(N−1) during year N — independent of the rate.** 100% (yr 2), 50% (yr 3), 25% (yr 5), 10% (yr 11), 5% (yr 21), 3.03% (yr 34), 2% (yr 51), 1% (yr 101).
2. **For any positive-issuance schedule with zero genesis supply, inflation in year N is issuance_N ÷ cumulative_(N−1).** Hitting a target *x* by year N requires cumulative_(N−1) ≥ issuance_N ÷ *x* — i.e. most of the eventual supply must already exist. Only two things produce that: (i) a large genesis supply, which is a **premine** and forbidden by §1.1 #5, or (ii) **front-loaded early issuance**, the Pirate failure mode (§4.3) that §1.1 #4 exists to prevent.
3. **Therefore any constraint of the form "below fiat inflation (≈2–3%) from the early years" or "initial deflation" is mathematically incompatible with flat-from-genesis positive issuance and no premine.** At 0.9 MEOW/block, showing 3% in year 2 would need a 7,884,000 MEOW genesis supply; 2% would need 11,826,000. A **999,999,999 "genesis supply" is a premine** — it would make year-1 issuance read as 0.024% "inflation" precisely because 99.98% of the coin would pre-exist mining. **Rejected.** No such claim is ratified, and none may appear in brand copy.
4. Todd's convergence result (E3 §4b: circulating supply → issuance ÷ loss-rate) is a **long-run** statement about *circulating* supply under coin loss. It does not lower early-year percentage inflation and must not be marketed as if it did.
5. **No burn mechanism is added to manufacture a deflation narrative.** A burn is a consensus delta with its own audit cost and no security purpose here (§2.1 "prefer subtraction").

**Historical comparison (2026-09-05), not current ballot options.** The 2026-09-07 decision selects the fixed perpetual shape and honest percentage-growth disclosure; decay-to-tail below is not approved. All figures at 262,800 blocks/yr; percentages are inflation *during* the named year.

| Option | Shape | Yr 2 | Yr 5 | Yr 11 | Yr 20 | Yr 35 | Share of yr-20 supply issued in yrs 1–2 / 1–8 | Trade |
|---|---|---|---|---|---|---|---|---|
| **P-flat 0.9** (candidate) | 0.9/block forever | 100% | 25% | 10% | 5.3% | 2.9% | 10% / 40% | Least front-loaded; "same meow forever"; high early % is the honest price of no premine |
| **P-decay-to-tail** (illustrative: 9/block yr 1, ×0.75 per year, floor 0.9 from yr 9) | Monero-shaped decline into a 0.9 tail | 75% | 11.6% | 2.6% | 2.1% | 1.6% | 36% / 75% | Lower % sooner, but three-quarters of the year-20 supply goes to the first eight years' miners — a fairness cost against §1.1 #4 |
| **Restate the constraint** | Keep P-flat; publish issuance as constant MEOW/yr and the 1/(N−1) curve honestly | as P-flat | | | | | as P-flat | No consensus change; brand copy changes; the only option that satisfies §1.1 #4, #5 *and* says nothing false |

**Claims decision (2026-09-07):** drop initially ultra-low percentage inflation and deflation claims. Flat issuance from zero has high early percentage growth irrespective of denomination; smaller units do not change the arithmetic.

- **Unfinalized parameters for ADR-001:** the 90 s / 0.675 versus 120 s / 0.9 pairing after comparative benchmarks, preserving the candidate annual issuance above; exact atomic-unit precision (retain the inherited 12 dp until justified otherwise); wallet presentation that simplifies display without losing nonzero amounts or rounding payment inputs silently; fee policy and block-weight limits/penalties rechecked for the chosen subsidy and spacing; launch difficulty and network timeouts. The flat perpetual shape, zero premine and honest claims are not open parameters.

### 8.2 No premine, no dev tax — and what "no insider advantage" requires operationally

- Genesis block contains **zero spendable outputs** to any party. Genesis message: something datestamped and public (headline + cat pun), chosen at the launch livestream, not before.
- Founders/insiders mine under **exactly the same conditions** as the public: same binaries, same announcement, same start time. TJ and the whitepaper author disclose that they will be mining.
- **No secret pre-genesis testing advantage:** the final chain parameters (genesis hash excepted) are public at least 2 weeks before launch; anyone can pre-provision miners.

### 8.3 Launch process (fairness is a procedure, not a vibe)

1. **T−4 weeks:** launch date/time announced publicly; parameters frozen and published; mining guide (and merge-mining proxy, if E6 survived) released for testnet rehearsal.
2. **T−2 weeks:** release-candidate binaries published with SHA-256 hashes and signatures; reproducible-build instructions public so third parties can verify (§9.4). Pool outreach concludes; committed pools listed publicly.
3. **T−0:** genesis at the announced timestamp. Initial difficulty set to a sane floor (not 1) with a well-precedented adjustment algorithm (E5 §2 records the LWMA family's incident history — a >50% selfish-mine via mishandled negative solvetimes, Verge's 2018 timestamp collapse — and the published mitigations to adopt: FTL ≈ T×N/20, ±6·T solvetime clamp, N ≈ 45–120 window, never feed the algorithm from lagged MTP) so early blocks cannot be insta-minted faster than difficulty reacts; with a constant 1 MEOW reward the worst case is bounded, but a chaotic first hour is still a reorg risk and a bad look.
4. **T+2 weeks:** post-launch fairness report — blocks mined, pool distribution, any incidents — published against the pre-committed criteria.

### 8.4 Dev funding without a founder tax

Protocol allocates nothing to anyone — that is settled. Development is funded by: (a) a **disclosed, multisig community donation fund** (Monero CCS-style, proposals public), (b) direct sponsorship of specific audits or bounties, (c) volunteer work. The group's own capital ("$100K in the group") may seed the donation fund like any other donor — publicly, at market terms, with addresses disclosed. Buying MEOW from members via "wire instructions" (the 02-06 chat bit) is exactly the kind of informal insider dealing that must **not** happen once this is real; all acquisition is mining or open-market.

### 8.5 Mining-pool incentives

Pools carry us or nobody does — in every PoW configuration. Concretely: pool-operator documentation and a pool reference deployment; a testnet dry-run with at least two independent pools before mainnet; zero pool fees taken by the project (pools set their own); and, if E6 survives, a multi-aux-capable proxy that coexists with Tari. If E5 lands on RandomX, solo CPU mining stays genuinely viable — the "everyone in the group mines it" story from the chat is real on RandomX in a way it never was on ASIC-dominated algorithms.

---

## 9. Security, legal, and operational program

### 9.1 Threat model (v0 — to be formalized as a living doc)

| Threat | Vector | Posture |
|---|---|---|
| 51% / deep reorg | Young-chain hashrate; if merge-mined, a large Monero pool attacks at zero parent-chain cost | §6.3–6.4; E6 decision; confirmation guidance; chain monitoring |
| Inflation bug | Soundness flaw in shielded/membership proofs or our patches | §2 framework; minimal deltas; upstream advisory tracking; duplicate-nullifier/key-image monitors; external audit before mainnet |
| Tx-graph/timing analysis | Statistical deanonymization, poisoned outputs | Whole-pool anonymity sets (Orchard / FCMP++); wallet-side guidance |
| Network-layer deanonymization | IP linkage, eclipse/sybil attacks on P2P | Lineage-dependent (§7); Tor relay support; diverse seed nodes; anchor connections |
| Interop-layer attacks | Swap counterparty griefing, adaptor-signature implementation flaws | E4 ships nothing unreviewed; swap losses bounded to participants |
| Supply-chain compromise | Malicious dependency, compromised CI, backdoored release | §9.4; two-person release rule; dependency pinning + review |
| Key compromise | Release-signing or seed-node keys stolen | §9.5 |
| Social/insider | "Leak" paranoia (see 02-10 chat), squatter projects, fake binaries | Everything public by default; official-channel discipline; the Solana "Meownero" is a brand problem, not a chain problem |
| Regulatory shock | Exchange delistings of privacy coins, jurisdictional bans | §9.2; design assumes no exchange support at launch |
| Upstream shock | Critical vulnerability disclosed upstream post-fork | 72h security-merge SLA; §9.9 rehearsed playbook |

### 9.2 Questions for legal counsel (obtain real counsel; none of this is settled by us)

1. Exposure of identifiable founders launching a **mandatory-privacy** coin: money-transmission, sanctions (OFAC precedent from the Tornado Cash saga), and jurisdiction-specific privacy-coin bans (e.g., Japan, South Korea; EU AMLR trajectory for 2027).
2. Does a zero-premine, no-sale, mined-only launch keep MEOW clearly outside securities frameworks (Howey / MiCA utility analysis)? What launch communications would jeopardize that?
3. ~~BOSL obligations and grant path for the `orchard` crate~~ — **closed** (E1 §5: MIT OR Apache-2.0 since v0.7.0, confirmed through Ironwood-era releases); no license question remains that can move the architecture.
4. Legal posture of facilitating BTC↔MEOW atomic swaps or hosting swap infrastructure (E4) — protocol vs. operator liability.
5. Liability for marketing claims: the coin art literally says "no trace currency" and "zero logs" — what claims can we responsibly make?
6. Trademark: register "Meownero"? Posture toward the pre-existing Solana "Meownero" token; risk that *we* are accused of association with it.
7. Domain/entity structure: should meownero.com and the donation multisig sit in a foundation or association rather than with TJ personally?
8. Contributor exposure: does merging code or running seed nodes create liability for individual group members?

### 9.3 Upstream licenses and attribution

- **Monero (Candidate M):** BSD-3-Clause-style — fork-friendly; preserve notices; attribute prominently. **RandomX:** BSD-3-Clause.
- **Zcash stack (Candidate Z):** Zebra and librustzcash are MIT/Apache-2.0; the `orchard` crate is **MIT OR Apache-2.0** since v0.7.0 (2024), confirmed for 0.15.x and `zcash/ironwood` (E1 §5); no BOSL question remains. `halo2` crates pinned in the same audit.
- **Tari:** if E6 adapts their proxy or validation code, verify license (BSD-3-Clause family) and attribute.
- Deliverable: `LICENSES.md` + per-file header audit before any code is vendored.

### 9.4 Supply-chain security and reproducible builds

- Deterministic builds from day one: Candidate M inherits Monero's Guix pipeline; Candidate Z uses pinned Rust toolchain, committed lockfiles, vendored dependencies, and a reproducibility harness.
- All release binaries built by ≥2 independent parties whose hashes must match before publication; hashes + minisign/GPG signatures published on the site and in-repo.
- Dependency policy: pinned versions, lockfiles committed, no dependency added without review; CI runs from committed config only; branch protection + signed commits for consensus-critical paths.

### 9.5 Key management

- **Release-signing keys:** hardware-backed, held by ≥2 maintainers (TJ + the whitepaper author to start), with a published key-transparency page and revocation procedure.
- **Donation fund:** m-of-n multisig, holders disclosed, no single spender.
- **Seed-node infrastructure:** separate credentials per node, no shared root, documented rotation.
- **No "network keys" exist** in this architecture — no trusted setup we control, nothing like a mint key — and we must be able to say so truthfully.

### 9.6 Testnet → mainnet gates

Each promotion requires **all** exit criteria of the prior stage (§10) plus the §2.2 checklist for every consensus/crypto delta: no open consensus-severity bugs; external audit findings triaged with **zero unresolved critical/high**; two independent pools mining on testnet; reproducible-build verification by a third party; incident-response runbook rehearsed once.

### 9.7 Wallets, node, and miner tooling (v1 scope)

- **v1:** the lineage daemon + a CLI wallet (Candidate M: inherited; Candidate Z: a Zallet/`zingolib`-derived shielded-only port — **Zebra ships no wallet; on that lineage the wallet is launch-critical path from week 1**), mining guide, and the merge-mining proxy if E6 survived.
- **v1.x:** GUI wallet (rebrand an upstream GUI where licensing allows), light-wallet support with honest privacy caveats about trusting a light server.
- **Later, explicitly not launch-blocking:** mobile wallets, hardware-wallet integration, merchant tooling, swap infrastructure (E4).

### 9.8 Block explorer for a private chain

An explorer can show: block heights/hashes/timestamps, tx hashes and sizes, fee totals (public in both lineages), emission tally, and hashrate/difficulty — and **cannot** show amounts, senders, or recipients. Build or adapt a minimal explorer; document loudly that "the explorer looks empty of amounts" is the product working. Supply tally page (`emission = height × subsidy`; genesis contributes zero) doubles as a public no-premine proof — and, because genesis is zero, as the public record that the §8.1 inflation curve is exactly 1/(N−1) and nothing lower.

### 9.9 Incident response

- Published security policy + PGP/security@ contact before mainnet; 90-day coordinated disclosure default.
- Consensus-bug playbook drafted and rehearsed pre-launch: severity ladder, who can call for an emergency patch or rollback, pool/exchange contact tree, pre-agreed public-comms template. The June 2026 Orchard vulnerability and zcashd's emergency EOL are the case study: mature upstreams *do* have fire drills, and we inherit whichever lineage's we choose.
- Upstream watch: security advisories for the chosen lineage (plus Monero's in any case if E6 survives, since merge-mining creates a dependency), RandomX repo if adopted.

---

## 10. Milestones and exit criteria

**M0 — Phase 0 evidence-first program, weeks 1–8** (§5).
Stage 1: evidence dossiers E1–E6 from primary sources. Stage 2: screened feasibility prototypes + both-lineage control prototypes.
*Exit criteria:* every dossier complete with primary-source citations against the §5 template; prototypes documented with the explicit caption "feasibility only, not security" (§2.3); ADR-001 signed by TJ and the whitepaper author selecting the architecture per §5.4 and dispositioning every desideratum (adopt / defer / drop). **No fork is blessed until this gate passes.**

**M1 — Foundation, weeks 9–14.**
Repo layout from the chosen upstream at a pinned tag; consensus deltas as a reviewable patch series; threat model v1; CI + reproducible-build pipeline green; test vectors for every changed behavior (§2.2 item 5); wallet-path work started if on Candidate Z.
*Exit criteria:* clean build from source by an outsider following docs; every consensus delta has an ADR and test vectors; `git diff` vs upstream tag is enumerable and justified.

**M2 — Private devnet, weeks 15–22.**
Multi-node devnet exercising every adopted delta (emission, mandatory-privacy mechanism, PoW, merge-mining if adopted); CLI wallet round-trip; explorer alpha; difficulty algorithm validated under hashrate-whiplash simulation; fuzzing running on changed surfaces (§2.2 item 6).
*Exit criteria:* 2-week devnet uptime without consensus fault; reorg/partition chaos tests pass; fairness-relevant parameters frozen.

**M3 — Public testnet + audit, weeks 23–34.**
Public testnet with ≥2 independent pools; **independent expert review/audit of every consensus and cryptographic delta** (§2.2 item 7); bug bounty opens; launch-procedure dry run including a rehearsed incident.
*Exit criteria:* zero unresolved critical/high findings (§2.2 item 8); third-party reproducible-build verification; testnet survives an invited adversarial event; §9.6 gates met.

**M4 — Mainnet launch.**
Execute §8.3 exactly as published.
*Exit criteria:* genesis at announced time; ≥2 independent pools mining in the first 24h; post-launch fairness report published at T+2 weeks.

**M5 — Post-launch hardening.** GUI wallet, light-wallet infrastructure, seed-node diversity, upstream-merge cadence, deferred desiderata (E4 research, E6 if deferred), governance formalization. (Deliberately unscheduled until M4 lands.)

---

## 11. Two tracks: consensus engineering vs. Much Meow

These run in parallel and must never share a critical path:

- **Consensus track (this document, §§2–10):** slow, reviewed, audited, boring on purpose. No memes in commit messages on consensus code. the whitepaper author's "no script-kiddie vibes" applies here: clean history, ADRs, signed releases.
- **Brand/launch track:** the coin art (already canon, `assets/PHOTO-2026-01-14-20-32-47.jpg`), "Much Meow" voice guide, meownero.com site, a *rewritten* whitepaper v2 (this plan's content, whitepaper's voice — the Super Troopers energy stays), launch livestream, T-shirts (a group member gets the merch lane, wolf shirts and all), community channels + moderation plan, and the Twitter presence (organic; a group member's "army of bots" is vetoed — bot amplification is exactly the sketch we're avoiding).
- The brand track may ship whenever it wants **except** claims about the chain, which must be reviewed against this plan (see §9.2 item 5 on "no trace" claims — and nobody promises features still in exploration: no "Bitcoin bridge," no "ASIC-proof," no "secured by Monero" anywhere, ever).

---

## 12. First 10 GitHub issues

1. **ADR-001 scaffold + evidence-dossier template** — encode the §5 template (precedents/maturity · delta · assumptions · audit burden · kill criteria · fallback) and the §5.4 decision rule; owners TJ + the whitepaper author. *(M0)*
2. **E1 dossier: Zcash/Zebra/Orchard lineage** — production-maturity evidence, incident review from primary sources (June 2026 Orchard vuln, CVE-2019-7167), maintainer continuity, wallet-path assessment. License audit closed (MIT/Apache-2.0). *(M0)*
3. **E2 dossier: mandatory-privacy mechanisms** — Monero-inherent vs. Pirate/Sapling precedent vs. unprecedented Orchard-only rule; for the Z mechanism, enumerate the patch surface and the invariants it touches (value balance, turnstiles, mempool DoS). *(M0)*
4. **E3 dossier + emission spec v1** — Dogecoin/Monero-tail precedent record; per-lineage delta map (penalty math on M, dev-fund stream removal on Z); atomic units, fee policy, 120s check, difficulty parameters. *(M0)*
5. **E4 dossier: atomic-swap evidence** — xmr-btc-swap/Farcaster maturity and maintenance status; FCMP++ swap-compatibility question; RedPallas adaptor-signature precedent search; external cryptographer consult; launch verdict (expected: defer). *(M0)*
6. **E5 dossier: PoW evidence** — RandomX production record; Equihash ASIC landscape; LWMA-family incident review from small-chain postmortems; Z-path integration scope. *(M0)*
7. **E6 dossier: merge-mining evidence** — Namecoin/Dogecoin/Tari/CoiledCoin precedent review; verify §6 against Tari's shipped code and FCMP++-era Monero; pool-commitment soundings. *(M0)*
8. **Incident-history review pack** — primary-source summaries of the major Monero and Zcash security incidents and responses, feeding §2.2 item 3 for both candidates. *(M0)*
9. **Control prototypes, both lineages** — throwaway devnets per §5 (M + emission patch; Z stock incl. custom-network and wallet round-trip); touched-file inventories; effort calibration report captioned "feasibility only, not security." *(M0, Stage 2)*
10. **Security acceptance operationalization** — turn §2.2 into repo machinery: PR checklist for consensus paths, test-vector and fuzzing harness templates, advisory-subscription runbook. *(M0→M1)*
    *Tooling note (2026-09-05, clerical):* two org-backed Claude Code skill packs are registered at project scope in `.claude/settings.json` for use when Stage 2 unlocks — **Trail of Bits `skills`** (github.com/trailofbits/skills, CC BY-SA 4.0; pinned at review to `d3323ce`; plugins: differential-review, audit-context-building, spec-to-code-compliance, rust-review, constant-time-analysis, zeroize-audit, supply-chain-risk-auditor, property-based-testing, writing-lean-proofs) and **`leanprover/skills`** (github.com/leanprover/skills, Apache-2.0; pinned at review to `7d3da02`; plugin `lean`). Four SKILL.md files were read before install (differential-review, constant-time-analysis, rust-review, lean-proof): no network calls, no writes outside the working repo. Marketplace source is a git URL, so updates are pulled on `claude plugin update`; re-read diffs before updating, per §9.4. No anonymous marketplace skills; Circom/Noir skills rejected as the wrong proof systems.

*(Reproducible-build pipeline, threat-model v1, and the launch-fairness procedure doc are M1 issues, opened once ADR-001 is signed. Brand-track issues — voice guide, site, whitepaper v2 — live under a separate `brand` label so they never block the consensus board.)*

## 13. Questions TJ and the whitepaper author must decide

1. ~~Ratify the security doctrine (§2) as written~~ — **answered 2026-09-05:** ratified *as amended* — calendar bar replaced by the non-waivable §2.2 readiness rubric with no timeline minimum; §2.3 gadget-layer controls adopted.
2. **Confirm the hard-requirement list (§1.1)** — in particular that mandatory privacy is a hard *product* requirement with an evidence-led mechanism, and that every §1.2 desideratum is individually droppable.
3. ~~Are any desiderata launch-blocking?~~ — **answered 2026-09-05: none.** Mainnet quality is the only launch priority; Bitcoin interop defers to reviewed production precedent (§1, §5 E4).
4. ~~Maturity bar for new upstream cryptography~~ — **answered 2026-09-05:** no calendar floor; mainnet-first eligibility via the §2.2 rubric; Ironwood not approved before Pirate's 2026-10-03 activation is observed and the exact gadget/encoding/integration review completes; FCMP++ monitored, not awaited (§7).
5. **Deep-reorg protection:** if E6 survives, accept young-chain 51% risk naked, or adopt a bounded finality/checkpoint mechanism at launch with a sunset date? (§6.4 — a values call as much as an engineering one.)
6. **Ticker collision:** "MEOW" is used by existing tokens (including the Solana squatter). Keep MEOW and fight for the name, or pick a cleaner ticker?
7. **Public identities:** are you both willing to be publicly identifiable founders of a mandatory-privacy coin? (Feeds §9.2 items 1, 6, 7.)
8. **Money:** who funds the external audit (5–6 figures), the counsel engagement, and the E4 cryptographer consult — group donation fund, out of pocket, or launch-delayed-until-funded?
9. **Upstream-relationship posture** (lineage-dependent): open collaboration with Monero maintainers and/or ECC / Zcash Foundation / Shielded Labs (grant ask, upstreaming patches, shared advisories), or quiet derivative? Recommendation: open — E1's license question likely requires the conversation anyway, and goodwill is cheap insurance.
10. **the whitepaper author's role:** whitepaper author → is he the second maintainer with release-signing keys? The two-person release rule (§9.4) needs its second person named.
11. ~~Monetary policy and early-inflation claims~~ — **answered 2026-09-07:** small fixed perpetual subsidy, fair launch / zero premine; initially ultra-low percentage inflation and deflation claims dropped. Precision and display implementation remain to finalize (§8.1).
12. **Block time:** benchmark 90 s / 0.675 MEOW against working 120 s / 0.9 MEOW at matched candidate annual issuance. Selection remains evidence-gated (§8.1); no new vote on whether to test 90 s is needed.

---

## 14. References

**Zcash stack / Candidate Z**
- Zebra (Rust consensus node): https://github.com/ZcashFoundation/zebra
- zcashd deprecation: https://z.cash/support/zcashd-deprecation/ and EOL details: https://zcash.github.io/zcash/user/end-of-life.html
- Orchard protocol implementation: https://github.com/zcash/orchard · halo2: https://github.com/zcash/halo2
- ZIP-213, shielded coinbase: https://zips.z.cash/zip-0213
- ZIP-317, proportional fee mechanism: https://zips.z.cash/zip-0317
- Network Upgrade 7: https://z.cash/upgrade/nu7/
- Z3 / zcashd-deprecation ecosystem thread (Zcash forum): https://forum.zcashcommunity.com/t/zcash-z3-updates-formerly-zcashd-deprecation/48965
- Zcash counterfeiting vulnerability postmortem (CVE-2019-7167): https://electriccoin.co/blog/zcash-counterfeiting-vulnerability-successfully-remediated/
- ZIP 257 (NU6.2 emergency fix, 2026-06-03) and ZIP 258 (NU6.3 Ironwood, 2026-07-28): https://zips.z.cash/zip-0257 · https://zips.z.cash/zip-0258
- Orchard/halo2_gadgets soundness advisory, CVE-2026-54496 (missing copy constraint, variable-base scalar mul): https://advisories.gitlab.com/cargo/halo2_gadgets/CVE-2026-54496/
- Project Tachyon Ironwood verification (2026-07-28) and scope statement (grant post 2026-08-14): https://tachyon.z.cash/blog/ironwood-verification-complete/ · https://forum.zcashcommunity.com/t/retroactive-grant-application-ironwood-zk-snark-formal-verification-project-tachyon/57007 · Ironwood Book: https://zcash.github.io/ironwood/
- Pirate Chain `ac_private` enforcing code (pinned E2 §2a): https://github.com/PirateNetwork/pirate

**Monero / Candidate M**
- Full-Chain Membership Proofs development announcement — getmonero.org: https://www.getmonero.org/2024/04/27/fcmps.html
- Monero project (source, releases): https://github.com/monero-project/monero
- RandomX specification and code: https://github.com/tevador/RandomX
- Monero tail emission (Moneropedia): https://www.getmonero.org/resources/moneropedia/tail-emission.html
- FCMP++ Trail of Bits cryptography audit summary (2026-08-17): https://magicgrants.org/2026/08/17/Monero-FCMP-Cryptography-Implementation-ToB

**Merge-mining precedents (E6)**
- Tari RFC-0132, "Merge Mining Monero": https://rfc.tari.com/RFC-0132_Merge_Mining_Monero
- Tari RFC-0131, Mining (hybrid split): https://delta1.github.io/tari/RFC-0131_Mining.html
- Tari mainnet launch coverage: https://www.theblock.co/post/353240/tari-privacy-network-merged-monero-mining-launch-mainnet
- Tari merge-mining proxy: https://lib.rs/crates/minotari_merge_mining_proxy
- Merged-mining specification (Namecoin/Bitcoin AuxPoW): https://en.bitcoin.it/wiki/Merged_mining_specification
- Dogecoin (merge-mined with Litecoin since 2014; fixed 10k/block emission since 2015): https://github.com/dogecoin/dogecoin

**Atomic-swap precedents (E4)**
- COMIT `xmr-btc-swap` (production BTC↔XMR atomic swaps, scriptless on the XMR side): https://github.com/comit-network/xmr-btc-swap
- Farcaster BTC↔XMR atomic swap project (dormant since 2023–24): https://github.com/farcaster-project
- eigenwallet/core (COMIT successor, maintained): https://github.com/eigenwallet/core
- Zwap early-access thread (abandoned 2026): https://forum.zcashcommunity.com/t/zwap-trustless-shielded-atomic-swaps-for-zcash-early-access/55874

**Pirate Chain (cautionary, and E2 precedent)**
- Pirate Chain FAQ (self-reported ~90%-mined emission): https://piratechain.com/faq/
- Pirate Chain mining docs: https://piratechain.com/mining/

**Monetary design (E3)**
- Peter Todd, "Surprisingly, Tail Emission Is Not Inflationary": https://petertodd.org/2022/surprisingly-tail-emission-is-not-inflationary

**Historical / internal**
- Canonical whitepaper v1.1: `assets/Meownero updated.pdf` (SHA-256 in `research/artifact-inventory.md`)
- Chat record: `research/chat-transcript.md` · Whitepaper corrections: `research/whitepaper-notes.md`

*Note on source quality: the Phase 0 dossiers (`research/dossiers/`) have since pinned FCMP++ status, the `orchard` license, ZIP-213 shielded-coinbase behavior, and the Pirate incident history to primary sources; Zebra custom-network coverage and Tari's incident history remain Stage 2 / open verification tasks. Claims still tagged as open in the dossiers are not facts.*

---

*Meownero: nine lives, zero premine, and no security shortcuts. Much Meow.* 🐈
