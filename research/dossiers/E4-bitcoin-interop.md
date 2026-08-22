# E4 — Bitcoin interoperability / atomic swaps

**Exploration:** What Bitcoin interop is achievable without novel cryptography, and is any of it launch-relevant? · **Status:** Draft · **Date:** 2026-08-22

## 1. Draft verdict (DRAFT)

**Defer to post-launch research; preserve prerequisites at launch.** The Phase 0 precedent search returned a clear negative on the one construction PLAN.md flagged: **no reviewed or production adaptor-signature scheme over RedDSA/RedPallas exists anywhere** — existing Zcash-ecosystem swap work either uses transparent-side HTLCs (XCAT, 2017) or deliberately *avoids* adaptor signatures in favor of cross-curve DLEQ proofs + ZK binding circuits (Zwap's Orchard-native swaps — which target EVM chains, not Bitcoin). Under PLAN.md §2.1 ("no novel cryptography"), a shielded-native BTC swap on a Zcash-derived Meownero is therefore not shippable in v1. The Monero-side story is proven-in-principle but currently degraded in practice: the COMIT `xmr-btc-swap` protocol (adaptor signatures + cross-curve DLEQ over Ed25519/secp256k1) worked in production, but the repo is **unmaintained** ("USE eigenwallet INSTEAD"), notes a Monero-fork network-level break, and states its cryptography "has not been formally audited"; FCMP++ will preserve the high-level swap choreography but break CLSAG-specific implementations. Net: on either candidate, Tier-1 trustless swaps are a *credible research direction with named mechanisms*, not a launch feature. This is a scope decision, not an architecture decision — it cannot pick between candidates.

**PLAN.md impact:** §5 E4's "plausible in principle, unverified" for RedPallas adaptor signatures is now a confirmed **no-precedent** result. New fact for the tier framework: Zwap demonstrates a *fully shielded* swap pattern (DLEQ + hashbind circuits) that avoids adaptor signatures — a second candidate mechanism PLAN.md didn't list. Recommend E4's tiers be restated around three mechanisms (transparent-HTLC bounce, DLEQ+ZK binding, adaptor-signature scriptless) at amendment time.

## 2. Production precedents & maturity evidence

- **BTC↔XMR adaptor-signature swaps:** h4sh3d protocol (cross-curve DLEQ Ed25519↔secp256k1 + one-time VES/adaptor signature on the Bitcoin side); implemented by COMIT `xmr-btc-swap`; real mainnet usage. `[VERIFIED-PRIMARY]` — github.com/h4sh3d/xmr-btc-atomic-swap, github.com/comit-network/xmr-btc-swap (read 2026-08-22).
- **Current maintenance:** COMIT repo banner: unmaintained, community successor **eigenwallet/core** (GUI; includes network-level changes incompatible with the original); repo notes a Monero fork broke network compatibility; "cryptography … not formally audited." `[VERIFIED-PRIMARY]` — repo README (read 2026-08-22). eigenwallet's own maintenance level and FCMP++ readiness: `[OPEN]`.
- **FCMP++ effect:** high-level swap choreography (lock/lock/reveal) survives; CLSAG-hardwired implementations break and must be rewired to the new proof system. `[SECONDARY]` — explainer synthesis; upgrade via Farcaster/MRL discussions before relying on it.
- **Zcash-side precedents:** XCAT (2017) — BTC/ZEC atomic swaps via transparent HTLCs `[SECONDARY]`; **Zwap** (2025–26, Zcash forum) — Orchard-native shielded swaps with EVM chains using cross-curve DLEQ (Pallas↔secp256k1) + client-side "hashbind" ZK circuit, explicitly sidestepping adaptor signatures; and an earlier Zwap BTC/ZEC transparent-side design. `[SECONDARY→PRIMARY]` — forum threads are near-primary; pin them.
- **RedDSA/RedPallas adaptor signatures:** ZcashFoundation/reddsa implements standard signatures only; ZIP-312 rerandomized FROST covers *threshold* signing, not adaptors. **No adaptor construction found.** `[VERIFIED as negative result across Phase 0 searches]`
- **Rejected class (unchanged):** custodial bridges, federated pegs, wrapped assets — fail §2.1 by construction; no evidence could rehabilitate them.

## 3. Consensus/crypto delta

Target **zero consensus delta** at launch. The only launch obligation is negative: don't gratuitously break future swap paths (keep spend-auth schemes standard; document curve/scheme choices). The crypto delta, if/when pursued post-launch: (a) M-path — port the proven Ed25519 DLEQ+adaptor stack to FCMP++-era spend auth (implementation rework, known design); (b) Z-path — either transparent-HTLC-style bounce (needs a transparent escape hatch we won't have under E2 — likely dead on arrival; verify) or a Zwap-style DLEQ+ZK-binding design retargeted from EVM to Bitcoin script (design work; no BTC instance exists yet). `[OPEN]`

## 4. Security assumptions introduced

None at launch (nothing ships). If pursued later: adaptor/VES security over the chosen scheme; DLEQ proof soundness across curve pairs; swap-implementation correctness. Bounded blast radius: swap failures lose swap participants' funds, never chain consensus.

## 5. Audit burden

Zero at launch. Post-launch: external cryptographer review of the chosen construction + audit of any implementation we endorse (the COMIT stack's own "not formally audited" warning is the cautionary label here).

## 6. Kill criteria (met for v1 — per PLAN.md §5 E4)

"No reviewed construction exists for our chosen lineage within Phase 0" — **this criterion is presently met on both candidates** (Z: no adaptor precedent at all; M: proven design but no maintained, FCMP++-ready implementation). Interop is deferred accordingly. Never launch-blocking; never architecture-deciding.

## 7. Safest fallback

No protocol-level interop at launch; swaps via exchanges/OTC; revisit when (a) eigenwallet or Farcaster ships FCMP++-ready swaps (M-path), or (b) a Zwap-style BTC design or a reviewed RedDSA adaptor scheme appears (Z-path).

## 8. Open verification tasks

- [ ] Pin the Zwap forum threads (shielded swaps, unlinkable swaps, BTC/ZEC design) as near-primary sources.
- [ ] Assess eigenwallet/core: activity, maintainers, FCMP++ roadmap.
- [ ] Track Farcaster project status and any FCMP++ swap-compatibility statements from MRL.
- [ ] Confirm whether a Z-path transparent-HTLC bounce is definitionally excluded by E2's mandatory-shielded rule (likely yes — document).
- [ ] Write the "prerequisites to preserve" list for ADR-001 (signature-scheme choices that keep future swaps possible).

## 9. Sources

Primary: github.com/comit-network/xmr-btc-swap · github.com/h4sh3d/xmr-btc-atomic-swap · github.com/ZcashFoundation/reddsa · arxiv.org/abs/2101.12332 (swap protocol paper)
Secondary (to upgrade): Zcash forum Zwap threads (55874, 55104, 44864) · zips.z.cash/zip-0224, ZIP-312 (context) · FCMP++ swap-impact explainers · github.com/eigenwallet/core · github.com/farcaster-project
