# Native daemon P2P over a private Unix bridge (TJS-996)

**Result:** Two executions passed against candidate code commit
`6ba799b909d005be57232e4566ee3617a63574ac`. This is a bounded local
engineering witness for native `monerod` P2P transport and recovery, not an
external audit or public-network readiness claim.

## Workload and containment

The runner builds the pinned `seraphis-migration/monero` FCMP++ integration
commit `e151643c5269c83bf24a83b2548e2493876026b2`. Each execution starts
two actual `monerod` processes with separate LMDB directories plus a disposable
wallet RPC. Node A dials an exclusive loopback peer at the bridge, which copies
native Levin frames through a mode-0600 AF_UNIX stream to node B's loopback P2P
listener. Both daemons report one native P2P peer at the first handshake. The
bridge records command, direction, length and SHA-256 for each frame; saved
adversarial frames retain their raw bytes.

The container has `--network=none`, no published ports, only `lo`, no route,
and only loopback TCP listeners. It runs with two CPUs, 4 GiB memory and swap
cap, 256 PIDs, dropped capabilities, `no-new-privileges`, and disabled core
dumps. The heavy-work lock excludes another local build or measurement using
the shared pinned source. The byte bridge rejects a Levin frame above 16 MiB.
The two daemons share this network namespace; they are isolated by process,
database and pool, with all traffic to other namespaces disabled. The bridge
does not add AF_UNIX support to `monerod` itself.

The wallet mines 70 fixed-difficulty regtest blocks. It then creates an FCMP++
transaction (RingCT type 7), which both daemon pools receive over P2P. The
captured transaction notification is replayed unchanged and then replayed with
a malformed binary varint. A confirmed block and a later empty block cross P2P;
the captured empty block notification is replayed unchanged, with a malformed
header, and with a malformed coinbase transaction body. After every replay or
mutation, both daemons retain the same tip, pools and key-image status as
before that input. Node B's raw log records one transaction parse rejection
and two block parse rejections per run.

Both daemons confirm the spend and report key-image status `1` (spent in chain).
The bridge partitions them. The harness uses node B's local `pop_blocks` RPC
to remove two blocks and mines a three-block competing branch there. Node A
retains its old tip during the partition. On reconnection, native P2P chain
and object exchange selects B's longer branch; the old tip is orphaned. Both
daemons agree at height 73 and report key-image status `2` (spent in pool),
showing rollback of the confirmed spend. A later block from B reaches A and
both agree at height 74. The witness does not construct a naturally occurring
fork or test a root-changing FCMP proof after the split.

## Exact receipt

The committed raw bundle is
`research/evidence/vanguard-daemon-p2p-tjs996-2026-09-29/`. Its
`MANIFEST.sha256` hash is
`afedfb9d82162d954ecdbc556dd7c02394bdb678d29cadea6e09f9290a760942`.
`receipt.json` records the exact candidate and upstream commits, source hashes,
builder image, complete Docker commands, binary hashes, wall times and cgroup
metrics. The binary SHA-256 values are
`5ba64f2e04e21550575b396b250bcebba01471c4246d74d88e679f06cee86509`
for `monerod` and
`cf2ea70c353c5124e86f2bfac46da28fad2993af28636ab28ca7ea9db81678f2`
for wallet RPC. This build stage reused already compiled local objects; the
source and binary pins allow independent clean rebuild comparison.

| Stage | Wall seconds | CPU seconds | Peak bytes | Exit |
| --- | ---: | ---: | ---: | ---: |
| Cached build | 4.12 | 3.50 | 61,145,088 | 0 |
| Run 1 | 31.08 | 21.12 | 757,858,304 | 0 |
| Run 2 | 33.16 | 21.95 | 758,366,208 | 0 |

Run 1 records 104 native frames, 48,038 bridge bytes and five bridge
connections; run 2 records 102 frames, 55,471 bytes and five connections.
The signed transaction and block hashes differ because the disposable wallet
and mining fixture vary. Each run records 31 events, parser logs, raw injected
frames, live listener snapshots, state transitions and cgroup files. Neither
run recorded a cgroup OOM or OOM kill.

Reproduce from this worktree with the prepared pinned scratch checkout and
offline Rust cache:

```sh
python3 -B vanguard/run-daemon-p2p.py --out build/vanguard-daemon-p2p-tjs996-recheck01
python3 -B vanguard/verify-daemon-p2p.py research/evidence/vanguard-daemon-p2p-tjs996-2026-09-29
cd research/evidence/vanguard-daemon-p2p-tjs996-2026-09-29
sha256sum --status -c MANIFEST.sha256
```

The committed verifier prints `PASS_DAEMON_P2P_RECEIPT_RECONCILIATION` for
the raw bundle. This checks actual P2P frame carriage and local daemon state,
not loaded 90s/120s performance, public-network behavior, fee economics,
mining payouts, external audit or launch readiness.
