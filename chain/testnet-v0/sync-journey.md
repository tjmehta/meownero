# Late-peer sync and restart catch-up journey

TJS-242 adds milestone check 2 of the testnet v0 freeze (sync, including a
late peer and restart catch-up) on top of the accepted TJS-229 two-peer launch
recipe. The original launcher and its 43-file manifest remain unchanged.
`sync.py` imports the accepted profile, baseline and binary admission checks and
the daemon RPC helper, and it pins the accepted recipe manifest to SHA-256
`1e3b8a784828b05634abd4b4ac22ba7cc83652b32af023c71c146f3216a5e59f`.
Peers 0 and 1 run the accepted daemon command plus one flag,
`--max-connections-per-ip 3`, on every daemon: monerod admits one inbound
connection per IP by default, which refuses a third loopback peer. This is a
P2P admission limit for the isolated loopback testbed, not a consensus or
protocol change; the first run without it is retained as a refusal receipt.

Run from the repository root, using a new path each time:

```sh
python3 -B chain/testnet-v0/sync.py --work build/testnet-v0-sync-01 --check-only
python3 -B chain/testnet-v0/test-sync-refusals.py --work build/testnet-v0-sync-refusals-01
python3 -B chain/testnet-v0/sync.py --work build/testnet-v0-sync-01
python3 -B chain/testnet-v0/verify-sync.py build/testnet-v0-sync-01
sha256sum -c build/testnet-v0-sync-01/INPUTS.sha256
```

Admission refuses the same inputs as the accepted recipe: wrong genesis,
genesis reward, subsidy, target, fork version, fork height, pool profile,
enabled pool, prefix, testnet mode, stale directory and binary hash, plus any
change to an accepted recipe input. Execution needs the shared heavy-work lock
and at least 5 GiB available RAM and disk. Exit 75 means another worker owns
the lock; keep the refusal receipt, wait for its owner, and use a new path.
The container is unchanged from the recipe: no external network, 4 GiB RAM
without swap, two CPU quotas, 256 processes, loopback-only P2P and RPC. The
wall limit is 1,500 s plus forced cleanup because native DAA approaches one
block per 90 s after the first eight blocks.

## Seams exercised

1. **Two-peer chain.** Peer 0 mines natively until top index 5 or more;
   peer 1 converges through P2P. This reuses recipe v1 behaviour.
2. **Late peer.** Peer 2 starts on a fresh, exclusively created data directory
   with `--add-exclusive-node` for peers 0 and 1 only. It must reach the exact
   two-peer state (hash, height, cumulative work, emission, fees) through P2P.
   `late-peer-sync.json` records start and sync times, its first RPC readback,
   `sync_info`, connections and bytes received.
3. **Three connected peers.** Two or more further blocks; all three converge.
4. **Restart.** Peer 1 receives SIGTERM and must exit 0. Peer 0 mines two or
   more blocks while peer 1 is down; peer 2 receives them. Peer 1 restarts with
   the identical command on the same data directory. Its first RPC height must
   not be below the pre-shutdown height, the stored pre-shutdown tip hash must
   be unchanged, and it must converge with the others. `restart-catchup.json`
   records the timeline, blocks missed and catch-up time.

The final receipts contain identical header sets from all three peers, each
peer's final `get_info`, tip and coinbase sums, per-process CPU time, peak RSS,
threads, I/O and data-directory size samples (`process-usage.json`), the
container's peak memory and `cpu.stat`, a per-height first-seen table
(`relay.json`) and per-node RPC method counts (`rpc-methods.json`). The
method counts show that peers 1 and 2 received only read RPC and that peer 0
received only `start_mining`/`stop_mining` beyond reads: no `submit_block`,
`generateblocks` or block copying.

## Limits

Relay timing is RPC-height polling at 0.1 s cadence, not wire timing; TJS-44
retains the accepted shaped-link relay medians. The chain is finite and tiny;
elapsed, CPU, RAM and disk numbers describe this run only and must not be
extrapolated to full historical sync or steady-state 90 s cadence. Existing
TJS-44 sync/restart component evidence remains accepted and is reused by
reference. This run does not test partitions, malformed frames, wallets, pool
reconnect, cold backup/restore or public networking. The separate verifier is
a receipt consistency check, not an independent operator or external audit.
