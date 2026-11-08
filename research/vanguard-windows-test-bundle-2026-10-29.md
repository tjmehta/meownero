**Changed**

Prepared a private Windows test-and-report candidate for TJS-1882, run
`c738785b-cb43-4118-9742-ab060169a35f`, following lead comment `340593ac`.
Implementation revision: `4564531f143e40ee6f5efdc3aee7380de3f0d0da`.
The VM entitlement stop remains separate. No Windows installation, VM start,
Actions dispatch, purchase, public publication or group send occurred.

The bundle ZIP is 163,986,069 bytes, SHA256
`69b182c744e3e7eb00dcfb0b8e3fe6770f7b23441dea1df7408e9c695aa1064b`.
It contains the exact i68635 and ARM13 archives, unchanged controllers, a Python
entrypoint, a small Windows launcher, short instructions and a file manifest.
The 20 private review parts have separate hashes in
[parts.json](evidence/vanguard-windows-test-bundle-tjs1882-2026-10-29/parts.json).
These parts are an internal transport for one ZIP; a tester should receive the
reassembled ZIP after review and the delivery conflict below is resolved.

Before/after: baseline `58d00c3e` had frozen Windows artifacts and CI controllers,
but no group tester report entrypoint. The candidate **composes** these existing
controllers and **adds** only a portable assembler, launcher, report exporter and
focused packaging checks. It changes no program, crypto, consensus or controller
code. The i686 source manifest **removes** three unused host/Mac source bindings:
`vanguard/tester-profile.json`, `vanguard/tester.py` and
`vanguard/run-portable-mac-check.py`. Its original input SHA256 is
`a49c9c833e624c6e8abce07224f715ae6d40b345f18554b77164f4e4e7c77f2f`.
The adapted input and removed bindings are explicit in `bundle.json`.
The Windows branch calls the archive's tester, the retained journey diagnostic
and refusal helper. The omitted inputs are not callers on that branch.

Native machine selection uses IsWow64Process2: native x64 CPython selects i68635
on WoW64; native ARM64 CPython selects ARM13. Emulated Python and a standalone
32-bit OS are refused. The unchanged ARM controller retains its Python/PE,
native-machine, ARMv8 crypto and program-hash guards. A byte-only mode is labelled
separately. The wrapper does not expose a runtime architecture override.

The controller executes in the wrapper process so its existing Windows console,
Job ownership, deadlines, phase ordering and finalizers still apply. It writes
into a new UUID directory. Only the controller's five fixed public JSON filenames
enter `report.zip`; raw logs, wallets and unlisted files stay local. The wrapper
removes GitHub run/commit environment fields during the controller call and
restores them afterward. A failed test produces an honest report. Kernel Job
cleanup and actual Windows launcher behavior still need a Windows witness.

**Verified**

Fresh checks use the final ZIP, extracted into owned scratch, with
Python 3.14.7 on Linux x86_64. See
[bundle-verification.json](evidence/vanguard-windows-test-bundle-tjs1882-2026-10-29/bundle-verification.json).

- All 14 outer ZIP members are unique regular files with safe paths; ZIP CRC
  verification and all 13 file-manifest hashes pass.
- Both original archives, both input bindings and both controller hashes match.
  The Intel controller remains `0046f001...e70d9`; ARM remains
  `7a04b1ff...c382`. Original archives remain
  `3a0a34d8...6e745` and `fff26ea9...ae15d` respectively.
- Running the real packaged entrypoint in prepare-only mode passes each exact
  controller's reconstruction, archive, helper and manifest checks. Both report
  `PASS_INPUT_BYTES_ONLY_NATIVE_EXECUTION_UNTESTED`.
- A normal Linux invocation exits 1 and exports `NOT_RUN` with
  `REQUIRES_WINDOWS_CPYTHON`. No Windows program starts.
- Appending one space to the Intel input is a deliberate negative control. The
  actual entrypoint exits 1 with `BUNDLE_HASH_MISMATCH`. The input is restored.
- Five focused tests pass: architecture selection/emulation refusal; exclusion
  of wallet/log sentinel files; preservation of an existing report; refusal of
  symlink and hardlink public receipts; and manifest traversal refusal. These
  are portable packaging checks, not Win32 execution evidence.
- Scanning all final distributable files, including nested archive members,
  finds none of the available current run/GitHub credential values. The old
  host profile and device inventory are absent. Six historical build-path
  findings remain inside the unchanged archives, as listed below.

Reproduction uses the existing retained source/part carriers:

```text
python3 -B vanguard/test-windows-test-bundle.py
python3 -B vanguard/make-windows-test-bundle.py --out build/new-owned-bundle
python3 -B build/new-owned-bundle/meownero-windows-test/windows-test-bundle.py --prepare-only --target windows-i686
python3 -B build/new-owned-bundle/meownero-windows-test/windows-test-bundle.py --prepare-only --target windows-aarch64
```

The assembler refuses collisions, reconstructs the reviewed archives from
hash-bound parts and uses fixed ZIP timestamps. The final ZIP binds the
implementation revision above. Later evidence commits do not alter that code.
The baseline tracked evidence edit and all pre-existing untracked entries are
preserved. No shared host, device, browser, container or remote scratch is used.

Primary contracts consulted: [Python 3.13 runpy.run_path](https://docs.python.org/3.13/library/runpy.html#runpy.run_path)
and [Microsoft IsWow64Process2](https://learn.microsoft.com/en-us/windows/win32/api/wow64apiset/nf-wow64apiset-iswow64process2).
The first establishes in-process script execution; the second provides the
process/native architecture distinction. Their documented semantics do not
substitute for a native Windows witness.

**Unconfirmed/next**

Group delivery cannot yet proceed. The brief requires both the exact reviewed
archives and no private host data. The retained archives include historical home
directory paths in six provenance members: ARM `BUILD.json`; Intel `BUILD.json`,
`cached-build-receipt.json`, `i686-exception-probe-cross-receipt.json`,
`i686-exception-probe-cross.py` and `pre-exception-probe-build-receipt.json`.
The exact member list is in the verification JSON. No path values are repeated
here. Silently redacting them would change the required archive identity.

Existing independent reviewer `ec85048c` should inspect the exact source and
bundle, reproduce the portable checks, assess this delivery-contract conflict
and give an actionable scoped verdict. A likely remedy is a sanitized successor
with unchanged program bytes and refreshed manifest/input/archive bindings, but
that differs from the lead's exact-archive brief and needs a lead scope ruling
before implementation. Keep this candidate private meanwhile. This is a scoped
bundle review, not approval of the seven-target release. Return findings and
the existing issue to platform engineer `92a7b4f2`; preserve the attached review
stage and all five historical native target acceptances.

The launcher, IsWow64Process2 call, native controller journeys, all ten controls
and Job/handle cleanup are NOT_RUN on Windows in this run because no qualified
Windows runtime is available here. The prepared build-mac ARM64 guest remains
uninstalled at the separate entitlement stop. The studio lead already delivered
that question. No new Windows or Actions spending authority is inferred.

After review and any required correction, the platform engineer must post the
requested ready handoff on TJS-3090. That ready handoff has not been sent because
review and the delivery-contract decision remain unresolved. The parent owns
group wording and sending.

**Observed behavior:** frozen i686 CI bindings included an unused host profile.
Removing only those unused host/Mac bindings preserves the executable Windows
controller while preventing that profile from entering the tester bundle.
Archive provenance paths are a separate, still-open delivery concern.

Needs TJ: The existing Windows entitlement answer through the studio lead,
affecting only the build-mac VM lane. No new ask in this run.
