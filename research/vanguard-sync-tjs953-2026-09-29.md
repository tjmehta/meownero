# Vanguard bounded sync and reorg diagnostic (TJS-953)

**Status:** partial engineering witness, not TJS-953 acceptance. The complete
two-process integration and key-image reapplication after the competing-branch
switch are blocked pending the actions below. Independent exact-commit QA has
been requested separately. No public network, wallet keys of value, mainnet,
remote push, spend, external audit or readiness claim is involved.

## Pinned implementation and scope

The code commit is `30d520af7eb9c1961624857443b1b6f77a452125`, on top of
accepted TJS-751 `eb81b9296fe5d0eb8a077e9a415c84e590fadb07`. It compiles
the pinned upstream FCMP++ source `e151643c5269c83bf24a83b2548e2493876026b2`
and uses the accepted v0 builder image ID
`sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e`.
The source lock remains unchanged.

`vanguard/sync/sync_tests.cpp` uses two independent LMDB folders and actual
`cryptonote::core` instances in FAKECHAIN mode. It transports serialized
blocks/transactions through a deterministic local delivery sequence; there is
no P2P transport or second process. Its original FCMP++ transaction and chain
come from pinned upstream `tests/core_tests/fcmp_pp.cpp`, compiled unchanged.
One peer receives block 137 ahead of 136, then receives the predecessor and
continues. It is restarted with `--keep-fakechain` and its database retained.

The fork splits after height 78. It replaces one valid synthetic coinbase
output at height 79 and changes subsequent block hashes. This output enters
the FCMP++ tree before the transaction's reference height 138. A fresh branch
through height 141 overtakes the original height-139 branch. Both cores then
agree on tip hash, stored root/depth, transaction absence, and unspent key
image. The stale transaction leaves both pools. A candidate block with the
original transaction supplied explicitly is rejected on the new root, while
the active branch remains unchanged. This last control avoids mistaking a
missing-pool-transaction rejection for a proof rejection, although the exact
internal rejection stage still merits independent QA inspection.

## Exact-commit receipt

Run from the task worktree with the prepared pinned scratch checkout and Rust
cache:

```sh
python3 -B vanguard/run-sync.py --out build/vanguard-sync-exact01
python3 -B vanguard/verify-sync.py build/vanguard-sync-exact01
sha256sum build/vanguard-sync-exact01/MANIFEST.sha256
```

The exact-commit bundle is durably copied to
`research/evidence/vanguard-sync-tjs953-2026-09-29-exact01/`. Its `receipt.json`
records the complete Docker argv,
source SHA-256s, commit, pinned image and toolchain, binary hash, wall time,
cgroup CPU and memory metrics. `MANIFEST.sha256` covers the raw checks, node
databases, logs and before/after state receipts. The runner restored the
accepted upstream CMake registration after its injected build; the task
branch is clean.

| Stage | Wall seconds | CPU usage seconds | Peak bytes | Exit |
| --- | ---: | ---: | ---: | ---: |
| Warm cached build | 5.58 | 4.97 | 231,272,448 | 0 |
| Run 1 | 21.41 | 21.89 | 604,143,616 | 0 |
| Run 2 | 20.90 | 21.33 | 601,055,232 | 0 |

Each container had `--network=none --pull=never --cpus=2 --memory=4g
--memory-swap=4g --pids-limit=256 --ulimit core=0`; both runs had zero cgroup
OOM/OOM-kill events. The binary is 24,602,760 bytes, SHA-256
`c644394e32f2ca94939b9d61bb8e4628ada8acda6aac6a747c295e98a16b2df8`.
Both runs passed 435 recorded checks and the receipt reconciler. The named
check streams match at SHA-256
`414fd305690e1836f9f2eccd44ed2c0a937e3066adf68da4c477a6d0008786e0`.
The manifest SHA-256 is
`d30c81e0abe403e104266f768e5a0306cc0e90cbfa361c56c7da963450152054`.
Synthetic account and proof randomness changes chain and root hashes between
runs; each run's exact values are in `run1/states.tsv` and `run2/states.tsv`.

In run 1, both original nodes held tip
`3f6571f3a550ee63b2bccebdfd2e99b42a32437c5b02583541c2c0ffb97da947`,
root `94f46ca7471ae78b4338cbdcd050719fcfe9eb8c2d817ab210786c95f228ffdf`,
depth 2, confirmed transaction and spent key image. After the fork, both held
tip `90e20276e027ec1eab5ae12bf40a0155c75c7ab3cac24ab9d8988421fdfc5c15`,
root `01afbcb6c8c03df1ba59d43925e6c272d96a91ee423e726c8d81908ce329119a`,
depth 2, no confirmed transaction and no spent key image. Run 2 reached the
same state relationships with different synthetic hashes.

## Unaccepted reverse path and concrete blocker

Before narrowing the committed witness, a local reverse-branch trial generated
old-branch blocks 140–142, switched both cores to the competing branch, then
redelivered the old extension. The branch switch back at height 142 failed in
`Blockchain::switch_to_alternative_blockchain` (pinned upstream
`src/cryptonote_core/blockchain.cpp:1246`). The stale transaction was absent
from the pool after the first reorg. Supplying it with the last extension block
still failed. `research/evidence/vanguard-sync-tjs953-2026-09-29-reverse-attempt/`
retains `checks.tsv`, `states.tsv`, `stderr.log` and `core.log` from that attempt
(`core.log` SHA-256
`cbcd56db62106c49cce39cde82a4c9ce21ec71e904c0e3e08d0870709c970074`).
The log also reports a CARROT output being checked under pre-FCMP fork v15
during the deep rollback; that does not by itself identify the decisive failure.
Later unpublished trial variants crashed during the first branch switch, so
they are not acceptance evidence. Their identical check-stream SHA-256 is
`6fd0514b3244306e69f6f68a4905b80375602f4f1ece39dec9c7eff6770bb938`.

**Next action and owner:** Meownero Privacy Cryptography should first move the
driver to two separate processes with explicit serialized delivery and capture
the block verification context at each reverse-switch step. Reproduce the
reverse failure at the pinned commit, determine whether the old transaction is
lost as the pool is revalidated while crossing fork v15, and make the smallest
safe fix at the responsible core/pool boundary or adjust the fixture only if
the original branch is invalid by consensus. Then prove key-image reapplication
and obtain a new independent exact-commit QA verdict from Meownero Adversarial
Release Assurance. Until that happens, TJS-953 is blocked. Wallet restore,
subsequent spend, broader cases and loaded performance remain separate gates.
