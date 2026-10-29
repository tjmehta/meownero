**Changed**

Prepared the Windows x64 provenance successor under the lead ruling
`lead-ruling-private-paths-2026-10-29`, revision
`d3ac81ac-f21c-4b9b-b112-17aa6f447bf4`, step 2. Run
`f591a0e4-38eb-4922-9a88-0ba9141c99ca`; issue TJS-1882.
Baseline `524ddbb98609f95bbec5486855e3f16ce912186c`.

The package **composes** the existing reviewed `portable_provenance.py` helper.
There is no product-code change. The new standalone evidence script reproduces
assembly and independently checks the exact permitted semantic changes. The
existing file manifest is **extended** with a new archive identity, the two
rewritten provenance identities and the transport hashes. The historical source,
archives, native evidence and all six pre-existing changed files stay intact.

Only BUILD.json and release.json change. TJ's home prefix becomes `/BUILD_HOME/`.
Both members identify their original member and archive hashes and explicitly
state `DISTRIBUTION_COPY_NOT_ORIGINAL_EXECUTION_BYTES`. The release file inventory
and build-receipt binding point to the new BUILD.json. The successor is not
claimed to be the archive that originally executed. Program, runtime controller,
launcher, source pins, compiler inventory, dependency and license bytes stay
identical; no crypto, consensus, runtime or signature behavior changes.

| Archive | Bytes | SHA256 |
| --- | ---: | --- |
| Original, retained private | 71355612 | `859d4644815b4c990cca093c6d74bb077e6ab74f267236ed84746d5b6cf690d0` |
| x64 sanitized v1 successor | 71356211 | `bc5829dadaae0a84271a7993d9440a6210353567a6cf9b7caddb2a545695c19e` |

Successor release.json SHA256:
`00d4aa4d1d8f91a4dd5eb9f596c1c27f4f4b0b37db5984fbe0bbcfc2361fdbab`.

**Verified**

The real archive check on Linux x64 / CPython3.14.7 passes in 11.128 seconds:
289 safe unique regular members, all CRCs, all 288 release file bindings, the
build-receipt binding, an actual clean extraction, and the independent semantic
comparison of both changes. All 287 other members retain their exact original
bytes, including all three PE32+ x64 programs, controllers and licenses. Nine
8MiB-or-smaller parts reassemble to the successor's exact bytes.

The same recursive guard that passes the successor rejects the actual original
archive with `PRIVATE_HOME_PREFIX_IN_DISTRIBUTABLE`. It scans ZIP metadata and
member content for both Linux/macOS home forms in UTF-8 and UTF-16. The available
two current credential values are absent. This is a bounded scan; it does not
establish absence of every private identifier or historical credential.
The actual helper refuses an existing destination and preserves the candidate.
Four focused provenance regressions pass (0 failures, 0 skips).

The unchanged packaged tester actually refuses Linux preflight with `wrong
operating system`, before Windows program execution. Owned extraction and lock
scratch are removed. No native runtime was claimed. This is an expected refusal,
not a native journey pass. No failed candidate or retry was needed.

The recorded native Server2025 x64 witness and original scoped acceptance remain
reusable for the byte-identical programs and runtime helpers: run37998310375,
original reviewer comment74d6566c-63f8-4361-bcb9-6640aa42c141. Full journey, ten
controls and owned cleanup were previously accepted. Their exact-byte premise
was freshly checked here. No expensive native rerun is justified by a provenance
rewrite alone, but the independent reviewer must accept this successor's new
archive and release bindings. Historical embedded BUILT_UNTESTED/UNTESTED fields
remain truthful and unchanged. Other Windows versions stay untested.

Reproduction from this task branch, with fresh output directories:

```text
python3 -B research/evidence/vanguard-windows-x64-successor-tjs1882-2026-10-29/verify-and-package.py build/tjs1882-3175-export04/meownero-vanguard-windows-x86_64.zip build/new-owned-x64-successor research/evidence/new-owned-x64-successor-check
python3 -B vanguard/test-portable-provenance.py
```

`check01/verification.json` includes all unchanged member and program hashes,
rewrite bindings, part hashes, source/helper/verifier identities and measured
results. `preservation.json` proves all six pre-existing file hashes. The fresh
seven-target manifest records the accepted test bundle and macOS redistribution
restriction without changing historical evidence.

**Unconfirmed/next**

Reviewer `ec85048c` owns scoped inspection of this exact successor, source/evidence
commit, original bytes and accepted original native witness. Independently verify
the two-member semantic correction, all unchanged bytes, privacy/known-bad scan,
new release/hash/part bindings and honest native scope. Save a scoped verdict
on this issue and return it `todo` to platform engineer `92a7b4f2`. Do not advance
the dormant whole-release stage or mark the seven-target issue done.

No native Windows journey was executed in this run. Fresh Windows execution is
NOT_RUN because there is no qualified current runtime; the separate build-mac guest
remains uninstalled until the existing entitlement question is answered. Parent
owns delivery of the already accepted i68635/ARM13 test-and-report bundle; the
ready handoff is saved as `windows-successor-ready-handoff-2026-10-29`, revision
`d2c51836-27c9-4545-b938-680e53d23d7b`, with an explicit lead mention. Delivery and
pickup are unconfirmed, not inferred from that saved handoff.

After scoped x64 review, the writer continues step3: macOS path-remapped rebuilds
and native re-acceptance. The old macOS programs contain build-home prefixes, so
neither archive may be newly published or redistributed. Apple Silicon has the
authorized build-mac build route; native Intel capability remains to be established
without spending on Actions. Five historical native acceptances remain preserved;
the requested seven-target outcome stays OPEN. Linux and the published Docker
leaf retain their accepted scope.

Needs TJ: None for this successor review. The existing Windows entitlement
question remains with the studio lead for the separate VM installation lane.
