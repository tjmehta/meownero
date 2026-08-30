# E1 — Zcash/Zebra lineage viability

**Exploration:** Can Meownero safely derive from the modern Zcash stack (Zebra node + shielded-pool cryptography)? · **Status:** Draft (rev 2) · **Date:** 2026-08-22, revised 2026-08-30

> **Rev 2 changelog (2026-08-30):** Stage 1 open tasks 1–3 closed against primary sources; task 4 partially closed. The June 2026 incident and the NU6.3 upgrade are now `[VERIFIED-PRIMARY]` end-to-end (ZIP 257, ZIP 258, ZIP 2005, ZIP 318, zfnd.org, Project Tachyon). Three findings are new and load-bearing: the root cause was a **shared gadget-library bug, not Orchard-specific code**; **Ironwood ships an unfinished post-quantum roadmap dependency (ZIP 2005)**; and the **NU6.3 ZIPs are still Draft/Proposed/Reserved despite being live on mainnet**. No PLAN.md edits made — see §10.

## 1. Draft verdict (DRAFT)

The two blockers PLAN.md anticipated have moved in opposite directions. The **license blocker is fully resolved and now confirmed through the Ironwood era**: `orchard` is MIT OR Apache-2.0 since v0.7.0 (2024), and the Ironwood-era releases (0.15.x, July–Aug 2026) plus the `zcash/ironwood` proof repo carry the same dual license `[VERIFIED-PRIMARY]`. The **maturity picture is more nuanced than rev 1 recorded**. A Candidate Z fork today chooses between **Ironwood** (live since 2026-07-28, ~1 month of production, but backed by the strongest formal-verification artifact any shielded pool has ever shipped with) and **Sapling** (production since 2018, but the pool upstream is separately moving to restrict — see ZIP 219). Rev 1 framed this as "assurance story vs. production history"; the evidence now shows that framing is too clean, in both directions:

- **Against Ironwood's youth:** the verification is real, public, and unusually thorough (2,700+ Lean theorems, two independent firms, published sources under MIT/Apache-2.0). It is materially better evidence than "N years without a known incident" — which is exactly what Orchard had for four years while carrying a counterfeiting bug.
- **Against over-crediting it:** Project Tachyon's own scope statement excludes implementation bugs and assumes the named cryptographic assumptions hold. And Ironwood carries a **forward dependency we would inherit**: ZIP 2005 restructures note commitments for a future "Recovery Protocol" whose post-quantum proof system **has not been selected yet**. Adopting Ironwood means adopting an unfinished roadmap, not a finished pool.

The single most important new finding for PLAN.md §2 is the **root cause**: a missing copy constraint in `halo2_gadgets`' variable-base scalar multiplication — a **general-purpose gadget library**, not Orchard-specific circuit code `[VERIFIED-PRIMARY]` (ZIP 257). Four years of production, multiple audits, and ~$1.7B secured did not surface it; a researcher looking deliberately (with LLM assistance) did, in days. This is direct evidence for the §2.2 doctrine and against reading "years in production" as a soundness proxy — and it cuts against *both* candidate lineages, since the same argument applies to any proof-system dependency we inherit.

Lineage viability otherwise looks credible and, if anything, better than rev 1 judged: Zebra is the sole maintained node, and the upstream's incident response was fast, coordinated, and documented in the ZIPs themselves (emergency soft fork in ~4 days, permanent fix in 5, a re-architected pool in 8 weeks). That is positive evidence under §2.2 items 2–3.

## 2. The June 2026 Orchard incident — verified timeline

All `[VERIFIED-PRIMARY]` unless marked. Sources: ZIP 257 (Final), zfnd.org release post, Shielded Labs disclosure post (all read 2026-08-30).

| Date (2026) | Event |
|---|---|
| May 29 | Taylor Hornby discovers the soundness flaw; discloses to ZODL core engineers the same evening. |
| May 31 | Private coordination with miners and exchanges begins. |
| Jun 2, ~02:00 UTC | **Emergency soft fork** activates at mainnet height **3,363,426**: `nActionsOrchard = 0` enforced — Orchard disabled network-wide (Zebra 4.5.3). |
| Jun 3 | **NU6.2** hard fork activates at mainnet height **3,364,600** (testnet 4,052,000), re-enabling Orchard on the corrected circuit (Zebra 5.0.0, `orchard` 0.14.0, `halo2_gadgets` 0.5.0). |
| Jun 12 → Jun 23 | Ironwood circuit implementation: `zcash/orchard` PR #504 opened and merged. `[SECONDARY]` — grant application. |
| Jul 28 | **NU6.3 "Ironwood"** activates at mainnet height **3,428,143**; Orchard sealed. |

- **Root cause, verbatim (ZIP 257):** "Missing copy constraint in halo2_gadgets variable-base scalar multiplication allows under-constrained base, breaking Orchard Action circuit soundness." The ZIP states it "could have allowed balance violation and theft of funds." NU6.2's permanent change corrected the variable-base scalar multiplication gadget, **changing the verifying key**, and added a canonical-length rule: "The `proofsOrchard` field MUST have the canonical length of 2720 + 2272 · nActionsOrchard bytes."
- **Exposure window:** Orchard activation (May 2022) through 2026-06-01 — approximately four years.
- **Detectability — the two official statements do not say the same thing, and the difference matters to us:**
  - Zcash Foundation: "The vulnerability was caught before any known exploitation occurred. There is no evidence of unauthorized value creation," and "Zcash's turnstile mechanism confirmed that the total supply remained intact throughout."
  - Shielded Labs (Zooko Wilcox, Jason McGee, Taylor Hornby): "due to the privacy properties of Orchard and the nature of the bug, there is no definitive way to determine using only cryptography whether such exploitation occurred before the vulnerability was discovered and fixed." They assess exploitation as *unlikely* given the bug's complexity and the deliberate nature of its discovery.
  - **Reading:** these are compatible but easily conflated. The turnstile bounds *value that left the pool*; it cannot detect counterfeit value that was created and never exited, nor distinguish counterfeit from legitimate value still resident in the pool. Any claim we make about supply auditability must respect that distinction. Rev 1's phrasing ("retroactive audit … was impossible") was directionally right but imprecise — the correct statement is the Shielded Labs one, scoped to cryptographic determination.
- **Advisories:** GHSA-jfw5-j458-pfv6 (Zebra, Critical). Separately GHSA-2x4w-pxqw-58v9 (`orchard`: authorized bundle/PCZT could carry a `zkproof` padded with arbitrary trailing data), fixed in the same 0.14.0 release. No CVE and no single consolidated ECC postmortem was located; the authoritative written record is distributed across ZIP 257, the ZF release post, and the Shielded Labs forum disclosure. **Correction to rev 1:** the disclosure post is by **Shielded Labs**, not ECC/ZF — rev 1's open task named the wrong publisher.
- Taylor Hornby's full technical work log is linked from the disclosure post (Google Drive). `[SECONDARY]` — not yet read; see §9.

## 3. NU6.3 "Ironwood" — verified specification

Activation: mainnet height **3,428,143**, 2026-07-28 (ZIP 258; Zebra 6.0.0 release notes). All rules below quoted from ZIP 258 `[VERIFIED-PRIMARY]` (read 2026-08-30).

**ZIP set (note the statuses):**

| ZIP | Title | Status |
|---|---|---|
| 258 | Deployment of the NU6.3 Network Upgrade | **Draft** |
| 2005 | Ironwood Quantum Recoverability | **Proposed** |
| 2006 | Restricting Transfers into the Orchard Pool | **Reserved** |
| 318 | Orchard to Ironwood Migration | **Draft** |
| 326 | NU6.3 Consequences for Wallets | **Draft** |
| 229 | Version 6 Transaction Format | **Draft** |
| 257 | Deployment of the Orchard Temporary Vulnerability Mitigation and NU6.2 Network Upgrade | Final |
| 209 / 213 / 317 | Chain value pool balances / Shielded Coinbase / Proportional Transfer Fee (rev 1: NU6.3) | Final / Final / Draft |

> **Finding — ZIP status vs. deployment.** The consensus rules securing ~$1.7B are live on mainnet while their specifications sit at Draft/Proposed/**Reserved**. ZIP 2006, which the Orchard restriction is attributed to, has no published text at all. A Candidate Z fork must pin to *implementation* (Zebra tag + `orchard` version), not to spec text, and must budget for spec churn as these ZIPs are finalized. This is an editorial-lag risk PLAN.md does not currently account for.

**Ironwood pool creation (ZIP 258):** value-balance consistency via `valueBalanceIronwood`; `anchorIronwood` must refer to an earlier block's final Ironwood treestate; commitment-tree capacity bound; and "Any _Ironwood-pool_ output of a coinbase transaction decrypted to a note plaintext MUST have note plaintext lead byte `0x03`."

**Orchard sealing (ZIP 258), verbatim:**
- "No new value may enter the _Orchard pool_: for every transaction, value balance must be nonnegative"
- "Every _Orchard-pool_ Action MUST be created with cross-address transfers disabled (the `enableCrossAddress` bit set as 0)"
- "A coinbase transaction MUST NOT contain any _Orchard-pool_ Actions; that is, its Orchard component MUST be empty"
- Chain value pool balances: "If the chain value pool balance for any of the Sprout, Sapling, Orchard, Ironwood, transparent, or deferred development fund pools would become negative … then all nodes MUST reject the block as invalid." (ZIP 209, amended for NU6.3.)

**Migration (ZIP 318):** a two-phase wallet-side process — quantize the migratable balance into canonical denominations (n × 10^k ZEC, n ∈ {1,2,5}) via send-to-self, then broadcast pre-signed pool-crossing transactions at randomly drawn scheduled heights, one Orchard note → one Ironwood denomination each. The ZIP notes "a pool-crossing transfer necessarily reveals the net amount crossing between the pools on-chain," and that NU6.3 "enables a rule that disables ordinary payments within the old Orchard pool while still permitting change." **This is a privacy-degrading migration by construction** — relevant to E2 and to any launch story we tell about pool migrations.

> **Finding — ZIP 2005 is a forward dependency, not a finished feature.** "Ironwood Quantum Recoverability" (status: Proposed) re-derives note randomness commitments so that note parameters are bound through hash functions modeled as post-quantum random oracles (BLAKE2b-512, BLAKE3) rather than resting solely on discrete-log hardness. It does **not** change the circuits today, and it explicitly disclaims completeness: "This change does not by itself make Zcash secure against attacks using quantum computers, but is a necessary and substantial step toward that goal." The recovery path it enables requires a future Recovery Protocol "checking a more expensive and complicated statement in zero knowledge" using **a post-quantum proof system to be selected later**. Binding security for Ironwood notes therefore rests on those hashes behaving as collapsing/post-quantum random oracles, while DLP hardness is assumed to hold "until the protocol is disabled." Adopting Ironwood means adopting this trajectory and the NU7-era work that completes it.

## 4. Formal verification — what was actually proven

`[VERIFIED-PRIMARY]` — tachyon.z.cash "Formal Verification of Zcash Ironwood Completed" and the retroactive grant application (read 2026-08-30).

- **Who:** Tal Derei (formalization lead, algebraic verifier model and knowledge-soundness notions), Sean Bowe (circuit implementation, coordination), Daira-Emma Hopwood (ZODL), with two externally funded firms: **zkSecurity** ($150k — circuit security audit, AI-assisted auditing, formal verification; Gregor Mitscha-Baude) and **Formal Land** ($75k — independent backup formalization; Guillaume Claret, Valerii Huhnin). Also Giorgio Dell'Immagine.
- **What:** 2,700+ theorems in **Lean**, built with the Clean tool over ArkLib, VCV-io and Mathlib. The bulk of the effort proves **knowledge soundness for Ironwood's zk-SNARK**; the headline property is **balance integrity** — "undetectable counterfeiting bugs do not exist in Ironwood," reduced "down to named assumptions."
- **Duration:** ~8 weeks (2026-06-01 → 2026-07-28). Two independent formalizations were funded deliberately.
- **Sources:** `github.com/zcash/ironwood`, public, **dual MIT/Apache-2.0** — i.e. we could reuse the proofs, not merely cite them.
- **Explicit scope limits, verbatim:** the verification "rules out undetectable counterfeiting bugs originating in the zk-SNARK construction (circuit or protocol specification), up to explicitly named cryptographic assumptions," and "deliberately does not cover implementation bugs" or "failures of cryptographic assumptions." **Privacy properties are not covered** — only balance integrity.

> **Assessment for §2.2.** This is the strongest assurance artifact available on either candidate lineage, and it is reusable. Two caveats before it can be credited at full weight: (a) the **model-to-code gap** — whether the Lean model is mechanically tied to the deployed Rust circuit, or is a hand-written model of it, is not established by the sources read and is the classic failure mode of circuit verification `[OPEN]`; (b) the named cryptographic assumptions have not been enumerated and checked against our own doctrine `[OPEN]`. Note the uncomfortable adjacency: the June bug lived in a **gadget library**, and "implementation bugs" are exactly what Tachyon excludes. Whether a missing copy constraint in `halo2_gadgets` falls inside or outside the verified boundary is the question that decides how much this artifact is worth to us.

## 5. Production precedents & maturity evidence

- Zcash mainnet live since 2016; shielded pools in continuous production since launch (Sprout → Sapling 2018 → Orchard 2022 → Ironwood 2026). `[SECONDARY]` (uncontroversial; heights pinnable from zips.z.cash on final pass)
- **zcashd end-of-life:** automatic End-of-Support halt at block 3,417,100 on 2026-07-18; users directed to Zebra (node) / Zallet (wallet). `[VERIFIED-PRIMARY]` — zcash.github.io/zcash/user/end-of-life.html (read 2026-08-21)
- **Licensing, Ironwood era — open task closed.** `orchard` is "MIT OR Apache-2.0" since v0.7.0 (2024-01-26; the Zcash/Zebra-only exception "is no longer necessary"), and the current Ironwood-era line **0.15.0 (2026-07-09) → 0.15.5 (2026-08-02)** carries the same dual license. There is **no separate `ironwood` crate** — Ironwood support ships inside `orchard` (`orchard::ValuePool`, `BundleVersion`, `OrchardCircuitVersion::PostNu6_3` enforcing the `disableCrossAddress` public input). `zcash/ironwood` (the Lean proofs) is also dual MIT/Apache-2.0. `[VERIFIED-PRIMARY]` — orchard CHANGELOG/README, zcash/ironwood README (read 2026-08-30). BOSL does not apply anywhere on this path.
- **Zebra release cadence (Ironwood era):** 4.5.3 (emergency soft fork) → 5.0.0 (NU6.2) → 6.0.0-rc.0 (2026-07-02) → **6.0.0 (2026-07-10, NU6.3 support)** → 6.2.0 (2026-07-17, experimental zcashd-compat mode) → 6.2.1/6.2.2/6.2.3 (Jul 22/24/28; 6.2.2 fixed credential exposure and RPC consistency) → **6.3.0 (2026-08-10)**. Dual MIT/Apache-2.0. `[VERIFIED-PRIMARY]` — GitHub releases (read 2026-08-30). First-stable (1.0.0) date still `[OPEN]`.
- **Zebra custom-network support:** Regtest configuration exists and is granular enough to include consensus-relevant toggles — the releases name `should_allow_unshielded_coinbase_spends` and a Regtest-only `generatetoaddress` RPC. Encouraging for both the Stage 2 prototype and the E2 mandatory-privacy delta, but **not yet confirmed** to cover custom genesis, custom activation heights and custom PoW parameters together. `[OPEN]`
- **Zallet (wallet):** official zcashd-wallet successor, **alpha** as of July 2026 (Alpha.4; incomplete RPC coverage; breaking changes expected). `[VERIFIED-PRIMARY]` — zcash.github.io/zallet + EOL page. **Zebra ships no wallet; on this lineage the wallet is launch-critical path.** Zebra 6.2.0's zcashd-compat mode is a migration aid for existing wallets, not a wallet.
- **Historical incident:** CVE-2019-7167 (Sprout counterfeiting vulnerability, disclosed/remediated 2019). With the June 2026 Orchard flaw, this lineage has now had **two** counterfeiting-class soundness bugs found and remediated, in two different proving systems, seven years apart. Read honestly, that is evidence both of real risk and of a functioning find-and-fix culture. `[VERIFIED-PRIMARY]` — ECC postmortem (linked in PLAN.md §14).

## 6. Consensus/crypto delta (lineage adoption itself)

Fork Zebra at a pinned post-NU6.3 tag (6.3.0 or later); re-genesis; network parameters (magic bytes, address HRPs, ports, DNS seeds). Small and mechanical. The load-bearing deltas live in E2 (mandatory privacy), E3 (emission + dev-fund stream removal), E5 (PoW).

**Pool choice remains the big decision, and rev 2 sharpens the options:**

- **Ironwood-only** — current upstream direction; strongest assurance artifact; ~1 month production; inherits the v6 transaction format (ZIP 229, Draft) and the ZIP 2005 post-quantum trajectory; no Orchard/Sapling legacy code paths to carry.
- **Sapling-only** — 8 years production; Pirate Chain precedent for mandatory-shielded operation; but upstream has **ZIP 219 "Disabling Addition of New Value to the Sapling Chain Value Pool"** reserved, i.e. upstream intends to restrict Sapling too. Building on a pool upstream is walking away from means diverging from the maintained path early, which directly contradicts our 72h-security-merge posture. **This materially weakens the Sapling option relative to rev 1.** `[VERIFIED-PRIMARY]` for ZIP 219's existence/status; upstream intent and timeline `[OPEN]`.
- **Both** — largest surface; no reason to carry two pools on a greenfield chain with mandatory privacy.

A greenfield chain has one advantage upstream lacks: **no legacy pools to seal, migrate, or turnstile.** We would launch with exactly one pool and no migration machinery — which removes ZIP 318's privacy-degrading migration path and much of ZIP 258's complexity from our surface.

## 7. Security assumptions introduced

- Soundness of the chosen pool's circuit as deployed. For Ironwood this is now backed by a public Lean proof of balance integrity, **modulo the model-to-code gap and the named cryptographic assumptions** (§4) `[OPEN]`. For Sapling: 8 years of production, but pre-Halo trusted-setup lineage — which proving system the current Sapling pool uses post-NU5, and what a Sapling-only fork actually inherits, remains `[OPEN]`.
- **Ironwood-specific:** binding security depends on BLAKE2b-512/BLAKE3 as post-quantum collapsing hash functions; DLP hardness assumed to hold until the protocol is disabled; the recovery path depends on a **post-quantum proof system not yet selected** (ZIP 2005).
- Shared-dependency risk: we inherit `halo2` / `halo2_gadgets` wholesale. The June 2026 flaw was in that shared gadget layer, not in Orchard-specific code — our audit scoping must treat the gadget library as in-scope, not as a trusted dependency.
- Upstream continuity (ECC / Zcash Foundation / Shielded Labs / ZODL funding and coordination) through our fork's lifetime.
- Our team's competence in Rust consensus code (calibrated by the Stage 2 control prototype).

## 8. Audit burden

Inherited audits cover only unmodified paths (PLAN.md §2.3). Burden = our deltas (E2/E3/E5) + the wallet path (Zallet is alpha — any wallet we ship needs review at a depth alpha software has not had) + **the gadget layer** (§7) + verification that the Tachyon artifacts cover what we need them to cover (§4). Rev 2 finding: the Tachyon proofs are MIT/Apache-2.0, so a portion of this burden is **reusable rather than repeatable** — if our circuit is Ironwood's circuit unmodified, we inherit the proof, not just the audit report. Any circuit-level delta we introduce voids that inheritance for the touched components, which is a strong argument for a **zero-circuit-delta** posture on this lineage.

## 9. Kill criteria (amended — flagged per discrepancy rule)

- ~~`orchard` BOSL license unobtainable~~ — **resolved, and now confirmed through the Ironwood era** (§5). `[VERIFIED-PRIMARY]` — this kill criterion is closed.
- Upstream maintenance collapse, or churn that our 72h-security-merge posture cannot absorb. **Rev 2 note:** the observed churn rate (three consensus-relevant upgrades in eight weeks, six Zebra releases in five weeks) is itself the evidence to score here — it demonstrates responsiveness *and* sets a demanding floor for what we must track.
- Neither pool option passes the maturity bar TJ/the whitepaper author set (PLAN.md §13 Q4).
- Wallet path unworkable in Phase 0.
- Total delta for hard requirements exceeds the minimal-delta bar of §2.2.
- **New:** the Lean proofs turn out not to be tied to the deployed circuit code in any mechanical way *and* the named assumptions are unacceptable under §2 — which would collapse Ironwood's case back to "one month of production."

## 10. PLAN.md impact (proposed amendments — not applied)

Per the discrepancy rule, PLAN.md is unchanged. Proposed for the amendment pass, pending TJ/the whitepaper author sign-off:

1. **§4.2/§4.5** — Candidate Z's pool description "Orchard, ~4 yrs production" is stale and now demonstrably misleading: Orchard is sealed, and its four years of production coexisted with a counterfeiting bug. Re-score as Ironwood (~1 month, formally verified for balance integrity) vs. Sapling (2018-era, but upstream-restricting per ZIP 219).
2. **§2.2 item 1** — the maturity bar as written ("≥2 yrs battle-tested") would have *passed* Orchard in May 2026 and *failed* Ironwood today, which is backwards on this evidence. Propose adding a second axis: assurance artifacts (formal verification, audit scope, proof reusability) alongside production time.
3. **§7 supply-auditability caveat** — restate using the precise Shielded Labs formulation (§2), not "retroactive audit impossible," and note the turnstile's actual scope.
4. **New** — record the shared-dependency finding: audit scope must include the proof-system gadget libraries, for either candidate.
5. **New** — record the ZIP editorial-lag risk (§3) and the ZIP 2005 forward dependency as costs of the Candidate Z path.

## 11. Safest fallback

Candidate M (Monero-derived), where mandatory privacy and RandomX are inherent — noting the symmetric caveat for M: FCMP++ is not on mainnet either (stressnet-only as of 2026-08; details in E6 §2 "Monero context" and PLAN.md §7). Rev 2 note: the §1 argument about production time as a soundness proxy applies symmetrically to Monero's ring signatures and to FCMP++, and neither has an assurance artifact comparable to Tachyon's. E6 should be re-read with that comparison in mind.

## 12. Open verification tasks

Closed in rev 2:

- [x] Pin the official June 2026 Orchard vulnerability advisory and its scope statement. → §2. Publisher was **Shielded Labs**, not ECC/ZF; no CVE; GHSA-jfw5-j458-pfv6.
- [x] Pin the Ironwood ZIP(s), activation height, turnstile mechanism, formal-verification artifacts and who performed them. → §3, §4.
- [x] Confirm licenses of all Ironwood-era crates we would vendor. → §5. All MIT/Apache-2.0; no separate `ironwood` crate.

Remaining:

- [ ] **Highest value next:** determine whether the Lean formalization is mechanically tied to the deployed Rust circuit, and enumerate the named cryptographic assumptions (read `github.com/zcash/ironwood` and the Clean/ArkLib framing directly, not the blog post). Decides how much Ironwood's assurance story is worth to us. (§4)
- [ ] Read Taylor Hornby's technical work log for the June bug — the best available primary account of how a four-year-old soundness bug was actually found. Directly informs our own review posture. (§2)
- [ ] Confirm Zebra custom-network support covers custom genesis + activation heights + PoW parameters *together*, not just Regtest toggles; pin Zebra's first stable release date and full incident record. (§5)
- [ ] Pin ZIP 2006's text if/when published, and track ZIP 258/229/318/326 from Draft to Final — spec churn is a tracking cost we would inherit. (§3)
- [ ] Determine what a *Sapling-only* fork inherits exactly (proving system, parameters, trusted-setup implications), and read ZIP 219 for upstream's Sapling-restriction intent and timeline. (§6)
- [ ] Zallet maturity re-check at ADR-001 time (alpha → beta trajectory); zingolib as alternative. (§5)
- [ ] NU7/Tachyon roadmap: what consensus changes are scheduled next — especially the post-quantum Recovery Protocol implied by ZIP 2005 — and what tracking them would cost us. (§3)

## 13. Sources

**Primary (read 2026-08-30 unless noted):** zips.z.cash/zip-0257 (NU6.2, Final — root cause, mitigation, activation heights) · zips.z.cash/zip-0258 (NU6.3 deployment, Draft — Ironwood creation and Orchard sealing rules) · zips.z.cash/zip-2005 (Ironwood Quantum Recoverability, Proposed) · zips.z.cash/zip-0318 (Orchard→Ironwood migration, Draft) · zips.z.cash ZIP index (statuses for 229, 2006, 219, 326, 209, 213, 317) · zfnd.org/zebra-4-5-3-and-5-0-0-emergency-soft-fork-and-nu6-2-activation · forum.zcashcommunity.com/t/.../56015 (Shielded Labs disclosure) · tachyon.z.cash/blog/ironwood-verification-complete · forum.zcashcommunity.com/t/.../57007 (Tachyon retroactive grant application) · github.com/zcash/orchard (README, CHANGELOG through 0.15.5) · github.com/zcash/ironwood (README, license) · github.com/ZcashFoundation/zebra releases · z.cash/upgrade/nu6-3 · zcash.github.io/zcash/user/end-of-life.html (2026-08-21) · zcash.github.io/zallet · electriccoin.co CVE-2019-7167 postmortem (linked in PLAN.md §14)

**Secondary (flagged; not load-bearing):** CoinDesk 2026-07-28 (the "$1.7B sealed" figure — press only, never verified against chain data) · ZecHub Ironwood explainer · press coverage of the June price move.

**Note on z.cash/upgrade/nu6-3:** the official upgrade page asserts Ironwood is "Formally verified and independently auditable" but links **no** verification report, artifact, or auditor. The substantiating material is on tachyon.z.cash and in the grant thread. Anyone evaluating this lineage from the official page alone would be taking the central assurance claim on trust — worth remembering when we write our own claims.
