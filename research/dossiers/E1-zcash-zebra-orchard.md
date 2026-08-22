# E1 — Zcash/Zebra lineage viability

**Exploration:** Can Meownero safely derive from the modern Zcash stack (Zebra node + shielded-pool cryptography)? · **Status:** Draft · **Date:** 2026-08-22

## 1. Draft verdict (DRAFT)

The two blockers PLAN.md anticipated have moved in opposite directions. The **license blocker is resolved**: the `orchard` crate was relicensed from BOSL to dual MIT OR Apache-2.0 in v0.7.0 (2024-01-26), explicitly as a "strict relaxation" removing the Zcash/Zebra-only exception. But the **maturity picture changed materially in July 2026**: following the June 2026 Orchard counterfeiting vulnerability, the NU6.3 "Ironwood" upgrade (activated ~2026-07-28) **sealed the Orchard pool** and replaced it with a new Orchard-derived pool, **Ironwood**, which adds a supply-auditability turnstile and formal-verification work — but has only weeks of production history. A Candidate Z fork today therefore chooses between **Ironwood** (current upstream direction, strongest assurance story, near-zero production history) and **Sapling** (in production since 2018, and the pool Pirate Chain has run mandatory-shielded since 2018, but older cryptography). Neither choice is disqualifying; both must be scored honestly against PLAN.md §2.2 item 1. Lineage viability otherwise looks credible: Zebra is the sole maintained node (zcashd reached end-of-life 2026-07-18), and the upstream demonstrated a serious, fast incident response — which is itself positive evidence under §2.2 items 2–3.

**PLAN.md impact:** §4.2/§4.5 describe Candidate Z's pool as "Orchard, ~4 yrs production." That is now stale: Orchard is sealed following a real counterfeiting flaw, and the maturity axis must be re-scored as Ironwood (weeks) vs. Sapling (2018-era, 8 yrs). §7's "supply auditability caveat" should note that Ironwood was *designed* to improve supply auditability — a potential direct win for our disclosure story. Propose amendment after TJ/the whitepaper author review.

## 2. Production precedents & maturity evidence

- Zcash mainnet live since 2016; shielded pools in continuous production since launch (Sprout → Sapling 2018 → Orchard 2022 → Ironwood 2026). `[SECONDARY]` (uncontroversial; pin exact activation heights from zips.z.cash during final pass)
- **zcashd end-of-life:** automatic End-of-Support halt at block 3,417,100 on 2026-07-18; every zcashd 6.20.0 node has shut down; users directed to Zebra (node) / Zallet (wallet). `[VERIFIED-PRIMARY]` — zcash.github.io/zcash/user/end-of-life.html (read 2026-08-21)
- **Orchard relicensing:** orchard CHANGELOG v0.7.0 (2024-01-26): license is now "MIT OR Apache-2.0"; prior BOSL exception "no longer necessary"; change described as a "strict relaxation." `[VERIFIED-PRIMARY]` — github.com/zcash/orchard CHANGELOG.md + README license section (read 2026-08-22)
- **June 2026 Orchard vulnerability:** soundness/counterfeiting flaw in the Orchard circuit disclosed ~2026-06-01; emergency patch; because the pool is shielded, retroactive audit of whether counterfeiting occurred was impossible. `[SECONDARY]` — multiple outlets + Zcash forum; **upgrade to primary via the official ECC/ZF advisory before ADR-001**
- **NU6.3 "Ironwood" (~2026-07-28):** new Ironwood shielded pool (Orchard-style circuit with the flaw fixed); Orchard pool sealed (~$1.7B at sealing per press); migration via supply-audit turnstile; coinbase rule now Sapling and/or Ironwood only, **Orchard coinbase prohibited**; Project Tachyon involved in formal verification. Coinbase rule `[VERIFIED-PRIMARY]` via ZIP-213 current text (read 2026-08-22); the rest `[SECONDARY]` — pin the Ironwood ZIP(s)/spec and formal-verification artifacts.
- **Zebra:** Rust consensus node by Zcash Foundation, dual MIT/Apache-2.0; now the network's sole maintained full node. `[SECONDARY]` for production-history length — pin first-stable-release date and any Zebra-specific incident history.
- **Zallet (wallet):** official zcashd-wallet successor, **alpha** as of July 2026 (Alpha.4; incomplete RPC coverage; breaking changes expected); wallet.dat migration supported. `[VERIFIED-PRIMARY]` — zcash.github.io/zallet + EOL page. **Zebra ships no wallet; on this lineage the wallet is launch-critical path.**
- **Historical incident:** CVE-2019-7167 (Sprout counterfeiting vulnerability, disclosed/remediated 2019) — precedent that this lineage has had, found, and remediated soundness bugs before. `[VERIFIED-PRIMARY]` — ECC postmortem (linked in PLAN.md §14).

## 3. Consensus/crypto delta (lineage adoption itself)

Fork Zebra at a pinned post-NU6.3 tag; re-genesis; network parameters (magic bytes, address HRPs, ports, DNS seeds). Small and mechanical. The load-bearing deltas live in E2 (mandatory privacy), E3 (emission + dev-fund stream removal), E5 (PoW). **Pool choice is the big new decision:** Ironwood-only vs. Sapling-only vs. both — each option changes E2's surface.

## 4. Security assumptions introduced

- Soundness of the chosen pool's circuit as deployed (Ironwood: fresh code + formal verification claims to be validated; Sapling: 8 years of production, but pre-Halo trusted-setup lineage — verify which proving system the current Sapling pool uses post-NU5 and what a Sapling-only fork would actually inherit). `[OPEN]`
- Upstream continuity (ECC / Zcash Foundation / Shielded Labs funding and coordination) through our fork's lifetime.
- Our team's competence in Rust consensus code (calibrated by the Stage 2 control prototype).

## 5. Audit burden

Inherited audits cover only unmodified paths (PLAN.md §2.3). Burden = our deltas (E2/E3/E5) + the wallet path (Zallet is alpha — any wallet we ship on this lineage needs review at a depth alpha software has not yet had) + verification that the Ironwood formal-verification artifacts actually cover what press claims they cover.

## 6. Kill criteria (amended — flagged per discrepancy rule)

- ~~`orchard` BOSL license unobtainable~~ — **resolved favorably** (v0.7.0 relicense) `[VERIFIED-PRIMARY]`; residual: confirm the Ironwood-era crates carry the same licensing. `[OPEN]`
- Upstream maintenance collapse, or churn that our 72h-security-merge posture cannot absorb.
- Neither pool option passes the maturity bar TJ/the whitepaper author set (PLAN.md §13 Q4): Ironwood too young *and* Sapling-only judged an unacceptable regression.
- Wallet path unworkable in Phase 0 (Zallet/zingolib cannot be made to operate shielded-only on a custom network within bounded effort).
- Total delta for hard requirements exceeds the minimal-delta bar of §2.2.

## 7. Safest fallback

Candidate M (Monero-derived), where mandatory privacy and RandomX are inherent — noting the symmetric caveat for M: FCMP++ is not on mainnet either (stressnet-only as of 2026-08; details in E6 §2 "Monero context" and PLAN.md §7).

## 8. Open verification tasks

- [ ] Pin the official June 2026 Orchard vulnerability advisory (ECC/ZF) and its scope statement.
- [ ] Pin the Ironwood ZIP(s)/protocol spec, activation height, turnstile mechanism, and the formal-verification artifacts + who performed them.
- [ ] Confirm licenses of all Ironwood-era crates we would vendor (orchard successor, halo2, librustzcash, Zebra at target tag).
- [ ] Pin Zebra's first stable release date, production-history length, and incident record; confirm configurable custom-network support covers custom genesis, activation heights, and PoW parameters.
- [ ] Zallet maturity re-check at ADR-001 time (alpha → beta trajectory) and zingolib as alternative.
- [ ] NU7/Tachyon roadmap: what consensus changes are scheduled next, and what would tracking them cost us.
- [ ] Determine what a *Sapling-only* fork inherits exactly (proving system, parameters, trusted-setup implications) — required to score the Sapling option honestly.

## 9. Sources

Primary: github.com/zcash/orchard (CHANGELOG.md, README) · zips.z.cash/zip-0213 (current text incl. post-NU6.3 coinbase rule) · zcash.github.io/zcash/user/end-of-life.html · zcash.github.io/zallet · electriccoin.co CVE-2019-7167 postmortem · github.com/ZcashFoundation/zebra
Secondary (to upgrade or accept): Zcash community forum Z3/zcashd-deprecation and ZF engineering-update threads · Galaxy Research and CoinDesk coverage of Ironwood activation and pool sealing (2026-07-28/29) · forum "BOSL or MIT — Orchard" thread (relicensing history context)
