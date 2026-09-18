# Funded wallet integration — send, restore-then-spend, fees, aggregate (2026-09-18)

TJS-41. Extends the coinbase-only seed-recovery evidence to the untested funded
wallet paths with the real selected daemon and wallet, on an isolated chain. This
is a bounded local verification, not release certification; findings are handed to
the independent TJS-43 review.

## Source under test

| Item | Value |
|---|---|
| Profile | Selected 9/90 (subsidy 9 MEOW = 9,000,000,000,000 atomic, `COIN = 10^12`) |
| Source HEAD | `7410c04bab0e304112710d63c3225c110bd8b4de` (tree `4db958cb…`) |
| Build | `build/repro-selected-20260918/selected-9-90/first/source` (TJS-40 reproduction pair, first clean build) |
| `monerod` SHA-256 | `b79cb49dbea95c0eeff7dca8c945d65f4fab3d49fb626fcbe7a9343569d4a2c1` |
| `monero-wallet-rpc` SHA-256 | `5782abee489e8b245b42fd237ece34d6df1c67929c552960755fab41de3a921a` |
| Builder image | `sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e` |

The selected 9/90 subsidy is a reversible working-tree overlay (emission spec v2),
so the Git HEAD is the historical source revision while the built binary emits
9 MEOW/block. The harness derives and asserts the 9 MEOW subsidy empirically from
mined coinbase rather than trusting the label.

## Harness and command

- `chain/test-wallet-funded.py` — the integration script (runs inside the builder).
- `chain/test-wallet-funded.sh` — isolation wrapper: pinned builder image,
  `--network none`, 4 GiB/2 CPU, records source revision and binary/input hashes.

```
flock /tmp/meownero-swarm-20260912-heavy.lock \
  bash chain/test-wallet-funded.sh \
  build/repro-selected-20260918/selected-9-90/first/source \
  build/wallet-funded-20260918/run-04
```

Single job under the shared heavy lock; available memory was 16.1 GiB, above the
5 GiB preflight. RandomX mining needs its ~2 GiB dataset, so the container cap is
4 GiB (a 2 GiB cap produced `std::bad_alloc` in the miner thread). No host service
was stopped. All keys are disposable test keys on an isolated fixed-difficulty
chain with no peers and no external networking.

## What passed (real daemon + real wallet-rpc)

All amounts are atomic units (`10^-12` MEOW). Evidence:
`research/evidence/wallet-funded-2026-09-18/` (result.json, harness stdout,
image/source/binary/input receipts, MANIFEST.sha256).

1. **receive_coinbase** — 105 coinbase blocks mined to wallet A; every coinbase
   equals 9,000,000,000,000; balance 945,000,000,000,000 = 105 × subsidy; 105
   incoming history entries summing to the balance; unlocked balance respects the
   60-block coinbase window.
2. **send_receive** — real transfer A → B of 5,000,000,000,000 with fee
   649,800,000; B's balance after confirmation is exactly the sent amount and its
   incoming history carries the txid.
3. **fee_atomic_units** — sender identity holds exactly:
   `945,000,000,000,000 − 5,000,000,000,000 − 649,800,000 = 939,999,350,200,000`.
   Confirmation blocks were mined to a separate sink wallet so the sender's only
   balance change is the spend, isolating fee arithmetic.
4. **restore_outgoing_metadata** — wallet A restored from its 25-word seed at
   height 0 into a fresh wallet C. C's balance and incoming history match A, and
   **C recovered the outgoing spend (txid + fee) purely from the chain rescan** —
   the previously untested "outgoing metadata recovery" gap.
5. **restore_then_spend** — the restored wallet C spent 3,000,000,000,000 to B
   (fee 649,800,000); B's balance becomes 8,000,000,000,000 (5 + 3) and C's
   balance identity holds exactly. This closes "spending after restore".
6. **reopen** — closing and reopening C reproduces balance, incoming and outgoing
   history byte-for-byte.
7. **aggregate_reporting** — with the real daemon, `get_coinbase_tx_sum(0, 236)`
   returns emission 2,115,000,000,000,000 = 235 × subsidy, and fee_amount
   1,299,600,000, which **exactly equals the sum of the two wallet-reported fees**.
   This ties the daemon's aggregate emission/fee tally to the wallets' own
   accounting on live data, extending the prior synthetic 40-case reporting test.

## Observer / transport threat model (documented, not claimed anonymous)

This run does **not** test transport privacy. The wallet↔daemon channel is
trusted loopback HTTP inside a `--network none` namespace. It proves fund
mechanics and accounting, not unlinkability. Against a **remote / untrusted node**,
the operator should assume the node observes at least:

- the wallet's **network source** (IP/onion) and connection timing;
- the **set of transactions and outputs the wallet fetches** (`/get_transactions`,
  `/get_outs`, `/get_o_indexes`, `/is_key_image_spent`), which narrows the wallet's
  owned outputs and spends by intersection over time;
- the **restore height** and refresh cadence, which bound wallet age and activity;
- for a submitting wallet, the **first node to see a broadcast tx** (first-relay
  origin), absent Dandelion++/Tor/i2p hardening.

On-chain, ring/CLSAG membership provides the usual sender ambiguity, but a small
private chain gives a small decoy pool; that is a devnet artifact, not a mainnet
anonymity measurement. Controller-side handling of a hostile/anomalous daemon is
covered separately by the preserved 52-case restricted controller checkpoint
(`chain/privacy-test.py`); this task did not modify it.

## Limits and exclusions

- Single run; identities are exact and self-checking, but this is not a repeated
  statistical study. A reviewer can re-run via the committed harness.
- Fixed difficulty 1, offline single daemon, empty non-fee blocks; no relay,
  reorg, or fee-market dynamics. Fee here is the wallet's default estimate, not a
  congestion-tested value.
- Ring/CLSAG defaults over a small private-chain decoy pool; not a privacy
  (unlinkability) measurement.
- Transport hardening (Tor/i2p, untrusted remote node, subaddress/integrated
  flows, multi-destination and sweep paths) not exercised.
- Interactive `monero-wallet-cli` restoration remains untested (RPC path only).
- Selected 9/90 only; fallback 12/120 binaries exist and the harness is
  profile-agnostic, but this receipt is 9/90.

## Next bounded action

Hand to independent TJS-43 review. Candidate follow-ups (not done here): repeat on
the 12/120 fallback binary; add sweep_all / multi-destination and subaddress
cases; exercise an untrusted-node proxy to record the observer surface as data;
add interactive CLI restore.
