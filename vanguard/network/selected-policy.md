# Current-lineage 9/90 preparation

This checkpoint prepares the selected policy on upstream
`e151643c5269c83bf24a83b2548e2493876026b2`, starting from accepted genesis
checkpoint `983f405dfcb72b843a653a728e1e8a8af1de94e3`. No native build or
execution occurred in this preparation. The full candidate remains blocked.
Public launch stays disabled.

The canonical profile remains
`56a25f173448b3caa34ae9bb29761f5d467376df4470902fd89824ddc11fe4e8`.
The source lock, genesis bytes, crypto pins and prior evidence are unchanged.
The new overlay has its own identity, SHA256
`0f971c34e3401f2faf85fa98862f7f28698af3b5ee28765c17657f8bee5eb044`.
Bind both identities when preparing or integrating a build. A profile digest
alone does not identify its implementation. The
[machine receipt](evidence/selected-policy/policy-overlay.json) binds every
original and changed file; [policy-bindings.json](policy-bindings.json) adds
four source hashes to the original 34-path binding and checks their pinned Git
objects. This remains scoped source verification, not full-tree attestation.

## Implementation and invariants

[policy.py](policy.py) writes the complete ten-file preparation patch into a
fresh owned directory. It combines the accepted admission prerequisite with
TESTNET-only reward and target helpers. It never applies a patch to shared
source, starts a process or enables a network. Generate it with:

```sh
python3 -B vanguard/network/policy.py --source "$PINNED_UPSTREAM_SOURCE" \
  --out "$TASK_PRIVATE_SCRATCH/selected-policy-new"
python3 -B vanguard/network/test_policy.py --source "$PINNED_UPSTREAM_SOURCE" \
  --scratch "$TASK_PRIVATE_SCRATCH" --evidence "$TASK_PRIVATE_SCRATCH/policy-checks-new"
```

| Requirement | Implementation and check | Unconfirmed native claim |
| --- | --- | --- |
| Selected 9 MEOW/90 seconds, 12 decimals | TESTNET constants in its config namespace; network argument in reward helper; fallback is refused | Linked policy vectors and native chain agreement |
| Preserve foreign selectors | MAINNET/STAGENET identity and fork regions, global 60/120 constants and foreign emission formula preserved; FAKECHAIN retains upstream policy | Differential native MAINNET/STAGENET/FAKECHAIN vectors |
| Preserve penalty and accounting | Reward penalty suffix, exact-coinbase/point validation, main/alternate tally expressions and fee addition unchanged | Native penalties, fees, saturation and actual database accounting |
| Height-zero exception only | Constructor returns the bound one-zero-output native recipe only for explicit TESTNET height0, fee0; validation retains prior height0 rule | Height1 pays9 even at zero previous generated coins; genesis fee refusal |
| All production reward callers agree | Three chain reward calls, two miner constructors, two pool reward calls and one constructor reward call pass the real network | Native construction, template and fee admission |
| Primary/alternative/checkpoint difficulty agree | All three chain target expressions use one network helper; mining-status RPC reads the chain target | Native target/difficulty callers and competing-chain behavior |
| Address separation | Dedicated prefixes remain4240/4241/4242; static profile and bootstrap controls remain | Native own roundtrip and foreign-selector/upstream/historical address refusals |
| No crypto or package changes | No wallet, P2P, crypto, portable helper, source-lock, shared lockfile or other writer edits | Final daemon/CLI/wallet integration and independent acceptance |

Eleven new source/runner checks pass, including apply/reverse of every changed
byte, source drift, unchanged penalty and foreign emission paths, fallback
refusal, consumed-grant refusal before output creation, and held/wrong-inode
fixture-lock refusal before native admission. The lock tests use disposable
fixtures; they do not claim live host admission. All17 existing tooling and6
provenance regression checks pass. See
[checks.json](evidence/selected-policy/checks.json) and adjacent logs.
These checks do not execute the C++ patch, network handshakes or native policy.
The source/document diff whitespace check passes. The verbatim unified patch
contains upstream blank context lines with a required leading space; its full
diff-check diagnostic is retained as `patch-format-diff-check.txt`.

## Exact next native workload

The missing claim is that the linked current-lineage implementation honors its
TESTNET-specific reward/target and address separation through actual native
helpers and a height-one template. Accepted genesis admission is completed
work. It will not be repeated as a separate genesis workload.

[run-policy.py](run-policy.py) and
[the native target](native/policy/policy.cpp) prepare one cold-build attempt.
The old helper and admission grants are consumed and refused by the runner.
A new platform-owner grant is required before invoking it. A UUID argument
records a grant; arbitrary UUID text does not grant authority.

The proposed window is900 seconds total, including a20-second cleanup reserve,
with one native container,2CPUs,4GiB memory and no swap,256PIDs, one compiler job,
network-none, no capabilities, no-new-privileges, no published ports, no image
pulls and offline Cargo. Admission requires the original lock at
`/tmp/meownero-swarm-20260912-heavy.lock`, device66306/inode657237, owner-only
mode0600, a nonblocking exclusive claim, at least5GiB memory/disk, and no native
process/container collision. Recheck admission and the same lock path before
creation. The runner records actual Docker containment before startup.

It exports pinned Git/submodule objects into new owned staging, checks all38
bound paths, applies only the frozen overlay and hashes the result. Cargo inputs
are copied without hardlinks or credentials; the Rust toolchain stays read-only.
The accepted builder is used by its source-lock digest. There are no reusable
prior task build objects after accepted cleanup, so no incremental reuse claim.

Build only `vanguard_network_policy`, registered as `tests/vanguard-policy` in
the private export. Execute it twice, each with a separate fresh root and60s
timeout. Each invocation has the following fixed limits:

- 13,608 native reward/penalty vectors covering selectors MAINNET, TESTNET,
  STAGENET and FAKECHAIN, versions1 through18, overweight refusal and supplies
  around u64 saturation. Compare against independent u128 reward arithmetic.
- 39 native address checks covering own three-form roundtrip, bilateral foreign
  selector refusal, upstream TESTNET53/54/63 and historical mainnet120/121/123.
- 24 native height-one CARROT coinbase constructions across zero/positive/
  saturated previous accounting, fees0/12345 and four penalty weights.
- Explicit genesis construction and fee refusal, genuine TESTNET/null-options
  core target90/v18, native height-one9-MEOW template, and the missing same-boundary
  positive `reset_and_set_genesis_block` control.

No non-genesis block is mined or admitted. There is no daemon P2P/RPC listener,
wallet file, payment, mature-root claim or network-separation claim. The two
summary JSON outputs must agree. A failed positive reset leaves prior negative
reset results non-specific; do not reinterpret them as confirmed genesis checks.

```sh
# Only after a new platform grant, with a clean committed candidate:
python3 -B vanguard/network/run-policy.py \
  --grant-comment "$NEW_PLATFORM_GRANT_COMMENT_UUID" \
  --out "$TASK_PRIVATE_SCRATCH/policy-attempt-new"
```

The runner reserves cleanup time, retains configure/build/witness diagnostics,
binary/source/cache hashes, exits, peak memory and OOM counters. Remove only its
exact returned container ID under the original lock. Save and upload reports,
verify no remaining container and lock release, then archive any needed stopped
valueless DB/binary state and remove exact owned source/build/Cargo/DB staging.
No native attempt or staging was created during preparation. A timeout or failed
build consumes the new window; no native retry or reservation is implied.

## Review boundary before full network execution

The proposed chain target also feeds deterministic timestamp projection and the
legacy seconds-based unlock tolerance. Those lines are explicit in the patch.
Core and Privacy/Cryptography must review their interaction with v18 before
full-network assurance is claimed. No point/proof verifier is changed.

Separately, pinned `get_last_locked_block_index` in
`src/cryptonote_basic/cryptonote_format_utils.cpp:2102` hardcodes the mainnet v15
time/height and divides by the global120-second target. Its own TODO asks for
network-aware conversion. It has no network argument and participates in
FCMP output lock metadata. This preparation leaves it unchanged. Do not silently
replace its historical anchor or turn unsupported timestamp locks into height
locks. The concrete consultation asks Core/Cryptography to select a network-aware
mapping and adverse vectors, or explicitly constrain timestamp-locked transactions
pending that implementation. Any constraint itself needs reviewed consensus
and wallet agreement. No such choice has been made here.

Wallet restore-height estimates, time displays and legacy selection windows still
use120-second constants; wallet fork-table validation and addresses must agree
with the final profile. Block-rate notification and protocol progress estimates
also retain upstream timing. These are explicit remaining integration work,
not evidence that merely rebuilding existing packages completes this profile.

After the bounded policy result, complete native height1 funding, maturity/root
accounting, FCMP++/CARROT positive/adverse validation, actual same/foreign-peer
handshakes, bootstrap refusal, authenticated/restricted RPC, persistence,
catch-up/recovery and cross-node receive/payment/restore/later spend. The
[operator runbook](operators.md) still governs private endpoint assignment and
cleanup. Keep Core/Security native stages pending for the complete candidate,
then obtain independent acceptance and lead-only integration. No public network,
release signing key, package promotion, merge or push is authorized here.
