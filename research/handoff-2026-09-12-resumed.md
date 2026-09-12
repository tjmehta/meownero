# Resumed engineering handoff — 2026-09-12

Later local work: [parallel engineering handoff](handoff-2026-09-12-swarm.md).
This document remains the provenance for the preserved foundation checkpoint.

Read this before the earlier September 12 publishing-pause handoff. **The pause
is superseded.** TJ reported the snapshot at `a4f358679aeb98844e0a2b3bae97ad84bbd4b320`
published privately to `tjmehta/meownero`, with the requested invitation pending.
That authorization covered the snapshot only. All subsequent work here remains
local; no project remote was changed, and no push or third-party message was performed.

Local implementation, tests, benchmarks and reviewable commits remain authorized.
No public launch/deploy, spending, real keys, host/OpenClaw changes or additional
agents. Fixed perpetual subsidy, zero premine, precision, current 120 s / 0.9,
matched 90 s / 0.675 candidate, floor 1 and human safety gates remain unchanged.

## Verified checkpoint

- **Thirteen-patch clean binary reproduction passed, exit 0.** Two fresh,
  cache-disabled builds have identical daemon/CLI/RPC hashes, package manifests,
  image IDs and version metadata. [Full provenance and hashes](verification-2026-09-12-m1.md).
  The original background harness finished successfully; it is no longer running.
- **Wallet refresh/seed failure fixed by patch 0014.** Actual fork entries replace
  the invalid version-as-array-index assumption. Invalid versions/heights remain
  rejected; no mismatch override or genesis bypass. The clean thirteen-patch
  binary supplies a reproduced negative control.
- **Seed recovery passed:** identical address, 130 coinbase-history entries,
  117.0 MEOW total, 63.9 unlocked, then identical state after reopen. Original
  cache/key files were removed before restore into a second wallet process.
- **Patch 0015 boundary tests passed 10/10 at each floor, 1 and 150M.** Actual
  main/alt sampling, varying work, full/partial recalculation and rollback/rebuild
  across the 720/735 boundaries. Production floor remains 1.
- **Full CI selection: 1,237/1,237 in 79.174 s.** Exactly the same three historical
  exclusions; not an unfiltered suite or remote CI result. Historical fixture
  bytes remain unchanged; tests used read-only source and disposable tracked data.
- **Authority checks, Shellcheck and workflow syntax pass.** CI now includes the
  seed/reorg/native-DAA runners and protects fixture data/test-failure propagation.
- **Initial M2 checkpoint:** actual depth-3 reorg/restart/rejection tests pass in
  regtest and native-DAA mainnet mode beyond height 738. All 720 paired native-DAA
  scenario runs completed, and a second run matched every per-seed result.
  [Evidence and interpretation](verification-2026-09-12-m2.md).

The M2 implementation/evidence commit is `81b3182`; the commit containing this
handoff carries the verified wallet patches and foundation evidence. The branch
remains `m1/september-7-verification`. Do not automatically push either commit.

## Exact source/build state

| Artifact | Value/location |
|---|---|
| Pinned upstream | `4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5` |
| Current patch series | `chain/patches/0001…0015` |
| Deterministic applied HEAD | `7410c04bab0e304112710d63c3225c110bd8b4de` |
| Built/tested source tree | `4db958cb96d72943c5c2433bd5f4a8f730037148` |
| Delta | 28 files, +643/−616; `docs/security/code-map.md` |
| Current built source | `/tmp/meownero-wallet-verified-source-20260912` |
| Source-only fresh application | `/tmp/meownero-fifteen-final-20260912` |
| Preserved clean reproduction trees | `/tmp/meownero-repro-20260912/{first,second}` |
| Frozen thirteen-patch harness | `/tmp/meownero-repro-inputs-20260912/chain` |
| Immutable image | `sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e` |

The current fifteen-patch build was made from a **copy** of the first clean
thirteen-patch tree with the two patches applied. It is an incremental verification
build; clean fifteen-patch binary reproduction remains open. Both original clean
trees remain intact. Independent apt/toolchain reconstruction and cross-host proof
also remain open.

Build log: current source's `build/release/make-wallet-reviewed.log` (final reviewed build).
A 3 GiB capped compile was killed; a 4 GiB retry passed without changing compiler
flags/optimization. Full suite log: `/tmp/meownero-full-ci-reviewed-20260912.log`.
The earlier scratch source under
`<agent-scratch>`
is **superseded as the verification build**. Its attempted rebuild was stopped;
its pre-existing untracked wallet fixtures remain untouched. Use the current built
source above. No engineering containers/builds are intentionally left running.

Durable results are under `research/evidence/2026-09-12/`; `/tmp` is ephemeral.

## Remaining work, in scope for the next local checkpoint

1. Full matched-issuance **network** benchmarks: actual 90 s / 0.675 candidate
   binaries, comparable loads/topologies, proof validation, capacity, relay,
   competing blocks/orphans and reorg performance. The completed native-DAA runs
   model hashrate/clock behavior; they do not measure those network properties.
2. Replay the modeled launch timestamp distortion with real miners/competing
   branches and realistic clocks. Model-only 20% forward-stamp producers yielded
   roughly three target-days of issuance inside one day. Do not assign severity
   or adopt a mitigation from the model alone; the older warmed-up simulator did
   not cover this launch scenario.
3. Adversarial variable-work/shorter-heavier fork selection, long alternative-only
   windows, P2P partition/rejoin, malformed/privacy-escape transactions/proofs and
   sustained uptime. Existing real reorg tests use constant low work; synthetic
   varying-work tests do not replace high-work acceptance evidence.
4. Extend recovery to private incoming payments, distinguish seed-recoverable
   history from lost outgoing metadata, and exercise the interactive CLI.
5. Clean fifteen-patch reproduction before any updated release claim; independent
   toolchain reconstruction, audit and human launch gates remain required.

Unrelated local files preserved and unstaged: `.codex/`, `.mcp.json`, and
`chain/test-authorities.sh.tmp.1647189.55b20b892d45`. Site work was left to TJ's
separate commit. No settled decision needs to be re-asked to continue this work.
