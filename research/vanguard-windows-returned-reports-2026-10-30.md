# Returned Windows diagnostics-v2 reports

**Changed**

Consumed the three original-tester reports relayed in comment
`92646432-1823-4578-b8f0-b82d251115a0`, under owner authorization
`3A6B942CF66ABF3A50C6`. Run `7952e965-c0c9-436a-b25e-7ac18ad40dd4` remains
the sole platform-engineer writer, `92a7b4f2`. Reviewer `ec85048c` retains the
existing stage. This is an evidence-only continuation of accepted source/bundle
candidate `6836e5e1b14e66292cb0393b9f8ba0d1b8ab0dec`.

The [validation packet](evidence/vanguard-windows-returned-reports-tjs1882-2026-10-30/verification.json)
and [current matrix](evidence/vanguard-windows-returned-reports-tjs1882-2026-10-30/release-status.json)
supersede the missing-successor-report statements in the earlier Windows handoff.
Historical reports and verdicts remain intact. No program, helper, timeout,
guest setting, privilege or release artifact changed.

**Verified**

| Returned report | Observed scope | Controls and cleanup | Disposition for review |
| --- | --- | --- | --- |
| `arm-report-v2.zip`, source `<message-id>`, 19:06:13Z | Windows 11 build 26300, native ARM64 CPython 3.15.2 and ARM64 programs. Funding, payment/receive, restore, later spend and restored-wallet CLI open pass. | Nine controls completed. Only symlink-directory is NOT_EXECUTED, SYMLINK_PRIVILEGE_NOT_HELD, winerror 1314, without refused:true. Hardlink, collision, busy-lock, cancellation and deadline controls ran afterward. Controller controls phase exits 2. Journey and controller Jobs report zero active processes. | INCOMPLETE_NATIVE_ARCHIVE_CONTROLS. Native journey and harness continuation evidence only; no full ARM control acceptance. |
| `intel-report-v2.zip`, source `<message-id>`, 19:11:25Z | Windows 11 build 26200, AMD64 CPython 3.15.2, i686 executables under NATIVE_WINDOWS_WOW64. Full payment/receive, restore, later spend and CLI journey passes. | All ten controls pass, all controller phases exit 0 and are reaped, both Jobs report zero active processes. Native i686 exception probe also passes. | PASS_NATIVE_ARCHIVE_JOURNEY_AND_TEN_CONTROLS for i686 under WoW64, awaiting independent review. |
| `intel-report3-v2.zip`, source `<message-id>`, 19:30:04Z | Same reported OS/Python class and exact i686 programs under WoW64. Full journey passes again. | All ten controls pass, all phases exit 0 and are reaped, both Jobs report zero active processes. | A second successful i686/WoW64 run. The tester's "intel native64" shell description does not establish x64 executable coverage. Independent-host identity is not attested. |

Each journey records five units received, matching restoration, a later two-unit
spend, two type-7/CARROT payments and successful restored-wallet CLI open. Owned
cleanup rows all say removed:true. The stopped daemon/RPC children report exit 1;
this does not override their completed journey or reported Job cleanup. These
are tester-produced receipts inspected on Linux, not newly witnessed Windows
execution by this writer or an independent acceptance decision.

The three report ZIP hashes and sizes match the relay exactly. All five ARM and
six Intel members are expected public JSON files, with no duplicate names,
encrypted entries, directories, link entries, oversized members, duplicate JSON
keys or nonfinite values. No report member was extracted or executed. Exact
public fields, equality with the reviewed lane's pure public projectors, and a
bounded private-field/path/value scan pass. Every outer private_data_exported
flag is false. The reports contain public disposable transaction hashes and
amounts, not seeds, addresses, credentials, wallet databases or private logs.
This bounded check is not a universal secret detector.

Fresh hashing of the retained actual diagnostics-v2 archive confirms
164,120,029 bytes and SHA256
`bedd371bc042ec2b893e45693083eae64637ca1a1f496933f2f90a5bf6f38034`.
Embedded manifest SHA256 is
`46489d0ac6cea2e023506f4c893176d4d6d7de68580b19aa0c2c5d52bc364c65`.
For every report, controller, inputs, all frozen source bindings, nested archive,
release manifest, package helper and all three actual executable hashes match.
PE headers independently identify ARM64 0xaa64 and i686 0x14c. The parent summary
agrees with these direct observations. Exact digests are in verification.json.

| Intel funding operation | First report, seconds | Second report, seconds |
| --- | ---: | ---: |
| generateblocks | 71.229059 | 70.170385 |
| refresh | 2.743025 | 0.069358 |
| get_balance | 0.029417 | 0.032981 |

All six operation outcomes are PASS. The 90-second socket and 1200-second
journey budgets are unchanged; elapsed-at-start plus remaining-at-start matches
the same journey deadline. The controller remains the accepted, hash-identical
1500-second implementation. The original unclassified funding timeout did not
recur. Its root cause remains **UNKNOWN**. These observations do not establish
that instrumentation fixed an engine defect, that timing differences have a
known cause, or that every host will complete within the budget.

Reproduction, using the exact archive and these saved report copies:

```text
python3 -B research/evidence/vanguard-windows-returned-reports-tjs1882-2026-10-30/verify.py BUNDLE_ZIP research/evidence/vanguard-windows-returned-reports-tjs1882-2026-10-30 OUTPUT_JSON
```

The first execution passed all three report validations and 13 synthetic
negative checks. In-memory wrong-manifest, active-process and wrong-architecture
mutations are rejected for each report. False ARM full-pass and refused-skip
claims, and unknown Intel diagnostic fields, are also rejected. These checks
test the evidence inspector's sensitivity; they are not additional native runs.
The source/bundle regression suite and independent source acceptance are reused
because the source and artifact inputs did not change.

**Unconfirmed/next**

Reviewer `ec85048c` now owns scoped review of this exact packet through the
existing issue stage. Check the immutable ZIPs, bindings, actual outcomes,
privacy, cleanup and architecture limits. Retain source/package acceptance
`a22f00f6-e4e7-48d2-ad05-2a4d67114129`. Save a new scoped verdict and return
remaining release work to writer `92a7b4f2` through changes requested. Do not
approve the final whole-release stage or set the seven-target issue done.

Full ARM control acceptance cannot proceed from this report because the tester
could not create the symlink fixture under ordinary privileges. The reviewer
can accept the observed harness repair and native journey while retaining that
specific gap. No further BhaFresh rerun, elevation or policy change is requested.
An existing qualified native route that can already create this fixture would
be needed for full coverage; that later work remains with the platform engineer.

Standalone 32-bit Windows and native x64 executables remain untested by these
reports. The pre-existing x64 Server2025 acceptance is separate and unchanged.
Native Intel Mac remains untested; its Rosetta-only verdict stands. Existing
Mac/Linux acceptance, delivery and distro/ABI limits are reused unchanged. The
seven-target release remains **OPEN**. Parent owns any future group contact and
delivery; this run sent no tester reply, rerun request or publication.

The pre-existing current-evidence.md edit and six other changed leaves are
preserved. The existing issue release-handoff and this Windows matrix carry the
current update. No Windows process, VM, container, browser, simulator, remote
scratch, private extraction or persistent workload was started.

Learning delta, **observed behavior**: the native ARM successor reports honest
incomplete coverage and continues later controls. The two Intel runs complete
under the unchanged budgets; the earlier funding timeout's cause remains unknown.

Needs TJ: None.
