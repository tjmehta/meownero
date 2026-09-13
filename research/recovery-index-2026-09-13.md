# Session recovery — September 13, 2026

TJ requested inspection of unfinished Claude/Codex/Claudex sessions and restarting
focused agents in the Meownero Herdr workspace. This index records the recovered
sessions, verified results, and remaining work.

## What survived

The main checkout started at `1f1cb13` on `m1/september-7-verification`.
September 12 handoffs, raw committed evidence, worker branches, Codex transcripts
and Claude transcripts survive. The old `/tmp/meownero-*` worktrees and build
directories are absent; Git lists their worktree registrations as prunable.
They were not pruned or recreated during recovery. No Meownero build container
was running at inspection. The original builder image
`sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e`
is still present. Historical receipt claims survive; ephemeral binaries do not.

Herdr now identifies Meownero as workspace `wS`, initially only pane `wS:p1`.
Old worker workspace IDs `wB`–`wF` are stale. Three sibling panes were created
without changing user focus, all using the main checkout and disjoint ownership.

## Recovered work status

| Workstream | Last established result | Remaining work / disposition |
|---|---|---|
| Historical clean15 | Both clean builds and provenance verified, integrated into main | Same-host/same-image claim only; do not repeat as unfinished |
| Selected build/network | Fresh 9/90 and 12/120 builds each pass all 1,237 native tests and bounded actual P2P checks | Recovery complete; selected-family reproduction, wallet/fee/aggregate integration and loaded/FCMP performance remain open |
| Rust/Cuprate | Genuine pinned dependencies restored; actual context-crate check and final wrapper pass (`19d0304`) | Runtime/consensus parity remains open; historical 1,870-case primitive evidence retains its original scope |
| Privacy | `7dedf3d` / worker `ffc7f77`: restricted wallet controller and 52/52 cases | Completed bounded checkpoint; broader transport/funded-wallet tests remain roadmap work |
| Mining | `f4c1506` / worker `13f10a0`: 2,551 cases per selected profile | Completed bounded checkpoint; stock P2Pool remains incompatible, no pool/payout result |
| Demo/brand | `c9ddfb3`: private incoming payment/seed restore and comparison materials | Completed bounded checkpoint; no reason to restart the old assignment |
| Aggregate reporting | `b092ca4`: 40 synthetic storage/formatting cases | Full daemon/wallet integration still open; no separate worker started |
| Website | `bd77e07` committed the already-deployed unsupported-browser signup fix | September 13 local verification passed; real iPhone and end-to-end delivery remain unverified |

`git cherry HEAD swarm/20260912-network` identified **two missing patch-unique
commits**: `5aeabb6` (guarded selected runner) and `c1f8d05` (failed selected run
and diagnosis). Other commits on that branch have integrated patch equivalents.
The latest root handoff's “active selected build” status is therefore stale.

The recovered failures included six DNS/address cases run with networking
disabled and `select_outputs.gamma`, whose fixture used a literal 120-second
conversion and unequal wallclock history for the 90-second picker. Recovery
separated the existing DNS cases and corrected the gamma fixture using repeated
controls, equal-duration history and more samples. Conversion alone was
insufficient. The original failures, exclusions and statistical bounds remain
preserved.

The site handoff's “uncommitted” status is also stale: `bd77e07` contains the fix.
The unfinished Rust attempt reported a container-path `IndexError` and an
unavailable pinned `monero-oxide` dependency. A platform refusal also occurred;
the new task concerns ordinary build tooling, not retrying refused output.

## Resumed assignments

| Agent | Herdr pane | Scope / expected report |
|---|---|---|
| `meow-network-recovery` | `wS:p2` | Completed 9/90 and 12/120 native and P2P verification. `research/recovery-network-2026-09-13.md` |
| `meow-rust-recovery` | `wS:p3` | Completed dependency and crate-build recovery. Final cached wrapper verification also passed. `research/recovery-rust-2026-09-13.md` |
| `meow-site-recovery` | `wS:p4` | Completed local browser capability/hydration/signup verification; no source change needed. `research/recovery-site-2026-09-13.md` |

All three reports exist and their completed checkpoints have been reviewed.
Workers share the checkout: network owns its harness/selected fixture paths,
Rust owns `spikes/cuprate/`, site owns `site/`, each owns its new report/evidence.
They were told not to stage, commit, switch/reset branches, cherry-pick whole
commits, or spawn more agents. The coordinator verified and archived their
completed receipts. All three agents are idle after these assignments; no
completed-result claim follows merely from agent startup.

**Site checkpoint reviewed:** [report](recovery-site-2026-09-13.md) and browser
traces establish placeholder-to-email rendering without push text, supported
desktop presentation, mocked email success/error, returning visitor persistence
and mocked push control flow. The mobile screenshot was visually inspected.
The production build's embedded source-map contents match the current component
and related site sources. Application source is unchanged; the owned loopback
server and isolated browser state were cleaned up. These are local Chrome
checks with intercepted submissions, not actual delivery or iPhone verification.

**Recovered evidence reviewed:** all 39 entries in the network recovery manifest
match their original Git objects; all 37 evidence files match recovered bytes.
New runner changes are reviewed separately from those original receipts.

**Native build completed:** the fresh selected 9/90 pipeline at
`build/recovery-network-20260913/selected-9-90-launch-01/` exited 0. All 1,237
selected native tests passed across disjoint offline (1,228) and DNS (9)
partitions, with exactly the existing three CI exclusions. Equal-duration gamma
fixtures retain the original median bounds. The first P2P attempt failed before
mining; its blank exit file and nonfatal allocation trace do not establish a
successful exit or memory-cap failure. After adding a bounded synchronization
wait, the retry passed relay, partition/rejoin, depth-three reorg and malformed
transport rejection with healthy subsequent relay at the original 1.5 GiB cap.
This remains accelerated empty-block testing. The coordinator verified native
binary hashes and exact XML coverage, and archived native/P2P receipts under
`research/evidence/recovery-network-2026-09-13/selected-9-90-{native,p2p-pass}/`.
See [network report](recovery-network-2026-09-13.md).

**Fallback completed:** the fresh 12/120 build also exited 0 and passed the same
1,237-case native selection. Direct P2P execution exited 0 and passed relay,
partition/rejoin, depth-three reorg and malformed-transport recovery. Both daemon
exits were 0, with peak memory 614,367,232 bytes and no limit/OOM events. The
coordinator verified five executable hashes and exact XML coverage, and archived
the receipts under `research/evidence/recovery-network-2026-09-13/fallback-12-120-{native,p2p-pass}/`.
One fresh build per profile is not a selected-family reproduction pair or a
matched-capacity loaded-network comparison.

**Rust completed:** [report](recovery-rust-2026-09-13.md) records 658 resolved
packages, genuine pinned Git sources and an actual `cuprate-consensus-context`
compile pass. The frozen wrapper subsequently passed end-to-end with cached
artifacts in 0.64 seconds. Original cache, Git-metadata and wrapper-bookkeeping
failures remain preserved. This is build integration, not runtime parity.

The network agent resumed Codex session
`01a097bd-031d-7d52-be6f-70dadffac411` with cwd explicitly overridden to the main
checkout. Rust and site started fresh with recovered bounded context because
their old state is missing or mixes completed work with pending verification.
Network has priority on `/tmp/meownero-swarm-20260912-heavy.lock`; the existing
single-job, 4 GiB/no-swap, two-CPU, 5 GiB-available preflight stays in force.
Available memory fluctuated below the preflight during recovery; no service may
be stopped to force a build through. Lightweight container tests stay <=512 MiB.

All work remains local: no public push/deploy/launch, spending, real keys,
subscriber reads, live signup, notification send, outreach or host-service change.
Selected 9/90 with gated 12/120 fallback and all launch gates remain unchanged.
The pre-existing `.codex/`, `.mcp.json` and authority-script temporary file remain
untouched. Real-device checks cannot be represented by browser emulation.

## Session evidence and next resume

The current source and build directories are local, untracked artifacts:

| Artifact | Path relative to this checkout |
|---|---|
| Reconstructed clean historical source | `build/recovery-network-20260913/source` |
| Verified selected 9/90 build | `build/recovery-network-20260913/selected-9-90-launch-01/output/source` |
| Verified fallback 12/120 build | `build/recovery-network-20260913/fallback-12-120-run-01/output/source` |
| Genuine pinned Cuprate checkout | `spikes/cuprate/.scratch/recovery-2026-09-13/source-checkout` |
| Isolated Cuprate dependency cache | `spikes/cuprate/.scratch/recovery-2026-09-13/fetch-cache` |

Each network build's `output/` directory holds phase exits, native XML and binary
hashes; `build.exit` is written only when the runner terminates. Read the profile
receipt before using a binary, and compare its hash with the durable evidence.
The reconstructed historical source must stay clean and unbuilt for the
source-only staging mode. Its HEAD is
`7410c04bab0e304112710d63c3225c110bd8b4de`, tree
`4db958cb96d72943c5c2433bd5f4a8f730037148`; the clean15 manifest covers 4,320
tracked files and recursive submodules. Source reconstruction used the pinned
upstream and deterministic patch application from the first two steps of
`chain/build.sh`. Do not rebuild the completed historical reproduction just
to recover source.

Codex metadata was inspected read-only in `<agent-session-store>`, with rollouts
under `<agent-session-store>`. Relevant IDs:

- Coordinator: `01a097bb-f558-7c13-99f6-1f68a23331a3`.
- Network: `01a097bd-031d-7d52-be6f-70dadffac411`.
- Rust unfinished: `01a097bd-1700-7b80-880a-d163c57405f7`.
- Privacy completed: `01a097bd-093d-7ef0-a080-4095709177ba`.
- Mining completed: `01a097bd-0fc4-7c71-8c02-387d6e455dfd`.
- Later Claudex network recovery: `b0f4061d-0313-43e1-9821-8f9c0d68bcce`
  under `<agent-session-store>/`.
- Claude site handoff: `ab32d92f-91b5-4769-a641-07f7baacdcc9`
  under `<agent-session-store>/`.

On resume, inspect `herdr workspace list`, then the live agent names and their
reports before sending work. Do not reuse IDs without checking current layout.
Use `herdr agent read <name> --source recent-unwrapped --lines 80` and inspect
actual processes/receipts before restarting any build. Review recovered changes
and update this index with outcomes before claiming the engineering work done.
