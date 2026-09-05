# Milestone checklist — PLAN.md rev 4 made executable

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
- [~] Private devnet: 3 nodes mine, sync, pay exactly 0.9/block, `get_coinbase_tx_sum` = h × 0.9 (2026-09-05, `devnet.sh`); wallet round-trip: see candidate-m README.
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

- [ ] Repo layout: pinned upstream (submodule or vendored at tag) + reviewable patch series under `patches/`, applied by one script; `git diff` vs upstream tag enumerable.
- [ ] Reproducible build from clean checkout: pinned toolchain, lockfiles, container recipe; two independent builds produce identical hashes.
- [ ] Consensus deltas each have an ADR entry and test vectors (§2.2 item 5).
- [ ] Emission spec v1: 0.9 MEOW/120 s, atomic units, overflow horizon, honest dilution table (PLAN §8.1) — no deflation or sub-fiat-inflation claims anywhere.
- [ ] Identity: genesis (zero spendable outputs), prefixes, ports/magic, chain ID, seed/bootstrap policy, version/upgrade rules — explicit and tested.
- [ ] Difficulty: algorithm choice recorded with E5 mitigations (FTL, solvetime clamp, window, launch floor) and simulated under hashrate whiplash.
- [ ] Threat model v1; inherited-vs-modified code map; audit-scope document.
- [ ] CI: fmt, lint, unit, integration, consensus vectors, fuzz/property where applicable, dependency/license/security checks, reproducibility check, smoke test.
- [ ] Wallet path: CLI wallet works for send/receive/restore on the private network; gaps documented, not faked.

## M2 — Private devnet

- [ ] Deterministic local multi-node network: mine, sync, reorg within policy, private tx, restart/recover.
- [ ] Rejects malformed, inflationary, and non-private data (adversarial suite).
- [ ] 120 s benchmark: propagation, validation, block capacity, orphan/reorg, proof-size effects. **If evidence favors another interval, stop for the group** (PLAN §8.1).
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
