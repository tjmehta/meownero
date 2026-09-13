# Rust/Cuprate build-tooling recovery — September 13, 2026

**Coordinator completion:** after the selected 9/90 build released the shared
lock, the frozen final wrapper completed successfully with both Cargo and
container exit **0**. The cached context-crate check finished in **0.64 s**;
manifest/lock hashes remained unchanged. [Final wrapper receipts](evidence/recovery-2026-09-13/rust/final-wrapper-pass/)
close the queued wrapper verification described below. The earlier failures
remain preserved. This establishes actual crate compilation, not runtime or
consensus parity.

**The actual locked `cuprate-consensus-context` crate check passed in 72 seconds
using genuine pinned Git sources and installed Rust 1.96.1.** Frozen resolution
also passes with 658 packages. The compiler/container receipt is exit 0; a
launcher bookkeeping error is preserved separately. The final unchanged runner
passed syntax/input checks, initially yielded to the occupied shared lock
(exit 75), then passed the cached end-to-end verification after the lock was
released.

The historical [1,870-case primitive result](swarm-rust-2026-09-12.md) remains
the last passing parity evidence. It was not rerun or upgraded to crate parity.
Selected 9/90 and gated 12/120 policy, production patches, historical evidence,
consensus and cryptographic code are unchanged.

## Recovered inputs and initial cache inventory

Read the [restarted handoff](handoff-2026-09-12-restarted.md) and historical Rust
report. The surviving `swarm/20260912-rust` branch has the same tracked spike
inputs as this checkout. It contains no committed `resume/prepare.py`.
The vanished uncommitted implementation cannot establish the cause of its
reported `IndexError`; no recovery of the refused output was attempted.

- All **16 retained upstream files** match `spikes/cuprate/source-lock.json`.
  The retained subset lacks 25 of the workspace's 30 member manifests and was
  never a standalone Cargo workspace.
- Cuprate commit `318c2dea4eb404ac4ecf2bea87c1a4696b0198cc` downloaded once from
  its pinned codeload URL: **3,507,499 bytes**, SHA-256
  `2ab36cd384c1e2f245b185a5b154dde255617c6b22f03ec40ce2d1e7a2ba831a`.
  This matches the preserved September 12 archive receipt exactly.
- The exact `monero-oxide` commit
  `946ec5f00ff071b129758ee8cba5528539fccfe4` and `randomx-rs` commit
  `76c2385771ca5aca941e0991ebd822e6edb8d94d` each returned HTTP 200 in one
  bounded codeload request. Their archive sizes and hashes are in the receipts.
  These tarballs were not substituted for Cargo Git dependencies; the later
  Cargo fetch obtained genuine Git objects and checkouts independently. Their
  hashes are new download observations, not pre-existing independent
  authentication pins.
- The inspected `~/.cargo` cache has **272 of 614 registry package
  archives with checksums matching the lock**; 342 lack a matching archive.
  Source-directory presence is recorded separately and does not prove usable
  offline registry resolution.
- None of the four locked Git revisions exists in either local Cargo Git
  database (`mesh-llm` and `rust-s3`). Besides the two dependencies above, the
  lock requires `Cuprate/Tapes` at
  `f28b6fb2db24996e3b58b64bfcd33c1e350d9979` and `Cuprate/tokio-socks` at
  `8737caf429a86ab181954444fac4f9b917795b19`. Both were subsequently fetched at
  their exact Git revisions. Inventory is scoped to the retained spike, surviving worker branch,
  ordinary local Cargo cache and searched scratch paths, not every disk/cache.

Evidence: [inventory](evidence/recovery-2026-09-13/rust/inventory.json),
[one-attempt download receipts](evidence/recovery-2026-09-13/rust/fetch-receipts.json),
[preparation receipt](evidence/recovery-2026-09-13/rust/preparation.json).
Downloaded archives and the extracted full workspace are under
`spikes/cuprate/.scratch/recovery-2026-09-13/` (ignored, disposable).

## Genuine dependency recovery

One `cargo fetch --locked` in a fresh task cache completed with exit **0** in
nine seconds (07:41:10–07:41:19 UTC), with a 90-second timeout, no automatic
Cargo retries, and Git CLI fetching without interactive credentials or host Git
configuration. It fetched all four exact Git revisions plus RandomX submodule
`102f8acf90a7649ada410de5499a7ec62e49e1da`. All **614 registry archives** now
match their upstream lockfile checksums. No tarball-to-Git reconstruction,
manifest edits, lock edits, patches or dependency stubs were used.

[Fetch log](evidence/recovery-2026-09-13/rust/locked-fetch/stderr.log),
[populated cache receipt](evidence/recovery-2026-09-13/rust/populated-cache.json).
The isolated cache is `spikes/cuprate/.scratch/recovery-2026-09-13/fetch-cache`.
The new [fetch-locked.sh](../spikes/cuprate/recovery/fetch-locked.sh) captures the
successful command as a reusable bounded runner. The successful run used its
underlying Docker invocation; wrapper syntax and refusal paths were checked
without a redundant second download.

Frozen metadata using that cache and the unchanged complete workspace then
passed, resolving **658 packages and 30 workspace members**. The original
host cache remains unchanged. [Resolved summary](evidence/recovery-2026-09-13/rust/resolved-summary.json)
and [full metadata](evidence/recovery-2026-09-13/rust/frozen-after-fetch/metadata.json).

## Tooling and tested outcome

Added [prepare-source.py](../spikes/cuprate/recovery/prepare-source.py): explicit
archive, destination, spike and historical-receipt paths work even with shallow
container mounts `/spike`, `/scratch` and `/receipt.json`. Before extraction it
checks receipt/lock commit agreement, the historical archive hash and all 16
retained source hashes. It refuses an existing destination and uses Python's
filtered tar extraction. This is a new source-restoration utility, not a claimed
repair of the lost implementation.

Added [check-locked.sh](../spikes/cuprate/recovery/check-locked.sh): runs actual
`cargo metadata --frozen --format-version 1` on the complete unmodified
workspace, with read-only sources and existing caches, a fresh writable Cargo
home, no network, a 45-second timeout and recorded exit/memory/input hashes.
It performs dependency resolution only. Neither dependency overrides nor stubs
are introduced. No Cargo manifest or lock is rewritten.

| Check | Result |
|---|---|
| Complete source preparation in shallow container mounts | Passed; archive and all 16 source pins matched |
| Existing destination / altered archive / wrong receipt commit / altered file pin | All four refused with exit 2 before extraction |
| Python parsing and Bash syntax | Passed |
| Initial frozen workspace metadata | Exit 101; missing local `monero-oxide` Git checkout; peak 37,470,208 bytes |
| Initial `cargo check --frozen --package cuprate-consensus-context --jobs 1` | Exit 101 at the same dependency-resolution blocker, before compilation; peak 84,639,744 bytes |
| Frozen metadata after genuine fetch | Passed, exit 0; peak 161,755,136 bytes |
| Actual crate check with genuine Cuprate checkout | Passed, Cargo exit 0, 72 seconds; peak 533,258,240 bytes |
| Final frozen runner cached verification | Exit 75 at occupied shared lock; no container launched |
| Cargo manifest/lock hashes before and after fetch/resolution | Identical |
| Offline resolution/check memory limit/OOM counters | All zero |

The initial failure reports `monero-address` required by workspace member `cuprated`, even
for the package-selected check: resolution still traverses the unchanged
workspace. The diagnostic is:

```text
Unable to update https://github.com/monero-oxide/monero-oxide.git?rev=946ec5f#946ec5f0
can't checkout from 'https://github.com/monero-oxide/monero-oxide.git': you are in the offline mode (--frozen)
```

[Preparation checks](evidence/recovery-2026-09-13/rust/preparation-checks.json),
[metadata diagnostic](evidence/recovery-2026-09-13/rust/locked-resolution/cargo.stderr),
[crate-check diagnostic](evidence/recovery-2026-09-13/rust/crate-check/stderr.log).
The initial empty metadata/stdout files are failed-command output, not successful results.

All workload containers used immutable builder
`sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e`.
Dependency preparation and resolution used 512 MiB memory and equal memory+swap
limits (no swap), one CPU and 64 PIDs. The fetch recorded peak 537,214,976 bytes
and 3,814 memory-limit events with **zero OOM/OOM-kill events**: it reached the
configured 512 MiB limit; the kernel peak counter slightly exceeded that limit.
The separate guarded compile uses the heavy-work limits described below.
Preparation/resolution Cargo and rustc came from the existing host stable toolchain mounted read-only;
[versions](evidence/recovery-2026-09-13/rust/locked-resolution/cargo-version.txt)
are recorded (Cargo 1.93.0). No package or service changes were made.

## Target graph and toolchain boundary

The initial complete metadata closure from `cuprate-consensus-context` contains
202 packages including target-specific/development edges. `sysinfo 0.39.6`,
which declares Rust 1.95, is **absent** from that closure. Its immediate workspace
dependents are `cuprated` and `tor-memquota`.

A separate successful offline command, `cargo tree --frozen --package
cuprate-consensus-context --target x86_64-unknown-linux-gnu --edges normal,build
--prefix none --format "{p}"`, identifies **137 packages including the root**.
None is `sysinfo`; the greatest declared MSRV in this target graph is **1.85**.
Several packages declare no MSRV, so this is not proof of compiler/native-library
compatibility. Stable 1.93 clears every declared MSRV in the scoped graph.
[Target graph](evidence/recovery-2026-09-13/rust/target-graph/tree.txt) and
[precise summary](evidence/recovery-2026-09-13/rust/target-graph/summary.json).

Installed toolchains are stable 1.93, 1.91.0 and **1.96.1**. The existing 1.96.1
cargo/rustc executables were explicitly mounted read-only and their versions and
hashes recorded. This also clears sysinfo's declared MSRV for future broader
workspace work. No toolchain was installed or default changed.
[1.96.1 version](evidence/recovery-2026-09-13/rust/target-graph/newer-rust-version.txt),
[executable hashes](evidence/recovery-2026-09-13/rust/target-graph/toolchain-executables.sha256).

## Guarded actual crate check

The user authorized an initial at-most-300-second offline check, then one
follow-up after the demonstrated source-input fix, only when the shared lock
and memory preflight permit them; network gets the following heavy slot.
[check-crate.sh](../spikes/cuprate/recovery/check-crate.sh) acquires the shared
`/tmp/meownero-swarm-20260912-heavy.lock` without waiting and checks at least
5 GiB MemAvailable while holding it. It records exit 75 without a container
if either guard fails. A permitted run uses installed 1.96.1 explicitly, one
Cargo job, 4 GiB/no swap/two CPUs, a 300-second TERM timeout with a five-second
kill grace, a unique container name and an exit cleanup trap. Sources and
populated dependency caches are mounted read-only. Build artifacts stay in
ignored scratch.

Initial available RAM was below 5 GiB, but the later authorized attempt acquired
the free shared lock with **6,660,068 KiB available**. It ran for **143 seconds**
(07:45:26–07:47:49 UTC), exited **101**, and peaked at **647,634,944 bytes** with
zero memory-limit/OOM events. It checked the genuine `monero-oxide` dependency,
then failed in `constants/build.rs`: the archive has no `.git`, so the upstream
`git show -s --format=%H` command returned empty output and the 40-character
commit assertion failed. The earlier shorthand description of this as
`git rev-parse HEAD` was imprecise; `git show` is the actual build command.
[Preserved first compile log](evidence/recovery-2026-09-13/rust/guarded-crate-check/stderr.log).

The root input fix uses **real fetched Git objects**. One capped 45-second
shallow Git fetch of the full Cuprate commit succeeded into a new isolated bare
repository, followed by a local `git clone --no-hardlinks` into
`spikes/cuprate/.scratch/recovery-2026-09-13/source-checkout`. All **682 tracked
Git blobs** match both the checkout and extracted archive byte-for-byte, with
no extra archive files. The genuine checkout HEAD and the exact `git show`
command from `constants/` return the pinned commit.
[Fetch receipt](evidence/recovery-2026-09-13/rust/source-git/stderr.log),
[source correspondence](evidence/recovery-2026-09-13/rust/source-git/correspondence.json).
No commit or Git metadata was synthesized, no `GITHUB_SHA` override was set, and
`build.rs` was untouched.

The crate runner now refuses archive-only input before acquiring the lock, and
requires the pinned checkout HEAD with unchanged tracked files. Its optional
fourth argument reuses a prior scratch target directory while keeping each
attempt's logs separate. The follow-up acquired the shared lock with
**6,200,772 KiB available**, using the genuine checkout and retained artifacts.
**Cargo passed with exit 0 in 72 seconds** (07:50:15–07:51:27 UTC), checking the
actual `cuprate-consensus-rules` and `cuprate-consensus-context` crates. Peak
memory was **533,258,240 bytes**, with zero memory-limit/OOM events. Existing
`cuprate-types` unused-import/dead-code warnings remain unmodified. Manifests and
lock hashes are unchanged. This is a `cargo check` result with the unchanged
development profile; it is not a linked daemon build, test execution, crate
behavioral integration or new parity evidence.
[Successful Cargo receipt](evidence/recovery-2026-09-13/rust/guarded-crate-check-after-git/cargo.exit),
[compiler log](evidence/recovery-2026-09-13/rust/guarded-crate-check-after-git/stderr.log).

**Launcher qualification:** I edited the shell runner while Bash was waiting on
Docker, shifting the file offsets used for its continuation. After the successful
container run, host-side `/out` redirections failed and the outer shell exited
1 instead of completing its bookkeeping. The container had already written its
Cargo exit, completion log, timestamps, memory counters and unchanged input
hashes. The unique container was verified absent. The outer failure is retained
in the [launcher note](evidence/recovery-2026-09-13/rust/launcher-note.json); it
must not be represented as an end-to-end wrapper pass.

After freezing the script, the coordinator scheduled one quick cached verification.
The shared heavy lock was occupied, so the final runner returned **75 without
waiting or launching a container**. No resource guard was bypassed. Its hash
was identical before/after that attempt, and final Bash syntax plus archive-input
refusal passed. [Guard receipt](evidence/recovery-2026-09-13/rust/final-wrapper-check/guard.log),
[final tooling checks](evidence/recovery-2026-09-13/rust/final-tooling-checks.json).

The following queued command was subsequently run successfully by the
coordinator after network released its priority slot (use a new output path
for another run):

```sh
bash spikes/cuprate/recovery/check-crate.sh \
  spikes/cuprate/.scratch/recovery-2026-09-13/source-checkout \
  spikes/cuprate/.scratch/recovery-2026-09-13/fetch-cache \
  spikes/cuprate/.scratch/recovery-2026-09-13/final-wrapper-check-after-network \
  spikes/cuprate/.scratch/recovery-2026-09-13/guarded-crate-check/target
```

## Reproduce preparation and dependency recovery

From the repository root, use a **new** scratch/output directory. Python 3.12+
is required; the immutable builder supplies 3.12.3. The example uses host Python
for preparation; the recorded test used the same script in the builder.

```sh
mkdir -p spikes/cuprate/.scratch/recovery-recheck
curl --fail --location --retry 0 --connect-timeout 10 --max-time 30 \
  https://codeload.github.com/Cuprate/cuprate/tar.gz/318c2dea4eb404ac4ecf2bea87c1a4696b0198cc \
  --output spikes/cuprate/.scratch/recovery-recheck/cuprate.tar.gz
python3 spikes/cuprate/recovery/prepare-source.py \
  --archive spikes/cuprate/.scratch/recovery-recheck/cuprate.tar.gz \
  --destination spikes/cuprate/.scratch/recovery-recheck/prepared \
  --spike spikes/cuprate \
  --receipt research/evidence/swarm-2026-09-12/rust/source-receipt.json
bash spikes/cuprate/recovery/check-locked.sh \
  spikes/cuprate/.scratch/recovery-recheck/prepared/cuprate-318c2dea4eb404ac4ecf2bea87c1a4696b0198cc \
  spikes/cuprate/.scratch/recovery-recheck/resolution
```

The last command reproduces exit 101 with the original host cache. To recover
the genuine dependencies and obtain passing frozen resolution instead:

```sh
bash spikes/cuprate/recovery/fetch-locked.sh \
  spikes/cuprate/.scratch/recovery-recheck/prepared/cuprate-318c2dea4eb404ac4ecf2bea87c1a4696b0198cc \
  spikes/cuprate/.scratch/recovery-recheck/cache \
  spikes/cuprate/.scratch/recovery-recheck/fetch
CARGO_HOME="$PWD/spikes/cuprate/.scratch/recovery-recheck/cache" \
  bash spikes/cuprate/recovery/check-locked.sh \
  spikes/cuprate/.scratch/recovery-recheck/prepared/cuprate-318c2dea4eb404ac4ecf2bea87c1a4696b0198cc \
  spikes/cuprate/.scratch/recovery-recheck/frozen
```

A full compile additionally needs the genuine checkout. With the prepared
archive still in `recovery-recheck`, the following obtains actual Git objects
and checks the whole source correspondence within the lightweight cap:

```sh
docker run --rm --memory 512m --memory-swap 512m --cpus 1 --pids-limit 64 \
  --read-only --tmpfs /tmp:rw,size=32m -u "$(id -u):$(id -g)" \
  -v "$PWD/spikes/cuprate/.scratch/recovery-recheck:/work" \
  -e GIT_TERMINAL_PROMPT=0 -e GIT_CONFIG_NOSYSTEM=1 -e GIT_CONFIG_GLOBAL=/dev/null \
  sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e bash -ec '
    git init --bare --initial-branch=pinned /work/cuprate-git
    timeout --signal=TERM --kill-after=5 45 git --git-dir=/work/cuprate-git fetch --depth=1 \
      https://github.com/Cuprate/cuprate.git \
      318c2dea4eb404ac4ecf2bea87c1a4696b0198cc:refs/heads/pinned
    git clone --no-hardlinks /work/cuprate-git /work/source-checkout
    test "$(git -C /work/source-checkout rev-parse HEAD)" = 318c2dea4eb404ac4ecf2bea87c1a4696b0198cc
    diff -qr --exclude=.git \
      /work/prepared/cuprate-318c2dea4eb404ac4ecf2bea87c1a4696b0198cc /work/source-checkout
  '
```

When a heavy slot is authorized and available, the exact guarded command is:

```sh
bash spikes/cuprate/recovery/check-crate.sh \
  spikes/cuprate/.scratch/recovery-recheck/source-checkout \
  spikes/cuprate/.scratch/recovery-recheck/cache \
  spikes/cuprate/.scratch/recovery-recheck/crate-check
```

The resolution wrapper expects `registry/` and `git/` cache directories, both
created by the successful fetch. It does not compile if resolution succeeds.
Full daemon integration, runtime/cache behavior, Meownero compatibility and new
parity remain outside this build-tooling result.

Only assigned Rust paths were changed; nothing was staged or committed. Final
file hashes are in [SHA256SUMS](evidence/recovery-2026-09-13/rust/SHA256SUMS).
Worker writes stopped for coordinator review. The coordinator subsequently
completed the cached wrapper check as recorded at the top of this report.
