# Loaded 90 s versus 120 s at matched issuance — September 15, 2026

TJS-39 (M2). Local, agent-run measurement of the selected 9 MEOW/90 s profile
against the gated 12 MEOW/120 s fallback under an actual transaction load, using
the September 13 recovered binaries. Agent-authored and agent-reviewed; not an
external audit. Nothing here locks 90 s.

## Revision binding

| Item | Value |
|---|---|
| Branch / HEAD | `m1/september-7-verification` / `17bb881c2470add06129ac69aa72fae89a8d52b3` (harness files untracked at this revision) |
| Harness | `chain/test-network-loaded.py` `d65aca97346dad325f44c89c9c6a3b9ac7386c32dfe6d81116171e104cbee71b`; wrapper `chain/test-network-loaded.sh` `bf3a3af6ce218011d59d0fb1295038b873b22117ffa568d179678c7190c31b67` |
| Driver / summarizer | `spikes/network-benchmark/loaded-matrix.py`, `spikes/network-benchmark/summarize-loaded.py` (hashes in `matrix.json`) |
| Selected 9/90 binaries | `build/recovery-network-20260913/selected-9-90-launch-01/output/source/build/release/bin/` — `monerod` `b79cb49d…`, `monero-wallet-rpc` `5782abee…` (native receipt: 1,237/1,237) |
| Fallback 12/120 binaries | `build/recovery-network-20260913/fallback-12-120-run-01/output/source/build/release/bin/` (native receipt: 1,237/1,237; hashes in `matrix.json`) |
| Builder image | `sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e` |
| Guards (unchanged) | shared heavy lock `/tmp/meownero-swarm-20260912-heavy.lock`; >=5 GiB host MemAvailable preflight (bounded wait, exit 75 on refusal); container `--network none --memory=1536m --memory-swap=1536m --cpus=2` |

## What is held constant, and what is not

Per cell both arms use identical `--duration`, `--tx-interval`, `--outputs`,
`--link`, `--accel`, `--seed`, `--competing-every`, `--partition-txs`, the same
container caps, the same two-daemon topology through the same shaped TCP proxies
and the same hardware. Only `DIFFICULTY_TARGET_V2` and `MEOW_BLOCK_REWARD` differ,
and both are asserted on both daemons (RPC `target`, emission = height × reward).
Issuance per second is therefore matched by construction (10¹¹ atomic/s).

Not matched, reported rather than hidden:

- **Block capacity is not normalized.** Both binaries keep the pinned 300,000
  penalty-free zone, so 90 s admits 4/3 the bytes per second of 120 s. The
  offered load in these cells is far below either limit, so capacity never binds.
- **Difficulty is fixed at 1** (`--regtest --fixed-difficulty 1`) and blocks come
  from `generateblocks`. There is no proof-of-work race; the native DAA is not
  exercised here (it is covered separately by `chain/test-difficulty.sh` and the
  native-DAA benchmark).
- **No FCMP integration exists in the pinned source** (`src/fcmp_pp` absent).
  The `--outputs 8` cells scale RingCT transaction size only; they are a size
  sensitivity, never a proof-cost model. The "intended FCMP profile" is
  therefore explicitly **unavailable**, not approximated.
- **Accelerated cells** (`--accel 6`: one block every 15 s at 90, every 20 s at
  120) are not target-rate measurements. Only the `--accel 1` cells are.
  Wall-clock latencies from accelerated cells are additionally shown multiplied
  by the acceleration factor as "chain seconds"; that is a conversion, not data.
- Two daemons on loopback through a deterministic shaper (nominal: 20 ms per
  16 KiB chunk + 64 KiB/s per stream; slow: 150 ms + 16 KiB/s) are not a WAN
  topology. Stale-block probability is derived as 1 − exp(−relay/target) from
  measured relay; it is a propagation-delay model, not an observed natural
  orphan rate. Induced competing blocks and the depth-3 partition are forced.

## Predeclared matrix (written before any matrix cell ran)

Sixteen cells, sequential, interleaved by profile so both arms see the same host
drift:

| Group | Cells | Constants |
|---|---|---|
| accelerated | {nominal, slow} × seeds {1, 2, 3} × {selected-9-90, fallback-12-120} = 12 | `--accel 6 --duration 240 --tx-interval 2 --outputs 2 --competing-every 4 --partition-txs 5` |
| size-sensitivity | nominal, seed 1, both profiles = 2 | as above with `--outputs 8` |
| target-rate | nominal, seed 1, both profiles = 2 | `--accel 1 --duration 600 --tx-interval 2 --outputs 2 --competing-every 4 --partition-txs 5` |

Each cell: fresh databases; funding warm-up (empty coinbase blocks, enough
matured outputs that steady-state transfers never wait on change maturity);
steady state with one real wallet-rpc RingCT transfer every 2 s ± 0.2 s jitter
and one block per emulated slot; every 4th slot both nodes generate a competing
block and the next slot resolves it; then a partition with 5 transactions
submitted and mined on the cut-off side, a 3-versus-4 block race, rejoin,
orphan-flag and return-to-pool checks, a post-rejoin block carrying the
re-relayed transactions, and a final no-transaction-lost check on both nodes.

Sample adequacy: 240 s at `--accel 6` gives 16 slots (12 steady + 4 competing)
at 90 s and 12 slots (9 + 3) at 120 s per seed, so 36 versus 27 steady block
relay samples per link across three seeds and about 120 transactions per cell.
That bounds medians; maxima are observed maxima, not tail estimates. The two
target-rate cells give 6 and 5 slots each; they exist to check that the
accelerated numbers are not artefacts of acceleration, not to add samples.

## Predeclared decision criteria

Evaluated per link on the accelerated group (the target-rate and sensitivity
cells are reported and must not contradict them):

1. Block relay maximum under load ≤ 10 % of the target interval for every seed
   (9 s at 90, 12 s at 120).
2. Derived stale probability (max-based) for 90 < 1 % and ≤ 2 × the 120 value.
3. Every cell converges after partition with zero lost transactions and
   `PASS`.
4. No daemon exit ≠ 0, no cgroup memory-limit or OOM event.
5. First-confirmation median (chain seconds) at 90 lower than at 120, and
   equal-work confirmation (4 blocks at 90 versus 3 at 120) not worse than 120
   (≤ 105 %).

Outcomes: 90 fails any criterion while 120 passes → **no-go** on these criteria.
Both fail the same criterion → **inconclusive**, inspect harness/host first.
90 meets all → **defer (no blocker found)**. Because FCMP integration is
unavailable and capacity is not normalized, "go" is not attainable from this
task, and 90 s is not to be locked from these results or the earlier
empty-block passes.

## Smoke (before the matrix)

`build/loaded-network-20260915/smoke-01/`: selected-9-90, seed 1,
`--accel 10 --duration 40 --tx-interval 2 --competing-every 4 --partition-txs 3`.
Gate passed at 5,667,364 KiB available; wrapper exit 0. 23 transfers, 0 lost,
0 wallet errors; steady blocks carried 5/4/5 transactions (10,917/8,751/10,917
weight); block relay median 0.122 s, max 0.210 s; transaction relay median
1.33 s, max 2.72 s; competing slot diverged and resolved; partition rejoin
0.59 s with 3/3 orphaned transactions returned and re-relayed; peak cgroup
memory 674,627,584 B, no limit/OOM events; both daemons and wallet-rpc exited 0.
No harness change was needed after the smoke.

## Results

All 16 predeclared cells completed. The matrix stopped once at the unchanged
>=5 GiB gate (cell 10, host MemAvailable 1.6–2.3 GiB) and was **resumed unchanged**
on 2026-09-17 (host ~28 GiB free) after re-verifying that every binary, harness,
wrapper, driver and builder-image hash still matched `matrix.json` (no drift).
Final table: `build/loaded-network-20260915/matrix-01/summary.md`
(completed `2026-09-17T16:51:26Z`).

Receipts (SHA-256):

| Artifact | SHA-256 (first 16) |
|---|---|
| `matrix-01/summary.json` | `a02ff34734241c9e…` |
| `matrix-01/summary.md` | `211d99beb72d724f…` |
| `matrix-01/progress.json` | `2fa434c984cbc112…` |
| `matrix-01/matrix.json` | `4a9b36ae8ad945a3…` |
| `matrix-01/MANIFEST.sha256` (101 per-cell files) | `fa1c8b75e24ffe93…` |

**Functional outcome (all 16 cells):** every cell `PASS` — 0 transactions lost,
partition rejoin + orphan return + re-relay succeeded, no daemon exit ≠ 0, and
no cgroup memory-limit or OOM event (peak 625–664 MiB against the 1,536 MiB cap).

**Predeclared criteria (evaluated per link on the accelerated group; target-rate
and size-sensitivity reported alongside and consistent):**

| group / link | relay 90/120 | stale p max 90/120 | converge 90/120 | resources 90/120 | confirmation 90 | pass 90 | pass 120 |
|---|---|---|---|---|---|---|---|
| accelerated / nominal | True/True | 0.00285 / 0.00186 | True/True | True/True | True (1st 48.0 vs 66.1; eq-work 312.1 vs 299.9) | **True** | True |
| accelerated / slow | True/True | **0.03314** / 0.00655 | True/True | True/True | True (1st 49.2 vs 68.1; eq-work 313.6 vs 300.8) | **False** | True |
| size-sensitivity / nominal | True/True | 0.00197 / 0.00162 | True/True | True/True | True | True | True |
| target-rate / nominal (`accel=1`) | True/True | 0.00277 / 0.00243 | True/True | True/True | True (1st 46.1 vs 61.1; eq-work 316.1 vs 301.1) | **True** | True |

The **only** predeclared failure is the **slow-link stale-probability** bound for
90 s: `stale_p_max = 0.0331 > 0.01` (criterion 2), while 120 s passes (0.0066).
Relay-fraction, convergence, resources and confirmation-latency criteria all pass
for 90 s in every group, including the non-accelerated target-rate cells (90 s
first-confirmation median is lower than 120 s, and equal-work confirmation is
within 105 %). Under the predeclared decision table, "90 fails any criterion while
120 passes" ⇒ **no-go on these criteria**.

**Why that single failure is confounded, stated without explaining it away.** The
slow-link `stale_p_max` is a max over seeds and is set entirely by one cell,
`accelerated/slow-s3/selected-9-90`:

- That cell's steady-block relay ran hot across the whole 4.5-min window
  (median 0.769 s, max 3.034 s; sorted tail 1.279 / 2.855 / 3.034 s), roughly
  2.5–4× the other two slow 90 s seeds (max 0.793 s and 0.776 s; stale_p_max
  0.0088 and 0.0086, both under 0.01).
- Its **paired** `slow-s3/fallback-12-120` was normal (relay max 0.788 s), as was
  every other slow cell, and the cell itself still `PASS`ed with 0 tx lost, all
  exits 0, peak mem 627 MiB, no OOM. A profile-structural slow-down would not
  spare the paired 120 s arm of the same seed.

This signature — one cell's wall-clock relay inflated uniformly while its 120 s
pair and the other 90 s seeds are clean — is consistent with **transient host
CPU/IO contention during that cell's window**, not a property of the 9 s/90 s
interval. It is recorded here as an **unresolved reliability observation**, not as
proof of a 90 s defect and not as something the other passing seeds "explain
away."

## Recommendation

**No-go for 90 s on the predeclared criteria as run** — reported faithfully — but
**this is not a clean structural no-go**, because the sole failing criterion rests
on one contention-confounded cell (above). It is therefore **not** evidence that
90 s is safe either. Concretely:

- Do **not** lock or advance 90 s on this matrix. The earlier empty-block passes
  and the 15 clean cells here do not override the recorded slow-link failure.
- Do **not** silently re-run or overwrite `slow-s3/selected` to recover a "pass";
  that would be cherry-picking. The cell stands as recorded.
- **Next bounded action (follow-up, not done here):** repeat the slow-link arm
  with additional seeds (e.g. seeds 4–6, both profiles) on a quiescent host under
  the same unchanged guards, to determine whether the slow 90 s relay tail
  reproduces. If the slow-link 90 s `stale_p_max` stays < 0.01 across the added
  seeds, the failure is attributable to host contention and the criteria are met;
  if it recurs, it becomes a first-class 90 s slow-propagation blocker to fix
  before any 90 s decision.

Independent of the above, a **GO remains unattainable from this task** regardless
of the numbers: actual FCMP integration is **unavailable** in the pinned source
(size-sensitivity is a RingCT-size proxy only, never a proof-cost model), block
capacity is **not** normalized (90 s admits 4/3 the bytes/s of 120 s), and
difficulty is fixed at 1 so the **native DAA / PoW is not exercised here**.
Capacity matching, adequate target-rate sampling, and equivalent-security
evidence with the intended crypto profile remain preconditions for any 90 s GO.

## Exclusions

No mainnet or public node, no spending, no real keys, no remote push, no new
agents, no FCMP or capacity-normalization claim, no change to any gate, cap or
host service. The matrix was resumed on the same root with all predeclared
constants and guards byte-identical (hashes re-verified before relaunch); no cell
was retried to change its result. Host services that consumed memory were left
running; the matrix waited for or yielded to the unchanged >=5 GiB preflight.
Agent-authored and agent-reviewed; not an external audit.
