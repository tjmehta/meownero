# Network identity specification v1 (provisional — Candidate M lineage)

**Status:** provisional; values are the Stage 2 control's and become binding only when ADR-001 is signed and the M1 patch series is cut. Mainnet values in particular are **not frozen** (PLAN §8.3: parameters freeze at T−4 weeks, a human gate). **Implementation:** `spikes/candidate-m/apply.py` → `cryptonote_config.h`, `hardforks.cpp`, `checkpoints.cpp`, `blocks.cpp`, `net_node.h/.inl`, `cryptonote_core.cpp`.

## 1. Names and identifiers

| Item | Mainnet | Testnet | Stagenet |
|---|---|---|---|
| `CRYPTONOTE_NAME` (data dir `~/.meownero`) | meownero | meownero/testnet | meownero/stagenet |
| Network ID (16 bytes) | sha256("meownero-mainnet-network-id-v1")[0:16] = `887D7D6E82AB5C036392F4DBA8949B11` | sha256("meownero-testnet-network-id-v1")[0:16] = `36A4BF5FA01CA0B6C3BB7F9506D14053` | sha256("meownero-stagenet-network-id-v1")[0:16] = `9E6E055F00F0AC1BD8CA7490F0A4252A` |
| P2P / RPC / ZMQ ports | 19080 / 19081 / 19082 | 29080 / 29081 / 29082 | 39080 / 39081 / 39082 |
| Address prefix (standard / integrated / subaddress) | 120 / 121 / 123 → `M5…ME` / `ME…MQ` / `Ma…Mj` | 156 / 157 / 158 → `T6…` / `TG…` / `TR…` | 150 / 151 / 152 → `S6…` / `SF…` / `SR…` |
| Genesis nonce | 90000 | 90001 | 90002 |

Address prefix derivation: Monero base58 encodes 8-byte blocks into 11 characters; the leading character is fixed by the prefix varint's top bits. Base58 has no `O`, so "MEOW" cannot lead an address. `M` (index 20) is reachable only with single-byte prefixes 120–124; `T`/`S` (indices 25/24) need two-byte varints ≥ 128. Values verified by sampling 3,000 random keys per prefix (`spikes/candidate-m/README.md`).

## 2. Genesis block

- Coinbase: v2 transaction, `RCTTypeNull`, `unlock_time = 60`, one `txin_gen` at height 0, **one output of amount 0** (`txout_to_key`), `tx_extra` = tx pubkey. Output key and tx pubkey are Monero's public genesis keys; with amount 0 nothing is claimable. Blob: `023c01ff000100029b2e…890d100` (75 bytes, `GENESIS_TX`).
- A v1 zero-amount output is invalid on this lineage ("RCT output without commitment"), hence v2.
- Genesis pays 0 by consensus on both template and validation paths, so `supply(h) = h × 0.9` exactly (emission spec §2).
- Genesis block header: major/minor version 1, timestamp 0, nonce per network; hash is computed at first start and is **not** hardcoded as a checkpoint. **Mainnet genesis timestamp/message are chosen at launch (PLAN §8.2), so the mainnet genesis hash is not final.**

## 3. Hard-fork table (mainnet)

Fresh chain: versions 1..16 activate at heights 1..16 with strictly increasing times (2026-09-05 UTC + version). From height 16 the chain runs upstream v16 consensus (RingCT/CLSAG, BP+, ring 16, view tags, tagged outputs, per-byte dynamic fee). `mainnet_hard_fork_version_1_till = 1`. Testnet/stagenet tables are still Monero's and must be replaced before either network is used.

## 4. Removed trust surfaces (must stay removed)

| Surface | Upstream | Meownero |
|---|---|---|
| Hardcoded checkpoints | mainnet/testnet/stagenet lists | none |
| Embedded block-hash blobs (`blocks.cpp`) | Monero chain | none |
| DNS checkpoints (MoneroPulse) | 4 domains | `load_checkpoints_from_dns` returns true immediately |
| IP seed nodes | 6 mainnet IPs | none (operators pass `--seed-node`/`--add-peer`) |
| DNS seed hostnames | 4 moneroseeds domains | none |
| Tor / I2P seeds | 6 / 3 | none |
| Update checks | default `notify` | default `disabled` |

Seed/bootstrap policy for launch (which hosts, who runs them, DNS or not) is PLAN §9.5 / open-questions territory — a human decision, not a code default.

## 5. Not yet decided / not yet done

- Difficulty launch floor and future-time-limit tightening (E5 rev 2; M1).
- Wallet-facing strings and defaults in `simplewallet` (still say Monero in places).
- `version.cpp` release naming.
- Testnet/stagenet hard-fork tables and genesis (control only exercised mainnet).
- Seed infrastructure and DNS (human).
