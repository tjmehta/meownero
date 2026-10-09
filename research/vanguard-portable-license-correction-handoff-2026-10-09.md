# TJS-1882 license correction for the existing review stage

F1 is corrected in three new archives. The prior candidate
`f1cdbae3ef5abbae8ce6af17b2518e6448db3f6b`, its export and v3 parts are
preserved. The full seven-target request remains OPEN. These bytes await
independent acceptance through reviewer `ec85048c-4b2b-4dcc-84e1-ff9bf87c9fe6`
and existing stage `82aa96f6-a7bf-422f-afe7-8d1cb3b2626a`.

| Target | Corrected archive | SHA256 |
| --- | --- | --- |
| Linux x64 | `build/tjs1882-c0cf-linux-x64-package02/meownero-vanguard-x86_64.tar.gz` | `2480d20dada4d963e2d302c0a2fdd81746cb7e3540d0a19a4f2254bc7ad252eb` |
| Linux ARM64 | `build/tjs1882-c0cf-linux-arm-package03/meownero-vanguard-aarch64.tar.gz` | `36f76bb6ae68d0e4574ccb57d9fb2dbfad38789e84d63ea0ad4a100f2835cc2f` |
| Apple Silicon macOS | `build/tjs1882-c0cf-macos-aarch64.tar.gz` | `70697083bec51c1af70de97b3cb8e02c9d6dcca78b4f4f8c500cb8f64bde2d80` |

The correction retains Mac Boost 1.91.0-1, OpenSSL 3.5.8, libsodium 1.0.18,
Unbound 1.25.2 and ZeroMQ 4.3.5 notices directly from source archives whose
SHA256 values match the pinned depends recipes. Packaging and future native
builds retain those inputs. All three packages also include Easylogging++
9.96.7's complete MIT text from upstream tag commit
`5181b4039c04697aac7eac0bde44352cd8901567`, the exact vendored copyright
header, and qrcodegen's inline MIT notice. Linux includes the full texts
referenced by the shipped packages' copyright files, taken from the exact
immutable builders. Their x64/ARM common-text hashes match.

`license-coverage.json` in each package binds component/version/source/text
hashes to the three actual linker commands and shipped runtime SONAMEs.
Unknown native libraries, absent mapped notices, missing referenced full
texts and changed depends archives stop packaging. Cargo.lock dependency
source notices have crate/version/source mappings. Four negative checks pass:

```sh
python3 -B vanguard/test-portable-licenses.py \
  --build build/tjs1882-linux64-attempt02 \
  --package build/tjs1882-c0cf-linux-x64-package02/meownero-vanguard-x86_64
```

## Exact behavior binding

`research/evidence/vanguard-portable-license-correction-tjs1882-2026-10-09/archive-audit.json`
checks every regular archive member and manifest hash. All existing files are
byte-identical except `release.json`; additions are notices/provenance and the
coverage manifest. The nine native programs, three starters, launchers,
guides and source locks are unchanged. This explicitly carries the prior
reviewer's Ubuntu x64, native ARM Linux and native Mac journey/control
witnesses forward by those hashes, as permitted by F1's acceptance condition.
Original receipts still bind original archive/manifest hashes.

Fresh corrected-byte evidence is in the same evidence directory:

- `debian-{check,journey,controls}.json`: corrected x64 archive passed the
  full native Debian 13.7 journey and all ten controls; owned cleanup passed.
  This is writer evidence. The prior reviewer's Debian controls remain an
  incomplete independent attempt, not an independent pass.
- `native-preflights.json`: corrected Mac and ARM Linux archives passed
  clean-extract file-set/hash/target checks and native program startup.
  ARM is Linux under Colima; Mac is native Mach-O.
- Per-target `*-license-coverage.json`, common-text retention receipts,
  `license-controls.json`, `delivery-parts.json` and `media-readback.json`.

The first ARM preflight fixture used a read-only system temp directory and a
non-executable temporary mount. Its refusals and exact owned cleanup remain
in remote `c0cf-preflight01` and `c0cf-preflight02/03/04.json`. The corrected
fixture provides a writable `/tmp` and executable task-owned extraction mount;
`c0cf-preflight05.json` passes. No starter gate was weakened.

The full machine matrix is
`research/vanguard-portable-license-correction-2026-10-09.json`.
Linux still requires glibc 2.38. Only Ubuntu 24.04 x64/ARM and Debian 13.7 x64
have journeys. Fedora/RHEL, Arch/openSUSE and Debian ARM remain UNTESTED.
Mac's declared minimum is 11.0; the runtime witness is 26.5.1. Its signatures
are ad hoc, with no Developer ID or notarization. Download quarantine and
older macOS versions remain unverified.

## Reproduction and handoff

The exact correction commit/tree is in the review request and
`build/tjs1882-c0cf-export02/candidate-identity.json`. The parent-readable
export includes all three intact archives, SHA256SUMS, TESTER.md, full
seven-target matrix, archive audit and delivery receipts.

To regenerate with fresh output names, use `vanguard/package-portable.py`
with the retained x64 build `build/tjs1882-linux64-attempt02`, the completed
public ARM import `build/tjs1882-c0cf-arm-import01`, or on build-mac the native
Mac build `~/Developer/tjs1882-a6abe690/mac-arm-attempt04`.
The ARM import includes the original programs/libraries/receipt and exact
public linker/header/Cargo inputs from `arm64-inspection04`. The Mac
packager requires native `otool`, `vtool` and `codesign`; Linux packaging
uses the existing Linux `readelf`. Compare output contents; tar metadata
and gzip creation times mean a rerun need not reproduce archive hashes.
The submitted exact archive bytes are retained.

The unchanged runtime wrappers can repeat journeys with the corrected hashes
above and fresh owned outputs. Debian uses immutable image
`sha256:9657bb863141f8d36723783c36d94348bf87a910f36372168cc061812383e3a4`.
Original reproduction guidance is in
`research/vanguard-portable-handoff-2026-10-09.md`; substitute these new
archives/hashes. Retained corrected ARM/Mac remote archives are
`c0cf-linux-arm-candidate.tar.gz` and
`c0cf-mac-arm-package01/meownero-vanguard-macos-aarch64.tar.gz`.

All 26 numbered parts are <=8 MiB and byte-verified through ordered full
reassembly and the installed gateway media loader. New container directories:

- `/home/node/.openclaw/media/tjs1882-c0cf566a-linux-x86_64-v4`
- `/home/node/.openclaw/media/tjs1882-c0cf566a-linux-aarch64-v4`
- `/home/node/.openclaw/media/tjs1882-c0cf566a-macos-aarch64-v4`

Each has PART-SHA256SUMS, whole SHA256SUMS and reassembly instructions.
Parent owns actual delivery after independent acceptance. No send, public
release, integration, new account, signing credential or shared settings
change occurred. Wallets, seeds and private runtime logs are unshared.

After this stage, the same platform writer owns authorized scoped compiler
installation, supported Windows x86/x64/ARM and Intel Mac cross-builds,
launcher work and target re-review. Missing native runners are separate
validation gaps. Cross output remains UNTESTED. Parent/board coordination
identifies native Windows and Intel Mac runners; BhaFresh's offered ARM
hardware is not an identified OS/model/access capability. No new paid
infrastructure is authorized. Lead `38e398e0` integrates only accepted exact
ancestry/tree after a fresh parent preservation check of the 1,163 original
entries. Historical TJS-1816/1856/1870 remain closed.

Needs TJ: None for this correction and resubmission.
