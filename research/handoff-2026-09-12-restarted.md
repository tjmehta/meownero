# Restarted engineering checkpoint — September 12, 2026

**Later update:** [clean15 completed; selected builds started](handoff-2026-09-12-selected-builds.md).
The in-progress historical-build status below records the earlier checkpoint.

TJ requested resuming local work and explicitly named the idle network, privacy,
mining and Rust Herdr panes. All four panes were at shell prompts with no Codex
foreground process. The previous handoff had closed their bounded tracks;
the selected-policy distribution had only requested acknowledgments. The exact
reason their old processes exited is not established.

New Codex sessions started in the same existing panes/worktrees: network
`wB:p1`, privacy `wC:p1`, mining `wD:p1`, Rust `wE:p1`. No extra panes, workspaces
or worktrees were created. The earlier track-closed instructions were
superseded for these explicitly assigned tasks. The coordinator remains in the
main checkout. Selected 9/90, gated 12/120 fallback and prior safety boundaries
remain as recorded in the [issuance decision](decision-2026-09-12-issuance.md).

## Integrated work

- `b092ca4`: [wide aggregate reporting](resume-reporting-2026-09-12.md), 40 cases
  using literal pinned core aggregation and RPC/CLI formatting with synthetic
  block storage. Exact totals survive u64 saturation; legacy RPC low-word fields
  alone do not represent the full total. Full daemon/wallet integration remains
  open.
- `7dedf3d` (worker `ffc7f77`): [privacy](resume-privacy-2026-09-12.md), 52/52 cases
  with the real historical wallet binary. Optional native restricted RPC opens
  an existing wallet and denies daemon changes/spending/key export. Default
  administrative mode and restricted OpenAlias limitations remain explicit.
  Large malformed responses were semantically rejected; no response-size ceiling
  is established.
- `f4c1506` (worker `13f10a0`): [mining](resume-mining-2026-09-12.md), 2,551 cases
  per selected profile, 5,102 total, plus stock controls. Actual pinned reward,
  fork and address routines feed an isolated profile gate. Stock P2Pool remains
  incompatible; no shares, pool, payout or FCMP integration is demonstrated.
- `15cd331` (worker `1c0705b`): [network](resume-network-2026-09-12.md), five
  profile/refusal tests, selected source preparation preserving 4,320 tracked
  input hashes, profile-aware P2P entry checks and bounded resource/lock waits.
  Selected sources are staged but unbuilt. Actual capacity/time remains unequal;
  no new selected P2P or FCMP performance result is claimed.

Coordinator review verified the changed flows and input/evidence scope, fixed
one Shellcheck warning through the network worker, and checked integrated bytes,
manifests, compressed mining vectors, Python syntax and five profile tests.
[Integration checks](evidence/resume-2026-09-12/coordinator/integration-checks.json)
and [Shellcheck/workflow log](evidence/resume-2026-09-12/coordinator/lint.log).
The production suite was not rerun because production code did not change.

## Rust work is incomplete

The new Rust session stopped with the platform UI message “This content can’t be
shown” and a note that some cybersecurity requests may be limited. The
coordinator requested only an operational handoff, not a retry of the restricted
output. No passing result or code integration is claimed for this resumed work.

Partial uncommitted files remain under
`/tmp/meownero-swarm-20260912-rust/spikes/cuprate/resume/` and its new `.gitignore`;
scratch output remains under `spikes/cuprate/.scratch/`. The worker reports a
container-path `IndexError` in `prepare.py`, unfinished frozen dependency/fixture
checks, and full crate resolution blocked by uncached pinned `monero-oxide`.
Its historical 1,870-case primitive checkpoint remains the last passing result.

## Build recovery

The old clean15 waiter was no longer advancing and had no completion receipt.
The network worker verified its state and restarted one reproduction using the
preserved frozen scripts and immutable builder. The new launcher is:

`/tmp/meow-swarm-network-20260912-run/resume-once/run.sh`

Its adjacent `reproduction.pid`, `reproduction.log` and completion-only
`reproduction.exit` identify the new run. Build roots remain
`/tmp/meow-swarm-network-20260912-run/reproduction/{first,second}`. It uses one
compiler job, a 4 GiB/no-swap cap, two CPUs, the shared heavy lock and unchanged
5 GiB available-memory preflight. No existing services were stopped. Do not
launch another reproduction while this one is live. No matching binary hashes
have yet been collected for this resumed run.

At the network checkpoint the first daemon had compiled and wallet dependencies
were building. A partial daemon receipt is preserved in the network evidence;
it is not completion of the first full build or the two-build comparison.
Launcher PID was `1294126`; always re-check both it and the owned container
before deciding whether the run is still active.

All work remains local. No push, release, launch, spending, real keys or external
messages. Protected production patches, seed-recovery/demo evidence and site
remain unchanged. Unrelated `.codex/`, `.mcp.json` and the pre-existing
`chain/test-authorities.sh.tmp.1647189.55b20b892d45` remain untouched.
