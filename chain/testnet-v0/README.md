# Testnet v0: isolated two-peer launch, recipe v1

This recipe starts two real C++ daemons on the accepted selected 9 MEOW / 90 s
candidate. It checks the live profile, mines at least three empty blocks with
the daemon's native miner, waits for P2P convergence, saves public receipts and
stops both nodes. It needs no wallet or private keys.

This is the candidate assembly and launch check assigned in TJS-229, from the
[TJS-223 freeze](../../docs/testnet-v0-freeze-tjs223-2026-09-20.md). The daemon uses
its **mainnet mode inside an isolated container** because that mode contains the
selected fork table. These are local test coins with no value. Do not add
`--testnet`, `--stagenet`, `--regtest`, fixed difficulty or public networking.
The inherited testnet/stagenet fork tables are not this candidate. The 12/120
fallback requires a different chain and is outside this recipe.

## Inputs and prerequisites

Run from the repository root on Linux with Python 3.10+, Docker access and at
least 5 GiB available RAM and disk. The existing shared heavy-work lock must be
free. The launcher refuses a busy lock; it never steals one or stops another
worker. Its lock path is `/tmp/meownero-swarm-20260912-heavy.lock`.

The accepted immutable builder image must already exist locally:
`sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e`.
The recipe uses `--pull=never` and does not build or download anything.

The default binary is the completed TJS-40 reproduction:
`build/repro-selected-20260918/selected-9-90/first/source/build/release/bin/monerod`.
Use `--binary /absolute/path/to/monerod` for another copy of the same bytes.
Its required SHA-256 is
`b79cb49dbea95c0eeff7dca8c945d65f4fab3d49fb626fcbe7a9343569d4a2c1`.

[`baseline.json`](baseline.json) pins the following inputs and their hashes:

- `chain/upstream.lock`: Monero v0.18.5.1 at
  `4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5`, including all four submodule pins.
- Fifteen ordered patches, historical HEAD
  `7410c04bab0e304112710d63c3225c110bd8b4de`, tree
  `4db958cb96d72943c5c2433bd5f4a8f730037148`.
- Selected issuance, unit and gamma overlays and their source locks. The
  selected issuance patch is
  `de750169f3f3aac75de8325a09570343cc10df7cf2da52dec9b084ad0b3414fe`.
- Build/staging scripts, builder Dockerfile and TJS-40 source diff, compiler
  versions, package manifest, configuration and binary reproduction receipts.

The launcher verifies every baseline input before executing the binary. It
reuses the accepted source-to-binary evidence. It does not claim a new build or
independent toolchain reconstruction. If an input differs, recover the accepted
input or obtain review of a new candidate; do not replace the pin to make a run
pass. Plain `chain/build.sh` alone produces historical economics, not this
selected candidate.

## Run and inspect

Choose a path that does not exist, including an empty directory. The launcher
never adopts or deletes a previous data directory.

```sh
python3 chain/testnet-v0/launch.py --work build/testnet-v0-launch-01
python3 chain/testnet-v0/verify.py build/testnet-v0-launch-01
sha256sum -c build/testnet-v0-launch-01/INPUTS.sha256
```

`--check-only` verifies admission without creating the work directory or
starting any processes. `--profile path.json` admits only an exact copy of
[`profile.json`](profile.json). There are no arbitrary daemon argument or
container-network overrides.

Expected events are `profile_verified`, `native_mining_started`, `converged`.
The launcher and container exit 0, both daemon exit codes are 0, and the
verifier reports `PASS_RECEIPT_RECONCILIATION`. Expect a top block index of at
least 3, the same hash and cumulative work on both peers, and emission equal
to `top index * 9000000000000` atomic units. RPC `get_info.height` includes
genesis and is one greater than the top index. Hashes, elapsed time, work and
the final number of mined blocks can vary between runs. Mining uses genuine
RandomX, native DAA and ordinary timestamps; there is no fixed-difficulty or
timestamp override. This tiny chain does not measure steady-state 90 s cadence.

The container has no external network interface or published ports. Peer 0
listens on `127.0.0.1:28080`, peer 1 on `127.0.0.1:28180`; each explicitly names
only the other peer. RPC is on loopback ports 28081 and 28181 inside the same
container. ZMQ, UPnP, DNS checkpoints and updates are disabled. Empty explicit
config files prevent inherited configuration. These ports do not touch the F4
pool's host or container ports. The entire container has 4 GiB RAM, no swap,
two CPU quotas and a 256-process limit. The run has a 420 s wall-time limit
plus up to 75 s for forced cleanup.

While running, the owned container name is in `container-command.json`.
For another local tool to inspect the network, use `docker exec` with that
explicit name and the above loopback RPC addresses. Host loopback cannot reach
the container RPC. The recipe finishes automatically after collecting its
bounded witness; it is not a persistent service launcher.

## Refusals and recovery

Run the actual-command admission checks with another fresh path:

```sh
python3 chain/testnet-v0/test-refusals.py --work build/testnet-v0-refusals-01
```

This demonstrates wrong genesis hash, nonzero genesis reward, wrong subsidy,
target, fork version, fork height, pool profile, enabled pool, address prefix,
testnet mode, stale directory and binary hash. Each exits 2 with `REFUSED` and
a specific reason before node launch. An accepted-input control exits 0.
The stale-directory sentinel remains unchanged. Each case retains its exact
command, output and exit code. Wrong genesis/reward/target/fork declarations
are admission tests, not experiments against an altered consensus binary.

The pool profile is a compatibility declaration for the selected prefix-120
9/90 chain. `pool_enabled` must be false. This recipe launches no pool and
cannot accept, validate or close the F4 implementation; TJS-187/TJS-224 own it.
Stock P2Pool and fallback declarations are refused here.

For startup or mining failure, read `run.log`, both `peer*.stdout.log`,
`peer*.log`, `result.json` and exit receipts. A resource refusal may occur
before daemon receipts exist. Keep the failed directory as evidence and rerun
with a new path after resolving the cause. Do not remove someone else's data
or lower the resource gate. Ctrl-C stops the exact owned container. Its name
can also be passed to `docker stop --time 65 NAME` if the launcher is lost.
Successful completion removes the container; a subsequent cleanup receipt
may say `No such container` because Docker's `--rm` already removed it.

Data stays under `WORK/data/peer0` and `WORK/data/peer1`. After checking the
receipts, an operator may remove only that run's `WORK/data` directory to
reclaim space. The launcher intentionally has no resume/restart option.
Restart, late-peer sync, transactions, wallet recovery and reorg journeys are
separate milestone checks.

## Evidence and invariant map

The output directory holds all container/daemon/mining commands, public logs,
initial profile readback, peer connections, every mined header, final RPC
responses, resource limits/peak/OOM events, exit codes and the final result.
`INPUTS.sha256` checks repository inputs from the repository root;
`EVIDENCE.sha256` checks public receipts from the output directory. Data files
are excluded from the public receipt manifest. No seed or private key is
created, read or copied by this recipe.

| Invariant | Admission / live check | Retained evidence |
| --- | --- | --- |
| Exact candidate | Fixed binary hash, ordered patch/input hashes | `baseline.json`, `INPUTS.sha256`, `BINARY.sha256` |
| Fresh zero-reward genesis | New directories, genesis hash/reward/version readback | `profile-readback.json`, `headers.json` |
| 9 MEOW / 90 s | Profile, template reward, both nodes' target, all rewards | `profile-readback.json`, `rpc-final.json`, `headers.json` |
| v16 at height 1 | Fork readback, height-one template and mined headers | `profile-readback.json`, `headers.json` |
| Pool compatibility | Fixed prefix/profile; pool disabled | `profile.json`, refusal receipts |
| Actual peer convergence | Native mine on peer 0, P2P to peer 1; no block-copy RPC | `peers-*.json`, logs, `rpc-final.json` |
| Work and supply | Sum header difficulty/rewards; reconcile both RPC totals | `headers.json`, `rpc-final.json`, `result.json` |
| Isolation and cleanup | No external network, local RPC, caps, owned exits | Commands, `resources.json`, `*.exit`, `cleanup.json` |

The separate verifier checks saved receipt consistency. It is not an
independent operator run, external audit, FCMP/privacy acceptance, F4 closure,
90-second GO, public testnet publication or mainnet readiness claim.
