# ADR-001 — Architecture selection (PLAN.md §5.4)

**Status:** PROPOSED (provisional selection; not signed) · **Date:** 2026-09-05 · **Deciders:** TJ, the whitepaper author (signatures required) · **Inputs:** dossiers E1–E6, Stage 2 controls (`spikes/`), readiness records (`docs/readiness/`), PLAN.md rev 4.

## Decision (provisional)

**Select Candidate M (Monero v0.18.5.1 lineage) as the provisional implementation lineage**, and continue all architecture-neutral release engineering on it now. **Candidate Z (Zebra 6.3.0 + Ironwood) is not rejected**: it is held open behind the single named gate in PLAN.md §7 — Pirate's Ironwood activation on **2026-10-03** observed clean plus the exact gadget/encoding/integration review — with the re-evaluation procedure in §5 below. If that re-evaluation shows Z's total unproven surface has become the smaller one, this ADR is superseded before M1 code is promoted.

This is a §5.4 step-3 selection ("smallest total unproven surface"), not a preference. Every desideratum is dispositioned in §4.

## 1. Measured delta per candidate (§5.4 step 1)

From the Stage 2 controls, both implementing the same binding parameters (0.9/block perpetual, genesis 0, 120 s, mandatory privacy, no funding streams, no premine).

| Surface required by §1.1 hard requirements | Candidate M | Candidate Z |
|---|---|---|
| Mandatory privacy (§1.1 #3) | **Inherited** (RingCT since 2017; no transparent transaction type exists) — 0 lines | **New consensus rule** (`mandatory_shielded`, 12 lines + wiring + error variant); relies on ZIP-213 shielded coinbase into the Ironwood pool (works in stock Zebra 6.3.0, verified by the control) |
| Emission (0.9 flat, genesis 0) | `get_block_reward` constant; genesis special-case on template + validation sides; penalty math inherited — ~20 lines | `block_subsidy` constant; **`MAX_MONEY` raised** (Zcash's 21M cap would be crossed after ~88 years) — ~15 lines; funding streams/lockbox off by *config* on the control, a **code delta on a real fork** |
| Identity (name, magic/network ID, ports, prefixes, genesis) | Done in the control (`cryptonote_config.h`); zero-amount v2 genesis coinbase generated | **Not done**: Zebra cannot generate genesis blocks; control runs on Regtest identity. Genesis generator, network magic, name, and address prefix work are M1 items with no upstream tooling |
| Trust surfaces to remove (checkpoints, seeds, DNS, update checks) | Removed in the control (5 files) | Regtest has none; a real fork must strip Mainnet/Testnet checkpoint lists, DNS seeders, and `zcashd`-compat paths |
| PoW | RandomX inherited; difficulty algorithm inherited (launch floor: E5 open item) | Equihash inherited → **fails the ASIC desideratum** (E5); RandomX-in-Zebra is a novel integration with no precedent (**not built**) |
| Block time 120 s | Native | One constant, but every 75 s-derived parameter (difficulty averaging window, expiry deltas, network timeouts) inherits it and must be re-validated |
| Wallet | `monero-wallet-cli` inherited and built in the control | Zebra ships no wallet; Zallet is alpha (E1 §5) — **launch-critical path from week 1** |
| Network-layer privacy | Dandelion++ and Tor/I2P relay inherited | None in production on the lineage (PLAN §7) — a delta to design and review |
| Control diff size | 10 source files + 1 test file, 169 insertions / 384 deletions (mostly removed trust lists) | 8 files, ~150 insertions |
| Per-block floor | coinbase-only block: hundreds of bytes | coinbase-only block: **7,579 bytes** (Ironwood coinbase proof) |
| Upstream tests broken by the delta | 3 address/base58 vector tests (expected: Meownero prefixes), multisig tests via the same vectors; 3 env-class failures pending baseline attribution | `amount` vector test needed `MAX_MONEY` ≤ i64::MAX/2 (done); subsidy/halving vector tests expected to fail (schedule replaced) — full enumeration pending |

## 2. Readiness of the shipped privacy layer (§2.2 item 1)

| Line | M: RingCT/CLSAG/BP+ (`docs/readiness/candidate-m-ringct.md`) | Z: Ironwood (`docs/readiness/candidate-z-ironwood.md`) |
|---|---|---|
| (a) exact mechanism | recorded | recorded |
| (b) gadgets/libs | enumerated; review to perform | enumerated; **review gated** |
| (c) encodings/FFI | enumerated; review to perform | enumerated; **review gated** (encodings outside proof) |
| (d) proof ↔ impl | no mechanized proof (audits + paper proofs) | circuit soundness CI-pinned; ledger composition **not done** |
| (e) audits | CLSAG 2020, BP 2018 ×3, RandomX 2019 ×4; BP+ report to read | zkSecurity + Formal Land 2026; Least Authority 2026; reports to read |
| (f) unresolved | residual P2P/remote-node items to triage; none critical/high | composition gap, ZIP 2005 forward dependency; none critical/high |
| (g) maintenance | Core team, LTS line, HackerOne; **FCMP++ rewrite pending** | ZF/ECC, weekly releases; Zallet alpha |
| (h) incidents | 2017 key-image, 2018 burning bug, 2025 Qubic reorgs (economic) | CVE-2019-7167, CVE-2026-54496 (both undetectable-by-design, years latent) |
| (i) production time | 6–9 years per component | 5.5 weeks (Ironwood); Sapling 2018– but upstream restricting |
| **External gate** | none | **Pirate 2026-10-03 + exact review** |

Neither record is complete. M's is completable by review effort alone; Z's has a date gate.

## 3. Scoring against §2.2 (step 2) and selection (step 3)

Total *unproven* surface a Meownero release would carry:

- **M:** emission constant + genesis + identity + trust-surface removal + launch procedure. Every cryptographic component is inherited unchanged and has multi-year audited production history. Unproven items are ours and small; they are exactly the ones the control exercised and the tests cover.
- **Z:** everything in M's list **plus** a new consensus rule on the transaction structure, a raised value bound, a genesis generator, a RandomX integration (or the ASIC desideratum dropped), a wallet, network-layer privacy, and a privacy layer whose own readiness record is gated. Its assurance artifact (Tachyon) is the strongest in the field for circuit soundness, which is real credit on line (d), but it does not shrink the list above.

By §5.4 step 3, **M has the smaller total unproven surface today by a wide margin.** Step 4 (tie-break by novelty) is not reached.

**Honest counterweight (§1.1 #7, "no cosmetic rename").** On M the consensus-meaningful deltas are monetary policy (perpetual 0.9, genesis 0, no premine), fair-launch procedure, and removal of every inherited trust surface. That is a real, defensible design difference from Monero — Monero's tail is 0.6 and it launched with a 17.59 XMR genesis payout — but it is a *thin* differentiation compared with Z's mandatory-shielded rule on a Zcash lineage. §1.1 #7 says differentiation never outranks §1.1 #1; this ADR applies that ordering and records the tension rather than hiding it.

**Honest counterweight 2 (FCMP++).** Selecting M today means shipping ring signatures that upstream is replacing. PLAN §7 accepts this with the transition cost counted; the readiness record must be redone for FCMP++ when it lands on mainnet (PLAN §7 monitor rule), and the M1 patch series must stay rebase-clean against upstream so the merge is a tracked cost, not a fork.

## 4. Desiderata disposition (§5.4)

| Desideratum | Disposition | Basis |
|---|---|---|
| Zcash/Zebra/Orchard lineage (E1) | **Deferred** to the §5 re-evaluation gate; not dropped | Ironwood gated (PLAN §7); Z's extra unproven surface (§1 above) |
| Perpetual fair emission (E3) | **Adopted:** fixed perpetual shape; matched-issuance 0.9/120 s vs 0.675/90 s benchmarks; final pair and precision/display details open (PLAN §8.1) | group update 2026-09-07 (§7); controls measured at 0.9/120 s |
| Bitcoin interop (E4) | **Deferred** post-launch; six prerequisites preserved (E4 §9) | no reviewed precedent; PLAN §5 E4 |
| ASIC-resistant mining (E5) | **Adopted on M** at zero delta (RandomX inherited); posture "ASIC-unfriendly today, re-evaluated at every upgrade" | E5 |
| Merge-mining with Monero (E6) | **Deferred**: solo-mined launch; add later by audited upgrade if pool soundings justify it (open-questions #5 still open) | E6; PLAN §6.3 zero-cost-attacker class |

## 5. Re-evaluation procedure for Candidate Z

1. After 2026-10-03: record Pirate's Ironwood activation (clean activation, no consensus fault, `halo2` pins include the June fix) in E2 §2c.
2. Complete `docs/readiness/candidate-z-ironwood.md` lines (b)–(e) by performing the review (not by waiting).
3. Re-run §1 with Z's remaining M1 items costed (genesis generator, RandomX-in-Zebra or Equihash-with-disclosure, wallet path, network privacy).
4. If Z's total unproven surface is then smaller than M's, supersede this ADR with ADR-002 before any M1 code is promoted; otherwise close Z as "held, not selected" and record why.

## 6. What continues now (architecture-neutral or M-provisional)

Milestone checklist M1 on the M lineage (`docs/milestones.md`): pinned-tag layout with reviewable patch series, reproducible build, identity/genesis, emission spec v1, difficulty policy with E5 mitigations, threat model v1, CI, wallet path. Everything is throwaway-safe until signatures land: it lives under a patch series against an unmodified upstream tag.

## 7. September 7 decision update (not architecture signatures)

TJ relayed group alignment on 2026-09-07: fair launch / zero premine, a small fixed perpetual subsidy, adequate precision for small payments and simpler wallet display are agreed. Initially ultra-low percentage inflation and deflation claims are withdrawn; denomination does not change early percentage growth. No demonstrated causal adoption advantage is established for capped versus perpetual issuance; use measured payment/conversion/retention evidence.

The controls and historical measurements above remain at 0.9 MEOW / 120 s. Compare 0.675 MEOW / 90 s against that working default, preserving candidate expected issuance of 236,520 MEOW per 365 days. 0.9 / 90 s is not approved. Selection requires propagation, proof-validation, competing-block/orphan and reorg benchmarks; 90 s is not locked and 120 s is not a theoretical limit. Flat shape and honest claims are settled; final parameters and architecture signatures are not. See PLAN.md rev 5 §8.1 and `docs/spec/emission.md`.

Continue the existing local end-to-end charter, including M1 fixture/floor/reproducibility blockers and subsequent safe milestones. Reviewable local commits are authorized; public mainnet launch, spending, external push, fabricated audit claims and OpenClaw/runtime changes are not.

## 8. Signatures

- TJ: ______ (date)
- the whitepaper author: ______ (date)

Dissent, if any, is recorded here, not litigated elsewhere (§5.4 step 5).
