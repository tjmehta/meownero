# Vanguard transaction/core integration candidate

Status: author build, two executions and eight receipt-refusal controls passed. Independent exact-commit transaction QA is still required. This report does not declare acceptance.

The prerequisite boundary gate passed. Meownero Adversarial Release Assurance accepted exact commit `5c2a031ba075028b30899366676e853173208fcd` in TJS-753 with no required findings. Its report is `research/evidence/vanguard-boundary-tjs753-2026-09-26/review-verdict.md`. The accepted V1 and V2 boundary work remains closed.

## Implementation

`vanguard/transaction/transaction_tests.cpp` compiles the pinned upstream `tests/core_tests/fcmp_pp.cpp` and `chaingen.cpp` unchanged. The former builds a synthetic chain, constructs a Bulletproof+ source transaction, then calls the actual wallet functions `make_carrot_transaction_proposals_wallet2_transfer` and `finalize_all_fcmp_pp_proofs` to create an FCMP++ transaction with CARROT outputs. This includes its spend authorization, membership proof, output range proof, value commitments and fee.

The local target adds callbacks around the generated transaction's admission and confirmation events. It initializes the actual `cryptonote::core` with `FAKECHAIN` test options, offline mode, disabled DNS checkpoints and disabled fast block sync. The core uses an ephemeral LMDB database inside the network-disabled container. It does not instantiate the P2P server or an RPC server.

Before transaction admission, the callback reads the root and depth for the transaction's reference block from `BlockchainDB::get_tree_root_at_blk_idx`. It checks the claimed depth against that stored depth, expands the transaction and passes its signable message, proof, pseudo outputs and key images to the accepted Vanguard boundary. Positive controls surround proof-suffix, truncated-proof, wrong-depth and corrupt-proof checks.

The node-facing path first calls the real `parse_and_validate_tx_from_blob`, then `core::handle_incoming_tx`. The candidate requires whole-blob suffix/truncation rejection at parsing. Six separately serialized mutations must parse but fail core admission: corrupt FCMP++ proof, changed fee, corrupt range proof, changed CARROT view tag, unavailable reference block and wrong depth with a matching serialized proof length. Every rejection must leave the pool empty and chain tip/height unchanged. The original generated transaction must subsequently enter the pool, enter the next block, leave the pool after confirmation and mark its single key image spent.

This target tests the boundary alongside upstream core admission. It does not replace the node's verifier with the Vanguard wrapper. The node retains its existing full transaction validation, database root lookup and depth checks. The local boundary verifies an FCMP++ proof and does not itself validate range proofs, balance, reference-block eligibility or double spending.

Both executions passed all 53 named checks. The runner creates two fresh executions. Transaction bytes, keys and proof randomness may differ between them; only the named outcomes are expected to match. Raw transaction blobs and each run's observations are retained separately.

## Reproduction

Starting with the prepared pinned upstream/cache and accepted boundary injection:

```sh
python3 -B vanguard/run-transaction.py --out build/vanguard-transaction-review-01
python3 -B vanguard/verify-transaction.py build/vanguard-transaction-review-01
python3 -B vanguard/test-transaction-refusals.py build/vanguard-transaction-review-01
```

The output directory must be new. The runner holds the established project heavy-work lock nonblocking, requires at least 5 GiB available memory and disk, uses one build job, and limits containers to two CPUs, 4 GiB memory/swap and 256 PIDs. All containers disable networking and image pulls. Execution mounts upstream source and the dependency cache read-only, disables core dumps and has a 900-second process alarm. Each container has a 1,800-second external timeout. The scratch upstream test registration is restored after the run, including failure exits handled by Python.

The pins remain upstream `e151643c5269c83bf24a83b2548e2493876026b2`, oxide `31c26d96eaadbba910ffe3613ad8b4cf9c598a93`, Rust `1.93.0`, and builder image `sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e`. Accepted v0 activation, recipes and image are unchanged.

The receipt reconciler checks source and upstream pins, file hashes, fixed outcomes, recorded containment flags, finite timings, memory caps and zero OOM events. Eight re-manifested tamper controls challenge these checks. These are self-produced receipts, not independent proof of execution. Exact-commit QA must rebuild and run the candidate before acceptance.

## Author execution evidence

The initial execution bundle is `research/evidence/vanguard-transaction-tjs751-2026-09-26-attempt01/`. It was built from the new source on top of `5c2a031`; source hashes bind those then-uncommitted bytes. All three container exits were zero, with no OOM or OOM-kill events.

| Measurement | Build | Run 1 | Run 2 |
| --- | ---: | ---: | ---: |
| Wall seconds | 372.90 | 11.44 | 12.75 |
| Cgroup peak bytes | 3028750336 | 597983232 | 596402176 |
| Transaction/chain generation seconds | n/a | 7.68 | 8.81 |
| Core initialization/replay/cleanup seconds | n/a | 3.31 | 3.52 |

Each generated transaction has one input, three CARROT outputs, 5,433 serialized bytes and a 4,256-byte FCMP++ proof. It references block 138 with two stored tree layers. The final chain height is 140. The six parseable mutations all failed core admission; whole-blob suffix and truncation failed parsing. The valid transaction entered the pool and then the chain after the rejection checks. The Vanguard proof controls passed before and after those checks.

These are warm-host measurements with previously built core/crypto libraries and the Rust cache. The first build compiled the wallet dependencies and this target; it is not a cold dependency rebuild. Generation includes the entire synthetic chain and preparatory transactions. Replay includes chain verification, all negative cases, boundary checks, core initialization and cleanup. Neither number measures transaction throughput or isolated proof latency. The upstream compiler emitted a `wallet2.cpp:3400` possibly-uninitialized warning, retained in `make.log`; this target compiles that source unchanged and does not exercise wallet refresh.

Hashes from the initial bundle:

- Result checks for both runs: `ede53effc1764462c13e5505bd2d06c46d17cbc683d62bb97a266d0d11bac1ca`.
- Binary, 24,632,304 bytes: `d9ac913cc6fef87eec110f2cdae3d127c31a3246de13c35065088b42bad5abd2`.
- Run 1 valid transaction: `3c2bd8953e0d5fcba8c7e2a225e3564b61eceb2c0a3a717dc50c38790bc8ce9d`.
- Run 2 valid transaction: `59081d5d8eb071f470abd5f887a9a4413aff6465c87c7909055162a697dee06b`.
- Evidence manifest: `f1862b27e6b190c1b4b8fbf26d12035bc354e7ca07925670801e6a67eb69d4a8`.

The receipt verifier and all eight re-manifested refusal cases passed. The upstream scratch checkout was restored to its two pre-existing test registrations. No upstream tracked implementation file changed.

The implementation is committed at `fb592a02ef7e0917532c1c915f8696b8af43f9dc`. A second author bundle, `research/evidence/vanguard-transaction-tjs751-2026-09-26-exact01/`, records that exact commit and the same source and binary hashes. Its cached build took 5.63 seconds with peak 256,966,656 bytes; runs took 14.08 and 13.55 seconds with peaks 594,440,192 and 595,116,032 bytes. Both again passed all 53 checks, the receipt verifier, and all eight refusal controls, with zero OOM events. Its manifest SHA-256 is `44f819a792529abd61bf80ecbbd7c5818dc6e9a28fc871690cec86e5f35c167c`. This warm rerun reused compiled objects and is not an independent rebuild.

The evidence/report commit adds no implementation changes relative to `fb592a0`. Independent QA must use the exact final candidate, rerun the mandatory commands above, inspect rejection stages and trusted anchor handling, and report required findings before this slice can be accepted.

## Remaining integration gates

| Gate | Required runnable evidence before acceptance |
| --- | --- |
| Independent transaction QA | Fresh exact-commit build and execution by Meownero Adversarial Release Assurance, with adversarial cases and a recorded verdict. No self-acceptance. |
| Sync | Two isolated nodes independently ingest the same FCMP++ blocks and converge on block hash, root, depth, spent-key-image state and transaction validity. Exercise delayed and reordered delivery and restart catch-up. |
| Reorg and verifier caches | Replace the chain containing the referenced root, prove stale root/depth and cached proof results cannot admit an invalid transaction, and check pool revalidation and key-image rollback on both branches. |
| Restore and rescan | Restore a synthetic CARROT wallet from its defined recovery material, rescan the chain, recover the expected outputs and balance, and construct/verify a subsequent synthetic transaction. Repeat after a reorg. |
| Performance | Measure construction, proof verification, pool admission and block validation separately for representative input/output counts and tree depths. Record cold/warm wall time, CPU time, peak memory and block backlog under bounded load before selecting throughput limits. |
| Broader transaction coverage | Valid fixtures at multiple depths and input counts, spending CARROT outputs, invalid spend authorization and key images, duplicate spends, range/balance edge cases and invalid blocks. The one-input historical-output transition cannot establish these. |

These are subsequent acceptance gates, not results of the current candidate. No external audit, node exploit, public-network operation or release/security-readiness claim is made.
