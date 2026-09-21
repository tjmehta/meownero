# Pool restart journey

TJS-297 adds milestone check 5 of the testnet v0 freeze (the pool half of the
"restart node, pool and wallet without lost funds or changed tip" row) on top
of the accepted TJS-229 two-peer launch recipe. `pool-restart.py` imports the
accepted profile, baseline and binary admission checks and the daemon RPC
helper, pins the accepted recipe manifest to SHA-256
`1e3b8a784828b05634abd4b4ac22ba7cc83652b32af023c71c146f3216a5e59f`, pins the
F4 candidate `p2pool` executable to
`bbc3240607bf40bd3db7e13f011ccf9eda431dddd751918a3ebf4e3aaf129fad` (TJS-187
writer build, reproduced byte-identically in TJS-224) and pins its two source
inputs from the freeze document, `spikes/p2pool/full-source-lock.json`
(`62354e65…`) and `spikes/p2pool/meownero-local.patch` (`0b28c5d9…`). Peer 0
runs the exact accepted daemon command. Peer 1 runs the same command with one
documented difference: `--no-zmq` is replaced by a loopback ZMQ publisher
(`--zmq-rpc-bind-ip 127.0.0.1 --zmq-rpc-bind-port 28182 --zmq-pub
tcp://127.0.0.1:28183`), because the pool learns about new blocks from the
daemon's ZMQ feed. The verifier checks both commands token for token. This is
an operator-recovery check of the pool process, not a pool payout, share,
sidechain or consensus claim; the recipe profile's `pool_enabled: false` still
describes the daemon launch, and the pool here is a separately pinned
component attached to peer 1.

Run from the repository root, using a new path each time:

```sh
python3 -B chain/testnet-v0/pool-restart.py --work build/testnet-v0-pool-restart-01 --check-only
python3 -B chain/testnet-v0/test-pool-restart-refusals.py --work build/testnet-v0-pool-restart-refusals-01
python3 -B chain/testnet-v0/pool-restart.py --work build/testnet-v0-pool-restart-01
python3 -B chain/testnet-v0/verify-pool-restart.py build/testnet-v0-pool-restart-01
sha256sum -c build/testnet-v0-pool-restart-01/INPUTS.sha256
```

Admission refuses the same inputs as the accepted recipe: wrong genesis,
genesis reward, subsidy, target, fork version, fork height, pool profile,
enabled pool, prefix, testnet mode, stale directory and binary hash, plus the
pool binary hash, the two pinned pool source inputs and any change to an
accepted recipe input. Execution needs the shared heavy-work lock and at
least 5 GiB available RAM and disk. Exit 75 means another worker owns the
lock; keep the refusal receipt, wait for its owner, and use a new path. The
container is unchanged from the recipe: no external network, 4 GiB RAM
without swap, two CPU quotas, 256 processes, loopback-only P2P, daemon RPC,
ZMQ, pool P2P and stratum. The wall limit is 1,800 s plus forced cleanup;
each mining phase is bounded to twice its DAA-expected time plus slack. A
timeout is an incomplete journey, never permission to lower difficulty, alter
timestamps or copy blocks.

## Seams exercised

1. **Attach at a common tip.** Peer 0 mines natively to the public fixture
   address until top index 3 or more; peer 1 converges through P2P. The pool
   then starts on peer 1 in light mode with no built-in miner, no cache, no
   DNS and loopback listeners, and with its JSON data API enabled. The runner
   logs in once on the stratum port: the job's `height` must be the tip
   height plus one and the 32-byte previous block id inside the hashing blob
   must equal the tip hash; the pool's `network/stats` must report the same
   hash and height; `pool/stats.totalBlocksFound` must be 0.
2. **Follow live blocks.** Peer 0 mines two or more blocks with the pool
   running. They reach peer 1 only through P2P, and the pool only through
   peer 1's ZMQ feed and RPC. A fresh stratum login must show a job on the
   new tip and the pool API must agree.
3. **Stop, mine on, restart, resume.** The pool receives SIGTERM and must
   exit 0. Peer 0 mines two or more blocks while the pool is down. The pool
   restarts with the byte-identical command on the same data directory; its
   first served job and its API view must build on the tip the two daemons
   share, which the runner reads from peer 1 before and after the restart.
   The elapsed time from restart to the first job on that tip is recorded
   (`pool-restart.json`).

The final receipts contain identical header sets from both peers, each
peer's final `get_info`, tip and coinbase sums, per-process CPU time, peak
RSS, threads and data-directory size samples for both daemons and both pool
lives (`process-usage.json`), the container's peak memory and `cpu.stat`,
per-node RPC method counts (`rpc-methods.json`) and the pool's own log
(`pool.log`, shared across both lives). The method counts show that peer 1
received only read RPC from the runner and that peer 0 received only
`start_mining` and `stop_mining` beyond reads. The pool's own requests go to
peer 1 directly; the pool log must contain no `BLOCK FOUND` or
`submit_block`, and the pool API must report zero blocks found, because no
stratum miner is connected and the pool never submits work here.

## Privacy boundary

No wallet, seed or private key exists in this journey. The pool's payout
address is the existing public recipe fixture and appears on its command
line by design. `WORK/data` holds both node databases, the pool's data
directory and its API files; it is not part of the public receipt set. Copy
only the top-level files covered by `EVIDENCE.sha256`.

## Limits

The chain is finite and tiny; elapsed, CPU and RAM numbers describe this run
only. The pool runs with no connected miner and no sidechain peer, so this
witnesses that the pool process restarts and resumes serving work at the
common tip; it does not witness share acceptance, PPLNS accounting, a pool
payout, a pool restart with a populated sidechain cache, a pool reorg or a
restart under load. Those remain with the F4 acceptance (TJS-187/TJS-224)
and the open gates listed in the freeze document. Only peer 1 publishes
ZMQ; peer 0 stays on the exact accepted command. The separate verifier is a
receipt consistency check, not an independent operator run or external
audit.
