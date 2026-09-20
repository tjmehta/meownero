# TJS-229: testnet v0 two-peer launch recipe

2026-09-20. Packaging/configuration implementation and bounded local verification complete.

Delivered `chain/testnet-v0/launch.py`, operator `README.md`, selected profile,
source/overlay/build baseline, actual-command refusal checks and a separate
receipt verifier. Thirty-seven baseline files plus six recipe files are pinned
in the final run's `INPUTS.sha256`. The accepted binary matched TJS-40 SHA-256
`b79cb49dbea95c0eeff7dca8c945d65f4fab3d49fb626fcbe7a9343569d4a2c1`.
No rebuild or consensus change was made.

## Observed final run

- Both real P2P peers reached top index 4 / RPC height 5.
- Common hash `a13d5cb6d8d91c0f23a6da847a9b438a3eb435ba1342df1f26b4724f4669c341`.
- Common cumulative work 27; emission 36000000000000 atomic units, or 36 MEOW; fees zero.
- Native daemon RandomX miner, native DAA, ordinary timestamps, no fixed difficulty.
  Blocks originated only on peer 0 and reached peer 1 through P2P.
- Live zero-reward genesis, 9 MEOW reward, 90 s target and v16 at height 1 verified.
- Loopback-only explicit peers/RPC inside Docker `--network none`, no public ports.
  Isolated fresh data directories; no inherited config; no wallet or pool started.
- Launcher, container and both daemon exits 0. Owned container removed.
- Peak container memory 2777055232 bytes; elapsed 25.379 s.
  Caps: 4 GiB, no swap, two CPU quotas, 256 processes; zero OOM/limit events.

## Verification and evidence

Twelve actual-launch admission refusals passed: wrong genesis, genesis reward,
subsidy, target, fork version, fork height, pool profile, enabled pool, prefix,
testnet mode, stale directory and binary hash. All returned exit 2 with a
specific message before node launch. The accepted-input control exited 0.
The stale-directory sentinel survived unchanged.

The separate verifier returned `PASS_RECEIPT_RECONCILIATION`: linked canonical
headers, per-block work/reward sums, two peers' final RPC totals, profile
readback, P2P traffic, network isolation, resource limits and clean exits agree.
All 43 recipe/input checksums passed. Python syntax and authored-code whitespace
checks passed. Raw daemon logs retain their original trailing whitespace.

Raw public receipts: [evidence](evidence/testnet-v0-launch-tjs229-2026-09-20/).
Operator entry point: [recipe](../chain/testnet-v0/README.md).
The evidence manifest covers public logs, exact process commands, RPC outputs,
exit codes, refusal cases and verification output. Node databases are retained
only in `build/testnet-v0-tjs229-run02/data`; they are not in the public archive.
No seeds/private keys were created, read or copied.

## Disposition and limits

The assigned candidate assembly/launch packaging check is complete. QA/Release
can use the documented commands and package for its independent operator
acceptance in the broader v0 journey. This author-run witness and separate
receipt checker are not independent operator or toolchain reproduction.

Pool profile admission is a compatibility declaration only. No pool binary,
writer file or pool port was changed, launched or independently accepted.
TJS-187/TJS-224 retain that work. No fallback chain, public service, external
push, mainnet launch, protocol change or paid-auditor prerequisite was added.

This finite empty-block witness does not close late-peer/restart sync, payment,
wallet recovery, reorg, F3, F4, F7, 90-second GO or broader release gates.

**TJ decision:** isolated testnet v0, selected 9/90, reuse matching TJS-40 build.
**Observed behavior:** fresh native-mode peers converge and incompatible launch
inputs are refused before startup. **Agent proposal:** QA/Release reuse this
package for the next integrated operator check. Historical statements that no
versioned two-peer launcher exists are superseded for this bounded scope.
