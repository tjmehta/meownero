# TJS-44 — Local-only release-candidate acceptance, September 18, 2026

Local QA acceptance of the selected **9 MEOW / 90 s** candidate. Agent-authored
and agent-run; **not** an external audit, **not** a release/milestone sign-off,
and **not** a launch authorization. Assembles the accepted upstream evidence
(TJS-39/40/41/42/43) against the exact candidate, adds two fresh live witnesses,
and states every unresolved launch gate. No public launch, push, spend, real
keys, or host-service change occurred.

## 1. Candidate freeze (exact revision under acceptance)

| Item | Value |
|---|---|
| Repo branch / HEAD | `m1/september-7-verification` / **`678606fbed84f1d70e575075a9b5231a8066fa77`** (tree `5737294af8db0b767d0bb8131049ca127d92c98b`) |
| Candidate definition | HEAD **plus** the frozen dirty/untracked evidence set (34-file `DIRTY_MANIFEST.sha256` = `eab4af0dd5df37c3ac12e111744b631d33d6d05b21f715afa4a51ce6c01e4683`) — not HEAD alone |
| Selected 9/90 source | HEAD `7410c04bab0e304112710d63c3225c110bd8b4de`, tree `4db958cb96d72943c5c2433bd5f4a8f730037148` (reconstructed clean15 historical source + reversible selected overlays) |
| `monerod` | `b79cb49dbea95c0eeff7dca8c945d65f4fab3d49fb626fcbe7a9343569d4a2c1` |
| `monero-wallet-cli` | `76ad8cb92d25decd91e0fc88152356dad2405703cac2190fb0508edb59301120` |
| `monero-wallet-rpc` | `5782abee489e8b245b42fd237ece34d6df1c67929c552960755fab41de3a921a` |
| Builder image (immutable) | `sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e` |
| Profile constants (from source) | `MEOW_BLOCK_REWARD = 9000000000000` (9 MEOW), `DIFFICULTY_TARGET_V2 = 90 s` |
| Freeze evidence | `research/evidence/tjs44-2026-09-18/freeze/` (revision, git-status, dirty manifest, binary hashes, builder image, host state, live-harness hashes) |

**Binary ↔ candidate binding.** The binaries above were built at repo revision
`da0f97c` (TJS-40 reproduction). `git diff --name-only da0f97c..678606f` touches
**only** harness/evidence/docs — **no** `src/`, `chain/patches/`, `chain/build.sh`,
`chain/upstream.lock`, or `spikes/selected-issuance/` product/consensus/build-input
source changed (`freeze/DELTA_DA0F97C_TO_HEAD.txt`). The binaries are therefore
validly bound to candidate HEAD. Both TJS-40 clean builds (`first`/`second`) hash
byte-identically to the table above.

Pre-existing, unrelated artifacts (`.codex/`, `.mcp.json`) and a transient
authority-script tmp file are **preserved untouched** and excluded from the
candidate manifest (`freeze/UNRELATED_PRESERVED`).

## 2. Build-bound acceptance

The candidate's native/CI acceptance is inherited from accepted revision-bound
evidence (no redundant rebuild, per the standing "no redundant clean builds"
direction; the binaries and source are byte-identical to that evidence):

- **Native selection 1,237/1,237** per selected profile, 0 failures/0 errors,
  exactly the three documented baseline exclusions (`ban.subnet`,
  `http_server.response_soft_limit`, `notify.works`) — TJS-40
  `research/repro-selected-2026-09-18.md`, verified against candidate binaries here.
- **Emission / supply invariant** asserted empirically from the daemon in every
  live run below. With `h = get_info.height` (RPC height, counts genesis),
  `emission_amount == (h − 1) × 9 MEOW` and, at fixed difficulty 1,
  `cumulative_difficulty == h` — witnessed on both peers of the cross-node run
  (`h = 125`) and the funded run (`h = 209`, `emission = 208 × 9 MEOW`). Not
  trusted from a label. See `docs/ops/rollback-recovery.md` §0 for the definitions.

## 3. Private payment / recovery journey — LIVE, PASS

> **Correction (lead acceptance check of 2026-09-18, comment 4e6916b6):** the two
> runs in §3a/§3b are **component** passes — §3a mines empty blocks
> (`transactions=0`) and §3b runs one `monerod` with every wallet on the same
> `DAEMON_RPC` (single node). Neither alone proves payment **propagation/recovery
> across nodes**. The cross-node integration run in **§3c** closes that seam and is
> the primary evidence for the "private multi-node payment/recovery journey"
> acceptance item; §3a/§3b are retained as supporting component evidence.

Fresh live witnesses were run **this task** on the candidate binaries, real
`monerod` + real `monero-wallet-rpc`, disposable keys, isolated chain, container
`--network none`, under the shared heavy lock with the ≥5 GiB preflight. Harness
versions frozen in `freeze/LIVE_HARNESS_SHA256` (funded harness hashes ==
committed HEAD versions) and `tjs44-integration-2026-09-18/freeze/HARNESS_SHA256`.

### 3a. Multi-node network + rollback — `chain/test-network-p2p.py` (selected-9-90) — **PASS**

Two actual daemons over a real shaped TCP P2P link. Evidence:
`research/evidence/tjs44-2026-09-18/p2p-selected-9-90/`.

- **Relay:** 65-block warmup then 12 connected-relay samples, median **0.0956 s**,
  p95/p99 0.1049 s.
- **Partition proven:** both sides mine a divergent branch (A→height 80, B→81),
  **0 bytes forwarded** while partitioned.
- **Rollback (reorg):** rejoin performs a **depth-3 reorganization**, converging
  in **0.347 s** to the heavier tip; displaced blocks orphaned.
- **Malformed transport:** hostile inbound frame closed (EOF), **healthy relay
  survives** afterward.
- Bound to `monerod b79cb49…`; profile `selected-9-90`, reward `9000000000000`,
  target 90 s; 1536 MiB container, no swap, 2 CPU. Accelerated empty-block
  regtest, fixed difficulty 1, no FCMP (stated scope).

### 3b. Funded payment + seed recovery — `chain/test-wallet-funded.py` (selected-9-90) — **PASS (7/7)**

Actual coinbase-funded send, restore-then-spend, fee arithmetic and aggregate
cross-check. Evidence: `research/evidence/tjs44-2026-09-18/funded-selected-9-90/`.

| Case | Result | Key figures (atomic) |
|---|---|---|
| receive_coinbase | PASS | coinbase == 9,000,000,000,000 each; 60-block unlock window respected |
| send_receive | PASS | A→B transfer, fee 649,800,000; B balance == sent amount, txid in B history |
| fee_atomic_units | PASS | sender identity exact after spend + fee |
| restore_outgoing_metadata | PASS | wallet restored from 25-word seed at height 0; **outgoing spend (txid+fee) recovered from chain rescan alone** |
| restore_then_spend | PASS | restored wallet spends 3 MEOW to B; B balance → 8,000,000,000,000; sender identity exact |
| reopen | PASS | close/reopen reproduces balance (819,998,700,400,000), 92 in / 2 out entries |
| aggregate_reporting | PASS | height 209, emission 1,872,000,000,000,000 == 208×9 MEOW; daemon fee tally 1,299,600,000 **== wallet-reported fees** |

Top-level `result = PASS`; reward asserted empirically = 9 MEOW. This is the
**payment + recovery demonstration** required by TJS-44 (send, receive, restore
from seed, spend after restore, reopen), tied to the exact candidate.

**Transport / anonymity boundary (not a claim).** Both live runs use trusted
loopback wallet↔daemon HTTP in a `--network none` namespace. This is **fund
mechanics and network correctness, not unlinkability**. A remote/untrusted node
would additionally observe source address, fetched txids/outputs, restore height
and timing. Transport hardening (Tor/i2p, untrusted-node behaviour) is not
exercised here; see `research/wallet-transport-2026-09-18.md` (TJS-41) and the
observer note in each `result.json`.

### 3c. Cross-node private payment + seed recovery — `chain/test-network-payment.py` (selected-9-90) — **PASS (7/7)**

The seam the lead flagged: a real **two-daemon** network with the payment
**relayed and confirmed across P2P** and the receiver **restored from seed on the
far node**. Two actual `monerod` peers (regtest, fixed difficulty 1), connected
**only** to each other by `--add-exclusive-node` (real TCP P2P; **no** RPC
block/tx injection between nodes); a `monero-wallet-rpc` on each node. New
QA-owned harness `chain/test-network-payment.py` (`ebac3a52…`) / `.sh`
(`52472360…`). Evidence: `research/evidence/tjs44-integration-2026-09-18/`
(9-file `MANIFEST.sha256`, verified ALL OK); 6 processes exit 0, peak RSS 663 MB,
no OOM.

| Case | Result | Cross-node fact |
|---|---|---|
| two_node_p2p_up | PASS | both daemons peer (1 conn each), same genesis `20ce111b…` |
| fund_and_block_propagation | PASS | 100 blocks mined on node 0 propagate to node 1; both tips height 100, identical hash; miner balance 900,000,000,000,000 |
| payment_relayed_p2p | PASS | wallet A (node 0) sends 5 MEOW to wallet B (node 1); tx `ace51ab7…` enters node 0 pool and **relays to node 1 pool over P2P**; RingCT **type 6, ring 16, v2** (observed, not an anonymity claim) |
| payment_confirmed_cross_node | PASS | confirmation block (mined to sink) propagates; **B on node 1 receives** 5 MEOW; sender debit == amount + fee 649,800,000 |
| seed_recovery_cross_node | PASS | receiver **restored from 25-word seed on node 1**; restored balance and incoming `(txid,amount)` rows equal the original's |
| restored_spend_observed_cross_node | PASS | restored wallet (node 1) spends 2 MEOW back to A; tx `985506da…` **relays to node 0 pool over P2P**; **A on node 0 observes** the receipt |
| cross_node_convergence | PASS | both daemons identical: `rpc_height 125`, `top_index 124`, `emission (h−1)×9 MEOW = 1,116,000,000,000,000`, `cumulative_difficulty = h = 125`, same `top_block_hash 237105b8…`, fee total 1,101,900,000 |

Top-level `result = PASS`. This demonstrates a **private payment relayed and
confirmed across two P2P-connected nodes, seed recovery on the far node, and a
restored-wallet spend observed on the origin node**, with tips/emission/work equal
on both. Scope bound: regtest, fixed difficulty 1, small decoy pool, CLSAG/BP+
RingCT — **not** an anonymity, FCMP, variable-DAA or matched-capacity measurement.

**Transport / anonymity boundary (not a claim).** The wallet↔daemon channel is
trusted loopback HTTP in a `--network none` namespace. This proves **fund
propagation and recovery correctness across nodes, not unlinkability**. A remote/
untrusted node would additionally observe source address, fetched txids/outputs,
restore height and timing. Transport hardening (Tor/i2p, untrusted-node behaviour)
is not exercised here; see `research/wallet-transport-2026-09-18.md` (TJS-41).

## 4. Reproducibility — accepted by reference (no redundant build)

Same-host / same-immutable-image reproduction of **both** selected profiles is
accepted from TJS-40 (`research/repro-selected-2026-09-18.md`): two cache-disabled
builds per profile produced byte-identical `monerod`, both wallets and both test
executables, matching the September 13 recovered binaries. The candidate binaries
used above hash **exactly** to that accepted evidence, and no build-input source
changed since (§1). **Open:** independent-toolchain reconstruction (apt snapshot /
version pinning — `chain/Dockerfile`) and cross-host/cross-hardware reproduction
remain unproven (TJS-40 limits).

## 5. Rollback / operator procedures

New runbook: **`docs/ops/rollback-recovery.md`** (companion to
`docs/ops/operator.md`). Every step is either demonstrated on the candidate or
marked inherited-and-not-exercised:

- **Automatic reorg rollback — DEMONSTRATED:** depth-3 (P2P, §3a) and depth-6/12
  (RPC, regtest + native-DAA, TJS-42 `reorg-deep/`), supply/work invariants
  intact, no silent depth cap.
- **Restart preserves selected tip — DEMONSTRATED** (TJS-42 §2).
- **Wallet seed recovery — DEMONSTRATED** cross-node (§3c seed_recovery_cross_node
  / restored_spend_observed_cross_node) and single-node (§3b
  restore_outgoing_metadata / restore_then_spend / reopen).
- **Manual `pop_blocks` and cold data-dir snapshot/restore — INHERITED, NOT
  EXERCISED HERE** (honestly flagged; inherited unchanged from Monero v0.18.5.1).

## 6. Completion matrix (tied to candidate `678606f`)

| TJS-44 acceptance item | Status | Evidence |
|---|---|---|
| Freeze exact source/build/dirty manifest | **DONE** | `freeze/` (CANDIDATE_REVISION, DIRTY_MANIFEST 34 files, binary hashes, delta-to-HEAD) |
| Build-bound acceptance (native 1,237/1,237) | **DONE (by reference)** | TJS-40 repro; binaries hash-identical to candidate |
| Private **multi-node** payment journey (relayed+confirmed across P2P) | **DONE (live)** | §3c payment_relayed_p2p / payment_confirmed_cross_node (RingCT type 6, ring 16) |
| Multi-node network correctness (2-daemon P2P, cross-node funds + convergence) | **DONE (live)** | §3c fund_and_block_propagation / cross_node_convergence; §3a partition/rejoin (empty-block) |
| Recovery demonstration (seed restore + spend, **across nodes**) | **DONE (live)** | §3c seed_recovery_cross_node / restored_spend_observed_cross_node; §3b single-node restore_then_spend/reopen |
| Rollback (reorg) demonstration | **DONE (live+ref)** | §3c cross-node reconvergence; §3a depth-3 P2P reorg; TJS-42 depth-6/12 |
| Reproducibility | **DONE (same-host/image, by ref)** | §4; TJS-40 |
| Rollback/operator procedures | **DONE** | `docs/ops/rollback-recovery.md` |
| Findings resolved before acceptance | **DONE (review-accepted)** | TJS-43 R1–R3 ACCEPTED (`research/review-tjs43-recheck-2026-09-18.md`) |
| Well-formed non-private consensus rejection | **OPEN (F7)** | TJS-42 §1/F7 — parse-level only |
| Variable-difficulty deep-reorg economics | **CLOSED (F2 evidence gap; bounded)** | TJS-129 → independent accept → TJS-165 QA; [exact acceptance](qa-tjs165-2026-09-20.md). Both frozen runs AC1–AC4 PASS: height 17/work 472 beats height 36/work 467; timestamp-steered, isolated RPC, empty blocks. No live-hashrate/equal-work/FCMP or launch claim. |
| Matched-capacity intended-crypto (FCMP) loaded partition/reorg | **OPEN (F3, blocks GO)** | TJS-42 F3 — FCMP absent from source |
| Decentralized mining / P2Pool payout | **OPEN (F4)** | TJS-42 §5 — stock P2Pool incompatible, no payout |
| Independent-toolchain reproducibility | **OPEN** | TJS-40 limits — apt pinning unaddressed |
| 90 s parameter GO | **NOT LOCKED** | bounded F2 evidence accepted by TJS-165; still needs F3 + matched capacity and remaining launch gates; retain 90 s default |

## 7. Unresolved launch gates (no public launch; every gate named)

- **F3 (high, blocks GO):** matched-capacity, **intended FCMP** loaded
  partition/reorg — FCMP is not in the pinned source.
- **F2 evidence gap closed by TJS-165 (2026-09-20); broader adversarial
  economics remain unverified:** meaningful live-hashrate competition, selfish
  mining/withholding and eclipse. Timestamp-steered young-chain DAA response is
  evidenced, not a physical-miner race or complete reorg-trust sign-off.
- **F4 (high):** no functioning decentralized pool / payout proof.
- **F7 (low–medium):** mandatory-RingCT/minimum-rct-type consensus rule on a
  **well-formed** non-private tx not exercised (wallet-rpc cannot build one).
- **Reproducibility:** independent-toolchain (apt-pinned) and cross-host builds.
- **M2/M3 gates:** performance evidence, 2-week-equivalent uptime, explorer,
  full hostile review with dispositions, release/checkpoint/signing plan,
  incident-response runbook, final clean-checkout RC handoff.
- **Human gates (never crossed here):** ADR-001 architecture signature, seed/
  bootstrap policy, launch difficulty-floor value, key custody, public testnet/
  mainnet, release signing.

**No claim is made** of milestone100, 90 s GO, anonymity, FCMP, or production
readiness.

## 8. Exclusions, resources, cleanup

- Local only: no mainnet/public node, no spending, no real keys, no remote push,
  no new agents, no infrastructure/provider/host-service change. Reorg/tx/loaded
  crypto is RingCT-era (CLSAG + bulletproof+), **not** FCMP.
- Heavy runs serialized under `/tmp/meownero-swarm-20260912-heavy.lock`; ≥5 GiB
  MemAvailable preflight held (15.0–15.5 GiB during runs); containers
  `--network none`, ≤4 GiB/no-swap, 2 CPU. No host service was stopped.
- Live-run working trees under `build/tjs44-20260918/` are disposable and were
  removed after receipts were copied into `research/evidence/tjs44-2026-09-18/`
  (owned cleanup). Pre-existing dirty/untracked files preserved.

## 9. Disposition and next bounded action

Local QA acceptance of the candidate's **in-scope** items is **complete and
PASS**; the honest completion matrix (§6) and every open launch gate (§7) are
recorded. This is **not** release acceptance: TJS-44's launch gates remain open
and belong to product/QA at M2/M3 and to the human launch gates. Failures, if any
arise, go to the existing writing owner with a repro; QA edited no consensus
source. F2’s bounded evidence gap is now closed by TJS-165; next bounded action
(product/QA, not agent-closeable now): F3 (matched-capacity once an FCMP profile
exists); optional F7 constructed-tx case; independent-toolchain reproducibility.

## 10. F2 acceptance lineage addendum — TJS-165, 2026-09-20

TJS-129 evidence → independent revision-bound **accept**
(`review-tjs129-2026-09-20.md`) → **QA ACCEPT**
([qa-tjs165-2026-09-20.md](qa-tjs165-2026-09-20.md)). QA rehashed MANIFEST
9/9 and the original harness/binary receipts, checked both result files against
the report table and original run receipts, and verified retained reorg log
excerpts. No new daemon execution, rebuild or release occurred. This is a dated
addendum to the original candidate, not a rewrite of its frozen dirty manifest.

Only the F2 absence-of-variable-difficulty-evidence row changes disposition.
Full daemon logs are unavailable; equal-work retention was not exercised here;
source-overlay binding is inherited transitively through the accepted TJS-40/44
binary. R1–R4 report/future-receipt corrections remain owned by TJS-166. F3/FCMP,
F4, F7, independent-toolchain reproduction, 90 s GO and human launch gates are
unchanged. **Observed behavior:** above-floor work beats height in the two
retained runs; this is no claim of general economic safety or launch readiness.
