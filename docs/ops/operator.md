# Operator guide (alpha, provisional lineage) — local networks only

**Scope:** running Meownero nodes and wallets on a private/devnet. There is no public network; nothing here is a launch instruction. Binaries come from `chain/build.sh` (Docker) and are unsigned until the release plan exists (PLAN §9.4–9.5).

## Node

```
monerod --data-dir <dir> --non-interactive --no-igd --hide-my-port \
        --p2p-bind-ip 0.0.0.0 --rpc-bind-ip 127.0.0.1 \
        --add-exclusive-node <peer>:19080          # repeat per peer; NO seeds ship with the binary
```

Facts an operator must know:

- **No seeds, no DNS, no checkpoints, no update checks.** A fresh node with no `--add-exclusive-node`/`--add-peer`/`--seed-node` has zero peers and will sit at its own genesis. This is deliberate until the seed policy is decided (PLAN §9.5; `docs/spec/network-identity.md` §4). Eclipse risk is entirely the operator's peer list (threat model T9).
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
- Remote nodes: prefer your own node (2025 malicious-remote-node advisory, unpatched upstream; threat model T11).

## Supply audit (anyone can run)

`get_coinbase_tx_sum {"height":0,"count":h+1}` on any node returns `emission_amount`; it must equal `h × 900000000000` (0.9 MEOW × height; genesis contributes 0). `docs/spec/emission.md`.

## What is not available

Public network, seed nodes, GUI wallet, light wallets, hardware wallets, merge-mining proxy, explorer (M2), release signatures (M3).
