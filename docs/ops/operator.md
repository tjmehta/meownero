# Operator guide (alpha, provisional lineage) — local networks only

**Scope:** running Meownero nodes and wallets on a private/devnet. There is no public network; nothing here is a launch instruction. Binaries come from `chain/build.sh` (Docker) and are unsigned until the release plan exists (PLAN §9.4–9.5).

## Node

```
monerod --data-dir <dir> --non-interactive --no-igd --hide-my-port \
        --p2p-bind-ip 0.0.0.0 --rpc-bind-ip 127.0.0.1 \
        --add-exclusive-node <peer>:19080          # repeat per peer; NO seeds ship with the binary
```

Facts an operator must know:

- **No shipped seeds, inherited checkpoints or update/download authorities.** A fresh node with no `--add-exclusive-node`/`--add-peer`/`--seed-node` has zero peers and will sit at its own genesis. This is deliberate until the seed policy is decided (PLAN §9.5; `docs/spec/network-identity.md` §4). Eclipse risk is entirely the operator's peer list (threat model T9).
- **Ports:** 19080 P2P, 19081 RPC, 19082 ZMQ (testnet 29xxx, stagenet 39xxx). Never expose 19081 without `--restricted-rpc` (CVE-2025-26819 class; threat model T8).
- **Data dir:** `~/.meownero` by default (`CRYPTONOTE_NAME`).
- **Difficulty:** inherited Monero DAA; launch floor undecided (`docs/spec/difficulty.md`). Devnets use `--fixed-difficulty 1`.
- **Confirmations:** no checkpoints exist; treat depth as the only finality. Confirmation guidance for a young chain is a launch-time policy (PLAN §6.4 item 4; open-questions #6).
- **Reorgs/monitoring:** watch `HEIGHT`/`REORGANIZE` in the log; an alt-chain monitor is an M2 deliverable.

## Wallet

Automation: use `monero-wallet-rpc` (deterministic JSON-RPC).

```
monero-wallet-rpc --daemon-address <node>:19081 --trusted-daemon --rpc-bind-port 19090 \
                  --wallet-dir <dir> --disable-rpc-login          # devnet only; use --rpc-login otherwise
```

`create_wallet`, `open_wallet`, `get_balance`, `transfer`, `get_transfers`, `rescan_blockchain {"hard":true}`.

CLI (`monero-wallet-cli`) caveats found on the devnet (`spikes/candidate-m/README.md`):

- `--password ''` is ignored and the CLI prompts instead; always pass a real password or `--password-file`.
- A newly generated wallet estimates its refresh height from the hard-fork table and the clock; on a fresh chain run `set refresh-from-block-height 0` then `rescan_bc hard` (each asks for the password).
- Addresses start with `M` (mainnet), `T` (testnet), `S` (stagenet). Amounts have 12 decimal places.
- **Never reuse Monero keys on Meownero** (the CLI warns about this; key reuse across forks links transactions).
- Remote nodes: prefer your own node when practical; TLS authentication and proxy routing do not make remote blockchain data trustworthy. The [metadata tests](../../research/swarm-privacy-2026-09-12.md) exercise selected malformed responses, not general malicious-node resistance (threat model T11).

### Tested local payment and metadata tools

- [Private-payment demo](../../demos/private-payment/README.md): exact atomic accounting, received-payment seed recovery and reopen with disposable wallets. Local notes are not seed-derived; the tiny controlled chain does not demonstrate meaningful anonymity.
- [Wallet metadata controls](../../research/swarm-privacy-2026-09-12.md): strict local authenticated RPC startup, explicit proxy and TLS/onion policy, plus controlled observer tests. Wallet RPC, daemon transaction relay and daemon synchronization are distinct paths. **`--no-dns` does not prevent an authenticated RPC caller from requesting OpenAlias resolution.** The launcher is not a process-wide network sandbox, and Tor alone does not remove traffic correlation.
- [P2Pool compatibility gate](../../spikes/p2pool/README.md): unmodified upstream P2Pool fails the current chain's address, subsidy and fork assumptions. This is an executable compatibility probe, not a pool launch/onboarding command.

## Supply audit (anyone can run)

`get_coinbase_tx_sum {"height":0,"count":h+1}` on any node returns `emission_amount`; for the full, unpenalized-subsidy devnet it must equal `h × 900000000000` (0.9 MEOW × height; genesis contributes 0). Account for inherited block-weight penalties when auditing other workloads. `docs/spec/emission.md`.

## What is not available

Public network, seed nodes, GUI wallet, light wallets, hardware wallets, merge-mining proxy, explorer (M2), release signatures (M3).
