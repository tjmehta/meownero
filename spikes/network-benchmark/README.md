# Bounded network benchmark

`chain/test-network-p2p.sh` runs two existing fifteen-patch daemons inside one
network-disabled container. Two interruptible TCP proxies carry the actual P2P
protocol. The RPC client only generates a block at its originating daemon; it
never transfers a block to the receiving daemon. The fixture address and local
block-generation flow come from `chain/test-reorg.py`.

```bash
export MEOW_BUILDER_IMAGE=sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e
chain/test-network-p2p.sh /path/to/built-source /tmp/meow-swarm-network-unique-run
python3 spikes/network-benchmark/check-readiness.py --source /path/to/built-source
# Optional: --candidate-source /path/to/separate-experimental-90-source
```

The network test takes the shared heavy lock and caps its entire workload at
1.5 GiB/no swap/two CPUs. It binds no host ports, uses only a disposable chain
and public test fixture address, and mounts existing binaries/source read-only.
The readiness inventory intentionally exits **2 (blocked integration)** until
an actual paired-workload implementation replaces its listed missing receipts.
It verifies source constants and matched arithmetic; it cannot certify proof
integration merely because an FCMP source directory exists.

The test warms fresh databases with 65 blocks, records 12 connected observations,
cuts both TCP connections, creates three/four competing blocks, restores P2P,
checks the three losing blocks' orphan flags and both daemons' selected tip,
then probes malformed transport rejection and healthy relay. Issuance is checked
on both nodes. Each stream gets 20 ms per chunk plus 64 KiB/s serialization;
this is a small deterministic TCP shaper, not a calibrated WAN simulator or a
64 KiB/s aggregate topology cap. The host page cache is uncontrolled and never
purged. `resources.json` captures the cgroup settings/peak/events and exit codes.

Measurements run at fixed difficulty one with accelerated empty blocks. Timings
include block generation and RPC; receiver polling has a 25 ms interval. Twelve
samples cannot establish tail latency: nearest-rank p95 and p99 are just the
observed maximum. The three forced orphans do not estimate a natural stale rate.
No claim covers FCMP, loaded throughput, real miners, native DAA, higher-work
forks, privacy escape, long uptime, or the peer policy in upstream PR #11283.

## Paired 90/120 experiment still requires integration

The approved comparison preserves 7,500,000,000 atomic units/second: 0.9/120
and 0.675/90. At the present 300,000 penalty-free floor and 600,000 maximum,
the candidate's **configured** floors must be 225,000 and 450,000 respectively.
That gives 2,500 penalty-free weight/second and 5,000 maximum weight/second in
both arms at the floor. Equal per-block weight instead adds one third nominal
capacity/second. These are budgets, not observed throughput. These issuance rates are nominal
unpenalized subsidy; loaded runs must also record actual rewards and matched
normalized fullness because the existing weight penalty can reduce issuance.

Before claiming matched capacity, the separate experimental binary must prove
accepted/rejected weight boundaries in floor-dominated, short-median,
long-median and surge states. Record configured values, daemon RPC values,
actual accepted weights and failed over-budget blocks separately. Simply
throttling the load generator does not enforce a consensus capacity limit.
Changing the minimum alone does not guarantee a persistent 0.75 ratio under
evolving medians. The existing 100/100,000-block windows represent different
wallclock durations at 90 and 120 seconds; matching those durations requires
an explicit experimental choice/rounding policy, not a silent production edit.

Use the same ordered transaction/proof mix and offered transactions/second,
paired topology/link conditions, identical CPU/RAM limits, fresh chain databases
and explicitly equal warmup criteria. Record output-set/tree depth, cache state,
proof count and size, coinbase/transaction weight and wire/header overhead.
Headers and coinbases happen one third more often at 90 seconds; payload
capacity/second is not implied by equal total weight budgets. Use the same
wallclock run and confirmation horizons (for example, 40 vs 30 nominal blocks
per hour); equal confirmation counts have different time horizons and do not
establish equal security.

Required real receipts include proof validation and relay timing distributions,
accepted payload/second, offered/confirmed transaction counts, competing/stale
blocks, partition/rejoin and difficulty recovery. Pin the complete FCMP daemon,
wallet, Rust FFI/dependencies and proof format together, construct/spend real
private transactions and test rejection/rollback before measuring. Synthetic
proof delays or an upstream component microbenchmark cannot fill those fields.

## Clean fifteen-patch reproduction

```bash
export MEOW_BUILDER_IMAGE=sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e
export MEOW_REPRO_BUILD_RUNNER="$PWD/chain/network-build-guard.sh"
bash chain/test-reproducibility.sh /tmp/meow-swarm-network-unique-reproduction
```

The opt-in guard checks >=5 GiB available RAM/disk before locking, rechecks after
locking, releases/retries if insufficient, and holds the lock for one complete
build/test run. It enforces one compiler job and 4 GiB/no swap/two-CPU containers,
including the existing child test scripts. The second clean build reacquires
the guard. Generic `build.sh` still honors `MEOW_JOBS` and has no swarm policy.
Cache-disabled builds do not mount the shared ccache volume. The comparison
includes binaries, image ID, package list, source HEAD/tree, submodules, patch
input hashes, compiler/CMake versions and all three executable versions. It
remains same-image source reproducibility, not toolchain reconstruction or
cross-host reproducibility.
