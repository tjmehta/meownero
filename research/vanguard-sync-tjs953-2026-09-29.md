# Vanguard bounded sync and reorg diagnostic (TJS-953)

**Status:** TJS-959's third independent exact-commit QA accepted this bounded two-core, one-process witness as engineering evidence at `d5b4afbb82c1859cf98012555a6dddde3d0c6c42` with no required findings. Its follow-up clarifies that only core B's full reverse proof re-verification was established. TJS-953 as a whole is not accepted; the separate two-process candidate is documented in `research/vanguard-sync-process-tjs953-2026-09-29.md`. No public network, mainnet, remote push, spend of value, external audit, or security-readiness claim is involved. The accepted v0 activation, recipes, builder image, and TJS-751 slice remain unchanged.

## Current code and fixture

The code commit is `2cf3795820847e732ed2d80db654e125c34730b0`, following the earlier TJS-953 code commit `951b1eb456a98564fc9a7744c551e1c99cd2cf0d` and accepted TJS-751 base `eb81b9296fe5d0eb8a077e9a415c84e590fadb07`. The pinned upstream FCMP++ source is `e151643c5269c83bf24a83b2548e2493876026b2`. The source lock and accepted builder image are unchanged.

`vanguard/sync/fixture.cpp` is a harness-owned derivative of the pinned upstream FCMP++ generator. It adds two valueless blocks after the Bulletproof+ prerequisite and creates v17 miner outputs from height 80 onward. `vanguard/sync/sync_tests.cpp` supplies v17 header roots from each core's database. The FAKECHAIN schedule is v2 at height 1, v15 at 78, and v17 at 80. The FCMP++ spend's reference block is 140, exactly 60 blocks after the competing fork begins at 80; both branches stay on v17 during switching. The old v17→v15 confounder is absent.

Two independent LMDB folders and `cryptonote::core` instances receive serialized transactions and blocks. Block 137 arrives before 136 on one core and is retried after its parent. That core restarts with its database retained. A different v17 miner output at height 80 changes the trusted root at reference height 140, and a branch through height 143 overtakes the original height-141 branch. Both cores agree on tip, root/depth, absence of the original confirmed spend, and unspent key image. A new block with the old spend explicitly supplied and a correct new-branch header root fails FCMP++ batch verification on both cores. The `stale_root_a` and `stale_root_b` controls record failed block verification and unchanged key-image state. The `stale_root_pool_a` and `stale_root_pool_b` controls submit the same block without a supplement, taking the retained spend from each pool; both fail input verification without missing transactions. `core.log` records both rejection paths. Its v17 pool-validation line occurred during initial activation, before the spend first entered a pool.

The old branch is then delivered as an alternative. Immediately before old block 141, the harness flushes the peer's retained spend and verifies its absence. It supplies the spend with that block and verifies its admission to the peer pool; `core.log` records removal followed by admission of the same txid. Three precomputed old-branch blocks overtake the competing branch. Both cores restore the original trusted root, confirmed spend, and spent key image. `controls.tsv` records the alternative-block context and the final reverse-switch block contexts. The reverse harness is part of the code commit above.

**Pool behavior:** after switching to the competing v17 branch, both cores retain the old spend (`fork_a` and `fork_b` show pool=1). No pool-wide revalidation runs after the spend enters either pool: the version remains v17 across the switch. Pinned upstream validates retained entries lazily when building a template or including them in a block; its relay path checks the stored input-verification root, and kept-by-block entries expire after seven days. Independent QA observed template exclusion and read the relay/expiry paths, classifying this retention as acceptable for the bounded slice. This witness directly proves rejection through both supplemented and retained-pool block paths, then reverse key-image reapplication; it does not prove relay behavior or full TJS-953 acceptance.

## Exact-commit receipt

From this worktree and the prepared pinned scratch checkout and Rust cache:

```sh
python3 -B vanguard/run-sync.py --out build/vanguard-sync-exact04
python3 -B vanguard/verify-sync.py build/vanguard-sync-exact04
python3 -B vanguard/verify-sync.py research/evidence/vanguard-sync-tjs953-2026-09-29-exact04
sha256sum research/evidence/vanguard-sync-tjs953-2026-09-29-exact04/MANIFEST.sha256
```

The bundle is committed under `research/evidence/vanguard-sync-tjs953-2026-09-29-exact04/`. `receipt.json` records the complete Docker commands, exact code commit and source hashes, pinned image/toolchain, binary SHA-256, wall time and cgroup metrics. `MANIFEST.sha256` covers raw checks, states, controls, logs and databases; its SHA-256 is `b4ee2579f8f38104fd9094d45b59fbe152420794a3d38ecaeb463c5e378832dd`. The binary is 24,615,544 bytes, SHA-256 `6a35254a77a3a84fb41c948003f17f4659bd81164dfea5fe9578bbc913e7ce02`.

| Stage | Wall seconds | CPU seconds | Peak bytes | Exit |
| --- | ---: | ---: | ---: | ---: |
| Build | 18.90 | 17.87 | 1,251,897,344 | 0 |
| Run 1 | 28.52 | 28.48 | 622,120,960 | 0 |
| Run 2 | 27.17 | 27.30 | 602,943,488 | 0 |

All containers used `--pull=never --network=none --cpus=2 --memory=4g --memory-swap=4g --pids-limit=256 --ulimit core=0`; cgroup OOM and OOM-kill counts were zero. Both runs and the receipt reconciler passed 520 named checks. Their check streams match at SHA-256 `c3f926ff18586c4d5619da4a9e66bca81eb4b84a65c0c61865fe82c62bc11cbd`. Synthetic keys and proof randomness change absolute roots and tips between runs; the per-run values are in `states.tsv`. The earlier exact02 bundle remains preserved as the independently reviewed baseline; exact04 is the corrected candidate.

## Earlier evidence and correction

The earlier `3e7a5f4` diagnostic and its exact01 bundle remain preserved. Its reverse attempt crossed from v17 to v15; pool revalidation then dropped the CARROT spend, so its pool-removal check did not establish stale-root invalidation. It did not prove reverse key-image reapplication. The prior report transcribed the reverse-attempt `core.log` hash incorrectly. The correct SHA-256 of `research/evidence/vanguard-sync-tjs953-2026-09-29-reverse-attempt/core.log` is `cbcd56db62106c49b063877d6ad2bae2784180b3761c5d16bb0870709c970074`.

The independent exact-commit verdict is TJS-959 comment `358aee1a-60a4-4f8c-bf5f-9e3d5983e0b5`; its correction is comment `1bb73e6a-d45a-4fac-b4a9-5c6bff9a1368`. The separate two-process candidate requires its own independent QA. Wallet restore/subsequent spend, broader cases and loaded performance remain separate unaccepted gates.
