# Testnet v0 end-to-end journey

TJS-313 adds the operator journey for the testnet v0 freeze: one command runs
the five accepted milestone recipes in freeze order, one after another, in one
output directory with one input manifest and one evidence manifest.
`journey.py` imports the accepted profile, baseline and binary admission checks
from `launch.py` and the wallet and pool pins from `payment.py` and
`pool-restart.py`, pins the accepted TJS-229 recipe manifest to SHA-256
`1e3b8a784828b05634abd4b4ac22ba7cc83652b32af023c71c146f3216a5e59f`, and then
runs each recipe unchanged as its own process:

| Step | Milestone | Recipe | Verifier |
| --- | --- | --- | --- |
| `01-launch` | M1 TJS-229 two-peer launch | `launch.py` | `verify.py` |
| `02-payment` | M2 TJS-230 payment, seed restore, reopen | `payment.py` | `verify-payment.py` |
| `03-sync` | M3 TJS-242 late peer sync and restart | `sync.py` | `verify-sync.py` |
| `04-recover` | M4 TJS-287 cold backup/restore, payout wallet | `recover.py` | `verify-recover.py` |
| `05-pool-restart` | M5 TJS-297 pool restart at the common tip | `pool-restart.py` | `verify-pool-restart.py` |

Each step runs in its own container on its own fresh two-peer chain from the
same genesis. This is a property of the accepted recipes, not a choice of the
journey: every recipe creates its node directories exclusively and refuses
existing state, and every accepted verifier requires a fresh-genesis readback
and, for M1, M3, M4 and M5, an empty-block chain with zero fees. Running them
on one continuing chain would need changed recipes and changed verifiers, which
TJS-313 forbids. The journey therefore proves that an operator can reproduce
the whole testnet v0 witness from one command on one machine, with every
milestone's own receipts and verifier intact, and it adds the cross-step checks
that are meaningful for five chains from one genesis. A continuing-chain
variant is a separate decision, not a hidden gap in this one.

## Run from the repository root

Use a new path each time. The journey admits nothing that the recipes would
refuse, and it starts nothing until all five admissions and the builder image
check have passed.

```sh
python3 -B chain/testnet-v0/journey.py --work build/testnet-v0-journey-01 --check-only
python3 -B chain/testnet-v0/test-journey-refusals.py --work build/testnet-v0-journey-refusals-01
python3 -B chain/testnet-v0/journey.py --work build/testnet-v0-journey-01
python3 -B chain/testnet-v0/verify-journey.py build/testnet-v0-journey-01
sha256sum -c build/testnet-v0-journey-01/INPUTS.sha256
```

Admission runs the shared pins first (daemon `b79cb49d…`, wallet RPC
`5782abee…`, F4 candidate pool `bbc32406…`, the accepted 43-file recipe
manifest and the four journey files), then each recipe's own `--check-only`,
then `docker image inspect` on the pinned builder image. `payment.py` takes no
profile argument; it reads the recipe profile directly, and the journey admits
`--profile` only as an exact copy of that file, so the steps see one profile.
A refusal exits 2 with `REFUSED` and the first failing step's own message, and
creates no directory. Execution then probes the shared heavy-work lock without
holding it: each step takes and releases the lock itself, because only one
testnet container may run at a time. A busy lock exits 75 with a `BLOCKED`
receipt and no step started; wait for the owner and use a new path. The host
must have at least 5 GiB available RAM and disk.

## Expected wall time and resources

| Step | Accepted run | Container bound |
| --- | --- | --- |
| `01-launch` | 25 s | 420 s + 75 s cleanup |
| `02-payment` | 10,005 s (2 h 47 min) | 24,000 s + 150 s cleanup |
| `03-sync` | 165 s | 1,500 s + 75 s cleanup |
| `04-recover` | 45 s | 1,800 s + 75 s cleanup |
| `05-pool-restart` | 41 s | 1,800 s + 75 s cleanup |
| Journey | about 2 h 52 min plus five container starts | 29,970 s |

The payment step dominates: its 100 funding blocks, 12 confirmation blocks and
12 further confirmation blocks are mined by the native RandomX miner on one
thread under the native difficulty algorithm, which holds about 90 s per block
after the first ten. More threads raise difficulty, not block rate. Do not
trim the funding phase: coinbase maturity is 60 blocks and ring size 16 needs
unlocked decoys. The container peak is about 3.3 GiB (the pool step; the
miner's RandomX dataset is about 2.4 GB of it) under the recipes' 4 GiB cap,
two CPU quotas and no swap. Each step keeps its node databases under
`WORK/<step>/data`; the payment step's daemon logs are about 26 MB.

`journey.py` streams every step's output and writes it to
`WORK/<step>.launcher.log`. The payment recipe writes its own container output
to `WORK/02-payment/run.log` and its case progress to
`WORK/02-payment/progress.json` instead of streaming; follow those while it
runs. `Ctrl-C` or `SIGTERM` stops the current step, which stops its own owned
container; the journey then exits 130 with the receipts written so far.

## How to read the result

The journey exits 0 only when all five steps exited 0. `WORK/result.json`
says `PASS`, `FAIL` (with `failed_step` and a reason) or `BLOCKED`.
`WORK/steps.json` lists each step's command, start and finish time, wall
seconds, exit code, container name, container exit and the recipe's own
result; `WORK/<step>.exit` is each step's exit receipt. A step that fails
stops the journey; later steps are not run and appear in no receipt.

`verify-journey.py` prints `PASS_JOURNEY_RECEIPT_RECONCILIATION` after it has
checked, in this order: the single `EVIDENCE.sha256` against every listed file
and against each step's own manifest; the journey exits, sequencing (no
overlap, five distinct containers, container time inside step time), admission
receipts, image pin, lock probe, resource gate and executable pins; each step's
receipts with that milestone's accepted verifier (`verify.py`,
`verify-payment.py`, `verify-sync.py`, `verify-recover.py`,
`verify-pool-restart.py`), run unchanged; and the cross-step invariants: the
same genesis header in all five chains, identical baseline, profile and
executable pins, each step's `INPUTS.sha256` contained in the journey's, a
fresh-genesis readback with target 90, fork v16 at height 1 and the 9 MEOW
template reward in every step, strictly increasing height and cumulative work
within every chain, each step reaching its accepted minimum top index (3, 124,
9, 7, 7), emission equal to the top index times the flat subsidy in every step
with header rewards equal to subsidy plus fees, the payment step's two fees as
the only fees and its two transactions as the only transactions, the funded
sender's balance equal to its mined subsidy and its final balance equal to
funding minus payment minus fee plus the returned spend, the payout wallet's
balance equal to its mined subsidy and unchanged across the cold restore, and
the pool restart with zero pool-attributed blocks paying only the public
fixture address. The printed summary lists each chain's top index, tip hash,
cumulative work, emission, fees and container peak memory. Tips and work are
per step; they are not cumulative across steps.

`sha256sum -c WORK/INPUTS.sha256` from the repository root checks that every
input any step pinned is still the accepted byte sequence. The journey manifest
is the union of the five step manifests plus the journey files; a conflict
between steps fails the journey.

## Privacy boundary

The payment step creates four disposable wallets and the recovery step one;
their files, seeds and logs stay under `WORK/02-payment/data` and
`WORK/04-recover/data`, which no manifest lists. The only address in public
receipts is the public recipe fixture. Copy only the files covered by the
journey's `EVIDENCE.sha256`.

## Limits

This journey sequences the accepted milestone witnesses; it does not extend
any of them. It is not a continuing-chain run, an independent operator run, an
external audit, F3/FCMP work, share or payout clearance, a 90-second cadence
GO, a public testnet or a mainnet readiness claim. The wall time and memory
figures come from the accepted runs on one host and will vary.
