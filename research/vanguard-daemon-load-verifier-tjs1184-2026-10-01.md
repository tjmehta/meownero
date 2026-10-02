# TJS-1184 receipt-verifier correction

Blocked on TJ: none.

Changed: corrected F1-F4 from the [TJS-1174 independent review](/TJS/issues/TJS-1174#document-qa-review).
The native execution workspace is the inherited
`TJS-1171-meownero-vanguard-bounded-two-daemon-performance-load-gate-after-accepted-restore-qa`
worktree. It was clean at `f31c83edef484c5ab1089a88d674b92ade958685` before these edits.
Only `vanguard/verify-daemon-load.py`, `vanguard/test-daemon-load-refusals.py`
and this report change. No branch was reset, switched or re-pointed.

| Finding | Correction | Named refusal |
| --- | --- | --- |
| F1 | Compare sorted immutable output identities across the final receiver, restore original and post-spend wallet. Require the selected spent key image in the unique original set and the expected spent flags. | `restore output identity reconciliation`; `restored spend original key image` |
| F2 | Bind the duplicate control to the restored spend key image, require distinct alternate and confirmed transaction IDs, and reconcile every control field with its event. Retain both nodes' native double-spend/invalid-input classification. | `duplicate key image input identity`; `duplicate key image distinct candidate`; `duplicate key image event/result mismatch` |
| F3 | Compare each receipt upstream, Rust toolchain and builder field directly with the versioned source lock. Require the pinned image at the selected Docker image position. | `receipt lineage: upstream_commit`; `receipt lineage: rustc`; `receipt lineage: builder_image`; `build selected builder image` |
| F4 | Pin the existing Docker option layout before the image, permitting the recorded name, uid/gid and host mount paths to vary. Pin mount destinations and trial read-only flags. Extra, replaced or duplicated privilege, capability, network or resource options fail. | `<stage> container containment` |

Verified: the original two-run bundle passes receipt reconciliation and direct
local executable byte checks. Its 31-file manifest remains
`714bc667e2aae7e465ec981a6491d1c4f2da255543175ee899e78352c0c073aa`.
The expanded regression suite refuses 44 isolated cases, including wrong
executable bytes and invalid-proof acceptance. It checks all five immutable
output fields at both wallet checkpoints, spend membership, duplicate input
and distinct candidate binding, an event-only contradiction, isolated lineage
labels, selected-image position, and eight conflicting Docker options in each
of build/run1/run2. Every receipt mutation regenerates its manifest.

The unedited public `qa-tamper.py` from the downloaded TJS-1174 evidence archive
was also run against this checkout, changing only its in-memory checkout/bundle
paths. All ten required reviewer cases fail with named assertions, and each
mutated manifest independently passes `sha256sum -c`. The downloaded archive
SHA-256 is `df731c8bdd214e49bd578300bf051a91f8433a415d19fc1b7c10cc06c2c4283b`.
Run-owned logs, command arrays, the reproduction wrapper and the final source
diff are supplied as a Paperclip evidence attachment.

The first expanded-test attempt used a block-height mutation of 1 and expected
the identity assertion. The verifier correctly refused it earlier as `restore
height`. The test now uses 999 to isolate the new identity predicate. The initial
failed test log is retained; the final suite exits zero.

Reproduce the committed checks from the task checkout:

```sh
export PAPERCLIP_RUN_SCRATCH_DIR=<agent-scratch>
python3 -B vanguard/verify-daemon-load.py \
  research/evidence/vanguard-daemon-load-tjs1171-2026-10-01 --src build/vanguard-src
python3 -B vanguard/test-daemon-load-refusals.py \
  research/evidence/vanguard-daemon-load-tjs1171-2026-10-01 \
  --src build/vanguard-src --scratch "$PAPERCLIP_RUN_SCRATCH_DIR"
python3 -B "$PAPERCLIP_RUN_SCRATCH_DIR/reproduce-review-controls.py" \
  --repo "$PWD" --src build/vanguard-src \
  --qa "$PAPERCLIP_RUN_SCRATCH_DIR/qa" --prefix handoff-qa-controls
git diff --check
```

Use a fresh control prefix on a repeated invocation. Extract the public QA
archive into `qa/` first; the bridge scratch directory may be removed after
completion. The correction attachment preserves the wrapper and required
reviewer script. Checks use only local public receipt copies and existing
executable bytes. Mutated Docker commands are data and are never executed.

| Existing executable pin | SHA-256 | Bytes |
| --- | --- | ---: |
| monerod | `5ba64f2e04e21550575b396b250bcebba01471c4246d74d88e679f06cee86509` | 29,872,608 |
| monero-wallet-rpc | `cf2ea70c353c5124e86f2bfac46da28fad2993af28636ab28ca7ea9db81678f2` | 33,545,392 |

Unconfirmed: historical tips, execution provenance and containment remain
receipt claims. Equal, wrong idle tips still pass with `UNVERIFIED_LIVE_TIPS`.
The reviewer script's additional zero-generated-block and failed-process-exit
counterexamples still pass this verifier; they are outside the assigned F1-F4
correction. The reviewer independently reconciled those invariants in the clean
receipts. This correction makes no broader verifier-completeness claim.

The native scenario, runner, shared P2P code, source lock, dependency locks and
archived receipts are unchanged. Existing reviewer binary rebuilds and live
observations retain their original scope. No fresh native run was needed for
this verifier-only correction. The named `invalid_proof` control remains an
invalid commitment encoding/RCT semantics refusal, not an isolated FCMP
membership or range-proof test. Finite 1/2 completion establishes no sustained
capacity, isolated proof cost or production 90/120-second decision.

Next owner: Rust & Cuprate Parity in [TJS-1185](/TJS/issues/TJS-1185) for independent
review of the exact committed correction. [TJS-1171](/TJS/issues/TJS-1171) remains
unaccepted, and accepted historical gates remain closed. The author does not
self-approve. Final commit and attachment identifiers are recorded in the
Paperclip result document after committing.

Observed behavior: the supplied contradictory wallet/control/lineage/containment
claims now fail while clean receipts and the explicitly unverified tip control
retain their expected outcomes. This is local agent-reviewed engineering work.
