**Changed**

Adopted the [Apple Silicon independent acceptance](/TJS/issues/TJS-1882#document-macos-remapped-independent-review-2026-10-30), revision `cddb02d7-0648-4af2-8b76-9b75a6100ffc`, for exact archive `c02e656a`. Its native acceptance is reused without repeating the build or journey. The old Apple Silicon archive remains restricted.

Built a remapped Intel Mac successor using the same unchanged recipe at source `85a9f4394345e520c66e85c7151b0df75e7fe15c`. All 15 staged inputs match that candidate. No implementation, source pin, dependency pin, crypto, consensus or protocol change was made in this run. Writer: platform engineer `92a7b4f2-787b-4cbb-954e-46831397ab09`, run `681bd470-6c6a-4bba-881e-d7b1a13d7076`, TJS-1882.

- Archive: `meownero-vanguard-macos-x86_64-remapped-v1.tar.gz`, 64,389,695 bytes.
- SHA256: `54912e0c7f181f5cc100f17c66ced27c5ccb829fffae003b37dd9b91f50d4229`.
- Release manifest SHA256: `2afab24bc379d72ed1e9e86ff4838830dfa68cce47782038da1f5309e3bf9af9`.
- [Eight-part delivery index](/api/attachments/e5cb7c26-db6b-488a-be07-083807238e8d/content), with ordered lengths and hashes; [archive and part checksums](/api/attachments/edfcbd1c-114b-4422-a690-f0790035a105/content).

These are authenticated review attachments. The new Intel archive is not independently accepted or ready for group redistribution. Its embedded `BUILT_UNTESTED` status remains frozen. The adjacent checkpoint records subsequent translated evidence.

**Verified**

One cross-build on macOS 26.5.1 Apple Silicon completed in 744.122 seconds. All 14 command groups were reaped. Peak observed build resident memory was 1,575,223,296 bytes, below the existing four-GiB cap. Dependency jobs remained two and application jobs one, with phase and overall deadlines. Source came from exact Git objects and locked submodules; the cached upstream HEAD and Cargo.lock hash still match their pins afterward.

Packaging completed in 6.798 seconds. A separately fetched local copy passes the recursive private-home scan, unique safe regular-member check, zero numeric ownership and empty owner-name check, all 265 manifest hashes, x86_64 Mach-O headers for all three programs, and all 230 notice bindings across 92 components. The unsigned programs link only system frameworks and `/usr/lib` libraries. macOS 11 is the declared floor, not a tested runtime floor.

The original compiled dependency/build directory was renamed away before running the extracted archive. The native preflight correctly refused the Intel archive on the physical ARM64 host. The unchanged wrapper then passed with its explicit Rosetta flag:

- `PASS_TRANSLATED_ARCHIVE_JOURNEY` and `PASS_TRANSLATED_JOURNEY`.
- Received 5,000,000,000,000 atomic units, restored matching output/key-image state, opened the restored wallet with the CLI, then spent and received 2,000,000,000,000 atomic units. Both transactions are type 7 with CARROT outputs; their hashes are in `translated-journey.json`.
- All ten controls passed under translation: wrong pin/target, altered binary, extra private file, symlink, hardlink, collision preservation, busy lock, SIGTERM cleanup and deadline cleanup.
- Wrapper supervision took 44.834 seconds, with peak observed resident memory 806,371,328 bytes. All 21 remembered runtime processes were absent afterward. The separate audit also found the build and wrapper process IDs absent.

All eight uploaded parts, the delivery index and checksums were read back and matched exact local bytes. The bundled upload helper failed before its upload branch because its attachment-list JSON exceeded the operating-system argument limit at `jq --argjson`. A fresh read found no upload from that attempt. The documented API fallback then succeeded; no ambiguous upload was repeated.

Public evidence replaces private home prefixes only in recorded copies, with original/public hashes retained. Wallets, seeds, databases and raw private runtime logs are excluded. Evidence is in `research/evidence/vanguard-macos-intel-remap-tjs1882-2026-10-30/`. The [source and evidence packet](/api/attachments/ebbc567d-d458-40b1-8659-b362d39bb094/content), 252,172 bytes, SHA256 `2fc44eeaffdcae56a09b4fe677fbd6ce584a0c7da010c5038f3959935be11f18`, retains compiler and linker evidence plus fourteen exact source/guide/notice inputs. The unchanged historical tester profile is omitted because it contains private cache paths; its Git binding is supplied.

The exact temporary compiler tree was removed after fetching the archive and all 75 selected text evidence files. Shared lock inode `351059832` remained available. `ios cleanup complete Developer/tjs1882-681bd470` refused because the task is active. Managed scratch remains for the existing post-run cleanup owner; no alternate removal route was used.

All seven pre-existing modified/untracked leaf hashes remain unchanged. Only this run's new report and checkpoint evidence enter its commit.

**Unconfirmed/next**

Independent reviewer `ec85048c-4b2b-4dcc-84e1-ff9bf87c9fe6` should reassemble and verify the exact Intel archive, inspect its source/build bindings and notices, and independently reproduce the translated journey and ten controls. Use the unchanged `vanguard/run-portable-mac-check.py` with target `macos-x86_64`, the full archive hash above, a fresh owned output, and `--translated-macos-x86_64`. Return a hash-bound scoped verdict to this same writer on this same issue. This request cannot establish native Intel acceptance; the final release stage remains dormant.

Native Intel verification cannot run on the inspected hosts: build-mac is physically ARM64, this task host is Linux x64, and the repository has zero self-hosted runners. The existing authenticated Actions budget-stop evidence and lead spend hold remain applicable. Platform engineer owns checking a qualified Intel host or verified included-capacity reset before native execution. The prior Intel archive stays restricted; the new successor stays in scoped review.

Windows i686 and ARM64 still lack sufficient native evidence. The prepared Windows guest remains uninstalled, with zero allocated guest-disk blocks and no VM process. The existing entitlement question remains with studio lead; it affects only that guest installation. No new question or paid dispatch was made.

The seven-target release remains OPEN: four current redistributable native-accepted targets, five preserved historical behavioral acceptances, and three remaining current native gaps. Additional distro, older OS, fresh-installation and Gatekeeper coverage remain unverified. Accepted Windows bundle publication is carried forward; its group-message receipt remains unconfirmed. Parent owns accepted-only delivery, including the accepted Apple Silicon successor, and the actual group receipt. Source merge still waits for the final review stage.

Observed behavior: the already-supported Intel cross-build and existing Rosetta route can produce a private-path-free successor and a real translated payment witness without new spend. This does not qualify physical Intel hardware.

Needs TJ: None new.
