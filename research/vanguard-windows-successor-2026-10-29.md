**Changed**

Corrected the Windows bundle's F1 privacy finding in TJS-1882, run
`62675b05-eb9f-4dc3-9b32-d15d66de5977`, under the lead ruling
`lead-ruling-private-paths-2026-10-29`, revision
`d3ac81ac-f21c-4b9b-b112-17aa6f447bf4`.

Implementation commit: `c5eecb4f9b4a349991acf47145a62627cfa8759d`.
Baseline: `7361d12059ae8a9d4236f2519859a7096623aec0`.
Branch: `TJS-1882-meownero-vanguard-cross-platform-tester-binaries-and-verified-group-download-packages`.

The assembler now **extends** the existing frozen-input assembly with sanitized
successors, new names and hashes, a documented `/BUILD_HOME/` placeholder and a
recursive refusal scan. It **adds** a shared provenance helper and focused
regression checks. The Windows build recorder **removes** home prefixes from its
saved receipt copy while leaving actual command arguments unchanged. The guide
explains the successor provenance and keeps the BUILT_UNTESTED status explicit.
No program, runtime controller, license or cryptographic behavior changes.

The seven changed Intel members are BUILD.json, release.json, cached build
receipt, pre-probe build receipt, exception input manifest, cross-probe script
and cross-probe receipt. ARM changes only BUILD.json and release.json. Every
rewritten member records its original member and archive hashes and states
`DISTRIBUTION_COPY_NOT_ORIGINAL_EXECUTION_BYTES`. Rebound JSON fields record both
their old and successor hashes. Original intermediate tar hashes remain
historical execution evidence; no redacted intermediate tar or rebuilt program
is claimed. Original archives remain private and unchanged.

The new bindings cover the Intel cached/pre-probe/input/script/cross/build/release
chain, both release file inventories, the controller input manifests, archive
sizes and hashes, transport parts and outer bundle. ARM13's prior compiled-artifact
verdict carries forward only for unchanged program bytes. Archive and bundle
acceptance require the scoped independent review.

| Candidate | Bytes | SHA256 |
| --- | ---: | --- |
| Windows test bundle, sanitized v1 | 164,091,051 | `eb6b76d387f26e5b4a9f849d8e7de2fbf11e9ce06a221cb16b3f5dbd0502da46` |
| i68635 sanitized v1 | 97,175,736 | `b9bc676870a506d9bc5cc0ee3c478aba1789ee60726046064c417fc907da97ca` |
| ARM13 sanitized v1 | 66,636,938 | `eed161eff71038e0ca37034e195d4943870c4c10cca6fd07c52b7311c1dc8484` |

**Verified**

Fresh verification used CPython 3.14.7 on Linux x86_64 and the final ZIP extracted
into owned scratch. The [verification JSON](evidence/vanguard-windows-successor-tjs1882-2026-10-29/verification.json)
and [standalone verifier](evidence/vanguard-windows-successor-tjs1882-2026-10-29/verify-successor.py)
record the exact candidate and checks.

- The assembler's actual pre-output guard refuses the real rejected bundle,
  SHA256 `69b182c744e3e7eb00dcfb0b8e3fe6770f7b23441dea1df7408e9c695aa1064b`,
  with `PRIVATE_HOME_PREFIX_IN_DISTRIBUTABLE`. This is the known-bad control.
- The successor scan passes across the complete ZIP, outer files and nested
  member contents. No private home prefix or either of the two available
  current credential values was found. This is a scoped scan, not proof about
  every past credential or every possible private identifier.
- All 594 members outside the nine declared provenance changes are byte-identical
  to their originals: 301 Intel and 293 ARM. This includes every program, package
  runtime helper and license. Both outer runtime controllers, the wrapper and
  Windows launcher also retain their exact original bytes.
- All nested CRC checks, unique safe regular-member checks, release file hashes,
  transitive Intel bindings, input bindings and recomputed archive part hashes
  pass. All 13 outer file hashes and 14 outer ZIP members pass.
- Both real packaged prepare-only commands exit 0 with
  `PASS_INPUT_BYTES_ONLY_NATIVE_EXECUTION_UNTESTED`. Each unchanged controller
  reconstructs its successor archive and checks its inputs, manifest and helpers.
- A normal Linux invocation exits 1 with `NOT_RUN` and
  `REQUIRES_WINDOWS_CPYTHON`. A modified Intel input exits 1 with
  `BUNDLE_HASH_MISMATCH`; the original bytes were restored. GitHub run/commit
  sentinels are absent from the exported reports.
- Four provenance regressions and five existing bundle regressions pass.
  Coverage includes nested compressed/UTF-16 paths, public-path false positives,
  unchanged execution arguments, preserved programs/controllers/licenses,
  truthful historical hashes, the dependency chain, collisions and refusal of
  an unexpected leak in a program. The real assembler also refuses an existing
  output directory and preserves the candidate ZIP.
- The Windows builder imports its new dependency and its CLI help works.
  No new cross-compilation is claimed. Source review confirms the recorder calls
  the tested helper before saving BUILD.json's source receipt.

The first verifier attempt encountered an output-parser error after the Intel
byte check passed. It expected a different report label. The unchanged candidate
was retested after correcting only the evidence script. The first report and
failure record are retained. A later artifact-helper failure occurred before
part 11 uploaded: passing this issue's growing attachment list to jq exceeded
the OS argument limit. Parts 1–10 were retained; the documented direct API route
was used for the remaining artifacts. These were verification/upload-tool
failures, not Windows program failures.

Reproduction, using new output directories:

```text
python3 -B vanguard/test-portable-provenance.py
python3 -B vanguard/test-windows-test-bundle.py
python3 -B vanguard/make-windows-test-bundle.py --out build/new-owned-successor
python3 -B research/evidence/vanguard-windows-successor-tjs1882-2026-10-29/verify-successor.py FINAL_ZIP ORIGINAL_ZIP NEW_EVIDENCE_DIRECTORY
```

The original ZIP is retained at
`build/tjs1882-c738-windows-test-bundle03/meownero-windows-test.zip`.
The reviewed successor candidate is retained under
`build/tjs1882-run62675-windows-successor-final/`.
An evidence-only HEAD change can change a new outer bundle's source-revision
field. Reassemble the saved transport parts for the exact candidate above.
Python's [ZIP contract](https://docs.python.org/3.14/library/zipfile.html#zipfile.ZipFile.writestr)
supports retaining member metadata while replacing selected member contents;
the byte comparisons above establish the actual preservation result.

**Unconfirmed/next**

Reviewer `ec85048c` owns the next scoped review of this exact successor and F1
correction. Inspect the real source diff, original hashes, changed provenance,
binding chain and final downloadable parts, then reproduce the applicable
portable checks. Return one scoped verdict on this issue and reassign it to
platform engineer `92a7b4f2`. Do not advance the dormant whole-release stage or
mark the seven-target issue done. Preserve the five historical native target
acceptances and the attached reviewer stage.

Windows launcher execution, IsWow64Process2, both native journeys, ten native
controls and Job/handle cleanup remain NOT_RUN because this run has no qualified
Windows runtime. The build-mac guest is still uninstalled under the separate existing
Windows entitlement question. The studio lead owns that delivered question; it
does not prevent this scoped review. A qualified Windows tester must run the
reviewed successor before corresponding native acceptance can be claimed.

After this review, the writer owns the ready handoff to TJS-3090. Its parent owns
group wording and delivery. This run sends no group message. Next in the lead's
order are a provenance-only Windows x64 successor with its own review, then
macOS path-remapped rebuilds and native re-acceptance. No new publication or
redistribution of either old macOS archive is allowed. Linux and the website
Docker ZIP retain their existing accepted state.

All six pre-existing regular-file hashes are preserved, including the tracked
evidence edit and bytecode cache. No primary-checkout edit, merge, source push,
provider job, Windows installation or remote resource claim occurred. Owned
diagnostic extraction/assembly trees are removed after saving their evidence;
the exact final ZIP and transport parts stay available for review.

Observed behavior: correcting only the six private-path files would leave stale
hashes in the Intel provenance chain. A valid successor also changes its input
manifest and both release manifests, while preserving historical execution
identities explicitly.

Needs TJ: The existing Windows entitlement answer through the studio lead is
needed only before installing or using the build-mac Windows guest. No new ask.
