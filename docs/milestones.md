# Milestone checklist — PLAN.md rev 7 made executable

**Selected-policy update, September 12:** [decision and verification](../research/decision-2026-09-12-issuance.md). Target 9/90, fallback 12/120 if 90 s fails; both 3,153,600 MEOW/year before penalties. Prior parameter results below are historical controls. Selected binaries now pass the bounded checks described below; fee/wallet integration and matched-capacity intended-crypto network gates remain open.

**Latest recovery checkpoint:** [September 13 session recovery](../research/recovery-index-2026-09-13.md).
Two clean historical fifteen-patch builds match. Selected/fallback emission
fixtures each pass 7/7 smoke tests. Later recovered evidence records that the
9/90 build compiled but its native selection failed seven of 1,237 tests.
September 13 recovery fixed the fixture/test-environment issues; fresh 9/90 and
12/120 builds each pass all 1,237 selected native tests, with no new exclusions.
P2P relay/partition/rejoin/reorg checks also pass for both profiles. Rust's pinned
context crate compiles and local site presentation checks pass. Earlier queued
build descriptions below record their original checkpoints, not current processes.

**Collaboration update, September 13:** anyone may help test; maintainers may
remain anonymous, and TJ is doing most of the work. Agents handle review and
research. No named second maintainer or paid-review procurement prerequisite;
technical verification and findings disposition remain required. The next group
ask is help testing, beginning with iPhone Safari.

**Status:** live checklist · **Started:** 2026-09-05 · Governed by `PLAN.md` §2 (doctrine), §5.4 (decision rule), §10 (gates). This file converts settled philosophy into objective exit criteria; it does not restate or reopen the philosophy.

Authorization boundary (group, 2026-09-05): implementation work is authorized. **Not** authorized: public deployment or mainnet launch, spending, third-party messages, domain/account changes, key custody, pushing externally. Every item below stops at a locally reproducible, review-ready artifact.

Legend: `[ ]` open · `[x]` done with evidence link · `[~]` partial · `[G]` gated on an external/date event (named)

**2026-09-12 resumed checkpoint:** [foundation evidence](../research/verification-2026-09-12-m1.md)
and [M2 evidence](../research/verification-2026-09-12-m2.md). Thirteen-patch clean
binary reproduction passes; fifteen-patch full CI selection passes 1,237/1,237;
wallet seed recovery passes; each floor target passes 10/10. Private daemon reorg
checks and 720 native-DAA modeled scenarios pass with explicit limits. TJ completed
private snapshot publishing; future engineering changes remain local. Settled
parameters and human launch gates are unchanged.

**Parallel local checkpoint (2026-09-12):** [integrated handoff](../research/handoff-2026-09-12-swarm.md). Actual P2P partition/rejoin passes; received private-payment seed recovery passes; 29 wallet metadata/observer cases pass with an explicit OpenAlias DNS gap; 1,870 Cuprate primitive cases agree with three separately expected extreme-arithmetic mismatches; P2Pool incompatibilities are demonstrated by source-pinned probes. Storyboard and challenge materials are local. Clean fifteen-patch reproduction is queued behind host RAM; actual matched-capacity 90/120 and FCMP workloads remain open.

---

## M0-S1 — Stage 1 evidence (close or mark as watch items)

- [x] E1 rev 3, E2 rev 3, E4 rev 2 researchable tasks closed (`research/dossiers/`).
- [x] E3 rev 2 reframed; monetary decision taken 2026-09-05 (PLAN §8.1).
- [~] E5 residuals: Zephyr/Salvium/Wownero pinned (rev 2); seed schedule: solo mode inherent (control confirms), merge-mined deferred; **launch difficulty floor** remains an M1 design item.
- [x] E6 residuals closed in rev 2 (Tari `MoneroPowData`/multi-aux, Tari incident review, Dogecoin v1.8.0 pin, Monero ~6 GH/s).
- [~] E1 residuals: Zebra Regtest custom activation heights + shielded coinbase confirmed by running it; custom genesis **not** possible without a generator; Sapling-only/ZIP 219 and Zallet status held with Candidate Z.
- [G] E2: Pirate Ironwood activation observed clean (2026-10-03) — gate for Ironwood eligibility (PLAN §7).
- [G] E3 rev 3: faithful read of the 2026-09-04 transcript (needs `wa-bridge`).
- [G] E6: FCMP++ mainnet release (no date) — monitor.

Exit: every E1–E6 task is `[x]` or `[G]` with the gate named.

## M0-S2 — Stage 2 control prototypes (throwaway, feasibility only — PLAN §2.3)

Both controls exercise the *actual* risky deltas, not stand-ins.

**Candidate M control** (Monero v0.18.5.1, pinned `4f92268`):
- [x] Builds from pinned tag in a documented container (`spikes/candidate-m/Dockerfile`); baseline `monerod` built before patching. *(baseline unit-test run still owed for failure attribution)*
- [x] Emission delta: constant 0.9 MEOW/block in `get_block_reward`, genesis reward 0, penalty math retained; `block_reward` tests replaced — 7/7 pass (2026-09-05).
- [x] Identity delta: network ID, ports, address prefixes, `CRYPTONOTE_NAME`, v2 zero-amount genesis, empty seed lists, fresh hard-fork table, checkpoints/blobs/DNS/updates removed (`docs/spec/network-identity.md`).
- [x] Private devnet: 3 nodes mine, sync, pay exactly 0.9/block, `get_coinbase_tx_sum` = h × 0.9; wallet round-trip: RingCT tx (type 6, ring 16) sent from the miner wallet, mined, received by a wallet on another node (2026-09-05, candidate-m README).
- [x] Touched-file inventory (`apply.py` output, `docs/security/code-map.md`) and diff committed.

**Candidate Z control** (Zebra v6.3.0, pinned `d1fd7ad`):
- [x] Builds from pinned tag natively with the documented user-space toolchain; baseline zebrad mined 3 regtest blocks into the Ironwood pool before patching.
- [~] Regtest config boots with NU6.3 at height 1 (Meownero magic/name/genesis **not** done: Zebra cannot generate genesis blocks — M1 task if Z is selected).
- [x] Emission delta: constant subsidy; `MAX_MONEY` raised; funding streams/lockbox empty by Regtest config; `meow_tests` 4/4 pass.
- [x] Mandatory-shielded rule implemented and wired; `meow_mandatory_shielded` 2/2 pass over every upstream vector transaction; live adversarial run: transparent-miner block rejected (`TransparentValueForbidden`).
- [ ] PoW: RandomX-in-Zebra scope estimate — **not done**; deferred with Candidate Z (ADR-001 §5).
- [~] Single Regtest node mines 10 blocks paying 0.9 into the Ironwood pool; multi-node and wallet round-trip **documented as gaps** (Regtest is single-node; Zallet alpha).
- [x] Touched-file inventory (`apply.py` output, `docs/security/code-map.md`) and diff committed.

**Measurements (both):** diff size and touched invariants; validation cost per block/tx; propagation on the local network; maintenance surface (upstream commit velocity, open security advisories); audit-burden estimate per PLAN §2.2 rubric lines (a)–(i).

Exit: both controls boot and mine with Meownero identity and 0.9/block; measurements table committed under `spikes/README.md`.

## M0-S3 — ADR-001

- [x] Per-candidate delta enumeration from the measured controls (ADR-001 §1).
- [~] §2.2 readiness records drafted (`docs/readiness/`): M RingCT, Z Ironwood; Z Sapling not drafted (held with Z).
- [x] Provisional selection (M) with the named gate and re-evaluation procedure (ADR-001 §5) — PROPOSED, unsigned.
- [x] Disposition of every desideratum (ADR-001 §4).
- [ ] Architecture approval recorded by TJ as current active maintainer; no mandatory the whitepaper author co-signature. The ADR remains "proposed" until approval is recorded.

## M1 — Foundation (on the selected/provisional lineage)

- [x] Repo layout: `chain/upstream.lock` (tag + commit + submodule hashes) + `chain/patches/0001…0015` applied by `chain/build.sh` (`git am`, fails on drift). Fresh upstream checkout end-to-end build passed 2026-09-06, including `meow_*` 8/8; hashes in `chain/README.md` and `research/verification-2026-09-06-m1.md`.
- [~] Reproducible build from clean checkout: deterministic patch commit dates, `ARCH=default`, digest-pinned base and immutable builder/package records implemented. Two fresh cache-disabled fifteen-patch builds now pass (`chain/test-reproducibility.sh`, exit 0); all three daemon/wallet hashes, source/submodule/input receipts, version metadata and package manifests match. [Complete clean15 verification](../research/verification-2026-09-12-clean15.md) supersedes the queued/in-progress status; the thirteen-patch reproduction remains historical evidence. This proves same-host fixed-image reproduction of the historical 0.9/120 family. Selected-profile reproduction, apt snapshots/version pinning and independent toolchain reconstruction remain open.
- [ ] Consensus deltas each have an ADR entry and test vectors (§2.2 item 5).
- [x] Emission spec v1 (`docs/spec/emission.md`): invariants with tests, honest dilution table, 78-year tally horizon at 12 dp, forbidden claims listed.
- [~] Identity (`docs/spec/network-identity.md`): genesis (zero-amount v2 coinbase), prefixes, ports, network IDs, hard-fork table — explicit and exercised on the devnet; **seed/bootstrap policy, testnet/stagenet tables, mainnet genesis timestamp are human/launch-time decisions**.
- [~] Difficulty (`docs/spec/difficulty.md`): patch 0008 fixes startup clamping while preserving genesis difficulty 1 and recalculation consistency. **2026-09-07: 9/9 tests each at floor 1 and 150M**, including actual core initialization, fixed-difficulty override and cumulative work; production constant stays 1. 2026-09-12: 10/10 at each floor, including varying-work main/alt sampling, window/lag rollback and recalculation; actual floor-one daemon reorg passes beyond height 738. High-work and long-alt-chain cases remain M2. **Floor value needs the guaranteed genesis hashrate (launch input)**.
- [x] Threat model v1 (`docs/security/threat-model.md`), code map (`docs/security/code-map.md`, includes baseline-attributed test failures); audit scope = code map + readiness records.
- [~] CI (`.github/workflows/chain.yml`): shellcheck, pin/patch consistency, container build, consensus tests, upstream suite with exclusions, devnet smoke, hash comparison. **Remote CI status not verified here; TJ published a private snapshot, and future changes stay local.** 2026-09-07: thirteen-patch count, bounded protocol/floor tests and isolated authority runner wired; address exclusion removed after patch 0009 and multisig exclusion after patch 0011; relink-only check replaced by two fresh compilations in one immutable image (verified for eight patches). 2026-09-12: builder/devnet image forwarding and shellcheck fixed; seed/reorg/native-DAA runners wired; full-suite source is read-only with disposable data and pipefail. Patches 0012/0013 close the six wallet/serialization fixture failures with historical bytes and production genesis checks preserved. The thirteen-patch network-enabled full CI selection passed **1,234/1,234**; the current fifteen-patch selection passes **1,237/1,237**, retaining only the three baseline-attributed exclusions (not an unfiltered pass). Patch-0013 targeted tests pass 91/91; patch-0010 raised-floor tests pass 9/9. No fuzz/property targets yet.
- [~] Wallet path: `monero-wallet-rpc` send/receive verified across nodes; CLI caveats documented (`docs/ops/operator.md`); 2026-09-12: patch 0014 fixes sparse-fork wallet refresh; restore from seed verifies address, 130 coinbase-history entries, exact total/unlocked balances and reopen. A separate private received-payment demo now verifies seed restoration, matching history/balance/reopen and loss of a local note. 2026-09-18: on the selected 9/90 binary, a funded-devnet harness (`chain/test-wallet-funded.py`) verifies an actual send A→B, fee/atomic-unit arithmetic by exact sender identity, **outgoing-metadata recovery** and **spending after restore** from a rescan, reopen stability, and a real-daemon aggregate whose emission/fee tally equals the wallets' own fee reports ([evidence](../research/wallet-funded-2026-09-18.md), [receipts](../research/evidence/wallet-funded-2026-09-18/)). 2026-09-18: a recording forwarding proxy on the untrusted wallet↔daemon boundary captures the **actual observed transport metadata** (`/getblocks.bin`, `/get_outs.bin`, `/get_output_distribution.bin`, `/sendrawtransaction` first-relay origin, `/json_rpc`, `/getheight`) and correlates **one injected node denial** (`503` on a sync `.bin`) with the wallet observing the error, not crashing, and recovering on the next refresh ([evidence](../research/wallet-transport-2026-09-18.md), [receipts](../research/evidence/wallet-transport-2026-09-18/); records are metadata-only, sanitized). This is observed-exposure execution evidence, not an anonymity claim; public-IP exposure and Tor/I2P remain untested hypotheses. Remaining open: interactive CLI restoration, sweep/multi-destination/subaddress paths, public-network transport hardening, and repetition beyond a single run; findings await independent TJS-43 review.
- [ ] Wallet presentation (2026-09-07): simpler display with adequate small-payment precision, exact-amount disclosure and no silent input rounding/nonzero-to-zero display. Preserve consensus/RPC atomic units; test smallest amounts and large balances. Adoption evaluation uses measured payment completion, conversion and retention—not claimed causal benefits of an issuance model.

## M2 — Private devnet

- [~] Local multi-node network: three-node mining/sync and private tx previously verified; 2026-09-12 actual daemon depth-3 reorg/restart checks pass in regtest and native-DAA mainnet mode beyond h738. The initial RPC delivery harness is now complemented by an actual P2P proxy partition/rejoin test with a depth-3 reorg and malformed-frame/healthy-relay control. All are low-work/empty-block tests; final reorg policy remains open.
- [~] Malformed block, obsolete block version, future/below-median timestamp and +1-atomic coinbase rejected with a positive control (2026-09-12). Invalid/private-proof and non-private transaction cases remain open.
- [~] Matched-issuance comparison (group instruction 2026-09-07): **90 s / 0.675 MEOW vs 120 s / 0.9 MEOW**, each targeting 236,520 MEOW per 365 days. 2026-09-12: 720 paired native-DAA modeled scenarios completed; launch timestamp distortion remains an open modeled risk. Propagation, proof validation, block capacity, competing blocks/orphans and reorg performance under comparable loads/topologies remain unmeasured. **90 s is not locked; retain the current default until evidence supports a decision.** Do not weaken mainnet-quality gates or test 0.9/90 s as though its +1/3 issuance were approved (PLAN §8.1).
- [ ] Performance evidence: initial sync, steady-state validation, worst-case block, relay latency, memory/CPU/disk.
- [ ] 2-week-equivalent devnet uptime run without consensus fault (accelerated where honest).
- [ ] Explorer alpha or documented gap.

## M3 — Testnet readiness (local, not public)

- [ ] Hostile review passes: inflation/supply, privacy escape hatches, consensus split, malformed proofs/tx, reorg/difficulty/timestamp, DoS/resource, network isolation/eclipse/bootstrap, wallet recovery, supply chain, upgrade safety — each with findings and dispositions.
- [ ] No open high/critical; every medium has a written disposition.
- [ ] Release/checkpoint/signing plan, incident-response runbook, operator docs, testnet launch checklist.
- [ ] Final clean-checkout verification and release-candidate handoff.
- [ ] Agent review/research completed with scope, evidence and findings dispositions. Paid external audit/counsel procurement is not a prerequisite under TJ's September 13 direction.
- [G] Public testnet, key custody, mainnet — human gates; never crossed here.
