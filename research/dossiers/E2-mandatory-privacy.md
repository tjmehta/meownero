# E2 — Mandatory privacy: mechanism

**Exploration:** Which mechanism enforces "no transparent transactions, ever" (hard requirement §1.1 #3) without material security risk? · **Status:** Rev 2 draft · **Date:** 2026-09-03

## 1. Draft verdict (DRAFT)

Three mechanisms, in descending order of precedent strength. **(a) Monero-inherent** (Candidate M): mandatory by construction since 2014 — zero delta, strongest precedent. **(b) Pirate-style Sapling-only** (Candidate Z on the Sapling pool): production-enforced since 2018 on Pirate Chain. Current Pirate consensus code hard-enables `-ac_private=1`; non-coinbase transparent outputs are rejected except for explicit notary outputs, and a spend containing shielded inputs is rejected if it also creates a non-notary transparent output. **(c) Ironwood-only rule** (Candidate Z on the current-generation pool): no live production precedent as of this revision, but it is no longer merely hypothetical. Pirate v6.0.0 contains Ironwood transaction support while retaining the `ac_private` rule, with mainnet activation scheduled for 2026-10-03. That is implementation evidence, not maturity evidence. ZIP-213 also permits fully shielded coinbase, so Meownero need not inherit Pirate's transparent coinbase/notary exceptions. The product requirement is achievable on either candidate; what differs is how much unproven surface each mechanism adds.

**PLAN.md impact:** §5 E2 assumed the Z-mechanism targets "Orchard"; post-NU6.3 the real options are Ironwood-only or Sapling-only (see E1). The Pirate precedent is stronger than PLAN.md assumed: the enforcement path is pinned in code, and Pirate has now carried the rule into an Ironwood-capable release. It still runs on a zcashd-era Komodo lineage rather than Zebra, so it transfers as a design and implementation precedent, not a reusable code path. Do not amend PLAN.md until TJ/the whitepaper author approve the discrepancy pass.

## 2. Production precedents & maturity evidence

- **Monero:** every transaction private by construction since 2014; ~12 years securing a top-tier coin. `[VERIFIED-PRIMARY]` (uncontroversial; getmonero.org)
- **Pirate Chain (ARRR), 2018–present:** Komodo-derived private assetchain. Pirate's official whitepaper v3 (2022-03-01) says coinbase is transparent for supply auditability and every later P2P transaction must be shielded. Current source at commit `b9b8b4cfe63e48a251c86946d53a223e9aa124e4` hard-enables `-ac_private=1` in `src/komodo_utils.cpp`; `CheckTransactionWithoutProofVerification` in `src/main.cpp` rejects non-notary transparent outputs and rejects shielded spends that create them. The notary exception is explicit in `src/komodo_notary.cpp`. `[VERIFIED-PRIMARY]`
- **Pirate Ironwood transition:** current v6.0.0 release notes and source add Ironwood transactions while retaining the same private-chain checks; activation is scheduled for 2026-10-03. This proves an implementation exists but, as of 2026-09-03, contributes zero incident-free mainnet history. `[VERIFIED-PRIMARY]`
- **Pirate incident record:** no publicly documented 51% double-spend, inflation bug, or consensus break since 2018 launch; relies on Komodo dPoW (notarization to KMD/LTC) for reorg resistance. `[SECONDARY]` — absence-of-evidence caveat applies; check Komodo security advisories for assetchain-relevant issues.
- **Shielded coinbase:** ZIP-213 — coinbase MAY contain shielded outputs (Sapling since Heartwood; Orchard from NU5; **post-NU6.3: Sapling and/or Ironwood, Orchard prohibited**); transparent coinbase also still permitted upstream; no consensus-level maturity rule for shielded coinbase (wallets impose de-facto ~3-block maturity via anchor selection). `[VERIFIED-PRIMARY]` — zips.z.cash/zip-0213 (read 2026-08-22)
- **Ironwood-only enforcement:** not yet live on any chain found in this pass. Pirate's scheduled activation is the first concrete implementation evidence located. Re-check after 2026-10-03 and track its mainnet incident history. `[VERIFIED-PRIMARY for Pirate schedule; negative result elsewhere]`

## 3. Consensus/crypto delta

- **Candidate M:** zero.
- **Candidate Z:** consensus rule requiring (i) empty transparent input/output bundles for all transactions, (ii) coinbase paid directly to shielded outputs per ZIP-213 (no Pirate-style transparent-coinbase exception needed), (iii) removal/disabling of transparent mempool acceptance, RPC, and address surface. Pool-scoping decision from E1 (Ironwood-only vs. Sapling-only) sets which bundles must be non-empty. No new cryptography — but a new *rule* with no deployment history if Ironwood-scoped; partially precedented (by analogy) if Sapling-scoped.

## 4. Security assumptions introduced (Z mechanism)

- The rule must not disturb value-balance accounting across pools or turnstile logic (now load-bearing upstream for Orchard→Ironwood migration). Zcash's protocol defines the remainder of the transparent transaction value pool as the miner fee. With no transparent inputs or outputs, the public Sapling/Ironwood value-balance field therefore exposes the fee while addresses, note values, and transferred amount remain shielded. The rule must preserve this accounting exactly. `[VERIFIED-PRIMARY]`
- **All-shielded mempool DoS economics:** every transaction carries heavy proof verification; upstream Zcash was designed assuming a cheap transparent majority. Needs adversarial analysis (proof-verification cost per byte, mempool admission policy), not assumption. `[OPEN]`
- If Sapling-scoped: assumption that a Sapling-only chain's proving/parameter inheritance is acceptable (see E1 open task).

## 5. Audit burden

The rule plus every path whose invariants it touches: value balance, coinbase handling, mempool policy, RPC surface. Plus the wallet's shielded-only operation (interacts with E1's Zallet-alpha finding). On Candidate M: zero incremental burden for this requirement.

## 6. Kill criteria (unchanged from PLAN.md §5 E2)

For the Z mechanism only: unbounded patch surface, or indication the rule perturbs audited invariants in ways review cannot bound. The *product requirement* is never dropped — only the risky mechanism is.

## 7. Safest fallback

Candidate M, where the property is inherent.

## 8. Open verification tasks

- [x] Pin Pirate whitepaper v3 + Pirate Code v2 PDFs and locate the enforcing `ac_private` consensus code in current Pirate source.
- [ ] Complete the Komodo/Pirate incident audit. GitHub advisory lists are empty, but absence of advisories is not evidence of absence; the 2019 Agama wallet supply-chain incident and Komodo v0.9.2-2 remote memory-safety fixes are relevant inherited-stack warnings, not evidence that Pirate's privacy consensus rule failed.
- [x] Confirm fee visibility and value-balance semantics: fee is public through the shielded pool's value-balance contribution; sender, receiver, and note values remain shielded.
- [ ] Re-check Pirate's Ironwood activation after 2026-10-03 and record any consensus/privacy incidents before treating it as production precedent.
- [ ] Draft the all-shielded mempool DoS analysis plan (verification cost benchmarks belong to Stage 2).
- [ ] Decide pool scoping jointly with E1 (Ironwood-only vs. Sapling-only) — this dossier's delta estimate depends on it.

## 9. Sources

Primary:

- Zcash protocol specification: https://zips.z.cash/protocol/protocol.pdf (`Transactions and Treestates`; Sapling and Orchard/Ironwood balance sections)
- ZIP-213 shielded coinbase: https://zips.z.cash/zip-0213
- Pirate whitepaper v3: https://piratechain.com/wp-content/uploads/Pirate_Chain_White_Paper_v3.pdf (SHA-256 `08e068b6155e2764d49a6a94bf17041b57d9211741f6e1f61bf186d7aeee3e23`)
- Pirate Code v2: https://piratechain.com/wp-content/uploads/The_Pirate_Code_V2.0.pdf
- Pirate private-chain initialization: https://github.com/PirateNetwork/pirate/blob/b9b8b4cfe63e48a251c86946d53a223e9aa124e4/src/komodo_utils.cpp#L1058-L1062
- Pirate consensus enforcement: https://github.com/PirateNetwork/pirate/blob/b9b8b4cfe63e48a251c86946d53a223e9aa124e4/src/main.cpp#L1612-L1875
- Pirate notary exception: https://github.com/PirateNetwork/pirate/blob/b9b8b4cfe63e48a251c86946d53a223e9aa124e4/src/komodo_notary.cpp#L102-L130
- Pirate v6.0.0 Ironwood release notes: https://github.com/PirateNetwork/pirate/blob/b9b8b4cfe63e48a251c86946d53a223e9aa124e4/doc/release-notes/release-notes-6.0.0.md
- getmonero.org design documentation
