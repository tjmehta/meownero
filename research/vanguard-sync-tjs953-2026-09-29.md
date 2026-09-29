# Vanguard bounded sync and reorg diagnostic (TJS-953)

**Status:** exact-commit two-core witness ready for fresh independent QA, not TJS-953 acceptance. Both cores share one process and receive serialized local delivery. Two-process delivery is a separate required gate. No public network, mainnet, remote push, spend of value, external audit, or security-readiness claim is involved. The accepted v0 activation, recipes, builder image, and TJS-751 slice remain unchanged.

## Current code and fixture

The code commit is `951b1eb456a98564fc9a7744c551e1c99cd2cf0d`, following the earlier TJS-953 commit `3e7a5f4c028adb1a42dd07eacd8c99d56e8bf287` and accepted TJS-751 base `eb81b9296fe5d0eb8a077e9a415c84e590fadb07`. The pinned upstream FCMP++ source is `e151643c5269c83bf24a83b2548e2493876026b2`. The source lock and accepted builder image are unchanged.

`vanguard/sync/fixture.cpp` is a harness-owned derivative of the pinned upstream FCMP++ generator. It adds two valueless blocks after the Bulletproof+ prerequisite and creates v17 miner outputs from height 80 onward. `vanguard/sync/sync_tests.cpp` supplies v17 header roots from each core's database. The FAKECHAIN schedule is v2 at height 1, v15 at 78, and v17 at 80. The FCMP++ spend's reference block is 140, exactly 60 blocks after the competing fork begins at 80; both branches stay on v17 during switching. The old v17→v15 confounder is absent.

Two independent LMDB folders and `cryptonote::core` instances receive serialized transactions and blocks. Block 137 arrives before 136 on one core and is retried after its parent. That core restarts with its database retained. A different v17 miner output at height 80 changes the trusted root at reference height 140, and a branch through height 143 overtakes the original height-141 branch. Both cores agree on tip, root/depth, absence of the original confirmed spend, and unspent key image. A new block with the old spend explicitly supplied and a correct new-branch header root fails FCMP++ batch verification on both cores. The `stale_root_a` and `stale_root_b` controls record failed block verification and unchanged key-image state; `core.log` records the `verify` batch failure and `txpool` v17 validation.

The old branch is then delivered as an alternative, with the spend explicitly supplied alongside its height-141 block on the peer. Three precomputed old-branch blocks overtake the competing branch. Both cores restore the original trusted root, confirmed spend, and spent key image. `controls.tsv` records the alternative spend delivery and the final reverse-switch block contexts. The reverse harness is part of the code commit above.

**Open pool finding:** after switching to the competing v17 branch, both cores retain the old spend in their pools (`fork_a` and `fork_b` show pool=1), although blocks containing it fail FCMP++ verification. Pool revalidation runs at v17 but does not evict this stale-root entry. This differs from the old fixture's v15 eviction and needs independent QA assessment and a separate owner decision within the no-core-change boundary. The witness proves block rejection and reverse key-image reapplication, not pool eviction or full TJS-953 acceptance.

## Exact-commit receipt

From this worktree and the prepared pinned scratch checkout and Rust cache:

```sh
python3 -B vanguard/run-sync.py --out build/vanguard-sync-exact02
python3 -B vanguard/verify-sync.py build/vanguard-sync-exact02
python3 -B vanguard/verify-sync.py research/evidence/vanguard-sync-tjs953-2026-09-29-exact02
sha256sum research/evidence/vanguard-sync-tjs953-2026-09-29-exact02/MANIFEST.sha256
```

The bundle is committed under `research/evidence/vanguard-sync-tjs953-2026-09-29-exact02/`. `receipt.json` records the complete Docker commands, exact code commit and source hashes, pinned image/toolchain, binary SHA-256, wall time and cgroup metrics. `MANIFEST.sha256` covers raw checks, states, controls, logs and databases; its SHA-256 is `cdd1d341a022895008229e02e568c78aa24c49ceb0b612cc0fa685b5d3059d51`. The binary is 24,611,448 bytes, SHA-256 `9b2ea1dfd848b6d10739a4ea280ca9ec5ff35e452582e2ea0072ae5976d037a5`.

| Stage | Wall seconds | CPU seconds | Peak bytes | Exit |
| --- | ---: | ---: | ---: | ---: |
| Build | 23.07 | 20.54 | 1,369,145,344 | 0 |
| Run 1 | 30.88 | 30.70 | 622,309,376 | 0 |
| Run 2 | 37.44 | 34.24 | 617,734,144 | 0 |

All containers used `--pull=never --network=none --cpus=2 --memory=4g --memory-swap=4g --pids-limit=256 --ulimit core=0`; cgroup OOM and OOM-kill counts were zero. Both runs and the receipt reconciler passed 515 named checks. Their check streams match at SHA-256 `fdb2f26bdcc99b573589264cb3b05e8db046c74bcd2a8e86ff41e3c5a94b1c5d`. Synthetic keys and proof randomness change absolute roots and tips between runs; the per-run values are in `states.tsv`.

## Earlier evidence and correction

The earlier `3e7a5f4` diagnostic and its exact01 bundle remain preserved. Its reverse attempt crossed from v17 to v15; pool revalidation then dropped the CARROT spend, so its pool-removal check did not establish stale-root invalidation. It did not prove reverse key-image reapplication. The prior report transcribed the reverse-attempt `core.log` hash incorrectly. The correct SHA-256 of `research/evidence/vanguard-sync-tjs953-2026-09-29-reverse-attempt/core.log` is `cbcd56db62106c49b063877d6ad2bae2784180b3761c5d16bb0870709c970074`.

Independent exact-commit review is required on this new candidate. Two-process delivery, wallet restore/subsequent spend, broader cases and loaded performance remain separate unaccepted gates. TJS-958 remains dependency-gated.
