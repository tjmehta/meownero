# TJS-230 payment/recovery journey checkpoint

2026-09-20. Implementation prepared; native integration execution blocked by the
shared heavy-work lock. No payment, recovery or reopen pass is claimed.

Added `chain/testnet-v0/payment.py`, `verify-payment.py` and
`payment-journey.md`. The runner binds the accepted TJS-229 43-file manifest
SHA-256 `1e3b8a784828b05634abd4b4ac22ba7cc83652b32af023c71c146f3216a5e59f`,
reuses the launcher validation/RPC helpers, and pins the accepted TJS-40 daemon
and wallet. The original launch recipe and F4 writer files are unchanged.

The new journey uses the authorized solo-funded option because TJS-224 has not
accepted pool exports. It adds the existing TJS-44 cross-node payment assertions
to native RandomX/DAA mining, requires type 6 and ring size 16 on every input,
reconciles both daemon aggregates against wallet fees and canonical headers,
and checks recovery plus store/close/open state. The operator document states
the observer boundary and excludes wallet state/logs from public receipts.
TJS-44's completed component behavior is reused, not rerun or reopened.

Verification performed:

- Python syntax and authored-file whitespace checks passed.
- Actual admission command passed recipe/profile/binary pins.
- Actual stale-output and wrong-wallet commands refused admission with exit 2.
- Execution at `build/testnet-v0-payment-tjs230-01` returned exit 75 because the
  shared heavy lock was busy. No owned container, daemon or wallet started.
- The separate verifier rejected that blocked receipt with exit 1.

Public receipts and checksums are under
`research/evidence/testnet-v0-payment-tjs230-2026-09-20/`. This is refusal and
admission evidence, not evidence of a successful financial or recovery journey.
The new runner and successful-receipt verifier still require runtime validation.

Unblock owner/action: TJS-224 QA/Release must finish its serialized heavy work and
release the lock; Studio Lead can then resume TJS-230. Use a fresh directory:

```sh
python3 -B chain/testnet-v0/payment.py --work build/testnet-v0-payment-tjs230-02
python3 -B chain/testnet-v0/verify-payment.py build/testnet-v0-payment-tjs230-02
sha256sum -c build/testnet-v0-payment-tjs230-02/INPUTS.sha256
```

Native funding/maturity may exceed the 1,800-second limit. Record any timeout
without switching to regtest, fixed difficulty or timestamp steering. Archive
only reviewed top-level public receipts; never include `WORK/data`, seeds,
private keys or wallet logs. No broader testnet milestone or F4 gate is closed.

TJ decision: use solo funds unless the F4 exports have passed TJS-224 verification.
Observed behavior: recipe admission passes; execution cannot acquire the shared
lock. Agent proposal: resume the exact bounded command after QA releases the
resource, then give QA the successful package for independent acceptance.

The prompt names a `security` routing policy, but the current routing file has
no policy under that name. No model configuration was changed or alternate
review capability claimed. Work stayed in this assigned runtime without delegation.

Resume run `2597981e-8f5a-4e6f-98d8-a37a05d7ed7b` rechecked the lock and found it still busy with `meow-tjs224-reorg-378730`. All 13 prior evidence manifest entries rehashed successfully. No duplicate integration run was started. The tools inherited the old run environment; control-plane requests in this run use the current supplied `pane.env`.

## Run 02 failure and run 03 result (2026-09-21)

Run 02 (`build/testnet-v0-payment-tjs230-02`, container `meow-tjs230-1459651`) resumed the
accepted checkpoint unchanged after TJS-224 closed. It passed profile/P2P admission and
started native solo funding, then failed with `TimeoutError` in phase `fund_solo_A` after
1,518 s at height 25. The block timeline shows the native DAA converging by height 10 and
holding about 86 s per block against the 90 s target at difficulty 32k–46k on one thread,
so 100 funding blocks need about 9,000 s and the 1,500 s per-phase wait was the failing
bound. The outer runner died with its herdr session before writing its closing receipts;
the failure record is kept unchanged as `attempt-02/` with a labeled post-hoc listing
(`POSTHOC-LISTING.json`, `failure.json`). Nothing after `mining_started` is claimed for it.

Run 03 changed execution budget only, as directed by the Studio Lead and the board:
`phase_limit(count) = 120 + 2 × count × 90` s (18,120 s for the 100 funding blocks,
2,280 s for each 12-block confirmation) and the container wall bound 1,800 → 24,000 s.
One mining thread and 100 funding blocks stay, because extra threads only raise
difficulty under the DAA and the 60-block maturity plus ring-16 decoy margin depends on
the block count. No difficulty, timestamp, `generateblocks` or regtest change was made.
Because these two authored files changed, `INPUTS.sha256` for run 03 differs from run 02
by exactly the `payment.py` and `payment-journey.md` digests; the accepted TJS-229
recipe manifest `1e3b8a78…` and all 43 recipe inputs are unchanged.

Run 03 (`build/testnet-v0-payment-tjs230-03`, container `meow-tjs230-3294823`, launched
detached 02:06:26Z, finished 04:53:13Z, 10,004.9 s inside the container) returned
`result.json` **PASS** with solo funding, and the separate verifier returned
`PASS_PAYMENT_RECEIPT_RECONCILIATION`. `sha256sum -c INPUTS.sha256` verified all 48
entries; `EVIDENCE.sha256` verified all public files. All six owned processes exited 0,
no memory events, peak container memory 2.70 GiB of 4 GiB.

| Check | Observed |
| --- | --- |
| Funding tip | height 100, native cumulative work 0x36bb67 |
| A balance after funding | 900 MEOW total, 369 MEOW unlocked |
| Payment A→B (peer 0 → peer 1) | 5 MEOW, fee 0.0006498 MEOW, txid `4e28f52f188ec63a…`, in both mempools, type 6, ring 16 on every input |
| A after payment | 894.9993502 MEOW = before − 5 − fee |
| B after confirmation | 5 MEOW, same block hash on both peers at height 101 |
| D restored from B's seed on peer 1 | address equal, incoming history and balances equal to B |
| Recovered spend D→A | 2 MEOW, fee 0.0004521 MEOW, txid `4fa2aa1ce64b6d15…`, both mempools, type 6, ring 16, confirmed at height 113 |
| D after store/close/open | address and full snapshot equal before and after reopen; outgoing history includes the spend |
| Daemon aggregates (both peers) | emission 1116 MEOW = 124 × 9, fees 0.0011019 MEOW = fee1 + fee2, header rewards and cumulative difficulty match |
| Final tip | height 124, `2ccf565487abc19e…`, peers converged |

Public receipts for run 03 are under `attempt-03/` in the evidence directory (large daemon
logs stay in the build directory and are covered by `attempt-03/EVIDENCE.sha256`). The
regenerated evidence manifest `MANIFEST.sha256` has SHA-256
`3aac0455f7b70fd365127f0a92d03853cf8491c1b9f51d8deb2a22afe47209a1` (49 entries); the
checkpoint manifest `03d1848b…` remains the accepted pre-execution reference.

Scope of this pass: solo-funded native RandomX/DAA on the accepted two-peer recipe with
disposable wallet RPC instances in one isolated container. It proves bounded cross-node
payment accounting, fee reconciliation, seed restore, recovered spend and reopen state.
It does not test pool-funded inputs, anonymity, FCMP, Tor/I2P, hostile remote nodes,
public transport, CLI restore or whole-service restart, and agent review is not an
external audit. `chain/test-network-payment.py` (TJS-44 writer) is bound by digest but
not committed by this writer.
