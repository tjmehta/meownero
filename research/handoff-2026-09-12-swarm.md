# Parallel engineering integration handoff — 2026-09-12

This follows the [foundation checkpoint](handoff-2026-09-12-resumed.md).
TJ explicitly authorized focused parallel local Codex/Herdr sessions. Five
workers started from `39070e8` (including `81b3182`), completed bounded
deliverables and stopped repository writes. The coordinator reviewed and
integrated all five locally. [Ownership and commit mapping](swarm-coordination-2026-09-12.md).

No push, public release, launch, spending, third-party messages, real keys or
host/OpenClaw/runtime changes occurred. No economics, identity, ticker,
checkpoint, second-signer or audit-budget decision was made. Unrelated `.codex/`,
`.mcp.json` and `chain/test-authorities.sh.tmp.1647189.55b20b892d45` remain untouched.
Site and all fifteen production patches are unchanged.

## Integrated results

| Track | Local integrated commit | Verified deliverable | Remaining boundary |
|---|---|---|---|
| Network | `924f367` | Real P2P partition/rejoin, depth-3 reorg, malformed-frame rejection followed by healthy relay; bounded empty-block timings | Clean15 waiting for host RAM; actual matched 90/120 capacity and FCMP workloads unbuilt/unmeasured |
| Privacy | `48f224b` | Strict wallet startup launcher and 29 observer/refusal/response cases; no direct daemon fallback in tested failures | OpenAlias can issue DNS despite no-dns; trusted RPC controller can change trust/TLS; actual Tor/relay/sync correlation and broader hostile-node tests open |
| Mining | `3b4c448` | Pinned P2Pool reward/fork routines plus actual Meownero RPC/ZMQ and coinbase negative/positive controls | Unmodified P2Pool is incompatible; no pool or payouts demonstrated |
| Rust | `8b3fc83` | 1,870 ordinary/synthetic/fixture primitive parity cases, three separately expected extreme-arithmetic mismatches | Extracted source functions, not Cargo/cache/full-node integration or a live vulnerability claim |
| Demo/brand | `c9ddfb3` | Private incoming payment, fresh-process seed restoration and reopen; 321 hash vectors; baseline measurement, comparison recipe and visual materials | No optimization gain, meaningful anonymity, FCMP, chosen identity, prize or outreach claim |

Reports with commands and raw receipts: [network](swarm-network-2026-09-12.md),
[privacy](swarm-privacy-2026-09-12.md), [mining](swarm-mining-2026-09-12.md),
[Rust](swarm-rust-2026-09-12.md), [demo](swarm-demo-2026-09-12.md).
The coordinator's [facts versus choices](swarm-facts-and-choices-2026-09-12.md)
separates source corrections and exact issuance arithmetic from normative policy.

The received payment was **0.123456789012 MEOW**. Its address, incoming history,
total/unlocked balance and reopened state match after original wallet files are
removed and the seed restored in a fresh process. A local note does not return.
The original successful coinbase seed test and its evidence remain intact.

## Coordinator verification

- Reviewed changed flows and callers, test positive/negative controls, source
  extraction and arithmetic domains, subprocess/network boundaries and evidence
  scope. Rendered storyboard/moodboards were visually inspected.
- [Integration checks](evidence/swarm-2026-09-12/coordinator/integration-checks.json):
  source/harness/evidence manifests match; nine new Python files parse; all
  production patches, original seed scripts, site and preserved source are
  unchanged; the three preserved binary hashes match the foundation receipt.
- [Shellcheck/workflow check](evidence/swarm-2026-09-12/coordinator/lint.log):
  Shellcheck 0.9.0 passes all sixteen runners; workflow YAML and eleven embedded
  shell steps parse. Tools were installed only in a disposable capped container.
  One literal-brace warning was fixed by quoting `HEAD^{tree}` in `build.sh`.
- CI now watches/lints the new harness paths. New local fixture-specific runtime
  suites were not wired into remote CI; no remote-CI success is claimed. The
  prior 1,237/1,237 production selection remains historical verified evidence,
  not a newly rerun suite. Production code did not change in this checkpoint.
- Authored-code/document whitespace checks pass. Raw upstream/evidence bytes
  retain their original whitespace; their hashes are preserved.

Shared operator/threat guidance now distinguishes wallet daemon RPC, transaction
relay, sync and local RPC administration. Blanket no-DNS and unsupported stale
advisory claims were removed. Startup policy is not process-wide anonymity.

## Preserved clean-fifteen reproduction waiter

**Compiler not started at handoff.** Host available RAM repeatedly stayed around
2–3 GiB, below the 5 GiB preflight gate for the 4 GiB capped, single-job build.
Existing services were not stopped or reconfigured. Disk was approximately
38 GiB free. This is a concrete host-capacity blocker, not a successful build.

- Detached launcher PID at snapshot: `19457`.
- Launcher/log/exit directory: `/tmp/meow-swarm-network-20260912-run`.
- Log: `reproduction.log`; completion-only exit file: `reproduction.exit`.
- Future source builds: `reproduction/{first,second}`.
- Frozen inputs: `frozen-inputs-15`; frozen manifest SHA-256:
  `6f74c265453e138cea3b3936542ef410ff3f0396ae561a8aa9a9f3eae7c3518e`.
- Preserve worktree `/tmp/meownero-swarm-20260912-network`: the live waiter uses
  its unchanged worker-commit scripts, byte-matched to the frozen input copy.
  The coordinator's later quoting-only lint fix is semantically equivalent and
  does not alter those running inputs or production patches.

Read-only collection:

```sh
ps -p 19457 -o pid,stat,etime,comm
tail -20 /tmp/meow-swarm-network-20260912-run/reproduction.log
test ! -f /tmp/meow-swarm-network-20260912-run/reproduction.exit || cat /tmp/meow-swarm-network-20260912-run/reproduction.exit
```

The waiter releases the shared lock while checking resources and will proceed
when the gate passes; do not start a duplicate. After completion, collect its
exit, both clean-build hashes, source/submodule/input/version/package receipts
and logs before claiming reproduction. The network report includes recovery
commands if the waiter is gone. The preserved thirteen-patch clean trees and
incremental fifteen-patch source/binaries remain unchanged. Cross-host and
independent compiler/package reconstruction are separate open claims.

## Next work without reopening settled decisions

1. Collect the queued clean15 build once host capacity permits. Actual 90/.675
   candidate builds need demonstrated capacity-per-second normalization, not
   merely matched subsidy or offered load. Full FCMP daemon/wallet/FFI/proof
   integration must exist before FCMP network-performance claims.
2. Apply literal-address/OpenAlias and authenticated-controller policy when
   integrating the wallet application, then test that boundary. Extend hostile
   node tests to funded-wallet/decoy paths, false valid-looking data, eclipsing,
   response limits and real transport observers. No blanket Tor safety claim.
3. A P2Pool port needs an explicitly reviewed chain profile: genesis binding,
   address encoding, flat reward, fork table, peer/sharechain identity and
   measured low-hashrate share/payout behavior. Current probes do not supply a
   working pool or protection against majority hashpower.
4. Cuprate remains a differential-testing candidate. Actual locked crate/cache
   integration, arithmetic-domain handling, Meownero consensus adaptations and
   full validation/persistence/reorg parity remain open.
5. The optimization challenge has an actual baseline and runnable candidate
   comparison recipe. No candidate or constant-time certification is supplied.
   Brand assets remain review materials. Full video, outreach and prizes are
   outside this completed local deliverable.

Other earlier open work remains: real variable-work/shorter-heavier/long-alt
forks, launch timestamp-attack replay, malformed private proofs/transactions,
sustained uptime, restored-wallet spending and interactive CLI recovery. Human
readiness and launch gates remain unchanged. Herdr workspaces `wB`–`wF` and their
worktrees remain available for inspection; all workers have stopped writes.
