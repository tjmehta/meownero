# Outer launcher source evidence, October 27

This is source evidence for the [latest lead decision](/TJS/issues/TJS-2504#comment-c78e1c2c-262f-41fb-9f1e-6e3ef52ca45d). Read [the capability checklist](../../capability-checklist.md) first.

- `authorization.json` preserves authenticated exact-comment readback with original lead author/run attribution.
- `tests.log` records 22 new outer lifecycle tests. They use disposable lock/ledger files, sealed memfds and an in-memory manager. OOM, crash, timeout and cleanup failure are modeled events.
- `retained-tests.log` and `handoff-tests.log` record the 18 profile and 11 inherited-handoff tests. Total: 51 passing source tests.
- `source-check.json` records the final full source check after the correction pass, including exact candidate/input hashes, 32 repository bindings, 63 pinned upstream paths and 17 request/guard schema mappings.
- `capability-check.json` records four unbound named inputs. `default-refusal.json` records exit 3 before host operations.
- `summary.json` records the source-only scope and remaining NOT_RUN boundaries.

Bash syntax and whitespace checks pass. No actual original heavy-lock operation, capacity/resource observation, admission/reservation, provisioning, image export/import, build, container/native binary, host recovery or final cleanup ran. The source test's duplicate temporary FD surviving launcher-core close is not evidence that an installed manager survives host OOM or SIGKILL. No bootstrap hash is enabled. No grant is requested. The prior native/helper evidence, zero-premine 9/90 policy, full native proof/maturity/payment matrix and independent review gates are preserved.

One implementation pass and one correction pass were used. The correction adds live lock checks during custody/cleanup, guaranteed local descriptor closure on interrupted recovery, and separate tests of file and directory fsync failures. Exact source qualification, a real manager adapter and host capabilities remain necessary. P2P/Mining keeps source ownership. Needs TJ: None.
