# M1 verification — 2026-09-06

Continuation of `handoff-2026-09-05c.md`. This record supersedes its predictions of a passing protocol regression and an existing difficulty-floor test. Local work only; no public deployment, remote push, spending, or key custody. ADR-001 remains PROPOSED and unsigned.

## Results

| Check | Actual result |
|---|---|
| Rebuild saved six-patch tree | `make -j2 unit_tests daemon simplewallet wallet_rpc_server` succeeded |
| Meownero consensus cases | `meow_emission.*` 7/7; `meow_hardforks.single_jump_table` 1/1 |
| Inherited difficulty hash check | `difficulty.check_hash` 1/1 (not a floor test) |
| Inherited hard-fork state-machine cases | 18/18, including voting, activation, reorganization |
| Protocol race regression | **Timed out after 300 seconds (exit 124)**; handshake now advances to sync, then rejects the fixture's untagged miner output |
| Fresh upstream checkout → `chain/build.sh` | Pins verified; six patches applied; 14 files, +184/−385; daemon, both wallets, unit tests built; `meow_*` 8/8 |
| Three-node real-block devnet | All nodes converged to h2,841, identical tip; v16 from height 1; supply exact |
| Independent reproducibility | **Not attempted**; fresh build used existing image + shared ccache |

### Regression failure (do not count as passing)

```text
Sync data returned a new top block candidate: 4095 -> 9596
SYNCHRONIZATION started
wrong variant type: N10cryptonote12txout_to_keyE, expected txout_to_tagged_key
miner transaction has invalid output type(s)
[exited with code 124]
```

`tests/unit_tests/node_server.cpp:559–613` constructs synthetic coinbases using `txout_to_key`, then inserts blocks directly into the DB. The production v16 rules reject those outputs during sync. Updating the fixture to construct valid v16 blocks is the next regression task; changing consensus validation to accept the fixture is not appropriate. Further fixture assumptions may surface after this first rejection is corrected.

The handoff's `meow_difficulty.floor_is_applied_by_next_difficulty` is absent from both the applied tree and patch 0006. The patch clamps the computed result, but `next_difficulty` still returns literal 1 for ≤1 timestamp. This is harmless for the current constant 1 but bypasses a future launch floor >1. Add regression coverage and correct the startup path before raising the constant; preserve the upstream overflow-error sentinel.

### Devnet evidence

Fresh data directory: `/tmp/meownero-m1-devnet-20260906-WjhZZr`.

The existing smoke harness was invoked with target 30; mining overshot to height 167 before its first successful height observation. It checked every reward over heights 0–167:

- Genesis: block version 1, reward 0.
- Heights 1, 2, and 167: block version 16, reward 900,000,000,000 atomic each.
- Emission over 0–167: 150,300,000,000,000 atomic = 150.3 MEOW; fees 0.

The harness prints follower heights but does not assert convergence. An additional independent RPC check, after stopping mining, asserted identical heights **and** tip hashes on all three nodes:

```text
height: 2841
version: 16
hash: ec92460ab8d8e70f8e146c10504168f97c700dc7dabede5964107a069badc4bc
```

A final `get_coinbase_tx_sum` over 2,842 blocks asserted emission **2,556,900,000,000,000 atomic = 2,556.9 MEOW = 2,841 × 0.9**, fees 0. All three test containers were then stopped. This used fixed difficulty 1; it does not validate natural-difficulty dynamics, 120-second performance, wallet recovery, or adversarial behavior.

### Fresh build artifacts

Workdir: `/tmp/meownero-m1-clean-20260906-vHd6tb` (fresh upstream clone, not a second independent toolchain build).

Builder image used locally: `sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e`.

```text
7917ce988dad32abd6b5419a61b025637c8ee726efcfc98f442a1780b34c8ac9  monerod
8fca7a8ae447aaa17c8c43d49e6101bf2ea9a2e30c4ce9fe26a047282e1b519d  monero-wallet-cli
b17615457d54252fd1eb381c48c8556984ae0315315ecd9898d106b6ba1db3f1  monero-wallet-rpc
```

`chain/build.sh` now forwards `MEOW_JOBS` into Docker (previously ignored), defaults to two jobs, stops on CMake failure, and runs all `meow_*` cases rather than emission alone. Shell-stub checks verified the default, an explicit override, and that a CMake exit 7 prevents make; `bash -n` and `git diff --check` passed. Host shellcheck is unavailable, so shellcheck was not run. CI's stale five-patch assertion was corrected to six; CI has not been run remotely.

## Next work, in order

1. Adapt the protocol test's synthetic-block fixture to v16; bounded rerun must pass before clearing the regression.
2. Implement the missing difficulty-floor tests (including a nontrivial floor) and correct startup-path coverage; current constant remains 1 pending human launch inputs.
3. Independent reproducibility: pin image digest/packages; two fresh builds without shared object/cache reuse. Current CI merely relinks existing objects, which is not this criterion. Also align CI's test exclusions with documented cases and its devnet builder-image name with the image it actually builds.
4. Address-prefix and genesis vectors; wallet restore-from-seed. Then the remaining M2 adversarial/performance work in `docs/milestones.md`.

## Session-local raw evidence

Previous scratch tree remains at:
`<agent-scratch>`.

There: `make-hf-resume.log`, `test-hf-resume.log`. Fresh build: `build/release/{cmake.log,make.log}`, `SHA256SUMS`. Devnet: `supply-check.txt`, per-node data/logs. `/tmp` is not durable; the outcomes and full artifact hashes above are the repository record.
