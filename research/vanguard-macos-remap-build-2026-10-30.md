**Changed**

Built a new native Apple Silicon archive after the lead restored build-mac's canonical
heavy-work lock. The successor has writer native PASS evidence and is ready for
scoped independent review. It is not independently accepted or approved for
redistribution. The seven-target release remains OPEN; no source was merged.

- Source candidate: `85a9f4394345e520c66e85c7151b0df75e7fe15c`.
- Review baseline: `fa7ac6ed418314fc6437354983c246756e740f57`; material correction
  commits `93bfc7c`, `5e50d75` and `85a9f43`. The intervening evidence/adoption
  commit `8cc4921` changes no additional implementation.
- Archive: `meownero-vanguard-macos-aarch64-remapped-v1.tar.gz`, 63,055,195 bytes.
- SHA256: `c02e656ae0fe0e8ffc774392dd535f12efec89b04a7fc400b4398124505eda00`.
- Embedded release manifest SHA256:
  `2cbefbae0203c3219ee16fb1941e7d819578de0b55c2582e6ef6ac403437408a`.
- [Delivery index](/api/attachments/c9712cc5-8387-4016-9293-599430127da9/content)
  binds eight ordered attachment parts, their lengths and hashes. All ten archive,
  index and checksum uploads were read back and matched exact local bytes.
- [Archive and part checksums](/api/attachments/af37c32e-1c62-48b7-a86c-0762223a39ed/content).
  This is authenticated board transport for review. Parent owns group delivery.

The prior correction remaps compiler paths in depends, CMake and Cargo, scans all
three programs, scans compressed tar contents and ownership/PAX metadata, and
clears tar owner names. The Docker build context and sparse Linux workflow include
the shared guard module. Those changes are still part of this scoped source review.

The first real rebuild revealed a remaining cause: depends embeds its configured
prefix in OpenSSL/Unbound literal strings, and OpenSSL records the complete compiler
flags, including the private path inside the old mapping option. A linked native
OpenSSL reproducer ran successfully but contained 11 private-prefix occurrences;
the distribution guard refused it. This behavior is consistent with the official
[OpenSSL version API](https://docs.openssl.org/3.5/man3/OpenSSL_version/) and the
[Clang file-prefix-map scope](https://clang.llvm.org/docs/ClangCommandLineReference.html).

Commit `85a9f43` extends the existing recipe at that shared point. It rejects build
output containing a private home prefix before lock acquisition or output creation,
and remaps the owned build root rather than embedding the user's home in compiler
flags. The successful build used a fresh mode-0700 task directory under the existing
owner-writable, non-symlink Homebrew cache parent, outside private homes. No dependency,
upstream patch, crypto, consensus, protocol or evidence gate changed.

**Verified**

The actual corrected entrypoint refused a home-directory output before creating
any output. The same native OpenSSL probe then linked and ran with zero private
home occurrences. All 19 static dependency archives passed the guard. The first
build was cancelled after the failing probe; its 628.91-second attempt, exact
owned cleanup and sanitized diagnostics remain recorded.

The corrected native build completed in 1,039.206 seconds with exit 0. All 13
command groups were reaped; peak observed resident memory was 1,991,081,984 bytes.
Existing two-job depends/one-job application limits, 4-GiB cap, phase and overall
deadlines and disabled core dumps were retained. The cache upstream HEAD and Cargo
lock hash still match the pins after execution:
`e151643c5269c83bf24a83b2548e2493876026b2` and
`6a8e9217b94169e26a8f595cb528d72c19dc2f5484e903c57328c594d62f8239`.
No upstream source patches were applied.

Packaging first failed because the staged source kit omitted three existing pinned
Easylogging license inputs. Restoring those exact tracked inputs fixed packaging;
no compilation or license gate was bypassed. The successful package took 6.863
seconds. The final source packet includes those three inputs and their bindings.

The exact archive passed native clean extraction and the full valueless journey on
macOS 26.5.1 Apple Silicon. The compiled dependency prefix was hidden during the
archive checks, so successful execution did not use the original build directory.
All three programs passed native version/signature checks; dynamic links name only
system frameworks and `/usr/lib` libraries. Signatures are ad hoc, without Developer
ID or notarization. The declared macOS 11 floor was not runtime-tested here.

- Receive 5: transaction
  `dc147a772c8816bd8c89718cea409f061023f5facc6285743b277a62e02ddce8`,
  5,000,000,000,000 atomic units, type 7 with CARROT outputs.
- Restore: matching wallet state; native wallet CLI opened the restored wallet.
- Subsequent spend 2: transaction
  `669b1b5e1bdc1eac61cedcaed9f57b40786914c43819ce4d23554da79500a5a2`,
  2,000,000,000,000 atomic units, type 7 with CARROT outputs.
- `PASS_NATIVE_ARCHIVE_JOURNEY`, `PASS_NATIVE_JOURNEY` and `PASS_REFUSALS`.
  All ten controls passed: wrong pin/target, changed binary, unlisted private file,
  symlink directory, hardlink, collision preservation, busy lock, SIGTERM cleanup
  and deadline cleanup. Both cleanup controls reaped their two owned processes.

The independently downloaded local copy contains 266 regular members, with all 265
internal file hashes matching the immutable release manifest. The recursive private
home scan passes; tar uid/gid are zero and user/group names empty. All three binaries
have arm64 Mach-O headers. Linked dependency/license coverage passes, including all
79 external locked Rust packages. The manifest retains its original `BUILT_UNTESTED`
status; later native PASS evidence is adjacent and does not alter the archive.

Reused 115 local checks from the prior checkpoint after verifying their source and
evidence bindings: 5 provenance, 5 Windows bundle, 24 Docker lifecycle/context and
81 linker/privacy fixtures. The changed Mac recipe is excluded from that reuse
claim and was exercised by the real refusal, probe, build, package and native
journey above. The prior unused fixture invocation errors remain failures, not
passes. See `reused-checks.json` for the precise 27-of-28 unchanged binding scope.

Native build/journey processes are absent. The canonical lock remains inode
351059832, uid 501, mode 0600 and available. After fetching the archive and 80
sanitized public evidence files, the exact temporary build outside Developer was
removed. `ios cleanup complete Developer/tjs1882-9ea6fdb5` refused because the task
is active. Managed scratch and private diagnostics remain for the existing post-run
cleanup owner; no workaround removed managed or unowned work.

Six of seven pre-existing dirty/untracked file hashes remain unchanged. One local
Python inspection refreshed `vanguard/__pycache__/portable_provenance.cpython-314.pyc`.
Its original bytes were not backed up, so exact preservation of that generated
cache cannot be claimed. No source/evidence file was overwritten; the refreshed
cache is uncommitted. Subsequent inspections disable bytecode writes. Both the
initial seven-file check and final differing hashes are recorded.

Evidence directory:
`research/evidence/vanguard-macos-remap-build-tjs1882-2026-10-30/`.
The downloadable source/evidence packet contains the exact correction sources,
baseline diff, first-attempt failure evidence, compiler/link receipts, native
results, controls, release/license manifests, transport bindings and current
seven-target checkpoint. Sanitized copies carry original/public hashes and are
identified as copies; private wallets, seeds, raw native logs and credentials are
excluded. The frozen source packet omits the unchanged historical tester profile
because it contains an old private cache path; its Git binding is supplied. Use
the existing exact checkout for the reviewer command.

**Unconfirmed/next**

Assign scoped review on this same issue to independent reviewer
`ec85048c-4b2b-4dcc-84e1-ff9bf87c9fe6` after the writer run settles. Review the
material source delta from `fa7ac6e` through `85a9f43`, including shared guard
callers, tar metadata, dependency-string correction, failure controls and license
inputs. Reassemble the eight parts into a fresh file and verify the full archive
hash before any execution. Independently reproduce the exact native archive
journey and ten controls on a qualified Apple Silicon host:

```sh
python3 -B vanguard/run-portable-mac-check.py \
  --archive <reassembled-archive> \
  --sha256 c02e656ae0fe0e8ffc774392dd535f12efec89b04a7fc400b4398124505eda00 \
  --target macos-aarch64 --out <fresh-owned-native-output>
```

Use the existing shared lock and resource limits. Bind the verdict to source,
archive and release-manifest hashes, then return the same issue to writer
`92a7b4f2-787b-4cbb-954e-46831397ab09` with findings or scoped acceptance. The
attached final release stage `82aa96f6-a7bf-422f-afe7-8d1cb3b2626a` remains dormant.
This scoped review does not approve the entire branch or seven-target release.

Both old Mac archives remain restricted. Intel still needs a qualified native
Intel route for a successor; Actions spend is held. Windows i686 and ARM64 still
lack sufficient native acceptance. Historical five-target behavioral acceptances,
accepted Linux archives, Windows x64 successor and the separate Docker leaf remain
preserved. Other OS versions/distributions, Gatekeeper quarantine behavior and a
fresh OS installation were not tested by this run.

Adopted the lead's saved anonymous exact-byte publication evidence for the untested
Windows test-and-report bundle, rather than repeating the download. It is live on
[meownero.com/downloads](https://meownero.com/downloads), deployment
`dpl_Gc964cpaKwooYKsT964kaz9n2kpk`, source `f7e3aae`, 164,091,051 bytes, SHA256
`eb6b76d387f26e5b4a9f849d8e7de2fbf11e9ce06a221cb16b3f5dbd0502da46`.
Evidence: [TJS-3090 publication document](/TJS/issues/TJS-3090#document-native-publication-2026-10-30),
revision `4ac5b33b-34a0-4da3-b8ac-54a73382657f`. This does not establish native
Windows execution. Parent owns the group tester message; its receipt remains
unconfirmed. No new entitlement question, paid dispatch, publication, group message,
VM/simulator use, source push or merge occurred here.

Needs TJ: None new. The existing Windows entitlement question remains with the
studio lead and gates only the build-mac Windows guest installation.
