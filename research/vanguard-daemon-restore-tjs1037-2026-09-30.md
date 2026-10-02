# TJS-1037 restore verifier fix round

Candidate: the `TJS-990-meownero-vanguard-bounded-offline-daemon-transport-between-two-isolated-nodes`
branch after `bb7176dfbe2fd030e76682124c091269613b4e5e`.
The TJS-1032 QA files and both original restore bundles were left unchanged.

## Changed

- `vanguard/verify-daemon-restore.py` now checks both receipt binary SHA-256
  values and sizes against repository-side pins. The values come from the
  independent fresh rebuild recorded in
  [TJS-1032 QA](vanguard-daemon-restore-tjs1032-2026-09-30.md#exact-candidate-and-source),
  rather than from the bundle being verified.
- The verifier requires equal daemon tips in both pooled and confirmed
  snapshots. It binds `final_tip` to the confirmed snapshot, the matching
  event state, and the event's confirmed block hash.
- `vanguard/test-daemon-restore-refusals.py` commits the QA's exact
  hash-consistent monerod mutation and matching-event confirmed-tip mutation.
  It also checks the other binary, pooled tips, `final_tip`, and event block.
- `vanguard/test-daemon-p2p-refusals.py` exercises missing pool membership and
  unspent key-image state in separate, hash-consistent copies.

## Network-disabled checks

All commands below exited 0. A test's `EXPECTED_REFUSAL` line means the
mutated bundle's verifier process exited nonzero with the named assertion.

| Command | Result |
| --- | --- |
| `python3 -B vanguard/verify-daemon-restore.py research/evidence/vanguard-daemon-restore-tjs1010-2026-09-29` | `PASS_DAEMON_RESTORE_RECEIPT_RECONCILIATION` |
| `python3 -B vanguard/verify-daemon-restore.py research/evidence/vanguard-daemon-restore-tjs1032-2026-09-30/bundle` | `PASS_DAEMON_RESTORE_RECEIPT_RECONCILIATION` |
| `python3 -B vanguard/test-daemon-restore-refusals.py research/evidence/vanguard-daemon-restore-tjs1010-2026-09-29` | All six mutations refused; `PASS_DAEMON_RESTORE_HASH_CONSISTENT_REFUSALS` |
| `python3 -B vanguard/test-daemon-restore-refusals.py research/evidence/vanguard-daemon-restore-tjs1032-2026-09-30/bundle` | All six mutations refused; `PASS_DAEMON_RESTORE_HASH_CONSISTENT_REFUSALS` |
| `python3 -B vanguard/test-daemon-p2p-refusals.py` | Missing pool and unspent key image independently refused |
| `python3 -B vanguard/test-daemon-p2p-refusals.py research/evidence/vanguard-daemon-restore-tjs1032-2026-09-30/p2p-step0` | Missing pool and unspent key image independently refused |
| `git diff --check` | Clean |

The committed restore manifests remain
`24b4ecdb2bac9f4b4114e1745632ce1dcb89217c917684c7a735b618a8f1ac2a`
(TJS-1010) and
`21ecbfb2b8c043e59dfba7af5daf8f2c1820f6c41d21bd25554ac5eafc111f10`
(TJS-1032 QA). Existing fields sufficed, so the daemon scenario was not rerun
and no new receipt was minted.

These checks reconcile recorded receipts against independently rebuilt binary
pins and internal state relationships. They do not inspect executable bytes
inside the receipt bundle or establish release readiness. Fresh independent
exact-commit QA of this fix remains the lead's next gate.
