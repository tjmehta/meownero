# Private operator and bootstrap preparation

This recipe is executable through preparation only. `network.py` has no launch
subcommand. `readiness` exits3 and lists the unresolved protocol/native gates.
Proposal configs must not be fed to the existing upstream packages.

## Inspect and prepare

Use the task's existing execution checkout and an existing task-owned private
scratch directory. The tool accepts only a new leaf below an owner-only parent
outside the source checkout. It never overwrites an old attempt or reads wallets.

```sh
python3 -B vanguard/network/network.py validate
python3 -B vanguard/network/network.py check-source --source "$PINNED_UPSTREAM_SOURCE"
python3 -B vanguard/network/network.py identity-overlay \
  --source "$PINNED_UPSTREAM_SOURCE" --out "$PAPERCLIP_RUN_SCRATCH_DIR/identity-new"
python3 -B vanguard/network/test_network.py \
  --source "$PINNED_UPSTREAM_SOURCE" --scratch "$PAPERCLIP_RUN_SCRATCH_DIR" \
  --evidence "$PAPERCLIP_RUN_SCRATCH_DIR/checks-new"
python3 -B vanguard/network/network.py readiness
```

The source-check command reads the thirteen pinned paths, five submodule HEADs
and Cargo.lock. It does not download dependencies, configure, build, alter the
source cache or attest executable bytes. The identity-overlay command writes a
patch and original/changed SHA256 receipt, not a runnable node tree.

Copy [operators.example.json](operators.example.json) to task scratch. Keep its
profile hash. Replace nulls only with explicitly assigned operator pseudonyms,
distinct seed node IDs and actual claimed loopback endpoints. Nulls deliberately
fail preparation; this document does not allocate operators or ports. Endpoint
availability and process ownership must be checked by the eventual native runner.
The prepared client binds fixed48080/48081/48083; its selected seed must use a
different port. Recovery endpoints and operator identities must be distinct.
Literal fixture identities in tests are not operating hosts.

```sh
python3 -B vanguard/network/network.py prepare \
  --bootstrap "$PAPERCLIP_RUN_SCRATCH_DIR/operators.json" \
  --role primary --node-id observer-a \
  --out "$PAPERCLIP_RUN_SCRATCH_DIR/observer-primary-new"
python3 -B vanguard/network/network.py prepare \
  --bootstrap "$PAPERCLIP_RUN_SCRATCH_DIR/operators.json" \
  --role recovery --node-id observer-a \
  --out "$PAPERCLIP_RUN_SCRATCH_DIR/observer-recovery-new"
```

Each command writes mode0600 daemon/wallet `.conf.proposal` files and a
profile-binding receipt under a new mode0700 directory. It creates an empty
namespace/node directory and records the native TESTNET LMDB path. It never opens
a port, starts a process, creates LMDB, connects to a seed or creates credentials.
The two preparations are alternative review inputs; do not start both clients.
Canonical JSON details follow the [Python JSON interface](https://docs.python.org/3.14/library/json.html).
The reader bounds input to64KiB and rejects duplicate keys/nonfinite numbers.

## Capacity proposal and boundaries

Use already existing capacity after platform-owner coordination. Proposed roles
are two independent validating seeds with distinct operators and owned persistent
data roots, plus one client and its private wallet owner. Seed primary and recovery
are equal validators; neither can mint through remote RPC. No seed holds wallet
files, exposes RPC or accepts a wallet bootstrap-RPC role. These are roles to
assign, not new paid services or a named-maintainer prerequisite.

The first native run must be finite, local and contained: existing shared
`/tmp/meownero-swarm-20260912-heavy.lock`, nonblocking; at least5GiB available
memory and free disk; no build before an agreed platform slot. Use one owned
network-none container capped at2CPUs,4GiB memory/no swap,256PIDs, no capabilities,
no-new-privileges, no published ports and900s wall lifetime. Use existing cached
builder/binaries only when exact completed-overlay receipts match. Any necessary
new build uses a private copy, offline dependencies and one compile job under
the same lock/caps. Do not move work to another host to evade admission checks.
No Docker runtime, unrelated container, Mac/device claim or shared cache changes.

All native P2P and RPC listeners must bind loopback in the isolated container.
For two peers choose distinct explicit ports and connect only the owned primary
and recovery endpoint. No public, personal-host, DNS, foreign built-in seed, UPnP,
ZMQ or daemon bootstrap-RPC exposure. An exclusive-node setting suppresses
upstream discovery; it does not remove foreign lists from an unmodified binary.
The completed overlay/launcher must also prove there is no fallback when that
peer is unavailable. Profile metadata is not authenticated remote identity;
adverse native handshakes remain required.

Daemon RPC must receive a fresh runtime RPC_LOGIN through the private process
environment before startup. Native wallet RPC authentication stays enabled and
restricted for observation. Never put auth values into commands, configs,
receipts, screenshots or evidence. Wallet RPC's native generated login file is
private state. A separate authenticated signer/controller must own payment and
restore operations; these are unavailable on the restricted observer. No shared
credential reuse, no read of release signing keys and no key-custody change.

Native peer lists reveal endpoint addresses, peer IDs, timings and connectivity.
Raw connection and daemon logs stay private to the task/operators; review exports
must exclude endpoint/auth headers and all wallet secrets. Bind public evidence
with digests and redacted, scoped identities. Do not promise P2P anonymity or
cryptographic authentication of an operator based on its profile string.

## Native acceptance sequence after the protocol ruling

This tests the missing claim: **the complete dedicated-profile native binaries
form and recover their own network while refusing foreign lineages**. Repeating
the accepted upstream regtest payment trial does not test that claim.

1. Freeze the final profile, genesis hash, activation, policy, source/overlay,
   binary hashes and resource/cleanup deadlines. Check both peers against it and
   use distinct fresh roots with no upstream database. Authenticate RPC and test
   unauthorized requests plus restricted-method denial before funding.
2. Start two actual native peers through only the assigned loopback transport.
   Read native genesis/header/network ID and selected wallet address encodings.
   Require positive handshake and matching tips; test wrong UUID and same UUID
   with wrong genesis, upstream/mainnet/regtest identities, foreign address
   families and refused bootstrap endpoints. Retain rejection diagnostics and
   prove healthy later relay. Source/static checks do not satisfy this step.
3. Obtain disposable funding only through the agreed zero-premine native mining
   path and final policy. No real coins, premine, external faucet or fixed-difficulty
   substitution. Before any expensive mining trial, freeze a realistic finite
   block/time bound with the workload owner. No assertion that90s policy funding
   fits an accelerated regtest's900s window.
4. Freeze both peer tips; stop the counterpart. Gracefully stop/restart the
   retained peer and record a new process generation with the same LMDB files.
   Use get_info to bind saved height/top hash/wide cumulative difficulty before
   reconnecting. A fresh resync after losing the directory is a failure of the
   persistence claim. Keep failed LMDB/logs private for diagnosis.
5. While one peer is down, advance the other within the frozen trial bound. Resume
   the peer, prove native missing-block catch-up and another valid relay/payment.
   Repeat using the explicitly selected recovery seed with primary unavailable.
   Fail closed if both are unavailable. No automatic switch to a foreign seed.
6. Complete cross-node payment, receive, restore/rescan and later spend on that
   same final profile, as specified in [the launch sheet](launch-sheet.md).
   Record raw state, timing, memory/CPU/disk, listener/process IDs, exits and OOM
   counters through shutdown. Archive every failure with its original verdict.

## Backup, withdrawal, rollback and incident handling

For the final implementation, stop only owned processes gracefully before a cold
backup. Save the profile/binary/overlay manifests with the stopped LMDB directory,
config and peer-state files. Never copy an LMDB file while its writer is running.
Wallet backups belong to their private wallet owner, outside seed/evidence copies.
Restore into a new root, verify source/profile/genesis bindings, attest saved
get_info with the counterpart stopped, then reconnect and catch up. Native cold
restore and corrupt/incomplete-backup refusal are unmeasured for this profile.

Withdrawal means stop the owned seed, remove its endpoint from the explicit
topology through a versioned reviewed update and select the recorded recovery
role. Never erase the saved chain as an incident workaround. If a fork, inflation,
auth exposure, unexpected listener or resource breach appears, stop the affected
owned runtime, retain private diagnostics and notify the lead/Core/Security on
this same issue. Do not export secrets or change public networking.

Rollback restores the previous accepted executable **with its matching profile
and saved data root**. A changed identity, genesis or consensus requires another
network namespace and fresh directory. Never open this proposal's database with
upstream or historical Candidate M binaries. There is currently no prior accepted
shared-profile runtime to roll back to; the safe current state is no node running.

Capture reports before cleanup. Remove only exact owned process/container names
and disposable successful scratch after verifying exit, noOOM and no listeners.
Preserve failed-attempt evidence/private state until reviewed. Do not prune Docker,
stop shared services, reuse another task's lock/claim or delete source caches.
If an eventual run uses extra owned Mac scratch, fetch reports then apply
`ios cleanup complete` to that exact owned task folder under the shared Mac rules.
No Mac scratch or simulator was used in this checkpoint.
