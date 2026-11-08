# Consultation application checkpoint, 2026-10-19

The [Cryptography ruling](<private-tracker>/TJS/issues/TJS-2504#comment-3b6c0197-43f9-4c30-a90c-399f82fc0b57)
accepts v1@0/v18@1/cutoff0 and the explicit native zero-valued genesis
construction for bounded non-public implementation. The conceptual consultation
blocker is satisfied. Exact bytes and the final candidate remain unverified.

This extends `4d89b4a35d0a3c8d8f40648989d5b6ffacc2e7b7` in the same assigned
worktree. Only `vanguard/network/` changes. Launch remains disabled.

| Core finding | Current disposition |
| --- | --- |
| P1 permanent v17 transition | Corrected direction retained; consultation recorded. Prepared reversible TESTNET v1@0/v18@1 fork table, cutoff0 and explicit height-zero reward/shape rule. This source patch is uncompiled and has not proved admission |
| P1 missing native candidate | Still open. Native public-input genesis construction/serialization/commitment/leaf/torsion driver is written. No helper execution, native genesis bytes, selected-policy integration, daemon admission or final-profile two-peer/wallet proof is claimed |
| P2 bootstrap aliases | Prior fix retained; current positive and adverse controls pass for both selected roles |

Profile canonical SHA256 is
`920825038185340ea4461e3899c0c74e579249fa57735621b7929dec4f3ef7c5`.
The pre-consultation v18 and superseded v17 profiles remain refused. Operator
examples and new receipts bind the current digest. Earlier alias and tooling
receipts remain intact with their original digest and scope.

The helper explicitly constructs the v2/RCTNull height-zero transaction with
unlock60 and one amount0 txout_to_key. Public canonical recovery scalars1/2/3
feed the native derivation path. It checks the native amount0 commitment G and
records native transaction/block roundtrips, hashes, actual nonce and legacy
O/I/C leaf data. Unchanged helper rejection controls cover identity, small-order,
malformed and validly encoded historical torsion-bearing points in both output
and commitment positions. This is prepared source, not successful native tests.

The emitted validation patch only sets base_reward0 at explicit TESTNET
height0 and enforces the one-zero-output v2/RCTNull form and fee0. Ordinary
weight validation still runs first; exact-coinbase and torsion validation still
run afterward. There is no early-success return or generated-coins heuristic.
Height1 remains a rewarded ordinary block. This prerequisite patch omits the
still-ungenerated genesis blob and selected-policy overlay. It cannot launch.

Verified: fifteen tooling tests pass, zero skips/failures/errors; both scoped
patches apply/reverse byte-for-byte in disposable fixtures; native-input export
hashes match and existing output is preserved on refusal. Thirty-four inspected
native paths match working bytes and pinned Git objects. Cargo.lock and five
submodule HEADs pass. This is not full-tree or executable provenance; the cache
retains its disclosed test CMake injection. Source-lock, shared package/build/CI
helpers and existing accepted evidence remain unchanged.

Current raw evidence is in `evidence/consultation-applied/`. Earlier failures and
prior correction receipts are retained. Private tooling fixtures were cleaned.
No build, syntax-only compile, native workload, container, service, external
endpoint or Mac claim was created. The preliminary read-only local resource
snapshot found the pinned builder image and >5GiB memory/disk; it is not a slot
assignment or native-run admission receipt.

The immediate dependency is an idle slot and confirmed read-only build inputs
from platform owner92a7b4f2-787b-4cbb-954e-46831397ab09, requested in
[this structured mention](<private-tracker>/TJS/issues/TJS-2504#comment-80fd656e-4d6b-4547-a8d5-3ebd8b41f5d3).
The P2P writer owns obtaining that response and then running the bounded native
recipe and genuine TESTNET admission before extending dependent network and
wallet machinery. No further conceptual ruling is requested from Cryptography.

Full selected-policy/difficulty/capacity, native separation, persistence/recovery,
final-profile receive/payment/restore/later-spend, private RPC controls, operator
assignment and package integration remain open. Keep Core/Security changes-requested
stages until a real complete candidate is ready. Lead accepted-only integration
and all separate public-release gates remain required. Do not resubmit this
prepared checkpoint as a completed launch candidate. Needs TJ: None.
