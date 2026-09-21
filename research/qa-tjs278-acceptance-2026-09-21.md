# TJS-278 — QA acceptance of testnet v0 milestone checks 4–5 on TJS-230 run-03 (86226ae)

QA/Release (agent `0b42215e-c278-424b-b68b-7b731047a093`), 2026-09-21. Independent acceptance
of the freeze-audit rows "Send, confirm and reconcile fees across nodes" (check 4) and
"Restore payout wallet, spend, reopen" (check 5) from `docs/testnet-v0-freeze-tjs223-2026-09-20.md`
against the exact TJS-230 run-03 candidate. Read-only on every candidate file; no fix applied;
no daemon, container or heavy lock used. **Agent acceptance, not an external audit; no launch,
mainnet, release or FCMP authority.** Findings route to the Wallet & Transport Privacy role on TJS-230.

## 1. Candidate binding (verified on disk before any other work)

| Input | Value | Check |
|---|---|---|
| Repo HEAD | `86226ae9899f2a87962ef0292a8ae7f7fe6e778d` on `m1/september-7-verification` | equals the issue's `86226ae` |
| Report `research/testnet-v0-payment-tjs230-2026-09-20.md` | `4b549cba0015fdc27d1d708b09e4b8f589ccc0e7fbc20077768ec3dbb66e2daa` | byte-equal to TJS-230 document `tjs230-result` (rev `d5ec2371…`) |
| Evidence manifest `research/evidence/testnet-v0-payment-tjs230-2026-09-20/MANIFEST.sha256` | 49 entries, `3aac0455f7b70fd365127f0a92d03853cf8491c1b9f51d8deb2a22afe47209a1` | `sha256sum -c`: **49 OK** (`manifest-check.txt`) |
| `attempt-03/EVIDENCE.sha256` against `build/testnet-v0-payment-tjs230-03` | 25 entries | **25 OK** (`evidence-check.txt`); all 20 non-log receipts byte-equal between evidence dir and work dir (`attempt03-vs-workdir.txt`) |
| `attempt-03/INPUTS.sha256` against the repo | 48 entries | **48 OK** (`inputs-check.txt`); includes the accepted TJS-229 recipe manifest `1e3b8a78…` |
| `monerod` / `monero-wallet-rpc` | `b79cb49d…4a2c1` / `5782abee…3a921a` | equal to `launch.py`, `BINARY.sha256`, repro-selected `SHA256SUMS`; same binaries as TJS-44/TJS-129/TJS-224 |
| Builder image | `sha256:10a15deb…1c3e` | `launch.py`, `container-command.json`, `docker image inspect` equal |
| Work dir receipts | `result.json` PASS, solo; `container.exit` 0; 6/6 owned exits 0; `memory.events` all 0; peak 2,895,466,496 B of 4 GiB; 10,004.9 s | as claimed in the report |

Evidence for this acceptance: `research/evidence/qa-tjs278-2026-09-21/` (18 files,
`MANIFEST.sha256` = `beeee96d5ae15af1a8383f3aa29d5dc9b1772c2a0b9e09bec8b9857a3369cce8`),
regenerable with `bash research/evidence/qa-tjs278-2026-09-21/collect.sh` from the repo root.

## 2. Verdict

**PASS — accepted on receipts.** Milestone checks 4 and 5 are met by run-03 for the stated
scope (solo-funded native RandomX/DAA, accepted two-peer recipe, disposable wallet RPC, one
isolated container). Every quantity the freeze audit names was re-derived by QA-authored code
from the retained public receipts and corroborated in the retained daemon logs; the candidate's
own verifier was exercised with positive and tampered negative controls.

QA did **not** execute the journey itself. The shared heavy lock was free at 05:08Z–05:16Z and
no `meow-*` container was running, but the M3 worker (TJS-242, herdr tab `w1V:tF`) was live and
the board's run-03 authorization on TJS-230 said "no competing M3 heavy workload". A fresh run
holds the lock for about 10,000 s, so taking it would have contended with M3. Per the issue's
own fallback clause this acceptance rests on receipts, and it says so here explicitly. Only the
lock-free operator steps were exercised (§4).

## 3. Independent re-derivation (`rederive.py`, 38/38 OK)

Amounts in atomic units (1 MEOW = 10^12). Sources: `result.json`, `headers.json`, `rpc-final.json`.

| Claim (freeze row) | Re-derived | Source |
|---|---|---|
| Funding = 100 blocks × 9 MEOW | 900,000,000,000,000 at tip 100 | `solo_funded` |
| Sender debit = amount + fee (check 4) | 900,000,000,000,000 − 5,000,000,000,000 − 649,800,000 = 894,999,350,200,000 | `payment_confirmed.sender_after` |
| Recipient credit = amount (check 4) | 5,000,000,000,000; incoming `[tx1, 5 MEOW]` | `payment_confirmed.recipient/incoming` |
| Confirmation same height + hash on both peers (check 4) | height 101, `67711ae5…` on node 0 and node 1; equals `headers[n][101].hash` | `confirmations`, `headers.json` |
| Type-6 / ring-16 on every input, both peers, both txs | tx1 rings `[16,16]`, tx2 `[16]`; `rct_type` 6, version 2, `in_pool` true on nodes 0 and 1 | `*_relay.decoded` |
| Both mempools witnessed | tx1 and tx2 present in node 0 and node 1 pool lists | `*_relay.pools` |
| Daemon aggregate agrees (check 4) | `fee_amount` 1,101,900,000 = 649,800,000 + 452,100,000 on **both** daemons; `emission_amount` 1,116,000,000,000,000 = 124 × 9 MEOW on both | `rpc-final.json` |
| Header rewards reconcile | Σ reward = emission + fees on both peers; block 101 = 9 MEOW + fee1, block 113 = 9 MEOW + fee2, every other mined block exactly 9 MEOW; `num_txes` 1 at 101 and 113, else 0 | `headers.json` |
| Cumulative work | Σ difficulty = 4,531,640 = `cumulative_difficulty` = `0x4525b8` = `headers[124].cumulative_difficulty`, both peers | `headers.json`, `rpc-final.json` |
| Restore on the far peer (check 5) | address equal; `original == restored` (balance, unlocked, incoming); restored balance equals recipient's post-confirmation balance | `seed_restored` |
| Recovered spend (check 5) | D debit 5 MEOW − 2 MEOW − 452,100,000 = 2,999,547,900,000; A credit 894,999,350,200,000 + 2 MEOW = 896,999,350,200,000; confirmed at 113 `3f69e389…` on both peers | `recovered_spend_confirmed` |
| Reopen preserves state (check 5) | `before == after` after store/close/open; outgoing history contains `[tx2, 2 MEOW, fee2]`; balance equals post-spend balance | `wallet_reopened` |
| Chain shape | 125 headers per peer, `prev_hash` linked, genesis `20ce111b…` reward 0 v1, all mined blocks `major_version` 16; hash and difficulty lists identical across peers; tip `2ccf5654…` at 124; `alt_blocks_count` 0, `tx_pool_size` 0, `tx_count` 2, `target` 90 | `headers.json`, `rpc-final.json` |
| Timing / no steering | block 1 timestamp ≥ daemon `start_time`, tip ≤ `adjusted_time`; 9,982 s for 124 blocks; interval mean 81 s, median 50 s, max 400 s; difficulty 1 → ~40k by height 10 and held 37.9k–40.9k; 124 distinct nonces | `headers.json` |

Daemon-log corroboration (`daemon-log-crosscheck.txt`): `peer0.log` shows 124 `Found block`
lines including `67711ae5…` at 101 (04:24:55Z), `3f69e389…` at 113 and `2ccf5654…` at 124;
both txids "added to pool" on both peers (tx1 at 04:24:06Z on peer 0, 04:24:09Z on peer 1);
peer 1 received each of those blocks as `NOTIFY_NEW_FLUFFY_BLOCK`; `REORGANIZE` 0 and
`alternative` 0 on both peers; 125 blocks added on each. Log wall-clock (02:06:27Z–04:53:12Z)
matches the container's 10,004.9 s and the report's launch/finish times.

## 4. Operator steps exercised by QA (lock-free) and negative controls

| Step | Result |
|---|---|
| `python3 -B chain/testnet-v0/payment.py --work <fresh> --check-only` | `PASS_ADMISSION`, exit 0 (`admission.txt`) |
| `python3 -B chain/testnet-v0/verify-payment.py build/testnet-v0-payment-tjs230-03` | `PASS_PAYMENT_RECEIPT_RECONCILIATION`, fees 1,101,900,000, top 124, exit 0 (`verify-run03.txt`) |
| `sha256sum -c` INPUTS / EVIDENCE / MANIFEST | 48 / 25 / 49 OK |
| Existing work dir passed to the runner | `REFUSED: work directory must be fresh`, exit 2 (`stale-refusal.txt`) |
| Verifier on the run-02 failure record | exit 1 (missing `EVIDENCE.sha256`, see F2) (`verify-run02-negative.txt`) |
| Faithful copy of the 25 public receipts | verifier exit 0 |
| Copy with `sender_after.balance` +1 atomic and re-signed manifest | `FAIL: sender debit mismatch`, exit 1 (`tamper-refusal.txt`) |
| Copy with peer 1's block-113 confirmation hash altered and re-signed manifest | `FAIL: confirmation does not match canonical chain`, exit 1 |

## 5. Findings (route to the wallet role on TJS-230; none blocks this acceptance)

- **F1 — pinned inputs not committed at 86226ae (lineage).** Two of the 48 `INPUTS.sha256`
  entries are untracked at HEAD: `chain/test-network-payment.py` (the report acknowledges
  this) and `docs/testnet-v0-freeze-tjs223-2026-09-20.md`, which is inside the accepted
  TJS-229 43-file recipe manifest `1e3b8a78…` (`inputs-git-lineage.txt`). A clean checkout of
  `86226ae` therefore cannot pass `payment.py` admission; the bytes on this host match the pins,
  so the evidence is bound, but a second operator needs both files committed or shipped with
  the package. Suggested owner: wallet role for the TJS-44 harness file, Consensus role
  (TJS-223 author) for the freeze document; Studio Lead to route.
- **F2 — run-02 record has no `EVIDENCE.sha256`.** The outer runner died with its herdr session,
  so `attempt-02` is a labeled post-hoc listing and the verifier's rejection of run-02 is a
  missing-file refusal, not an arithmetic one. Correctly labeled by the writer; noted so nobody
  cites run-02 as a verifier negative control.
- **F3 — observation.** One `Unable to send transaction(s) via Dandelion++ stem` ERROR on peer 0
  for a two-peer loopback topology; the transaction still reached both mempools and was
  included in the next block. Not a payment defect; worth knowing when reading logs.
- **F4 — observation.** `headers.json` carries empty `pow_hash` (the RPC default without
  `fill_pow_hash`). Native PoW is evidenced by the per-block nonces and the miner's
  `Found block … for difficulty` lines, not by that field.

## 6. Open gates not covered by this candidate

- **Pool-funded inputs.** Solo funding only; the accepted F4 exports (TJS-224) were not used,
  so "TJS-44 covers the cross-node seam and F4 writer covers pool funds; the combined recipe
  must bind both" is still open for the pool half of check 5.
- **Anonymity / transport.** No Tor/I2P, hostile remote nodes, public transport, or
  network-observer claims; wallet RPC endpoints unauthenticated inside the isolated namespace only.
- **CLI restore.** Restore used `monero-wallet-rpc` `restore_deterministic_wallet`; no
  `monero-wallet-cli` restore path was exercised.
- **Service restart.** Store/close/open of one wallet RPC only; no whole daemon/pool/wallet
  restart on the same data dirs (freeze row 6 remains open).
- **Reorg with transactions** (freeze row 5), FCMP, external audit, mature-window economics.
- **Independent execution by a second operator.** Not performed here (lock deferred to M3);
  the freeze's final "operator handoff and independent acceptance" row still requires QA to run
  the packaged journey once the lock is free. Recommended as a bounded QA follow-up serialized
  after TJS-242.
- **Lineage** per F1 until both untracked inputs are committed.

## 7. What this run did not do

No daemon, wallet, container or miner was started. The heavy lock was probed with a
non-blocking `flock` and released immediately. No candidate file, manifest or Paperclip
document of another role was modified. No board card was created (TJ is WhatsApp-only).
