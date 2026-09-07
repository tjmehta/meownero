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

## Address and URI fixtures — patch 0009

Test-only patch 0009 retains upstream public-key/payment-ID payloads and re-encodes fixed vectors using the native CryptoNote base58 codec. It covers standard, integrated and subaddress encodings on all three networks; decoded keys/flags/payment IDs; cross-network rejection; checksum corruption; and rejection of original modern Monero base58 addresses, including through URI parsing. These are encoding vectors, not subaddress key-derivation tests. Legacy hex-address parsing and the inherited `monero:` URI scheme remain unchanged.

The rebuilt targeted selection `get_account_address_*:base58*:meow_*:uri.*:difficulty.*:cryptonote_protocol_handler.race_condition` passed **278/278 in 3.443 s**, including all eight inherited address cases, two new address tests and all 32 URI cases. CI's `get_account_address_*` exclusion is removed; patch count is nine.

A fresh local clone applied patches 0001–0009 cleanly and matched the tested source tree `96dbf344ae63e9772d4330fa47d33e99fb0d49ed` (deterministic applied HEAD `7871fb1604caadd7a54015c40db045f649ade843`). No new binary reproducibility claim is made for this nine-patch series.

Broader selection without the address exclusion, with Docker networking disabled, ran **1,224 cases in 47.861 s: 1,212 passed, 12 failed (exit 1)**. The three historical serialization and three genesis-mismatched wallet-storage cases still fail. The other six failures were `AddressFromURL.{Success,Failure}` and `DNSResolver.{IPv4Success,DNSSECSuccess,DNSSECFailure,GetTXTRecord}`, which attempt network DNS lookups in this offline run. This run is not directly comparable to the earlier network-enabled count. The fourteen previously failing URI cases now pass; no new CI exclusions were added. The whole suite is still not green.

Local logs in the scratch source: `make-address-fixtures.log`, `test-address-fixtures.log`, `test-address-broader.log`.

## Opt-in authorities and donation path — patch 0010

Confirmed inherited update authorities remained reachable despite the disabled default: `tools::check_updates` is shared by core, update RPC and wallet-manager API callers. Patch 0010 removes its DNS authority list, clears outputs and returns false; `get_update_url` returns an empty string instead of a Monero download URL. Existing option parsing remains compatible; help explicitly states updates are unavailable. The wallet API caller was inspected, but no separate GUI/API runtime test is claimed.

The P2P DNS-blocklist callback no longer resolves hosts or installs remote bans. `--enable-dns-blocklist` remains accepted, warns and is ignored. Local bans remain intact. CLI `donate` now gives an explicit disabled message without parsing a destination or calling transfer, on every network; help no longer advertises Monero donations. No new authority, donation address or consensus parameter was introduced. The inherited donation constant remains only as an unused production-header constant referenced by an upstream URL test; the executable donation path no longer uses it.

Verification:

- Rebuilt daemon, CLI wallet, RPC wallet and both unit-test targets. Initial build failed when `cc1plus` was killed during wallet compilation; a single-job retry completed successfully after swap capacity recovered. No optimization or consensus settings were relaxed.
- Address/URI, authority and consensus/protocol regression selection: **280/280 in 3.379 s**. Raised-floor target: **9/9 in 0.192 s**.
- `chain/test-authorities.sh` passed with source mounted read-only and Docker networking disabled. Source assertions check removal of the inherited endpoints; actual RPC `check`, `download` and `update` fail closed with no URLs/download file; explicit DNS-blocklist opt-in logs its warning; RPC local host bans still work. Disposable unfunded CLI wallets report donations disabled on mainnet/testnet/stagenet, with no transfers. Test wallet output is captured, not printed, and temporary files are removed with the container.
- Initial runner checked only console output and missed the warning in the file log; the final runner explicitly enables level 1 and checks both logs. Final runner exited 0. Shell syntax and embedded Python parsing pass; host ShellCheck is unavailable, so no local ShellCheck pass is claimed.
- Fresh application of patches 0001–0010 matches tested tree `1e7f5e4347968c8824b4fe4284ccc6db298e42fb`; deterministic applied HEAD `8c24067c9e2f7a0b855d3d239c9ccf2e7e7be8a9`. This is source-tree verification, not a new two-build binary reproduction claim.

The authority runner is wired into `chain/build.sh`; CI counts ten patches and includes the new runner in ShellCheck. Full upstream-suite failures documented above remain open. Logs: `make-authorities.log` (initial failure), `make-authorities-retry.log`, `test-authorities.log`, `test-authorities-floor.log` in the scratch source.

## Multisig fixtures — patch 0011

Before the change, `multisig.*` ran seven cases: six `make_*` cases failed at the fixed testnet-address comparison (`multisig.cpp:81`), and the key-exchange-message case passed. Patch 0011 re-encodes the five inherited address strings using native `tools::base58::{decode_addr,encode_addr}`, from Monero testnet prefix 53 to Meownero testnet prefix 156. Generation verifies the 64-byte public-key payload is unchanged after decoding each replacement. All five spend-key literals, wallet generation, multisig assertions and production code remain unchanged.

Rebuilt selection `multisig.*:get_account_address_*:base58*:meow_*:uri.*:difficulty.*:cryptonote_protocol_handler.race_condition`: **287/287 in 25.108 s**, including all seven multisig cases in 21.982 s. CI removes the `multisig.*` exclusion; only the three previously attributed environment exclusions remain.

Broader offline run with a read-only source mount and disposable copied test data: **1,233 cases in 70.072 s; 1,221 passed, 12 failed (exit 1)**. The same three serialization, three wallet-storage and six DNS-dependent failures remain. No new failures or exclusions were introduced; the suite is still not green. This run covers patches 0001–0011, including the authority unit tests.

Fresh full-series application matches tested tree `cd8fa65fe527556e7d9b4996fdf84b9f57a492ae`; deterministic applied HEAD `663d9cf6f0871ace096e8beadeb737c879ec544c`. Delta: 25 files, +456/−584. The eight-patch binary reproducibility record is not extended to this series. Scratch logs: `make-multisig-fixtures.log`, `test-multisig-fixtures.log`; broader result is retained in task `b1ilg2bo7` output and summarized here.

## Raw local evidence

Scratch source: `<agent-scratch>`.

Logs: `test-fixture.log`, `test-m1-suite.log`, `make-floor-final.log`, `test-floor-final-default.log`, `test-floor-final-high.log`. These are session-local; summary evidence above is durable. The prior Docker tracking wrapper failed because zsh reserves `status`; the build's logs showed passing tests, and a subsequent direct invocation of `chain/test-difficulty.sh` independently exited 0 with 9/9 in each variant.
