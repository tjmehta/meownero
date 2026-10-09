# Vanguard local tester kit writer result

Writer implementation and fresh native rehearsal: PASS. Independent reproduction,
review acceptance and accepted-only local integration: NOT_RUN. The overall task
is not complete. The existing single review stage is the next execution path.

## Changed

The root README now routes operators to `docs/vanguard-tester.md` and
`research/current-evidence.md`. The guide distinguishes current accelerated
upstream FCMP++/CARROT regtest from the historical selected-policy 9/90 journey.
Historical writer reports and all accepted native scenarios, verifiers and source
locks are unchanged. No consensus, crypto or monetary-policy code changed.

`vanguard/tester.py` packages named source/docs, performs read-only admission,
uses the fixed independently accepted ARM cache, and runs the short native P2P
and funded restore/later-spend scenarios once each. The explicit ARM adapter
retains all original scenario assertions and calls the unchanged reconcilers.
Its local restore module instance uses the separately checked ARM binary pins;
the historical x86 verifier CLI remains unchanged. The receipt's `build` stage
is explicitly cached inspection, not a compile.

The native instrumentation records actual `/proc/<pid>/exe` hashes and public
RPC observations. Seed/key/password RPC and private pending-transaction metadata
are excluded. The private Unix socket uses the accepted tmpfs approach on Colima.
Work is capped by container deadlines, bounded subprocess waits and a 2,500-second
whole-workload timer. Cleanup targets only exact owned container names.

## Verified

Execution commit is `a4e63f940fba56754d28f2bbc3c426ca3f6e90df`, descended from assigned
integrated base `86393a36b11d2eb3d395bb63a96ea405a8059520`. The later evidence-only
handoff commit does not alter any of the 12 execution/package input files. Native
output is `journey04` under `~/Developer/tjs1870-843d0763`.

| Check | Writer result | Evidence |
| --- | --- | --- |
| Verified supported profile | PASS | build-mac Darwin25.5.0 arm64, existing Colima context; client29.2.1/server29.5.2; fixed ARM image/profile, original preparation digest, source/submodule/Cargo.lock and native/toolchain hashes |
| Fresh short native journey | PASS | 61.414s total; both scenarios exit0 |
| Native P2P payment | PASS | tx `42ae3b68139e5bb55c37ca54d675222240910b78800534371e9f3b9dd503a6c0`, native relay, malformed/duplicate frame refusals, reorg and healthy exchange |
| Receive/restore/later spend | PASS | received5 units tx `54423b557ea3a542af2c33dc7909048688279242696b90168c0441b63a886c4a`; restore/rescan equality; recovered2-unit spend tx `3e2b2e07ce01a7ec631e14f7f884adefb536f987d18b2d8379b18e48c862d956` confirmed on both native daemons |
| Exits/resources | PASS | ten scenario child exits0 plus four container exits0; P2P peak841,400,320B and restore peak1,082,765,312B, both below4GiB; OOM/oom_kill0 |
| Read-only inputs unchanged | PASS | source/package and original cache rechecked after the workload |
| Export and offline reconciliation | PASS | archiveSHA256 `1a1163035857b7770f00c4cee833306f81e729d1edc1ff8fb62f0d4e20a7f826`, 131592bytes; unchanged legacy assertions plus native payment/receive/restore bindings |
| Admission/privacy controls on build-mac | PASS | 15 controls, no NOT_RUN; wrong pins, unsupported architecture, existing output, actual competing lock process and privacy cases |
| DEV evidence/export controls | PASS with platform row explicit | 21 passing controls; real ARM-cache row NOT_RUN on Linux and covered on build-mac. Includes rehashed wrong pins/profile/receive balance and export extras/symlinks/FIFO/hardlink/renamed databases/secrets |
| Owned cleanup | PASS | four final containers absent;18 exact successful private wallet/home/ring paths removed across attempts02/03/04; runtime/cache preserved |
| Primary preservation | PASS writer recheck | all1,163 dirty/untracked file hashes/sizes/modes and raw status identical; primaryHEAD remains86393a3 |
| Independent reproduction and exact-candidate verdict | NOT_RUN | attached reviewer ec85048c owns it |
| Accepted-only integration and parent verification | NOT_RUN | existing studio lead38e398e0, then parent OpenClaw |

The allowlisted public export contains named receipts, structured native
observations, counters and native Levin refusal frames. Raw daemon logs become
recognized parser markers with original raw digests retained. No recursive
wallet/chain/ring export is used. Additional directories/files, symlinks,
hardlinks, FIFOs, renamed databases and secret-bearing JSON are refused or excluded.
`UNVERIFIED_LIVE_TIPS` remains the post-run reconciliation limit. Raw successful
logs remain private on build-mac; seeds and wallet/ring databases were deleted through
exact owned paths after export/verification. Failed attempt01 is preserved and
failed before any daemon/wallet was started. The operator cleanup receipt records
actual later deletion; original native cleanup receipts correctly record the
private retention state at their own timestamp.

Preserved attempt01 at841f2df failed socketchmod on the Colima shared folder,
exit1/OOM0 and no payment. Attempt02 at3c2b876 passed in103.021s. Attempt03 ata9cb56f
passed in66.418s after privacy/input-preservation hardening. Final04 includes the
whole-workload timer and passed in61.414s. Prior passing exported-only archives,
failed diagnostic receipts and attempt identities are retained. These are short
kit rehearsals, not repeated completed soaks or Railway trials.

## Independent acceptance and integration

Reviewer ec85048c must review the exact final handoff branch and reproduce the
**documented invocation**, rather than accept this summary or screenshots:

1. From the clean final candidate, `python3 -B vanguard/tester.py package --out <fresh-owned-kit>`.
2. Transfer only that named source package to a fresh owned build-mac directory.
3. There run `python3 -B vanguard/tester.py preflight`, then
   `python3 -B vanguard/tester.py run --out <fresh-owned-journey>`, then the
   documented `export --out <fresh-public> --archive <fresh-archive>` command.
4. Retrieve only the allowlisted export; from the exact full repo run
   `python3 -B vanguard/tester.py verify <fresh-public>` and the refusal suite.
   Record actual invocation, native hashes/transactions/exits/OOM/cleanup and
   its independent verdict. Clean only that reviewer's successful private output.

Reproduce using the existing verified cache and runtime. Busy shared lock or
active Docker containers must refuse admission. No competing build, broad kill,
public network, install, pull, runtime setting change, Railway recreation, seed
sharing or external push/publication is authorized. Return content findings to
the same writer on the same existing stage. After acceptance, the existing studio
lead owns safe local integration; parent independently checks exact tree/ancestry
and pre-existing file preservation before any group completion. This report does
not claim either action has happened. The final candidate/tree and uploaded
artifact IDs are recorded in the Paperclip result document and bridge result.

## Unconfirmed/next

Independent fresh reproduction, exact final-candidate approval, accepted-only
local integration and parent verification remain required. Portability outside
the one verified profile, selected9/90 integration of current crypto lineage,
public-testnet readiness and production cryptographic/security assurance remain
open. Explicit local trusted-daemon RPC and loopback transport give no remote-node
honesty, public-IP, DNS/OpenAlias or Tor/I2P assurance. Agent review is not an
external audit. The completed52-case restricted-controller checkpoint is preserved.

Observed behavior: Colima shared-folder Unix sockets need the already accepted
container tmpfs path. Native cache reuse reduced these complete short journeys to
about one minute without changing the accepted scenarios or policy.

Needs TJ: None.
