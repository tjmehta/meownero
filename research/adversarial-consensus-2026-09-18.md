# Adversarial consensus, difficulty and mining — TJS-42, September 18, 2026

Local, agent-run adversarial exercise of the recovered selected **9 MEOW / 90 s**
binary. Owned scope: `chain/`/network/mining test harness and its evidence only
(one writer). Agent-authored and agent-reviewed; **not** an external audit and
**not** a launch-readiness sign-off. Nothing here locks 90 s or crosses any human
launch gate. Findings await the independent TJS-43 revision-bound review.

## Revision binding

| Item | Value |
|---|---|
| Repo branch / HEAD | `m1/september-7-verification` / `678606fbed84f1d70e575075a9b5231a8066fa77` |
| Dirty tracked file (pre-existing, untouched) | `research/resume-network-2026-09-12.md` (M) |
| New harnesses (untracked, added by this task) | `chain/test-tx-rejection.py` **`6793925e…`** (relabeled 2026-09-18 per R1/R2; receipt-producing rev `a932bdb2…` preserved in evidence), `chain/test-tx-rejection.sh` `d860cc5d…`, `chain/test-reorg-deep.py` `f475b1ca…`, `chain/test-reorg-deep.sh` `a81070e5…` |
| Correction note (2026-09-18) | R1/R2/R3 from TJS-43 (`research/review-tjs43-2026-09-18.md`) applied: label/claim accuracy for the tx-rejection cases and F1 reconciled with TJS-78. Prose/label-only; **raw receipts unchanged**; no re-run. This edit changes this report's own hash from the TJS-43-frozen `0010035d…`. |
| Selected 9/90 source | HEAD `7410c04bab0e304112710d63c3225c110bd8b4de`, tree `4db958cb96d72943c5c2433bd5f4a8f730037148` |
| Selected 9/90 binaries | `monerod` `b79cb49dbea95c0eeff7dca8c945d65f4fab3d49fb626fcbe7a9343569d4a2c1`, `monero-wallet-rpc` `5782abee489e8b245b42fd237ece34d6df1c67929c552960755fab41de3a921a` |
| Builder image | `sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e` |
| Guards (unchanged) | heavy work serialized under `/tmp/meownero-swarm-20260912-heavy.lock`; ≥5 GiB MemAvailable preflight; container `--network none`, ≤4 GiB/no-swap, 2 CPU, `--cap-drop ALL`, non-root |

Selected-profile reward is **9 MEOW/block** and is asserted from the daemon's own
`get_coinbase_tx_sum` in every harness (`emission == height × 9 MEOW`).

## Scope and honesty boundaries (stated, not hidden)

- **Crypto is RingCT-era (CLSAG + bulletproof+), not FCMP.** `src/fcmp_pp` is
  absent from the pinned source. Every proof-rejection result below concerns the
  shipped RingCT verifier; it says nothing about the intended FCMP profile.
- **Fixed difficulty 1, empty/near-empty blocks, no PoW race, no peers on the
  consensus tests.** The reorg and tx-rejection harnesses use `--offline` isolated
  daemons with explicit RPC delivery (reorg) or a single loopback wallet↔daemon
  channel (tx). At floor-1 difficulty **cumulative work is proportional to height**,
  so "heavier branch" = "longer branch"; this is a longest-chain-at-equal-work
  test, not a variable-difficulty reorg-economics test.
- **The native DAA / timestamp adversarial evidence is a compiled-DAA hashrate
  MODEL**, not real miners (see §3). The only *actual-daemon* timestamp checks are
  the future/below-median block rejections (§2).
- **Tampered vs constructed.** The invalid-proof / non-private tx cases are
  byte-tampered copies of one genuine wallet transaction; they exercise the node's
  acceptance/verification path, not proof soundness in the abstract.
- Single runs, disposable keys, amounts/counts only (no secret material recorded).

## Acceptance-item map

| TJS-42 acceptance item | Real test exercised | Disposition |
|---|---|---|
| Invalid proof rejection | `chain/test-tx-rejection.py` — two structure-agnostic single-byte corruptions inside the RingCT signature area | **PASS** — rejected by the **verifier** (`invalid_input`), not the parser; **which** proof sub-check failed is not identified (R2) — §1 |
| Non-private tx rejection | same — version-1 downgrade + RCTTypeNull byte | **PARTIAL / NOT directly met** — both are **parse-level** rejections of malformed blobs (empty reason, no flags); the mandatory-RingCT / minimum-rct-type **consensus** rule on a *well-formed* non-private tx is **not** exercised (wallet-rpc cannot build one). Original acceptance item remains **open** (R1) — §1 |
| Double-spend rejection (bonus) | same — two independently-signed txs over one key image | **PASS** (rejected `double_spend`) — §1 |
| DAA hashpower changes | `chain/benchmark-difficulty.py` (compiled DAA, 720 modeled runs) + `chain/test-difficulty.sh` native | **Covered, MODELED** — §3 |
| Timestamps adversarial | modeled forward-stamp (§3) + **actual** future / below-median block rejection (`chain/test-reorg*.py`) | **PASS (actual rejects) + MODELED (issuance distortion)** — §2/§3 |
| Sustained partition / rejoin | `chain/test-network-p2p.py` (actual P2P) + `chain/test-network-loaded.py` (TJS-39 matrix) | **Covered, bounded** — §4 |
| Deeper reorganizations | `chain/test-reorg-deep.py` — depth 6 and 12, regtest + native-DAA | **PASS** — §2 |
| Decentralized mining compatibility | `spikes/p2pool/` source-pinned probes | **Incompatible; no payout proof** — §5 |
| Reorg-trust recommendation | this document — §6 | **Delivered (no authorities appointed)** |

---

## 1. Invalid-proof and non-private transaction rejection (NEW)

`chain/test-tx-rejection.py` / `.sh`. Funds wallet A by mining 90 coinbase blocks
on an isolated fixed-difficulty-1 chain, has `monero-wallet-rpc` build **one
genuine RingCT transfer** A→B without relaying it (`do_not_relay`, `get_tx_hex`),
inspects its structure, then submits the unmodified transaction and six adversarial
forms to the **real daemon `/sendrawtransaction` verifier**. Negatives are
submitted with `do_sanity_checks=false`, so a rejection can come **only** from full
parse/consensus verification — the same path a P2P-relayed transaction takes — not
the RPC pre-filter. Every rejection is checked three ways: the daemon returns a
failure, the txid does **not** enter the mempool, and the chain tip is unchanged;
the daemon must stay alive and still accept a fresh valid tx afterward.

Built transaction (this run): txid `76bcc36d…`, 2166 bytes, **version 2**,
**2 inputs, ring size 16, 2 outputs**, RingCT type **6 (bulletproof+)**, fee
649,800,000 atomic. Evidence: `research/evidence/adversarial-2026-09-18/tx-rejection/`.

Case labels below are the **current (relabeled) harness labels**; the frozen raw
receipt (`tx-rejection/result.json`, sha256 `7be6bd36…`, unchanged) records the
**old** labels. Old→new mapping is in the table's last column and repeated after it.
The daemon-status / flag / reason columns are the **actual recorded** values.

| Case (relabeled) | Submitted form | Daemon status | Flag / reason (actual) | In pool? | Tip moved? | Result | (old receipt label) |
|---|---|---|---|---|---|---|---|
| `positive_control_ringct_accepted` | unmodified RingCT tx | `OK` | (not relayed) | **yes** | no | **PASS** (accepted, mineable) | (same) |
| `version1_downgrade_parse_reject` | version byte → 1 | `Failed` | **empty reason, no flags → PARSE rejection** (malformed layout) | no | no | **PASS** (parse-reject; consensus mandatory-privacy rule NOT exercised — R1) | `nonringct_version1_downgrade` |
| `malformed_rct_type_null_parse_reject` | RingCT type byte → 0 (RCTTypeNull) | `Failed` | **empty reason, no flags → PARSE rejection** | no | no | **PASS** (parse-reject; not a well-formed non-private consensus test — R1) | `nonprivate_rct_type_null` |
| `corrupted_ringct_sig_byte_final` | final blob byte flipped (RingCT sig area; sub-object undecoded) | `Failed` | **`invalid_input`** (verifier, not parser; sub-check unidentified — R2) | no | no | **PASS** | `invalid_clsag_signature_last_byte` |
| `corrupted_ringct_sig_byte_mid` | mid-RingCT byte flipped | `Failed` | **`invalid_input`** (verifier; sub-check unidentified — R2) | no | no | **PASS** | `invalid_rct_proof_payload` |
| `garbage_blob_parser` | random bytes, tx length | `Failed` | parse rejection | no | no | **PASS** | (same) |
| `confirmed_tx_resubmission_no_double_credit` | resubmit already-mined tx | `OK` | not re-added; B balance = exactly 5 MEOW; supply/fees do not inflate | no | no | **PASS** | (same) |
| `onchain_double_spend_rejected` | 2nd independently-signed tx reusing tx1's key image | `Failed` | **`double_spend` + `invalid_input`** | no | no | **PASS** | (same) |
| `valid_tx_accepted_after_rejections` | fresh valid transfer | `OK` | accepted, mineable | yes | no | **PASS** | (same) |

**Old → new label mapping** (relabel 2026-09-18 for claim accuracy; raw receipts
preserved unchanged, outcomes byte-identical, no re-run): `nonringct_version1_downgrade`
→ `version1_downgrade_parse_reject`; `nonprivate_rct_type_null` →
`malformed_rct_type_null_parse_reject`; `invalid_clsag_signature_last_byte` →
`corrupted_ringct_sig_byte_final`; `invalid_rct_proof_payload` →
`corrupted_ringct_sig_byte_mid`. Live harness after relabel: sha256
`6793925ef4961b97028423b60a1d9a992b9a5c5acbcaca77c5569e25ef34dda7`; the
receipt-producing revision `a932bdb2…` is preserved in the evidence directory.

**Reading (corrected per TJS-43 R1/R2).**
- **Invalid-proof (verifier) rejection — solid, but structure-agnostic.** A single
  flipped byte inside the RingCT signature area is rejected by **consensus
  verification** (`invalid_input`), *not* by the parser — the parse cases below
  carry no flag and an empty reason, so the distinction is genuine and valuable.
  The harness does **not** decode the RingCT prunable structure, and `invalid_input`
  is a generic flag, so **which** sub-check (CLSAG scalar, bulletproof+, or
  pseudoOuts commitment) rejected each byte is **not identified**. In particular the
  final blob byte (offset 2165 of 2166) falls in the trailing pseudoOuts commitment
  region, not a CLSAG scalar, so the earlier "clsag signature" attribution was
  removed. Claim retained: *invalid RingCT signature-area corruption is caught by
  verification, not parsing*.
- **Non-private tx rejection — NOT directly met (parse-level only).** The version-1
  and RCTTypeNull cases are rejected at **deserialization/parse** (empty reason, no
  flags) because a v1 / RCTTypeNull header does not match the RingCT-6 body still
  present. They are **proxies**, not the mandatory-RingCT / minimum-rct-type
  **consensus** rule applied to a *well-formed* transparent/cleartext transaction —
  which `monero-wallet-rpc` cannot construct. The original "non-private tx
  rejection" acceptance item is therefore **not directly exercised** and stays
  **open** (see F7). No daemon defect is implied.
- **Double-spend — genuine.** An un-refreshed sender reselected the confirmed
  output, producing a real two-transaction key-image conflict rejected with the
  `double_spend` flag. Nine of nine cases PASS as recorded (outcomes unchanged;
  only claims/labels corrected).

**Limits.** Tampered copies of one tx, RingCT-era only, single run, isolated
loopback channel. Not proof soundness; not FCMP; not a fuzzing campaign; not a
well-formed-non-private consensus test (R1); proof sub-check not attributed (R2).

## 2. Deeper reorganizations, sustained partition, and actual timestamp rejection

**Deeper reorg (NEW):** `chain/test-reorg-deep.py` / `.sh`. Two isolated daemons,
explicit `get_block`/`submit_block` delivery, empty blocks. For each scenario one
side builds `main_n` blocks and the attacker side builds `attacker_n > main_n`
under monotonic historical timestamps (a modeled sustained partition), then the
attacker branch is delivered in three stages:

- a **shorter** attacker prefix must NOT replace the heavier main chain;
- an **equal-work** prefix must NOT replace it (first-seen retained);
- the **strictly-heavier** branch MUST reorganize to full depth, orphaning every
  displaced block; cumulative work == height+1 and emission == height × 9 MEOW on
  both nodes; a daemon restart preserves the deepest selected tip.

Scenarios: **depth 6** (main 6 / attacker 7) and **depth 12** (main 12 / attacker
13), in **regtest** (fixed-difficulty 1) and **native-DAA mainnet** mode (DAA held
at floor 1 by 120 s historical timestamps; exercises the shipped difficulty code,
not a fixed-difficulty override). Evidence:
`research/evidence/adversarial-2026-09-18/reorg-deep/`.

| Mode | Scenario | Root→final height | Shorter retained | Equal-work retained | Heavier reorged | Orphaned | Result |
|---|---|---|---|---|---|---|---|
| regtest | depth 6 (6/7) | 65→72 | yes | yes | yes | 6 | **PASS** |
| regtest | depth 12 (12/13) | 72→85 | yes | yes | yes | 12 | **PASS** |
| native-DAA | depth 6 (6/7) | 738→745 | yes | yes | yes | 6 | **PASS** |
| native-DAA | depth 12 (12/13) | 745→758 | yes | yes | yes | 12 | **PASS** |

Restart-preserves-tip: **PASS** in both modes. Emission asserted `== height × 9 MEOW`
and cumulative work `== height + 1` on both nodes after every reorg.

This extends the existing depth-3 `chain/test-reorg.py`. It confirms the shipped
chain-selection code performs correct multi-block rollback/reconnect at greater
depth with supply and work invariants intact, and applies **no silent depth cap**
that would refuse a legitimately-heavier deep branch. It is **not** a
variable-difficulty reorg: heavier == longer at floor-1 work.

**Actual timestamp / malformed-block rejection** (existing `chain/test-reorg.py`,
regtest + native-DAA, re-affirmed as current-revision evidence): the daemon
rejects, without moving the tip, a malformed block, an obsolete block version, a
**future timestamp** (+2 h beyond FTL), a **below-median timestamp**, and a
**+1-atomic inflated coinbase**, with the unmodified template accepted as a
positive control. These are real-daemon consensus rejections (contrast the modeled
timestamp study in §3).

## 3. Native DAA hashpower and timestamp adversarial paths (MODELED + native callers)

Per the TJ decision ("no redundant long matrix"), this was **not** re-run as a new
matrix. It is covered by existing, current-revision evidence, honestly bounded:

- **`chain/benchmark-difficulty.py`** drives the **compiled production DAA**
  (`meow_next_difficulty`) over 720 paired runs (2 profiles × 6 scenarios × …
  seeds): steady, late-join (×500 ramp), whiplash (×10 burst), disappear/recover,
  and forward-timestamp attacks at 20 % and 50 % attacker share stamping at +FTL.
  Key adversarial reading (`docs/spec/difficulty.md`): **forward-timestamp attacks
  did not lower difficulty** — the sorted-cut-of-60 plus median-of-60 rule absorbs
  or slightly *raises* difficulty (10–13 %). The real modeled hazard is the
  **launch ramp** (a slow start then sudden hashrate → ~7× block rate for ~1 h
  before the 735-block window catches up), an economically bounded "premine-like"
  optics issue, not a difficulty-manipulation exploit.
- **`chain/test-difficulty.sh`** runs the **actual core DAA callers** (main-chain
  validation, recalculation, cumulative work, the intentionally floor-free
  `--fixed-difficulty` override) at floor 1 and a separately-compiled 150 M floor;
  10/10 native tests pass with the shipped floor 1.

**Honesty bound:** this is a **hashrate model plus native unit tests**, not real
miners on a live network. It does not include selfish-mining/withholding strategies
or variable-difficulty reorg economics. The inherited Monero DAA (735-window, 15
lag, 60-cut, median-of-60 timestamp rule, +2 h FTL) is unchanged; the launch floor
constant stays **1** until a guaranteed genesis hashrate is a launch input.
CLSAG/ring is the crypto, **not** FCMP.

## 4. Sustained partition / rejoin (bounded, existing)

- **`chain/test-network-p2p.py`** — actual TCP P2P through a shaping proxy: 65-block
  warmup, 12 connected-relay samples, a **forced partition** (both sides mine a
  divergent branch, zero bytes forwarded — proven), **rejoin** with a **depth-3
  reorg** and orphan-flagging, and a malformed-inbound-frame close with healthy
  subsequent relay. Empty-block, fixed-difficulty-1, no FCMP; TCP shaping is
  per-chunk, not a calibrated WAN.
- **`chain/test-network-loaded.py`** (TJS-39, `research/loaded-network-2026-09-15.md`)
  — the 16-cell matched 90/120 matrix under real wallet-rpc RingCT load, competing
  blocks and a partition/reorg with orphan return. **All 16 cells functionally PASS
  (0 tx lost); the one predeclared criterion failure was the accelerated slow-link
  stale-prob bound for 90 s (`stale_p_max = 0.0331 > 0.01`), driven by a single
  contention-hit cell.**

**F1 reconciled with TJS-78 (2026-09-18) — cadence artifact, not a propagation
regression.** The follow-up TJS-77/78 falsification re-ran exactly the three seeds
that failed at `accel=6` (s3/s4/s6, both profiles, slow link) at **`accel=1`
target-rate** (the scored chain target equals the wall slot, so the shared 16 KB/s
proxy can drain fork-reconciliation backlog between blocks) on a **quiescent host**.
The relay tail **disappeared**: 90 s `stale_p_max` fell from `0.03314/0.03020/0.03607`
(FAIL) to **`0.00511/0.00524/0.00507`** (all < 0.01, **0 of 3 fail**, zero hot slots),
even though `accel=1` blocks are ~5.6× heavier. All 6 cells PASS; the predeclared
summarizer verdict at target rate is **"defer (no blocker found): 90 s met every
predeclared criterion against 120 s"**. This confirms the slow-link 90 s tail is an
**emulated-link × short-accelerated-cadence queueing artifact of the harness**, not
a daemon propagation defect. The **original failing `accel=6` receipts are preserved
unchanged**; they are not overwritten or "explained away", only mechanistically
attributed. Evidence (lead-rehashed, 140 + 10 entries, zero mismatches; I
re-verified `sha256sum -c` — all readable entries OK, only root-owned in-container
key material excluded):
  - `build/loaded-network-20260915/slow-accel1-20260917/{summary.md,summary.json,matrix.json,MANIFEST.sha256}`
  - `build/loaded-network-20260915/slow-accel1-perslot-20260917/{FINDINGS.md,analysis.json,MANIFEST.sha256}`
  Secondary (not a criterion failure, not a blocker): at `accel=1` the 90 s arm's
  `tx_relay_max` (~8.9–9.5 s vs ~3.8–4.3 s at 120 s) and `rejoin_s` (~5.8–6.5 s vs
  ~1.3–2.0 s) are elevated — the same shared-link contention surfacing in tx
  propagation, tripping no predeclared bound.

**These are still not a matched-capacity, intended-crypto (FCMP), variable-difficulty
partition test, and 90 s is NOT locked** (FCMP unavailable, capacity not normalized,
native variable DAA not exercised). That GO remains a launch precondition, not
closeable here.

## 5. Decentralized mining compatibility — honest assessment

Preserved disposition (`spikes/p2pool/`, `research/swarm-mining-2026-09-12.md`,
`research/resume-mining-2026-09-12.md`): **stock P2Pool is incompatible with
Meownero and there is no functioning pool or payout proof.** Source-pinned probes
show P2Pool needs Meownero-side changes to address serialization, subsidy
construction, sidechain validation/identity, fork-height validation and separate
sharechain/peer identity before it could mine Meownero correctly. Executed checks
are the two compiled routine adaptations (address prefix decode, flat-reward
construction) plus RPC-field/negative-control probes with the real daemon; **no
P2Pool process is started, no share chain is built, no payout is demonstrated.**
Solo mining works (used to fund every test here). Low-hashrate share difficulty and
PPLNS behavior are unmeasured. This is **not disproven** and remains a first-class
open item for any decentralized-mining claim.

## 6. Reorg-trust recommendation (no authorities appointed)

**Question:** with checkpoint authorities explicitly off the table, what does the
evidence say about trusting deep reorganizations at launch?

**Evidence in hand:** the shipped chain-selection code correctly prefers strictly
greater cumulative work, retains first-seen on ties, rolls back and reconnects
correctly at depth 3 (P2P and RPC), 6 and 12 (RPC), preserves supply/work
invariants and the selected tip across restart, and rejects malformed / future /
below-median / inflated-coinbase blocks, corrupted-RingCT-signature transactions
(caught by verification, `invalid_input`) and a genuine key-image double-spend —
while **non-private transactions here are only parse-rejected as malformed v1 /
RCTTypeNull proxies, NOT exercised as well-formed transactions against the
mandatory-RingCT consensus rule (see §1 and open gap F7)**. **What is NOT in
evidence:** reorg behavior under **real
variable difficulty**, a **matched-capacity loaded** network, the **intended FCMP**
crypto, sustained multi-hour uptime, or any adversary with meaningful hashrate
(selfish mining, timestamp+difficulty coupling, eclipse). At floor-1 work every
test here treats "heavy" as "long".

**Recommendation (technical, no authority appointment):**

1. **Do not rely on checkpoints or any trusted signer.** Keep the inherited
   longest-cumulative-work rule as the sole arbiter; it is exercised and correct
   at the depths tested. Appointing a checkpoint authority is neither necessary on
   this evidence nor acceptable under the project's decentralization stance.
2. **Manage reorg risk at launch through hashrate and confirmations, not
   consensus changes.** The genuine launch hazard is a **low-hashrate young chain**
   (a small miner can produce a deep heavier branch cheaply), compounded by the
   735-block window's slow adaptation after whiplash (§3). Mitigate with (a) the
   **launch difficulty floor** set to the *guaranteed* genesis hashrate (already
   the design, value deferred to a launch input — `docs/spec/difficulty.md`), and
   (b) **exchange/merchant confirmation guidance** scaled to observed hashrate, not
   a fixed number.
3. **Before any reorg-trust sign-off, close the four preconditions** that this task
   could not: variable-difficulty deep-reorg economics, matched-capacity loaded
   partition/reorg, the intended FCMP crypto profile, and a multi-hour uptime run.
   These are M2/M3 gates, not agent-closeable here.
4. **Optional consensus delta to weigh separately:** an LWMA-style shorter window
   would speed post-whiplash recovery but is a PoW-path consensus change with no
   production precedent on this exact lineage; §3 argues confirmation guidance
   covers the same risk at lower audit cost. **Not recommended for v1.**

No checkpoint authority, trusted signer, named second maintainer or paid auditor is
proposed or required by this recommendation.

## Failure dispositions

| # | Observation | Severity | Disposition |
|---|---|---|---|
| F1 | 90 s slow-link stale-probability criterion failed once at `accel=6` (TJS-39) | **resolved as harness cadence artifact** (was: medium/unresolved) | **RECONCILED via TJS-78** (§4): the `accel=1` target-rate re-run of the failing seeds s3/s4/s6 on a quiescent host gives `stale_p_max` 0.00511/0.00524/0.00507 (< 0.01), 0/3 fail, zero hot slots → emulated-link × accelerated-cadence queueing artifact, not a propagation regression. Original `accel=6` receipts preserved. **Still no 90 s GO** (FCMP/capacity/variable-DAA unmet) |
| F2 | Previously no variable-difficulty deep-reorg evidence (all tests floor-1 → heavier==longer) | **CLOSED (bounded evidence gap)** | **TJS-129 → independent accept → TJS-165 QA, 2026-09-20:** two frozen runs, AC1–AC4 PASS; shorter height 17/work 472 replaces height 36/work 467, 24 displaced. See [QA acceptance](qa-tjs165-2026-09-20.md). Timestamp-steered, isolated RPC/empty-block evidence only; not equal-work, live-hashrate economics, FCMP/F3, F4 or 90 s GO. |
| F7 | "Non-private tx rejection" acceptance item exercised only at PARSE level (version-1/RCTTypeNull proxies), not the mandatory-RingCT/minimum-rct-type CONSENSUS rule on a well-formed non-private tx (R1/TJS-43) | low–medium (claims/gap) | Original acceptance item **remains open**; wallet-rpc cannot build a well-formed transparent tx. Optional follow-up: hand-construct a well-formed v1/RCTTypeNull tx submitted past the fork height. No daemon defect implied |
| F3 | Matched-capacity, intended-crypto (FCMP) loaded partition/reorg absent (FCMP not in source) | high (gap, blocks GO) | Launch precondition; FCMP integration does not exist in pinned source. Open, not agent-closeable |
| F4 | Stock P2Pool incompatible; no pool/payout proof | high (gap) | Honest disposition preserved; first-class open item for any decentralized-mining claim (§5) |
| F5 | Launch-ramp modeled issuance distortion (premine-like optics) | low–medium | Bounded (≈160 MEOW vs 648 MEOW/day); mitigated by guaranteed-hashrate difficulty floor at launch (§3) |
| F6 | Double-spend case relies on deterministic wallet input reselection | low (test robustness) | Recorded SKIP-not-FAIL if the sender picks different outputs; a constructed conflicting-tx variant would be more robust. Minor follow-up |

## Exclusions

No mainnet or public node, no spending, no real keys, no remote push, no new
agents, no service/provider changes, no FCMP or capacity-normalization claim, no
change to any gate/cap/host service. Recovery checkpoints, the funded seven-case
(TJS-41 at `678606f`) and historical evidence are preserved. Heavy runs serialized
under the existing lock with the ≥5 GiB preflight; no host service was stopped.

## F2 acceptance update — TJS-165, 2026-09-20

The original September 18 floor-1 scope above remains historically accurate. The
subsequent TJS-129 variable-difficulty receipts close only the named **absence of
variable-difficulty reorg evidence**, after independent review and QA readback:
[QA verdict and exact binding](qa-tjs165-2026-09-20.md). Both runs satisfy the four
predeclared criteria; no new daemon run was needed. Full historical daemon logs
were deleted; retained reorg excerpts and harness receipts are the evidence, not
a new QA witness. Equal-work retention was not exercised in these runs.

This supersedes the F2 harness request below, not the broader reorg-trust or launch
preconditions. Selfish mining/withholding, eclipse, meaningful live-hashrate
competition, mature-window DAA behavior and matched-capacity FCMP remain outside
this evidence. TJS-166 owns the R1–R4 report/future-receipt corrections; no original
receipt is rewritten. **Observed behavior:** work-over-height selection is now
evidenced above the floor, without establishing adversarial launch economics.

## Next bounded action (historical; F2 superseded above)

Optional constructed-transaction case to close F7 (a hand-built well-formed
version-1 / RCTTypeNull tx submitted past the fork height, exercising the
mandatory-RingCT consensus rule rather than a parse rejection). Then a
variable-difficulty deep-reorg harness (drop the fixed-difficulty override; drive
the DAA with adversarial timestamp/hashrate to make a genuinely-heavier *shorter*
branch) to close F2, and the matched-capacity loaded partition/reorg once an FCMP
profile exists (F3). F1 is reconciled (TJS-78 cadence artifact); 90 s stays
unlocked. The **same independent reviewer (TJS-43)** owns the affected recheck of
these R1/R2/R3 corrections before TJS-44 local QA; no self-certification.
