# TJS-1882 portable candidate: review and delivery handoff

The candidate builds and executes the pinned FCMP++/CARROT daemon, wallet RPC
and wallet CLI on Linux x86_64, Linux ARM64 and native Apple Silicon macOS.
The full requested platform matrix remains **OPEN**. Independent review,
parent integration/preservation checks and actual group delivery are pending.
The exact candidate commit is the commit containing this handoff; the issue's
review request must name its full hash and the three archive hashes below.

| Target | Archive in this execution workspace | SHA256 | Native witness |
| --- | --- | --- | --- |
| Linux x86_64 | `build/tjs1882-linux64-package05/meownero-vanguard-x86_64.tar.gz` | `fcb1b3a0ba41484cdf2fcf44c4f6da538c82db564e1d1c66cda975c129c48e36` | Ubuntu 24.04 and Debian 13.7 |
| Linux ARM64 | `build/tjs1882-arm64-package08/meownero-vanguard-aarch64.tar.gz` | `635c7ab6067d0d5efd826c24fe61807fba3cf677a5147a242a788f8e640d7994` | Ubuntu 24.04 on native ARM CPU in Colima |
| macOS Apple Silicon | `build/tjs1882-macos-aarch64-candidate.tar.gz` | `2f3f72d696a81cd7bc5694a2ce9b520cff87d973eab6d944fa448fe4cc95079f` | Native Mach-O on macOS 26.5.1 |

Each archive contains three programs, an OS/architecture-checking `launch.sh`
and Python starter, `TESTER.md`, pinned source/dependency metadata and license
texts. Linux requires glibc 2.38 or later. The Mac programs declare minimum
macOS 11.0, but only 26.5.1 was exercised. Mac binaries have verified ad hoc
linker signatures, with no Developer ID signing or notarization. Download
quarantine/Gatekeeper approval has not been exercised. No signing keys were
created. Fedora/RHEL, Arch/openSUSE and Debian ARM remain untested; no distro
installation packages are claimed.

## Evidence and affected callers

The machine matrix is `research/vanguard-portable-release-2026-10-09.json`.
The frozen internal `release.json` intentionally records `BUILT_UNTESTED`;
subsequent execution evidence binds its exact hash and archive bytes. Review
must bind both source and artifacts rather than editing those frozen archives.

Final public receipts live in
`research/evidence/vanguard-portable-tjs1882-2026-10-09/`:

- `x64-final-{check,journey,controls}.json`, `debian-final-{check,journey,controls}.json`;
- `arm64-final-{check,journey,controls}.json`;
- `mac-arm-{build,check,journey,controls}.json`;
- architecture compiler/dependency inventories, runtime environments, bounded
  memory/cleanup receipts and per-target release manifests;
- `SHA256SUMS` and `delivery-parts.json` for the final candidate only.

The successful native journeys mine 70 disposable local blocks, send 5 units,
decode the actual daemon transaction to require FCMP++ type 7 and CARROT
outputs, restore the receiver from its disposable 25-word seed in memory,
compare address/balance/output/key-image identities, spend 2 recovered units
and verify that exact receipt, then open the restored wallet through the CLI.
Ten controls cover wrong pin/target, changed binary, an extra private file,
symlink directory, hardlink, existing-output preservation, busy lock, SIGTERM
cleanup and SIGALRM cleanup. Every final native process/container was removed;
private diagnostics and disposable databases were retained only in owned,
unshared runtime directories. Share the fixed `result.json` only.

The affected flow is:
`portable-build.py` / `portable-mac-build.py` → `package-portable.py` → bundled
`portable-tester.py` (`tester.py` in the archive) → native programs.
`run-portable-check.py` and `run-portable-mac-check.py` exercise those exact
archives; `test-portable-refusals.py` checks their boundary controls.
The historical host-locked `tester.py`, profiles, chain rules, cryptographic
source and completed TJS-1816/1856/1870 reports remain intact.

Upstream is `seraphis-migration/monero` at
`e151643c5269c83bf24a83b2548e2493876026b2`, including the locked submodules and
Cargo.lock SHA256
`6a8e9217b94169e26a8f595cb528d72c19dc2f5484e903c57328c594d62f8239`.
No upstream cryptographic/consensus patches were applied. Linux receipts bind
immutable builder images, GCC/CMake versions, Rust 1.93 and package inventories.
Mac receipts bind Apple clang/Xcode SDK, exact depends commands/download
checksums, task-local Rust 1.93 and program hashes. Cached sources were read
only; fresh exports came from exact git objects.

Failed attempts remain evidence. ARM static builds exposed missing transitive
dependencies; the final package includes verified dynamic closure. Cancellation
initially retried a fatal deadline; `JourneyInterrupted` now bypasses retries
and both signals pass on all executable targets. Mac attempts exposed rejected
RLIMIT_DATA, missing sysroot and missing LLD. The final source-supported route
uses an owned RSS watchdog, explicit Xcode sysroot and the existing Apple
linker. The standard Mac `/var` alias is canonicalized only for the system
temporary lock directory; package/output symlinks still fail. Earlier archive
hashes and evidence are superseded, not approved for sending.

## Independent reviewer reproduction

Use the existing reviewer `ec85048c-4b2b-4dcc-84e1-ff9bf87c9fe6` through the
one attached stage `82aa96f6-a7bf-422f-afe7-8d1cb3b2626a`. Review the final
source commit, inspect archive manifests/file closure/licenses/provenance and
independently reproduce these journeys. Return findings to the same writer.
Do not mark the whole Windows/Mac/Linux request done from these three targets.

Run from an exact-source checkout with the archives available at the paths
above. Choose fresh owned output names; the examples deliberately refuse an
existing output. The verification harness requires Python 3.12+ for safe tar
extraction; the distributable starter uses Python 3.8+. Both wrappers acquire
the existing nonblocking heavy lock and use bounded owned workloads. Leave
`/tmp/meownero-swarm-20260912-heavy.lock` in place.

On the existing x64 Linux host:

```sh
python3 -B vanguard/run-portable-check.py \
  --archive build/tjs1882-linux64-package05/meownero-vanguard-x86_64.tar.gz \
  --sha256 fcb1b3a0ba41484cdf2fcf44c4f6da538c82db564e1d1c66cda975c129c48e36 \
  --target linux-x86_64 --out build/tjs1882-review-ubuntu01
python3 -B vanguard/run-portable-check.py \
  --archive build/tjs1882-linux64-package05/meownero-vanguard-x86_64.tar.gz \
  --sha256 fcb1b3a0ba41484cdf2fcf44c4f6da538c82db564e1d1c66cda975c129c48e36 \
  --target linux-x86_64 \
  --runtime-image sha256:9657bb863141f8d36723783c36d94348bf87a910f36372168cc061812383e3a4 \
  --out build/tjs1882-review-debian01
```

That Debian image is a retained task-owned immutable derivative of the existing
official `postgres:18.6-trixie` image, prepared with signed Debian packages for
Python. Its database service was never launched. Preparation receipt and
inventories are retained; no global Docker settings were changed.

On the existing `build-mac` Apple Silicon host, the task-owned exact source copy is
`~/Developer/tjs1882-a6abe690`. Before executing, compare the
reviewed commit's relevant scripts against that copy (or use another exact
owned checkout). Retained archives are `arm64-candidate08.tar.gz` and
`mac-arm-package03/meownero-vanguard-macos-aarch64.tar.gz`:

```sh
cd ~/Developer/tjs1882-a6abe690
/opt/homebrew/opt/python@3.14/bin/python3.14 -B vanguard/run-portable-check.py \
  --archive arm64-candidate08.tar.gz \
  --sha256 635c7ab6067d0d5efd826c24fe61807fba3cf677a5147a242a788f8e640d7994 \
  --target linux-aarch64 --out review-arm64-01
/opt/homebrew/opt/python@3.14/bin/python3.14 -B vanguard/run-portable-mac-check.py \
  --archive mac-arm-package03/meownero-vanguard-macos-aarch64.tar.gz \
  --sha256 2f3f72d696a81cd7bc5694a2ce9b520cff87d973eab6d944fa448fe4cc95079f \
  --out review-native-mac-01
```

Run sequentially. The first command is native CPU Linux in Colima; the second
executes native macOS Mach-O without Docker. Verify public check/journey/control
receipts and owned cleanup. Keep raw runtime logs/private wallet data unshared.

## Group delivery route for the parent

Whole archives are 63–71 MB, larger than the observed task attachment limit
(10 MB) and configured WhatsApp limit (50 MiB). An actual intact upload was
rejected. The verified route uses ordered document parts of at most 8 MiB,
plus checksums and reassembly instructions, under the existing approved gateway
media root. No public/private signed URL or new account is needed.

`delivery-parts.json` records all 26 part hashes, sizes and reassembly proof.
The installed gateway media loader read every part and preserved its hash;
the installed WhatsApp outbound contract sends unknown MIME as a document.
These checks did not send anything. Final directories inside the gateway are:

- `/home/node/.openclaw/media/tjs1882-a6abe690-linux-x86_64-v3` (9 parts);
- `/home/node/.openclaw/media/tjs1882-a6abe690-linux-aarch64-v3` (9 parts);
- `/home/node/.openclaw/media/tjs1882-a6abe690-macos-aarch64-v3` (8 parts).

Each directory contains `PART-SHA256SUMS`, whole `SHA256SUMS` and `README.txt`.
Parent owns actual delivery to `<group-jid>` after independent
acceptance. Use the existing gateway CLI, for each exact ordered part and
checksum/instruction file; the host CLI has no active WhatsApp channel:

```sh
docker exec openclaw-gateway node /app/openclaw.mjs message send \
  --channel whatsapp --target <group-jid> \
  --media /home/node/.openclaw/media/tjs1882-a6abe690-linux-x86_64-v3/meownero-vanguard-x86_64.tar.gz.part-0001 \
  --json
```

Recipients verify every part, concatenate the ordered parts, verify the whole
archive, then extract and follow `TESTER.md`. Mac recipients can use
`shasum -a 256 -c` in place of `sha256sum -c`. Do not send earlier v1/v2 media
directories or superseded archives. Board workspace links require authenticated
board access and are not established as group-accessible downloads.

## Missing capabilities and next actions

Board/parent capability coordination owns these concrete unresolved targets:

| Target | Observed blocker | Smallest next action |
| --- | --- | --- |
| Windows x86 | No MinGW32 compiler or native Windows runner on inspected hosts | Provide an existing approved native x86 runner and pinned scoped compiler/Rust dependencies; build, package and run the native journey |
| Windows x64 | No MinGW64 compiler or native Windows runner | Provide an existing approved native x64 runner and pinned compiler/dependencies; build and native-test |
| Windows ARM64 | CMake selects `aarch64-pc-windows-gnu`, absent from exact Rust 1.93 target list; no native ARM Windows runner | Select a compatible pinned gnullvm/MSVC compiler/sysroot/FFI route and provide a native ARM Windows runner |
| Intel Mac | No native Intel Mac execution host; source depends route exists but was not cross-built | Provide an existing approved Intel Mac runner for pinned build/native journey; any earlier cross output must remain UNTESTED |

No paid runner, signup, signing certificate or public live node was created.
Additional distro claims require separate actual runtime witnesses, and older
glibc platforms need a compatible rebuild rather than weakening the ABI gate.

Lead `38e398e0` owns accepted-source integration. Before integration, verify
the candidate's exact tree and ancestry from
`0f60722fb0eeb349a524cf73416d736edf49d9cd` and independently compare the primary
checkout against `/tmp/meownero-portable-parent-preintegration-preserve.json`.
This writer never touched the primary checkout and cannot certify preservation
on the parent's behalf. Do not stash/reset/clean or overwrite its 1163
pre-existing entries. Parent independently verifies before group completion.
