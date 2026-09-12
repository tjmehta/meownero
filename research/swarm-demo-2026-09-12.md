# Swarm demo track — 2026-09-12

Bounded deliverable complete in the linked worktree based on verified
`39070e8e3ab32a695d80c90b7c0ad74cf39fb581`, including `81b3182`. Parent
`meownero-codex` owns review/integration. All changes are limited to assigned
demo, brand and track-evidence paths. No shared runners, existing handoffs,
policy, CI, site or preserved build/source trees were modified. No push,
deployment, outreach, package installation or extra agent was used.

## Verified private payment and recovery

[Runner and instructions](../demos/private-payment/README.md) use the actual
current15 daemon and wallet RPC, with all three release binary hashes pinned to
the existing receipt. The build is the preserved incremental fifteen-patch
verification build; this track does not claim clean fifteen-patch reproduction.

The successful run exited 0 in approximately 22 seconds under a 512 MiB cap,
two-CPU quota, `--network none`, no host port mapping, read-only source/harness
mounts and the shared heavy-job flock. Docker reported no OOM kill.
Disposable mainnet-mode chain, fixed difficulty 1, historical 120-second
headers; no P2P. No chain compilation was needed.

| Checked quantity | Atomic units |
| --- | ---: |
| Payment and recovered unlocked balance | 123456789012 |
| Transaction fee (this run) | 64950000 |
| Sender before payment | 90000000000000 |
| Eleven subsequent subsidies | 9900000000000 |
| Fee received by sender acting as miner | 64950000 |
| Sender after | 99776543210988 |
| Final emission, equal to sender + recipient | 99900000000000 |

The payment is a confirmed version-2 transaction with RingCT type 6, sixteen
ring offsets per input, and zero public input/output amount fields. The recipient
receives a normal incoming payment, not a coinbase. The original recipient
process stops and its entire wallet directory is removed. Seed restoration into
a fresh process/empty directory reproduces address, incoming history and total/
unlocked balances, including after reopen. A deliberately stored local note
does not return. Sender outgoing amount and fee match the same transaction ID.

Evidence:

- [Checked result](evidence/swarm-2026-09-12/demo/payment/result.json),
  [run log](evidence/swarm-2026-09-12/demo/payment/run.log),
  [binary/toolchain provenance](evidence/swarm-2026-09-12/demo/payment/provenance.json),
  [container exit state](evidence/swarm-2026-09-12/demo/payment/container-state.json).
- [Tested Python/C harness hashes](evidence/swarm-2026-09-12/demo/tested-harness.sha256).
- Ephemeral complete run directory: `/tmp/meownero-swarm-demo-payment-02`.
  Disposable wallet files remain there for local debugging and are not committed.

This small fully controlled output set does not establish meaningful anonymity.
Public representation checks do not prove network privacy or resistance to
observer inference. FCMP++, normal DAA/security, propagation, interactive CLI,
subaddress recovery, spending after restore and outgoing-metadata recovery are
not measured. The original successful shared coinbase seed test was not rerun
or modified.

## Optimization materials and baseline only

[Challenge specification and runnable comparison recipe](../demos/private-payment/challenge.md)
define the `keccak.c` allowlist, unchanged APIs, fixed hardware/toolchain, separate
input sizes, A/B/B/A order, correctness/differential checks, and an explicit
x86_64/GCC constant-time review gate. Candidate fields are **not measured**.
No optimization was introduced and no before/after gain is claimed.

The small baseline harness links two existing current15 objects and runs all
321 preserved fast-hash vectors before measurement. Its single compilation
used the immutable builder, one compiler job, shared flock, 128 MiB cap,
one-CPU quota and CPU-0 affinity. GCC `13.3.0-6ubuntu2~24.04.1`, i7-8700K.
No daemon, library or source object was rebuilt.

| Input | Baseline median ns/call | Batch min–max ns/call | Candidate |
| --- | ---: | ---: | --- |
| 32 bytes | 471.10858 | 464.59358–544.35365 | Not measured |
| 16,384 bytes | 53763.629 | 51970.283–54378.492 | Not measured |

Nine batches per size, after warmup. These are shared-host diagnostic measurements,
not a ranking, constant-time proof or whole-chain performance result. Raw data:
[measurement](evidence/swarm-2026-09-12/demo/hash/measurement.json),
[summary](evidence/swarm-2026-09-12/demo/hash/summary.json),
[input hashes](evidence/swarm-2026-09-12/demo/hash/inputs.sha256),
[compiler](evidence/swarm-2026-09-12/demo/hash/compiler.txt),
[container state](evidence/swarm-2026-09-12/demo/hash/container-state.json).
Ephemeral binary and full CPU details: `/tmp/meownero-swarm-demo-hash-01`.

The external/source boundary for an actual comparison is a separately built,
reviewed candidate tree. The supplied command runs twelve labeled measurements
once that tree exists; it does not substitute for its provenance, all-API
correctness/constant-time review, or parent-owned daemon/wallet integration.

## Visual deliverable

[Six-frame storyboard](../docs/brand/swarm-2026-09-12/storyboard.svg),
[three-direction mood board](../docs/brand/swarm-2026-09-12/moodboards.svg), and
[timing, captions, references and claim boundaries](../docs/brand/swarm-2026-09-12/README.md).
Both original SVGs were parsed, rendered through installed librsvg/Cairo and
visually inspected. Text equivalents and observer labels are included. This is
storyboard material, not a produced video or chosen brand identity.

## Factual corrections, separately from proposed choices

- **Fixture correction:** the first new demo attempt used headers older than the
  wallet's creation-time scan window, so its funding assertion failed. The exact
  local check is `wallet2.cpp:3020` (`timestamp + one day > account creation`).
  The runner now uses a 15,000-second lookback, keeping all 111 headers in the
  past and within that window. No wallet/consensus patch or bypass was added.
  [Failure log](evidence/swarm-2026-09-12/demo/first-attempt-timestamp-failure.log).
- **Library scope correction:** verified the requested primary Monero contest
  page on September 12; precise library-specific figures and limits are recorded
  [once in the challenge](../demos/private-payment/challenge.md#factual-correction-from-the-monero-precedent).
  No whole-chain gain is inferred.
- **Attention scope:** inherited the supplied closed September 12 attention
  snapshots without repeating the scrape. Ages/exposure differ; counts are not
  audited unique people or evidence of causal adoption.
- **Normative proposals:** the visual directions, frame sequencing, challenge
  code allowlist and proposed review/measurement contract are design choices.
  They do not settle protocol, economics, ticker, identity, checkpoint, signer,
  audit budget, public outreach or prize decisions.

## Final verification and integration boundary

Payment/recovery assertions passed; benchmark vectors 321/321 passed; C harness
compiled with `-Wall -Wextra -Werror`. Bash syntax, Python parse, SVG XML, local
Markdown links and staged whitespace/path scope were checked. No new full-chain
suite was run. Shellcheck was unavailable on the host and is not claimed.
After the successful runs, wrapper cleanup was adjusted to save container state
on failures as well as success; this bookkeeping change received syntax review.

Only small allowlisted outputs are committed; no mnemonic, key/cache files,
chain database or binary artifacts. The parent can integrate the explicit-path
commit and decide where shared documentation/CI should link it. Those changes
and any broader security/performance verification remain with the parent.
