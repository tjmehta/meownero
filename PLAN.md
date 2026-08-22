# Meownero Engineering Plan

**Status:** Rev 2 — draft for review by TJ and the whitepaper author · **Date:** 2026-08-22 · **Scope:** Planning only — no consensus code, no vendored upstream, no remote repository yet.

**Direction update (2026-08-22).** Per the whitepaper author's steer, adopted collaboratively: the **preferred product direction is a modern Zcash/Zebra-derived chain with mandatory privacy, the fair linear emission, meaningful Bitcoin interoperability, and ASIC-resistant mining**. Phase 0's job is to *make this direction feasible* — each known gap is a workstream with a solvable decision and pass/fail exit criteria (§4). A Monero-derived path is retained as the fallback and engineering control, not as a competing bet.

This plan turns the January 2026 whitepaper and the chat history into a credible first engineering phase. It is deliberately blunt where the source material is wrong, and deliberately conservative where cryptography or consensus questions are unresolved. Much Meow, but measured meow.

---

## 1. Product thesis and non-negotiables

**Thesis.** Meownero (MEOW) is a full, independent, proof-of-work cryptocurrency where privacy is mandatory for every transaction — Zcash-grade zero-knowledge cryptography, Dogecoin-fair linear emission, honest launch with no insider advantage, real interoperability with Bitcoin, and a meme-worthy cat brand that makes strong privacy approachable.

**Non-negotiables** (distilled from the chat record in `research/chat-transcript.md`):

1. **Independent coin, not a token.** Its own chain, own consensus, own P2P network. No Solana/EVM contract.
2. **Mandatory privacy.** No transparent transaction type, ever. Privacy that is optional is privacy that is absent.
3. **Fair, honest launch.** Public advance notice ("give everyone a couple weeks, then everyone mines"), reproducible binaries published before genesis, no insta-mine games.
4. **No premine, founder reward, or developer tax.** Zero protocol-level allocation to insiders. Dev funding is out-of-band and disclosed (§7.4).
5. **Meme-worthy brand, "Much Meow" voice.** Fun is a feature, but it lives in the branding track (§10), never in consensus code.
6. **No cosmetic rename.** Meownero must make consensus-meaningful, defensible design changes — not a find-and-replace of any upstream's name (the whitepaper author, 2026-08-22). This bar applies to the Zcash-derived direction too: mandatory privacy, the PoW change, linear emission, and the launch process are the meaningful deltas.

**Product goals from the current steer** (goals, not non-negotiables — each has a workstream that defines exactly what is achievable):

- **Bitcoin interoperability** — precisely defined and tiered in WS3 (§4). We promise mechanisms we can name, not "bridges."
- **ASIC-resistant mining** — honestly framed in WS4 (§4): ASIC-*unfriendliness today* plus a maintenance posture, because permanent ASIC resistance is not a property anyone can promise.

Anything that conflicts with the non-negotiables is out, regardless of how fun it sounds.

---

## 2. Blunt audit of the January whitepaper

`assets/Meownero updated.pdf` (v1.1, "Merge-Mined Edition") is product vision and comedy, not a specification. Treat it as historical context. Specific defects that must not leak into engineering:

| # | Whitepaper claim | Reality |
|---|---|---|
| 1 | Monero miners solve "CryptoNight" puzzles | Monero abandoned CryptoNight for **RandomX** in November 2019. Every mining-related number and mechanism in the paper is built on a PoW that no longer exists. |
| 2 | "Kovri integration — the gold standard" | Kovri is **dead** (abandoned ~2019). Monero's actual network-layer stack is Dandelion++ (since 2020) plus optional Tor/I2P transaction relay. |
| 3 | "Meownero mandates a fixed ring size" / ring-signature framing | Monero's FCMP++ work **replaces ring signatures entirely** with full-chain membership proofs (anonymity set = the whole output set, ~10^8, instead of 16). Freezing 2022-era ring language into a new chain would ship obsolete privacy on day one. |
| 4 | "Attackers would need to defeat both networks simultaneously"; "instant, massive security from genesis" | **False.** A merge-mined chain inherits only the hashrate of miners who opt in, and attacking the aux chain costs a Monero miner nothing on Monero. A single large pool could reorg young Meownero at near-zero marginal cost (see §5.3). |
| 5 | "Monero nodes validate AuxPoW submissions, providing distributed verification" | **False.** Monero neither knows nor cares about aux chains. All AuxPoW validation happens on the aux chain's own nodes. Monero's only role is that its coinbase `tx_extra` can carry a commitment. |
| 6 | "~2 GH/s as of 2026" hashrate figure | Unverified; treat every quantitative claim in the paper as unchecked. |
| 7 | "1 MEOW/block reward is distributed to the Monero miner's AuxPoW coinbase address" | Sloppy. The aux reward goes to a Meownero address the miner configures in the merge-mining proxy; there is no such thing as paying a Meownero reward to a Monero coinbase. |
| 8 | References list | Thin and partly wrong — it cites the "Dogechain Whitepaper" (an unrelated EVM sidechain project), not Dogecoin. None of the load-bearing claims are sourced. |
| 9 | "ASIC resistance (complementary)" section | Hand-waves the actual constraint: to merge-mine with Monero, the PoW must **be RandomX** (same VM, same key schedule), not merely "ASIC resistant." |

**What the whitepaper gets right and we keep:** mandatory privacy; no premine/dev tax; two-minute blocks; the linear 1 MEOW/block emission as a deliberate, defensible monetary design (§7); community governance posture; and the jokes.

---

## 3. Directions

### 3.1 Direction Z (preferred) — modern Zcash/Zebra-derived, privacy mandatory

Build on **Zebra**, the actively maintained Rust consensus node (`zcashd` hit end-of-life July 2026), with the **Orchard** shielded protocol (Halo 2, no trusted setup), the transparent pool removed at consensus level, linear 1 MEOW emission, and an ASIC-resistant PoW.

**Why this is the direction we want to make work:**

- **Strongest answer to "genuinely different."** A mandatory-shielded, linear-emission, ASIC-resistant, Bitcoin-interoperable zk chain is not a rename of anything — it is a design point no production chain currently occupies.
- **Best-in-class privacy cryptography.** Orchard's anonymity set is the whole shielded pool; Halo 2 removes trusted setup; the implementation is compact, audited Rust. The in-development Tachyon protocol gives the lineage a scalability future.
- **Modern, memory-safe codebase.** Zebra is well-factored Rust with an active maintainer organization — a better long-term foundation for a small team than a large legacy C++ tree.
- **Mandatory-shielded has production precedent.** Pirate Chain has run z-address-only on the older Sapling protocol since 2018 (§3.3): the *product shape* is proven, even though we reject Pirate's economics and security borrowing.

**Known gaps — each one is a Phase 0 workstream (§4), not a rejection:**

| Gap | Workstream |
|---|---|
| `orchard` crate's BOSL licensing history | WS1 |
| Zcash ships privacy as optional; transparent-pool removal is consensus surgery | WS2 |
| "Bitcoin interoperability" needs an exact, honest definition and mechanism | WS3 |
| Equihash (Zcash's PoW) has mature ASICs — fails the ASIC-resistance goal as-is | WS4 |
| Merge-mining with Monero becomes possible only if WS4 lands on RandomX, and has no precedent on a Zcash-derived chain | WS5 |
| Upstream churn: zcashd EOL, June 2026 Orchard vulnerability, NU6.3/NU7 cadence, Tachyon in flight | WS6 |
| Zebra ships no wallet, and a custom network + wallet + explorer path must exist end-to-end | WS7 |

### 3.2 Direction M (fallback / control) — modern Monero-derived fork (FCMP++-era)

Fork `monero-project/monero` after the FCMP++ hard fork stabilizes; change emission to linear, add merge-mining validation, rebrand, re-genesis.

- **Privacy:** mandatory by construction (FCMP++ membership proofs + RingCT amounts + stealth addresses) with zero new cryptography.
- **Merge-mining:** native fit — same RandomX PoW as the parent; Tari proves the model in production with no Monero consensus changes (§5).
- **Costs:** large legacy C++ tree mid-transition through Monero's biggest-ever upgrade; and it is the path most exposed to the "cosmetic rename" criticism — the very objection driving the current steer.
- **Role in this plan:** *fallback and control.* A thin, timeboxed control spike (WS-M, §4) keeps this path warm and calibrates effort estimates, so that if Direction Z fails a hard gate we can pivot within weeks instead of months — and so Direction Z's spikes are honest about what the simpler path would have cost.

### 3.3 Pirate Chain — the cautionary comparison (not a candidate)

Pirate Chain (ARRR, 2018) is the existence proof that **mandatory shielded transactions work in production** — z-address-only on Sapling, as a Komodo asset chain with delayed proof of work. That precedent directly de-risks WS2. It is equally the existence proof of what to avoid:

- **Front-loaded emission.** By Pirate's own FAQ, ~90% of the 200M supply is already mined; the schedule began at 256 ARRR/block and collapsed rapidly. Whatever the stated rationale, the outcome is that early miners hold the supply — exactly the "aggressive early emission resembles a premine" failure the whitepaper author flagged on 2026-01-15. Meownero's linear emission is the direct antidote.
- **Borrowed security with strings.** dPoW notarization to Komodo/Bitcoin trades 51% resistance for dependence on a notary set — a centralization trade we should only accept knowingly, if ever (§5.4).
- **Ecosystem fragility.** Dependence on another project's stack, thin dev funding, and privacy-coin exchange attrition. Plan for all three.

### 3.4 Clean-room / new chain — rejected

Writing new consensus and new privacy cryptography from scratch is a multi-year, multi-cryptographer effort; the failure mode is an unaudited zk implementation guarding real money. Every non-negotiable is achievable by deriving from an audited upstream. Rejected unless both Z and M fail their Phase 0 gates for reasons a new chain would actually fix (they won't).

### 3.5 Summary

| Criterion | Z: Zcash/Zebra-derived (preferred) | M: Monero fork (fallback) |
|---|---|---|
| Mandatory privacy | Surgery with precedent (WS2; Pirate proves the shape) | Free (inherent) |
| Privacy tech | Orchard/Halo 2 (proven), Tachyon (future) | FCMP++ (in rollout) |
| ASIC-resistant PoW | Requires PoW change (WS4) | RandomX inherent |
| Bitcoin interop | Defined + scoped in WS3 | Same mechanisms apply, unscoped |
| Merge-mine w/ Monero | Possible iff RandomX (WS5), no precedent | Native, Tari-proven |
| Codebase | Modern Rust, churning ecosystem (WS6) | Mature C++, mid-transition |
| License risk | **Unresolved: orchard/BOSL (WS1)** | Low (BSD-style) |
| "Not a cosmetic rename" | Strongest | Weakest, must be earned |
| Wallet/testnet tooling | Must be assembled (WS7) | Inherited |

---

## 4. Phase 0 — the feasibility program

Phase 0's mandate: **make Direction Z feasible, or prove concretely that it isn't.** Every known gap becomes a workstream with a solvable decision, an owner, and pass/fail exit criteria. Nothing here re-litigates the product direction — that is decided; what Phase 0 decides is *how*, and whether any hard gate forces the fallback.

**Rules:**

- **Timebox:** 8 weeks from kickoff, mid-point checkpoint at week 4. Hard stop.
- **Deliverable:** `ADR-001` recording the outcome of every workstream, signed off by TJ and the whitepaper author.
- **Spikes are throwaway.** Phase 0 code lives under `spikes/` and is never promoted; this prevents sunk-cost capture.
- **No unresolved-crypto hand-waving.** Anything a spike cannot answer is recorded in the ADR as an open risk with an owner — not assumed away.
- **Hard gates vs. scope gates.** WS1, WS2, WS4, WS7 are *hard gates*: a fail triggers the fallback assessment. WS3 and WS5 are *scope gates*: a fail narrows launch scope but cannot kill Direction Z. WS6 informs the baseline.

### WS1 — Orchard licensing (hard gate)

- **Gap:** Zebra and `librustzcash` are MIT/Apache-2.0, but the `orchard` crate historically shipped under the **Bootstrap Open Source Licence (BOSL)**, which restricts use outside Zcash without a grant.
- **Solvable decision:** *Under what terms can Meownero use the Orchard/Halo 2 stack?*
- **Work:** pin the current license of every crate we would vendor (`orchard`, `halo2_proofs`, `librustzcash`, Zebra); obtain a written counsel read on BOSL obligations; if a grant or exception is needed, open the conversation with Electric Coin Co. directly — a friendly ask, made early, in the open.
- **Pass:** written verdict that the stack is usable — via MIT/Apache relicensing, an obtained grant, or BOSL terms we can genuinely live with (including its copyleft-style obligations, which may be *compatible* with our everything-open posture).
- **Fail:** license unobtainable or incompatible → fallback assessment.

### WS2 — Mandatory-private consensus scope (hard gate)

- **Gap:** Zcash ships privacy as optional; non-negotiable #2 requires no transparent transactions, ever.
- **Solvable decision:** *Exactly which consensus rule enforces shielded-only, and how big is the patch?*
- **Work:** enumerate every consensus, mempool, RPC, and serialization surface in Zebra that touches the transparent pool. Candidate mechanism (minimal delta): keep the v5 transaction format but add a consensus rule that **transparent input/output bundles must be empty** for all non-coinbase transactions, with coinbase paid **directly to shielded outputs** (ZIP-213 already allows shielded coinbase — verify Orchard coverage). Prototype the rule on a custom regtest network. Decide excise-vs-disable for dead transparent code paths.
- **Pass:** regtest devnet rejects transparent transactions and processes shielded-only flows end-to-end, including shielded coinbase; the enumerated patch surface is bounded and reviewable (a patch series, not a rewrite).
- **Fail:** the transparent pool is load-bearing in ways that make removal unbounded → fallback assessment.

### WS3 — Bitcoin interoperability: exact meaning and mechanism (scope gate)

- **Gap:** "more Bitcoin interoperability" is a direction, not a spec — and mandatory shielding *removes* the Bitcoin-style script rails Zcash's transparent pool would have offered. Honesty first: there is a real tension here, and the resolution is to put the script logic on Bitcoin's side.
- **Solvable decision:** *Which interop tier is real, and is it launch-blocking?*
- **Tiers (from honest to fantasy):**
  - **Tier 1 — trustless BTC↔MEOW atomic swaps.** All timelock/hash-lock or PTLC logic lives in Bitcoin script; the Meownero side needs only its ordinary signature scheme with an adaptor-signature construction. This is exactly how production BTC↔XMR swaps work (COMIT `xmr-btc-swap`, Farcaster) despite Monero having *no* scripts. Orchard's spend authorization is RedPallas — a Schnorr-family scheme, so adaptor techniques are plausible **in principle**, but adaptor signatures over RedPallas interacting with the Orchard circuit is unverified cryptography for us. Requires a short external cryptographer review before we claim it.
  - **Tier 2 — swap infrastructure UX:** swap daemons, maker/taker marketplace, submarine-swap-style Lightning endpoints. Research-grade; explicitly not promised for launch.
  - **Rejected outright:** custodial bridges, federated pegs, wrapped MEOW/BTC. Their trust assumptions contradict the thesis, and "bridge" is where other projects keep their rug.
- **Work:** write the interop spec: chosen tier, mechanism sketch, and a feasibility memo on adaptor signatures over RedPallas reviewed by an external cryptographer; identify what (if anything) must land in consensus v1 to keep Tier 1 possible later (e.g., not breaking the signature scheme's adaptor-friendliness).
- **Pass:** a reviewed memo concluding Tier 1 is achievable (now or post-launch) with a named mechanism, and a decision on whether it is launch-blocking.
- **Fail:** Tier 1 unproven in the timebox → interop ships as a post-launch research track with its consensus prerequisites preserved; **cannot trigger fallback** (Direction M has the same interop questions).

### WS4 — PoW choice and ASIC-resistance tradeoffs (hard gate)

- **Gap:** Zcash's Equihash has mature ASICs — keeping it fails the steer's intent on day one. And *permanent* ASIC resistance is not a promise anyone can keep; it is a treadmill.
- **Solvable decision:** *Which PoW, and what ASIC posture do we commit to in writing?*
- **Candidates:**
  - **RandomX (recommended default):** best-in-class CPU-friendly PoW, proven at scale for 6+ years, mature miner ecosystem (XMRig), BSD-3-Clause — and it is the *only* choice that keeps merge-mining with Monero on the table (WS5).
  - **Keep Equihash:** zero integration work, but ASIC-dominated — fails the goal; rejected unless RandomX integration proves intractable.
  - **Custom/tweaked algorithm:** the treadmill at its worst; rejected.
- **Honest posture to publish:** "ASIC-unfriendly today, with a standing commitment to evaluate the ASIC landscape at every scheduled upgrade" — not "ASIC-proof forever."
- **Work:** PoC RandomX block-hash validation inside Zebra's PoW verification path on regtest; select the difficulty algorithm (LWMA-class) and the RandomX key-schedule policy (self-referential key blocks by default; Monero-chain key blocks only if WS5 chooses merge-mining — note that aux-chain validation of Monero-seeded RandomX requires tracking valid Monero seeds, as Tari does; that complexity belongs to WS5, not the base chain).
- **Pass:** regtest devnet mines and validates RandomX blocks with acceptable verification performance; difficulty algorithm chosen; ASIC-posture statement drafted.
- **Fail:** RandomX cannot be integrated tractably → Equihash-launch vs. fallback decision goes to TJ/the whitepaper author with the control-spike data.

### WS5 — Merge-mining decision (scope gate; conditional on WS4 → RandomX)

- **Gap:** merge-mining was the whitepaper's headline, but its security story was wrong (§2 #4–5), and no Zcash-derived chain has ever merge-mined with Monero.
- **Solvable decision:** *Launch merge-mined with Monero, solo-mined RandomX, or hybrid?*
- **Work:** the full audit in §5 applies. PoC the proxy path (XMRig → proxy → Monero stagenet + Meownero regtest) including the coinbase-merkle proof validation and multi-aux coexistence with Tari's use of the `tx_extra` field; write the honest security-model doc (opt-in hashrate only, zero parent-chain attack cost).
- **Pass:** an explicit, signed decision among {merge-mined, solo, hybrid} with the security model published; if merge-mined, the PoC validates end-to-end.
- **Fail:** launch solo-mined RandomX (a fine outcome — Monero itself launched solo); merge-mining remains a documented future upgrade. Cannot trigger fallback.

### WS6 — Upstream churn and security posture (informs baseline)

- **Gap:** the Zcash ecosystem is in motion — zcashd's forced EOL (July 2026), the June 2026 Orchard vulnerability, NU6.3 just activated, NU7 upcoming, Tachyon in development. Churn is risk, but it is also evidence of an alive upstream; we plan for it rather than fear it.
- **Solvable decision:** *Which Zebra tag / network-upgrade baseline do we derive from, and how do we track upstream?*
- **Work:** pin the fork baseline (an NU6.3-era stable Zebra release unless the spike finds a reason otherwise); write the upstream-tracking policy (security patches merged within 72h; NU-level changes by explicit ADR); subscribe to Zcash security advisories; open a courteous channel to the Zcash Foundation / ECC / Shielded Labs (this also serves WS1's grant conversation); pin FCMP++'s shipped status from primary sources for the fallback path's sake.
- **Pass:** baseline tag pinned with rationale; tracking policy written; advisory channels live; FCMP++ status documented from primary sources.

### WS7 — Credible testnet path: node, wallet, network tooling (hard gate)

- **Gap:** Zebra is a consensus node only — it ships **no wallet**. A chain nobody can hold is a paperweight with good cryptography. The full path (custom network params → mining → wallet → explorer) must exist.
- **Solvable decision:** *What is the end-to-end devnet stack, and does it work?*
- **Work:** stand up a custom network using Zebra's configurable-testnet support (verify it covers custom genesis, NU activation heights, and our PoW/difficulty params — extend if not); evaluate wallet paths (**Zallet**, the zcashd-wallet successor, and `zingolib`) for shielded-only operation on a custom network, and estimate the port; scope the explorer (§8.8) and genesis tooling.
- **Pass:** a multi-node devnet mines blocks (shielded coinbase) and a wallet sends/receives mandatory-shielded transactions end-to-end, with the wallet-port scope documented.
- **Fail:** no workable wallet/custom-network path within the timebox → fallback assessment.

### WS-M — Monero fallback control spike (1 week, strictly bounded)

Boot a private Monero-fork devnet with the linear-emission patch and rebrand constants; document every touched file. Purpose: (a) keep the fallback warm so a pivot costs weeks, not months; (b) calibrate — Direction Z's spike reports must answer "and how hard was this on the control?" honestly. No merge-mining PoC here unless WS5 needs a comparison harness.

### Phase 0 decision rule

At week 8: **Direction Z is adopted iff WS1, WS2, WS4, and WS7 all pass.** A hard-gate fail gets a one-week remediation assessment; if still failed, the fallback activates via its own short ADR (scoped by WS-M and §3.2), carrying over everything direction-agnostic (emission, launch process, threat model, brand). WS3/WS5 outcomes set launch scope either way. TJ and the whitepaper author sign ADR-001 in both worlds — the fallback is a decision, never a drift.

---

## 5. Merge-mining feasibility audit (input to WS5)

### 5.1 Verdict

**Merge-mining with modern Monero is feasible and production-proven — but the whitepaper's security story is wrong, and a Zcash-derived chain doing it would be a first.** The CryptoNight/AuxPoW framing is obsolete; the working model is the one Tari runs today on RandomX.

### 5.2 How it actually works (Tari precedent)

Tari (mainnet since May 2025, founded by early Monero contributors) merge-mines with Monero with **zero Monero consensus changes** (Tari RFC-0132):

- The aux chain's block-header hash is embedded in the **merge-mining subfield of the Monero coinbase transaction's `tx_extra`**. Because the coinbase hashes into Monero's transaction merkle root, the aux commitment is bound into Monero's RandomX PoW.
- The aux chain's nodes validate a proof package (Monero header fields, RandomX VM key, coinbase merkle proof, coinbase extra) and accept the block if the achieved RandomX difficulty meets the *aux chain's own* target.
- Miners run a merge-mining proxy between their mining software (XMRig) and both daemons; the proxy sets the job difficulty so one solve can satisfy either chain.

Consequences for Meownero:

- **The PoW must be RandomX**, byte-compatible with Monero's parameters — which is why WS4 and WS5 interlock. Validating Monero-seeded RandomX proofs means the aux chain must track valid Monero key-block seeds (as Tari's `MoneroPowData` does); this is real complexity that lands in our consensus code.
- FCMP++ does not change Monero's PoW, so the mechanism survives the FCMP++ era. (Verify against the shipped hard-fork code during WS5.)
- **The `tx_extra` merge-mining field is a shared, contended resource.** Pools already merge-mining Tari can only add Meownero via an aux-chain merkle tree in that single field. Our proxy and validation must support multi-aux from day one, or the largest merge-mining pools cannot carry us.
- **No precedent risk:** Tari proved the model for a chain designed around it. Bolting the same validation into Zebra is new engineering with no production reference — priced into WS5's scope-gate status.

### 5.3 The honest security model

- Day-one security equals **the hashrate of miners who opt in**, not "Monero's hashrate." If 2% of Monero merge-mines Meownero, our security is 2% of Monero — and any pool larger than that can 51% us.
- Attacking the aux chain is **costless on the parent chain**: a Monero pool can double-spend or censor Meownero while continuing to earn full XMR rewards. History has receipts — Eligius killed CoiledCoin (a merge-mined chain) in 2012 at effectively zero cost. The whitepaper's "must defeat both networks" claim inverts reality.
- Merge-mining also cuts the other way for fairness: it lowers the cost for honest hashrate to show up, which strengthens the fair launch — the more pools that adopt at genesis, the smaller any one pool's share.
- Solo-mined RandomX at launch (WS5's fail-mode) has the young-chain hashrate problem too — it is smaller and slower-arriving, but nobody attacks it for free from an adjacent chain. The tradeoff is genuinely two-sided; that is why WS5 is a decision, not a default.

### 5.4 Mitigations to evaluate in WS5 (none are free)

1. **Maximize pool adoption before genesis** — outreach to major Monero pools and P2Pool, a polished proxy, and a mining one-pager. The primary mitigation if merge-mining is chosen.
2. **Deep-reorg dampening** (e.g., rolling finality window or checkpoint policy) — effective, but a centralization trade that must be explicit, bounded, and ideally sunset-dated. Pirate's dPoW is the cautionary extreme.
3. **Hybrid solo+merge mining** (Tari-style algorithm split) — hedges pool capture but doubles mining-path complexity.
4. **Exchange/merchant confirmation guidance** scaled to observed hashrate, published from day one.

---

## 6. Privacy primitives recommendation

Ground rule from the brief: recommend based on **current upstream reality**, not the draft's Kovri/ring-size language.

- **Direction Z (preferred):** **Orchard only** (Halo 2, no trusted setup) — anonymity set is the entire shielded pool; transparent pool removed at consensus level (WS2); shielded coinbase per ZIP-213. Track Tachyon as a future upgrade, not a dependency. The June 2026 Orchard vulnerability is a reminder that even excellent zk code has soundness risk — subscribe to upstream advisories (WS6) and budget for re-audit of anything we alter.
- **Direction M (fallback):** FCMP++-era privacy — full-chain membership proofs, RingCT hidden amounts, stealth addresses. Do **not** fork pre-FCMP++ and freeze ring signatures; fork point = first post-FCMP++ stable release tag.
- **Network layer (honest gap in Direction Z):** Monero has Dandelion++ and Tor/I2P relay; **the Zcash lineage has no Dandelion++ equivalent in production**. Direction Z must evaluate porting Dandelion++-style origin obfuscation to Zebra's P2P layer and shipping first-class Tor support — scoped in WS2/WS7, tracked in the threat model. We do not claim network-layer privacy we haven't built.
- **Non-goals for v1:** no novel cryptography of our own, no custom curves, no bespoke proof systems. We are integrators of audited primitives, not authors of new ones. The single carve-out: WS3's adaptor-signature memo, which is exactly why it requires external cryptographer review before any claim is made.
- **Supply auditability caveat (must be disclosed honestly):** hidden-amount chains cannot be trivially supply-audited; soundness of the proofs is the backstop, and an undetected inflation bug is the worst-case failure (Zcash's CVE-2019-7167 counterfeiting vulnerability; Monero's 2017 key-image bug). Mitigations: minimize deltas to audited upstream code, run duplicate-nullifier monitors, adopt upstream turnstile/audit tooling as it lands.

---

## 7. Emission and fair launch

### 7.1 Emission schedule (keep the whitepaper's one good deliberate choice)

**1 MEOW per 2-minute block, forever.** 0.5/min, 720/day, 262,800/year, linear and infinite. This is Dogecoin's tail shape with Monero's block cadence, preserved verbatim from the whitepaper author's design, and it is defensible:

- **Perpetual security budget:** miners are always paid in subsidy; no terminal fee-only regime (Peter Todd, "Surprisingly, Tail Emission Is Not Inflationary": with lost coins, constant absolute emission converges to a stable, non-inflationary supply in practice).
- **Minimal early-holder advantage:** pure linear emission is the *least* front-loaded schedule available — year-2 inflation is 100%, diluting early accumulation fast, the opposite of Pirate's curve. The emission rate the day you join is the rate forever ("the same meow as it will be in 100 years").
- **Simplicity:** one constant. No halvings to game, no curve parameters to argue about. Rejected alternatives: Monero-style smooth decline + tail (favors early holders — the whitepaper author, 2026-01-15), capped supply (terminal security-budget problem, and the whitepaper author explicitly prefers limited-but-not-capped), "divisibility instead of emission" (it's just logarithmic tail emission with extra steps — the whitepaper author, correctly).
- **Open parameters for ADR-001:** atomic units/decimal places; fee policy and minimum relay fee (ZIP-317-style proportional fees are the Zcash-lineage default — evaluate against a mandatory-shielded mempool); block time confirmed at 120s (vs. Zcash's 75s — a deliberate deviation that must be checked against Orchard proof sizes and propagation); block-size policy (Zcash lineage: fixed limit — decide the number; Monero fallback: the dynamic-size penalty math must be re-derived for constant subsidy, not copy-pasted).

### 7.2 No premine, no dev tax — and what "no insider advantage" requires operationally

- Genesis block contains **zero spendable outputs** to any party. Genesis message: something datestamped and public (headline + cat pun), chosen at the launch livestream, not before.
- Founders/insiders mine under **exactly the same conditions** as the public: same binaries, same announcement, same start time. TJ and the whitepaper author disclose that they will be mining.
- **No secret pre-genesis testing advantage:** the final chain parameters (genesis hash excepted) are public at least 2 weeks before launch; anyone can pre-provision miners.

### 7.3 Launch process (fairness is a procedure, not a vibe)

1. **T−4 weeks:** launch date/time announced publicly; parameters frozen and published; mining guide (and merge-mining proxy, if WS5 chose it) released for testnet rehearsal.
2. **T−2 weeks:** release-candidate binaries published with SHA-256 hashes and signatures; reproducible-build instructions public so third parties can verify (§8.4). Pool outreach concludes; committed pools listed publicly.
3. **T−0:** genesis at the announced timestamp. Initial difficulty set to a sane floor (not 1) with an LWMA-class adjustment algorithm so early blocks cannot be insta-minted faster than difficulty can react; with a constant 1 MEOW reward the worst case is bounded, but a chaotic first hour is still a bad look and a reorg risk.
4. **T+2 weeks:** post-launch fairness report — blocks mined, pool distribution, any incidents — published against the pre-committed criteria.

### 7.4 Dev funding without a founder tax

Protocol allocates nothing to anyone — that is settled. Development is funded by: (a) a **disclosed, multisig community donation fund** (Monero CCS-style, proposals public), (b) direct sponsorship of specific audits or bounties, (c) volunteer work. The group's own capital ("$100K in the group") may seed the donation fund like any other donor — publicly, at market terms, with addresses disclosed. Buying MEOW from members via "wire instructions" (the 02-06 chat bit) is exactly the kind of informal insider dealing that must **not** happen once this is real; all acquisition is mining or open-market.

### 7.5 Mining-pool incentives

Pools carry us or nobody does — in every PoW configuration. Concretely: pool-operator documentation and a pool reference deployment; a testnet dry-run with at least two independent pools before mainnet; zero pool fees taken by the project (pools set their own); and, if WS5 chooses merge-mining, a multi-aux-capable proxy that coexists with Tari. RandomX (WS4) also keeps solo CPU mining genuinely viable — the "everyone in the group mines it" story from the chat is real on RandomX in a way it never was on Equihash.

---

## 8. Security, legal, and operational program

### 8.1 Threat model (v0 — to be formalized as a living doc)

| Threat | Vector | Posture |
|---|---|---|
| 51% / deep reorg | Young-chain hashrate; if merge-mined, a large Monero pool attacks at zero parent-chain cost | §5.3–5.4; WS5 decision; confirmation guidance; chain monitoring |
| Inflation bug | Soundness flaw in Orchard/membership proofs or our patches | Minimize consensus deltas; upstream advisory tracking (WS6); duplicate-nullifier monitors; external audit before mainnet |
| Tx-graph/timing analysis | Statistical deanonymization, poisoned outputs | Whole-pool anonymity sets (Orchard / FCMP++); wallet-side guidance |
| Network-layer deanonymization | IP linkage, eclipse/sybil attacks on P2P | Tor relay support; Dandelion++-equivalent evaluation for Zebra (§6); diverse seed nodes; anchor connections |
| Interop-layer attacks | Swap counterparty griefing, adaptor-signature implementation flaws | WS3 external review; swaps ship only with audited protocol implementations |
| Supply-chain compromise | Malicious dependency, compromised CI, backdoored release | §8.4; two-person release rule; dependency pinning + review (cargo lockfiles + `cargo vet`-style review for Direction Z) |
| Key compromise | Release-signing or seed-node keys stolen | §8.5 |
| Social/insider | "Leak" paranoia (see 02-10 chat), squatter projects, fake binaries | Everything public by default; official-channel discipline; the Solana "Meownero" is a brand problem, not a chain problem |
| Regulatory shock | Exchange delistings of privacy coins, jurisdictional bans | §8.2; design assumes no exchange support at launch |
| Upstream shock | Orchard-class vulnerability disclosed upstream post-fork | WS6 72h security-merge SLA; §8.9 rehearsed playbook |

### 8.2 Questions for legal counsel (obtain real counsel; none of this is settled by us)

1. Exposure of identifiable founders launching a **mandatory-privacy** coin: money-transmission, sanctions (OFAC precedent from the Tornado Cash saga), and jurisdiction-specific privacy-coin bans (e.g., Japan, South Korea; EU AMLR trajectory for 2027).
2. Does a zero-premine, no-sale, mined-only launch keep MEOW clearly outside securities frameworks (Howey / MiCA utility analysis)? What launch communications would jeopardize that?
3. **BOSL obligations and grant path for the `orchard` crate (WS1)** — the one license question that can move the architecture.
4. Legal posture of facilitating BTC↔MEOW atomic swaps or hosting swap infrastructure (WS3) — protocol vs. operator liability.
5. Liability for marketing claims: the coin art literally says "no trace currency" and "zero logs" — what claims can we responsibly make?
6. Trademark: register "Meownero"? Posture toward the pre-existing Solana "Meownero" token; risk that *we* are accused of association with it.
7. Domain/entity structure: should meownero.com and the donation multisig sit in a foundation or association rather than with TJ personally?
8. Contributor exposure: does merging code or running seed nodes create liability for individual group members?

### 8.3 Upstream licenses and attribution

- **Zcash stack (Direction Z):** Zebra and librustzcash are MIT/Apache-2.0; the **`orchard` crate's BOSL history is the open question and a Phase 0 hard gate (WS1)**. `halo2` crates to be pinned in the same audit.
- **RandomX:** BSD-3-Clause. **Monero (Direction M):** BSD-3-Clause-style — fork-friendly; preserve notices; attribute prominently.
- **Tari:** if we adapt their merge-mining proxy or validation code in WS5, verify license (BSD-3-Clause family) and attribute.
- Deliverable: `LICENSES.md` + per-file header audit before any code is vendored (Issue #2).

### 8.4 Supply-chain security and reproducible builds

- Deterministic builds from day one: for Direction Z, pinned Rust toolchain, committed lockfiles, vendored dependencies, and a reproducibility harness; for the fallback, inherit Monero's Guix pipeline.
- All release binaries built by ≥2 independent parties whose hashes must match before publication; hashes + minisign/GPG signatures published on the site and in-repo.
- Dependency policy: pinned versions, lockfiles committed, no dependency added without review; CI runs from committed config only; branch protection + signed commits for consensus-critical paths.

### 8.5 Key management

- **Release-signing keys:** hardware-backed, held by ≥2 maintainers (TJ + the whitepaper author to start), with a published key-transparency page and revocation procedure.
- **Donation fund:** m-of-n multisig, holders disclosed, no single spender.
- **Seed-node infrastructure:** separate credentials per node, no shared root, documented rotation.
- **No "network keys" exist** in this architecture — Halo 2 needs no trusted setup, there is nothing like a mint key, and we must be able to say so truthfully.

### 8.6 Testnet → mainnet gates

Each promotion requires **all** exit criteria of the prior stage (§9) plus: no open consensus-severity bugs; external audit findings triaged with criticals fixed; two independent pools mining on testnet; reproducible-build verification by a third party; incident-response runbook rehearsed once.

### 8.7 Wallets, node, and miner tooling (v1 scope)

- **v1:** `zebrad`-derived daemon + a shielded-only CLI wallet (Zallet- or zingolib-derived — the WS7 port), mining guide, and the merge-mining proxy if WS5 chose it. That's the launch surface. **Zebra ships no wallet; the wallet port is launch-critical path and is treated as such from week 1.**
- **v1.x:** GUI wallet (evaluate rebranding Zashi or an upstream GUI where licensing allows), light-wallet support (lightwalletd-style) with the honest privacy caveats about trusting a light server.
- **Later, explicitly not launch-blocking:** mobile wallets, hardware-wallet integration (requires vendor cooperation; long lead), merchant tooling, Tier 2 swap infrastructure.

### 8.8 Block explorer for a private chain

An explorer can show: block heights/hashes/timestamps, tx hashes and sizes, fee totals (public in both lineages — Zcash-style value balance exposes fees, Monero fees are cleartext), emission tally, and hashrate/difficulty — and **cannot** show amounts, senders, or recipients. Build or adapt a minimal explorer; document loudly that "the explorer looks empty of amounts" is the product working. Supply tally page (`emission = height × 1 MEOW` + genesis) doubles as a public no-premine proof.

### 8.9 Incident response

- Published security policy + PGP/security@ contact before mainnet; 90-day coordinated disclosure default.
- Consensus-bug playbook drafted and rehearsed pre-launch: severity ladder, who can call for an emergency patch or rollback, pool/exchange contact tree, and a pre-agreed public-comms template. The June 2026 Orchard vulnerability and zcashd's emergency EOL are the case study: our chosen upstream *does* have fire drills, and we inherit them — WS6's advisory channel and 72h merge SLA are the standing response.
- Upstream watch: Zcash security advisories (primary), Monero advisories (fallback path + merge-mining dependency), RandomX repo.

---

## 9. Milestones and exit criteria

**M0 — Phase 0 feasibility program, weeks 1–8** (§4).
Workstreams WS1–WS7 + WS-M control spike; mid-point checkpoint week 4.
*Exit criteria:* every workstream reports pass/fail against its §4 criteria; ADR-001 signed by TJ and the whitepaper author adopting Direction Z (or, on hard-gate failure + failed remediation, the fallback ADR). **No fork is blessed until this gate passes.**

**M1 — Foundation, weeks 9–14.**
Real repo layout from the chosen upstream at the pinned tag; consensus deltas as a reviewable patch series (shielded-only rule, RandomX, linear emission, network params); threat model v1; CI + reproducible-build pipeline green; wallet-port work started (launch-critical path).
*Exit criteria:* clean build from source by an outsider following docs; every consensus delta has an ADR; `git diff` vs upstream tag is enumerable and justified.

**M2 — Private devnet, weeks 15–22.**
Multi-node devnet: RandomX mining, shielded coinbase, mandatory-shielded transactions via the CLI wallet; merge-mining live against Monero stagenet if WS5 chose it; explorer alpha; difficulty algorithm validated under hashrate-whiplash simulation.
*Exit criteria:* 2-week devnet uptime without consensus fault; reorg/partition chaos tests pass; fairness-relevant parameters (difficulty floor, LWMA window) frozen; WS3 consensus prerequisites (if any) landed.

**M3 — Public testnet + audit, weeks 23–34.**
Public testnet with ≥2 independent pools; external security review of consensus deltas (shielded-only rule, PoW integration, and merge-mining validation if present); bug bounty opens; launch-procedure dry run including a rehearsed incident.
*Exit criteria:* audit criticals fixed; third-party reproducible-build verification; testnet survives an adversarial event (invited attack week); §8.6 gates met.

**M4 — Mainnet launch.**
Execute §7.3 exactly as published.
*Exit criteria:* genesis at announced time; ≥2 independent pools mining in the first 24h; post-launch fairness report published at T+2 weeks.

**M5 — Post-launch hardening.** GUI wallet, light-wallet infrastructure, seed-node diversity, upstream-merge cadence, Tier 1 swap implementation (per WS3's verdict), governance formalization. (Deliberately unscheduled until M4 lands.)

---

## 10. Two tracks: consensus engineering vs. Much Meow

These run in parallel and must never share a critical path:

- **Consensus track (this document, §§3–9):** slow, reviewed, audited, boring on purpose. No memes in commit messages on consensus code. the whitepaper author's "no script-kiddie vibes" applies here: clean history, ADRs, signed releases.
- **Brand/launch track:** the coin art (already canon, `assets/PHOTO-2026-01-14-20-32-47.jpg`), "Much Meow" voice guide, meownero.com site, a *rewritten* whitepaper v2 (this plan's content, whitepaper's voice — the Super Troopers energy stays), launch livestream, T-shirts (a group member gets the merch lane, wolf shirts and all), community channels + moderation plan, and the Twitter presence (organic; a group member's "army of bots" is vetoed — bot amplification is exactly the sketch we're avoiding).
- The brand track may ship whenever it wants **except** claims about the chain, which must be reviewed against this plan (see §8.2 item 5 on "no trace" claims — and nobody promises "Bitcoin bridge" anywhere, ever; the words are "atomic swaps," per WS3).

---

## 11. First 10 GitHub issues

1. **ADR-001 scaffold: workstream tracker + decision rule** — encode §4's workstreams, hard/scope gates, and the fallback trigger; owners TJ + the whitepaper author; closes with signatures. *(M0)*
2. **WS1: License audit + counsel memo** — pin licenses across `orchard`/`halo2`/`librustzcash`/Zebra (+ Monero/RandomX/Tari for the fallback and WS5); counsel read on BOSL; open the ECC grant conversation if needed; deliver `LICENSES.md` draft. *(M0, hard gate)*
3. **WS2: Shielded-only consensus rule spike** — enumerate Zebra's transparent-pool surface; prototype empty-transparent-bundle rule + shielded coinbase (ZIP-213 Orchard coverage check) on custom regtest. Throwaway. *(M0, hard gate)*
4. **WS3: Bitcoin interop tier memo** — adaptor-signatures-over-RedPallas feasibility sketch; external cryptographer review; launch-blocking verdict; consensus prerequisites list. *(M0, scope gate)*
5. **WS4: RandomX-in-Zebra PoC** — swap PoW validation on regtest; difficulty algorithm selection; ASIC-posture statement draft. Throwaway. *(M0, hard gate)*
6. **WS5: Merge-mining decision brief + proxy PoC** — conditional on WS4→RandomX; §5 security model doc; multi-aux/Tari coexistence test against Monero stagenet. Throwaway. *(M0, scope gate)*
7. **WS6: Upstream baseline + tracking policy** — pin Zebra tag/NU baseline; 72h security-merge SLA doc; advisory subscriptions; ZF/ECC/Shielded Labs contact; pin FCMP++ shipped status from primary sources. *(M0)*
8. **WS7: Devnet + wallet-path spike** — Zebra custom-network coverage check; Zallet vs. zingolib shielded-only evaluation on the custom network; end-to-end send/receive demo; wallet-port estimate. Throwaway. *(M0, hard gate)*
9. **WS-M: Monero fallback control spike** — 1-week timebox; devnet + linear-emission patch; touched-file inventory; effort calibration report. Throwaway. *(M0)*
10. **Emission & monetary spec v1** — direction-agnostic: atomic units, 120s block-time check vs. proof sizes, fee policy (ZIP-317 evaluation), block-size policy, difficulty floor + LWMA parameters. *(M0→M1)*

*(Reproducible-build pipeline, threat-model v1, and the launch-fairness procedure doc are M1 issues, opened when the direction is signed. Brand-track issues — voice guide, site, whitepaper v2 — live under a separate `brand` label so they never block the consensus board.)*

## 12. Questions TJ and the whitepaper author must decide

1. **Is Tier 1 Bitcoin interop (atomic swaps) launch-blocking or post-launch?** WS3 will report feasibility; you two set the ambition. Recommendation: post-launch, with consensus prerequisites preserved at launch.
2. **If WS4 lands RandomX, do we merge-mine?** Merge-mining buys cheap honest hashrate and imports a zero-cost attacker class (§5.3); solo RandomX is slower but self-contained. This is a values call as much as an engineering one.
3. **Fallback authority:** confirm the §4 decision rule — hard-gate fail + one-week failed remediation ⇒ Direction M activates. Who besides you two must sign?
4. **Block time:** confirm 120s (whitepaper canon) over Zcash's 75s, accepting that WS-scoped checks may push back.
5. **Ticker collision:** "MEOW" is used by existing tokens (including the Solana squatter). Keep MEOW and fight for the name, or pick a cleaner ticker?
6. **Public identities:** are you both willing to be publicly identifiable founders of a mandatory-privacy coin? (Feeds §8.2 items 1, 6, 7.)
7. **Money:** who funds the external audit (5–6 figures), the counsel engagement, and the WS3 cryptographer review — group donation fund, out of pocket, or launch-delayed-until-funded?
8. **Deep-reorg protection:** accept young-chain 51% risk naked, or adopt a bounded finality/checkpoint mechanism at launch with a sunset date? (§5.4 — interacts with question 2.)
9. **Relationship posture with ECC / Zcash Foundation / Shielded Labs:** quiet derivative, or open collaboration (grant ask, upstreaming patches, shared advisories)? Recommendation: open — WS1 likely requires the conversation anyway, and goodwill is cheap insurance on WS6.
10. **the whitepaper author's role:** whitepaper author → is he the second maintainer with release-signing keys? The two-person release rule (§8.4) needs its second person named.

---

## 13. References

**Zcash stack / Direction Z**
- Zebra (Rust consensus node): https://github.com/ZcashFoundation/zebra
- zcashd deprecation: https://z.cash/support/zcashd-deprecation/ and EOL details: https://zcash.github.io/zcash/user/end-of-life.html
- Orchard protocol implementation: https://github.com/zcash/orchard · halo2: https://github.com/zcash/halo2
- ZIP-213, shielded coinbase: https://zips.z.cash/zip-0213
- ZIP-317, proportional fee mechanism: https://zips.z.cash/zip-0317
- Network Upgrade 7: https://z.cash/upgrade/nu7/
- Z3 / zcashd-deprecation ecosystem thread (Zcash forum): https://forum.zcashcommunity.com/t/zcash-z3-updates-formerly-zcashd-deprecation/48965
- Zcash counterfeiting vulnerability postmortem (CVE-2019-7167): https://electriccoin.co/blog/zcash-counterfeiting-vulnerability-successfully-remediated/

**Bitcoin interoperability precedent**
- COMIT `xmr-btc-swap` (production BTC↔XMR atomic swaps, scriptless on the XMR side): https://github.com/comit-network/xmr-btc-swap
- Farcaster BTC↔XMR atomic swap project: https://github.com/farcaster-project

**Monero / fallback / merge-mining**
- Full-Chain Membership Proofs development announcement — getmonero.org: https://www.getmonero.org/2024/04/27/fcmps.html
- Monero project (source, releases): https://github.com/monero-project/monero
- RandomX specification and code: https://github.com/tevador/RandomX
- Tari RFC-0132, "Merge Mining Monero" (mechanism, coinbase `tx_extra` commitment, validation): https://rfc.tari.com/RFC-0132_Merge_Mining_Monero
- Tari RFC-0131, Mining (hybrid split): https://delta1.github.io/tari/RFC-0131_Mining.html
- Tari mainnet launch coverage: https://www.theblock.co/post/353240/tari-privacy-network-merged-monero-mining-launch-mainnet
- Tari merge-mining proxy: https://lib.rs/crates/minotari_merge_mining_proxy

**Pirate Chain (cautionary)**
- Pirate Chain FAQ (self-reported ~90%-mined emission): https://piratechain.com/faq/
- Pirate Chain mining docs: https://piratechain.com/mining/

**Monetary design**
- Peter Todd, "Surprisingly, Tail Emission Is Not Inflationary": https://petertodd.org/2022/surprisingly-tail-emission-is-not-inflationary
- Monero tail emission docs (Moneropedia): https://www.getmonero.org/resources/moneropedia/tail-emission.html

**Historical / internal**
- Canonical whitepaper v1.1: `assets/Meownero updated.pdf` (SHA-256 in `research/artifact-inventory.md`)
- Chat record: `research/chat-transcript.md` · Whitepaper corrections: `research/whitepaper-notes.md`

*Note on source quality: claims that could not be pinned to primary sources (FCMP++ mainnet-activation timing, `orchard` current license text, Zebra custom-testnet coverage, ZIP-213 Orchard coinbase coverage) are deliberately phrased as Phase 0 verification tasks, not facts.*

---

*Meownero: Zcash's cryptography, Dogecoin's fairness, Bitcoin's handshake, and a cat that keeps every secret. Much Meow.* 🐈
