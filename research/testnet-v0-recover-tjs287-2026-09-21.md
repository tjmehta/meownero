# TJS-287: testnet v0 cold backup/restore and payout-wallet restart

2026-09-21. Milestone check 4 of the TJS-223 freeze (operator recovery: cold
backup and restore of a node data directory, and a payout wallet closed and
reopened across daemon restarts) implemented and witnessed locally on the
accepted TJS-229 recipe. Recipe extension committed as `3bc39cb`; this
document and the evidence directory follow in the next commit.

Delivered `chain/testnet-v0/recover.py`, `verify-recover.py`,
`test-recover-refusals.py` and the operator document `recover-journey.md`.
The accepted launcher, its six recipe files and the 43-file TJS-229 manifest
(`1e3b8a78…`) are unchanged and re-verified at admission. The daemon is the
accepted TJS-40 `monerod` `b79cb49d…`; the wallet RPC is the accepted
TJS-40/TJS-44 `monero-wallet-rpc` `5782abee…`. No rebuild, consensus or
protocol change was made. The TJS-230 run-03 and TJS-242 work directories,
their daemons and the F4 pool port were not touched; no earlier run directory
or daemon was reused.

## Observed final run (`recover/`, container `meow-tjs287-1722030`)

Native RandomX mining on peer 0 only, native DAA, ordinary timestamps. Peer
1, the restarted peer 1 and the restored peer 1 received every block through
TCP P2P; the per-node RPC receipt (`rpc-methods.json`) shows peer 1 received
only read methods and `sync_info` from the runner, and peer 0 received only
`start_mining` and `stop_mining` beyond reads. No `submit_block`,
`generateblocks` or block copy. The payout wallet W lives on a wallet RPC
bound to peer 1's daemon RPC on container loopback.

| Seam | Observation |
| --- | --- |
| Payout chain | Top index 5 at 30.4 s, mined to W; both peers equal (hash `a2ce81d1…`, work `0xa0`, emission 45 MEOW, fees 0). W: balance 45,000,000,000,000 atomic, unlocked 0, five `block` entries at heights 1–5 of 9 MEOW each, every txid equal to the canonical header's `miner_tx_hash`; wallet height 6. |
| Plain restart | W stored and closed. Peer 1 SIGTERM at 31.27 s, **exit 0**, tip top 5. Restarted with the identical command on the same directory; its log reported `last block: 5` at database open and its first RPC readback was height 6, top hash `a2ce81d1…`, not synchronized. No blocks mined while down (0 missed). W reopened at 35.78 s: address, balances, incoming and outgoing history **equal** to the pre-restart snapshot; wallet height 6. |
| Cold backup | W closed again; peer 1 SIGTERM at 36.40 s, **exit 0**, tip top 5. With the daemon stopped, three files were hashed: `lmdb/data.mdb` 180,224 bytes (`0c15fcd7…`), `lmdb/lock.mdb` 8,192 bytes, `28180/p2pstate.bin` 62 bytes. Archived to `data/peer1-backup.tar`, 204,800 bytes, SHA-256 `072e5352…`. The data directory was then deleted and its absence recorded. |
| Mining while destroyed | Blocks 6 and 7 mined to the public fixture address in 4.4 s (difficulty 647 and 2,499) with peer 1 absent; peer 0 alone at top 7, hash `6d159c35…`, work `0xcea`. |
| Restore and rejoin | Archive extracted to the same path at 40.86 s; restored per-file manifest **equal** to the source manifest. Peer 1 restarted with the identical command at 40.86 s: log `last block: 5` at database open, first RPC readback height 6 with top hash equal to the backup tip, stored header at height 5 equal to the backup tip hash. Equal tip, work and aggregate with peer 0 at 41.47 s: **0.613 s after restart, 2 blocks recovered**, served over one local connection (1,170 bytes received, 703 sent). |
| Wallet after restore | W reopened at 43.31 s: address, balances and history **equal** to the original snapshot; wallet height 8 (it scanned blocks 6–7, which paid the fixture address, not W). |
| Final state | Both peers: top 7, hash `6d159c35…`, cumulative work `0xcea` (3,306), emission 63,000,000,000,000 atomic = 7 × 9 MEOW, fees 0. Identical header sets. |

Header difficulties: 1, 1, 5, 25, 127, 647, 2,499 at timestamp offsets 0, 22,
22, 22, 22, 29, 30 s. Cumulative work equals the sum. At the rejoin receipt
peer 1's only connection was the inbound one from peer 0; its own outbound
reconnection had not yet formed in that 0.6 s window, as in TJS-242.

## Resource measurements (finite seven-block chain only)

| Measure | Value |
| --- | --- |
| Wall time (container) | 45.0 s |
| Container CPU (`cpu.stat`) | 40.8 s total, 39.3 s user; cap two CPUs, no OOM |
| Container peak memory | 2,781,372,416 bytes (2.59 GiB) under the 4 GiB cap |
| Peer 0 (miner) | RSS 2.42 GB (RandomX dataset), 26.8 s user CPU |
| Peer 1 / restarted / restored | RSS 297 MB / 286 MB / 287 MB; 0.5 s / 0.4 s / 0.4 s user CPU |
| Peer 1 data directory | 184 KB allocated before backup, 192 KB after rejoin; three files |
| Backup archive | 204,800 bytes for a five-block LMDB, kept under `WORK/data` |
| Host preflight | 20.3 GB available RAM, 36.7 GB free disk; 5 GiB gate |

These numbers describe this tiny empty-block chain under the recipe's caps and
must not be extrapolated to a historical database, steady-state 90 s cadence
or a busy node.

## First attempt (`run01-history-order-refused/`)

The first run failed at 28.1 s with `payout history mismatch` after the
balance check had already passed. The recipe sorted W's history entries by
txid and then required their heights to appear in ascending order, so the
assertion, not the wallet, was wrong. The check now compares the sorted set
of heights to 1…top in both `recover.py` and `verify-recover.py`; no other
line changed. The failed run's public receipts are retained; its
`INPUTS.sha256` pins the pre-fix `recover.py`.

## Verification and evidence

- Thirteen actual-command admission refusals plus accepted control against
  `recover.py` (`refusals/`): wrong genesis, genesis reward, subsidy, target,
  fork version, fork height, pool profile, enabled pool, prefix, testnet mode,
  stale directory, binary hash and wallet hash; each exit 2 with a specific
  message before launch.
- `verify-recover.py` returned `PASS_RECEIPT_RECONCILIATION`
  (`verify.stdout.json`): two identical linked header sets, work and reward
  sums, both peers' RPC totals, exclusive-peer commands, three byte-equal
  peer 1 commands, wallet command bound to peer 1 with no secret on the
  command line, no write RPC on peer 1, wallet history bound to canonical
  coinbase hashes and equal across both reopenings, stored tip at open from
  the daemon log for both restarts, backup and restore manifests, archive
  hash, destroy witness, offline blocks, rejoin timeline, caps and clean exits.
- 34 public receipts pass `EVIDENCE.sha256`; 48 inputs pass `INPUTS.sha256`
  (`inputs-check.log`); 119 files in `MANIFEST.sha256`. Node databases, the
  backup archive, wallet files, wallet log and wallet process output stay in
  `build/testnet-v0-recover-tjs287-run02/data`, outside the archive. The
  payout address, seed and keys appear in no receipt; the only address in
  public receipts is the public recipe fixture used for the offline blocks.

| Invariant | Admission / live check | Retained evidence |
| --- | --- | --- |
| Exact candidate | Fixed daemon and wallet hashes, accepted 43-file manifest, new-file hashes | `baseline.json`, `INPUTS.sha256`, `BINARY.sha256` |
| Fresh zero-reward genesis | New directories, genesis hash/reward/version readback | `profile-readback.json`, `headers.json` |
| 9 MEOW / 90 s | Profile, template reward, both nodes' target, all rewards | `profile-readback.json`, `rpc-final.json`, `headers.json` |
| v16 at height 1 | Fork readback, height-one template and mined headers | `profile-readback.json`, `headers.json` |
| Payout wallet | One coinbase per mined block, txids equal to `miner_tx_hash`, balance = rewards, locked | `wallet-restart.json`, `headers.json` |
| Wallet across restart | Store/close, clean daemon exit, identical command, stored tip at open, reopen equal | `wallet-restart.json`, `process-commands.json`, `peer1-restart.stdout.log` |
| Cold backup/restore | Per-file SHA-256 with daemon stopped, archive hash, directory absent, restored manifest equal | `cold-restore.json`, `result.json` |
| Rejoin | Stored tip at open, backup tip header unchanged, equal tip/work/emission with peer 0 | `cold-restore.json`, `peer1-restore.stdout.log`, `rpc-final.json` |
| Actual peer convergence | Native mine on peer 0, P2P to peer 1; no block-copy RPC | `rpc-methods.json`, `peers-*.json`, logs |
| Work and supply | Sum header difficulty/rewards; reconcile both RPC totals | `headers.json`, `rpc-final.json`, `result.json` |
| Isolation and cleanup | No external network, loopback RPC, caps, five owned exits | `container-command.json`, `resources.json`, `*.exit`, `cleanup.json` |

Raw receipts: [evidence](evidence/testnet-v0-recover-tjs287-2026-09-21/).
Operator entry point: [journey](../chain/testnet-v0/recover-journey.md).

## Disposition and limits

The assigned cold backup/restore and payout-wallet restart check is complete
for the finite isolated chain. This is an author-run witness with a separate
receipt checker, not an independent operator run, external audit, hot or
partial backup test, corrupted-restore test, cross-host or cross-version
restore, CLI wallet restore, spend after restore, pool payout, partition,
public testnet, 90-second GO or mainnet readiness claim. F3 (FCMP, loaded
partition/reorg) stays deferred per TJS-223. No push, mainnet, protocol
change, pool deployment or paid-auditor prerequisite was added.

**TJ decision:** isolated testnet v0, selected 9/90, one operator recipe;
this milestone stays on operator recovery, not protocol.
**Observed:** a node restored from a cold whole-directory backup opens at the
backup tip and rejoins the common tip, headers and cumulative work through
P2P alone; a payout wallet reopened across a plain restart and across the
restored daemon shows the same address, balances and coinbase history.
**Agent proposal:** QA/Release accept milestone check 4 on the evidence
commit's receipts, as TJS-278 did for M2, and fold `recover.py` into the
operator handoff journey; the TJS-242 limits naming cold backup/restore and
wallet restart as unwitnessed are superseded for this bounded scope.
