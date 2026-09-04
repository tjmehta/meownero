# E4 — Bitcoin interoperability / atomic swaps

**Exploration:** What Bitcoin interop is achievable without novel cryptography, and is any of it launch-relevant? · **Status:** Draft (rev 2) · **Date:** 2026-08-22, revised 2026-09-04

> **Rev 2 changelog (2026-09-04):** all five researchable open tasks from §8 closed against current primary/near-primary sources. The v1 verdict is unchanged and, if anything, better-evidenced: **defer interop to post-launch; preserve prerequisites at launch.** Key new findings — Zwap (the only Orchard-native shielded-swap effort) is **abandoned** and hit a *fundamental* wall (Orchard/Ironwood have no script primitives, so its UTXO-lock design does not map to the shielded side); **eigenwallet is actively maintained** (the M-path implementation is alive) but publishes **no FCMP++-readiness statement**; **Farcaster is dormant** at the protocol layer; FCMP++ replaces CLSAG spend-authorization with a **Generalized Schnorr Protocol**, confirming that CLSAG-specific swap code breaks while the choreography can survive; and a transparent-HTLC bounce on the Meownero side is **definitionally excluded** by E2's mandatory-shielded rule. New §9 gives the ADR-001 "prerequisites to preserve" list.

## 1. Draft verdict (rev 2)

**Defer to post-launch research; preserve prerequisites at launch.** The Phase 0 precedent search returned a clear negative on the one construction PLAN.md flagged: **no reviewed or production adaptor-signature scheme over RedDSA/RedPallas exists anywhere** — existing Zcash-ecosystem swap work either uses transparent-side HTLCs (XCAT, 2017) or deliberately *avoids* adaptor signatures in favor of cross-curve DLEQ proofs + ZK binding circuits (Zwap's Orchard-native swaps — which targeted EVM chains, not Bitcoin, and are now abandoned; §2a). Under PLAN.md §2.1 ("no novel cryptography"), a shielded-native BTC swap on a Zcash-derived Meownero is therefore not shippable in v1. The Monero-side story is proven-in-principle and its implementation is **alive but FCMP++-unconfirmed**: the COMIT `xmr-btc-swap` protocol (adaptor signature on the Bitcoin/secp256k1 side + cross-curve DLEQ binding a split Ed25519 Monero key) worked in production; the original COMIT repo is unmaintained ("USE eigenwallet INSTEAD") but its successor **eigenwallet/core is actively developed** (latest commit 2026-08-28, release 4.14.0 2026-08-22; §2). What no maintained implementation states is FCMP++ readiness — and FCMP++ rewrites Monero's spend-authorization layer from CLSAG to a Generalized Schnorr Protocol (§2), so CLSAG-hardwired swap code must be rewired even though the high-level choreography survives. Net: on either candidate, Tier-1 trustless swaps are a *credible research direction with named mechanisms*, not a launch feature. **This is a scope decision, not an architecture decision — it cannot pick between candidates**, and it is never launch-blocking (PLAN.md §5 E4 kill criterion is met on both).

**PLAN.md impact:** §5 E4's "plausible in principle, unverified" for RedPallas adaptor signatures is a confirmed **no-precedent** result. Two facts for the tier framework at amendment time: (1) restate E4's mechanisms as three — transparent-HTLC bounce, DLEQ+ZK-binding, adaptor-signature scriptless — and record that **the first is impossible under mandatory privacy on both candidates** (§3, §2b), so any future Meownero swap must be of the scriptless/ZK-binding class; (2) note that the only shielded-native attempt (Zwap) failed on a structural obstacle (no script primitives in Orchard/Ironwood), which is direct evidence that the Z-path swap problem is *harder* than the M-path, not merely un-built.

## 2. Production precedents & maturity evidence

- **BTC↔XMR adaptor-signature swaps:** h4sh3d protocol (cross-curve DLEQ Ed25519↔secp256k1 + one-time VES/adaptor signature on the Bitcoin side); implemented by COMIT `xmr-btc-swap`; real mainnet usage. `[VERIFIED-PRIMARY]` — github.com/h4sh3d/xmr-btc-atomic-swap, github.com/comit-network/xmr-btc-swap (read 2026-08-22).
- **Current maintenance — updated rev 2.** The COMIT repo is unmaintained ("USE eigenwallet INSTEAD"); its successor **eigenwallet/core** ("a battle-tested Monero-Bitcoin DEX based on Atomic Swaps"; formerly UnstoppableSwap, rebranded 2024; `asb` maker + `swap` taker + Tauri GUI) is **actively maintained**: ~3,870 commits, latest commit **2026-08-28** ("Enable circuit relay connections for GUI", binarybaron), release **4.14.0 on 2026-08-22**, 147 open issues / 22 PRs. So the M-path *implementation* is alive and shipping. **But: no FCMP++-readiness statement anywhere in the repo/README, and no audit claim.** `[VERIFIED-PRIMARY]` — github.com/eigenwallet/core repo + commits/master (read 2026-09-04). FCMP++ roadmap: `[OPEN — no public statement found]`; audit: none disclosed.
- **FCMP++ effect — sharpened rev 2.** FCMP++ ("FCMP+SA+L") is an explicit **drop-in replacement for CLSAG**, and spend authorization is delivered by a **Generalized Schnorr Protocol (GSP)** proving knowledge of discrete logs over multiple generators, not a standalone CLSAG signature. The high-level swap choreography (lock/lock/adaptor-reveal) survives because it rests on Ed25519 key algebra that FCMP++ preserves, but **any CLSAG-specific signing/adaptor code breaks and must be rewired to the GSP scheme.** No primary source (kayabaNerve's FCMP++ writeup, the CCS proposals) mentions adaptor signatures or atomic swaps at all — swap-compatibility is neither promised nor demonstrated by MRL. `[VERIFIED-PRIMARY for the CLSAG-replacement/GSP facts; OPEN for post-FCMP++ adaptor compatibility]` — gist.github.com/kayabaNerve/0e1f7719…, ccs.getmonero.org fcmp++ proposals (read 2026-09-04).
- **Farcaster status — closed rev 2.** BTC↔XMR swap project (Rust; farcaster-node/farcaster-core/RFCs), an *alternative* to the h4sh3d/COMIT line. **Dormant at the protocol layer:** `farcaster-node` last updated 2024-08-11, `farcaster-core` 2023-04-10, `farcaster-gui` 2023-09; only the `containers` infra repo shows 2026 activity. No archival/deprecation banner, but no protocol development in ~2 years and **no FCMP++ statement.** Treat as inactive; not a path to rely on. `[VERIFIED-PRIMARY]` — github.com/farcaster-project (read 2026-09-04).
- **Zcash-side precedents:** XCAT (2017) — BTC/ZEC atomic swaps via **transparent** HTLCs `[SECONDARY]`; **Zwap** (2026, Zcash forum) — Orchard-native shielded swaps, **now abandoned and with a fundamental unresolved obstacle** (§2a). `[VERIFIED-PRIMARY]` — forum thread pinned in §2a.
- **RedDSA/RedPallas adaptor signatures:** ZcashFoundation/reddsa implements standard signatures only; ZIP-312 rerandomized FROST covers *threshold* signing, not adaptors. **No adaptor construction found.** `[VERIFIED as negative result across Phase 0 searches]`
- **Rejected class (unchanged):** custodial bridges, federated pegs, wrapped assets — fail §2.1 by construction; no evidence could rehabilitate them.

### 2a. Zwap — pinned and re-assessed (rev 2)

**Thread pinned `[VERIFIED-PRIMARY]`** (read 2026-09-04): *"Zwap: Trustless Shielded Atomic Swaps for Zcash (Early Access)"*, forum.zcashcommunity.com/t/…/55874, by **Aditya** (technical contributions from *immabeyeet*), active **2026-05-27 → 2026-08-25**. The related thread IDs cited in rev 1 (55104, 44864) belong to the same effort's discussion; 55874 is the load-bearing early-access announcement.

- **Mechanism (verbatim):** *"The two parties run a Diffie-Hellman-style exchange across Pallas (the curve Orchard uses for spend authorisation) and secp256k1… A DLEQ proof certifies that the same discrete log underlies both curve points without revealing the log itself,"* combined with *"a client-side hashbind circuit, proven with ProveKit,"* certifying the EVM-side commitment is consistent with the Orchard note being spent. **Adaptor signatures are explicitly avoided.**
- **Chain pair:** Zcash/Orchard ↔ **Ethereum/Base** (USDC, ETH). **Bitcoin support was "in progress" and never implemented** before the project stalled. So there was never a Zwap BTC/ZEC instance — rev 1's "earlier Zwap BTC/ZEC transparent-side design" overstated it; correct that at amendment time.
- **Status: abandoned.** Last maintainer response 2026-06-10; by August the app and docs sites were unresponsive and community members were asking whether it was still alive.
- **The finding that matters most:** community cryptographers (strahncryptography, aryaethn) identified a *structural* inconsistency — the design assumes UTXO-style hashlocks (`OP_SHA256`-type opcodes), but **Orchard has no script primitives and no scriptSig**, and *"the other party can't even see the broadcasted transaction to know what crucial data is revealed."* This is not a bug but a mismatch between the swap model and the shielded pool's capabilities, and it plausibly contributed to abandonment. **Direct evidence that a shielded-native (Z-path) swap is materially harder than the M-path**, and that the obstacle is the very property (no transparent script layer) that E2 makes mandatory. Ironwood inherits Orchard's action/proof structure (E1 §3, E2 §2c), so the same obstacle applies to an Ironwood-scoped Meownero.

### 2b. Transparent-HTLC bounce — definitionally excluded (rev 2, task closed)

Whether a Z-path transparent-HTLC "bounce" (XCAT-style: put the hashlock/timelock on a transparent Meownero output, settle the secret cross-chain) could work under E2's mandatory-shielded rule: **no, by construction.**

- An HTLC output *is* a transparent script output — a P2SH/P2WSH holding an `OP_SHA256 <h> OP_EQUALVERIFY … OP_CHECKLOCKTIMEVERIFY` redeem script. It requires a transparent value-bearing vout.
- E2's mechanism (E2 §2a/§3, `[VERIFIED-PRIMARY]`) rejects exactly that: Pirate's enforcing rule flags any **non-coinbase transparent vout with `nValue > 0`** (`main.cpp:1697`), and Meownero's planned Zebra rule requires **empty transparent bundles for all non-coinbase transactions**. A hashlocked transparent output cannot exist on such a chain.
- Shielded pools (Orchard/Ironwood/Sapling) expose **no script layer** to relocate the hashlock into — the same wall Zwap hit (§2a). There is no "shielded HTLC" primitive in these pools.
- **Conclusion:** the transparent-HTLC-bounce mechanism is permanently unavailable on a mandatory-private Meownero, on either the Sapling- or Ironwood-scoped variant. Any future Z-path swap must be scriptless/ZK-binding (DLEQ + in-circuit binding), which is precisely the class with **no reviewed BTC instance** today. This is a consequence of the §1.1 #3 product requirement, not a limitation we could engineer around without breaking mandatory privacy. `[VERIFIED-PRIMARY — derived from E2's pinned rule + Orchard/Ironwood structure]`

## 3. Consensus/crypto delta

Target **zero consensus delta** at launch. The only launch obligation is negative: don't gratuitously break future swap paths (keep spend-auth schemes standard; document curve/scheme choices — see §9). The crypto delta, if/when pursued post-launch: (a) M-path — port the Ed25519 DLEQ+adaptor stack (adaptor on the Bitcoin/secp256k1 side; Monero key split, no CLSAG adaptor strictly required) onto FCMP++-era spend auth, rewiring any CLSAG-specific code to the GSP scheme (implementation rework on a known design; eigenwallet is the living codebase but has not announced FCMP++ support); (b) Z-path — transparent-HTLC bounce is **now closed as impossible** under E2 (§2b), leaving only a Zwap-style DLEQ+ZK-binding design retargeted to Bitcoin — for which **no reviewed instance exists and the one attempt (Zwap) abandoned on the no-script-primitives obstacle (§2a)**. Z-path swaps are therefore the higher-uncertainty path. `[OPEN — post-launch]`

## 4. Security assumptions introduced

None at launch (nothing ships). If pursued later: adaptor/VES security over the chosen scheme; DLEQ proof soundness across curve pairs; swap-implementation correctness. Bounded blast radius: swap failures lose swap participants' funds, never chain consensus.

## 5. Audit burden

Zero at launch. Post-launch: external cryptographer review of the chosen construction + audit of any implementation we endorse (the COMIT stack's own "not formally audited" warning is the cautionary label here).

## 6. Kill criteria (met for v1 — per PLAN.md §5 E4)

"No reviewed construction exists for our chosen lineage within Phase 0" — **this criterion is presently met on both candidates** (Z: no adaptor precedent at all; M: proven design and a maintained implementation (eigenwallet), but no FCMP++-ready or audited one). Interop is deferred accordingly. Never launch-blocking; never architecture-deciding.

## 7. Safest fallback

No protocol-level interop at launch; swaps via exchanges/OTC; revisit when (a) eigenwallet ships (and audits) FCMP++-ready swaps — M-path, the more credible route given its live codebase — or (b) a reviewed scriptless/ZK-binding BTC design for a shielded pool appears — Z-path, currently with no instance and one abandoned attempt. Farcaster is no longer a candidate route (dormant, §2).

## 8. Open verification tasks

Closed in rev 2 (all researchable §8 tasks):

- [x] Pin the Zwap forum thread(s) as near-primary sources. → §2a. Thread 55874 pinned; abandoned; no BTC instance ever existed; structural no-script-primitives obstacle recorded.
- [x] Assess eigenwallet/core: activity, maintainers, FCMP++ roadmap. → §2. Actively maintained (commit 2026-08-28, release 4.14.0); FCMP++ roadmap **not stated publicly**; no audit claim.
- [x] Track Farcaster status and FCMP++ swap-compatibility statements from MRL. → §2. Farcaster dormant at protocol layer since 2023–24; MRL/FCMP++ primary sources make **no** adaptor/atomic-swap claims; FCMP++ = CLSAG replacement via a Generalized Schnorr Protocol.
- [x] Confirm whether a Z-path transparent-HTLC bounce is excluded by E2's mandatory-shielded rule. → §2b. **Yes, definitionally** — an HTLC needs a transparent value-bearing script vout, which E2 forbids; shielded pools expose no script layer.
- [x] Write the "prerequisites to preserve" list for ADR-001. → §9.

Remaining (post-launch / external, not researchable to closure now):

- [ ] External cryptographer consult on any construction actually pursued post-launch (PLAN.md §9.2 item 4 budget; §5 burden).
- [ ] Re-check eigenwallet for an FCMP++-migration branch/statement once Monero's FCMP++ hard fork ships (M-path readiness gate).
- [ ] Watch for any reviewed scriptless/ZK-binding shielded-pool swap design to appear (Z-path unblock trigger).

## 9. Prerequisites to preserve at launch (for ADR-001)

These cost nothing at launch and keep a future *reviewed* swap path open without any novel cryptography now. They are launch obligations of the **negative** kind — things not to break — consistent with PLAN.md §5 E4 ("preserving prerequisites where free") and §2.1.

1. **Do not fork the spend-authorization signature algebra.** Keep the chosen lineage's spend-auth scheme byte-for-byte standard (Candidate Z: RedPallas/RedDSA over Pallas, unmodified; Candidate M: Ed25519-based, whatever FCMP++ ships). Every known swap construction binds to the *unmodified* discrete-log structure of these keys; a custom signature scheme would forfeit all future reuse and would itself be novel crypto (§2.1). This also aligns with E1's **zero-circuit-delta** posture.
2. **Preserve and document the curve choices.** Cross-curve DLEQ to secp256k1 is the common primitive on both live mechanism families (M: Ed25519↔secp256k1; Z/Zwap: Pallas↔secp256k1). Record the exact curves and encodings in the spec so a future integrator inherits a known quantity, not a reverse-engineering task.
3. **Keep nonce/determinism behavior aligned with upstream.** Adaptor signatures depend on specific nonce handling; do not introduce deterministic-nonce or malleability changes that would preclude a future adaptor construction on the Bitcoin side.
4. **Accept that on-chain HTLCs are permanently foreclosed (§2b) and design brand/docs accordingly.** Mandatory privacy (§1.1 #3) means no transparent script layer ever. Any future swap is scriptless/ZK-binding by necessity; never imply an HTLC or "Bitcoin bridge" capability (PLAN.md §11 already forbids the claim). This is a preserved *fact to communicate*, not a capability to keep open.
5. **Do not diverge from the upstream proving system in ways that void reuse.** A future swap implementation will assume stock Orchard/Ironwood actions (Z) or stock FCMP++ spend auth (M). Circuit- or proof-level deltas we make for other reasons (E2/E3/E5) should avoid touching the note/spend structures a swap would bind to; enumerate any that do.
6. **Track the two live mechanism families as ADR-001 context, credit neither as shippable.** M-path: eigenwallet (alive, unaudited, FCMP++-unconfirmed). Z-path: DLEQ+ZK-binding (no BTC instance; Zwap abandoned on a structural wall). Both remain **deferred**; the §5 E4 kill criterion is met on both candidates, so interop **cannot** decide the architecture and **must not** be treated as launch-blocking.

## 10. Sources

**Primary (read 2026-09-04 unless noted):** github.com/eigenwallet/core (repo + commits/master — maintenance dates, description) · forum.zcashcommunity.com/t/…/55874 (Zwap early-access thread — mechanism, chain pair, abandonment, no-script-primitives dispute) · github.com/farcaster-project (org — repo activity dates, dormancy) · gist.github.com/kayabaNerve/0e1f7719e5797c826b87249f21ab6f86 (FCMP++/FCMP+SA+L — CLSAG replacement, GSP spend auth) · ccs.getmonero.org fcmp++-development / fcmp++-research proposals · github.com/comit-network/xmr-btc-swap (unmaintained banner) · github.com/h4sh3d/xmr-btc-atomic-swap · github.com/ZcashFoundation/reddsa · arxiv.org/abs/2101.12332 (swap protocol paper) — all earlier items read 2026-08-22 unless re-read above.

**Cross-references:** E2 §2a/§3 (mandatory-shielded enforcing rule — basis for §2b) · E1 §3 (Ironwood inherits Orchard action/proof structure) · PLAN.md §5 E4, §9.2 item 4, §11 (no "Bitcoin bridge" claim).

**Not relied upon:** FCMP++ swap-impact explainer blogs (secondary); superseded rev 1 assumption of a Zwap BTC/ZEC design (corrected in §2a).
