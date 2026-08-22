# E2 — Mandatory privacy: mechanism

**Exploration:** Which mechanism enforces "no transparent transactions, ever" (hard requirement §1.1 #3) without material security risk? · **Status:** Draft · **Date:** 2026-08-22

## 1. Draft verdict (DRAFT)

Three mechanisms, in descending order of precedent strength. **(a) Monero-inherent** (Candidate M): mandatory by construction since 2014 — zero delta, strongest precedent. **(b) Pirate-style Sapling-only** (Candidate Z on the Sapling pool): production-enforced since 2018 on Pirate Chain, with a now-documented mechanism — transparent activity is consensus-restricted to coinbase (and Pirate's dPoW notarizations, which we would not have), and the **first spend of any coinbase must go to a shielded address**; all other transparent outputs invalidate the block. **(c) Orchard/Ironwood-only rule** (Candidate Z on the current-generation pool): **no production precedent anywhere** — this would be a new consensus rule and PLAN.md §2 applies with full force. A significant new fact softens (c): ZIP-213 permits fully shielded coinbase (Sapling since Heartwood 2020; Ironwood post-NU6.3), so a modern mandatory-shielded chain would *not* need Pirate's transparent-coinbase carve-out — the rule can be simpler and stricter than Pirate's. The product requirement is achievable on either candidate; what differs is how much unproven surface each mechanism adds.

**PLAN.md impact:** §5 E2 assumed the Z-mechanism targets "Orchard"; post-NU6.3 the real options are Ironwood-only or Sapling-only (see E1). The Pirate precedent is stronger than PLAN.md assumed (mechanism now documented, no public consensus incidents since 2018) — but it is Sapling-specific and runs on zcashd-era Komodo code, not Zebra, so it transfers as a *design* precedent, not a code path.

## 2. Production precedents & maturity evidence

- **Monero:** every transaction private by construction since 2014; ~12 years securing a top-tier coin. `[VERIFIED-PRIMARY]` (uncontroversial; getmonero.org)
- **Pirate Chain (ARRR), 2018–present:** Komodo assetchain configured z-only. Mechanism per the Pirate whitepaper v3 and "Pirate Code" docs: all coinbase rewards are transparent; the **first spend of a coinbase reward must be to a shielded (Sapling) address**; dPoW notarization transactions are transparent by exception; all other transparent P2P transactions are consensus-invalid. `[SECONDARY→PRIMARY]` — sourced from piratechain.com's own whitepaper PDFs via search synthesis; pin the exact PDFs + the enforcing code path (`ac_private` in Komodo daemon) before ADR-001.
- **Pirate incident record:** no publicly documented 51% double-spend, inflation bug, or consensus break since 2018 launch; relies on Komodo dPoW (notarization to KMD/LTC) for reorg resistance. `[SECONDARY]` — absence-of-evidence caveat applies; check Komodo security advisories for assetchain-relevant issues.
- **Shielded coinbase:** ZIP-213 — coinbase MAY contain shielded outputs (Sapling since Heartwood; Orchard from NU5; **post-NU6.3: Sapling and/or Ironwood, Orchard prohibited**); transparent coinbase also still permitted upstream; no consensus-level maturity rule for shielded coinbase (wallets impose de-facto ~3-block maturity via anchor selection). `[VERIFIED-PRIMARY]` — zips.z.cash/zip-0213 (read 2026-08-22)
- **Orchard/Ironwood-only enforcement:** no chain has ever enforced it. `[VERIFIED-PRIMARY as a negative result]` — no precedent surfaced across Phase 0 searches; treat as confirmed-absent unless someone produces one.

## 3. Consensus/crypto delta

- **Candidate M:** zero.
- **Candidate Z:** consensus rule requiring (i) empty transparent input/output bundles for all transactions, (ii) coinbase paid directly to shielded outputs per ZIP-213 (no Pirate-style transparent-coinbase exception needed), (iii) removal/disabling of transparent mempool acceptance, RPC, and address surface. Pool-scoping decision from E1 (Ironwood-only vs. Sapling-only) sets which bundles must be non-empty. No new cryptography — but a new *rule* with no deployment history if Ironwood-scoped; partially precedented (by analogy) if Sapling-scoped.

## 4. Security assumptions introduced (Z mechanism)

- The rule must not disturb value-balance accounting across pools, turnstile logic (now load-bearing upstream for Orchard→Ironwood migration), or fee semantics (fees are revealed via value balance — confirm exact visibility on an all-shielded chain). `[OPEN]`
- **All-shielded mempool DoS economics:** every transaction carries heavy proof verification; upstream Zcash was designed assuming a cheap transparent majority. Needs adversarial analysis (proof-verification cost per byte, mempool admission policy), not assumption. `[OPEN]`
- If Sapling-scoped: assumption that a Sapling-only chain's proving/parameter inheritance is acceptable (see E1 open task).

## 5. Audit burden

The rule plus every path whose invariants it touches: value balance, coinbase handling, mempool policy, RPC surface. Plus the wallet's shielded-only operation (interacts with E1's Zallet-alpha finding). On Candidate M: zero incremental burden for this requirement.

## 6. Kill criteria (unchanged from PLAN.md §5 E2)

For the Z mechanism only: unbounded patch surface, or indication the rule perturbs audited invariants in ways review cannot bound. The *product requirement* is never dropped — only the risky mechanism is.

## 7. Safest fallback

Candidate M, where the property is inherent.

## 8. Open verification tasks

- [ ] Pin Pirate whitepaper v3 + Pirate Code PDFs and locate the actual enforcing consensus code (`ac_private` handling in the Komodo/PirateChain daemon repo).
- [ ] Check Komodo/Pirate security advisories 2018–2026 for assetchain consensus incidents.
- [ ] Confirm fee visibility and value-balance semantics for a 100%-shielded chain (what does an observer see per tx?).
- [ ] Draft the all-shielded mempool DoS analysis plan (verification cost benchmarks belong to Stage 2).
- [ ] Decide pool scoping jointly with E1 (Ironwood-only vs. Sapling-only) — this dossier's delta estimate depends on it.

## 9. Sources

Primary: zips.z.cash/zip-0213 · getmonero.org (design docs)
Secondary (to upgrade): piratechain.com Pirate_Chain_White_Paper_v3.pdf + The_Pirate_Code_V2.0.pdf · komodoplatform.com assetchain parameter docs (`ac_private`, `ac_public`) · Pirate integration guide (MrMLynch gist) · iq.wiki/piratechain
