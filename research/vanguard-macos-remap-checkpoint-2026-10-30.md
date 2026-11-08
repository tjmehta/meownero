**Changed**

Adopted the Windows x64 successor's independent acceptance, revision
`5adf41ec-f2b6-43fb-a608-451fcb15ce9e`, for archive SHA256
`bc5829dadaae0a84271a7993d9440a6210353567a6cf9b7caddb2a545695c19e`.
Historical native evidence applies to its unchanged programs and helpers.
Parent pickup and group delivery remain unconfirmed. The new checkpoint manifest
preserves all seven targets, five historical native acceptances, both macOS
redistribution restrictions and the dormant final review stage.

Prepared the macOS correction on the existing task branch. Baseline
`fa7ac6ed418314fc6437354983c246756e740f57`; implementation commits `93bfc7c`
and `5e50d755ff9076f91e1e480abcda697e38188ba6`. Run
`86f8883b-819e-42c5-b48b-85e2d56bdb0e`, platform engineer
`92a7b4f2-787b-4cbb-954e-46831397ab09`, issue TJS-1882.

The change **extends** the existing Mac recipe with home-prefix remapping in
depends compiler commands, CMake C/C++ flags, Cargo RUSTFLAGS and C/C++ build
environments. It **composes** the existing provenance recorder for saved command
receipts, leaving actual execution arguments intact. The build must scan all
three resulting programs before recording success. These are compiler-path
changes, with unchanged upstream, submodule, Rust and Cargo.lock pins.

The shared guard now **extends** its recursive ZIP inspection to compressed tar
members and metadata. The Linux/Mac packager scans members before archive output,
scans the resulting archive, and removes local user/group identity from tar
ownership metadata. Its isolated Docker context, Dockerfile and sparse Linux
workflow now include the guard module. Existing immutable CI input bindings are
preserved; future dispatch must use a reviewed, freshly bound candidate.

Compiler semantics were checked against the official
[Clang flag reference](https://clang.llvm.org/docs/ClangCommandLineReference.html)
and [Rust remapping reference](https://doc.rust-lang.org/rustc/command-line-arguments.html#--remap-path-prefix-remap-source-paths-in-output).
Actual application compilation remains unverified. No native runtime, crypto,
consensus, signing or payment assertion was relaxed.

**Verified**

- The new tar regression fails on the original guard because a compressed
  program path is accepted. The final five provenance tests pass, including
  compressed program and PAX metadata refusal and a clean archive control.
- The corrected guard refuses the actual old Apple Silicon archive with
  `PRIVATE_HOME_PREFIX_IN_DISTRIBUTABLE`. Its hash matches the restricted archive
  `fe920a54de9941ea2782df6f7aa5cfc10842f46279a0d2c47959b2b1fcdebb35`.
- Five existing Windows bundle checks, 24 Docker lifecycle/context controls and
  81 linker/privacy fixtures pass. These are local checks, with no native build,
  Docker workload or Mac application execution. A copied packaging command fails
  when only its new dependency is omitted, then loads after restoring that file.
- build-mac responds as Darwin arm64 with Apple clang 21, CMake 4.4.2 and SDK 26.5.
  The existing source cache matches upstream `e151643c5269c83bf24a83b2548e2493876026b2`
  and the pinned Cargo.lock hash. All 15 staged files match candidate `93bfc7c`.
- The actual build entrypoint exits 1 in 0.148 seconds because its required shared
  heavy-work lock is absent. Neither the logical `/tmp` path nor resolved
  `/private/tmp` contains it; the bounded alternate-name check found no matching
  existing lock. No build output directory or build phase was created.
- All seven initially dirty/untracked file hashes remain unchanged. No source
  integration, publication, group message, paid dispatch, simulator or VM claim
  occurred. Sanitized failure copies and original private-log hashes are retained.

Evidence lives in `research/evidence/vanguard-macos-remap-tjs1882-2026-10-30/`.
The original failure, unused fixture invocations and cache-toolchain diagnostic
are preserved in `attempts.json`; they are not counted as passing checks.

**Unconfirmed/next**

The Apple Silicon rebuild cannot proceed because
`/tmp/meownero-swarm-20260912-heavy.lock` is missing on build-mac. The existing
`tester.heavy_lock()` requires its established inode and explicitly forbids
installing or replacing it during a tester run. This is a host prerequisite,
not a compiler or application failure. No new Mac program, archive, native
journey or independent correction acceptance exists.

The studio lead must route restoration of the canonical lock through the
existing host provisioning owner. Platform engineer retains correction ownership
and will check lock identity, then run the remapped build, clean extraction,
full native payment/restore/later-spend journey, ten controls and cleanup before
the existing reviewer accepts exact new bytes. Intel also needs a qualified
native Intel execution route; Actions spend remains held. The old macOS archives
must not be redistributed in the meantime. The separate Windows entitlement
question does not gate these source corrections or the accepted bundle handoff.

Remote evidence was fetched first. `ios cleanup complete` with the corrected
`Developer/tjs1882-86f8883b` path refused completion because the task is still
active. The small staged source kit and private refusal log remain under that
owned folder for the existing post-run cleanup owner. There is no build output,
DerivedData or copied VM disk. No alternate deletion route was used.

The seven-target release remains OPEN. This source correction is unreviewed and
must not be merged or described as an accepted macOS successor.

Needs TJ: None. The host prerequisite is an operational action; the previously
asked Windows entitlement decision remains with the studio lead.
