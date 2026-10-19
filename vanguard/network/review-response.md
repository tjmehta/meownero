# Core changes response, 2026-10-19

Changed

This extends reviewed checkpoint `0e6b2b51c218bfcc00beba2ae488e702a88bddac`
on the assigned TJS-2504 branch. It remains a non-launchable proposal.
All changes stay in `vanguard/network/`.

| Core finding | Change and disposition |
| --- | --- |
| P1 permanent v17 transition | Profile and launch sheet now propose v1@0/v18@1 and version-one cutoff 0, following Core verdict revision `05b73cee-4e45-4fe5-8755-7d22870bc0cd`. Direction corrected; Cryptography ruling and native implementation/acceptance remain open |
| P1 missing full native candidate | Still open. The launch sheet specifies native genesis roundtrip/admission/zero-commitment/tree-root/torsion checks, explicit height-zero construction/validation, selected-policy differential vectors, fork/wallet agreement, valid FCMP++/CARROT and adverse legacy proof/output/ring checks. No new consensus or cryptographic implementation is asserted |
| P2 bootstrap aliases | Fixed in the shared topology validator. Require canonical ASCII decimal port spelling. A malformed recovery endpoint also refuses preparation when primary is selected |

New canonical profile SHA256 is
`b1711b3114e234a4975bcefc6f02fa1175df1d213ed03372bb5c50bc503aef31`.
The superseded v17 digest is
`d3d9905bd3c1464f4940f49e0872dfa8e7510127ddf83b781d6c6743e0627168`.
Examples and generated receipts bind the new digest; stale profile/bootstrap
copies are refused. The identity-only patch itself is byte-for-byte unchanged.
Source-lock, Cargo.lock, crypto pins, package/build/CI files and settled 9/90
with conditional 12/120 fallback remain unchanged.

Verified

- Thirteen tooling tests passed, zero skips/failures/errors, against actual
  pinned source. Fourteen alias/selected-role cases are refused before writing,
  alongside positive distinct primary/recovery preparation. Stale v17 profile
  and digest CLI controls pass. Raw outputs are in `evidence/tooling-checks.*`.
- `evidence/bootstrap-alias-regression.json` compares the reviewed code with this
  correction using private fixtures. Both baseline roles prepare successfully
  for numeric port 48180 spelled two ways; both corrected roles refuse before
  creating output. Successful baseline fixtures were removed.
- Seventeen native files match working bytes and pinned Git objects, with
  Cargo.lock and five submodule HEADs checked. Four new bindings cover fork
  lookup, output validation, native construction and commitment code. Full-tree
  and executable provenance are not claimed; the cache retains its existing
  CMake injection and untracked harness directories.
- Scoped identity patch apply/reverse checks pass with exact bytes restored.
  Both prior accepted native receipt digests still match. Historical/regtest
  receipts retain their original scope. The earlier failed tooling diagnostic
  stays in the manifest.
- Tests and comparison fixtures clean their private temporary directories.
  No native process, build, container, service, external endpoint or Mac claim
  was created. No shared source was changed.

The test command was:

```sh
python3 -B vanguard/network/test_network.py \
  --source <repo>/build/vanguard-src/monero-fcmp \
  --scratch "$PAPERCLIP_RUN_SCRATCH_DIR" \
  --evidence "$PAPERCLIP_RUN_SCRATCH_DIR/corrected-checks"
```

Scratch environment variables were absent. This run used the supplied bridge
run directory's private `scratch/` child as that path. Receipts were copied into
the owned evidence directory before cleanup. These checks are tooling evidence,
not native-network evidence. `readiness` still exits3; there is no launch command.

Unconfirmed/next

The smallest missing prerequisite is the source-bound Cryptography ruling on
the native zero-premine genesis construction and v18 activation, requested in
[this scoped consultation](<private-tracker>/TJS/issues/TJS-2504#comment-fb58a037-4cf6-47d2-8870-9c0e7f1c272a).
Privacy Cryptography `637e65be-a666-4b41-b211-9fea5eef61da` owns that ruling;
the assigned P2P writer owns recording and applying it. Silence is not approval.

After that ruling, the writer must coordinate an idle bounded build slot with
the platform owner, implement the completed overlay in owned paths and prove
native same/foreign separation, retained-LMDB reopening with counterpart stopped,
catch-up and primary/recovery behavior. Difficulty/capacity remain unresolved.
Final-profile cross-node payment/receive/restore/later spend, package integration,
private authenticated restricted RPC and operator assignment remain required.
Final Core/Security acceptance and lead-only accepted integration remain open.
This partial correction must not be resubmitted as a completed launch candidate.

Needs TJ: None.
