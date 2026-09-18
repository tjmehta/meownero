# Selected-family reproduction — September 18, 2026

TJS-40 (M1). Two clean, cache-disabled builds of **each** selected profile, built
under the existing heavy-build guard, independently compared. Agent-authored and
agent-reviewed; not an external audit. This reproduces binaries; it does not lift
any launch gate.

**PASS — same-host, same-immutable-image reproduction of both selected profiles.**
For each of `selected-9-90` and `fallback-12-120`, two independent source-only
builds produced byte-identical daemon, wallet-cli, wallet-rpc and both test
executables, with identical provenance receipts. Both pairs also match the
September 13 recovered binaries used by [TJS-39](../research/loaded-network-2026-09-15.md),
byte-for-byte, on the same host and image but a different day. This is **not**
independent-toolchain reconstruction.

## Revision binding

| Item | Value |
|---|---|
| Repo branch / HEAD | `m1/september-7-verification` / `da0f97ce035a1af7011d2a28a5dddb30e147fa41` (tree `0f327192…`; harness/report files untracked at this revision) |
| Reconstructed historical source | HEAD `7410c04bab0e304112710d63c3225c110bd8b4de`, tree `4db958cb96d72943c5c2433bd5f4a8f730037148` (clean, submodules match the clean15 receipt) |
| Builder image (immutable) | `sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e` |
| Compiler / CMake | GCC 13.3.0 (`13.3.0-6ubuntu2~24.04.1`), CMake 3.28.3 (verified identical across all four builds) |
| Recipe | committed `spikes/network-benchmark/build-profile.sh` + `stage-profile-build.py` under `chain/network-build-guard.sh` |
| Overlays | `spikes/selected-issuance/{selected-9-90,fallback-12-120}.patch` + approved `selected-unit-fixtures.patch` (`360acc9e…`) + `selected-gamma-fixture.patch` |
| Frozen input manifest | `research/evidence/repro-selected-2026-09-18/INPUT_SHA256SUMS` = `253747af6f15aef0379c8e04ec4815b71fcc404d742c731cc0e8cf8c526d443f` |
| Guards (unchanged) | shared heavy lock `/tmp/meownero-swarm-20260912-heavy.lock`; ≥5 GiB MemAvailable + ≥5 GiB disk preflight (exit 75 on refusal); container `--network none --memory=4g --memory-swap=4g --cpus=2`, one compiler job, `CCACHE_DISABLE=1`, no cache volume |

Every frozen harness input equals its committed version at HEAD (0 anomalies,
`freeze/inputs-vs-HEAD.txt`). The reconstructed historical source was verified
clean at the pinned revision before each build; it was never built in place.

## What ran

Four builds, sequential, one at a time under the heavy lock (driver detached so
it survived worker/bridge restarts):

| Cell | Started (UTC) | Ended (UTC) | build.exit |
|---|---|---|---|
| selected-9-90 / first | 04:52:21 | 05:24:36 | 0 |
| selected-9-90 / second | 05:24:36 | 05:56:21 | 0 |
| fallback-12-120 / first | 05:56:21 | 06:27:30 | 0 |
| fallback-12-120 / second | 06:58:21 (ended) | 06:58:21 | 0 |

Each cell: fresh `cp -a` copy of the clean historical source into an empty tree;
apply the profile monetary overlay + approved test fixtures + gamma fixture to
that disposable copy only; verify the changed tracked set is exactly the four
overlay files; delete any inherited executables; compile daemon, both wallets,
`unit_tests` and `meow_difficulty_floor_tests` with one job and ccache disabled;
run the native selection. Offline phase `--network none`; the DNS-only phase uses
ordinary bridge networking with public fixtures, matching `.github/workflows/chain.yml`.

## Independent comparison

`build/repro-selected-20260918/compare.py` re-hashes the actual executables from
each build tree (it never trusts the runner's success line), re-parses every
GTest XML, checks the staged source HEAD/tree and that the live tracked diff
equals the frozen overlay diff, checks the cgroup caps and memory events, and
compares receipts across the pair and against the September 13 receipts. All
checks passed (`summary.json`, `status: PASS_SAME_HOST_SAME_IMAGE_PAIRS`).

### selected-9-90 — identical across first and second build, and to Sept 13

| Executable | SHA-256 |
|---|---|
| `monerod` | `b79cb49dbea95c0eeff7dca8c945d65f4fab3d49fb626fcbe7a9343569d4a2c1` |
| `monero-wallet-cli` | `76ad8cb92d25decd91e0fc88152356dad2405703cac2190fb0508edb59301120` |
| `monero-wallet-rpc` | `5782abee489e8b245b42fd237ece34d6df1c67929c552960755fab41de3a921a` |
| `unit_tests` | `d9fd19c8c9028818487ad31c08890e81636600eef9776133de6e2f0341af63de` |
| `meow_difficulty_floor_tests` | `1426a07764615693d9391dafdc3f72adfd28c9f1660bf90349912a25972393e6` |

Target 90 s, reward 9,000,000,000,000 atomic. Changed files: `cryptonote_config.h`,
`cryptonote_basic_impl.cpp` (issuance) and `block_reward.cpp`, `output_selection.cpp`
(test fixtures) only.

### fallback-12-120 — identical across first and second build, and to Sept 13

| Executable | SHA-256 |
|---|---|
| `monerod` | `177855bf7fb13adff357e87273e0c8f1caeb14c2ebf31d29d37b107380fb6948` |
| `monero-wallet-cli` | `76888400acb4381b621174043cf8305c6ab92ec8161f32efa5eeb12ad5dd322a` |
| `monero-wallet-rpc` | `242633af93cfb3aaf8e641da0fef2baae3d5e4b7c5f28a50a8641e80913cb8bd` |
| `unit_tests` | `68eae116d2a665002e2719258ceafc4afb76d6700dfe3e805ea44283b1ddae03` |
| `meow_difficulty_floor_tests` | `d420684dbb20de881e710ebc94b1f729520a0876340fe12b1bcd77874a094ac1` |

Target 120 s, reward 12,000,000,000,000 atomic. Same changed-file set, with the
config hash differing only in the target/reward constants (expected).

### Tests, resources (every build)

- Native selection: consensus 24, difficulty 10, floor 10, offline 1,228, DNS 9,
  merged **1,237/1,237**, 0 failures/0 errors, retaining exactly the three
  documented exclusions (`ban.subnet`, `http_server.response_soft_limit`, `notify.works`).
- cgroup caps confirmed 4 GiB / swap 0 / 2 CPUs; peak 3.3–3.7 GB; **no**
  memory-limit or OOM events. No ccache activity in any make log.

Receipts identical across each pair: `BUILDER_IMAGE_ID`, `SHA256SUMS`, `VERSIONS`,
`packages.txt`, `source.diff`, all three patch files and both source-lock files.
Live builder package manifest equals the frozen clean15 image manifest.

## Evidence

`research/evidence/repro-selected-2026-09-18/` (182-file `MANIFEST.sha256`):
`summary.json` (full check list), the four per-cell receipt sets (exits, XML,
`SHA256SUMS`, `VERSIONS`, `packages.txt`, `source.diff`, cgroup files, `make.log`
hash), the frozen provenance (`freeze/`), `INPUT_SHA256SUMS`, the driver and the
comparison script. Raw build trees remain local and untracked under
`build/repro-selected-20260918/` (gitignored); the committed artifacts are the
provenance, receipts and hashes.

## Limits and exclusions

- **Same host, same immutable builder image.** This is not an independently
  reconstructed toolchain: apt package versions are unpinned in `chain/Dockerfile`
  (an open M1 item). Cross-host / cross-hardware reproduction is not established.
- **Source-only staging** from the reconstructed clean15 historical source plus
  the existing selected/fallback overlays. No monetary policy, consensus source
  or production patch series was changed. The historical clean15 claim was not
  rebuilt.
- Retains TJS-39's bounded limits: **no FCMP** integration in the pinned source,
  **capacity not normalized** (both keep the 300,000 penalty-free zone), and the
  native DAA / PoW is exercised only by the unit selection here. This task makes
  **no** loaded-network, capacity, FCMP, wallet/fee/aggregate, runtime-parity or
  launch-readiness claim, and does not lock or advance 90 s.
- No mainnet or public node, no spending, no real keys, no remote push, no new
  agents, no host-service change. TJS-78's harness, outputs and session were not
  touched. Agent-authored and agent-reviewed; not an external audit.

## Next bounded action

TJS-41 handoff: revision-bound independent review of this reproduction (re-run
`compare.py` against the evidence, or rebuild a third time and diff) before any
promotion. Independent-toolchain reconstruction (pinned apt snapshot) and the
matched-capacity intended-crypto workload remain the open follow-ons.
