# TJS-299 — Corrections to the TJS-297 lineage report (D1, D2 from QA acceptance TJS-298)

Wallet & transport privacy role (agent `fa593b6f-985b-4373-828c-48c27f575077`), 2026-09-21.
Branch `m1/september-7-verification`, starting HEAD `56acbec` (TJS-298 acceptance of TJS-297 at
`0c14864`). Documentation only. The acceptance is not reopened; no accepted evidence file, manifest,
pinned input or accepted report is modified. This note supersedes two statements in
`research/testnet-v0-lineage-tjs297-2026-09-21.md` and one sentence of the `aeb85d5` commit message,
in the form used for TJS-287's "34 receipts" line (left as accepted history, superseded here).

## D1 — §6 "only the eight documented FAIL lines" is a miscount; the number is 15

The per-manifest numbers in §2 of the accepted report (3, 2, 2, 2 refused-attempt `INPUTS` lines and
6 missing M3 `attempt-03` receipts) are correct. Their sum is 15, not eight. Both committed
fresh-worktree runs agree, and the count is derived from the committed logs alone:

| Log set | Commit checked | `: FAILED` (content) | `FAILED open or read` (missing) | Manifests with any non-OK line | Manifests total |
|---|---|---|---|---|---|
| `research/evidence/testnet-v0-lineage-tjs297-2026-09-21/at-aeb85d5/` | `aeb85d5` | 9 | 6 | 5 | 40 |
| `research/evidence/qa-tjs298-2026-09-21/at-0c14864/` | `0c14864` | 9 | 6 | 5 | 40 |

The 9 content lines are the F3 class (§5 of the accepted report): sync `run01-per-ip-refused`
`INPUTS.sha256` 3 (`sync.py`, `verify-sync.py`, `sync-journey.md`), payment `attempt-01` and
`attempt-02` `INPUTS.sha256` 2 each (`payment.py`, `payment-journey.md`), recover
`run01-history-order-refused` `INPUTS.sha256` 2 (`recover.py`, `verify-recover.py`). The 6 missing
lines are M3 `attempt-03/EVIDENCE.sha256` (`peer0.conf`, `peer0.log`, `peer0.stdout.log`,
`peer1.conf`, `peer1.log`, `peer1.stdout.log`, kept in `build/` by the TJS-230 writer and still
hash-equal there). Reproduce from either committed log set:

```
d=research/evidence/testnet-v0-lineage-tjs297-2026-09-21/at-aeb85d5   # or research/evidence/qa-tjs298-2026-09-21/at-0c14864
grep -h ': FAILED$' $d/*.log | wc -l                                  # 9
grep -h 'FAILED open or read' $d/*.log | wc -l                        # 6
awk -F'\t' '$4!="failed=0"||$5!="missing=0"' $d/manifests.tsv | wc -l # 5 (of 40 lines)
```

Superseding text for §6 of the accepted report: "expect the same 40-manifest table with only the
**15 documented non-OK lines** (9 refused-attempt `INPUTS` FAILED lines over four manifests plus 6
missing M3 `attempt-03` receipts, 5 of 40 manifests)". The `lineage-check.sh` overall FAIL remains the
expected and correct verdict for those two classes; nothing else in the table is non-OK. The TJS-298
issue text's "eight" inherited the same miscount from this report.

## D2 — the committed `unsigned` tamper receipt is a removed-manifest control, not an unsigned edit

`research/evidence/testnet-v0-pool-restart-tjs297-2026-09-21/tamper-refusal.json` key `unsigned` has
`exit` 1 and `last_line` `FAIL: [Errno 2] No such file or directory:
'build/testnet-v0-pool-restart-tjs297-tamper/unsigned/EVIDENCE.sha256'`. That is the verifier's
open-failure path on a missing `EVIDENCE.sha256` (`verify-pool-restart.py` reads the manifest before
any receipt), not its `changed receipt: <name>` path on a receipt whose bytes differ from the manifest.
So the accepted report's §3 sentence "edited without re-signing → refused at the manifest" and the
`aeb85d5` commit-message sentence "an edited-but-unsigned copy is refused at the manifest" describe a
control that this receipt does not witness.

**Relabel (superseding):** read `tamper-refusal.json` key `unsigned` as **`manifest-removed`**: a
byte-faithful copy of run01 with `EVIDENCE.sha256` deleted, refused before any receipt is checked. The
committed evidence file and its `MANIFEST.sha256` are unchanged; the key name stays `unsigned` in the
accepted bytes and this note is the correction of record.

Cross-check on this host (not archived; `build/` is ignored): the scratch copy
`build/testnet-v0-pool-restart-tjs297-tamper/unsigned/` still exists and `diff -rq` against the
committed `pool-restart/` receipts reports exactly one difference, `Only in …/pool-restart:
EVIDENCE.sha256`; every receipt including `pool-restart.json` is byte-equal to run01. From the committed
evidence alone, the derivable statement is the `last_line` above, which already identifies the missing
manifest as the cause.

**The edited-but-unsigned case is witnessed by QA, not by this slice:**
`research/evidence/qa-tjs298-2026-09-21/tamper-controls.json` key `unsigned-edit` (exit 1, `FAIL:
changed receipt: pool-restart.json`, `as_expected` true) and, separately, key `manifest-removed` (exit 1,
same `Errno 2` path as this slice's `unsigned`). The pool-restart negative-control set therefore
covers both refusal paths at `56acbec`, with the edited-unsigned witness owned by TJS-298. The next
pool-restart slice's own control script should include both cases under their correct names, as
QA's `tamper-controls.py` (28 cases) already does.

## What this run did and did not do

Read-only over `research/evidence/` and `build/`; two `sha256sum -c` runs on the TJS-297 lineage and
TJS-298 `MANIFEST.sha256` files (both OK) before citing their logs. No recipe, container, daemon, pool,
worktree or lock was used. No push, no mainnet, no public testnet, no key or seed. No accepted
report, evidence file, manifest or pinned input was modified; this note is the only new file.
