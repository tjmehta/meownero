# Network worker checkpoint — 2026-09-12

**Policy update:** this report and its readiness checker describe historical 0.9/120 and 0.675/90 controls. The selected gated comparison is now 9/90 versus 12/120; [decision](decision-2026-09-12-issuance.md). No selected-family or FCMP network measurement is inferred from these results.

Based on verified `39070e8e3ab32a695d80c90b7c0ad74cf39fb581` (including `81b3182`).
Complete decisions memo and resumed handoff were read before implementation.
All modifications are within the assigned worktree/owned paths and unique
`/tmp/meow-swarm-network-20260912-run`. Preserved source/binaries were mounted
read-only; closed thirteen-patch and seed-recovery evidence was not rerun.

**Actual P2P partition/rejoin and malformed-transport survival pass. Clean
fifteen-patch reproduction is queued but has not compiled: the >=5 GiB available
RAM gate remains unsatisfied. Actual matched 90/120 and FCMP performance remain
blocked integration, not successful benchmarks.**

## Delivered and verified

- [`chain/test-network-p2p.sh`](../chain/test-network-p2p.sh) and
  [Python harness](../chain/test-network-p2p.py): isolated container, real P2P
  through interruptible TCP proxies, bounded resources and timeout.
- [Reviewed run result](evidence/swarm-2026-09-12/network/p2p-reviewed/result.json),
  [execution log](evidence/swarm-2026-09-12/network/p2p-reviewed/run.log), and
  [resource/exit receipt](evidence/swarm-2026-09-12/network/p2p-reviewed/resources.json).
  Exit 0; both daemon exits 0; no cgroup OOM events; memory peak 631,209,984 bytes
  (602 MiB), 1.5 GiB/no swap/two-CPU cap. No public ports or external networking.
- Fresh databases, 65-block warmup, 12 empty-block observations. Final median
  approximately 95.6 ms; nearest-rank p95/p99 are the same 99.5 ms maximum.
  Deliberately disconnected branches diverged by three/four blocks with **zero
  forwarded proxy bytes**. Rejoin selected the greater-work tip in 448.7 ms;
  all three losing blocks report orphan status. Both chain supply checks pass.
  Malformed P2P input caused TCP reset; subsequent healthy P2P relay passes.
- These are **accelerated regtest, fixed-difficulty-one, empty-block** timings,
  including local generation/RPC and 25 ms polling. No proof validation, loaded
  capacity, native DAA, real miner, natural stale-rate or FCMP claim follows.
  Daemons **reported** 300,000 median/600,000 limit; acceptance at those limits
  was not tested. The final result labels enforcement untested explicitly.
- Bash syntax and Python AST checks pass. Shellcheck was unavailable on the
  host and immutable builder; no package was installed. Readiness inventory
  executes and exits 2 as intended, with [exact source constants, daemon hash,
  matched arithmetic and blockers](evidence/swarm-2026-09-12/network/readiness.json).

The tested reused fifteen-patch daemon SHA-256 is
`850d6eecef1831878d3a8196f3e2135a4c1ebe57f5e887566695ce9ce82e0ddc`.
It is **not** a new clean reproduction artifact.

Raw daemon logs and the upstream document are preserved as lossless gzip files;
`compressed-receipts.json` records their original hashes. Evidence file hashes
are in `EVIDENCE_SHA256SUMS`.

Earlier attempts are retained: `p2p-first` lost daemon 0 at startup under 512 MiB
(no captured OOM receipt, so cause is not proven); `p2p-second` passed before
resource instrumentation; `p2p-final` failed because the initial harness treated
TCP reset as an exception rather than valid connection closure. The reviewed
harness accepts EOF or reset and retains the positive healthy-relay control.

## Reproduction and external resource boundary

`build.sh` now omits the shared ccache mount when cache-disabled, isolates build
networking, and records source HEAD/tree, submodule revisions, patch hashes,
compiler/CMake and executable versions. The two-build runner compares all these
alongside package manifests, builder ID and executable hashes. Generic defaults
remain portable: `MEOW_JOBS` still works, with no dated lock or forced resource
policy in `build.sh`.

[`chain/network-build-guard.sh`](../chain/network-build-guard.sh) is the opt-in
swarm policy: gate before lock, acquire shared flock, recheck, release/retry if
insufficient; one compiler job; uniquely named 4 GiB/no swap/two-CPU containers
for build and existing child tests. Each clean build gets its own gate/lock.
A durable detached launcher was started early. Before any source tree existed,
its original lock-holding memory waiter was replaced, preserving the log, to
avoid starving other tracks while idle.

At the [recorded resource-boundary snapshot](evidence/swarm-2026-09-12/network/reproduction-status.json),
neither `first` nor `second` source tree existed. Available RAM readings stayed
below the required 5 GiB, mostly 2–3 GiB; disk remained about 38 GiB free.
[Wait log](evidence/swarm-2026-09-12/network/reproduction-wait.log) preserves the
boundary. No compiler or clean-build hash is invented. The durable waiter remains
alive and releases the lock between checks:

- PID: `19457`; launcher:
  `/tmp/meow-swarm-network-20260912-run/reproduce.sh`.
- Live log: `/tmp/meow-swarm-network-20260912-run/reproduction.log`.
- Completion exit: `/tmp/meow-swarm-network-20260912-run/reproduction.exit`
  (created only after completion).
- Output: `/tmp/meow-swarm-network-20260912-run/reproduction/{first,second}`.
- Immutable builder:
  `sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e`.

Parent integration must collect the eventual exit, both source/artifact manifests
and build logs before claiming clean fifteen-patch reproducibility. The waiter
uses this worktree's scripts, so retain it until completion. It never commits or
pushes. Independent toolchain reconstruction/cross-host proof remain separate.

## Fresh primary-source findings and factual corrections

GitHub API retrieval succeeded after web-open failures. Raw PR, changed-file and
check-run responses are preserved with a [compact head/status summary](evidence/swarm-2026-09-12/network/upstream-summary.json).
The following are snapshots, not guarantees about future upstream status:

| PR | Exact head | Observed readiness |
|---|---|---|
| [11283](https://github.com/monero-project/monero/pull/11283) | `a58e7b0227d9a29fb3a20068f019b1b6a561b17e` | Open, unmerged; 3 failed checks among 18 returned |
| [10361](https://github.com/monero-project/monero/pull/10361) | `3d3ed652469b0ce1852f47e8ded55b97bae60cc2` | Open, unmerged; 1 failed check among 28 returned |
| [10724](https://github.com/monero-project/monero/pull/10724) | `6fdb42b56b7fd0d78d1e6fa659eb73bb249d53b9` | Open, unmerged; detailed failures in receipt |

All reported `mergeable=true`, `mergeable_state=unstable`. Textual mergeability
is not successful CI, integration readiness, audit completion or release status.
Failure causes were not diagnosed; no inference that a PR caused each failure.

**Correction:** #11283 prepares peer handling for possible early relay; it does
not itself implement relay-before-expensive-validation. The changed source
explicitly describes that behavior as future work. It sets `m_no_drop_offense`
after successful PoW (including the alternative-chain path), changes treatment
of cached invalid blocks, and avoids treating cached-invalid blocks as successful
peer progress. The proposal preserves rejection while avoiding certain peer
disconnections. Its discussion of multi-second FCMP validation/propagation is
an upstream motivation, not a measurement produced here.
[Exact diff receipt](evidence/swarm-2026-09-12/network/pr-11283-files.json).

**Correction:** #10361 and #10724 are tower-cycle/hash/tree-building component
work with dependency stacks. They are not complete daemon/wallet FCMP integration.
The [pinned integration document linked by #10724](https://github.com/j-berman/monero/blob/7c6205403ed88924d48eb0dfb0a71140cd7902bb/docs/FCMP%2B%2B_INTEGRATION.md)
describes Rust FFI, trees/database and transaction representation, and has TODO
sections for verification, consensus and wallet sync. That document alone
cannot establish the current state of all development branches. Our pinned
Meownero source has no `src/fcmp_pp`, and the reused binary cannot faithfully
execute an FCMP transaction/proof workload. No upstream PR was applied.

**Correction:** equal block weights at 90 seconds raise nominal capacity/second
by 4/3. Matching subsidy/second alone does not isolate block timing. The planned
90 budget is 0.75 of the 120 budget, including minimum and dynamic effects, with
configured/RPC-reported/actually-enforced budgets distinguished.

## Normative experimental choices and missing integration

These choices are local benchmark design, **not adopted production policy**.
[Executable inventory and detailed run contract](../spikes/network-benchmark/README.md)
retain 120/0.9 and compare 90/0.675 at 7.5 billion nominal atomic units/second.
At the floor, the proposed 90 penalty-free/max weights are 225,000/450,000 vs
300,000/600,000. Actual loaded issuance needs reward-penalty measurements too.

Matched dynamic capacity needs real acceptance/rejection boundary probes under
short/long median and surge histories; merely scaling the floor or limiting
offered load is insufficient. The 100/100,000-block median windows have different
wallclock durations. Window changes/rounding require an explicit experimental
choice. Common proof/transaction mix, output-tree state, offered load/second,
hardware limits, warmup/cache treatment and wallclock observation horizon must
be recorded. Header/coinbase overhead occurs one third more often at 90 seconds;
30 vs 40 nominal blocks share a one-hour horizon, not a demonstrated security
level.

Missing deliverables: a separately built 90/0.675 binary with demonstrated
scaled dynamic capacity; complete pinned FCMP daemon/wallet/FFI integration;
valid real proof construction/spend/rejection/rollback; paired loaded network
runs; valid-PoW invalid-consensus-block P2P relay/repeated-work behavior for
#11283; shorter/heavier real fork tests and long-run measurements. The executable
inventory intentionally returns **BLOCKED_INTEGRATION**. Empty blocks, synthetic
delays and component microbenchmarks do not substitute for these receipts.

Settled policy, seed recovery, checkpoints, signer/identity/ticker decisions,
shared plans/CI/handoffs, parent checkout and other worktrees were not changed.

## Frozen input identity and exact continuation commands

A 32-file snapshot of `chain/` is preserved at
`/tmp/meow-swarm-network-20260912-run/frozen-inputs-15/chain`.
The [input manifest](evidence/swarm-2026-09-12/network/frozen-inputs-SHA256SUMS)
SHA-256 is
`6f74c265453e138cea3b3936542ef410ff3f0396ae561a8aa9a9f3eae7c3518e`.
It includes all fifteen patches, upstream lock, build/test scripts and the opt-in
guard. The existing waiter is deliberately preserved: **it still resolves the
byte-identical worktree paths**, not the snapshot directory. Parent must keep
this worktree's chain files present and unchanged until both builds complete.
The frozen copy provides exact fallback inputs and a check against accidental
drift; it does not retroactively change a running shell's arguments.

No resume action is needed while PID 19457 is alive: the guard automatically
starts the compiler only after its memory/disk checks pass. Monitor with:

```bash
kill -0 19457
ps -p 19457 -o pid,stat,args
tail -20 /tmp/meow-swarm-network-20260912-run/reproduction.log
```

Only if the waiter has exited **before either source tree was created**, the
following restarts the two-build operation from the frozen copy in a fresh output
path. It refuses an active waiter or any existing first/second build tree:

```bash
bash <<'SH'
set -euo pipefail
run=/tmp/meow-swarm-network-20260912-run
if kill -0 19457 2>/dev/null; then echo 'Existing waiter is alive; preserve it'; exit 75; fi
[ ! -e "$run/reproduction/first" ] && [ ! -e "$run/reproduction/second" ]
cd "$run/frozen-inputs-15"
sha256sum -c SHA256SUMS
export MEOW_BUILDER_IMAGE=sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e
export MEOW_REPRO_BUILD_RUNNER="$PWD/chain/network-build-guard.sh"
# Run in a durable terminal; output directory must be new.
bash chain/test-reproducibility.sh "$run/resumed-clean15"
SH
```

For the **preserved existing waiter**, collect successful evidence with this
command. Exit 75 means the compiler/build pair has not completed; a nonzero
recorded build exit is a failure and must be investigated, not labeled reproduced.
The command verifies frozen/worktree input identity and all compared receipts,
then copies only compact provenance/logs into a new unique collection directory:

```bash
bash <<'SH'
set -euo pipefail
run=/tmp/meow-swarm-network-20260912-run
[ -f "$run/reproduction.exit" ] || { echo 'Waiter/builds have not completed'; exit 75; }
[ "$(cat "$run/reproduction.exit")" = 0 ]
cd /tmp/meownero-swarm-20260912-network
sha256sum -c "$run/frozen-inputs-15/SHA256SUMS"
(cd "$run/frozen-inputs-15" && sha256sum -c SHA256SUMS)
for item in BUILDER_IMAGE_ID packages.txt SHA256SUMS SOURCE_REVISIONS SUBMODULES INPUT_SHA256SUMS VERSIONS; do
  diff -u "$run/reproduction/first/$item" "$run/reproduction/second/$item"
done
out=$(mktemp -d "$run/collected-clean15-XXXXXX")
cp "$run/reproduction.log" "$run/reproduction.exit" "$out/"
cp "$run/frozen-inputs-15/SHA256SUMS" "$out/frozen-inputs-SHA256SUMS"
for arm in first second; do
  mkdir "$out/$arm"
  for item in BUILDER_IMAGE_ID packages.txt SHA256SUMS SOURCE_REVISIONS SUBMODULES INPUT_SHA256SUMS VERSIONS; do
    cp "$run/reproduction/$arm/$item" "$out/$arm/"
  done
  cp "$run/reproduction/$arm.log" "$out/$arm/run.log"
  for item in cmake.log make.log CMakeCache.txt; do
    cp "$run/reproduction/$arm/monero/build/release/$item" "$out/$arm/"
  done
done
printf 'Verified collection: %s\n' "$out"
SH
```

Parent must review the collected result and integrate durable evidence separately.
This checkpoint does not mark the pending reproduction complete.
