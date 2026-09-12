# Foundation verification — 2026-09-12

Local engineering resumed after TJ's private snapshot publication. Future changes
remain local; the snapshot authorization is not recurring push permission.

## Thirteen-patch clean binary reproduction — PASS

The existing `test-reproducibility.sh` harness exited **0**. Two fresh source/build
trees compiled with **ccache disabled**, one compiler job and one immutable image.
Both builds passed the harness's consensus/protocol, floor-one, separately compiled
150M-floor and disabled-authority checks. **All three binary hashes match**, as do
package manifests, builder IDs and generated version metadata.

| Provenance | Value |
|---|---|
| Frozen repository input | `8b08205cca78519c9ac3c1a0b049ec9f2035c4ca` |
| Upstream | `4f92268d7c16741cfb41e5bbe2aa46cc260a9ea5` |
| Applied HEAD, both trees | `df1d93be4be4a700713268d772ff98b8367eeef7` |
| Source tree, both trees | `5239f02b7b2c1cfe75b3ff616ab0620c3068106e` |
| Builder | `sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e` |
| Package-manifest SHA-256 | `769dbcd72bac1dd528f5bd1833da29e0b788fdc50d9dee23791148ef6e6cd8d9` |
| Architecture | `ARCH=default` |
| Original output | `/tmp/meownero-repro-20260912/{first,second}` |

| Binary | SHA-256, identical in both builds |
|---|---|
| `monerod` | `527489b29a8cf0e41a478257c78e9accc0087a3911029c9df0ed1e8a7d4e3f92` |
| `monero-wallet-cli` | `13121432f7d022211a7c1f883f8aa35205332c88adecd022cb6e6ea2362f7341` |
| `monero-wallet-rpc` | `91edabcceb69857c7a22d5fdc16f3ea72a2b0dfc8ef6560e9493fabafb40fc0f` |

Durable evidence: [complete harness output](evidence/2026-09-12/reproduction/run.log),
[first hashes](evidence/2026-09-12/reproduction/first-sha256s.txt),
[second hashes](evidence/2026-09-12/reproduction/second-sha256s.txt),
[package manifest](evidence/2026-09-12/reproduction/packages.txt),
[version metadata](evidence/2026-09-12/reproduction/version.cpp),
[frozen patch checksums](evidence/2026-09-12/reproduction-patch-sha256s.txt).

This extends the historical eight-patch result to **thirteen patches only**. It
does not prove independent toolchain reconstruction, cross-host/hardware results
or reproducibility of later patches. Apt versions/snapshots remain unpinned.
Reproduction can faithfully reproduce a bug: the freshly compiled thirteen-patch
wallet still fails the live v16 refresh check, as shown by the
[clean-build negative control](evidence/2026-09-12/seed-clean13-failure.log).

## Harness and workflow checks

The devnet image forwarding, isolated network, stopped-miner supply check and
identical-tip assertions were verified with an immutable image and with the
default image name. The subsequent shell-array/quoting correction passed a fresh
three-node run at **height 140, 126.0 MEOW**, with both follower tips identical.
[Smoke output](evidence/2026-09-12/devnet-shellcheck-fix.log).

All eight chain/devnet shell runners pass **Shellcheck 0.9.0**. Workflow YAML
parses, and all **11 embedded shell steps** pass `bash -n`.
[Shellcheck output](evidence/2026-09-12/shellcheck.log),
[workflow syntax output](evidence/2026-09-12/workflow-check.log).
Lint tools were installed only in disposable containers; the host and immutable
builder image were not changed. This is local validation, not a remote CI result.

## Wallet fix and fifteen-patch validation — PASS

Patch **0014** fixes the shared wallet block-version check: it resolves an actual
fork-table entry instead of assuming that version numbers are contiguous array
indices. The mainnet table remains `{v1@0, v16@1}`. Unknown/skipped versions,
wrong activation heights, future versions and the original maximum-height
sentinel remain rejected. Two unit tests cover
the sparse mainnet table and inherited testnet/stagenet boundaries. No mismatch
override or genesis-validation bypass was added.

Patch **0015** adds varying-work sampling/recalculation tests at heights
599/600/601, 719/720/721, 734/735/736 and 800, then rolls back to 719 and builds a
different history. It compares the actual main and alternative sampling callers,
full/partial cumulative-work recalculation and cache behavior. Both floor variants
pass **10/10**. The injected DB blocks test accounting, not high-difficulty PoW;
separate M2 daemon tests cover actual competing-branch acceptance.
[Full boundary-test output](evidence/2026-09-12/difficulty-boundaries.log).

The isolated seed test passes on the patched binaries: at height **130**, the
restored address matches, all **130 coinbase-history entries** match, balance is
**117,000,000,000,000 atomic (117.0 MEOW)** and unlocked balance is
**63,900,000,000,000 atomic (63.9 MEOW)**. The original wallet cache and key file
are removed before restoration into a separate wallet process. Closing/reopening
the recovered wallet preserves all assertions.
[Machine-readable recovery result](evidence/2026-09-12/seed-recovery-pass.json).
This verifies mined-coinbase recovery through wallet RPC; it does not claim recovery
of outgoing metadata, private-payment history or the CLI's interactive restore flow.

The full **CI selection** passes **1,237/1,237 in 79.174 s**, retaining only
`ban.subnet`, `http_server.response_soft_limit` and `notify.works`. Source was
mounted read-only; test data came from a disposable archive of tracked fixture
bytes. No tracked historical archive bytes differ from upstream. This is not an
unfiltered suite or remote CI pass.
[Suite summary](evidence/2026-09-12/full-ci-summary.log),
[full-log checksum/path](evidence/2026-09-12/full-ci-log-sha256.txt).
The disabled-authority runner also passes on the updated daemon and CLI:
[authority results](evidence/2026-09-12/authorities-pass.log).

| Fifteen-patch provenance | Value |
|---|---|
| Applied HEAD | `7410c04bab0e304112710d63c3225c110bd8b4de` |
| Built/tested tree | `4db958cb96d72943c5c2433bd5f4a8f730037148` |
| Delta vs upstream | 28 files, +643/−616 |
| Built source | `/tmp/meownero-wallet-verified-source-20260912` |
| Fresh source-application cross-check | `/tmp/meownero-fifteen-final-20260912` (same tree) |

[Updated binary hashes](evidence/2026-09-12/fifteen-patch-binary-sha256s.txt) are
recorded separately. These binaries were built by applying patches 0014/0015 to
a **copy** of the first clean thirteen-patch source/build tree, preserving both
reproduction trees. This is an incremental fifteen-patch verification build,
**not a clean fifteen-patch binary reproduction result**. `ARCH=default`, Release
optimization and the immutable image remain unchanged. Final boundary review added maximum-height regression coverage before the
last verification build. A 3 GiB capped compile
was killed; retry with 4 GiB passed. No host services or packages were changed.

CI now includes seed recovery, native-window reorg checks and native-DAA models.
The full-suite step uses disposable data, read-only source and pipefail so a test
failure cannot be hidden by the final output filter. These changes remain local.

M2 results and limits are recorded separately in the
[adversarial and native-DAA benchmark report](verification-2026-09-12-m2.md).
