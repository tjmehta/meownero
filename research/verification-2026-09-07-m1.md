# M1 verification — 2026-09-07

Continues `verification-2026-09-06-m1.md`. Group decisions are recorded in PLAN.md rev 5 and ADR-001 §7. No launch, spending, external push, or runtime changes. The site change in `site/src/components/notify.tsx` is unrelated and untouched.

## Protocol regression closed

Patch 0007 uses the existing `set_tx_out` helper in the synthetic miner fixture, selecting the active hard-fork output encoding. No production validation is relaxed. The previously 300-second-timed-out protocol race test passed in 3.151 seconds, and again in the final consensus selection. Build execution now bounds it at 180 seconds.

## Difficulty floor coverage and fixes

The first regression experiment compiled the actual DAA with floor 1 and 150,000,000. The former passed; the latter failed startup because `next_difficulty({}, {}, 120)` returned 1. The startup clamp fixes this, but review exposed two required caller safeguards:

- Genesis itself must retain difficulty 1. Genesis and block 1 both supply empty DAA samples, because sample collection skips genesis. The exemption therefore belongs in `Blockchain::get_difficulty_for_next_block`, not an empty-vector branch inside the DAA.
- `Blockchain::recalculate_difficulties` must use the same genesis rule or it can rewrite post-genesis cumulative work with an erroneous offset when the floor is raised.

Patch 0008 includes both safeguards, eight tests, and a separate CMake test executable compiling the real DAA against a generated 150M-floor config header and linking the existing core libraries. A compile-time assertion pins the test header's floor. The production constant stays **1**; no new runtime floor option or consensus-parameter override is introduced.

Verified:

| Selection | Result |
|---|---|
| Default `meow_*:difficulty.*:cryptonote_protocol_handler.race_condition` | 18/18 |
| Default `meow_difficulty.*:difficulty.*` via `chain/test-difficulty.sh` | 9/9 |
| 150M-floor `meow_difficulty.*:difficulty.*` via the same runner | 9/9 |

The nine checks comprise clamp boundaries, empty/one-sample startup, computed results below/at/above floor, ceiling/sorted timestamps, equal timestamps, overflow sentinel 0, actual core genesis/recalculation, fixed-difficulty override, and inherited hash validation.

Core tests initialize mainnet, testnet and stagenet identities offline, assert genesis cumulative work 1, then inject one synthetic post-genesis block into each test DB and verify unchanged cumulative work after recalculation and correct next-block difficulty. A separate case confirms `--fixed-difficulty=7` intentionally overrides a 150M floor. The synthetic DB insertion tests accounting, **not** high-difficulty PoW mining or adversarial reorgs. Main/alt-chain callers share the DAA; adversarial alt-chain validation remains M2.

`bash chain/test-difficulty.sh <built-source>` runs both executables from a read-only source mount with writable temporary test data. `chain/build.sh` builds the additional target and runs the script.

## Broader suite: not green

Before the two additional core tests were added, the suite with the previously documented exclusions ran **1,211 tests in 48.930 s: 1,191 passed, 20 failed**. Exclusions were `get_account_address_*:multisig.*:ban.subnet:http_server.response_soft_limit:notify.works`; these exclusions are not newly claimed as passes.

Failures remaining for M1 fixture work:

- `Serialization.portability_wallet`, `Serialization.portability_unsigned_tx`, `Serialization.portability_signed_tx` (serialized Monero fixtures; all pass on the unpatched baseline, see attribution below).
- Fourteen URI cases: `good_address`, `good_integrated_address`, `unknown_parameter`, `unknown_parameters`, `long_payment_id`, `empty_description`, `empty_recipient_name`, `non_empty_description`, `non_empty_recipient_name`, `url_encoding`, `non_alphanumeric_url_encoding`, `truncated_url_encoding`, `percent_without_url_encoding`, `url_encoded_once`. These use Monero address/URI fixtures; replacement is not done.
- `wallet_storage.store_to_file2file`, `wallet_storage.change_password_same_file`, `wallet_storage.change_password_different_file`: throw `Genesis block mismatch` on the inherited wallet fixtures.

**Baseline attribution (2026-09-07):** the same three serialization cases plus all URI and wallet-storage cases passed **40/40 in 4.207 s** using the previously built unpatched v0.18.5.1 baseline. Its source HEAD is `4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5`, with no tracked changes. The baseline source was mounted read-only, test data copied inside a disposable container, networking disabled. These 20 Meownero failures are therefore not classified as generic environment failures. The historical serializer and wallet fixtures need adaptation without weakening production network/genesis checks.

Do not broaden CI exclusions merely to make the suite green. Replace/attribute fixtures and rerun. This record does not claim that the whole upstream suite or an audit passed.

## Same-host fixed-image reproducibility verified; toolchain reconstruction open

Review identified wall-clock-dependent patch commit IDs embedded through VERSIONTAG, host-dependent `-march=native`, unpinned image/package inputs, and CI's relinking of existing objects instead of independent compilation.

Implemented preparation: `git am --committer-date-is-author-date`, `ARCH=default`, digest-pinned Ubuntu base, immutable builder-ID resolution, complete package manifest, forwarded `CCACHE_DISABLE`, and `chain/test-reproducibility.sh` for two fresh compilations in separate source/build trees. The same harness is wired into CI, not a relink step. Shell syntax and orchestration stub tests pass (equal artifacts, unequal artifacts fail, preexisting build trees refused; immutable image and cache-disable variables asserted). Two independent patch applications produced identical commit `8c82c0fb55d5e8fa6743884e321a23738397683d`; actual ccache configuration reports `disable = true`.

**Completed, exit 0:** `/tmp/meownero-repro-20260907-CDD1jq`, task `b32ya9gkv`, first/second logs at `<workdir>/{first,second}.log`. Both fresh eight-patch builds and focused tests passed; the harness reports `PASS: independent source builds match in the recorded builder image.` The three binaries, generated `version.cpp`, builder IDs and package manifests match. Full binary hashes and provenance are recorded in [`chain/README.md`](../chain/README.md#reproducibility).

Immutable builder: `sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e`; package-manifest SHA-256: `769dbcd72bac1dd528f5bd1833da29e0b788fdc50d9dee23791148ef6e6cd8d9`. Upstream commit is `4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5`; applied series HEAD is the deterministic commit above, `VERSIONTAG=8c82c0fb5`, `ARCH=default`. Two compiler jobs, one build at a time, ccache disabled. The series stayed unchanged throughout both builds.

All three second-tree binaries passed `--help` startup smoke in the exact immutable image with networking disabled. This is **same-host fixed-image source reproducibility** for patches 0001–0008 only, not cross-hardware portability or performance evidence. Independent toolchain reconstruction remains open: apt snapshots/version pins are outstanding.

## Raw local evidence

Scratch source: `<agent-scratch>`.

Logs: `test-fixture.log`, `test-m1-suite.log`, `make-floor-final.log`, `test-floor-final-default.log`, `test-floor-final-high.log`. These are session-local; summary evidence above is durable. The prior Docker tracking wrapper failed because zsh reserves `status`; the build's logs showed passing tests, and a subsequent direct invocation of `chain/test-difficulty.sh` independently exited 0 with 9/9 in each variant.
