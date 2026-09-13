# Session recovery — September 13, 2026

TJ requested inspection of unfinished Claude/Codex/Claudex sessions and restarting
focused agents in the Meownero Herdr workspace. This index records recovered
status and assignments, not completion of the newly assigned engineering work.

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
| Selected build/network | Later worker commit `c1f8d05`: 9/90 compiled, full native selection 1,230/1,237 passing, seven failures | Recover runner/evidence, investigate failures; selected P2P and fallback 12/120 never ran |
| Rust/Cuprate | Historical 1,870-case primitive checkpoint integrated | Later crate/dependency attempt incomplete and uncommitted; missing `/tmp` partial files are not recovered code |
| Privacy | `7dedf3d` / worker `ffc7f77`: restricted wallet controller and 52/52 cases | Completed bounded checkpoint; broader transport/funded-wallet tests remain roadmap work |
| Mining | `f4c1506` / worker `13f10a0`: 2,551 cases per selected profile | Completed bounded checkpoint; stock P2Pool remains incompatible, no pool/payout result |
| Demo/brand | `c9ddfb3`: private incoming payment/seed restore and comparison materials | Completed bounded checkpoint; no reason to restart the old assignment |
| Aggregate reporting | `b092ca4`: 40 synthetic storage/formatting cases | Full daemon/wallet integration still open; no separate worker started |
| Website | `bd77e07` committed the already-deployed unsupported-browser signup fix | September 13 local verification passed; real iPhone and end-to-end delivery remain unverified |

`git cherry HEAD swarm/20260912-network` identified **two missing patch-unique
commits**: `5aeabb6` (guarded selected runner) and `c1f8d05` (failed selected run
and diagnosis). Other commits on that branch have integrated patch equivalents.
The latest root handoff's “active selected build” status is therefore stale.

The six DNS/address failures ran with networking disabled. The seventh,
`select_outputs.gamma`, retains a literal 120-second conversion while the selected
picker uses 90 seconds. Its statistical tolerance also needs investigation;
changing the conversion alone is not a verified fix. Original failures must be
preserved; no additional exclusions or weakened assertions were authorized.

The site handoff's “uncommitted” status is also stale: `bd77e07` contains the fix.
The unfinished Rust attempt reported a container-path `IndexError` and an
unavailable pinned `monero-oxide` dependency. A platform refusal also occurred;
the new task concerns ordinary build tooling, not retrying refused output.

## Active assignments

| Agent | Herdr pane | Scope / expected report |
|---|---|---|
| `meow-network-recovery` | `wS:p2` | Recover missing network runner/evidence; narrow DNS/gamma fixture investigation; guarded selected builds if prerequisites permit. `research/recovery-network-2026-09-13.md` |
| `meow-rust-recovery` | `wS:p3` | Pinned source/cache/dependency inventory and minimal reproducible build-tooling recovery. `research/recovery-rust-2026-09-13.md` |
| `meow-site-recovery` | `wS:p4` | Completed local browser capability/hydration/signup verification; no source change needed. `research/recovery-site-2026-09-13.md` |

These report paths are assigned outputs and may not exist until workers finish.
Workers share the checkout: network owns its harness/selected fixture paths,
Rust owns `spikes/cuprate/`, site owns `site/`, each owns its new report/evidence.
They were told not to stage, commit, switch/reset branches, cherry-pick whole
commits, or spawn more agents. Coordinator review/integration remains necessary.
No completed-result claim follows merely from agent startup.

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
