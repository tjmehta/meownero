# Vanguard tester review corrections

Writer corrections and final native rehearsal: PASS. Acceptance of this corrected
candidate, accepted-only integration and parent verification: NOT_RUN. This is
the writer's resubmission to the existing ec85048c review stage, not task completion.
The original writer report and reviewer receipts remain preserved.

## Changed

F1: each invocation gets random container names. Docker creation writes a cidfile
inside its fresh owned output. Before start or destructive cleanup, inspection
must match that exact ID, the pinned image and this invocation's label. Cleanup
never falls back to a name. A pre-existing stopped-container collision refuses
the run and leaves the fixture unchanged in the before/after inspection.

F2: stop, final inspection, removal and final ID listing each have independent
deadlines and error capture. A stop or inspection timeout still attempts removal.
The original workload exception propagates; cleanup outcomes remain in the
receipt. Unknown presence stays unknown, and any cleanup error fails the gate.
Only this invocation's attach client can be killed while reaping that client.

F3: exported JSON must match a frozen public field/type schema. It covers nested
objects, arrays and JSON encoded inside native RPC responses, and never learns
fields from an export input. Unknown fields refuse export before any shareable
directory/archive is created and also refuse full verification after rehashing.
Local wallet notes and labels are excluded at capture and refused by the schema.
The old sensitive-field check remains as an additional refusal.

The guide documents the ownership contract and native cleanup controls. The
current acceptance index records the actual changes-requested verdict. All
accepted daemon scenarios, legacy verifiers and source/policy locks are unchanged.
No consensus, crypto, policy, dependency or runtime setting changed.

## Verified

Final execution/package source commit is
`b92e8c8d55ccbed692c6da6df1a9124bc1a65b55`. The later handoff commit adds this
report and named public evidence only. All fourteen package input files are
identical to the measured source bytes.

Evidence is [the named receipt set](evidence/vanguard-tester-tjs1870-fixes-2026-10-09/MANIFEST.sha256).
Final native output is `journey02` under
`~/Developer/tjs1870-fixes-2c4c4836`; the final source package is `kit02`.

| Check | Writer result |
| --- | --- |
| Final documented preflight/run/export | PASS on pinned build-mac Darwin 25.5.0 ARM64 and unchanged Colima/cache; 64.672s |
| Native P2P payment | PASS, tx `08d56225a08428848620f444dc1137a2179ced53a089cce56ff361b166b36044` |
| Receive, seed restore/rescan and rollback | PASS, five-unit tx `a6e0286dc4fb06f6edb58e54245717b3ca72cdf6bf30488f6f3770301d8a21de` |
| Subsequent recovered spend | PASS, two-unit tx `06aa2308c5d1776eda629b7e78cf07e72d0c91881805fadc1c16bb34e9d626c0`, confirmed on both native daemons |
| Actual process identity and exits | PASS, ten `/proc` executable hashes match accepted ARM pins; ten child exits and four container exits are zero |
| Resource containment | PASS, P2P peak 844,804,096B and restore peak 1,088,151,552B below 4 GiB; OOM/oom_kill zero |
| Offline native reconciliation | PASS, both unchanged legacy verifiers and tester reconciliation; limit remains `UNVERIFIED_LIVE_TIPS` |
| Native cleanup controls | PASS, four on the final package: stopped collision, foreign invocation label, stop timeout and final-inspection timeout; injected faults are explicitly labeled |
| Admission/privacy suite | PASS, build-mac 16 with no NOT_RUN; Linux 28 with one NOT_RUN for the real ARM cache, covered on build-mac |
| Encoded JSON privacy | PASS, two additional final-receipt export/verification refusals for an unknown field inside the encoded transaction JSON |
| Exact successful cleanup | PASS, four journey containers absent; six exact private paths removed for each of the two successful rehearsals; failed controls retained |
| Input/primary preservation | PASS, final cache/package rechecks; integrated HEAD still 86393a3, original raw status hash and all 1,163 file/symlink identities unchanged |

Final public archive SHA256 is
`5b221a31ded2307d1b754656de6143e112a6c6765c48267fcae63cef48e2557a`, 129,988 bytes.
Only the exact allowlisted public archive and named control/cleanup summaries were
retrieved. No wallet, chain, ring database, seed, key or raw free-form log was exported.
The original native cleanup fields record private retention before the separately
timestamped operator deletion receipts.

The initial corrected execution at 4e55d0c also passed in 61.573s. Its evidence is
preserved under its original input identity; the final capture additionally drops
local wallet labels. Two operator/test setup failures remain explicit in
`attempts.json`: a premature export was refused while the native manifest was
absent, and an encoded-JSON export fixture had the wrong raw manifest. The latter
was corrected on a fresh fixture, then both intended privacy refusals passed.
Neither created a shareable output. Native failure outputs preserve their FAIL
results and cleanup errors, rather than being presented as successful journeys.

## Independent acceptance and next owner

Reviewer ec85048c must inspect the exact resubmitted branch/bundle and reproduce
the guide's `package`, `preflight`, `run` and `export` invocation on fresh owned
build-mac paths, then verify the receipt offline and execute both documented control
scripts. The final package includes `test-tester-cleanup.py` and the pinned public
schema. Screenshots or this report do not satisfy independent reproduction.

Use only the existing pinned cache/runtime and idle shared lock. Do not rerun
closed soaks or Railway work, install/pull, change runtime settings, kill other
workloads, publish or push. Return findings to this same writer/stage. Acceptance
must precede local integration by existing studio lead 38e398e0, followed by parent
exact-tree/ancestry and pre-existing-file verification.

Portability, selected 9/90 integration of current crypto, public-testnet readiness,
production cryptographic/security assurance and remote-node/Tor/I2P/DNS assurance
remain open. Agent review is not an external audit. The completed 52-case
restricted-controller checkpoint is unchanged.

Needs TJ: None.
