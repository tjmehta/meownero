# Cold backup/restore and payout-wallet restart journey

TJS-287 adds milestone check 4 of the testnet v0 freeze (operator recovery:
cold backup and restore of a node data directory, and a payout wallet closed
and reopened across daemon restarts) on top of the accepted TJS-229 two-peer
launch recipe. The original launcher and its 43-file manifest remain
unchanged. `recover.py` imports the accepted profile, baseline and binary
admission checks and the daemon RPC helper, pins the accepted recipe manifest
to SHA-256 `1e3b8a784828b05634abd4b4ac22ba7cc83652b32af023c71c146f3216a5e59f`
and pins `monero-wallet-rpc` to the accepted TJS-40/TJS-44 bytes
`5782abee489e8b245b42fd237ece34d6df1c67929c552960755fab41de3a921a`. Both
peers run the exact accepted daemon command; every restart of peer 1 must
reuse that command byte for byte. This is an operator-recovery check, not a
consensus, protocol or pool change.

Run from the repository root, using a new path each time:

```sh
python3 -B chain/testnet-v0/recover.py --work build/testnet-v0-recover-01 --check-only
python3 -B chain/testnet-v0/test-recover-refusals.py --work build/testnet-v0-recover-refusals-01
python3 -B chain/testnet-v0/recover.py --work build/testnet-v0-recover-01
python3 -B chain/testnet-v0/verify-recover.py build/testnet-v0-recover-01
sha256sum -c build/testnet-v0-recover-01/INPUTS.sha256
```

Admission refuses the same inputs as the accepted recipe: wrong genesis,
genesis reward, subsidy, target, fork version, fork height, pool profile,
enabled pool, prefix, testnet mode, stale directory and binary hash, plus the
wallet binary hash and any change to an accepted recipe input. Execution needs
the shared heavy-work lock and at least 5 GiB available RAM and disk. Exit 75
means another worker owns the lock; keep the refusal receipt, wait for its
owner, and use a new path. The container is unchanged from the recipe: no
external network, 4 GiB RAM without swap, two CPU quotas, 256 processes,
loopback-only P2P, daemon RPC and wallet RPC. The wall limit is 1,800 s plus
forced cleanup; each mining phase is bounded to twice its DAA-expected time
plus slack. A timeout is an incomplete journey, never permission to lower
difficulty, alter timestamps or copy blocks.

## Seams exercised

1. **Payout chain.** A disposable wallet W is created in memory on a wallet
   RPC bound to peer 1. Peer 0 mines natively to W's address until top index
   5 or more; peer 1 converges through P2P. W must show exactly one coinbase
   entry per mined block, each txid equal to the canonical header's
   `miner_tx_hash`, a balance equal to the mined rewards and zero unlocked
   balance (coinbase matures after 60 blocks).
2. **Wallet across a plain daemon restart.** W is stored and closed. Peer 1
   receives SIGTERM and must exit 0, with no blocks mined while it is down.
   It restarts with the identical command on the same data directory; the
   daemon's own `Blockchain initialized. last block: N` line and its first
   RPC readback must both show the stored tip. W is reopened; address,
   balances, incoming and outgoing history must be equal to the snapshot
   taken before the restart (`wallet-restart.json`).
3. **Cold backup, destroy, restore, rejoin.** W is closed again and peer 1 is
   stopped cleanly. With the daemon stopped, every file under
   `data/peer1` is hashed (`source_manifest`) and archived to
   `data/peer1-backup.tar`; the archive's size and SHA-256 are recorded. The
   data directory is deleted and its absence recorded. Peer 0 mines two or
   more blocks to the public recipe fixture address with peer 1 destroyed.
   The archive is extracted back to the same path; the restored per-file
   manifest must equal the source manifest. Peer 1 restarts with the
   identical command: its log must show the backup tip at database open,
   its stored header at the backup height must equal the backup tip hash,
   and it must converge with peer 0 on the new tip, cumulative work and
   emission (`cold-restore.json`). W is reopened and must again equal the
   original snapshot; the blocks mined while peer 1 was destroyed were paid
   to the fixture address, so W's history is unchanged while its scanned
   height advances.

The final receipts contain identical header sets from both peers, each
peer's final `get_info`, tip and coinbase sums, per-process CPU time, peak
RSS, threads and data-directory size samples (`process-usage.json`), the
container's peak memory and `cpu.stat`, and per-node RPC method counts
(`rpc-methods.json`). The method counts show that peer 1 received only read
RPC from the runner and that peer 0 received only `start_mining` and
`stop_mining` beyond reads: no `submit_block`, `generateblocks` or block
copying. The wallet's own daemon requests go to peer 1 directly and are read
requests (block and output fetches); they are not counted by the runner.

## Privacy boundary

W's keys are generated in memory by the wallet RPC with an empty password and
live only in `WORK/data/W`, together with the wallet log and wallet process
output. `WORK/data` also holds both node databases and the backup archive. Do
not archive or publish that directory. The payout address, seeds and private
keys never appear on a command line, in a public receipt or in the runner's
output; the payout mining receipt records the method and thread count only,
and the wallet receipt records `address_matches` booleans, balances and
public coinbase txids. Wallet RPC errors and bodies are never logged. Copy
only the top-level files covered by `EVIDENCE.sha256`.

## Limits

The chain is finite and tiny; elapsed, CPU, RAM and disk numbers describe
this run only and must not be extrapolated to a historical database, a
steady-state 90 s cadence or a busy node. The backup is a whole-directory
archive taken with the daemon stopped; it does not test hot backups,
`mdb_copy`, partial or corrupted restores, a restore onto a different
machine or a restore across binary versions. The wallet is reopened through
the same wallet RPC process; it does not test CLI restore, a wallet file
copied to another host, spends after restore, pool payouts or public
networking. The separate verifier is a receipt consistency check, not an
independent operator run or external audit.
