# Milestone checklist — PLAN.md rev 4 made executable

**Status:** live checklist · **Started:** 2026-09-05 · Governed by `PLAN.md` §2 (doctrine), §5.4 (decision rule), §10 (gates). This file converts settled philosophy into objective exit criteria; it does not restate or reopen the philosophy.

Authorization boundary (group, 2026-09-05): implementation work is authorized. **Not** authorized: public deployment or mainnet launch, spending, third-party messages, domain/account changes, key custody, pushing externally. Every item below stops at a locally reproducible, review-ready artifact.

Legend: `[ ]` open · `[x]` done with evidence link · `[~]` partial · `[G]` gated on an external/date event (named)

---

## M0-S1 — Stage 1 evidence (close or mark as watch items)

- [x] E1 rev 3, E2 rev 3, E4 rev 2 researchable tasks closed (`research/dossiers/`).
- [x] E3 rev 2 reframed; monetary decision taken 2026-09-05 (PLAN §8.1).
- [ ] E5 residuals: pin Zephyr/Salvium RandomX usage; difficulty-algorithm spec draft (LWMA-1 vs inherited Monero DAA) with launch floor; RandomX seed-schedule design for a non-Monero chain (solo + merge-mined modes).
- [ ] E6 residuals: Tari multi-aux / seed-tracking code check; Tari incident review; Dogecoin AuxPoW primary pin; current Monero hashrate from a live source.
- [ ] E1 residuals: Zebra custom-network coverage confirmed *by running it* (M0-S2 closes this); Sapling-only inheritance and ZIP 219 read; Zallet/zingolib status.
- [G] E2: Pirate Ironwood activation observed clean (2026-10-03) — gate for Ironwood eligibility (PLAN §7).
- [G] E3 rev 3: faithful read of the 2026-09-04 transcript (needs `wa-bridge`).
- [G] E6: FCMP++ mainnet release (no date) — monitor.

Exit: every E1–E6 task is `[x]` or `[G]` with the gate named.

## M0-S2 — Stage 2 control prototypes (throwaway, feasibility only — PLAN §2.3)

Both controls exercise the *actual* risky deltas, not stand-ins.

**Candidate M control** (Monero v0.18.5.1, pinned `4f92268`):
- [ ] Builds from pinned tag in a documented container; unit tests pass at baseline.
- [ ] Emission delta: constant 0.9 MEOW/block in `get_block_reward`, genesis reward 0, penalty math retained; `block_reward` unit tests updated and extended (boundary, overflow horizon, penalty interaction).
- [ ] Identity delta: network ID, ports, address prefixes, `CRYPTONOTE_NAME`, genesis tx/nonce, empty seed list, hard-fork table, checkpoints removed.
- [ ] Private devnet: 3 nodes mine, sync, and pay exactly 0.9 MEOW per block; wallet round-trip (RingCT tx) works.
- [ ] Touched-file inventory and `git diff --stat` vs upstream tag committed.

**Candidate Z control** (Zebra v6.3.0, pinned `d1fd7ad`):
- [ ] Builds from pinned tag natively with documented user-space toolchain; unit tests pass at baseline.
- [ ] Custom-testnet config boots a private network with Meownero magic/name/genesis; NU activation heights set so the chain starts at NU6.3 rules.
- [ ] Emission delta: constant subsidy replaces the halving schedule; funding streams and lockbox removed; subsidy tests updated.
- [ ] Mandatory-shielded rule: non-coinbase transactions with any transparent value-bearing output rejected (E2 §3 rule); adversarial tests (transparent output, mixed bundles, coinbase exception via ZIP-213 shielded coinbase).
- [ ] PoW: measured integration scope for RandomX-in-Zebra (touched modules, verification-cost estimate) — implementation only if ADR-001 selects Z.
- [ ] Private devnet: 3 nodes mine (PoW disabled or easy Equihash), sync, and pay the constant subsidy; shielded-only wallet round-trip via Zallet or zingolib, or documented as a gap.
- [ ] Touched-file inventory and `git diff --stat` vs upstream tag committed.

**Measurements (both):** diff size and touched invariants; validation cost per block/tx; propagation on the local network; maintenance surface (upstream commit velocity, open security advisories); audit-burden estimate per PLAN §2.2 rubric lines (a)–(i).

Exit: both controls boot and mine with Meownero identity and 0.9/block; measurements table committed under `spikes/README.md`.

## M0-S3 — ADR-001

- [ ] Per-candidate delta enumeration (§5.4 step 1) from the measured controls.
- [ ] §2.2 readiness record drafted for each candidate's *shipped* privacy layer (M: RingCT/CLSAG as shipped in 0.18.5.1; Z: Sapling and Ironwood separately).
- [ ] Selection or provisional selection with the single named gate (Ironwood observation 2026-10-03 + exact review) and the re-evaluation procedure.
- [ ] Disposition of every desideratum (adopt / defer / drop).
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
