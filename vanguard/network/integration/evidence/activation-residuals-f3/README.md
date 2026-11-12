# TJS-4398: F3 UTC and rotation correction

**Changed**

One correction round against `57d202ddee295593544bc560718a36007a301ad6`,
addressing [Security revision a1e5c6be](/TJS/issues/TJS-4398#document-security-review).
Writer: P2P & Mining Systems `3730ad68-e373-4c8a-84df-2e11327b86a5`,
run `6dd48dbd-3d76-4009-8d5b-cff9c5c62bdf`. The issue implementation report
names the exact correction commit on the existing managed branch.

| Finding | Before | After / affected caller |
| --- | --- | --- |
| F3 UTC | A naive banner datetime used the CLI's local zone. Tests made the same assumption. | `operator_contract.activation_seed_witness` assigns explicit UTC before conversion to POSIX seconds. Its read-only CLI caller and timestamp/rotation docstrings use UTC. The window fixture uses literal POSIX seconds; the regression sets UTC, UTC-8 and UTC+9 itself. This extends the witness's timezone behavior without changing launch selection or dial classification. |
| F3 rotation | The runbook suggested recovering a prefix into a file the CLI refuses. | The runbook uses the existing planned restart: preserve all logs, stop/seal/attest/reopen, refresh the PID and authenticated TLS pin when applicable, then sample a new UTC banner in the actual running file. No seed-pass line is required. Prior ALERTs still need investigation. This composes the existing restart and witness contracts. |

The review permitted either bound rotated predecessors or a planned restart.
The latter reuses the accepted supervisor and unchanged file-identity check;
it adds no rotated-file discovery or concatenation interface. It deliberately
costs a planned interruption after rotation and does not recover observation
for the old launch. This choice follows the review's stated acceptance option.

The current mutation runner adds local-time parsing as its nineteenth fault
and writes this round's output here. Its original directory manifest is updated
for that runner only. Earlier correction evidence and the original rehearsal
rows remain byte-identical. This report supersedes the historical reports'
timezone premise and rotation remedy, not their raw measurements.

**Verified**

Run from the worktree root:

```sh
python3 -B vanguard/network/integration/evidence/activation-residuals/guarded-source-tests.py --focus
python3 -B vanguard/network/integration/evidence/activation-residuals/guarded-source-tests.py --mutations
python3 -B vanguard/network/integration/evidence/activation-residuals/guarded-source-tests.py --full
python3 -B vanguard/network/integration/evidence/activation-residuals-f3/cli-check.py
```

`source-summary.json` records the collected exits, counts, timings, guard
receipts and tested source hashes. The gzip logs retain the full output.

- The new explicit-zone regression failed on the original parser in both
  non-UTC zones (`baseline-utc-regression.log`). Its fixed POSIX window is
  independent of the parser and host timezone.
- All 19 mutants are detected with clean controls and unchanged source bytes.
  The new local-time mutant fails in both non-UTC zones even on a UTC host;
  `mutations.json` and paired gzip logs record the details.
- All 40 unmocked CLI probes pass: clean UTC banners, current/old upstream
  dials, old-only and ambiguous launches, rotation and planned-restart recovery,
  each under UTC, America/Los_Angeles, Europe/Berlin and Asia/Tokyo. The actual
  CLI reads real procfs and files from short-lived sleeping stand-ins with the
  checked argv. A new PID and banner return OK without a seed pass; a new
  upstream dial returns ALERT. Rotated and concatenated substitutes remain
  UNVERIFIED. All stand-ins are reaped and temporary directories removed.
- `integrity.json` proves all 80 frozen paths still equal `fe479217`, all 65
  prior correction-evidence files equal `57d202d`, and the contract AST outside
  the witness and datetime import is unchanged. This preserves items 2–6.
- Both nft variants and both plan maxima render byte-for-byte identically to
  `57d202d`. Their accepted real `nft -c` and functional fairness/full-set
  evidence in `../activation-residuals-correction/` is reused, not rerun. The
  four exact hashes and reuse reason are in `integrity.json`.
- All three prior evidence manifests and this directory's manifest verify.
  `manifest-checks.log` records the prior checks. Whitespace passes.

The pinned fork `e151643c5269c83bf24a83b2548e2493876026b2` defines
`ELPP_UTC_DATETIME` in `external/easylogging++/ea_config.h:11`; the time helper
then uses `gmtime_r`. The log size and rename behavior are in
`contrib/epee/include/misc_log_ex.h:41` and `contrib/epee/src/mlog.cpp:166–170`.
`source-premises.json` retains inspected source excerpts and hashes. Explicit
UTC conversion follows the Python [datetime timestamp contract](https://docs.python.org/3/library/datetime.html#datetime.datetime.timestamp);
the regression restores the process timezone after [tzset](https://docs.python.org/3/library/time.html#time.tzset).

**Unconfirmed/next**

Security re-reviews F3 on the exact correction commit and checks unaffected
items by byte equality. Independent acceptance remains pending. The Meownero
lead owns subsequent integration and public replay; no branch merge or push
occurred here.

The stand-in probes verify the process/log/CLI boundary, not a native daemon,
seal/attestation execution, live 100 MB rotation or public-host operation. No
native seed rerun is needed: runner, driver and inputs remain frozen. The
witness still assumes managed single-writer logs, the default file format,
numeric INFO-visible logging and stable wall time since launch. Missing or
ambiguous current coverage remains UNVERIFIED. This is not executable
attestation or proof of arbitrary-egress absence. The restart remedy preserves
logs and cannot erase an incident or assert health for the previous launch.

No activation, host rules/router/DNS/uid/rented-host change, spending, key
custody or public push occurred. `launch_ready` and `public_launch` stay false.
Agent-reviewed is not externally audited.

Needs TJ: None.
