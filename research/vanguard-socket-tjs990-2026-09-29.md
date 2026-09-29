# Vanguard private socket delivery (TJS-990)

**Status:** Local engineering witness passed at code commit
`687b4b0e99cfbb1710c015fac86d950e20ac1ff2`. This extends the accepted
TJS-953 two-process core test. It does not run `monerod` or its P2P handshake,
peer discovery, request scheduling, gossip, or transaction relay policy.

## Boundary and workload

The parent and child each start an offline FAKECHAIN `cryptonote::core` with a
separate LMDB directory. They communicate through a private `AF_UNIX`
`SOCK_STREAM` pathname socket in their shared network-disabled container. The
parent binds a socket under a mode-0700 directory before forking; only the
child accepts connections. `getpeername` and `SO_TYPE` checks identify the
connected Unix stream. The test removes the pathname before exit. There is no
TCP or public listener, outside peer, testnet, or mainnet connection.

The wire messages are bounded length-prefixed harness frames. The parent sends
each serialized block header before its block; the child parses the header,
echoes its canonical bytes, and checks that the next block matches. Serialized
transactions and blocks are admitted through the upstream core's existing
parse and validation functions. This is a real local socket boundary and core
validation, but the wire format is specific to this harness.

The fixture is a valueless FCMP++ spend after a v17 fork at height 80 with its
reference at 140. The peer sees block 137 before 136 and then the proper
order. After initial convergence, the client disconnects and reconnects to
the same peer process and replays its tip; state stays unchanged. A frame over
the 16 MiB limit and a truncated frame each close only that connection. The
client reconnects after each and checks that state is intact. The peer then
restarts its core against the retained LMDB.

The competing branch changes the trusted root and removes the confirmed spend
and spent key image from both nodes. A stale-root spend is rejected from both
a block supplement and the retained pool without changing either core's
state. A longer original branch restores the initial root, confirmed spend,
and spent key image. Both cores agree on tip, reference root and depth, spend
presence, key-image state, and pool state at each recorded comparison.

## Reproduce and inspect

The runner requires the pinned scratch checkout and offline Rust cache prepared
for Vanguard. It refuses an existing output directory. In this task worktree:

```sh
python3 -B vanguard/run-sync-process.py --out build/vanguard-socket-tjs990-exact01
python3 -B vanguard/verify-sync-process.py research/evidence/vanguard-socket-tjs990-2026-09-29
cd research/evidence/vanguard-socket-tjs990-2026-09-29
sha256sum --status -c MANIFEST.sha256
```

The committed raw bundle is
`research/evidence/vanguard-socket-tjs990-2026-09-29/`. Its
`receipt.json` records the exact source commit and hashes, upstream commit
`e151643c5269c83bf24a83b2548e2493876026b2`, builder image and Rust
version, complete Docker commands, binary SHA-256
`622250d1b2626d4606c1f514ec1cf34e6f8fe72a80c8ee8102a1ad5abb6ad8e9`,
wall times and cgroup measurements. The manifest SHA-256 is
`4e679926a049beb94d836c1f614a643d780f88718c1c9a9dba8af4d945d4b491`.
The verifier checks the source against the recorded Git commit, all manifest
files, container flags, named checks, state transitions, stale-root controls,
process separation, fault records, and core logs.

| Stage | Wall seconds | CPU seconds | Peak bytes | Exit |
| --- | ---: | ---: | ---: | ---: |
| Build | 20.61 | 19.03 | 1,346,289,664 | 0 |
| Run 1 | 30.45 | 30.91 | 923,131,904 | 0 |
| Run 2 | 29.17 | 29.74 | 918,417,408 | 0 |

Each run passed 516 named checks; their check streams are byte-identical
(SHA-256 `ec0892cd23a9e4909c4f710cae03acdb3dd5cf962e3050c03f6cc1e9a16c5f9c`).
`rejected-frames.tsv` records exactly the oversized and truncated frame in
each run. `states.tsv` and `controls.tsv` hold raw per-node transition values;
absolute hashes differ between runs because the fixture uses synthetic keys
and proof randomness. All containers used `--pull=never --network=none`,
`--cap-drop=ALL`, `no-new-privileges`, two CPUs, 4 GiB memory and swap, 256
PIDs, and disabled core dumps. No cgroup OOM or OOM-kill was recorded. The
900-second runner timeout and 16 MiB frame cap bound this experiment.

This does not establish daemon P2P interoperability, autonomous backlog sync,
public-network behavior, loaded 90s/120s performance, fee or wallet behavior,
mining payouts, external audit, or launch readiness. The initial compile
attempt lacked the binary parser include; the corrected source was committed
before the passing receipt. The later truncated-frame fix was also followed
by a fresh two-run receipt.
