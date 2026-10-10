# TJS-1993 preserved Docker writer handoff

Changed

One normal Herdr prompt continued the existing TJS-1882 writer. It pointed to the already-persisted SOURCE HOLD comment `7f895389-413f-471c-ba09-addec7fe93d4` and its existing source-review receipt. At 17:41:19 UTC on 2026-10-10, the same native session explicitly adopted all four findings with receipt SHA256 `675d81524fbde416a7194e2cdf57846548b8e64b3e805709dfaff5f601268d40`. It began reading the affected Docker code. The current build remains diagnostic under its original bounds. This task added evidence only on its own branch.

Verified

- Herdr client/server 0.9.1, Codex 0.160.0. Genuine caller was `w1Y7:p1`; all writer controls used explicit `w1XK:p5`.
- Writer is `platform-engineer`, foreground PID `405325`, shell PID `402314`, terminal `term_65d7f5685b5911d4`, in the original TJS-1882 worktree. Its process environment names task `e7cb422f-9c00-46f6-b0c3-decce627b08e` and run `7b1748f7-db9e-498d-a199-03321fa7a39e`.
- Native transcript metadata proves thread `01a126be-22c3-7c71-a83e-077777c7e5d1`. The current bridge and task placement records map the live pane to adapter session `2df61bd7-5d1a-4b63-a9f0-c999e21fa396`. They have no published nativeThreadId. The older `99488148-04ad-4b7d-8de6-ac9ad47b7d85` record belongs to a closed earlier pane, not the live writer.
- Board run `7b1748f7` was terminalized at 17:08:00 UTC as `orphaned_running_run`, while native transcript activity and compilation continued afterwards. Follow-up `abc2f1c7` failed on occupied-pane refusal. Successor `d42620cc` was cancelled with `execution_reconciliation_required`.
- At the observation, TJS-1882 HEAD was `39b8f603260076a29cc79a2348e5b1719177eed5`. The Docker files still matched the held hashes `e441bab9`, `d2fc92d1`, and `ccb3347f`. Full hashes and timestamps are in the evidence. These are observation bindings, not a freeze of the writer's later corrections.
- Receipt was present at the supplied task-local path, exactly 28,635 bytes with the supplied full SHA256. Native delivery and adoption are separate transcript events, retained in `ownership-and-submission.json`.

Unconfirmed / next

Normal board linkage remains blocked. TJS-1882 has `executionRunId=null` and an `execution_owner_active` blocker naming failed run `abc2f1c7`. Its execution projection permits only `inspect_run`; recovery actions are empty. The task-session read returns 403. The installed bridge can observe a correctly identified active resume session, but does not adopt a different cached Codex session from occupancy. The exposed recovery-resolution API requires an active action and a stopped-provider claim; neither condition is satisfied for this live writer.

Agent systems lead `13de7aa2-02c2-41b4-b74c-185d843064d2` owns the smallest remaining boundary: restore authenticated task/run linkage to the surviving pane and its actual recorded session, and reconcile the failed follow-up lease through supported owner recovery with lease-specific liveness proof. Preserve the live writer and diagnostic build. A runtime change belongs to that protected owner scope.

Independent safe work is already live in the existing writer: source corrections for acquisition, cleanup/finalization, frozen input binding and actual Docker-host capacity. Parent retains original review, bounded image build, wallet/payment/restore/later-spend/CLI/deadline/live-interruption acceptance, website distribution and group synthesis. No accepted native archive or GUI source was changed here.

Observed behavior: adapter termination did not prove native worker termination. The live pane's recorded adapter session differed from the board's cached continuation identity.

Needs TJ: None.

## Lease recovery boundary (agent systems lead, 18:03 UTC)

The writer finished. At 17:53 UTC pane `w1XK:p5` reported `done`. Its result is `result.md` in run `7b1748f7`, 5,225 bytes, SHA256 `1a8e17b36f1fb57196ee1b6d6a1bd752c9dd56dd7f2543b36324a0359fb33bc0`. It committed candidate `823d1fe4fbdb7359f79aad6a05a613aa652d4697` with all four SOURCE HOLD findings corrected. The upload and the `in_review` submission returned HTTP 409 `Issue run ownership conflict`. No Docker build or TJS-1882 container is in flight.

TJS-1882 has exactly one server blocker. Lease `e9766e27-0177-4b24-aed8-bc6d3467534b` is still `active`, provider local, policy ephemeral. It belongs to failed run `abc2f1c7`. That run never launched a native provider: the bridge refused it at placement. Its bridge PID 9305 ran in the container instance that was replaced at 17:23:22Z, and the current container returns ESRCH for that PID and its process group. No native coordinator row exists, and no host process carries the run ID. The live writer's own lease was already terminal at 17:08.

Cause: the container restart interrupted post-run finalization before lease release. The startup sweep retries stranded leases only for `orphaned_running_run` or terminal issues, so this lease is never retried. In the last 14 days, 840 `adapter_failed` runs released their leases normally. Leases `1af33cfb` (TJS-1235) and `6d852309` (TJS-1240) from runs that finished at 17:22:45 are stranded in the same way.

The supported release is `POST /api/environment-leases/:id/release`. The server re-proves that the run is terminal, that no coordinator owns it, and that its PID and process group are dead. The route is restricted to a board instance admin. This run's attempt returned 403 and left the lease unchanged. Execution reconciliation cannot substitute, because it refuses while any lease is unreleased. The UI has no release control.

After release, the ownership blocker clears. A normal TJS-1882 wake then runs the bridge's launch recovery: the `interrupted` writer run counts as settled for a successor, so the owned `done` pane closes under its guards and the assignee's session starts. The bridge record has no native thread ID, so that session is new. Thread `01a126be` stays on disk. The writer's turn is complete and durable, so only the control-plane submission of `823d1fe` remains.

Full bindings: `research/evidence/preserved-docker-writer-tjs1993-2026-10-10/lease-recovery-boundary.json`.

Needs TJ: one board call, `POST /api/environment-leases/e9766e27-0177-4b24-aed8-bc6d3467534b/release` with an empty body.
