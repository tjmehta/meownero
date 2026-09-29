# Vanguard two-process delivery (TJS-953)

**Status:** TJS-958 independently accepted the two-process code commit `10a26e03fc580ff342d849162a93157556804dd1` and receipt bundle at `572a1e2588353d5b8ce0d9edd29686cd5668375a` as bounded engineering evidence, with no required findings. Its verdict is attached to TJS-958 as `tjs958-verdict-10a26e0.md` (SHA-256 `4715d742ec976d831478e87369688f62e14c019ff035dad24576dcff722beb39`). TJS-959 accepted the earlier bounded two-core, one-process slice at `d5b4afbb82c1859cf98012555a6dddde3d0c6c42`; its correction established full reverse proof re-verification only for core B in that slice. TJS-958's later DEBUG probe established full reverse proof re-verification for both processes in the two-process candidate. This is not a security-readiness claim.

## Harness and controls

The tested code commit is `10a26e03fc580ff342d849162a93157556804dd1`; the pinned upstream FCMP++ commit remains `e151643c5269c83bf24a83b2548e2493876026b2`. `vanguard/sync/process_tests.cpp` forks before either core starts. The parent and child each initialize one offline FAKECHAIN `cryptonote::core` with separate LMDB directories. The parent sends serialized transactions and blocks to the child through length-prefixed anonymous pipes and waits for block contexts and state responses. `processes.tsv` records distinct PIDs in each run. Both processes run inside one network-disabled container; this exercises local serialized delivery, not daemon P2P or socket transport. The accepted exact04 harness and fixture were not changed.

The two processes admit the valueless FCMP++ spend and converge on block hash, reference root/depth, key-image state, chain presence and pool state after block 137 arrives before 136 at the peer and is retried, then after the peer restarts with its database retained. Subsequent blocks are admitted after restart; this harness does not pull a backlog accumulated during downtime. The parent builds a competing v17 branch from height 80 through 143 and sends its blocks to the peer. Both converge on a changed trusted root at reference block 140, absent confirmed spend and rolled-back key image. Named controls reject the old spend on the new root in a supplemented block and through each process's retained pool entry, without missing transactions or state change.

For the reverse switch, the parent flushes its retained spend before receiving old alternative block 141 with the spend as a supplement. Named checks and `core-a.log` record removal and subsequent admission of the same txid. Old extension blocks 142–144 are delivered to both processes. They restore the original root, confirmed spend and spent key image, empty their pools, and agree on the final tip. `controls.tsv` records both stale-root paths, the alternative-block admission context and the reverse switch contexts. The candidate's INFO-level logs do not establish the reverse proof-cache path; TJS-958's DEBUG probe records full verification on both processes.

## Exact receipt

From this worktree and the prepared pinned scratch checkout and Rust cache:

```sh
python3 -B vanguard/run-sync-process.py --out build/vanguard-sync-process-exact02
python3 -B vanguard/verify-sync-process.py build/vanguard-sync-process-exact02
python3 -B vanguard/verify-sync-process.py research/evidence/vanguard-sync-process-tjs953-2026-09-29-exact02
sha256sum research/evidence/vanguard-sync-process-tjs953-2026-09-29-exact02/MANIFEST.sha256
```

The committed bundle is `research/evidence/vanguard-sync-process-tjs953-2026-09-29-exact02/`. `receipt.json` pins the exact code commit and five source hashes, upstream revision, accepted builder image and toolchain, complete Docker commands, binary hash, wall times and cgroup metrics. The verifier also checks that the receipt commit is an ancestor of the current head and that its Git source blobs match the recorded hashes. The manifest SHA-256 is `19d0bb435847e5b42287c5de99050df57ab6a962da941f11f12c0c93f58c3d17`. The binary is 24,639,296 bytes, SHA-256 `4e463ba0e34e4fac99aeefc5273a17063a02e77b3822a856634a7151524f74f6`.

| Stage | Wall seconds | CPU seconds | Peak bytes | Exit |
| --- | ---: | ---: | ---: | ---: |
| Build | 18.25 | 17.61 | 1,191,321,600 | 0 |
| Run 1 | 29.32 | 29.88 | 916,152,320 | 0 |
| Run 2 | 31.03 | 31.49 | 917,233,664 | 0 |

All containers used `--pull=never --network=none --cpus=2 --memory=4g --memory-swap=4g --pids-limit=256 --ulimit core=0`; cgroup OOM and OOM-kill counts were zero. Both runs and the receipt verifier passed 508 named checks each. Their check streams are byte-identical, SHA-256 `216434bdf79eb84eded35d2b8a5c6e7366e354804addfe9edc38635a6a8183c2`. Synthetic keys and proof randomness change absolute roots and tips between runs; per-run values are in `states.tsv`.

TJS-958's read-only exact-commit QA accepted this local serialized two-process delivery as closing the stated gate. Its clean-family reproduction passed 508 checks in each of two runs with byte-identical binary and check-stream hashes, and its additive probe passed 514 checks; see the attached verdict for six non-required findings and the probe's proof-cache observations. Wallet restore/subsequent spend, daemon P2P/socket transport, broader cases and loaded performance remain separate. No core change, public network, remote push, value spend, publication, external audit or security-readiness claim is involved.
