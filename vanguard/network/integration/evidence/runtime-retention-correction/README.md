Runtime staging retention correction for Platform finding5ab745cc at baseline6671d176.

Changed: run-profile.py now decides the started runtime outcome before deleting
staging. Rejected diagnostics/witnesses, FAIL or missing required runtime rows,
and failed or missing runtime OOM counters retain owned0700 staging after owned
CID absence. The result is FAIL and staging removal stays NOT_RUN with the existing
retention flag. Cleanup rows do not cause retention. Successful full/reuse runs
still delete staging; pre-runtime refusals/build failures keep their cleanup.
The existing same-run local inspection, redacted summary, exact-path deletion and
record procedure remains required for actual granted native failures.

Verified: final347 source tests PASS,0 failures/errors/skips, including68 direct
checks. The added matrix covers six zero-exit adverse outcomes in full/reuse modes
(12 connected cases), private fixture retention/no export and exact deletion.
Runtime-only nonzero exit and existing full/reuse success/pre-runtime controls pass.
The identical new matrix against baseline6671d176 detects all12 failures. This
known-bad execution uses the exact Git blob in a substituted controller fixture;
no extra worktree, native build or old grant is used.

First focused68 had two failures: old tests expected deletion after evidence
rejection. Their retention expectations were corrected without removing their
rejection/export assertions. First full347 had one stale historical manager runner
hash. All33 overlapping entries were checked; only that digest was updated, then
the complete index refrozen. Both original failed logs are retained. The final
source remains unchanged during passing qualification. See qualification-correction.md.

Eight protected files match16024ec4 exactly; the native driver is byte-identical
to6671d176, preserving its sole authorized traceback-line delta. All non-candidate
input sections and build/freezer/profile/overlay/pins/caps/workload/private RPC are
unchanged. The historical manager changes only its overlapping runner hash.
AST, build-shell syntax, whitespace and final freeze/check pass.

The source launcher rejects builtins/io/os opens of the original heavy-lock path
or device/inode before the call, and rejects flock before acquisition. Original
lock metadata is unchanged; zero blocked touches. All lock fixtures are disposable.
Docker, admissions, native runtime and private data are substituted. Only dummy
traceback/native/wallet log sentinels are inspected and deleted. These results are
source/model evidence, not actual native retention/reuse or capacity acceptance.

Next: P2P consumes Platform reassessment on this exact candidate, then requests
Security source assessment on lead items2-5 serially. Both precede a separate fresh
exact Platform grant and two admissions. Old grants remain consumed. Preserve Core
decision47234b59/count2 and later configured Security. Historical native runtime
ATTEMPTED_FAIL; this run native NOT_RUN; all16 functional rows remain NOT_RUN.
The complete consensus/maturity/payment/persistence/recovery matrix and accepted-only
lead integration remain open. launch_ready=false; public_launch=false. Needs TJ: None.

Learning delta (observed behavior): process exit zero does not establish a valid
runtime outcome. Validate required evidence before removing its private cause data.
