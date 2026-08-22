# Meownero Engineering Plan

**Status:** Draft for review by TJ and the whitepaper author · **Date:** 2026-08-22 · **Scope:** Planning only — no consensus code, no vendored upstream, no remote repository yet.

This plan turns the January 2026 whitepaper and the chat history into a credible first engineering phase. It is deliberately blunt where the source material is wrong, and deliberately conservative where cryptography or consensus questions are unresolved. Much Meow, but measured meow.

---

## 1. Product thesis and non-negotiables

**Thesis.** Meownero (MEOW) is a full, independent, proof-of-work cryptocurrency where privacy is mandatory for every transaction, launched honestly with no insider advantage, and wrapped in a meme-worthy cat brand that makes strong privacy approachable — Monero's substance with Dogecoin's charm.

**Non-negotiables** (distilled from the chat record in `research/chat-transcript.md`):

1. **Independent coin, not a token.** Its own chain, own consensus, own P2P network. No Solana/EVM contract.
2. **Mandatory privacy.** No transparent transaction type, ever. Privacy that is optional is privacy that is absent.
3. **Fair, honest launch.** Public advance notice ("give everyone a couple weeks, then everyone mines"), reproducible binaries published before genesis, no insta-mine games.
4. **No premine, founder reward, or developer tax.** Zero protocol-level allocation to insiders. Dev funding is out-of-band and disclosed (§7.4).
5. **Meme-worthy brand, "Much Meow" voice.** Fun is a feature, but it lives in the branding track (§10), never in consensus code.
6. **No cosmetic rename.** If Meownero is a fork, it must make consensus-meaningful, defensible design changes (emission, security model, launch process) — not a find-and-replace of "Monero" (the whitepaper author, 2026-08-22).

Anything that conflicts with these is out, regardless of how fun it sounds.

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
| 9 | "ASIC resistance (complementary)" section | Hand-waves the actual constraint: to merge-mine with Monero, the PoW must **be RandomX** (same VM, same keys), not merely "ASIC resistant." |

**What the whitepaper gets right and we keep:** mandatory privacy; no premine/dev tax; two-minute blocks; the linear 1 MEOW/block emission as a deliberate, defensible monetary design (§7); community governance posture; and the jokes.

---

## 3. Implementation directions compared

### Option A — Modern Monero-derived fork (FCMP++-era)

Fork `monero-project/monero` after the FCMP++ hard fork stabilizes; change emission to linear, add merge-mining validation, rebrand, re-genesis.

- **Privacy:** Mandatory by construction — every Monero-lineage transaction is private (FCMP++ membership proofs + RingCT amounts + stealth addresses). Meets non-negotiable #2 with zero new cryptography.
- **Merge-mining:** Native fit. Same RandomX PoW as the parent; Tari proves the model in production against Monero today with **no Monero consensus changes** (§5).
- **Codebase:** Mature C++, battle-tested consensus, but large, gnarly, and mid-transition — FCMP++ is the biggest change in Monero's history, and forking during the transition means inheriting fresh bugs. Timing matters: fork *after* the dust settles.
- **Differentiation risk:** This is the path most exposed to the "cosmetic rename" criticism. The consensus-meaningful deltas — linear emission, merge-mined security model, launch process — must be real and documented, or the whitepaper author's own objection applies to us.
- **License:** Monero's BSD-3-Clause-style license; RandomX is BSD-3-Clause. Fork-friendly, attribution required.

### Option B — Zcash-derived design with privacy mandatory

Build on **Zebra** (the Rust consensus node; `zcashd` hit end-of-life July 2026) with the Orchard shielded protocol, delete the transparent pool, and swap Equihash for RandomX to enable merge-mining.

- **Privacy:** Orchard (Halo 2, no trusted setup) is excellent cryptography with a small, auditable Rust implementation. But Zcash ships privacy as *optional*; making it mandatory means removing transparent addresses and the transparent value pool from consensus, wallets, and RPC — real surgery, though Pirate Chain proved mandatory-shielded is workable on the older Sapling protocol.
- **Merge-mining:** Requires replacing Equihash with RandomX inside Zebra and building the merge-mining validation layer from scratch in Rust. Feasible, but it is the largest single engineering item on this path and has no production precedent.
- **Codebase:** Modern Rust, memory-safe, well-factored — genuinely attractive. But the ecosystem is churning: zcashd's forced EOL, the June 2026 Orchard vulnerability disclosure, and the in-development Tachyon protocol all signal a stack in motion.
- **License risk:** Zebra and `librustzcash` are MIT/Apache-2.0 dual-licensed, but the `orchard` crate historically shipped under the **Bootstrap Open Source Licence (BOSL)**, which restricts use outside Zcash without a grant. Current licensing status **must be verified by counsel before any code is vendored** (§8.3). This is a potential hard blocker for Option B.
- **Differentiation:** Strongest answer to "genuinely different": a mandatory-shielded, merge-mined, linear-emission zk chain is not a rename of anything.

### Option C — Pirate Chain, the cautionary comparison (not a candidate)

Pirate Chain (ARRR, 2018) is the existence proof that **mandatory shielded transactions work in production** — z-address-only on Sapling, as a Komodo asset chain with delayed proof of work. It is equally the existence proof of what to avoid:

- **Front-loaded emission.** By Pirate's own FAQ, ~90% of the 200M supply is already mined; the schedule began at 256 ARRR/block and collapsed rapidly. Whatever the stated rationale, the outcome is that early miners hold the supply — exactly the "aggressive early emission resembles a premine" failure the whitepaper author flagged on 2026-01-15. Meownero's linear emission is the direct antidote.
- **Borrowed security with strings.** dPoW notarization to Komodo/Bitcoin trades 51% resistance for dependence on a notary set — a centralization trade we should only accept knowingly, if ever (§5.4).
- **Ecosystem fragility.** Dependence on another project's stack, thin dev funding, and privacy-coin exchange attrition. Plan for all three.

### Option D — Clean-room / new chain

Not justified. Writing new consensus and new privacy cryptography from scratch is a multi-year, multi-cryptographer effort; the failure mode is an unaudited zk or membership-proof implementation guarding real money. Every non-negotiable is achievable by deriving from an audited upstream. Rejected unless both A and B fail their spikes for reasons a new chain would actually fix (they won't).

### Summary

| Criterion | A: Monero fork | B: Zcash-derived | D: Clean room |
|---|---|---|---|
| Mandatory privacy | Free (inherent) | Surgery (remove transparent pool) | Build from scratch |
| Merge-mine w/ Monero | Native (RandomX already) | PoW swap required, no precedent | Build from scratch |
| Privacy tech currency | FCMP++ (in rollout) | Orchard/Halo 2 (proven), Tachyon (future) | N/A |
| Codebase | Mature C++, mid-transition | Modern Rust, churning ecosystem | None |
| License risk | Low (BSD-style) | **Unresolved (orchard/BOSL)** | None |
| "Not a cosmetic rename" | Weakest, must earn it | Strongest | Strongest |
| Time to credible testnet | Shortest | Medium–long | Years |

---

## 4. Decision: bounded Phase 0 process

The architecture is **not decided today**, and this plan does not pretend otherwise. It is decided by a timeboxed spike with a deadline and named deciders.

**Provisional lean: Option A** (Monero-derived, post-FCMP++, merge-mined, linear emission), because mandatory privacy and merge-mining are inherent rather than engineered, and the fair-launch + emission + security-model deltas are consensus-meaningful — enough to clear the "no cosmetic rename" bar if we document and defend them. Option B wins instead if **all** of the following hold at the end of Phase 0: (1) the orchard licensing question resolves cleanly, (2) the RandomX-in-Zebra spike shows the PoW swap is tractable, and (3) TJ and the whitepaper author weight "genuinely different" above time-to-testnet.

**Phase 0 rules:**

- **Timebox:** 6 weeks from kickoff. Hard stop.
- **Deliverable:** `ADR-001` (architecture decision record) with a scored decision matrix, signed off by TJ and the whitepaper author.
- **Spikes are throwaway.** Code written in Phase 0 is deleted or archived under `spikes/`; nothing from it is "blessed" into the real tree. This prevents sunk-cost capture of the decision.
- **No unresolved-crypto hand-waving.** Any question the spike cannot answer (e.g., exact FCMP++ mainnet status, orchard license, aux-PoW edge cases) is recorded in the ADR as an open risk with an owner — not assumed away.

---

## 5. Merge-mining feasibility audit

### 5.1 Verdict

**Merge-mining with modern Monero is feasible and production-proven — but the whitepaper's security story is wrong.** The CryptoNight/AuxPoW framing is obsolete; the working model is the one Tari runs today on RandomX.

### 5.2 How it actually works (Tari precedent)

Tari (mainnet since May 2025, founded by early Monero contributors) merge-mines with Monero with **zero Monero consensus changes** (Tari RFC-0132):

- The aux chain's block-header hash is embedded in the **merge-mining subfield of the Monero coinbase transaction's `tx_extra`**. Because the coinbase hashes into Monero's transaction merkle root, the aux commitment is bound into Monero's RandomX PoW.
- The aux chain's nodes validate a proof package (Monero header fields, RandomX VM key, coinbase merkle proof, coinbase extra) and accept the block if the achieved RandomX difficulty meets the *aux chain's own* target.
- Miners run a merge-mining proxy between their mining software (XMRig) and both daemons; the proxy sets the job difficulty so one solve can satisfy either chain.

Consequences for Meownero:

- **The PoW must be RandomX**, byte-compatible with Monero's parameters and key-block schedule. "ASIC-resistant algorithm" is not a design freedom here; it is fixed.
- FCMP++ does not change Monero's PoW, so the merge-mining mechanism survives the FCMP++ era. (Verify against the shipped hard-fork code during the spike.)
- **The `tx_extra` merge-mining field is a shared, contended resource.** Pools already merge-mining Tari can only add Meownero via an aux-chain merkle tree in that single field. Our proxy and validation must support multi-aux from day one, or the largest merge-mining pools cannot carry us.

### 5.3 The honest security model

- Day-one security equals **the hashrate of miners who opt in**, not "Monero's hashrate." If 2% of Monero merge-mines Meownero, our security is 2% of Monero — and any pool larger than that can 51% us.
- Attacking the aux chain is **costless on the parent chain**: a Monero pool can double-spend or censor Meownero while continuing to earn full XMR rewards. History has receipts — Eligius killed CoiledCoin (a merge-mined chain) in 2012 at effectively zero cost. The whitepaper's "must defeat both networks" claim inverts reality.
- Merge-mining also cuts the other way for fairness: it lowers the cost for honest hashrate to show up, which strengthens the fair launch — the more pools that adopt at genesis, the smaller any one pool's share.

### 5.4 Mitigations to evaluate in Phase 0 (none are free)

1. **Maximize pool adoption before genesis** — outreach to major Monero pools and P2Pool, a polished proxy, and a mining one-pager. This is the primary mitigation.
2. **Deep-reorg dampening** (e.g., rolling finality window or checkpoint policy) — effective, but a centralization trade that must be explicit, bounded, and ideally sunset-dated. Pirate's dPoW is the cautionary extreme.
3. **Hybrid solo+merge mining** (Tari-style algorithm split) — hedges pool capture but doubles mining-path complexity. Default: no for v1; record as an ADR option.
4. **Exchange/merchant confirmation guidance** scaled to observed merge-mined hashrate, published from day one.

---

## 6. Privacy primitives recommendation

Ground rule from the brief: recommend based on **current upstream reality**, not the draft's Kovri/ring-size language.

- **Option A (Monero lineage):** ship **FCMP++-era privacy** — full-chain membership proofs for sender ambiguity, RingCT/commitment-based hidden amounts, stealth addresses (subaddresses) for recipients. Do **not** fork pre-FCMP++ and freeze ring signatures; forking before FCMP++ stabilizes means launching with privacy Monero itself is discarding. Fork point = first post-FCMP++ stable release tag.
- **Option B (Zcash lineage):** **Orchard only** (Halo 2, no trusted setup), transparent pool removed at consensus level; track Tachyon as a future upgrade, not a dependency. The June 2026 Orchard vulnerability is a reminder that even excellent zk code has soundness risk — subscribe to upstream advisories and budget for re-audit of any code we alter.
- **Network layer (either option):** Dandelion++ for transaction-origin obfuscation, plus first-class Tor and I2P support for transaction relay. Kovri is dead; do not mention it outside the history section.
- **Non-goals for v1:** no novel cryptography of our own, no custom curve work, no bespoke proof systems. We are integrators of audited primitives, not authors of new ones. Any deviation requires an ADR and an external cryptographer review.
- **Supply auditability caveat (must be disclosed honestly):** hidden-amount chains cannot be trivially supply-audited; soundness of range/membership proofs is the backstop, and an undetected inflation bug is the worst-case failure (Zcash's CVE-2019-7167 counterfeiting vulnerability; Monero's 2017 key-image bug). Mitigations: minimize deltas to audited upstream code, run duplicate key-image/nullifier monitors, and adopt any upstream supply-audit tooling as it lands.

---

## 7. Emission and fair launch

### 7.1 Emission schedule (keep the whitepaper's one good deliberate choice)

**1 MEOW per 2-minute block, forever.** 0.5/min, 720/day, 262,800/year, linear and infinite. This is Dogecoin's tail shape with Monero's block cadence, and it is defensible:

- **Perpetual security budget:** miners are always paid in subsidy; no terminal fee-only regime (Peter Todd, "Surprisingly, Tail Emission Is Not Inflationary": with lost coins, constant absolute emission converges to a stable, non-inflationary supply in practice).
- **Minimal early-holder advantage:** pure linear emission is the *least* front-loaded schedule available — year-2 inflation is 100%, diluting early accumulation fast, the opposite of Pirate's curve. The emission rate the day you join is the rate forever ("the same meow as it will be in 100 years").
- **Simplicity:** one constant. No halvings to game, no curve parameters to argue about. Rejected alternatives: Monero-style smooth decline + tail (favors early holders — the whitepaper author, 2026-01-15), capped supply (terminal security-budget problem, and the whitepaper author explicitly prefers limited-but-not-capped), "divisibility instead of emission" (it's just logarithmic tail emission with extra steps — the whitepaper author, correctly).
- **Open parameters for ADR-001:** atomic units/decimal places, fee market and minimum relay fee, dynamic block size coupling (Monero's penalty system assumes nonzero subsidy — it works with a constant 1 MEOW but the penalty math must be re-derived, not copy-pasted), and whether the very first difficulty epoch needs special handling (§7.3).

### 7.2 No premine, no dev tax — and what "no insider advantage" requires operationally

- Genesis block contains **zero spendable outputs** to any party. Genesis message: something datestamped and public (headline + cat pun), chosen at the launch livestream, not before.
- Founders/insiders mine under **exactly the same conditions** as the public: same binaries, same announcement, same start time. TJ and the whitepaper author disclose that they will be mining.
- **No secret pre-genesis testing advantage:** the final chain parameters (genesis hash excepted) are public at least 2 weeks before launch; anyone can pre-provision miners.

### 7.3 Launch process (fairness is a procedure, not a vibe)

1. **T−4 weeks:** launch date/time announced publicly; parameters frozen and published; mining guide + merge-mining proxy released for testnet rehearsal.
2. **T−2 weeks:** release-candidate binaries published with SHA-256 hashes and signatures; reproducible-build instructions public so third parties can verify (§8.4). Pool outreach concludes; committed pools listed publicly.
3. **T−0:** genesis at the announced timestamp. Initial difficulty set to a sane floor (not 1) with an LWMA-class adjustment algorithm so early blocks cannot be insta-minted faster than difficulty can react; with a constant 1 MEOW reward the worst case is bounded, but a chaotic first hour is still a bad look and a reorg risk.
4. **T+2 weeks:** post-launch fairness report — blocks mined, pool distribution, any incidents — published against the pre-committed criteria.

### 7.4 Dev funding without a founder tax

Protocol allocates nothing to anyone — that is settled. Development is funded by: (a) a **disclosed, multisig community donation fund** (Monero CCS-style, proposals public), (b) direct sponsorship of specific audits or bounties, (c) volunteer work. The group's own capital ("$100K in the group") may seed the donation fund like any other donor — publicly, at market terms, with addresses disclosed. Buying MEOW from members via "wire instructions" (the 02-06 chat bit) is exactly the kind of informal insider dealing that must **not** happen once this is real; all acquisition is mining or open-market.

### 7.5 Mining-pool incentives

Pools carry us or nobody does. Concretely: multi-aux-capable proxy that coexists with Tari, pool-operator documentation, a pool reference deployment, testnet dry-run with at least two independent pools before mainnet, and zero pool fees taken by the project (pools set their own).

---

## 8. Security, legal, and operational program

### 8.1 Threat model (v0 — to be formalized as a living doc)

| Threat | Vector | Posture |
|---|---|---|
| 51% / deep reorg | Large Monero pool attacks aux chain at zero parent-chain cost | §5.3–5.4; confirmation guidance; monitoring for competing chains |
| Inflation bug | Soundness flaw in membership/range proofs or our patches | Minimize consensus deltas; upstream advisory tracking; key-image/nullifier duplicate monitors; external audit before mainnet |
| Tx-graph/timing analysis | Statistical deanonymization, poisoned outputs | FCMP++/Orchard-scale anonymity sets; Dandelion++; wallet-side churn guidance |
| Network-layer deanonymization | IP linkage, eclipse/sybil attacks on P2P | Tor/I2P relay support; diverse seed nodes; anchor connections |
| Supply-chain compromise | Malicious dependency, compromised CI, backdoored release | §8.4; two-person release rule; dependency pinning + review |
| Key compromise | Release-signing or seed-node keys stolen | §8.5 |
| Social/insider | "Leak" paranoia (see 02-10 chat), squatter projects, fake binaries | Everything public by default; official-channel discipline; the Solana "Meownero" is a brand problem, not a chain problem |
| Regulatory shock | Exchange delistings of privacy coins, jurisdictional bans | §8.2; design assumes no exchange support at launch |

### 8.2 Questions for legal counsel (obtain real counsel; none of this is settled by us)

1. Exposure of identifiable founders launching a **mandatory-privacy** coin: money-transmission, sanctions (OFAC precedent from the Tornado Cash saga), and jurisdiction-specific privacy-coin bans (e.g., Japan, South Korea; EU AMLR trajectory for 2027).
2. Does a zero-premine, no-sale, mined-only launch keep MEOW clearly outside securities frameworks (Howey / MiCA utility analysis)? What launch communications would jeopardize that?
3. Liability for marketing claims: the coin art literally says "no trace currency" and "zero logs" — what claims can we responsibly make?
4. Trademark: register "Meownero"? Posture toward the pre-existing Solana "Meownero" token; risk that *we* are accused of association with it.
5. Domain/entity structure: should meownero.com and the donation multisig sit in a foundation or association rather than with TJ personally?
6. Contributor exposure: does merging code or running seed nodes create liability for individual group members?

### 8.3 Upstream licenses and attribution

- **Monero:** BSD-3-Clause-style — fork-friendly; preserve copyright notices; attribute prominently. **RandomX:** BSD-3-Clause.
- **Zcash stack:** Zebra and librustzcash are MIT/Apache-2.0; the **`orchard` crate's BOSL history is the open question** — verify current license and, if BOSL applies, whether a grant is obtainable. Hard gate for Option B.
- **Tari:** if we adapt their merge-mining proxy or validation code, verify license (BSD-3-Clause family) and attribute.
- Deliverable: `LICENSES.md` + per-file header audit before any code is vendored (Issue #7).

### 8.4 Supply-chain security and reproducible builds

- Deterministic builds from day one (Monero uses Guix-based reproducible builds — inherit that pipeline for Option A; for Option B, cargo-based reproducibility with pinned toolchain and vendored deps).
- All release binaries built by ≥2 independent parties whose hashes must match before publication; hashes + minisign/GPG signatures published on the site and in-repo.
- Dependency policy: pinned versions, lockfiles committed, no dependency added without review; CI runs from committed config only; branch protection + signed commits for consensus-critical paths.

### 8.5 Key management

- **Release-signing keys:** hardware-backed, held by ≥2 maintainers (TJ + the whitepaper author to start), with a published key-transparency page and revocation procedure.
- **Donation fund:** m-of-n multisig, holders disclosed, no single spender.
- **Seed-node infrastructure:** separate credentials per node, no shared root, documented rotation.
- **No "network keys" exist** in this architecture — there is nothing like a mint key, and we must be able to say so truthfully.

### 8.6 Testnet → mainnet gates

Each promotion requires **all** exit criteria of the prior stage (§9) plus: no open consensus-severity bugs; external audit findings triaged with criticals fixed; two independent pools mining on testnet; reproducible-build verification by a third party; incident-response runbook rehearsed once.

### 8.7 Wallets, node, and miner tooling (v1 scope)

- **v1:** daemon + CLI wallet (inherited from upstream), merge-mining proxy, mining guide. That's the launch surface.
- **v1.x:** GUI wallet (rebrand upstream GUI where licensing allows), remote-node ("light") wallet support with the honest privacy caveats the whitepaper already states.
- **Later, explicitly not launch-blocking:** mobile wallets, hardware-wallet integration (requires vendor cooperation; long lead), merchant tooling.

### 8.8 Block explorer for a private chain

An explorer can show: block heights/hashes/timestamps, tx hashes and sizes, fee totals (public in Monero-lineage), emission tally, and hashrate/difficulty — and **cannot** show amounts, senders, or recipients. Build or adapt an onion-monero-blockexplorer-style tool; document loudly that "the explorer looks empty of amounts" is the product working. Supply tally page (`emission = height × 1 MEOW` + genesis) doubles as a public no-premine proof.

### 8.9 Incident response

- Published security policy + PGP/security@ contact before mainnet; 90-day coordinated disclosure default.
- Consensus-bug playbook drafted and rehearsed pre-launch: severity ladder, who can call for an emergency patch or rollback, pool/exchange contact tree, and a pre-agreed public-comms template. The June 2026 Orchard vulnerability and zcashd's emergency EOL are the case study: upstream privacy stacks *do* have fire drills, and we inherit them.
- Upstream watch: subscribe to Monero and (if relevant) Zcash security advisories; a merge-from-upstream policy with a 72-hour SLA for security patches.

---

## 9. Milestones and exit criteria

**M0 — Feasibility spike (throwaway), weeks 1–6.**
Two parallel throwaway prototypes: (a) Monero fork boots a private devnet with linear-emission patch + rebrand constants; merge-mining proxy PoC submits Meownero-committed blocks against Monero **stagenet** and our devnet validates them, including the multi-aux/Tari-coexistence case; (b) Zebra devnet memo: transparent-pool removal scope, RandomX-swap scope, orchard license verdict.
*Exit criteria:* both spike reports written; merge-mined devnet block demonstrably validated end-to-end (a); Option B costed with license verdict (b); FCMP++ shipped-status pinned from primary sources; ADR-001 signed by TJ + the whitepaper author. **The fork is not blessed until this gate passes.**

**M1 — Foundation, weeks 7–12.**
Real repo layout from chosen upstream at pinned tag; consensus deltas as a reviewable patch series; threat model v1; CI + reproducible build pipeline green.
*Exit criteria:* clean build from source by an outsider following docs; every consensus delta has an ADR; `git diff` vs upstream tag is enumerable and justified.

**M2 — Private devnet, weeks 13–20.**
Multi-node devnet with merge-mining live against Monero stagenet; CLI wallet sends mandatory-private transactions; explorer alpha; difficulty algorithm validated under hashrate whiplash simulation.
*Exit criteria:* 2-week devnet uptime without consensus fault; reorg/partition chaos tests pass; fairness-relevant parameters (difficulty floor, LWMA window) frozen.

**M3 — Public testnet + audit, weeks 21–32.**
Public testnet with ≥2 independent pools; external security review of consensus deltas and merge-mining validation; bug bounty opens; launch-procedure dry run including a rehearsed incident.
*Exit criteria:* audit criticals fixed; third-party reproducible-build verification; testnet survives an adversarial event (invited attack week); §8.6 gates met.

**M4 — Mainnet launch.**
Execute §7.3 exactly as published.
*Exit criteria:* genesis at announced time; ≥2 independent pools mining in the first 24h; post-launch fairness report published at T+2 weeks.

**M5 — Post-launch hardening.** GUI wallet, seed-node diversity, upstream-merge cadence, governance formalization. (Deliberately unscheduled until M4 lands.)

---

## 10. Two tracks: consensus engineering vs. Much Meow

These run in parallel and must never share a critical path:

- **Consensus track (this document, §§3–9):** slow, reviewed, audited, boring on purpose. No memes in commit messages on consensus code. the whitepaper author's "no script-kiddie vibes" applies here: clean history, ADRs, signed releases.
- **Brand/launch track:** the coin art (already canon, `assets/PHOTO-2026-01-14-20-32-47.jpg`), "Much Meow" voice guide, meownero.com site, a *rewritten* whitepaper v2 (this plan's content, whitepaper's voice — the Super Troopers energy stays), launch livestream, T-shirts (a group member gets the merch lane, wolf shirts and all), community channels + moderation plan, and the Twitter presence (organic; a group member's "army of bots" is vetoed — bot amplification is exactly the sketch we're avoiding).
- The brand track may ship whenever it wants **except** claims about the chain, which must be reviewed against this plan (see §8.2 item 3 on "no trace" claims).

---

## 11. First 10 GitHub issues

1. **ADR-001 scaffold + decision matrix** — encode §3/§4 criteria and scoring; owners TJ + the whitepaper author; closes with a signed decision. *(M0)*
2. **Spike A1: Monero fork devnet** — boot private devnet from latest release; patch emission to constant 1 MEOW; document every touched file. Throwaway. *(M0)*
3. **Spike A2: merge-mining proxy PoC** — XMRig → proxy → Monero stagenet + Meownero devnet; validate coinbase-merkle proof path end-to-end; test multi-aux coexistence with Tari's field usage. Throwaway. *(M0)*
4. **Spike B1: Zebra mandatory-shielded + RandomX feasibility memo** — scope transparent-pool removal and PoW swap; deliver orchard/BOSL license verdict with counsel input. *(M0)*
5. **Pin FCMP++ shipped status from primary sources** — getmonero.org, monero-project GitHub milestones; record fork-point tag recommendation. *(M0)*
6. **Emission & monetary spec v1** — atomic units, fee policy, dynamic-block-size penalty math re-derived for constant subsidy, difficulty algorithm + launch floor. *(M1)*
7. **License and attribution audit** — LICENSES.md across candidate upstreams (Monero, RandomX, Zebra/librustzcash/orchard, Tari proxy). *(M0/M1)*
8. **Threat model v1** — formalize §8.1 into a living doc with owners per threat. *(M1)*
9. **Reproducible build pipeline** — Guix (Option A) or pinned-cargo (Option B) deterministic builds; two-builder hash-match requirement in CI. *(M1)*
10. **Launch fairness procedure doc** — §7.3 as a checklist with dates templated, pool-outreach list, and the T+2-week fairness-report template. *(M2, drafted early)*

*(Brand-track issues — voice guide, site, whitepaper v2 — live in a separate `brand` repo/label so they never block the consensus board.)*

## 12. Questions TJ and the whitepaper author must decide

1. **Weighting for ADR-001:** if the spikes tie, does "genuinely different" (→ B) beat "shortest path to credible testnet" (→ A)? Say it now, before sunk costs say it for you.
2. **Ticker collision:** "MEOW" is used by existing tokens (including the Solana squatter). Keep MEOW and fight for the name, or pick a cleaner ticker?
3. **Public identities:** are you both willing to be publicly identifiable founders of a mandatory-privacy coin? (Feeds directly into §8.2 items 1 and 5.)
4. **Money:** who funds the external audit (5–6 figures) and the counsel engagement — group donation fund, out of pocket, or launch-delayed-until-funded?
5. **Deep-reorg protection:** accept young-chain 51% risk naked, or adopt a bounded finality/checkpoint mechanism at launch with a sunset date? (§5.4 — this is a values call, not just an engineering call.)
6. **Launch window:** commit to a target quarter now (affects fork-point choice relative to FCMP++ stabilization), or let M0–M3 exit criteria set the date? (Recommended: the latter, stated publicly.)
7. **Governance of the donation fund:** who are the multisig holders beyond you two, and is S's capital in as a disclosed donor?
8. **the whitepaper author's role:** whitepaper author → is he the second maintainer with release-signing keys? The two-person release rule (§8.4) needs its second person named.

---

## 13. References

**Monero / FCMP++ / RandomX**
- Full-Chain Membership Proofs development announcement — getmonero.org: https://www.getmonero.org/2024/04/27/fcmps.html
- Monero project (source, releases): https://github.com/monero-project/monero
- RandomX specification and code: https://github.com/tevador/RandomX
- Monero FCMP++ progress (project X/Twitter update): https://x.com/monero/status/1861129765870092395

**Merge-mining precedent**
- Tari RFC-0132, "Merge Mining Monero" (mechanism, coinbase `tx_extra` commitment, validation): https://rfc.tari.com/RFC-0132_Merge_Mining_Monero
- Tari RFC-0131, Mining (hybrid split): https://delta1.github.io/tari/RFC-0131_Mining.html
- Tari mainnet launch coverage: https://www.theblock.co/post/353240/tari-privacy-network-merged-monero-mining-launch-mainnet
- Tari merge-mining proxy: https://lib.rs/crates/minotari_merge_mining_proxy
- Tari Labs University, Monero merged mining: https://tlu.tarilabs.com/mining/merged-mining-monero

**Zcash stack**
- zcashd deprecation: https://z.cash/support/zcashd-deprecation/ and EOL details: https://zcash.github.io/zcash/user/end-of-life.html
- Zebra (Zcash Foundation Rust node): https://github.com/ZcashFoundation/zebra
- Network Upgrade 7: https://z.cash/upgrade/nu7/
- Z3 / zcashd-deprecation ecosystem thread (Zcash forum): https://forum.zcashcommunity.com/t/zcash-z3-updates-formerly-zcashd-deprecation/48965
- Zcash counterfeiting vulnerability postmortem (CVE-2019-7167): https://electriccoin.co/blog/zcash-counterfeiting-vulnerability-successfully-remediated/

**Pirate Chain (cautionary)**
- Pirate Chain FAQ (self-reported ~90%-mined emission): https://piratechain.com/faq/
- Pirate Chain mining docs: https://piratechain.com/mining/

**Monetary design**
- Peter Todd, "Surprisingly, Tail Emission Is Not Inflationary": https://petertodd.org/2022/surprisingly-tail-emission-is-not-inflationary
- Monero tail emission docs (Moneropedia): https://www.getmonero.org/resources/moneropedia/tail-emission.html

**Historical / internal**
- Canonical whitepaper v1.1: `assets/Meownero updated.pdf` (SHA-256 in `research/artifact-inventory.md`)
- Chat record: `research/chat-transcript.md` · Whitepaper corrections: `research/whitepaper-notes.md`

*Note on source quality: FCMP++ mainnet-activation timing circulating in secondary/SEO coverage was **not** treated as fact in this plan; pinning the shipped status from primary sources is Issue #5 and an explicit M0 exit criterion.*

---

*Meownero: Monero's substance, Dogecoin's charm, and a launch so fair even the dogs will respect it. Much Meow.* 🐈
