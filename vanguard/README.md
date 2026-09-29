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

`sync/process_tests.cpp` adds two operating-system processes, each with its own
FAKECHAIN core and LMDB directory. Transactions and blocks cross anonymous
pipes as serialized frames. It exercises the same bounded delivery, fork,
stale-root, and reverse-switch paths. Peer restart retains its database;
subsequent blocks are admitted after restart, without a backlog pull.

```sh
python3 -B vanguard/run-sync-process.py --out build/vanguard-sync-process-exact02
python3 -B vanguard/verify-sync-process.py build/vanguard-sync-process-exact02
```

Both runners use the accepted pinned upstream scratch checkout and cache from
`build.sh prepare`, the existing heavy-work lock, and network-disabled
containers capped at two CPUs, 4 GiB memory, 256 PIDs, and 900 seconds. They
write two fresh executions with source, command, cgroup, and state receipts.
TJS-958 accepted the two-process code commit `10a26e0` and receipt bundle at
`572a1e2` with no required findings, closing the stated two-process delivery
gate as engineering evidence. See
`research/vanguard-sync-process-tjs953-2026-09-29.md` for the exact commands,
hashes, and limits. This does not exercise daemon P2P or socket transport.
