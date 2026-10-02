# TJS-1032 independent exact-commit QA: daemon restore and reorg

## Blocked on TJ

None.

## Verdict

**The bounded scenario reproduced. The verifier has two material coverage gaps.**
Two fresh network-disabled runs passed the CARROT restore, reorg rollback,
restored FCMP++ spend, and both negative controls. The rebuilt daemon and wallet
RPC binaries were byte-identical to the writer's receipt. A hash-consistent
mutation of the recorded binary hash, and another of one daemon's confirmed tip,
each still made `verify-daemon-restore.py` print PASS. Accordingly this is a
qualified scenario PASS and an adverse verifier-completeness finding, not a clean
unqualified QA verdict. No observed daemon regression is asserted. This is
agent-reviewed bounded engineering evidence, not an external audit.

## Changed

Added only this QA report and the [QA receipt bundle](evidence/vanguard-daemon-restore-tjs1032-2026-09-30/). No writer-owned `vanguard/` file was edited.
The [command ledger](evidence/vanguard-daemon-restore-tjs1032-2026-09-30/commands.md)
records reproduction commands, exits, and intentional verifier failures. The
[comparison](evidence/vanguard-daemon-restore-tjs1032-2026-09-30/comparison.json)
contains SHA-256 hashes for `result.json`, `events.jsonl`, `wire.jsonl`,
`containment.json`, and `network-live.json` in each of the writer's two runs and
both QA runs. The [comparison script](evidence/vanguard-daemon-restore-tjs1032-2026-09-30/compare.py)
contains the independent semantic assertions. The [tamper script](evidence/vanguard-daemon-restore-tjs1032-2026-09-30/tamper.py)
and [results](evidence/vanguard-daemon-restore-tjs1032-2026-09-30/tamper-results.json)
preserve all four hash-consistent and ordinary controls.

## Verified

### Exact candidate and source

| Item | SHA / pin |
| --- | --- |
| Code commit | `9057e7bc220b5b690e978b69f3dcb583402807ce` |
| Committed evidence and detached QA checkout | `40be047b6ed89745c94d22b3a36537b138bc91ee` |
| Parent of code diff | `918d50cf` |
| Original `MANIFEST.sha256` | `24b4ecdb2bac9f4b4114e1745632ce1dcb89217c917684c7a735b618a8f1ac2a` |
| QA restore `bundle/MANIFEST.sha256` | `21ecbfb2b8c043e59dfba7af5daf8f2c1820f6c41d21bd25554ac5eafc111f10` |
| QA P2P `p2p-step0/MANIFEST.sha256` | `1bd880b11274ee65de184cd0fda5b453f74043fd5c819777882218eefe0bf8a1` |
| QA evidence `QA-MANIFEST.sha256` | `629821edffa146c580263f37cfa7ea73487fee1bcfa635dcc5a5255a250a930c` |
| Upstream Monero candidate | `e151643c5269c83bf24a83b2548e2493876026b2` |
| Pinned Cargo.lock | `6a8e9217b94169e26a8f595cb528d72c19dc2f5484e903c57328c594d62f8239` |
| Builder image | `sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e` |

`git diff --exit-code 9057e7b 40be047 -- vanguard` was empty, and the six
reviewed source hashes in the original and QA receipts match. The prepared
upstream source was copied with its prior `build/vanguard` directory excluded.
The QA CMake configure and target build therefore compiled from a fresh build
directory. `source-lock.json` pins sources, Cargo.lock, toolchain and builder; it
does **not** list expected output-binary hashes. Binary comparison is against
the original `receipt.json` and direct SHA-256 of the rebuilt files.

| Rebuilt binary | SHA-256 | Bytes | Writer receipt |
| --- | --- | ---: | --- |
| `monerod` | `5ba64f2e04e21550575b396b250bcebba01471c4246d74d88e679f06cee86509` | 29,872,608 | identical |
| `monero-wallet-rpc` | `cf2ea70c353c5124e86f2bfac46da28fad2993af28636ab28ca7ea9db81678f2` | 33,545,392 | identical |

The fresh build took 1433.239 seconds; restore runs took 66.857 and 70.661
seconds. All stage exits were 0. The exact Docker arrays in
[`bundle/receipt.json`](evidence/vanguard-daemon-restore-tjs1032-2026-09-30/bundle/receipt.json)
include `--pull=never --network=none --cpus=2 --memory=4g --memory-swap=4g
--pids-limit=256`, capability drop, no new privileges, and zero core dumps.
Peak cgroup memory was 3,769,704,448 bytes for the build, then 1,013,641,216
and 992,268,288 bytes. Every cgroup OOM and OOM-kill count was zero. The
[configure log](evidence/vanguard-daemon-restore-tjs1032-2026-09-30/configure.log)
records the successful fresh CMake configure.

### Four-run comparison and domain findings

All four public bundles passed their manifests and the writer's clean-bundle
verifier. `compare.py` additionally checked the state transitions and exact
source/binary receipts independently. All four had the same 33-event sequence.
Wire frame counts were 104 and 106 for the writer runs, 106 and 106 for the QA
runs; the extra frames were handshake timing differences. Transaction IDs,
key images, block hashes, frame hashes, and timings are newly generated and
therefore differ. The [comparison](evidence/vanguard-daemon-restore-tjs1032-2026-09-30/comparison.json)
records all five requested per-run file hashes and the per-direction command
histograms, so byte differences are visible rather than silently normalized.

1. **CARROT restore:** `daemon-restore.py:112-155` creates a 5 × 10¹² atomic-unit
   receiver output, decodes its transaction as FCMP++ RCT type 7 with
   `carrot_v1` output targets, then restores from the 25-word seed at the block
   before the output. The restored wallet and hard rescan match the original
   address, one output, amount, public key, block height, balance, and key image
   in each run. These are recorded in `carrot_received` and
   `restored_and_rescanned` as well as `result.json`.
2. **Reorg and pool discovery:** `daemon-restore.py:157-224` partitions the two
   peers, creates an 11-block old branch containing a 2 × 10¹² recipient output,
   then a 12-block competing branch. After rejoin both daemons converge; the old
   tip is orphaned. Both original and restored wallets discover the orphaned
   transaction in their own pools. Their temporary balance is 7 × 10¹² with
   5 × 10¹² unlocked, while confirmed outputs stay at the original one-output
   state. After flushing that pool transaction, both wallet states return to the
   original 5 × 10¹² balance. The two per-wallet `get_transfers(pool=True)`
   queries at `daemon-restore.py:198-209` are the behavior added in `9057e7b`;
   all four runs observed the 2 × 10¹² pool row in **both** wallets.
3. **Restored FCMP++ spend:** `daemon-restore.py:233-290` constructs a separate
   same-key-image alternative offline, then spends the stable output from the
   restored wallet. Its RCT type is 7 and outputs are `carrot_v1`. Both daemon
   pools contain the restored spend at height 94. After node 1 mines it, both
   tips agree at height 95, both key-image statuses are `[1, 1]`, neither pool
   retains it, and original/restored wallet final states are equal. Before
   confirmation, pooled key-image statuses were `[0, 2]` in all four runs.
4. **Negative controls:** the orphan-output spend is constructed offline, then
   both daemons return `Failed, invalid_input=True`; the confirmed-input replay
   is a **distinct** transaction ID using the same key image, and both daemons
   return `Failed, double_spend=True, invalid_input=True`. The before/after
   daemon snapshot is unchanged for both attempts. Public daemon logs also
   show `tx verification failed: invalid input` and `double spend, invalid
   input` on both nodes in both QA runs. This is an observed daemon refusal,
   not merely an assertion in the verifier.
5. **Containment:** each live and shutdown receipt lists only `lo`, no routes,
   a mode-0600 Unix bridge, five live loopback listeners, and ten listeners
   before process shutdown. All seven owned processes exited 0 per run. No
   public network or mainnet was used.

### Step-0 fixes

`daemon-p2p.py:378-381` takes the state snapshot before injecting the duplicate
transaction. `daemon-p2p.py:433-435` requires rollback statuses `[2, 2]` and
the transaction in both pools. `verify-daemon-p2p.py:69-71` requires the same
transition in the receipt. `test-daemon-p2p-refusals.py:31-50` makes a
hash-consistent altered receipt with `[0, 0]` and empty pools and confirms
the verifier rejects it. It tests the rollback verifier, not the snapshot
timing directly. For that timing path, the extra fresh one-run native P2P
scenario executed the duplicate injection and unchanged-state assertion and
passed. Its [P2P bundle](evidence/vanguard-daemon-restore-tjs1032-2026-09-30/p2p-step0/)
also passed the manifest, verifier, and refusal test. The fresh result has
confirmed `[1,1]`, rolled back `[2,2]`, and the spend in both pools.

## Defects and practical limit

1. **Binary hash is not checked by the restore verifier.**
   `vanguard/verify-daemon-restore.py:56` checks only that the `binary` object
   has the two expected keys. Replacing `binary.monerod.sha256` with 64 zeros
   and recomputing the manifest still prints
   `PASS_DAEMON_RESTORE_RECEIPT_RECONCILIATION`. The independent rebuild above
   does establish equality for these exact original receipts; the verifier
   alone does not.
2. **Cross-daemon confirmed-tip divergence is accepted by the restore verifier.**
   `vanguard/verify-daemon-restore.py:85-90` checks pool and key-image status
   but does not compare `pooled.tips` or `confirmed.tips` across nodes, nor bind
   `final_tip` to the confirmed snapshot. Changing one confirmed tip hash in
   `run1/public/result.json` and its matching event, then rehashing the
   manifest, still prints PASS. The actual scenario does wait for equal tips
   at `vanguard/daemon-restore.py:275-278`; `compare.py` checked equality in
   all four unmodified receipts. This is a verifier coverage defect, not an
   observed convergence failure.

The committed TJS-1003 and TJS-1010 outcomes remain closed. These findings
belong to this QA issue and should be considered before treating the restore
verifier's PASS string as complete evidence. Performance under load, fee paths,
and mining payouts were outside this review and remain separate integration
gates. No security, mainnet, or release readiness conclusion follows.

## Unconfirmed / next decision

The receipt verifier needs checks for recorded binary hashes against a trusted
rebuild or pin and for equal daemon tips at each claimed convergence point.
The existing Step-0 refusal test could isolate the missing-pool mutation from
the key-image mutation so each predicate is independently exercised. These are
bounded follow-up fixes for the writer; this QA task is complete with an
adverse verifier finding.
