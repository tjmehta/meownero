**Changed**

Adopted the [independent returned-report verdict](/TJS/issues/TJS-1882#document-windows-returned-independent-review-2026-10-30), revision `04f52059-7791-464a-a5a7-a0c82d79956c`, for evidence candidate `8d0570d96f75488753ec124f0a4b9f50ff63c906`. Accepted source/bundle candidate `6836e5e1b14e66292cb0393b9f8ba0d1b8ab0dec` and source/bundle review `a22f00f6-e4e7-48d2-ad05-2a4d67114129` remain applicable.

The [new seven-target matrix](evidence/vanguard-windows-review-adoption-tjs1882-2026-10-30/seven-target-status.json) replaces the pending-review accounting in the preceding returned-report supplement. Earlier evidence and embedded archive statuses remain intact. This adoption changes research status only. No program, helper, artifact, budget or guest setting changed.

Run `d7b40435-c9c9-4d69-960d-2f0a3873b2ea`, writer `92a7b4f2-787b-4cbb-954e-46831397ab09`. The existing reviewer is `ec85048c-4b2b-4dcc-84e1-ff9bf87c9fe6`. Stage `82aa96f6-a7bf-422f-afe7-8d1cb3b2626a` retains `changes_requested` for the unfinished release.

**Verified**

| Target | Adopted acceptance | Remaining limit |
| --- | --- | --- |
| Windows i686 | Both returned reports pass the recorded i686/WoW64 wallet journey, all ten controls and reported cleanup. Independent scoped evidence acceptance is complete. | Standalone 32-bit Windows remains untested. Both reports use the same i686 executable hashes. Host independence is not attested. |
| Windows ARM64 | Native ARM64 journey, nine controls and reported cleanup accepted within that scope. Later controls ran after the symlink fixture failed. | Symlink-directory is NOT_EXECUTED, SYMLINK_PRIVILEGE_NOT_HELD, WinError 1314, without refused:true. Controls exit 2; aggregate INCOMPLETE_NATIVE_ARCHIVE_CONTROLS. Full control acceptance is withheld. |
| Windows x64 | Prior sanitized successor and historical native Server2025 acceptance retained. | Returned Intel reports add no x64 executable coverage. Other Windows versions remain untested. |
| macOS Apple Silicon | Remapped native acceptance and completed parent delivery retained. | One macOS 26.5.1 host; earlier OS, fresh-install and Gatekeeper limits remain. Ad hoc signed, not notarized. |
| macOS Intel | Remapped Rosetta acceptance retained. | Native Intel execution and independent acceptance remain unconfirmed. |
| Linux ARM64 | Exact ARM39 acceptance and completed delivery retained. | Recorded Ubuntu 22/24 and Debian 12 container-userland limits remain. |
| Linux x64 | Exact Linux38 acceptance and completed delivery retained. | Ubuntu 22 Docker userland on a native Ubuntu 24 kernel. Other distribution and ABI claims remain unconfirmed. |

Fresh authenticated download of the [reviewer packet](/api/attachments/e4757ae4-eb43-42d7-bf0d-403389ba3349/content) matches 72,846 bytes and SHA256 `2c91b8fcfc75f364a9c2f6f4ff2ce5696b960c4432810444c5a11f572d823de5`. All thirteen safe outer members and twelve bindings pass. The embedded submitted packet has thirteen safe members and twelve bindings. Its ten research files match the reviewed Git objects and current files. The reviewer replay receipt equals the committed validation receipt. [Adoption verification](evidence/vanguard-windows-review-adoption-tjs1882-2026-10-30/verification.json) records these checks.

The reviewer's 601 nested file hashes, six PE headers, three report validations and thirteen negative rejections are reused from that exact packet. Those checks and the accepted source regressions were not repeated. The reports, source and artifacts did not change. This run inspected evidence on Linux and performed no Windows execution.

The two Intel funding runs completed under unchanged socket 90, journey 1200 and controller 1500 second budgets. The original funding timeout did not recur. Its root cause remains UNKNOWN. No engine-bug fix is established. Optional native_cli_event NOT_REQUESTED is informational; the recorded restored-wallet CLI journey passes separately. Cleanup means the tester receipts report zero active owned processes, not a fresh global process check by this writer.

**Unconfirmed/next**

Full ARM control acceptance needs native symlink-directory refusal evidence on an already-permitted, qualified ARM64 route. Fresh checks at about 20:01Z found zero registered repository runners, zero active or queued runs, Linux x64 without KVM or either inspected QEMU launcher, and build-mac still ARM64 macOS 26.5.1. These checked routes supply no current Windows runtime or native Intel Mac. [Route evidence](evidence/vanguard-windows-review-adoption-tjs1882-2026-10-30/native-route-check.json) records the observations and limits.

The existing [Windows guest lane](/TJS/issues/TJS-3090) still records no license found and the prior purchase question unanswered. The studio lead owns that existing answer. It affects guest installation only; a license answer would not establish native symlink capability. No new purchase, elevation, policy change or duplicate question is requested. The October 29 Actions budget-stop evidence and five-attempt monitor limit remain in force. New included compute or storage availability has not been established.

Platform engineer retains the next execution. When an existing qualified native route is supplied, or included compute and exact-job storage are verified, qualify the architecture and required fixture capability before running the accepted artifact. Then return new evidence through the same independent-review stage. Native Intel Mac still needs the exact remapped archive's full journey and ten controls. Standalone 32-bit Windows and the recorded common-distribution/current-archive requirements remain unconfirmed. These are runtime and coverage gaps, not new source defects.

The seven-target release remains OPEN. No whole-release approval, new publication, source integration or group send occurred. Completed Mac/Linux delivery stays closed. No further BhaFresh rerun or group reply is needed; parent owns future contact and delivery. All seven pre-existing changed leaves retain their bytes. No persistent workload or remote scratch was created.

Learning delta, **observed behavior**: independent review accepts the returned i686/WoW64 evidence and the partial ARM evidence. It does not close the ARM symlink gap or explain the earlier Intel timeout.

Needs TJ: None new. The existing guest-license question remains with the studio lead and affects that lane only.
