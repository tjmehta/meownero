# TJS-313: testnet v0 end-to-end operator journey (M6)

2026-09-22. Milestone check 6 after M1–M5 were each accepted (TJS-229,
230/278, 242, 287/294, 297/298/299): one command that reproduces the whole
testnet v0 witness on one machine, with one input manifest and one evidence
manifest, and one verifier that re-derives every milestone's claim plus the
cross-step invariants. Recipe committed as `73ce72a`, a verifier shape fix as
`9cf676e`; this document and the evidence directory follow in the next commit.

Delivered `chain/testnet-v0/journey.py`, `verify-journey.py`,
`test-journey-refusals.py`, the operator document `journey.md`, and the
top-level README section "Run testnet v0 end to end" (the recipe README is a
pinned accepted input and was not edited). The five accepted recipes
(`launch.py`, `payment.py`, `sync.py`, `recover.py`, `pool-restart.py`), their
five verifiers, the 43-file TJS-229 manifest (`1e3b8a78…`), the daemon
`b79cb49d…`, the wallet RPC `5782abee…` and the F4 candidate pool `bbc32406…`
are unchanged and re-verified at admission. No rebuild, consensus, protocol or
pool change was made. No earlier run directory, daemon or container was reused.

## One command, five fresh chains from one genesis

The issue asked for the M1–M5 steps "on one fresh two-peer chain" while
"reusing the existing recipe modules unchanged" and "calling the existing
per-step verifiers". The code makes the first and the other two mutually
exclusive: every accepted recipe creates its node directories exclusively and
asserts a fresh network (`get_info.height == 1`), and the accepted verifiers
for M1, M3, M4 and M5 require a fresh-genesis readback, an empty-block chain
(`num_txes == 0`) and zero fees over the whole chain, plus token-for-token
equality with their own daemon commands (M5's peer 1 publishes ZMQ, M3's
daemons carry `--max-connections-per-ip`). A continuing chain that has
carried the M2 payments, or a peer 1 restarted with a different command,
fails those verifiers by design. Satisfying "one chain" would therefore have
required forked seam code and forked verifiers, which the issue forbids.

The journey keeps the recipes and verifiers intact and sequences them: each
step runs unchanged as its own process and its own container, one at a time,
on its own fresh two-peer chain from the same deterministic genesis, inside
one output directory. The cross-step invariants are the ones that hold for
five chains from one genesis (identical genesis header, baseline, profile and
pins; strictly increasing height and work within each chain; one subsidy
explaining every emission total and every wallet balance). Tips and
cumulative work are per step, not cumulative across steps, and the verifier
says so in its output. Whether a continuing-chain variant is wanted is a
separate decision for TJ; it is not a hidden gap in this one.

## Observed journey run (`journey/`, `build/testnet-v0-journey-tjs313-run01`)

Started 2026-09-22T03:00:14Z detached, with the shared heavy lock free and no
other worker live; finished 06:22:37Z. Journey wall time 12,143.2 s
(3 h 22 min); the sum of the five step wall times is 12,143.1 s. Every step
exited 0 with container exit 0 and recipe result `PASS`; the five containers
are distinct and their time windows do not overlap.

| Step | Container | Wall s | Top | Tip | Work | Emission | Fees (atomic) | Peak RAM |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `01-launch` | `meow-tjs229-2050924` | 23.9 | 4 | `f2a3b417…` | 0x22 | 36 MEOW | 0 | 2.60 GiB |
| `02-payment` | `meow-tjs230-2054434` | 11,921.0 | 124 | `69aaf299…` | 0x4d18ba | 1,116 MEOW | 1,101,900,000 | 2.67 GiB |
| `03-sync` | `meow-tjs242-258576` | 92.4 | 9 | `7b2b6246…` | 0x4413 | 81 MEOW | 0 | 2.85 GiB |
| `04-recover` | `meow-tjs287-296736` | 46.8 | 7 | `9a7385de…` | 0x976 | 63 MEOW | 0 | 2.59 GiB |
| `05-pool-restart` | `meow-tjs297-311048` | 59.0 | 7 | `009e0008…` | 0xa83 | 63 MEOW | 0 | 3.10 GiB |

Every chain: genesis `20ce111b…` with reward 0 and version 1, then v16 blocks
of 9 MEOW mined natively by peer 0 on one RandomX thread under the native
difficulty algorithm; both peers (three in `03-sync`) hold identical header
sets at the tip; emission equals the top index times 9 MEOW. Per-step
witnesses, each re-derived by that milestone's accepted verifier:

- **Launch.** Profile verified on both fresh peers, native mining, top 4 at
  difficulty 26, converged through P2P only.
- **Payment.** Solo funding to wallet A reached height 100 (`279fc593…`,
  work 0x3e9fe6): 900 MEOW, 369 MEOW unlocked. Payment A→B of 5 MEOW, fee
  0.0006498 MEOW, txid `5b79de5f…`, type 6 with ring 16 on both inputs, in
  both mempools, confirmed at height 101 on both peers (block `199e7e6f…`);
  A then 894.9993502 MEOW, B 5 MEOW. Wallet D restored from B's seed on
  peer 1 with equal address, balance and history. Recovered spend D→A of
  2 MEOW, fee 0.0004521 MEOW, txid `df849392…`, confirmed at height 113;
  D 2.9995479 MEOW, A 896.9993502 MEOW. D's snapshot equal after
  store/close/open, outgoing history including the spend. Both peers:
  emission 1,116 MEOW = 124 × 9, fees 0.0011019 MEOW = fee 1 + fee 2.
- **Sync.** Late peer 2 received the five-block chain in 1.315 s (2,562 P2P
  bytes); three peers converged on two more blocks; peer 1 stopped cleanly
  at top 7, missed 2 blocks, restarted with the identical command and caught
  up in 0.821 s.
- **Recover.** Payout wallet W funded by five coinbase blocks: 45 MEOW, all
  locked, five `block` entries bound to canonical `miner_tx_hash`; plain
  peer 1 restart with W reopened equal; cold backup of the stopped data
  directory (3 files, archive 204,800 bytes, `80638c29…`), destroy, 2 blocks
  mined without peer 1, byte-identical restore, rejoin in 0.613 s; W reopened
  equal again.
- **Pool restart.** F4 candidate pool attached on peer 1 at tip 3 in
  1.204 s with a stratum job on that tip; followed live blocks to 5; stopped
  cleanly; 2 blocks mined while down; restarted with the identical command
  and served a job at height 8 on the common tip 7 in 1.305 s;
  `totalBlocksFound` 0 throughout, payout only the public fixture.

The payment step took 11,921 s against the accepted run's 10,005 s: the
native difficulty overshot to 56,179 around height 10 after the fast first
blocks and then settled between about 23,000 and 38,000, averaging 96.7 s per
block over the 123 mined intervals. This is PoW variance under the same
method, not a change; the phase and container bounds (18,120 s funding,
24,000 s container) were not approached.

## Resource measurements (this run on this host only)

| Measure | Value |
| --- | --- |
| Journey wall time | 12,143 s (3 h 22 min); `journey.json` expectation from the accepted runs 10,281 s; bound 29,970 s |
| Largest container peak memory | 3,323,445,248 bytes (3.10 GiB) in `05-pool-restart`, under the 4 GiB cap; no OOM or `max` event in any step |
| Host preflight | 28.99 GB available RAM, 32.68 GB free disk; 5 GiB gate |
| Public receipts | 179 files, 34.5 MB, of which the payment step's five logs are 31.4 MB |

These numbers describe five tiny isolated chains under the recipes' caps and
must not be extrapolated to a historical database, a busy node or a public
network.

## Verifier fix after the run

The first `verify-journey.py` pass on run01 stopped with a `TypeError` at
the payment step: `payment.py` saves `profile-readback.json` as a two-element
list while the other four recipes key it by peer, and the verifier indexed
it by key. Commit `9cf676e` makes the verifier take the two rows from either
shape and require exactly two; no recipe, receipt or other verifier changed,
and the fixed verifier passes run01's receipts. Because run01 executed under
`73ce72a`, its `INPUTS.sha256` pins the pre-fix verifier
(`a43be51c…`, which equals
`git show 73ce72a:chain/testnet-v0/verify-journey.py`), so `sha256sum -c`
on that manifest at or after `9cf676e` reports exactly one non-OK line,
`chain/testnet-v0/verify-journey.py: FAILED`, with 65 lines OK. The
derivation, both hashes and the diff are in `verify-journey-pin.txt`. The
journey recipe itself and every step recipe are unchanged since the run.

Two figures in the pinned `journey.md` are superseded by this run and are
left as pinned rather than edited after the fact: "about 3.3 GiB" reads as
3.3 GB (3.10 GiB), and the wall-time expectation of about 2 h 52 min is the
accepted-run sum, which this run exceeded by 31 minutes for the reason above.
The unpinned README section carries the observed range.

## Verification and evidence

- Fifteen actual-command admission refusals plus accepted control against
  `journey.py` (`refusals/`): wrong genesis, genesis reward, subsidy, target,
  fork version, fork height, pool profile, enabled pool, prefix and testnet
  mode (each surfaced from the launch recipe's own admission), stale
  directory, daemon hash, wallet hash, pool binary hash, and a busy heavy
  lock, which exits 75 with a `BLOCKED` receipt, `lock-probe.json` busy and
  no step directory. Each other refusal exits 2 before any directory is
  created; the sentinel in the stale directory is untouched.
- `verify-journey.py` returned `PASS_JOURNEY_RECEIPT_RECONCILIATION`
  (`verify.stdout.json`, `verify.exit` 0): the single `EVIDENCE.sha256`
  against every listed file and against each step's own manifest; journey
  exits, sequencing, admission receipts, image pin, lock probe, resource gate
  and executable pins; each step re-derived by its accepted verifier run
  unchanged (`verify.py`, `verify-payment.py`, `verify-sync.py`,
  `verify-recover.py`, `verify-pool-restart.py`, all `PASS`); and the
  cross-step invariants in the map below.
- `sha256sum -c INPUTS.sha256` from the repository root: 65 entries OK and
  the one expected verifier line (`inputs-check.log`); the journey manifest
  is the union of the five step manifests plus the four journey files, with
  no conflict. `sha256sum -c EVIDENCE.sha256`: 179 files OK
  (`evidence-check.log`). 266 files in `MANIFEST.sha256`.
- Privacy: the only address in any public receipt is the public recipe
  fixture, six occurrences (`address-privacy-grep.txt`). The payment step's
  four wallets and the recovery step's payout wallet, their seeds, keys and
  logs stay under each step's `data` directory in `build/`, outside the
  evidence set.
- Every owned container was removed by its recipe; the only `meow-`
  containers on the host are three unrelated ones stopped two weeks earlier
  (`container-cleanup.txt`).

| Invariant | Admission / live check | Retained evidence |
| --- | --- | --- |
| Exact candidate | Daemon, wallet and pool hashes; accepted 43-file manifest; journey files; five recipe `--check-only` admissions; builder image present | `BINARY.sha256`, `INPUTS.sha256`, `admission.json`, `image-check.json` |
| One run, one manifest | Union of step pins without conflict; every step receipt in the journey manifest | `INPUTS.sha256`, `EVIDENCE.sha256`, `<step>/EVIDENCE.sha256` |
| Sequenced, one container at a time | Lock probed and taken per step; step timelines do not overlap; distinct container names | `lock-probe.json`, `steps.json`, `<step>.exit`, `<step>/container-command.json` |
| Same genesis | Genesis header identical in all five chains; hash `20ce111b…`, reward 0, version 1 | `<step>/headers.json` |
| Same live profile | Fresh readback in every step: height 1, target 90, v16 at 1, 9 MEOW template; identical baseline and profile copies | `<step>/profile-readback.json`, `<step>/baseline.json`, `<step>/profile.json` |
| Monotone tip and work | Height +1 and strictly increasing cumulative work within every chain; accepted minimum tops 3, 124, 9, 7, 7 reached | `<step>/headers.json`, `<step>/rpc-final.json` |
| One subsidy explains supply | Emission = top × 9 MEOW in every step; header rewards = subsidy + fees; only the payment step carries fees and transactions | `<step>/rpc-final.json`, `<step>/headers.json` |
| Wallet accounting | Payment: funding = mined subsidy, final balances = funding − 5 − fee + 2 and 5 − 2 − fee; recover: payout wallet = mined subsidy, equal across cold restore; pool: zero pool-attributed blocks, fixture payout | `02-payment/result.json`, `04-recover/wallet-restart.json`, `05-pool-restart/pool-restart.json`, `process-commands.json` |
| Each milestone's own claims | Accepted verifier per step, unchanged | `verify.stdout.json` (`per_step`) |
| Isolation and cleanup | No external network, caps, hardening and owned exits per step; every container removed | `<step>/container-command.json`, `<step>/resources.json`, `<step>/cleanup.json`, `container-cleanup.txt` |

Raw receipts: [evidence](evidence/testnet-v0-journey-tjs313-2026-09-22/).
Operator entry point: [journey](../chain/testnet-v0/journey.md) and the
README section "Run testnet v0 end to end".

## Disposition and limits

The assigned one-command operator journey is complete for the finite isolated
chains: one invocation, one output directory, one input manifest, one
evidence manifest, per-step exit receipts, the existing refusal semantics,
and one verifier that re-derives every per-step claim with the accepted
verifiers and adds the cross-step checks. This is an author-run witness with
a separate receipt checker, not an independent operator run, an external
audit, F3/FCMP work, share or payout clearance, a 90-second cadence GO, a
public testnet or a mainnet readiness claim. It sequences the accepted
milestone witnesses and extends none of them: the M2–M5 limits (no pool-funded
inputs, no spend after cold restore, no pool restart under load or with
shares, no reorg with transactions, no second-operator execution) carry over
unchanged. No push, mainnet, protocol change, pool deployment or paid-auditor
prerequisite was added.

**TJ decision:** a working testnet, finite mature scope, one operator recipe,
no mainnet. **Observed:** one command reproduces the launch, funded payment
with seed restore, late-peer sync and restart, cold backup/restore with the
payout wallet, and the pool restart at the common tip, each on a fresh chain
from the same genesis, in 3 h 22 min of wall time, with every milestone's own
verifier passing on the receipts and the cross-step checks holding.
**Agent proposal:** QA/Release accept milestone check 6 on the evidence
commit's receipts as TJS-298 did for M5, treating the single
`verify-journey.py` manifest line as the expected residual with its
derivation receipt; whether a continuing-chain journey (which needs new seam
code and a new verifier) should follow is TJ's call before any publication
question, not a prerequisite for this acceptance.
