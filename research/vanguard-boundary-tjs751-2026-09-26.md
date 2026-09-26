# Vanguard V2 boundary reproducer and local hardening

Blocked on TJ: none. Independent exact-commit review is required before transaction integration starts. This report covers the boundary slice of TJS-751. It does not claim acceptance of the whole issue.

The starting revision is the accepted Vanguard V1 commit `9f6fc2e411dae910bc7c203ad89353bc8c2387cc`. The actual TJS-421 acceptance was read, including its distinction between mandatory fixes and optional receipt tightenings. Accepted v0 activation, recipes, builder image and V1 source files are unchanged.

## Reproducer notes for upstream review, retained locally

These are API robustness findings at fixed revisions, not demonstrated node vulnerabilities. No upstream contact or publication has occurred.

| Input | Revision |
| --- | --- |
| seraphis-migration/monero | `e151643c5269c83bf24a83b2548e2493876026b2` |
| monero-oxide | `31c26d96eaadbba910ffe3613ad8b4cf9c598a93` |
| Rust | `rustc 1.93.0 (254b59607 2026-01-19)` |
| Builder image | `sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e` |

The runner compiles C++ Release and upstream Rust release code. It reuses the five unchanged upstream `tests/data/fcmp_pp_verify_inputs_{1,2,4,8,128}in.bin` fixtures. Their complete hashes are pinned by the accepted V1 verifier and copied into the new receipt. There is no random proof generation or duplicated binary fixture. The one-input fixture is enough to reproduce both observations; the other four provide positive controls and expose the data-dependent layer result.

`vanguard/boundary/boundary_tests.cpp` deserializes the fixture using the same fields as upstream `SerializableFcmpPpVerify`. The unchanged full proof and its membership component must first verify. Each raw or guarded call runs in a child process, with core dumps disabled and a 45-second alarm. SIGABRT is recorded as `signal_6`; a timeout or any other unexpected result fails the suite.

### VG-F1: trailing byte acceptance

Take the valid fixture proof, append one zero byte, and call `fcmp_pp::verify` with the original message, depth, decoded root, pseudo outputs and key images. Repeat with the extracted membership proof and `fcmp_pp::verify_membership`. The raw APIs accept the suffix. The new Vanguard entry points reject it.

At the upstream pin, `src/fcmp_pp/fcmp_pp_rust/src/lib.rs:1002` uses `debug_assert_eq!` for full proof length. Release removes that assertion. `FcmpPlusPlus::read` receives a byte reader at line 1023 and the FFI wrapper does not check the remaining bytes. The membership wrapper at line 1102 likewise uses `Fcmp::read`. At the oxide pin, `crypto/fcmps/src/lib.rs:991-997` reads one proof's expected bytes without asserting end of stream.

The stream reader's behavior is consistent with reading an object from a larger stream. Exact consumption belongs at the complete-proof boundary. The FFI debug assertion, C++ proof assembly/splitting size checks in `fcmp_pp_types.cpp:243-290`, and consensus layout checks support exact-size semantics for a complete proof. This is a source-based inference about intended use, not a statement from upstream maintainers. Debug Rust was not executed.

### VG-F2: depth/root-curve mismatch abort

Keep the root decoded with the fixture's seven layers, but call the raw full verifier with six layers. The one-, four-, eight- and 128-input fixtures abort at oxide `crypto/fcmps/src/lib.rs:933`, with `claimed root is on a distinct layer than tree root`. The two-input fixture returns false. Commitment decoding can reject the wrongly aligned bytes before the panic, which explains why this is proof-dependent. A Rust panic crossing this FFI boundary cannot be repaired by a C++ exception handler.

The new API takes the compressed root and its trusted stored depth together. It checks the untrusted claimed depth against that stored depth before decoding the root or entering proof verification. The malformed claim returns false.

## Reachability and scope

The following call paths were inspected in the pinned C++ source:

- Pool admission calls `ver_non_input_consensus` before `check_tx_inputs`, in `src/cryptonote_core/tx_pool.cpp:254-270`. `tx_verification_utils.cpp:287-308,826-830` rejects invalid input/depth bounds and non-exact proof size.
- `blockchain.cpp:93-121` obtains both root and depth from the database and checks the transaction's depth. The single-transaction path calls that helper at line 3898 before `ver_input_proofs_fcmps` at line 3967.
- Block processing calls non-input checks at lines 2176 and 4625. Batch root collection at lines 2787-2819 checks cached depth or calls the database helper. `collect_fcmp_pp_tx_verify_input` at `tx_verification_utils.cpp:432-481` checks depth equality and decodes the root using the same depth before building a Rust verify input. The batch path uses that collection at line 894.
- The low-level direct caller in `ringct/rctSigs.cpp:1546` passes helper root data into the raw API. Its safety depends on the surrounding construction and validation contract. This report does not prove every possible caller safe.

In `ver_input_proofs_fcmps`, the pair at `tx_verification_utils.cpp:713` includes the transaction's claimed depth. That local pair alone is not authentication. The database check earlier in the blockchain path supplies the relevant binding. Future Vanguard callers must preserve the same trust boundary.

No live node or malicious transaction was exercised by this slice. No remote exploit, soundness defect or general panic immunity is established.

## Local implementation

`vanguard/boundary/verify.h` exposes full-proof and membership-proof verification. Each entry point checks 1 through 128 inputs and 1 through 12 trusted layers before narrowing or invoking Rust size arithmetic. Full verification also checks matching pseudo-output and key-image counts. Both reject proof sizes unequal to the upstream size calculation. Root decoding and C++ verification exceptions return false.

`TreeAnchor` must come from trusted state at the reference block. It does not authenticate its own fields. Passing attacker-controlled root and depth as an anchor violates the API contract. The wrapper deliberately keeps upstream cryptography, parameters and parsing unchanged; it adds the complete-proof and trusted-metadata checks at the Vanguard call boundary.

Tests include valid proofs before and after rejection cases, trailing and truncated bytes, a final-byte mutation, claimed layer changes of minus/plus one and two, zero/out-of-range/overflow-size layer claims and anchors, empty and excess input counts, mismatched key-image count, a different valid root and an invalid compressed root. Batch verification, other tree depths and transaction semantics remain outside this slice.

## Reproduce and inspect receipts

Use the already prepared pinned source/cache in `build/vanguard-src`:

```sh
python3 vanguard/run-boundary.py --out build/vanguard-boundary-review-01
python3 vanguard/verify-boundary.py build/vanguard-boundary-review-01
python3 vanguard/test-boundary-refusals.py build/vanguard-boundary-review-01
```

The output directory must be new. The runner refuses a held project heavy-work lock. It checks at least 5 GiB of available memory and disk, uses one build job, limits Docker to two CPUs, 4 GiB for build and 512 MiB for each execution, disables network and image pulls, and executes the binary twice with read-only source/cache mounts. It checks the upstream revision, tracked edits, submodule state, Cargo.lock, oxide checkout and Rust compiler before injection. Only test target registration and owned test sources are injected into the scratch upstream checkout.

The evidence verifier binds ordered results to 240 fixed cases, current boundary/runner/verifier source hashes, the source lock, fixture hashes and recorded containment flags. It checks finite positive wall times, cgroup peaks within caps and zero OOM events. The two result files must be byte-identical. The refusal script changes outcomes, positive controls, pins, time and network flags, then re-manifests the copies to exercise checks beyond file integrity.

The receipt stores exact Docker commands and binary SHA-256/size. Hashes and self-produced receipts are provenance, not independent execution proof. The verifier does not reconstruct the binary or authenticate wall time, compiler output or the reported Docker command against an external observer. Exact-commit QA must inspect the source and rerun it. Verdict determinism does not imply deterministic upstream batch-verifier randomness or portable binary reproducibility.

## Recorded result

The implementation is local commit `62d25db12224540eedf4852476c737e123c5f559`. Evidence is in `research/evidence/vanguard-boundary-tjs751-2026-09-26-run03/`. Its invocation started at HEAD `9f6fc2e`; `source_sha256` binds the executed boundary, runner and verifier bytes to the implementation commit. The report/evidence follow-up changes no executed source. Independent QA must name the final candidate commit, including this report and evidence.

Both executions matched all 240 ordered outcomes, including four raw SIGABRTs per run and zero guarded aborts. The suite includes 215 guarded calls, of which 20 are valid-proof controls and 195 require clean false. Its 25 raw calls preserve the observations and their valid controls. `verify-boundary.py` printed `PASS_VANGUARD_BOUNDARY cases=240 raw_aborts=4 hardened_aborts=0`. All nine re-manifested refusal controls passed. The unchanged V1 receipt verifier still passed its 187 vectors.

| Measurement | Build | Run 1 | Run 2 |
| --- | ---: | ---: | ---: |
| Wall seconds | 14.10 | 219.08 | 189.46 |
| Container memory peak, bytes | 401850368 | 255975424 | 255668224 |
| Largest child RSS, KiB | not measured | 262076 | 261992 |
| Exit | 0 | 0 | 0 |

All recorded cgroup OOM counters are zero. This is a warm incremental build on the existing V1 artifacts, not a cold build measurement. Each case forks, so wall times include repeated process-local cryptographic initialization; they are not steady-state transaction throughput. The previous two build attempts remain locally preserved: 3.53 seconds with exit 127 for the missing toolchain PATH, then 8.77 seconds with exit 2 for incorrect C++ API names. They produced no successful test receipts.

- Byte-identical `run1.tsv` and `run2.tsv` SHA-256: `cfe57d2d4334ccfcf9ac4bfc078cd604f6a4e90cb347fe1c05640a3ccf939208`.
- Binary SHA-256: `c824662a17a316053eeecb72d2086c67a93aa9343aff522cb2019cf141f50c71`, 17463624 bytes.
- Evidence manifest SHA-256: `7f899ae7452e3e10b55cdfc5a7ea93279cf0821292f0ec60807000a4d73b5ac9`.

These are author-run results awaiting independent exact-commit acceptance. The report does not imply external audit or security readiness.

## Remaining transaction/node gate

After independent boundary acceptance, the next bounded implementation must construct a real FCMP++/CARROT transaction using pinned upstream facilities, verify its spend authorization, range proof and value balance, and submit valid and invalid transactions through an isolated valueless node admission path. A hand-built proof-only wrapper is insufficient for that gate.

Subsequent integration gates must exercise peer sync over a local isolated transport; branch switch and stale-root/proof/cache handling through a reorg; cold database and wallet restore followed by rescanning and spending; and bounded build, tree growth, construction, verification, admission and sync measurements. Their thresholds and workloads must be recorded with that implementation. None of these gates has passed in this boundary slice. No change to v0 activation or public network access is authorized by this report.

Observed behavior: the fixed API reproducer can distinguish accepted proof suffixes, process aborts and clean rejections. Trusted tree metadata must be checked before Rust verification. This is the learning delta from this slice; V1 acceptance remains closed.
