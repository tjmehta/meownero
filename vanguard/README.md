# Vanguard V1: pinned FCMP++ and CARROT primitives (TJS-356)

An isolated, valueless harness. It compiles the upstream FCMP++ and CARROT code at
the pins in `source-lock.json` and runs positive and negative vectors against it.
It does not run a node, open a network, hold keys of value or spend. It does not
touch the accepted testnet v0 recipes or their builder image. It is not an audit.

| Path | Role |
| --- | --- |
| `source-lock.json` | Upstream, submodule, Cargo.lock, monero-oxide, crypto-bigint, builder image and rustc pins, with licenses and public review references (with scope caveats) |
| `build.sh` | `prepare` clones and verifies the pins; `build` and `run` go through the heavy lock; `receipts` writes toolchain, artifact and pin receipts plus `MANIFEST.sha256` |
| `harness/` | `vanguard_tests.cpp` and its CMake target. `build.sh` copies it into the scratch clone as `tests/vanguard` |
| `expected-vectors.txt` | The pinned vector list: each vector's expectation and documented finding, in harness order |
| `verify.py` | Checks an evidence directory: manifest, pins (including the exact upstream injection diff and vector hashes), determinism, the pinned vector list, verdicts, raw random-input verdicts, coverage, findings and an independent address decode |
| `test-verify-refusals.py` | Tamper controls: each mutated copy of the evidence must be refused by `verify.py` |

## Run

```sh
vanguard/build.sh all            # prepare, build (heavy lock), run twice (heavy lock), receipts
vanguard/verify.py               # prints PASS_VANGUARD_RECEIPTS or FAIL <reason>
vanguard/test-verify-refusals.py # prints PASS_VANGUARD_REFUSALS
```

Scratch work lives in the gitignored `build/vanguard-src`. The evidence directory
defaults to `research/evidence/vanguard-tjs356-2026-09-23`.

Requirements:
- Docker with the accepted builder image present locally. It is used by ID with `--pull=never --network=none`.
- A host rustup toolchain whose `rustc -V` equals the pinned string. It is mounted read-only at `/opt/rust`.
- Network access for `prepare` only: `git fetch` of the pin and `cargo fetch --locked`. The container build runs offline.

The recorded cold build at `-j3` took 455 s and peaked at 2.69 GB of container memory. The
binary runs 187 vectors in about a minute.

## Verdicts

Reject vectors run in a forked child with core dumps disabled. That way a panic
or abort inside the upstream code becomes a recorded verdict
(`reject_abort_signal_6`) rather than the end of the run.

`results.json` holds only run-independent facts, so run 1 and run 2 must match
byte for byte. Some vectors take their proofs and keys from fresh randomness:
`fcmp_pp.fresh*` and `sal.*`. For these, `results.json` records only the verdict
class, and each run's `metrics.json` keeps the raw observation under
`random_input_observed`.

Two observed deviations from the ideal verdict are documented rather than hidden.
They are marked in `results.json` only when the exact observed verdict reproduces:
- **VG-F1:** one appended byte is accepted. It is marked on all seven `extended_1_byte` vectors (five fixed, two fresh).
- **VG-F2:** an `n_layers - 1` claim aborts the process. It is marked on the four fixed vectors that abort.

`verify.py` accepts a process abort as a rejection only on those four fixed vectors and,
as a raw observation, on the two fresh `wrong_n_layers_minus_1` vectors. On those two the
abort depends on the random proof bytes, and `results.json` records the class `reject`.
Every other rejection must be a clean `false` or a caught exception.

See `research/vanguard-tjs356-2026-09-23.md`.

## Bounded sync and reorg integration (TJS-953)

`sync/sync_tests.cpp` exercises two FAKECHAIN cores in one process. It delivers
serialized transactions and an out-of-order block, restarts the peer with its
database retained, switches to a competing v17 branch, and switches back. The
cores converge on tip hash, trusted root and depth, transaction validity, pool
state, and key-image rollback and reapplication. Stale-root transactions are
rejected through both a block supplement and the retained pool. TJS-959 accepted
the exact one-process slice at `d5b4afbb` as bounded engineering evidence.

```sh
python3 -B vanguard/run-sync.py --out build/vanguard-sync-exact01
python3 -B vanguard/verify-sync.py build/vanguard-sync-exact01
```

At the accepted TJS-953 commit, `sync/process_tests.cpp` added two operating
system processes, each with its own FAKECHAIN core and LMDB directory.
Transactions and blocks crossed anonymous pipes as serialized frames. That
receipt remains pinned at `10a26e0` and `572a1e2`.

The current `sync/process_tests.cpp` extends that witness with a private Unix
socket, serialized headers before blocks, reconnect and tip replay, and
recovery after oversized and truncated frames. It exercises the same bounded
fork, stale-root, and reverse-switch paths. Peer core restart retains its
database; subsequent blocks are admitted after restart without a backlog pull.

```sh
python3 -B vanguard/run-sync-process.py --out build/vanguard-socket-tjs990-exact01
python3 -B vanguard/verify-sync-process.py build/vanguard-socket-tjs990-exact01
```

Both runners use the accepted pinned upstream scratch checkout and cache from
`build.sh prepare`, the existing heavy-work lock, and network-disabled
containers capped at two CPUs, 4 GiB memory, 256 PIDs, and 900 seconds. They
write two fresh executions with source, command, cgroup, and state receipts.
TJS-958 accepted the pipe-based two-process code commit `10a26e0` and receipt
bundle at `572a1e2` with no required findings. See
`research/vanguard-sync-process-tjs953-2026-09-29.md` for that historical
result. The new socket receipt and limits are in
`research/vanguard-socket-tjs990-2026-09-29.md`. Neither result exercises the
daemon's P2P protocol.

## Native daemon P2P over the private socket (TJS-996)

`run-daemon-p2p.py` builds the pinned upstream `monerod` and wallet RPC, then
starts two distinct regtest daemon processes with separate LMDB directories
inside one network-disabled container. Node A's exclusive peer is a loopback
proxy. The proxy carries unmodified native Levin P2P frames through a mode-0600
AF_UNIX stream to node B's loopback listener. The harness captures exact
transaction and block notifications, then replays or changes those frames on
the same stream. It records both daemons' RPC state and parser logs.

```sh
python3 -B vanguard/run-daemon-p2p.py --out build/vanguard-daemon-p2p-tjs996-exact01
python3 -B vanguard/verify-daemon-p2p.py build/vanguard-daemon-p2p-tjs996-exact01
```

The witness covers an FCMP++ transaction relayed into both pools and confirmed
on both chains, duplicate and malformed P2P notifications, a partition and
longer competing branch, key-image chain-state rollback after reconnection,
and later healthy block relay. The malformed transaction changes its binary
varint; malformed header and block change the captured block's header and
coinbase body. The verifier checks exact source hashes, raw native frames,
daemon rejection logs, state snapshots, the manifest, loopback-only listeners,
container flags, and cgroup OOM counts. This is an accelerated fixed-difficulty
regtest with disposable wallet keys; it does not establish loaded 90s/120s
performance, public-network safety, payout behavior, or launch readiness.
