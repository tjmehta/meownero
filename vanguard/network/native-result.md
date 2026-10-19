# Bounded native genesis result, 2026-10-19

The one local attempt granted in the
[platform reply](<private-tracker>/TJS/issues/TJS-2504#comment-2d70177d-b7a7-4ef6-8079-242320bdcb1f)
completed successfully in802.712 seconds, including cleanup. The native helper
ran twice and produced byte-identical output. Its result is
`PASS_NATIVE_RECIPE_HELPERS_ONLY`. No TESTNET database, daemon, wallet, listener
or endpoint ran. This checkpoint extends `b960a46fd7561e04099008cbb4b7ade51db79559`
in the existing isolated writer worktree. Only `vanguard/network/` changes.

The [native recipe](evidence/native-genesis-attempt01/recipe1.json) contains full
transaction/block bytes, public recovery inputs1/2/3, derived public keys,
amount0 commitment G and the native legacy O/I/C tuple. Native parse/serialize
roundtrips, transaction shape and header checks pass. Unchanged native helper
controls reject identity, small-order, malformed and historical torsion-bearing
points in both output and commitment positions. These controls do not establish
block admission or a persisted/scheduled trusted root.

| Binding | Exact result |
| --- | --- |
| Transaction hash | `981a90c0867b81cc5abf091c842ee0e85af5d8d967e8c6ce4b2fae75904bc975` |
| Block hash | `885cb43cf51086063f15c94d2fb7f327e34c447de53c9c6291b1a86d6510dab6` |
| Actual nonce | 424001 |
| Recipe SHA256 | `12e6e285abc394b1a775912c7d3eca74b9aa696546dc78828c58322a512486b9` |
| Native helper SHA256 | `5a9048e5147e2d8692b1682263354dce6f36ff3531784519a711a6131835029b` |
| Executed driver SHA256 | `477956aa139a2a3546ebebe8beec8e9221e66ada911fdb5cf89ca1fa12ac9e58` |
| Pre-execution profile | `920825038185340ea4461e3899c0c74e579249fa57735621b7929dec4f3ef7c5` |
| Updated proposal profile | `56a25f173448b3caa34ae9bb29761f5d467376df4470902fd89824ddc11fe4e8` |

The original source lock, upstream `e151643c5269c83bf24a83b2548e2493876026b2`,
five submodule revisions, Cargo.lock and both Rust Git revisions remain pinned.
The source was exported from committed Git objects into owned scratch; no
generated object or dirty source injection was imported. The helper-only build
changes the exported test CMake by one appended target and adds the owned helper
directory. Six source archive digests, original/changed test CMake digests,
helper sources, copied Cargo cache file digests, toolchains and complete logs
are retained in [the raw receipt](evidence/native-genesis-attempt01/receipt.json).
Shared source paths pass their post-run checks. Owned/shared Cargo.lock hashes
still match the pin. The shared source/cache/toolchain were not writable mounts.

Fresh admission under the exact host heavy-lock inode recorded11.93GB available
memory and1.18TB free disk, with no native workload collision; admission was
rechecked immediately before creation. The actual container inspection confirms
network-none, no published ports,2CPUs,4GiB RAM and equal memory+swap limit,
256PIDs, dropped capabilities, no-new-privileges and core limit0. CMake and Cargo
both used one compile job; upstream Cargo uses `--locked`, offline. Peak cgroup
memory was2,019,061,760 bytes, OOM events0, container exit0 and OOMKilled:false.
The container ran08:28:07–08:41:28UTC. It was removed by its exact returned ID.
The same host lock was successfully reacquired after cleanup.

One diagnostic defect is preserved: the executed driver checked the uppercase
string `No such`, while Docker29.5.3 returned lowercase `no such object`. Thus
its original receipt says `container_absent:false` after successful removal.
The independent [cleanup verification](evidence/native-genesis-attempt01/cleanup-verification.json)
records that response and a successful all-container ID query confirming the
exact ID absent. The executed driver is retained byte-for-byte in the evidence;
the subsequent source fix normalizes case and retains probe diagnostics. No
second native attempt was used to test this diagnostic change.

The profile now binds these native-derived genesis bytes and helper evidence,
while remaining `protocol-proposal`, `launch_ready:false` and independently
unaccepted. Superseded profile/bootstrap bindings are refused. The executable
`network.py admission-overlay` emits a reversible, source-bound three-file
TESTNET prerequisite patch: identity/genesis config, v1@0/v18@1/cutoff0 table and
explicit TESTNET height-zero validation. Its original/changed source hashes and
patch are retained in [admission-overlay](evidence/native-genesis-attempt01/admission-overlay).
That patch is uncompiled/unadmitted and deliberately lacks selected9/90 policy.
Seventeen tooling tests pass, zero skips/failures/errors, including actual-source
patch apply/reverse and adverse genesis/stale-profile/no-overwrite checks.
Readiness still refuses with exit3. Earlier evidence is preserved unchanged.

The consumed slot is complete. The existing P2P/Mining writer owns coordinating
the next finite platform window and implementing the
[genuine TESTNET admission boundary](native/admission-boundary.md). The existing
owned source/build staging is retained for bounded reuse after platform
coordination, not as an automatic continuation. Its absolute location and
resource receipts are in the raw attempt receipt. No further native process
will run under the consumed one-attempt grant. The platform owner can authorize
reuse of these owned outputs without shared cache writes or a cold rebuild.

Still required: real fresh TESTNET admission/accounting and negative genesis
controls; persisted commitment, maturity/root state and reopen agreement;
height-one v18 and wallet agreement; selected-policy/difficulty/capacity;
same/foreign two-peer separation, persistence/catch-up/recovery; private
authenticated/restricted RPC; operator capacity; package integration; genuine
cross-node receive/payment/restore/subsequent spend; independent Core/Security
acceptance and accepted-only lead integration. Public signatures/downloads and
activation retain their separate owners/gates. No cryptographic verifier,
signing material, public service or accepted historical proof was changed.
Needs TJ: None.
