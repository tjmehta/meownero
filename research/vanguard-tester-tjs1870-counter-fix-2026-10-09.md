# Vanguard tester counter privacy correction

Writer F4 correction and fresh native rehearsal: PASS. Independent acceptance of
this revision, local integration and parent verification: NOT_RUN. This report
supplements the preserved original writer reports and reviewer verdicts.

## Change and boundary

The last reviewer reproduced arbitrary text escaping through the first token in
`.cpu` and `.memory-events` files. The shared `public_bytes` boundary now freezes
the nine CPU and six memory-event names from the verified supported kernel.
Every name must appear exactly once with an ASCII numeric value. Unknown,
duplicate and missing names refuse the input. Export projects separators to plain
spaces and newlines; offline verification requires those same canonical bytes.
The allowlist never learns names from the input being exported.

Both normal export and full verification use this boundary. New controls append
the reviewer's synthetic private-token name or duplicate a recognized name in
`p2p/build.cpu` and `restore/run1/run1.memory-events`, then deliberately regenerate
the evidence manifest. All eight export/verification controls refuse the input.
The export controls confirm that neither a shareable directory nor archive was
created. Direct controls also cover missing names, nonnumeric values and non-ASCII
numeric values for both counter types.

The guide documents the restriction, and the current acceptance index links the
latest changes-requested verdict. F1–F3 lifecycle and JSON validation, accepted
native scenarios, legacy verifiers, source/policy locks and historical reports are
unchanged. No consensus, crypto, policy, dependency or runtime setting changed.

## Fresh evidence

Execution/package source commit is
`dae4e18258c12fd2f9221a724f81bae16c910340`. The handoff commit adds this report and
named public evidence only. Its fourteen package input files match the measured
source bytes. The [evidence manifest](evidence/vanguard-tester-tjs1870-counters-2026-10-09/MANIFEST.sha256)
binds the archive, control summaries, native summary, exact cleanup and primary
preservation receipt.

The documented `package`, `preflight`, `run` and `export` commands ran from a fresh
owned package on build-mac, Darwin 25.5.0 ARM64, using the existing pinned Colima
image/cache. Remote root is `~/Developer/tjs1870-counter-fix-bccb4e3b`.
The shared heavy lock refused busy work in the supplied admission controls.

| Check | Writer result |
| --- | --- |
| Fresh native journey | PASS, 63.670 seconds; both gates pass |
| P2P payment | PASS, tx `0e57f499d90c2dfaaccf0cb6a14591da903b9a58801f29ca4d7669a45249272e` |
| Five-unit receive, restore/rescan and rollback | PASS, tx `4314cb7f22167ab63820fbcd2e6bd5ec40481be4be07204ae97c67eee557299a` |
| Subsequent two-unit recovered spend | PASS, tx `62de535b70c69a6e6f51a9fcad1edd55b6243c57c02085064db97e61264ed5b8`, confirmed on both daemons |
| Native hashes and exits | PASS, ten actual process hashes match the ARM pins; ten child and four container exits zero |
| Memory/OOM | PASS, P2P peak 844,427,264B and restore peak 1,085,427,712B below 4 GiB; all memory-event counters and container OOM flags zero |
| Legacy and wrapper reconciliation | PASS; unchanged reconcilers, with `UNVERIFIED_LIVE_TIPS` retained |
| build-mac admission/privacy controls | PASS, 26; no NOT_RUN |
| Offline public-evidence controls | PASS, 46; one ARM-cache row NOT_RUN on Linux, covered on build-mac |
| New F4 unknown/duplicate export and verification controls | PASS_REFUSAL, eight after deliberate rehashing |
| Successful private cleanup | PASS, four exact container IDs absent and six exact owned wallet/chain/home/ring paths removed |
| Input and primary preservation | PASS, cache/package preserved, primary HEAD 86393a3, original raw status and all 1,163 file/symlink identities unchanged |
| Unchanged native F1/F2 fault controls | NOT_RUN in this narrow revision; independently PASS on f391b102 with identical lifecycle code |
| Independent acceptance, integration and parent verification | NOT_RUN |

The genuine public archive SHA256 is
`09d674d1373a78a69509cad277432668e09f3b8467874502e9ce5a40f04286a5`, 136,190 bytes.
Only this allowlisted archive and named control/cleanup summaries were retrieved.
No seed, key, wallet/chain/ring database or free-form log was exported. The native
receipt correctly records private-state retention at capture; the separately
timestamped operator receipt records later exact-path deletion.

One local preservation-script setup attempt failed because its comparator used
the wrong saved symlink-field name. The corrected comparator confirms preservation
of all original paths. No path changed and no native workload started in that
failed attempt. Its diagnostic remains in `attempts.json`. Earlier failed attempts
and reviewer controls remain preserved.

## Review handoff

The same attached reviewer ec85048c owns independent acceptance on the existing
stage. From the exact final candidate, reproduce the guide's package and fresh
build-mac preflight/run/export invocation, verify the allowlisted receipt from the
full repository, and run `test-tester-refusals.py --public <public> --work <fresh>`.
Check both F4 file types after deliberate rehashing, actual native bindings and
exact successful private cleanup. Return findings to this writer/stage. The
earlier F1–F3 results remain linked in the reviewer document; the native cleanup
control script is unchanged and available in the package.

Use only the existing cache/runtime and idle shared lock. No soak, Railway run,
install/pull, heavy build, broad kill, runtime change, publication or push occurred.
Acceptance must precede integration by studio lead 38e398e0 and parent exact-tree,
ancestry and pre-existing-file verification. Whole-task completion remains pending.

Portability, current-crypto selected-policy 9/90 integration, public-testnet
readiness, production cryptographic assurance and remote-node/Tor/I2P/DNS assurance
remain open. Agent review is not an external audit. The completed 52-case
restricted-controller checkpoint is preserved. Needs TJ: None.
