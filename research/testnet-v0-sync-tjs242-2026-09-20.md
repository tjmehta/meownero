# TJS-242: testnet v0 late-peer sync and restart catch-up

2026-09-20. Milestone check 2 of the TJS-223 freeze (sync, including a late
peer and restart catch-up) implemented and witnessed locally on the accepted
TJS-229 recipe. Recipe extension committed as `1887fa6`; this document and the
evidence directory follow in the next commit.

Delivered `chain/testnet-v0/sync.py`, `verify-sync.py`, `test-sync-refusals.py`
and the operator document `sync-journey.md`. The accepted launcher, its six
recipe files and the 43-file TJS-229 manifest (`1e3b8a78…`) are unchanged and
re-verified at admission. The binary is the accepted TJS-40 `monerod`
`b79cb49d…`. No rebuild, consensus or protocol change was made. The TJS-230
work directory and the F4 pool port were not touched.

## Runtime finding: per-IP inbound limit

The first attempt (`run01-per-ip-refused/`) failed `late peer sync timeout`.
`monerod` admits one inbound P2P connection per IP by default
(`max-connections-per-ip` = 1, `src/p2p/net_node.inl:239`). Peers 0 and 1 each
already held one loopback inbound connection, so peer 2 was refused every
second: `CONNECTION FROM 127.0.0.1 REFUSED, too many connections from the same
address`. When cleanup stopped peer 0, a slot freed on peer 1 and peer 2 synced
`6/6` blocks in 0.084 s (`peer2.sync-excerpt.log`). The limit was the only
blocker. Every daemon in the extension now passes `--max-connections-per-ip 3`.
This is a P2P host-policy argument for the isolated loopback testbed, not a
consensus change, and it is the only difference from the accepted command.

## Observed final run (`sync/`, container `meow-tjs242-2964474`)

Native RandomX mining on peer 0 only, native DAA, ordinary timestamps. Peers 1
and 2 and the restarted peer 1 received every block through TCP P2P; the
per-node RPC receipt (`rpc-methods.json`) shows peers 1 and 2 received only
read methods and `sync_info`, and peer 0 received only `start_mining` and
`stop_mining` beyond reads. No `submit_block`, `generateblocks` or block copy.

| Seam | Observation |
| --- | --- |
| Two-peer chain | Top index 5 at 23.8 s; both peers equal. |
| Late peer 2 | Started at 23.77 s on a freshly created data directory. First RPC readback: height 1 (genesis only), zero connections, not synchronized. Reached the exact two-peer state (hash `c1f657be…`, work `0xa0`, emission 45 MEOW, fees 0) at 25.08 s: **1.313 s from process start**, 2,562 bytes received and 1,020 sent over two outbound connections. |
| Three peers | Top index 7 at 34.8 s; all three equal. Coarse RPC first-seen spread across the three peers 0.002 s (height 7) and 0.001 s (height 8). |
| Clean shutdown | Peer 1 SIGTERM at 35.23 s, **exit 0**; stored tip top 7 `25731d67…`. |
| Offline mining | Blocks 8 and 9 mined in 127 s (difficulty 11,472 and 21,180) with peer 1 down; peer 2 saw them 0.107 s and 0.001 s after peer 0. |
| Restart | Identical command on the same data directory at 162.43 s. First RPC readback height 8 (stored top 7 plus genesis), top hash equal to the pre-shutdown tip, not synchronized. Equal tip, work and aggregate with both peers at 163.05 s: **0.614 s after restart, 2 blocks recovered**. |
| Final state | All three peers: top 9, hash `3b51561c…`, cumulative work `0x8e7e` (36,478), emission 81,000,000,000,000 atomic = 9 × 9 MEOW, fees 0. Identical header sets. |

At the final receipt, 0.6 s after restart, peer 1's only connection was the
inbound one from peer 2; the catch-up was served by the late peer, and peer
1's outbound reconnection to peer 0 had not yet been made in that window. Each
peer had one or two local connections with traffic in both directions.

Header difficulties: 1, 1, 5, 25, 127, 647, 3,019, 11,472, 21,180 at timestamp
offsets 0, 22, 22, 22, 22, 24, 30, 65, 160 s. Cumulative work equals the sum.

## Resource measurements (finite nine-block chain only)

| Measure | Value |
| --- | --- |
| Wall time (container) | 164.6 s |
| Container CPU (`cpu.stat`) | 164.4 s total, 162.1 s user; cap two CPUs, no OOM |
| Container peak memory | 3,064,344,576 bytes (2.85 GiB) under the 4 GiB cap; TJS-229 two-peer peak was 2.78 GB |
| Peer 0 (miner) | RSS 2.42 GB (RandomX dataset), 158.8 s user CPU |
| Peer 1 / restarted peer 1 | RSS 299 MB / 287 MB; 0.6 s / 0.4 s user CPU |
| Peer 2 (late) | RSS 289 MB after sync, 296 MB final; 0.9 s user CPU |
| Data directory per peer | about 184 KB allocated (LMDB), two or three files |
| Host preflight | 16.5 GB available RAM, 38 GB free disk; 5 GiB gate |

These numbers describe this tiny empty-block chain under the recipe's caps and
must not be extrapolated to full historical sync, steady-state 90 s cadence or
loaded relay. Relay figures are RPC-height polling at 0.1 s cadence, not wire
timing; TJS-44 keeps the accepted shaped-link relay medians and the earlier
depth-3 reorg and restart component evidence, reused here by reference.

## Verification and evidence

- Twelve actual-command admission refusals plus accepted control against
  `sync.py` (`refusals/`): wrong genesis, genesis reward, subsidy, target, fork
  version, fork height, pool profile, enabled pool, prefix, testnet mode, stale
  directory, binary hash; each exit 2 with a specific message before launch.
- `verify-sync.py` returned `PASS_RECEIPT_RECONCILIATION` (`verify.stdout.json`):
  three identical linked header sets, work and reward sums, three peers' RPC
  totals, exclusive-peer commands, restart command equality, no write RPC on
  peers 1 and 2, late-peer and restart receipts, caps and clean exits.
- 36 public receipts pass `EVIDENCE.sha256`; 48 inputs pass `INPUTS.sha256`;
  124 files in `MANIFEST.sha256`. Node databases stay in
  `build/testnet-v0-sync-tjs242-run03/data`, outside the archive. No seed or
  private key exists in this journey; the only "seed" strings in receipts are
  the RandomX seed hash and `pruning_seed` fields.
- An intermediate run (`build/testnet-v0-sync-tjs242-run02`) reproduced the
  late-peer and three-peer results and the clean shutdown, then was interrupted
  by an operator-session teardown before the restart seam; it is not archived.

Raw receipts: [evidence](evidence/testnet-v0-sync-tjs242-2026-09-20/).
Operator entry point: [journey](../chain/testnet-v0/sync-journey.md).

## Disposition and limits

The assigned late-peer sync and restart catch-up check is complete for the
finite isolated chain. This is an author-run witness with a separate receipt
checker, not an independent operator run, external audit, partition or
malformed-frame test, wallet or pool restart, cold backup/restore, public
testnet, 90-second GO or mainnet readiness claim. No push, mainnet, protocol
change, pool deployment or paid-auditor prerequisite was added.

**TJ decision:** isolated testnet v0, selected 9/90, one operator recipe.
**Observed:** a fresh late peer and a cleanly restarted peer reach the common
tip, work and aggregate through P2P alone on the accepted candidate.
**Agent proposal:** QA/Release fold `sync.py` into the operator handoff journey;
historical statements that late-peer sync and restart catch-up are unwitnessed
on the native-mode recipe are superseded for this bounded scope.
