# Observed wallet↔daemon transport metadata + denial/recovery (2026-09-18)

TJS-41 transport acceptance item. The funded-wallet run
([wallet-funded](wallet-funded-2026-09-18.md)) was accepted but explicitly did
**not** test the wallet transport; a written threat model is not execution
evidence. This run supplies that evidence: the real selected wallet and daemon,
with a recording forwarding proxy on the wallet's configured daemon boundary, so
the request/connection metadata a node/on-path observer actually sees is captured,
plus one injected denial correlated with the wallet's recovery. It is not an
anonymity claim and not a Tor/I2P deployment.

## Source under test

| Item | Value |
|---|---|
| Profile | Selected 9/90 (subsidy 9 MEOW = 9,000,000,000,000 atomic) |
| Source HEAD | `7410c04bab0e304112710d63c3225c110bd8b4de` (tree `4db958cb…`) |
| Build | `build/repro-selected-20260918/selected-9-90/first/source` |
| `monerod` SHA-256 | `b79cb49dbea95c0eeff7dca8c945d65f4fab3d49fb626fcbe7a9343569d4a2c1` |
| `monero-wallet-rpc` SHA-256 | `5782abee489e8b245b42fd237ece34d6df1c67929c552960755fab41de3a921a` |
| Builder image | `sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e` |

## Boundary and method

- `chain/test-wallet-transport.py` + `chain/test-wallet-transport.sh`.
- Topology: **wallet → recording forwarding proxy (models an untrusted remote
  node / on-path observer) → daemon**, all inside a `--network none` container,
  4 GiB/2 CPU, single job under the shared heavy lock, disposable keys.
- The wallet is configured **without `--trusted-daemon`**, i.e. the realistic
  boundary to a node the operator does not run. Mining is done directly against
  the daemon (an operator action), so only genuine wallet transport crosses the
  recorded boundary.

```
flock /tmp/meownero-swarm-20260912-heavy.lock \
  bash chain/test-wallet-transport.sh \
  build/repro-selected-20260918/selected-9-90/first/source \
  build/wallet-transport-20260918/run-02
```

## Observed exposure (what the node actually saw)

Evidence: `research/evidence/wallet-transport-2026-09-18/` (result.json, harness
stdout, `transport-records.json`, image/source/binary/input receipts, MANIFEST).
21 requests over the boundary in this run:

| Path | Count | What it discloses to the node |
|---|---:|---|
| `/getheight` | 1 | wallet is polling chain tip |
| `/getblocks.bin` | 6 | wallet is scanning blocks from a start height (refresh cadence, wallet age) |
| `/json_rpc` | 9 | assorted wallet queries (fee estimate, output distribution wrappers, etc.) |
| `/get_output_distribution.bin` | 2 | decoy-selection distribution fetch preceding a spend |
| `/get_outs.bin` | 2 | the specific output set the wallet pulls to build rings |
| `/sendrawtransaction` | 1 | **first-relay origin**: this node is the first to see the broadcast tx |

Key observed facts (data, not hypothesis):

- A spend caused a distinct, node-visible sequence: distribution fetch →
  `/get_outs.bin` → `/sendrawtransaction`. The submitting node is the tx's
  first-relay origin.
- The client source the proxy recorded is `127.0.0.1` (loopback in this isolated
  run).
- The recording stores only `method, path, req_bytes, req_sha256 (truncated),
  client, t`. No bodies, mnemonic, keys, or addresses; `scan_for_secrets()`
  asserts no 25-word phrase and no raw 32-byte hex in the records.

## Denial / recovery correlation (one injected fault)

The proxy denied the **next `/getblocks.bin`** with a `503 {"status":"Failed",
"untrusted":true}`, modelling an unavailable/untrusted node mid-refresh:

- The denial was exercised (`denied_path` = `/getblocks.bin`).
- The wallet **observed the daemon error and did not crash** (both processes
  stayed up).
- After the node stopped refusing, two consecutive refreshes **converged** to the
  same balance, equal to coinbase × subsidy (the self-transfer and self-mined fee
  net to zero). The wallet recovered its correct view without intervention.

## Hypotheses NOT tested here (kept separate)

- On a real network the node sees the operator's **public IP**, not `127.0.0.1`,
  unless Tor/I2P is used — not deployed or tested here.
- Repeated `/get_outs.bin` / `/get_transactions` patterns narrow wallet-owned
  outputs by intersection over time; not quantified.
- Timing/traffic analysis resistance and Dandelion++ relay-origin hiding are not
  evaluated.

## Limits and exclusions

- Single isolated run; loopback boundary; empty non-fee blocks; fixed difficulty.
- Untrusted-daemon RPC path only; no public network, no Tor/I2P, no real funds.
- One denial class (`503` on a `.bin` sync call). Connection-drop mid-stream and
  malformed-response classes are covered separately by the preserved 52-case
  restricted-controller checkpoint (`chain/privacy-test.py`), unchanged here.
- Not release certification; findings await independent TJS-43 review.

## Next bounded action

Independent TJS-43 review of this revision alongside the funded-wallet evidence.
Candidate follow-ups (not done here, and out of the current bounded scope):
quantify output-set intersection over repeated refreshes; exercise a
connection-drop mid-`sendrawtransaction`; record exposure against a genuinely
separate second node.
