# E1 — Zcash/Zebra lineage viability

**Exploration:** Can Meownero safely derive from the modern Zcash stack (Zebra node + shielded-pool cryptography)? · **Status:** Draft (rev 3) · **Date:** 2026-08-22, revised 2026-08-30 (rev 2 and rev 3)

> **Rev 3 changelog (2026-08-30, second session):** the two highest-value open tasks are closed against primary sources (the Ironwood Book at zcash.github.io/ironwood, and Taylor Hornby's work log PDF). §4 is rewritten: the **model-to-code gap is answered** — the Lean circuit model is hand-written but CI mechanically checks it against verifying-key and layout dumps regenerated from the pinned Orchard release, which is a real (if fixture-mediated) tie to the deployed constraint system. The **named cryptographic assumptions are enumerated** (§4a) and are standard for the Halo 2/IPA setting. One finding cuts the other way: **the headline "balance integrity proven" claim is not end-to-end mechanized** — by the project's own guide, the ledger-layer games are "not yet tied into the Action circuit knowledge soundness proof at all." New §2a records the work log's discovery-methodology findings, which directly shape our review posture. No PLAN.md edits made — see §10.
>
> **Rev 2 changelog (2026-08-30):** Stage 1 open tasks 1–3 closed against primary sources; task 4 partially closed. The June 2026 incident and the NU6.3 upgrade are now `[VERIFIED-PRIMARY]` end-to-end (ZIP 257, ZIP 258, ZIP 2005, ZIP 318, zfnd.org, Project Tachyon). Three findings are new and load-bearing: the root cause was a **shared gadget-library bug, not Orchard-specific code**; **Ironwood ships an unfinished post-quantum roadmap dependency (ZIP 2005)**; and the **NU6.3 ZIPs are still Draft/Proposed/Reserved despite being live on mainnet**. No PLAN.md edits made — see §10.

## 1. Draft verdict (DRAFT)

The two blockers PLAN.md anticipated have moved in opposite directions. The **license blocker is fully resolved and now confirmed through the Ironwood era**: `orchard` is MIT OR Apache-2.0 since v0.7.0 (2024), and the Ironwood-era releases (0.15.x, July–Aug 2026) plus the `zcash/ironwood` proof repo carry the same dual license `[VERIFIED-PRIMARY]`. The **maturity picture is more nuanced than rev 1 recorded**. A Candidate Z fork today chooses between **Ironwood** (live since 2026-07-28, ~1 month of production, but backed by the strongest formal-verification artifact any shielded pool has ever shipped with) and **Sapling** (production since 2018, but the pool upstream is separately moving to restrict — see ZIP 219). Rev 1 framed this as "assurance story vs. production history"; the evidence now shows that framing is too clean, in both directions:

- **Against Ironwood's youth:** the verification is real, public, and unusually thorough (2,700+ Lean theorems, two independent firms, published sources under MIT/Apache-2.0). It is materially better evidence than "N years without a known incident" — which is exactly what Orchard had for four years while carrying a counterfeiting bug.
- **Against over-crediting it:** Project Tachyon's own scope statement excludes implementation bugs and assumes the named cryptographic assumptions hold. **Rev 3 sharpens this:** the circuit knowledge-soundness proof is mechanically tied to the deployed constraint system (via pinned verifying-key/layout equality checks, §4), which is much better than a paper model — but the ledger-layer balance-integrity games are **not yet composed with** that circuit proof, byte-level encodings are explicitly out of scope (a historically buggy area upstream admits to), and the fixtures anchoring the tie were produced by unpublished one-off instrumentation. The honest summary is "the strongest assurance artifact in the field, with a documented composition gap" — not "balance integrity proven end-to-end." And Ironwood carries a **forward dependency we would inherit**: ZIP 2005 restructures note commitments for a future "Recovery Protocol" whose post-quantum proof system **has not been selected yet**. Adopting Ironwood means adopting an unfinished roadmap, not a finished pool.

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
  - **Rev 3 addition (work log):** Hornby did attempt *statistical* detection — analyzing Orchard transaction arity over the exposure window since Opus 4.8's release. Results were "inconclusive due to the normal high variance in shielded activity" (an arity-4 anomaly matched a similar anomaly a month prior). So the non-cryptographic detection avenue was actually tried, and it also could not settle the question. `[VERIFIED-PRIMARY]`
- **Advisories:** GHSA-jfw5-j458-pfv6 (Zebra, Critical). Separately GHSA-2x4w-pxqw-58v9 (`orchard`: authorized bundle/PCZT could carry a `zkproof` padded with arbitrary trailing data), fixed in the same 0.14.0 release. No CVE and no single consolidated ECC postmortem was located; the authoritative written record is distributed across ZIP 257, the ZF release post, and the Shielded Labs forum disclosure. **Correction to rev 1:** the disclosure post is by **Shielded Labs**, not ECC/ZF — rev 1's open task named the wrong publisher.
- Taylor Hornby's full technical work log is linked (twice) from the Shielded Labs disclosure post as a Google Drive PDF ("Orchard Security Bug", 6 pp.). **Read in full 2026-08-30 → §2a.** `[VERIFIED-PRIMARY]`

## 2a. The Hornby work log — how a four-year-old soundness bug was actually found

All `[VERIFIED-PRIMARY]` — the work log PDF itself, read in full 2026-08-30. This is the best primary account we will get of the failure mode our §2.2 doctrine exists to defend against, and it carries direct lessons for our own review posture.

**Precise mechanics (confirms and sharpens ZIP 257):** the bug is two `assign_advice()` calls that should have been `copy_advice()` in `halo2_gadgets/src/ecc/chip/mul/incomplete.rs` (L309–310) — the double-and-add loop's incomplete-addition stage witnesses the base point without any constraint binding it to the *actual* base. An internal-consistency gate (`q_mul_2`) forces the witnessed base values to equal *each other* across the loop, but nothing ties them to the real `g_d`. A malicious prover can therefore choose the base freely, solve algebraically for the base that makes `pk_d = [ivk]g_d` "check out" for arbitrary `(pk_d, ivk, g_d)`, supply a wrong nullifier key `nk`, and reveal a fresh, valid-looking nullifier for the same note on every spend — unbounded doubling, bounded only by the turnstiles. The fix constrains only the loop's *first* iteration (`copy_advice`), letting the existing `q_mul_2` gate propagate correctness. **Review lesson: the dangerous pattern is a witness assigned but never bound — an audit checklist item that is mechanically enumerable** (grep every `assign_advice()` and ask "can this deviate from the honest assignment without violating any constraint?"). Hornby ran exactly that enumeration over the fixed circuit with AI assistance and found nothing further.

**Discovery economics — the finding that matters most to our doctrine:**

- The bug was found by an automated agent audit (`zcash-full-stack-auditor`, Opus 4.8 at max effort) **one day after the model's release**. Timeline: audit initialized May 28 (release day), audit phase started ~2 pm May 29, critical finding ~6 pm, reported to ZODL (Daira-Emma Hopwood, Kris Nuttycombe) over Signal 11:53 pm MDT, working PoC against the real circuit by 2:06 am, full regtest RPC test (doubling one note past 10M ZEC) in ~6 hours more.
- **The same framework with the previous model (Opus 4.7 xhigh) had audited the same circuit before and did *not* find the bug.** Hornby later confirmed 4.7-xhigh *could* find it, but only under a very specific prompt ("Audit the variable base scalar mul gadget for any missing constraints…"); under a generic prompt, even Opus 4.8 found it in only **1 of 4** runs. He flags his own trials as "not scientific-quality data."
- **A plausible differentiator:** the successful run fed the **halo2 book** into the initialization stage, where prior runs used only the protocol spec / ZIPs. Feeding the auditor the implementation's own design docs may have been decisive.
- **The model resisted its own finding** — "extremely skeptical that it had found a real bug, thinking that the upstream code has been audited and so it must be correct" — and needed human prodding to take it seriously.
- **End-to-end effort was small:** ~6 hours for the full RPC-level PoC with minimal Zcash-specific guidance; the model derived the exploit algebra unaided.

**Implications for Meownero's review doctrine (feeds PLAN.md §2.3 and E1 §8/§10):**

1. Treat AI-assisted soundness auditing of the *entire* inherited gadget stack as a launch-blocking control, not an optional extra — the bug that mattered lived below the pool-specific code.
2. A single generic pass is insufficient: run **targeted, gadget-by-gadget** prompts and **multiple trials per target** (the 1-in-4 hit rate means one run proves nothing), and feed the auditor the *implementation's* design docs, not only the spec.
3. Budget for a human keeping low-signal-but-real findings alive against model skepticism.
4. Adopt Hornby's own standing recommendation verbatim: "Balance integrity violation audits should be performed immediately upon the public release of any new AI models." A cheap, high-value standing control.

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

**Rev 3 — the model-to-code gap is now answered `[VERIFIED-PRIMARY]`** (the Ironwood Book, zcash.github.io/ironwood, incl. the Formal Verification / CI-checks and "Guide to the Ironwood Formalization" chapters; read 2026-08-30):

- **The Lean circuit model is hand-written, not extracted from Rust.** The development formalizes the Halo 2 *verifier* logic; it does not formalize the prover or the constraint-system *generation*. So there is no compile-time or extraction-based equivalence between the Lean model and the Rust source.
- **But it is not a free-floating paper model either — CI mechanically pins it to the deployed circuit's artifacts.** A `CircuitCheck` step compares "the pinned verifying-key and layout dumps against the Lean circuit model," and a fixture-regeneration step "clones the pinned Orchard release, asserts the tag and its published lockfile checksums, regenerates every capture family … and diffs each committed artifact" against recorded SHA-256 digests. A verifier-fingerprint check confirms "Lean's assembled sum is identical to the Rust verifier's — **for the captured proofs in the repository, not for the verifier in general**." So the tie is real but **fixture-mediated**: it binds the Lean model to specific dumps/verifying-keys of a pinned Orchard release, not to the Rust source in general.
- **Two documented weaknesses in that tie, both quotable:** (1) the CS and layout dumps behind `CircuitCheck` "were emitted by one-off instrumentation of halo2/orchard that **was never published**" — the anchoring fixtures rest on unpublished tooling plus review; (2) the fingerprint equivalence holds only for the captured proofs, not the verifier in general. `native_decide`-style checks also carry a compiler-trust axiom.
- **The composition gap is the biggest caveat, and it undercuts the headline claim.** By the project's own guide: "the remaining significant gap is that ledger security arguments are **not yet tied into the Action circuit knowledge soundness proof at all**: the games state their circuit premiss over their own abstract types, and no definition is currently shared between the two developments." Spendability / spend-authority are "not yet finished." So "balance integrity proven" is really "circuit knowledge-soundness proven (and pinned to the deployed circuit's dumps) **and, separately**, a ledger balance model proven — with the two not yet composed." The public messaging ("undetectable counterfeiting bugs do not exist in Ironwood") runs ahead of the mechanized artifact.
- **On the uncomfortable adjacency (June bug vs. verified boundary):** the missing-copy-constraint class is exactly what `CircuitCheck`'s verifying-key/layout equality would now catch *if* the deployed circuit's dumps disagreed with the Lean model — i.e. this specific failure mode is inside the pinned boundary going forward. But the book is explicit that **byte-level encodings are out of scope** ("a potentially significant category of gap, because Zcash implementations have had quite a few significant security bugs due to unintentionally non-canonical encodings") and that the **prover and the custom-gate/gadget correctness are assumed**, not proven. The gadget layer is not blanket-verified; it is pinned by fixture.

## 4a. Named cryptographic assumptions (enumerated) `[VERIFIED-PRIMARY]`

From the Ironwood Book (read 2026-08-30). The proofs reduce to a standard, conservative set for the Halo 2 / inner-product-argument setting — no exotic or novel assumptions, which is favorable under PLAN.md §2:

1. **Discrete-log hardness on Pallas and Vesta** (for algebraic adversaries) — Vesta carries verifier knowledge-soundness; Pallas carries the Action circuit and ledger properties.
2. **Random-oracle model** — BLAKE2b, hash-to-field, and public-point-list derivation modeled as ideal random oracles.
3. **Algebraic-group-model adversary** — adversaries must declare, for every group element output, a recipe from given elements (built into the adversary type, not a hypothesis).
4. **Independence of fixed bases via group-hash indifferentiability** — soundness is proved for randomly sampled bases; the deployed uniform reference string inherits it through a proof that the deployed hash-to-curve is indifferentiable from a random oracle onto the group.
5. **Encoding-independence** — attacks assumed not to depend on specific byte encodings (this is *why* byte-level encoding bugs sit outside the verified boundary).

> **One caveat worth flagging for §2/§5 (PoW):** assumption 4 notes an adversary "has the protocol's entire lifetime to attack that one specific reference string," and "one discrete-log computation is sufficient to break binding/knowledge-soundness properties for the **entire** protocol." This is inherent to the fixed-URS design and not specific to Ironwood, but it is the kind of amortized-attack surface our own security doctrine should acknowledge explicitly rather than inherit silently.

> **Net assessment for §2.2.** This remains the strongest assurance artifact on either candidate lineage, and it is reusable (MIT/Apache-2.0). Rev 3 credits it *more* on the model-to-code axis than rev 2 feared (there is a real, CI-enforced tie to the deployed circuit's verifying key/layout, and the assumptions are standard and conservative) and *less* on the headline-claim axis (the ledger↔circuit composition is not done, the anchoring fixtures use unpublished tooling, and encodings/prover/gadget-correctness are out of scope). For a **zero-circuit-delta** Candidate Z posture we would inherit the circuit-soundness proof at close to full value; any circuit-level delta voids the inheritance for touched components and re-opens the gadget-audit burden of §2a/§8.

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

- Soundness of the chosen pool's circuit as deployed. For Ironwood this is now backed by a public Lean **circuit knowledge-soundness** proof that is CI-pinned to the deployed circuit's verifying-key/layout dumps (§4) — stronger than rev 2 assumed on the model-to-code axis — but with a documented **ledger↔circuit composition gap** and standard-but-load-bearing crypto assumptions (§4a). For Sapling: 8 years of production, but pre-Halo trusted-setup lineage — which proving system the current Sapling pool uses post-NU5, and what a Sapling-only fork actually inherits, remains `[OPEN]`.
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
- ~~**New:** the Lean proofs turn out not to be tied to the deployed circuit code in any mechanical way *and* the named assumptions are unacceptable under §2~~ — **partially retired in rev 3.** The proofs *are* mechanically tied (CI-pinned to the deployed circuit's verifying-key/layout, §4) and the assumptions *are* standard and acceptable (§4a). The residual kill-adjacent risk is narrower: the **ledger↔circuit composition gap** never closes upstream, leaving "balance integrity" un-mechanized end-to-end — track it, but on current evidence it does not collapse Ironwood's case.

## 10. PLAN.md impact (proposed amendments — not applied)

Per the discrepancy rule, PLAN.md is unchanged. Proposed for the amendment pass, pending TJ/the whitepaper author sign-off:

1. **§4.2/§4.5** — Candidate Z's pool description "Orchard, ~4 yrs production" is stale and now demonstrably misleading: Orchard is sealed, and its four years of production coexisted with a counterfeiting bug. Re-score as Ironwood (~1 month, formally verified for balance integrity) vs. Sapling (2018-era, but upstream-restricting per ZIP 219).
2. **§2.2 item 1** — the maturity bar as written ("≥2 yrs battle-tested") would have *passed* Orchard in May 2026 and *failed* Ironwood today, which is backwards on this evidence. Propose adding a second axis: assurance artifacts (formal verification, audit scope, proof reusability) alongside production time. **Rev 3 refinement:** when scoring an assurance artifact, credit *what is actually mechanized* — Ironwood's circuit-soundness proof is CI-pinned to the deployed circuit (score it high) but its end-to-end "balance integrity" claim is not yet composed (do not score the headline claim at face value). §4/§4a give the exact boundary.
3. **§7 supply-auditability caveat** — restate using the precise Shielded Labs formulation (§2), not "retroactive audit impossible," and note the turnstile's actual scope.
4. **New** — record the shared-dependency finding: audit scope must include the proof-system gadget libraries, for either candidate.
5. **New** — record the ZIP editorial-lag risk (§3) and the ZIP 2005 forward dependency as costs of the Candidate Z path.
6. **New (rev 3) — §2.3 review doctrine.** Adopt the four gadget-audit controls in §2a as launch-blocking: full-stack AI-assisted soundness audit of the inherited gadget layer (not just pool code); targeted, multi-trial, design-doc-fed prompting rather than a single generic pass; a human retained to defend low-signal-but-real findings against model skepticism; and re-run balance-integrity audits on each major new AI-model release (Hornby's own standing recommendation).

## 11. Safest fallback

Candidate M (Monero-derived), where mandatory privacy and RandomX are inherent — noting the symmetric caveat for M: FCMP++ is not on mainnet either (stressnet-only as of 2026-08; details in E6 §2 "Monero context" and PLAN.md §7). Rev 2 note: the §1 argument about production time as a soundness proxy applies symmetrically to Monero's ring signatures and to FCMP++, and neither has an assurance artifact comparable to Tachyon's. E6 should be re-read with that comparison in mind.

## 12. Open verification tasks

Closed in rev 2:

- [x] Pin the official June 2026 Orchard vulnerability advisory and its scope statement. → §2. Publisher was **Shielded Labs**, not ECC/ZF; no CVE; GHSA-jfw5-j458-pfv6.
- [x] Pin the Ironwood ZIP(s), activation height, turnstile mechanism, formal-verification artifacts and who performed them. → §3, §4.
- [x] Confirm licenses of all Ironwood-era crates we would vendor. → §5. All MIT/Apache-2.0; no separate `ironwood` crate.

Closed in rev 3:

- [x] **Model-to-code gap.** → §4. Lean model is hand-written (verifier logic; not extracted, prover not formalized) but CI mechanically pins it to the deployed circuit's verifying-key/layout dumps regenerated from a pinned Orchard release. Tie is real but fixture-mediated (anchoring dumps from unpublished instrumentation) and the **ledger↔circuit composition is not yet done** — so "balance integrity" is not end-to-end mechanized.
- [x] **Named cryptographic assumptions.** → §4a. DL on Pallas/Vesta, ROM, algebraic-group-model, fixed-base independence via group-hash indifferentiability, encoding-independence. Standard and conservative; acceptable under §2.
- [x] **Hornby work log read in full.** → §2a. Precise root cause (`assign_advice`→`copy_advice`, incomplete.rs L309–310); discovery economics (found 1 day post-model-release; 1-in-4 generic-prompt hit rate; model self-skepticism). Yields four review-doctrine controls.

Remaining:

- [ ] Confirm Zebra custom-network support covers custom genesis + activation heights + PoW parameters *together*, not just Regtest toggles; pin Zebra's first stable release date and full incident record. (§5)
- [ ] Pin ZIP 2006's text if/when published, and track ZIP 258/229/318/326 from Draft to Final — spec churn is a tracking cost we would inherit. (§3)
- [ ] Determine what a *Sapling-only* fork inherits exactly (proving system, parameters, trusted-setup implications), and read ZIP 219 for upstream's Sapling-restriction intent and timeline. (§6)
- [ ] Zallet maturity re-check at ADR-001 time (alpha → beta trajectory); zingolib as alternative. (§5)
- [ ] NU7/Tachyon roadmap: what consensus changes are scheduled next — especially the post-quantum Recovery Protocol implied by ZIP 2005 — and what tracking them would cost us. (§3)

## 13. Sources

**Primary (read 2026-08-30 unless noted):** zips.z.cash/zip-0257 (NU6.2, Final — root cause, mitigation, activation heights) · zips.z.cash/zip-0258 (NU6.3 deployment, Draft — Ironwood creation and Orchard sealing rules) · zips.z.cash/zip-2005 (Ironwood Quantum Recoverability, Proposed) · zips.z.cash/zip-0318 (Orchard→Ironwood migration, Draft) · zips.z.cash ZIP index (statuses for 229, 2006, 219, 326, 209, 213, 317) · zfnd.org/zebra-4-5-3-and-5-0-0-emergency-soft-fork-and-nu6-2-activation · shieldedlabs.net/the-orchard-counterfeiting-vulnerability (Shielded Labs disclosure) · **Taylor Hornby, "Orchard Security Bug" work log** (Google Drive PDF, 6 pp., linked from the disclosure — root cause, exploit, discovery methodology, mitigations; read in full) · **zcash.github.io/ironwood (the Ironwood Book)** — Concepts, Quantum-recoverability, Formal Verification / CI-checks, and "Guide to the Ironwood Formalization" (scope, assumptions, model-to-code tie) · tachyon.z.cash/blog/ironwood-verification-complete · forum.zcashcommunity.com/t/.../57007 (Tachyon retroactive grant application) · github.com/zcash/orchard (README, CHANGELOG through 0.15.5) · github.com/zcash/ironwood (README, license — Lean 4 over Mathlib, dual MIT/Apache-2.0) · github.com/ZcashFoundation/zebra releases · z.cash/upgrade/nu6-3 · zcash.github.io/zcash/user/end-of-life.html (2026-08-21) · zcash.github.io/zallet · electriccoin.co CVE-2019-7167 postmortem (linked in PLAN.md §14)

**Secondary (flagged; not load-bearing):** CoinDesk 2026-07-28 (the "$1.7B sealed" figure — press only, never verified against chain data) · ZecHub Ironwood explainer · press coverage of the June price move.

**Note on z.cash/upgrade/nu6-3:** the official upgrade page asserts Ironwood is "Formally verified and independently auditable" but links **no** verification report, artifact, or auditor. The substantiating material is on tachyon.z.cash and in the grant thread. Anyone evaluating this lineage from the official page alone would be taking the central assurance claim on trust — worth remembering when we write our own claims.
