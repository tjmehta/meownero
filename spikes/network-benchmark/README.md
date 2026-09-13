# Bounded network benchmark

TJ selects gated 9/90 versus 12/120; see the [decision](../../research/decision-2026-09-12-issuance.md). The checker now inventories selected profiles by default. Recorded P2P runtime results remain historical controls; selected binaries and network performance remain unverified.

`chain/test-network-p2p.sh` runs two existing fifteen-patch daemons inside one
network-disabled container. Two interruptible TCP proxies carry the actual P2P
protocol. The RPC client only generates a block at its originating daemon; it
never transfers a block to the receiving daemon. The fixture address and local
block-generation flow come from `chain/test-reorg.py`.

```bash
export MEOW_BUILDER_IMAGE=sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e
chain/test-network-p2p.sh /path/to/built-source /tmp/meow-swarm-network-unique-run
python3 spikes/network-benchmark/check-readiness.py --family historical --source /path/to/built-source
# Optional: --candidate-source /path/to/separate-experimental-90-source
```

The network test waits at most 60 seconds for the shared heavy lock, checks
>=5 GiB available RAM, and caps its entire workload at
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

## Selected 9/90 and gated 12/120 profiles

The selected comparison is **9 MEOW/90 seconds** versus the gated **12 MEOW/120
seconds** fallback: 100,000,000,000 atomic units/second, or 3,153,600 MEOW per
365 days before penalties. This branch's fifteen production patches and frozen
reproduction remain the historical 0.9/120 control. Historical 0.675/90 and
0.9/120 each issue 236,520 MEOW/year; select `--family historical` explicitly
when inspecting them.

`prepare-profiles.py` reads the coordinator's `spikes/selected-issuance` overlays
from a supplied path and prepares two disposable full tracked-source snapshots.
It verifies current15 HEAD, clean tracked state, initialized submodules and the
coordinator's source-lock hashes. Every tracked input is hashed; binaries,
untracked files and Git metadata are excluded. Internal tracked symlinks are
preserved (their manifest hash covers link text); escaping symlinks are refused.
Input source and production patches are never edited. Use a new output path.

```bash
# Run preparation/checker in an offline <=512 MiB container, or under the shared lock.
python3 spikes/network-benchmark/prepare-profiles.py \
  --source /path/to/verified-current15-with-submodules \
  --overlays /path/to/coordinator/spikes/selected-issuance \
  --output /path/to/new-prepared
python3 spikes/network-benchmark/check-readiness.py \
  --source /path/to/new-prepared/fallback-12-120 \
  --candidate-source /path/to/new-prepared/selected-9-90
# Intentional exit 2: BLOCKED_INTEGRATION, even when binaries/directories exist.
python3 chain/test-network-profiles.py -v
# After building the corresponding staged source, opt into its exact profile:
chain/test-network-p2p.sh /path/to/built-selected-source /path/to/new-p2p selected-9-90
```

These source snapshots are unbuilt. Full selected builds and profile-specific
unit fixtures remain required: `meow_emission.constant_is_0_9_meow` in current15
hard-codes the historical reward. The P2P harness accepts all four named profiles,
checks source reward/spacing before starting, and checks actual emission and RPC
target spacing on both nodes. Its default stays historical for existing callers.
It records an empty-block correctness result only; no paired loaded comparison
or binary/source provenance follows from that result.

The readiness checker defaults to the selected family and reports mismatched
historical input as a blocker. Observed source values and proposed matched-time
budgets are separate. The selected overlays **do not change capacity rules**:
both retain a 300,000-weight floor and 100/100,000-block median windows. Their
nominal floor rates are therefore 3,333⅓ versus 2,500 weight/second, with
9,000/9,000,000 versus 12,000/12,000,000-second windows. No enforced capacity
normalization or FCMP integration is claimed.

## Paired capacity experiment still requires integration

At the present 300,000 penalty-free floor and 600,000 maximum,
the 90-second arm's **proposed experimental** floors are 225,000 and 450,000 respectively.
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
locking, releases/retries if insufficient (60-second wait by default, exit 75;
`MEOW_NETWORK_WAIT_SECONDS=1..3600` can set a bounded wait), and holds the lock for one complete
build/test run. It enforces one compiler job and 4 GiB/no swap/two-CPU containers,
including the existing child test scripts. The second clean build reacquires
the guard. Generic `build.sh` still honors `MEOW_JOBS` and has no swarm policy.
Cache-disabled builds do not mount the shared ccache volume. The comparison
includes binaries, image ID, package list, source HEAD/tree, submodules, patch
input hashes, compiler/CMake versions and all three executable versions. It
remains same-image source reproducibility, not toolchain reconstruction or
cross-host reproducibility.

## Isolated incremental selected builds

`build-profile.sh` uses a disposable copy of the verified **first** clean15 source
and build tree. It verifies the seven completed receipts, all 4,320 tracked source
hashes and the collection-time build-file inventory before copying. The original
is mounted read-only. Copies use `cp -a --reflink=auto`, preserving build mtimes
and `/src` CMake paths without hard-linking back to the historical tree.

The coordinator supplies `selected-unit-fixtures.patch` and
`fixture-source-lock.json` beside the monetary overlays. The approved fixture
SHA-256 is `360acc9ea7bd014225aa20ad93bee19c5f5444d126b36f93ffed0f913030f0e7`.
Its source lock must match the original `block_reward.cpp` before application.
The runner applies the monetary overlay, then the common fixture patch; fixture
changes may touch only `tests/unit_tests/` and must replace the historical reward
test. It refuses an unreviewed fixture hash. No production patch is edited.

```bash
bash spikes/network-benchmark/build-profile.sh \
  /tmp/meow-swarm-network-20260912-run/reproduction/first \
  /path/to/coordinator/spikes/selected-issuance \
  selected-9-90 \
  /path/to/coordinator/spikes/selected-issuance/selected-unit-fixtures.patch \
  /path/to/NEW-selected-output
# Run fallback-12-120 separately only after reviewing the first result.
```

The shared guard holds the heavy lock across verification, copying, compilation
and tests. It checks >=5 GiB available RAM and disk; the runner also checks the
output filesystem. Containers use the same immutable image, 4 GiB/no swap,
two CPUs, one compiler job and disabled ccache. Compilation and the non-DNS
native partition use no networking. A separately logged DNS-only container uses
ordinary bridge networking, matching the existing CI environment. A two-hour
container timeout and owned-container cleanup bound interruption handling.
Neither a failed compiler nor a failed `tee` log write reports success.

Inherited daemon/wallet/test executables are removed from the **copy** before
building all three binaries plus `unit_tests` and the alternative-floor test
executable. Existing object/archive files can be reused, so this is an
**incremental selected build**, not clean selected reproduction. The runner
records copied-input provenance, all overlay hashes, source diff, changed-file
hashes, compiler/CMake logs, executable hashes/versions, XML/test logs and cgroup
limits/events. The historical input hashes are checked again afterward.

If the old build cache is gone, set `MEOW_PROFILE_SOURCE_ONLY=1` and pass the
reconstructed pinned source directory as the first argument. This mode refuses
inherited build outputs and verifies the original revision, submodules and full
frozen source manifest before copying. It creates a fresh build directory; the
receipt labels this as a single fresh selected build, with no preserved historical
build claim. Economic, approved reward, and source-locked gamma fixture overlays
apply only to the disposable copy.

Tests include the consensus/protocol selection, both difficulty-floor selections,
and the exact existing native CI selection with only
`ban.subnet`, `http_server.response_soft_limit`, and `notify.works` excluded.
Native fixture data is copied to `/tmp/test-data`. The DNS phase selects only
`AddressFromURL.*:DNSResolver.*`; the offline phase selects the complement.
`merge-native-results.py` rejects missing/extra/duplicate/unexecuted/failed tests
and requires their union to equal the original CI list. `offline.exit` and
`dns.exit` record phase termination; `build.exit` exists only at final termination.
No historical reward failure
is treated as an expected exclusion. Any new failure stops the run for review.
After a successful build, `chain/test-network-p2p.sh OUTPUT/source OUTPUT/p2p PROFILE`
runs the separate profile-specific empty-block P2P check under its own guard.
A native test pass still does not establish loaded capacity, intended FCMP
integration, wallet recovery, aggregate-consumer correctness, or launch readiness.

September 13 recovery, gamma controls, resource-wrapper checks and current build
status: [recovery report](../../research/recovery-network-2026-09-13.md).
