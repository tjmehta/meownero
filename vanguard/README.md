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

## Bounded two-core sync and reorg diagnostic (TJS-953)

`sync/sync_tests.cpp` runs two separate FAKECHAIN core databases in one
network-disabled process. It relays serialized prerequisite and FCMP++
transactions, delivers one block ahead of its predecessor, restarts the peer
without clearing its database, then feeds a competing branch that changes the
stored tree root at the spend's reference height. The cores must converge on
tip hash, root, depth, spent key-image state, chain transaction presence and
pool state. A block carrying the old transaction as an explicit supplement must
fail on the changed root, and the stale pool entry must be removed.

```sh
python3 -B vanguard/run-sync.py --out build/vanguard-sync-exact01
python3 -B vanguard/verify-sync.py build/vanguard-sync-exact01
```

The runner requires the accepted pinned upstream scratch checkout and cache
from `build.sh prepare`, uses the existing heavy-work lock, and caps each
network-disabled container at two CPUs, 4 GiB memory, 256 PIDs and 900 seconds.
It writes two fresh executions and a source, command, cgroup and state receipt.
The test is a diagnostic slice, not completion of TJS-953: the two cores share
a process, the original branch is not reapplied after the deep reorg, and
independent exact-commit QA remains open. See the TJS-953 report for the
observed reverse-switch failure and next action.
