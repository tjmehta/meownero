# Milestone checklist — PLAN.md rev 5 made executable

**Status:** live checklist · **Started:** 2026-09-05 · Governed by `PLAN.md` §2 (doctrine), §5.4 (decision rule), §10 (gates). This file converts settled philosophy into objective exit criteria; it does not restate or reopen the philosophy.

Authorization boundary (group, 2026-09-05): implementation work is authorized. **Not** authorized: public deployment or mainnet launch, spending, third-party messages, domain/account changes, key custody, pushing externally. Every item below stops at a locally reproducible, review-ready artifact.

Legend: `[ ]` open · `[x]` done with evidence link · `[~]` partial · `[G]` gated on an external/date event (named)

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
- [ ] Signed by TJ and the whitepaper author — **human gate**; until then the ADR is "proposed".

## M1 — Foundation (on the selected/provisional lineage)

- [x] Repo layout: `chain/upstream.lock` (tag + commit + submodule hashes) + `chain/patches/0001…0006` applied by `chain/build.sh` (`git am`, fails on drift). Fresh upstream checkout end-to-end build passed 2026-09-06, including `meow_*` 8/8; hashes in `chain/README.md` and `research/verification-2026-09-06-m1.md`.
- [~] Reproducible build from clean checkout: deterministic patch commit dates, `ARCH=default`, digest-pinned base and immutable builder/package records implemented. Two fresh cache-disabled eight-patch builds passed (2026-09-07; `chain/test-reproducibility.sh`, exit 0); **all three binary hashes match**, as do version metadata and package manifests. Same-host fixed-image source reproducibility is verified; provenance and full hashes are in `chain/README.md`. Apt snapshots/version pinning and independent toolchain reconstruction remain open.
- [ ] Consensus deltas each have an ADR entry and test vectors (§2.2 item 5).
- [x] Emission spec v1 (`docs/spec/emission.md`): invariants with tests, honest dilution table, 78-year tally horizon at 12 dp, forbidden claims listed.
- [~] Identity (`docs/spec/network-identity.md`): genesis (zero-amount v2 coinbase), prefixes, ports, network IDs, hard-fork table — explicit and exercised on the devnet; **seed/bootstrap policy, testnet/stagenet tables, mainnet genesis timestamp are human/launch-time decisions**.
- [~] Difficulty (`docs/spec/difficulty.md`): patch 0008 fixes startup clamping while preserving genesis difficulty 1 and recalculation consistency. **2026-09-07: 9/9 tests each at floor 1 and 150M**, including actual core initialization, fixed-difficulty override and cumulative work; production constant stays 1. Adversarial alt-chain/reorg coverage remains M2. **Floor value needs the guaranteed genesis hashrate (launch input)**.
- [x] Threat model v1 (`docs/security/threat-model.md`), code map (`docs/security/code-map.md`, includes baseline-attributed test failures); audit scope = code map + readiness records.
- [~] CI (`.github/workflows/chain.yml`): shellcheck, pin/patch consistency, container build, consensus tests, upstream suite with exclusions, devnet smoke, hash comparison. **Never executed remotely (no remote by authorization).** 2026-09-07: eleven-patch count, bounded protocol/floor tests and isolated authority runner wired; address exclusion removed after patch 0009 and multisig exclusion after patch 0011; relink-only check replaced by two fresh compilations in one immutable image (verified for eight patches). Devnet still assumes a separately named builder image. Six historical wallet/serialization failures remain; the patch-0011 offline broader run also failed six DNS-dependent cases (1,221/1,233 passed), without added exclusions. Patch-0011 targeted tests pass 287/287, including all seven multisig cases; patch-0010 raised-floor tests pass 9/9. No fuzz/property targets yet.
- [~] Wallet path: `monero-wallet-rpc` send/receive verified across nodes; CLI caveats documented (`docs/ops/operator.md`); restore-from-seed **not yet exercised**.
- [ ] Wallet presentation (2026-09-07): simpler display with adequate small-payment precision, exact-amount disclosure and no silent input rounding/nonzero-to-zero display. Preserve consensus/RPC atomic units; test smallest amounts and large balances. Adoption evaluation uses measured payment completion, conversion and retention—not claimed causal benefits of an issuance model.

## M2 — Private devnet

- [ ] Deterministic local multi-node network: mine, sync, reorg within policy, private tx, restart/recover.
- [ ] Rejects malformed, inflationary, and non-private data (adversarial suite).
- [ ] Matched-issuance comparison (group instruction 2026-09-07): **90 s / 0.675 MEOW vs 120 s / 0.9 MEOW**, each targeting 236,520 MEOW per 365 days. Measure propagation, proof validation, block capacity, competing blocks/orphans and reorgs under comparable loads/topologies; disclose uncertainty and test limits. **90 s is not locked; retain the current default until evidence supports a decision.** Do not weaken mainnet-quality gates or test 0.9/90 s as though its +1/3 issuance were approved (PLAN §8.1).
- [ ] Performance evidence: initial sync, steady-state validation, worst-case block, relay latency, memory/CPU/disk.
- [ ] 2-week-equivalent devnet uptime run without consensus fault (accelerated where honest).
- [ ] Explorer alpha or documented gap.

## M3 — Testnet readiness (local, not public)

- [ ] Hostile review passes: inflation/supply, privacy escape hatches, consensus split, malformed proofs/tx, reorg/difficulty/timestamp, DoS/resource, network isolation/eclipse/bootstrap, wallet recovery, supply chain, upgrade safety — each with findings and dispositions.
- [ ] No open high/critical; every medium has a written disposition.
- [ ] Release/checkpoint/signing plan, incident-response runbook, operator docs, testnet launch checklist.
- [ ] Final clean-checkout verification and release-candidate handoff.
- [G] External audit engagement (money + counsel — human gate, open-questions #8/#9).
- [G] Public testnet, key custody, mainnet — human gates; never crossed here.
