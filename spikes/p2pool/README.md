# P2Pool compatibility gate (local spike)

**Blocked for Meownero pool onboarding. No working pool is claimed.** Current
P2Pool needs changes to its address serialization, subsidy construction and
sidechain validation/identity before it can mine Meownero correctly. This spike
executes the narrow compatibility boundary without modifying production patches.

The [track report](../../research/swarm-mining-2026-09-12.md) maps the exact gaps
and distinguishes executed checks from source inspection.

## Selected 9/90 and fallback 12/120 source adaptation

The historical runner below predates the selected issuance policy. The new
[resumed report](../../research/resume-mining-2026-09-12.md) records an isolated
mainnet profile adaptation of the pinned reward and address routines, unchanged
fork lookup linked against Meownero's table, and genesis/sharechain refusal.
It remains **incompatible as a full pool**; no P2Pool process or payout is tested.

```sh
bash spikes/p2pool/run-selected.sh \
  /tmp/meow-swarm-mining-p2pool-source \
  /tmp/meownero-wallet-verified-source-20260912 \
  <repo>/spikes/selected-issuance \
  /tmp/meownero-mining-selected-YOUR_UNIQUE_SUFFIX
```

The coordinator's overlays are read-only inputs, applied and reversed only in
the new output directory. All consumed upstream/overlay files are hash-pinned.
This bounded source compilation uses the authorized lightweight exception:
512 MiB, no swap, half a CPU, low CPU shares, one compiler job and no network.
It does not take the heavy lock from network reproduction. Do not expand it
into a full build without the shared lock and required resource preflight.

Regular mainnet prefix 120 fits the pinned one-byte/95-character decoder.
The adapter retains checksum and curve-point checks, rejects other payout
address types, and omits only upstream's informational FCMP torsion warning.
Neither FCMP checks nor testnet/stagenet varint-prefix support are implemented.
Generated diffs expose every routine change. Experimental profile IDs are test
domains, **not production P2Pool consensus IDs or chosen launch identities**.

## Reproduce historical controls

Use fresh, unique output directories. The daemon source argument is mounted
read-only; the harness writes only to its output directory. No private keys are
needed: the public address is the existing disposable test fixture.

```sh
bash spikes/p2pool/fetch.sh /tmp/meow-swarm-mining-source-YOUR_UNIQUE_SUFFIX
bash spikes/p2pool/run.sh \
  /tmp/meow-swarm-mining-source-YOUR_UNIQUE_SUFFIX/source \
  /tmp/meownero-wallet-verified-source-20260912 \
  /tmp/meow-swarm-mining-results-YOUR_UNIQUE_SUFFIX
```

Requirements: existing Docker builder image in `run.sh`, curl, Python 3, flock.
No host package installation. The pinned archive includes the hardfork tables;
submodule checkout is unnecessary because this is **not a full P2Pool build**.
The fetch step downloads public source over HTTPS. Tests have `--network none`,
loopback-only listeners inside the container, no published ports, one compiler
process, two CPUs maximum, 1 GiB memory/swap combined, and the shared heavy lock.
The compilation is only two small routines; there is no large build requiring
the 5 GiB availability precondition. Do not extend this runner into a large build
without enforcing that precondition.

`source_probe.py` verifies 19 source hashes, extracts two exact upstream function
bodies, links unchanged upstream hardfork tables, and checks seven cases. Other
parser findings are explicitly **static source guards**, not execution of the
complete wallet/share parser. Generated code retains upstream copyright notice.

`devnet_probe.py` starts the already verified daemon in native mainnet mode with
an empty disposable data directory and networking disabled. It checks P2Pool's
required RPC fields, compares the compiled routines with actual miner data,
submits templates with incompatible coinbase amounts as negative controls,
accepts the original template, and receives a real ZMQ mining notification.
These amount substitutions are not serialized P2Pool shares or pool templates.

Exit 0 means **the expected incompatibilities and positive controls were
verified**. Both result JSON files deliberately contain `"compatible": false`.
Changed source hashes, unexpected daemon behavior or missing notifications fail
the runner. It never starts a P2Pool process or authorizes onboarding.

## Required future integration

A reviewed P2Pool fork would need an explicit Meownero chain profile and genesis
binding; varint address prefixes; flat-reward construction and consistent output
size accounting; Meownero fork-height validation; separate sharechain identity
and isolated peer discovery; and tests of share acceptance, competing share
chains, payouts and wallet recovery. Mainchain difficulty remains daemon-owned.
Low-hashrate share difficulty and PPLNS behavior require measurement. These are
P2Pool-side consensus changes, beyond an RPC shim. This spike makes none of those
changes in its historical runner and supplies no launch configuration. The
selected runner above supplies only the documented isolated adaptations.
