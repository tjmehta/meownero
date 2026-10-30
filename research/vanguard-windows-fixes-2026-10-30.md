# Windows tester harness repair and funding diagnostics

Owner source: `3A6B942CF66ABF3A50C6`, authorized 2026-10-30 16:01:24Z.
Run: `d77970d5-927a-48c5-8725-e07124555b1a`. Sole writer remains platform
engineer `92a7b4f2`; existing independent reviewer remains `ec85048c`.

## Changed

Source implementation: `dfa1bc18c5d69b65f71c865b33f7d5caeb835df2`.
Assembly and verification tools: `27bb8f1` (full revision in the download index).
Baseline: `3d04ba7be91f64ac2fdf964afe82ad6d2e6a7670`.
The complete brief, original JSON reports/bindings, and source trace were read from
`<private-notes-path>`.
Source trace SHA256: `dccf6b9cacf602ebcb306207b7d3fba28abb4d9955aa48be16bd2ba5800e1efa`.

Owner requirements and observable results:

1. **ARM fixture handling.** Only Windows error 1314 from the symlink mutation
   becomes `NOT_EXECUTED`, without `refused:true`. The harness continues later
   controls and returns `INCOMPLETE_REFUSALS` with exit 2. Copy errors, other
   fixture errors, real refusal failures and later failures still fail.
2. **Intel funding diagnosis.** The hash-bound wrapper measures initial
   `generateblocks`, `refresh`, and `get_balance` independently. It exports only
   fixed operation/outcome enums and finite elapsed, socket-timeout, journey
   deadline, elapsed-at-start and remaining-at-start scalars. Direct and wrapped
   socket timeouts are `FUNDING_RPC_TIMEOUT`. RPC arguments, addresses, seeds,
   URLs, exception text and local paths never enter this projection. Existing
   socket (90s), journey (1200s) and controller (1500s) budgets are unchanged.
3. **Real report boundaries.** Regression fixtures drive the actual refusal
   entrypoint and hash-bound packaged tester through the wrapper, public
   projector and ZIP exporter. Original baseline failures are retained. The
   real Linux38 package also rejects an actual directory symlink at preflight.
4. **Runnable successor.** The packager now loads explicit committed helper
   bindings. Two pinned patches extend each frozen controller while preserving
   its own unchanged functions, including ARM qualification and Intel capacity
   admission. Inputs, helper, manifest and outer hashes are rebuilt. Packaged
   wallet testers, native programs, licenses and sanitized provenance archives
   remain byte-identical to the previous distributed bundle.
5. **Independent review.** The exact source, tests and downloadable bytes go to
   the existing attached reviewer stage. This report does not grant acceptance.

Changed contract: this **extends** the existing diagnostic/public-report path,
**composes** the existing frozen lane controllers and ZIP exporter, and **removes**
the possibility of aggregate PASS with an unavailable symlink control. The
Windows controller, final CI aggregation and top-level runner all carry
`INCOMPLETE_NATIVE_ARCHIVE_CONTROLS` through the exported report. No crypto,
consensus, source lock, program, network, account or guest-entitlement change.

## Verified

- Nine regression methods pass, including independent timeouts for all three
  funding operations, wrapped timeout, successful funding followed by a later
  error, 1314 continuation, another fixture error and true refusal failure.
- Two selected methods fail against baseline as expected, with four failure
  records: the original 1314 abort and each unclassified funding timeout.
- The same nine regressions pass against the actual shipped i686 lane helpers.
- Five existing bundle selection/privacy/link/collision tests pass.
- Three synthetic scenarios pass through the final bundle's real staged
  controller and outer exporter: incomplete exits 2, full coverage exits 0,
  failed refusal exits 1. These replace the native execution boundary; they are
  explicitly **not native Windows acceptance**.
- Both final lanes pass the actual launcher `--prepare-only` path. This checks
  bytes, extraction and hash bindings only.
- Recursive inspection proves every final file/input/part/helper binding,
  unchanged nested program archives, and unchanged unaffected controller
  functions. All seven pre-existing dirty files are unchanged.
- Process/RPC fixtures finish cleanup and exported public JSON/ZIPs exclude the
  private sentinel. Temporary fixture directories are removed. No Windows
  program, guest or new native workload was started.

Final archive: `meownero-windows-test-diagnostics-v2.zip`, **164,120,029 bytes**.
SHA256: `bedd371bc042ec2b893e45693083eae64637ca1a1f496933f2f90a5bf6f38034`.
Embedded bundle manifest SHA256:
`46489d0ac6cea2e023506f4c893176d4d6d7de68580b19aa0c2c5d52bc364c65`.

The [download index](evidence/vanguard-windows-fixes-tjs1882-2026-10-30/windows-diagnostics-v2-download-index.json)
contains twenty authenticated attachment parts with individual SHA256 values.
The parent must reassemble and verify the whole hash before using the archive.
Group delivery remains the parent's responsibility after verification.

See [verification summary](evidence/vanguard-windows-fixes-tjs1882-2026-10-30/verification-summary.json),
[exact bundle inspection](evidence/vanguard-windows-fixes-tjs1882-2026-10-30/bundle-verification-final.json),
and [synthetic boundary cases](evidence/vanguard-windows-fixes-tjs1882-2026-10-30/aggregation-final/aggregation.json).
First unsuccessful local fixture runs remain alongside their corrected runs.
The first fixture needed a Linux-side stub for a Windows process flag; the
first shipped-helper command needed an explicit path to the top-level runner.
Neither repair changed product assertions. Initial generic patch application
also exposed different frozen source contexts. Exact lane patches supersede it.

Relevant primary documentation: [Windows error 1314](https://learn.microsoft.com/en-us/windows/win32/debug/system-error-codes--1300-1699-),
[urllib blocking-operation timeout semantics](https://docs.python.org/3.14/library/urllib.request.html#urllib.request.urlopen),
and [monotonic elapsed timing](https://docs.python.org/3.14/library/time.html#time.monotonic).
A socket timeout is not a total RPC wall deadline or a diagnosis of the wallet.

## Unconfirmed/next

The corrected harness is implemented and checked synthetically. Its independent
review has not yet happened. The existing reviewer must inspect this candidate
and its exact bundle, then return findings to the same writer.

Native Windows execution of the successor was **not_run**. This assigned runtime
is Linux x86_64; no qualified Windows guest is available through this run. The
separate Windows VM license answer does not affect this completed source work.
After review, the parent owns delivery and any contact with the original testers.
ARM needs a new report proving later controls run with honest incomplete/full
coverage. i686/WoW64 needs a new report identifying the failed funding operation
or showing completion. The Intel cause remains **unknown**; instrumentation is
not a wallet-engine fix. No claim of native x64 binaries or standalone 32-bit
Windows acceptance is made. The optional ARM `native_cli_event: NOT_REQUESTED`
remains informational; the original native ARM CLI open passed.

The seven-target release remains open. This scoped source/bundle review must not
close that release, reopen completed Mac/Linux work, or broaden delivery authority.

Learning delta — **observed behavior:** helper edits at HEAD alone do not reach
these frozen Windows lanes. The successor binding now names the actual committed
helper sources and validates the generated controllers in the runnable archive.

Needs TJ: None
