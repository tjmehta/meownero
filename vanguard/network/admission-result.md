# Genuine TESTNET admission checkpoint, 2026-10-19

One native workload under the [new platform grant](<private-tracker>/TJS/issues/TJS-2504#comment-15414082-2a53-4872-8d19-b87f302f0bae)
passed in 355.918 seconds including container cleanup. Executed writer commit
`da39035` extends helper checkpoint `22aff0c`. The result is
`PASS_NATIVE_TESTNET_GENESIS_AND_CONTROLS_ONLY`. Launch remains disabled and
independent acceptance remains open. No peer transport, daemon listener, RPC,
wallet, service or external endpoint ran.

The [raw receipt](evidence/native-admission-attempt01/receipt.json) binds full
commit, executed driver/witness, profile, overlay, builder, toolchain and reused
inputs. That directory retains executed source copies, configure/build logs,
per-case stdout/stderr/exits, cgroup samples, original failures and cleanup.

| Requirement | Observed native result | Limit |
| --- | --- | --- |
| Real selector | `core::init` with TESTNET, null test options, offline, DNS disabled and fast sync disabled | No FAKECHAIN options or fixed-difficulty substitution; no P2P proof |
| Genesis | Height 1 / block index 0; exact stored blob matches the helper; hash `885cb43cf51086063f15c94d2fb7f327e34c447de53c9c6291b1a86d6510dab6`; generated coins 0 | No height-one funding |
| Persisted output | One amount-zero output; expected derived key, commitment G, origin tx/index and unified ID 0; height 0/unlock 60 | Public fixture scalars 1/2/3; no positive value |
| Tree | Stored leaves 0, scheduled leaves at genesis 0, depth 0 and zero root | Immature output; no mature/trusted root |
| Fork | Current/ideal next-block version 18 after genesis | No height-one v18 block/crypto transaction admitted |
| Persistence | Graceful close/reopen agrees byte-for-byte on inspected metadata; second fresh independent DB agrees | Same-process DB agreement, not two-peer relay/catch-up/recovery |
| Adverse genesis | Nine fresh DBs refuse positive reward, wrong height/unlock, empty outputs, wrong version, identity/small-order/malformed/historical torsion output | Public `reset_and_set_genesis_block` after normal init. Same-boundary positive reset and alternate-config startup controls remain missing; no specific rejection reason asserted |
| Containment | Exact caps verified; peak 1,605,173,248 bytes; OOM 0; exit 0 | One native workload; grant consumed |

Source-lock SHA256 remains
`f70160e8b7de56bfaed50ed6d29155ea0fcb41789f0c2cfcd15019085c82d001`,
upstream `e151643c5269c83bf24a83b2548e2493876026b2`, profile
`56a25f173448b3caa34ae9bb29761f5d467376df4470902fd89824ddc11fe4e8`.
Every regular/symlink member across six pinned archives was checked; unexpected
source paths refused; 3,131 copied Cargo inputs, Rust Git HEADs, Cargo.lock and
prior helper binary verified. Hashes of 227 reused objects are retained. This
was an incremental task-owned build, not a clean rebuild. Only the already
prepared three-file TESTNET overlay changed consensus/identity source; its
original/changed hashes and patch are unchanged. MAINNET/STAGENET config and
crypto verifiers were preserved. Shared source/pins pass readback.

Fresh admission under device 66306/inode 657237 saw 7,551,131,648 bytes available
memory immediately before creation, 1,139,281,948,672 bytes free disk, load
8.10/11.15/12.26 on 12 logical CPUs, and no native collisions. Actual Docker
inspection confirms network none, no ports, 2 CPUs, 4 GiB memory and equal
memory+swap limit, 256 PIDs, all capabilities dropped, no-new-privileges and core
limit 0. Execution/cleanup budgets were 880/20 seconds. Container lifetime was
15:28:12–15:34:06 UTC. Exact removal, all-container ID absence and original lock
release/reacquisition were independently checked.

The stopped databases and exact witness binary were archived and all 30 members
verified before deleting 13 owned directories: source/build export, copied Cargo
home and 11 DB roots. The [runtime manifest](evidence/native-admission-attempt01/runtime-archive.json)
binds archive SHA256 `ac1777eebc5521b6645bf8da43b281fbb911faacd1013b693c1a5f338c278f8b`.
Prior source archives/receipts remain; shared inputs and unrelated services were
untouched. This private engineering archive is not a release package or audit.

The first preflight failed because the profile reader's 64 KiB cap was applied
to the larger internal receipt. It created no container and changed no source.
The correction verifies the committed receipt hash before loading it. Original
failure, writable-parent refusal and lock-contention refusal are retained.
There was no second native build/run. All 17 existing tooling checks and six
new adverse provenance checks pass. Readiness still exits 3.

Next: current-lineage selected 9/90 policy, native difficulty/capacity and
height-one funding/maturity/FCMP++/CARROT proof; then actual same/foreign-peer
separation, persistence/catch-up/recovery and private authenticated/restricted
RPC. Rebuild daemon, wallet RPC and CLI from one final profile/overlay and prove
address agreement plus cross-node receive/payment/restore/subsequent spend.
Historical regtest or Candidate M trials cannot substitute for these checks.

The existing P2P/Mining writer owns preparing that integration and coordinating
another finite native window with platform. This grant is consumed and staging
removed; no automatic rerun/reservation exists. Keep Core/Security stages pending
until a complete candidate exists, then obtain independent acceptance and
accepted-only lead integration. Signed manifests, checksum custodian, anonymous
native downloads and public activation retain their separate owners/gates.
No merge, push or public launch. Needs TJ: None.
