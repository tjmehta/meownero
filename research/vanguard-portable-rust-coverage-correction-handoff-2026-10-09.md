# TJS-1882 Rust coverage correction

F2 is corrected for the existing ec85048c review stage. The full seven-target
request remains OPEN. Prior f1cdbae3/v3 and 5b55804/v4 artifacts are preserved
and have no acceptance or delivery authority.

The guard derives the required set from the exact SHA256-pinned Cargo.lock,
not from discovered caches. All 79 external crates must have a unique
name/version/source mapping and every retained per-crate license text must
match the corresponding input byte hash. This conservative set includes
build and target-only dependencies. The one local FFI wrapper is covered by
the upstream Monero license. Both registry/git source trees and both notice
trees are required. Missing trees, crates or even one dual-license text stop
packaging; five real CLI refusal cases verify that no archive is emitted.
The existing four native controls also pass, for 12 checks in total.

| Target | Corrected exact archive | SHA256 |
| --- | --- | --- |
| linux-x86_64 | `build/tjs1882-cd53-linux-x64-package01/meownero-vanguard-x86_64.tar.gz` | `a423cd3bf375ba6467cf48b07cc29f452777d302a161fca9edc44c7f778cfbd2` |
| linux-aarch64 | `build/tjs1882-cd53-linux-arm-package01/meownero-vanguard-aarch64.tar.gz` | `20e0d0f36d2ab80587b55a801a431e94b66a6913b1c5aac22f73b0b04a75d57c` |
| macos-aarch64 | `build/tjs1882-cd53-macos-aarch64.tar.gz` | `12c257e6f9be0aa054bffc48ff6e4f93fb04e14dcb9d453f9f02060a93b5ab66` |

The evidence directory is
`research/evidence/vanguard-portable-rust-coverage-tjs1882-2026-10-09/`.
Its archive audit validates every member against release.json and every
coverage text hash. Only license-coverage.json and release.json changed.
Every program, bundled library, starter, launcher, guide, source lock and
notice text is byte-identical to 5b55804. Per-file old/new hashes bind the
prior reviewer's Ubuntu x64, Linux ARM and native Mac runtime evidence.
Original runtime witnesses still bind their original archive hashes.

Fresh Debian 13 x64 clean-extract payment/receive/restore/later-spend and all
ten runtime controls pass on the corrected archive, within the unchanged
2-GiB cap. Exact owned container removal passes. New ARM Linux and native
Mac clean-extract preflights pass, with exact owned container cleanup for
ARM. These are writer checks; independent acceptance remains pending.
The full negative helper uses the complete x64 build. The notice-only ARM
import lacks depends recipe boost.mk; its separate 79-crate guard and real
packager pass, but it cannot supply that full helper's native recipe fixture.

Reproduce the complete controls with:

```sh
python3 -B vanguard/test-portable-licenses.py \
  --build build/tjs1882-linux64-attempt02 \
  --package build/tjs1882-cd53-linux-x64-package01/meownero-vanguard-x86_64
```

The parent-readable export is `build/tjs1882-cd53-export01`, containing all
three exact archives, SHA256SUMS, TESTER.md, the full seven-target matrix,
identity and evidence. New v5 parts are at most 8 MiB, with ordered whole
reassembly and actual installed gateway media-loader hash readback.
Part manifests and reassembly instructions accompany them. Parent owns
actual WhatsApp delivery after independent acceptance.

Linux still requires glibc 2.38; Debian12/Ubuntu22.04 and other distro
witnesses remain open. Mac has ad hoc signatures, minOS11.0, and a runtime
witness on26.5.1; quarantine and older releases remain unverified.
Windows x86/x64/ARM64 and Intel Mac builds and native validation stay open.
Native runner gaps do not block safe cross production. The parent preflight
was recovered from the existing gateway and independently checksum-verified
as f3f25c38fea7a53e20b8e113ef823d382ecd8b40ba2057352d8219a4cb60a205.
Its unchanged upstream route references match; mac-builder and packager
references predate the F1/F2 corrections. Rosetta is already installed on
build-mac, with pkgutil witness retained separately; it cannot establish Intel CPU
coverage. Keep this source candidate frozen during review and put any next
build/toolchain work in disjoint task-owned output paths.

Return review findings and subsequent compiler/build/launcher work to the
stored writer 92a7b4f2 through stage82aa96f6-a7bf-422f-afe7-8d1cb3b2626a.
Lead38e398e0 integrates only accepted exact ancestry/tree after parent's
fresh preservation comparison of the 1,163 original entries. This writer
never modified the primary checkout. Historical accepted tasks stay closed.

Observed behavior: optional Rust cache discovery allowed a false PASS;
required coverage must be derived independently from the pinned lockfile.

Needs TJ: None.
