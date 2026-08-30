# Phase 0 evidence dossiers (Stage 1)

**Status:** Drafts · **Date:** 2026-08-22 · Governed by `PLAN.md` §5 (evidence-first program) and §2 (security acceptance framework).

One dossier per exploration E1–E6. Dossiers establish *what has already been done safely by others*, from primary sources, before anything is prototyped. A dossier is an input to ADR-001, never a decision by itself.

## Template (every dossier, in order)

1. **Draft verdict** — one paragraph, marked DRAFT until TJ/the whitepaper author review.
2. **Production precedents & maturity evidence** — dates, value secured, incident record.
3. **Consensus/crypto delta** — per candidate lineage (M = Monero-derived, Z = Zcash/Zebra-derived) where applicable.
4. **Security assumptions introduced**
5. **Audit burden**
6. **Kill criteria** — from PLAN.md §5; amendments flagged, never silent.
7. **Safest fallback**
8. **Open verification tasks** — checklist to complete Stage 1.
9. **Sources** — primary first; secondary flagged.

## Evidence tagging

Every load-bearing claim carries one of:

- `[VERIFIED-PRIMARY]` — read directly from a primary source (spec, changelog, repo, official advisory) this Phase 0.
- `[SECONDARY]` — from aggregators, press, or search synthesis; acceptable only if TJ/the whitepaper author explicitly accept it, otherwise it must be upgraded before ADR-001.
- `[OPEN]` — not yet verified; listed in the dossier's open-tasks section.

## PLAN.md discrepancy rule

Where evidence contradicts PLAN.md, the dossier carries a **PLAN.md impact** note. PLAN.md is amended only as a separate, explicit commit after TJ/the whitepaper author sign-off — dossiers never silently rewrite the plan.

## Status table

| Dossier | Subject | State | Headline finding |
|---|---|---|---|
| [E1](E1-zcash-zebra-orchard.md) | Zcash/Zebra lineage viability | **Rev 2 (2026-08-30)** | Licensing closed as a blocker (MIT/Apache-2.0 through the Ironwood era). Root cause of the June 2026 counterfeiting bug was a **shared `halo2_gadgets` flaw, not Orchard-specific code** — four years in production did not surface it. Ironwood is ~1 month old but ships a public 2,700-theorem Lean proof of balance integrity (reusable, MIT/Apache-2.0); it also carries an **unfinished post-quantum dependency (ZIP 2005)**, and the NU6.3 ZIPs are still Draft/Proposed/Reserved while live on mainnet |
| [E2](E2-mandatory-privacy.md) | Mandatory-privacy mechanism | Drafted | Pirate's enforcement mechanism documented (Sapling-only + transparent coinbase forced to shield); no precedent for an Orchard/Ironwood-only rule |
| [E3](E3-linear-emission.md) | Linear fair emission | Drafted | Best-evidenced exploration: Dogecoin flat emission since 2015, Monero tail since 2022 |
| [E4](E4-bitcoin-interop.md) | Bitcoin interop / atomic swaps | Drafted | **No precedent for adaptor signatures over RedPallas**; Monero BTC-swap stack proven but currently unmaintained/fork-broken; expected verdict: defer to post-launch research |
| [E5](E5-pow-randomx-asic.md) | PoW / RandomX / ASIC posture | Drafted | RandomX ~7 yrs production + multiple adopters; Equihash fully ASIC-dominated; rich LWMA incident record with concrete mitigations |
| [E6](E6-merge-mining.md) | Merge-mining with Monero | Drafted | Strong long-horizon precedents (Namecoin 2011, Dogecoin 2014) and one young RandomX precedent (Tari 2025); CoiledCoin sabotage confirms zero-cost-attacker class |
