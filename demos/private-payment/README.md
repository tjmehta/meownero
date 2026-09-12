# Local private-payment and seed-recovery demo

Run from this checkout with Docker and the preserved **current fifteen-patch**
build available. No package installation or chain compilation is required.

```sh
bash demos/private-payment/run.sh \
  /tmp/meownero-wallet-verified-source-20260912 \
  /tmp/meownero-swarm-demo-payment-my-run
```

The output directory must not exist. The runner refuses any other output prefix,
checks all three release binary hashes against the handoff's current15 receipt,
mounts source and harness read-only, uses a unique container, and acquires
`/tmp/meownero-swarm-20260912-heavy.lock`. The container has no external network,
no published ports, a 512 MiB memory/swap ceiling, two CPU quota and one worker
thread per binary. It is removed on exit. The 600-second timeout starts after
lock acquisition; lock waiting itself has no deadline. No host service changes.

All addresses and keys are freshly generated test material. Wallet files and
logs stay in the private output directory; **do not fund these wallets**. The
mnemonic is passed only in memory over container loopback. Python does not
guarantee secure erasure of its string copies. This is a disposable test harness,
not a production wallet or secrets-handling design. Successful runs remove the
original recipient directory, but keep sender/recovered disposable wallets for
local debugging. Commit only the small allowlisted evidence, never wallet files.

## What the run checks

1. Create separate sender and recipient wallets; recipient starts at zero.
2. Submit 100 real block templates with fixed difficulty 1 and controlled
   historical 120-second timestamps. These are accepted by the actual daemon.
   Headers remain within the new-wallet one-day scan window. This is mainnet
   **mode on an isolated disposable chain**, not a public mainnet transaction.
3. Send exactly `123456789012` atomic units (`0.123456789012` coin) using a
   16-member ring. Construct and submit through the real wallet RPC.
4. Submit eleven more templates, refresh both wallets, and check the received
   amount, unlocked amount, matching incoming/outgoing transaction ID, and fee.
   Inclusion can occur after the first new block; the run checks actual history.
5. Query the confirmed transaction: version 2, non-null RingCT, sixteen offsets
   per input, zero public input/output amount fields. Zero fields do **not** mean
   the payment value is zero; the recipient wallet decodes its amount.
6. Close and stop the recipient process, remove its entire wallet directory,
   and restore the in-memory mnemonic at height zero in a fresh wallet process
   with an empty directory. Address, incoming history, total and unlocked balances
   must match, including after close/reopen. A deliberate local note must be lost.

The sender also receives the eleven later coinbases. Exact integer checks are:

```text
sender_after = sender_before - payment - fee + 11 × subsidy + miner_fee
miner_fee = fee
sender_after + recipient_after = 111 × subsidy
subsidy = 900000000000 atomic units
```

No float rounding or guessed fee is used. The fee cancels in the sender's final
balance because this test's sender is also the miner; the RPC fee and on-chain
fee total are separately checked. This does not imply fee-free payments.

## Limits and artifacts

`result.json` contains the checked accounting and recovery flags;
`provenance.json` identifies binaries/toolchain; `run.log` records progress.
Recorded timings are single RPC-flow diagnostics, not optimization results.
Disposable keys, transaction IDs and some transaction details vary between runs;
reproducibility means the same assertions pass, not identical transaction bytes.

This demonstrates the current ring-based payment path. It does not demonstrate
FCMP++, meaningful anonymity on this tiny fully controlled output set, network
metadata protection, production difficulty/security, normal propagation,
interactive CLI recovery, recovered-wallet spending, subaddress recovery, or
recovery of outgoing destination metadata. The local-note test is only evidence
about that note. The original successful shared coinbase test remains untouched.

For the bounded optimization materials, see [challenge.md](challenge.md).
For the verified result, see [the track report](../../research/swarm-demo-2026-09-12.md).
