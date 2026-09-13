# Clean15 completion and selected-build continuation — September 12, 2026

**Superseded running-build status:** [September 13 recovery index](recovery-index-2026-09-13.md).
Later worker commit `c1f8d05` records successful 9/90 compilation followed by
seven native-test failures. P2P and fallback did not run. The old temporary
build paths are now absent; do not restart using the PIDs recorded below.

TJ requested continued engineering and useful questions for the WhatsApp group.
The coordinator reused the existing network Herdr agent for clean-build evidence
and isolated full selected builds, while preparing native emission fixtures and
the group-question draft in the main checkout. No messages were sent to the group.

## Completed locally

- The historical fifteen-patch reproduction finished with exit 0. Both fresh,
  cache-disabled builds match daemon, CLI wallet and wallet RPC hashes, source
  and submodule revisions, patch inputs, image/packages and versions.
  [Complete verification](verification-2026-09-12-clean15.md). This closes the
  same-host/same-image clean15 claim; independent toolchain reconstruction and
  selected-profile reproducibility remain open.
- `185ab78` adds the isolated native emission fixture overlay. Seven tests pass
  for each selected 9/90 and fallback 12/120 profile; the historical configuration
  fails pair, annual-supply and saturation-horizon checks as intended. Ten-year
  mathematical issuance uses u128; the internal tally is checked separately for
  saturation. Original fixtures and production patches remain unchanged.
  [Receipts](evidence/selected-fixtures-2026-09-12/summary.json).
- `6a6533d` refreshes the [remaining questions](open-questions.md) and provides a
  [short WhatsApp draft](whatsapp-questions-2026-09-12.md): independent operators,
  second maintainer/release signer, and external-review budget/owner. These
  answers do not block current local engineering. Selected issuance stays settled.

The fixture smoke build exceeded the 512 MiB lightweight cap when compiling
native headers. The retry passed under the existing shared heavy guard with a
4 GiB/no-swap container, one CPU and 5 GiB resource preflight. Both attempts are
recorded; no compiler optimization or safety condition was relaxed.

## Active selected build pipeline

The network worker staged a frozen runner and started a sequential local pipeline:

`/tmp/meownero-selected-network-20260912/driver.sh`

Its directory contains `driver.pid`, `driver.log`, `phase.txt` and completion-only
`driver.exit`. The recorded launch PID is `2126463`; inspect it rather than
assuming it is still alive. The pipeline builds 9/90, runs the native CI selection
with exactly the existing three exclusions and the profile P2P harness, then
proceeds to 12/120 only if earlier steps pass. It uses disposable copies of the
verified historical source/build tree; no historical source is modified.

Each profile has `build.exit`, compiler/test logs, source/overlay receipts and,
on successful completion, binary hashes and `result.json`. Build outputs are
**incremental selected builds**, not clean selected reproduction. The runtime
P2P harness remains accelerated empty-block/fixed-difficulty testing, not loaded
capacity or intended-FCMP testing. Neither profile has a launch-readiness claim.

At this checkpoint the selected 9/90 compile is active and no full selected
build/test result is claimed. Do not start a duplicate pipeline or change its
frozen inputs. On failure inspect the recorded phase, exit and logs; do not add
new unit-test exclusions to hide selected-profile failures. On success collect
both profile receipts before updating completion claims.

The previous [Rust partial work](handoff-2026-09-12-restarted.md#rust-work-is-incomplete)
remains unverified and unintegrated. All engineering stays local; no pushes,
launch, spending, real keys, host-service changes or new outreach occurred.
