# Native-network payment and recovery journey

TJS-230 adds the send/fee/recovery journey to the accepted TJS-229 two-peer
candidate. The original launcher and its 43-file manifest remain unchanged.
`payment.py` imports its profile validation, baseline validation, binary pin,
image pin and daemon RPC helper. It uses the same daemon arguments and ports.
The accepted recipe manifest itself is pinned to SHA-256
`1e3b8a784828b05634abd4b4ac22ba7cc83652b32af023c71c146f3216a5e59f`.
The wallet binary is additionally pinned to the accepted TJS-40/TJS-44 bytes.

This run uses fresh solo-mined inputs. It neither reads nor accepts pool exports.
TJS-224 must verify the F4 writer's exports before any pool-funded extension.
Existing TJS-44 component receipts remain valid; this run tests their integration
with the native-miner recipe and adds an explicit wallet close/open check.

Run from the repository root, using a new path each time:

```sh
python3 -B chain/testnet-v0/payment.py --work build/testnet-v0-payment-01 --check-only
python3 -B chain/testnet-v0/payment.py --work build/testnet-v0-payment-01
python3 -B chain/testnet-v0/verify-payment.py build/testnet-v0-payment-01
sha256sum -c build/testnet-v0-payment-01/INPUTS.sha256
```

Admission checks require the accepted source/recipe files and binaries to exist.
The execution requires the shared heavy-work lock and at least 5 GiB available
RAM and disk. Exit 75 means another worker owns the lock. Keep that refusal
receipt, wait for its owner to finish, and use a new output directory. Never
stop the other worker. There is no background retry or automatic resume.

The container has no external network or published ports, 4 GiB RAM without
swap, two CPU quotas and 256 processes. All P2P and RPC addresses are container
loopback. This runs the selected profile's mainnet **mode** only inside that
isolation; it is not the public Monero or a public Meownero network. There are no
fixed-difficulty, timestamp, `generateblocks` or block-copy overrides.

The journey creates disposable A and sink S wallets on peer 0, recipient B and
fresh restoration wallet D on peer 1. It mines at least 100 blocks to A, sends
5 MEOW to B, witnesses both mempools, then mines at least 12 blocks to S.
The sender debit, recipient credit, decoded fee and type-6/ring-16 inputs must
agree. D restores B's in-memory seed at height zero and must match its address,
incoming history, total balance and unlocked balance. D sends 2 MEOW back to A,
again with both mempools and canonical confirmations witnessed. D is stored,
closed and reopened; address, balances, incoming and outgoing history must match.
Both daemon aggregates must agree with the wallets' fees, the canonical header
rewards, issuance and actual cumulative work.

Each mining phase is bounded to twice its DAA-expected time plus slack
(18,120 s for the 100 funding blocks, 2,280 s for each 12-block confirmation),
and the whole container to 24,000 seconds plus forced cleanup. The first bound
of 1,500 s per phase failed in run 02 at height 25 with the DAA already holding
about 86 s per block against the 90 s target; only these time budgets changed.
More mining threads would raise difficulty, not block rate, so one thread stays.
A timeout is an incomplete journey, never permission to lower difficulty, alter
timestamps or substitute the old regtest receipt. `progress.json` identifies the last reached stage.
All owned processes are stopped on exit. No claim of payment/recovery success
is valid until `result.json` says PASS and the separate verifier passes.

Public receipts are top-level files in the work directory, with
`EVIDENCE.sha256`. `INPUTS.sha256` binds the accepted recipe and new journey.
`process-commands.json` records exact process commands; structured progress
records mining phases and public transaction observations. The mining address
is deliberately omitted from the public mining-call receipt. RPC bodies,
mnemonics, private keys and wallet RPC responses are never logged by the runner.

`WORK/data` is private local state: it includes wallet files with disposable
keys, wallet logs and chain databases. Do not archive or publish that directory.
Do not archive the entire work directory. Copy only the top-level files covered
by `EVIDENCE.sha256`, after reviewing them for secrets. The runner does not delete
private state or offer a resume path.

The observer boundary remains explicit. Each trusted wallet daemon sees wallet
sync/output requests and the origin of submitted transactions. The other peer
sees relayed transaction bytes and timing. Wallet RPC processes and the local
operator can access wallet secrets; their unauthenticated endpoints are allowed
only in this isolated namespace. Seeds are generated and restored in memory,
not put on command lines or in public receipts. This test proves bounded
accounting and recovery behavior only. It does not test anonymity, FCMP,
Tor/I2P, hostile remote nodes, public transport, CLI restore, pool recovery or
whole-service restart. TJS-44 transport evidence retains its original scope.

The receipt verifier is a separate arithmetic and consistency check, not a
second operator, external audit or broader milestone acceptance.
