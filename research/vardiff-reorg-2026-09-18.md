# Variable-difficulty reorg economics — F2 closure (TJS-129), September 18, 2026

Local, agent-run exercise of the recovered selected **9 MEOW / 90 s** binary that
closes **F2**: reorg selection and DAA behaviour under **real, above-floor, varying**
difficulty, where a **shorter** branch can out-work a **longer** one. Every prior
consensus/reorg test in this repo ran at fixed difficulty 1 (regtest
`--fixed-difficulty 1`, or the native DAA *held* at floor 1 by 120 s timestamps), so
"heavier" == "longer" and the work-over-height rule was never actually exercised. This
task removes that limitation with real RandomX proof-of-work and no fixed-difficulty
override.

Owned scope: `chain/` network/mining test harness and its evidence only (one writer).
Agent-authored and agent-run; **not** an external audit and **not** a launch-readiness
sign-off. This does not lock 90 s, adopt ASERT/LWMA, change consensus economics, or
cross any human launch gate. Independent agent review accepted the original revision on September 20
([review](review-tjs129-2026-09-20.md)); TJS-166 applies its report/receipt
corrections below without rerunning the experiment. QA and launch gates are unchanged.

## Revision binding

| Item | Value |
|---|---|
| Repo branch / HEAD | `m1/september-7-verification` / `678606fbed84f1d70e575075a9b5231a8066fa77` |
| Original run/review harness (historical hashes; preserved evidence) | `chain/test-reorg-vardiff.py` **`2c55674a3d9f1fa69330a8d0b3d79dcc58b86b4302894990c8913e50166478f1`**, `chain/test-reorg-vardiff.sh` `3d067df764222520824e090c091fd6ff3e00ef98c97a2cbeeedeab35fb77e7ca` |
| Selected 9/90 source | HEAD `7410c04bab0e304112710d63c3225c110bd8b4de`, tree `4db958cb96d72943c5c2433bd5f4a8f730037148` |
| `monerod` (selected 9/90) | `b79cb49dbea95c0eeff7dca8c945d65f4fab3d49fb626fcbe7a9343569d4a2c1` (built at TJS-40 `da0f97c`; binary-bound to candidate HEAD per `research/acceptance-tjs44-2026-09-18.md` §1) |
| Builder image (immutable) | `sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e` |
| Profile constants (from source) | `MEOW_BLOCK_REWARD = 9000000000000` (9 MEOW), `DIFFICULTY_TARGET_V2 = 90 s`, `DIFFICULTY_WINDOW = 720`, `DIFFICULTY_LAG = 15`, `DIFFICULTY_CUT = 60`, `MEOW_MIN_DIFFICULTY = 1` |
| Evidence | `research/evidence/vardiff-2026-09-18/` (`result.json`, `result-repeat.json`, `reorg-log-run{3,4}-node0.txt`, `harness.stdout.log`, `freeze/`, `MANIFEST.sha256` — all entries verify) |
| Guards | heavy work serialized under `/tmp/meownero-swarm-20260912-heavy.lock`; ≥5 GiB MemAvailable preflight (14.6 GiB free during runs); container `--network none`, `--memory 3g`/no swap, `--cpus 2`, `--pids-limit 512`, `--cap-drop ALL`, `--security-opt no-new-privileges`, non-root |

## How real above-floor difficulty is produced (no PoW shortcut)

The harness mines each block by taking a real `get_block_template` (real DAA difficulty),
setting the block timestamp, and then **searching the 4-byte nonce by submitting candidate
blocks to the daemon's own `submit_block` verifier until one is ACCEPTED**. Acceptance is
the authoritative signal that the block met the DAA-computed difficulty under full RandomX
consensus verification — the same path a P2P-relayed block takes. No difficulty is asserted
from a label; it is read from the daemon and *earned* with real work.

- **`calc_pow` is deliberately not the acceptance oracle.** Our probe supplied the full
  block blob, while `calc_pow` expects the **hashing blob** (`blockhashing_blob`) plus
  matching `major_version`, `height` and `seed_hash`. The observed mismatch was a
  harness-usage artifact, **not a daemon defect**. In the selected source above,
  `src/rpc/core_rpc_server.cpp:2054` passes supplied bytes to the blob overload at
  `src/cryptonote_core/cryptonote_tx_utils.cpp:729`; the verifier uses the block overload
  at `:757`, which first computes `get_block_hashing_blob(block)`. This correction is
  source-based, not a new equality probe. `submit_block` acceptance remains the oracle
  used by the original runs. See [independent review §3 R1](review-tjs129-2026-09-20.md).
- **Difficulty steering is a hashpower *model* on the real DAA, not a live hashrate race.**
  The DAA sets `next_difficulty = ceil(total_work × 90 / time_span)` over the young-chain
  window; inter-block spacing is the only lever a hashpower change pulls, so the harness
  steers the block timestamp to raise/hold/drop difficulty. This exercises the real daemon
  DAA and real PoW acceptance, but it is not competing physical hashrate. "50 % / 90 %
  miner departure" == spacing widened 2× / 10× vs target; "recovery / miners return" ==
  spacing tightened. Peak difficulty is bounded on purpose (`LEVEL = 32`) to keep RandomX
  cost small; this bounds cost, not the argument.

## Predeclared acceptance criteria and results (result = **PASS**)

Criteria were fixed in the harness docstring before the heavy runs. All four hold on the
primary run (`result.json`) and reproduce byte-identically in chain structure on the repeat
(`result-repeat.json`).

| # | Criterion | Result | Key figures |
|---|---|---|---|
| **AC1** | Non-floor variable difficulty: real DAA yields difficulty > floor (peak ≥ 16), each block accepted by RandomX consensus, tip work > height+1 | **PASS** | base difficulty ramps `1→18→33` then holds `32`; ramp peak **33**; root cumulative_difficulty **312** at height 12 (≫ 13) |
| **AC2** | DAA departure/recovery response: wider spacing strictly lowers next difficulty; tighter spacing raises it | **PASS** | stable `[32,32,32,32]`; 50 % departure `[32,30,29,27,26]`; 90 % departure `[25,19,15,12,11]`; recovery `[10…13]` (turns back up off the trough) |
| **AC3** | Cumulative-work-not-height selection: a strictly **shorter** heavier branch replaces a longer one; a shorter-and-lighter prefix does **not**; displaced blocks off the selected chain | **PASS** | main **height 36 / work 467** (24 blocks, difficulty collapsed to 2); attacker **height 17 / work 472** (5 blocks at difficulty 32); reorg switches exactly at attacker block index 4 (the block that crossed 467); **24/24** main blocks displaced |
| **AC4** | Invariants: both nodes converge; emission == height × 9 MEOW; tip work == recomputed sum of block difficulties; restart preserves tip | **PASS** | converged tip identical on both daemons; emission **153,000,000,000,000 == 17 × 9 MEOW**; recomputed work **472 == tip work**; restart preserved tip |

### The reorg, from the daemon's own log (`reorg-log-run3-node0.txt`)

```
###### REORGANIZE on height: 13 of 36 with cum_difficulty 467
 alternative blockchain size: 5 with cum_difficulty 472
REORGANIZE SUCCESS! on height: 13, new blockchain size: 18
```

A **5-block** alternative chain (cumulative work **472**) replaced a chain of **height 36**
(cumulative work **467**). Selection is decided by cumulative work, not height: the winning
chain is **19 blocks shorter**. The negative control is intrinsic to the incremental
delivery — attacker blocks 0–3 (still shorter *and* strictly lighter) were delivered and
**retained as alternatives without replacing main**; the switch occurred only on block 4,
the first at which alternative work strictly exceeded main work. Delivered alternative
work was `344→376→408→440→472` against main work `467`: **equal work was not
exercised**. Retention at equality follows from the strictly-greater fork-choice
condition in selected `src/cryptonote_core/blockchain.cpp:2100`, not this run.

## Scope and honesty bounds (stated, not hidden)

- **Two isolated `--offline` mainnet-mode daemons**; explicit `get_block`/`submit_block`
  delivery (no P2P, no transactions, empty blocks); disposable fixture address;
  `--network none`. Crypto is RingCT-era (empty blocks here); **no FCMP**, no capacity
  normalisation, no anonymity claim.
- **Difficulty is genuinely above the floor and varying, but timestamp-driven** (a hashpower
  model on the real DAA), not competing physical hashrate. The reorg, PoW acceptance, orphan
  handling, emission and convergence are all real daemon behaviour.
- **Young-chain DAA recovery is sluggish and is shown honestly.** Because the full prior
  history stays inside the < 720-block window, recovery after a 90 % departure climbs back
  only gradually (`10→13` over 24 minimal-spacing blocks). This matches the documented
  whiplash property in `docs/spec/difficulty.md`; it is recorded, not smoothed over.
- **The work margin is intentionally small (472 vs 467).** That is the point: height 17
  beats height 36 on 5 units of extra work. A larger margin is a parameter, not a stronger
  proof.
- **Determinism / repeat.** Chain structure (heights, difficulties, cumulative work, switch
  index, displaced count) is byte-identical across two runs; only the per-block nonce-search
  count differs (the satisfying RandomX nonce varies), total PoW submits 750 vs 536.
- Single fixture address, empty blocks, no secret material recorded.

## What this closes and what it does not

- **Closes F2** as scoped in `research/adversarial-consensus-2026-09-18.md` (§F2) and the
  TJS-44 completion matrix ("Variable-difficulty deep-reorg economics — OPEN … all evidence
  floor-1"): consensus prefers cumulative work over height under real, above-floor, varying
  difficulty, on the actual daemon, with supply/work/convergence invariants intact and a
  correct DAA response to modeled hashpower departure and recovery.
- **Does not** close, and makes no claim about: **F3** (matched-capacity, intended **FCMP**
  loaded partition/reorg — FCMP absent from source; still blocks GO); **F4** (decentralized
  pool / P2Pool payout); **F7** (well-formed non-private-tx consensus rejection); the 90 s
  parameter GO; selfish-mining / withholding strategies; eclipse; a real multi-miner
  hashrate race; independent-toolchain reproducibility. This is **not** authority to adopt
  ASERT/LWMA or change consensus economics.

## Executable commands

```
# heavy runs serialized under the shared lock; ≥5 GiB MemAvailable preflight upstream
flock -w 300 /tmp/meownero-swarm-20260912-heavy.lock \
  bash chain/test-reorg-vardiff.sh \
    build/repro-selected-20260918/selected-9-90/first/source \
    build/reorg-vardiff-20260918/run3
# verify evidence
( cd research/evidence/vardiff-2026-09-18 && sha256sum -c MANIFEST.sha256 )
```

## Resources, cleanup, exclusions

- Container `--network none`, `--memory 3g`/no swap, `--cpus 2`, `--cap-drop ALL`, non-root,
  1800 s timeout (actual runtime well under it; ≤ 750 PoW `submit_block` attempts total).
- Historical working trees (`build/reorg-vardiff-20260918/run{3,4}/n0`, `n1`,
  `n1-departrec`) and full daemon logs were removed. Only three `REORGANIZE` lines
  per run survived; the PoW rejection and alternative-chain diagnostic logs cannot
  now be inspected. This is an evidence-preservation limitation, not a full-log receipt.
- **Future runs:** the corrected wrapper keeps complete `n0.log.gz` / `n1.log.gz`
  (when their logs exist) and `DAEMON_LOG_SHA256` on normal completion or failure,
  retaining the original logs too. Copy these archives and checksum receipt into durable
  evidence before removing live working trees; include them in its manifest. Copy
  `SOURCE_REVISIONS` **and** `SOURCE_OVERLAY.patch` into `freeze/`: the revision receipt
  now appends the SHA-256 of the binary-safe tracked diff against HEAD (staged and
  unstaged). It does not cover untracked sources or prove a build used that overlay;
  the binary remains separately hashed. Do not retrofit these receipts into old evidence.
- Local only: no mainnet/public node, no spending, no real keys, no remote push, no new
  agents, no infrastructure/host-service change. Heavy lock held; no host service stopped.

## Next bounded action

The original candidate was accepted by independent agent review; TJS-166 corrects R1–R4
without a heavy rerun. QA retains its own acceptance responsibility. Remaining open gates are unchanged: F3
(FCMP matched-capacity), F4 (pool/payout), F7 (well-formed non-private consensus rule),
90 s GO, and independent-toolchain reproducibility.

## TJS-166 correction receipt — September 20, 2026

**Superseded:** the earlier daemon-defect attribution and exercised-equal-work wording.
R1 corrects the report and Python docstring; R2 records the lost historical logs and
adds full-log compression for future runs; R3 separates witnessed lighter prefixes
from source-only equality behavior; R4 binds future tracked source overlays.
No mining logic, acceptance assertions, consensus source, or original evidence changed.

Current corrected harness SHA-256 (not the producer of the September 18 evidence):

- `chain/test-reorg-vardiff.py`: `2f841710f49a9a3d60ff2a05139ed0804ba3080ff2c30bceab106ef9f97db1df`
- `chain/test-reorg-vardiff.sh`: `6754037ab5f320e7910e8cf0d0050538fb30f5b61e8e2022dd6e5b1291369e18`

The original Python hash `2c55674a3d9f1fa69330a8d0b3d79dcc58b86b4302894990c8913e50166478f1`
and shell hash in the revision table remain the reviewed producer bindings. The original
`freeze/INPUT_SHA256`, `freeze/SOURCE_REVISIONS` and nine-entry evidence manifest are
unchanged; the new hashes do not relabel the accepted historical results.

Lightweight verification (TJS-166): Bash syntax and Python compilation passed; Python
AST is identical to the reviewed harness except its module docstring. With Docker
replaced by a fixture (no daemon/container launch), the wrapper passed clean and
staged-plus-unstaged source receipt checks, full-log gzip round trips on success and
failure, preservation of nonzero exit codes, missing-log failure handling, and refusal
to reuse an output directory without mutating its receipts. Report hashes match current
harness bytes; all nine original evidence manifest entries still verify. No real
`calc_pow` equality probe, mining run, or new consensus result is claimed.
