# Resumed network checkpoint — September 12, 2026

TJ's resumed local engineering authorization supersedes the earlier closed track.
The coordinator's `research/decision-2026-09-12-issuance.md` selects **9 MEOW/90 s**,
with **12 MEOW/120 s** as a gated fallback. Both issue 3,153,600 MEOW per 365 days
before penalties. The frozen clean15 reproduction remains the historical
0.9 MEOW/120 s control. No production patch, historical evidence, real key,
shared decision document or host service was changed. No new agent, push,
publication, outreach or spend occurred.

## Reproduction resumed exactly once

At inspection, old launcher PID `19457` did not exist, no network build container
was running, the old log ended at `2026-09-12T18:14:53Z`, no exit receipt existed,
and neither clean build tree existed. Available RAM was about 11 GiB. The
[frozen manifest](evidence/resume-network-2026-09-12/frozen-input-SHA256SUMS), SHA-256
`6f74c265453e138cea3b3936542ef410ff3f0396ae561a8aa9a9f3eae7c3518e`, and every
listed input were verified before resumption and again at this checkpoint.
[Preflight](evidence/resume-network-2026-09-12/reproduction-preflight.json).

A create-once `resume-once` directory prevents this launch from being repeated.
[The new launcher](evidence/resume-network-2026-09-12/resume-runner.sh) reads the
**frozen** `test-reproducibility.sh`, guard and build scripts, so this worktree's
new harness edits cannot change its inputs. Original logs/launcher/PID file were
preserved. The resumed process has a three-hour outer timeout; its completion
receipt is separate from the historical missing receipt.

[Live snapshot at 22:44 UTC](evidence/resume-network-2026-09-12/reproduction-checkpoint.json):
launcher PID `1294126`, container `meow-swarm-network-1294160-27641`, first clean
source HEAD `7410c04bab0e304112710d63c3225c110bd8b4de`, tree
`4db958cb96d72943c5c2433bd5f4a8f730037148`. The first daemon has compiled and the
build has proceeded into wallet dependencies. Its [partial artifact receipt](evidence/resume-network-2026-09-12/first/partial-daemon.json)
is not a completed clean-build receipt. The first build's image/package receipts
and compiler-log snapshot are retained. Full first-build tests/artifacts and the
second build remain pending; **clean15 reproducibility is not yet established**.

The source build holds `/tmp/meownero-swarm-20260912-heavy.lock`, with one compiler
job, 4 GiB memory/no swap, two CPUs, no container networking and cache disabled.
Both resource preflights passed before first compilation. No second compiler was
started. New lightweight checks ran in network-disabled containers capped at
512 MiB/no swap and one CPU. The first build remains active at this bounded
checkpoint; do not start a duplicate or modify its frozen inputs.

Collection paths:

```bash
ps -p 1294126 -o pid,stat,etime,comm
cat /tmp/meow-swarm-network-20260912-run/resume-once/reproduction.exit
tail -20 /tmp/meow-swarm-network-20260912-run/resume-once/reproduction.log
# On completion collect both runs' seven receipts and compare them:
# /tmp/meow-swarm-network-20260912-run/reproduction/{first,second}/
# BUILDER_IMAGE_ID packages.txt SHA256SUMS SOURCE_REVISIONS SUBMODULES
# INPUT_SHA256SUMS VERSIONS
```

An absent exit file means completion has not been recorded. Inspect the exact
launcher and container as well; absence alone does not prove a live build. A
nonzero/timeout exit requires inspecting the owned container before retrying.
Even a successful pair would prove same-image source reproduction only, not
independent toolchain/package reconstruction or cross-host reproduction.

## Selected profile harness

[Preparation and commands](../spikes/network-benchmark/README.md) use the
coordinator's selected overlays directly and preserve their identities in the
[full input manifest](evidence/resume-network-2026-09-12/profile-inputs.json).
The runner verifies current15 HEAD, tracked cleanliness, initialized submodules,
source-lock hashes and every copied tracked file. It excludes untracked files,
binaries and Git metadata; rejects input/output overlap, source drift, output
reuse and unexpected overlay paths; preserves internal tracked symlinks without
dereferencing them; and confines patch application even under a parent worktree.
Both snapshots change only the configuration and reward-function source files.

Final prepared sources, **unbuilt**, are under:
`/tmp/meow-swarm-network-20260912-run/resume-profiles/parent-repo/prepared-reviewed/{selected-9-90,fallback-12-120}`.
The 4,320 tracked input hashes match the earlier inspected snapshots; both are
preserved. These are disposable source snapshots, not selected binary receipts.

The readiness checker defaults to selected issuance; historical controls require
`--family historical`. [Selected inventory](evidence/resume-network-2026-09-12/selected-readiness.json)
and [historical inventory](evidence/resume-network-2026-09-12/historical-readiness.json)
both intentionally exit 2. It distinguishes observed constants from proposed
matched-time budgets. Both overlays retain the 300,000-weight floor, giving
3,333⅓ versus 2,500 nominal floor weight/second. Their 100/100,000-block median
windows span 9,000/9,000,000 versus 12,000/12,000,000 seconds. The proposed
225,000 floor for 90 seconds is **not implemented or enforced** by either overlay.
Binary presence or an FCMP directory cannot turn this inventory into readiness.

The P2P harness accepts selected/fallback/historical profiles, verifies source
constants before startup, and checks each node's actual emission and RPC target.
Existing callers retain the historical default. Its test remains accelerated
empty-block correctness at fixed difficulty one; no selected P2P runtime or
loaded paired comparison was run while reproduction held the priority lock.
The current guard and P2P runner now bound lock/resource waits; the frozen guard
used by reproduction remains unchanged.

## Validation and limits

- [Five readiness/refusal tests pass](evidence/resume-network-2026-09-12/profile-tests.log):
  matched selected issuance with unequal observed capacity; explicit historical
  family; wrong profile; dummy binary/FCMP-directory non-readiness; missing or
  malformed input.
- [Preparation verification](evidence/resume-network-2026-09-12/preparation-verification.log)
  preserves all 4,320 tracked hashes and refuses source drift/output reuse.
  [Final reviewed preparation](evidence/resume-network-2026-09-12/preparation-reviewed.log)
  also passes under a parent Git repository, rejects input/output overlap, and
  rejects an added overlay path before applying it.
- [P2P entrypoint negative control](evidence/resume-network-2026-09-12/p2p-profile-refusal.log)
  rejects historical 120-second source requested as selected 90-second source
  before starting a daemon. This is a refusal test, not a fresh P2P runtime pass.
- [Final guard checks](evidence/resume-network-2026-09-12/guard-tests.log) pass:
  one-second busy-lock exit 75; invalid, zero, >3600 and overflow-sized waits
  exit 2. The coordinator's Shellcheck SC2015 finding was fixed with explicit
  `if`/short-circuit OR validation, rejecting the regex before arithmetic.
  Shell/Python syntax and authored whitespace checks pass. The coordinator's
  [final Shellcheck 0.9.0 log](evidence/resume-network-2026-09-12/integration-lint-final.log)
  confirms both network runners pass after that fix; no shell edits followed.

Remaining blockers are full selected binaries and profile-specific unit fixtures
(the current15 `meow_emission.constant_is_0_9_meow` hard-codes historical reward),
full clean15 receipts, enforced dynamic capacity normalization, actual intended
FCMP integration and proof workloads, loaded validation/relay/stale/reorg
measurements, and native difficulty/timeout recovery. The coordinator owns shared
issuance/aggregate-consumer integration. Neither profile passes launch gates at
this checkpoint, and the fallback has no automatic readiness exemption.
