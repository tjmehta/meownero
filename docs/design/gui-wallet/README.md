# Meownero desktop wallet: concept and prototype

Design candidate for TJS-1992 (2026-10-10). [`prototype.html`](prototype.html)
is a self-contained interactive prototype: open it in any current browser. It
uses mock data only, talks to no node or wallet, and has no remote fonts,
scripts or tracking. It is not a release and does not describe tested software.

TJ, Meownero WhatsApp, 2026-10-10 10:16 PDT: "Wallet is one that deserves
binaries bc we want gui let the design team cook it up." The node and test kit
stay Docker-first under TJS-1882. The wallet that people download is a native
desktop app.

## The job

**Observed:** TJ wants a downloadable GUI wallet for testing. The only
wallet behaviour accepted today is the local Vanguard FCMP++/CARROT
accelerated-regtest kit (TJS-1870), driven through `monero-wallet-rpc` and
`monerod` RPC, on build-mac ARM64 in a container. There is no shared public testnet
or mainnet. TJ's presentation rule (`docs/milestones.md:95`,
`docs/spec/emission.md:95`): display may simplify, but must never round payment
input silently or show a nonzero amount as zero.

**Assumed (to verify with the first testers):** testers are crypto-curious but
not Monero experts. They will try create, receive, send and restore once or
twice, and the biggest risks are mistaking test coins for money, losing recovery
words, and misreading a payment's state.

Primary job: *let me try Meownero privately, with a wallet I can recover, without
ever confusing test coins with real money.*

## Concept: quiet ledger, loud network

- **The network chooses the colour.** The single accent is bound to the network
  the node reports: violet for the local regtest chain, teal for a future
  testnet. Coin gold, the brand's money colour, is reserved for a mainnet build
  that does not exist. A screenshot of a test wallet cannot pass for a real one.
- **The network is always named.** A ribbon under the title bar states the
  network and that test coins have no value. The title bar, the sidebar, the
  review step and the first-run screen repeat it, and none of them can be
  dismissed. The label comes from the node's reported network, not from the
  address format: the current kit produces upstream Monero-style `4…`
  addresses (seen in `research/evidence/vanguard-daemon-soak-tjs1816-2026-10-08`),
  while Meownero's testnet identity is `T…` (`docs/spec/network-identity.md`).
- **The ledger is quiet.** Exact amounts, plain words, and no prices, charts or
  speculation. Privacy reads as normal behaviour: "Sender not shown", not
  "anonymous".
- **The cat stays on the coin.** The app mark is an outlined coin holding the
  unimpressed cat from the site coin. Copy has no puns in money moments.

Visual priorities on the main screen: (1) spendable balance and network
identity, (2) Receive and Send, (3) recent activity and sync status.

## Experience contract

**Key objects:** network, node connection (own or someone else's), wallet (file,
password, 25 recovery words, starting block), address, payment (incoming,
outgoing, grouped mined blocks), and balance (spendable, unlocking, total).

**State transitions the UI must represent:**

| Object | States |
| --- | --- |
| Outgoing payment | building → handing to node → pending → *n* of 10 confirmations → confirmed. Branches: node refuses (nothing sent, balance unchanged); connection drops (**unknown**: never shown as sent or failed, never retried automatically, resolves when the node returns) |
| Incoming payment | pending → *n* of 10 → spendable. Mined coins: unlocking for 60 blocks |
| Chain reorganization | confirmed → pending → confirmed, with a banner explaining the balance change |
| New wallet | name and password → recovery words (hidden until revealed) → word check → ready |
| Restore | words (count, word list and check-word errors) → starting block (future-block error) and new password → scanning → restored, with the note that local notes do not return |
| Wallet file | locked ↔ unlocked; wrong password error |
| Node | connecting → node catching up → wallet scanning → synced; unreachable (last-known balance, sending paused); wrong network (nothing loaded); someone else's node (exposure explained) |

**Amount rule (TJ decision):** amounts are integers of atomic units (12 decimal
places). Compact display shows at most four decimals, *truncated* and marked
with "…" when digits are hidden; amounts below 0.0001 show every digit, so
1 atomic unit reads `0.000000000001`. "Show every digit" and every review and
detail view show the lossless value. Input with more than 12 decimals is
refused with a message, never rounded. The prototype includes a 1-atomic-unit
wallet, a 3,153,600.123456789012 balance and a 13-decimal input to prove this.

**Shared tokens:** warm neutrals from the site (`site/src/app/globals.css`), one
network accent (`--net`) with soft and on-accent variants per network and
appearance, separate warning and danger colours, and no success green except the
connection dot. Fonts are the platform's system font, with monospace for
addresses and IDs. Radius is 8 px for controls and 12 px for cards. Motion: 180 ms
ease-out page entry and 200 ms sheets, with no movement under reduced motion.

**Left out on purpose:** fiat values, price tickers or charts; buy, swap or
exchange buttons; green/red profit-and-loss colouring; "anonymous",
"untraceable", "invisible" or "no trace" wording; hooded-hacker, neon or matrix
imagery; alley cats, glowing eyes or invented cat mythology; gold accents on any
test network; confetti or celebration after sending; countdowns or launch
promises; balances truncated to `0.00`; copy buttons for recovery words; generic
pure-black backgrounds; and pill-shaped buttons.

**Platforms:** macOS, Windows and Linux are *packaging targets* with native title
bars, system fonts and appearance that follows the system (all three window
styles can be switched in the prototype). No GUI build exists, so none is tested
or signed.

## What is real: capability tiers

The prototype's dashed labels (toggle under "Capability labels") mark each
feature:

| Tier | Meaning | Features |
| --- | --- | --- |
| **A** | Exercised in the accepted Vanguard kit (TJS-1870) through the named RPC | `create_wallet`, `get_address`, `query_key` (mnemonic), `restore_deterministic_wallet` with restore height, `rescan_blockchain`/`refresh`, `get_balance` (total vs unlocked), single-recipient `transfer`, `get_transfers`/`incoming_transfers`, reorg rollback, key-image replay refusal, daemon `get_info`/`get_connections`, regtest `generateblocks` for test coins |
| **B** | Upstream RPC exists, but it is not exercised in the current kit, or only in the older RingCT `chain/` lineage | wallet password (the kit uses an empty one), `open_wallet`/`close_wallet`, `validate_address`, fee preview (`do_not_relay` + `relay_tx`), subaddresses (`create_address`), Max (`sweep_all`), `change_wallet_password`, untrusted remote node mode, the unlock windows (60 mined / 10 other) as applied to the kit |
| **C** | Prototype only: GUI behaviour with nothing behind it yet | first-run and network choice, word check, compact amount display, grouped mined blocks, local notes, QR rendering, offline/wrong-network handling, the unknown-relay state, testnet (not live), Tor/I2P (untested), file location |

The in-app "About this test build" panel lists only tier A as "works today".

## Reviewing the prototype

- **Jump to screen** reaches every screen. The "Error states" group stages 17
  failures directly, such as an address typo, a 13-decimal amount, node refusal,
  a dropped connection, wrong network, reorg, misspelled recovery word, check-word
  mismatch and wrong password.
- **Network**, **Node and sync**, **Wallet contents**, **Chain** (add blocks,
  reorg) and **Next send result** change the live state, so a payment can be
  followed from review to confirmed.
- **Platform window**, **Appearance** and **Capability labels** change the
  presentation only.

## Implementation handoff (draft; final after privacy and critique review)

1. **Drive the proven boundary; do not reimplement it.** The GUI is a native
   shell over the exact `monero-wallet-rpc` and `monerod` methods in tier A.
   Wallet and crypto logic stay in those programs. Tier B items need their own
   implementation evidence before they ship enabled; tier C items are GUI work.
2. **First blocker, owned by implementation:** there are no native per-OS
   wallet-engine binaries. Today's accepted binaries are ARM64 Linux ELF in a
   container. The GUI needs `monero-wallet-rpc` (or the wallet library) built
   natively for each packaging target. It connects to the node in the Docker kit
   over local RPC.
3. **Stack (recommendation, the implementation owner decides):** a small native
   shell such as Tauri 2 can launch the wallet engine as a sidecar and reuse this
   prototype's layout directly. Qt/QML follows the upstream Monero GUI precedent
   (PLAN.md v1.x) but needs a heavier toolchain. Electron is not recommended,
   because of its size and attack surface for a wallet.
4. **Amounts:** carry atomic units as strings or 64-bit integers end to end
   (use RPC `wide_*` fields where totals can exceed u64). Never use floating
   point. Port `parseAmount`/`fmt` semantics and their test cases from the
   prototype.
5. **States:** implement every transition in the experience contract,
   especially the unknown-relay branch and the reorg banner, before visual
   polish.
6. **Acceptance for the build:** on the actual packaged binary per target, a
   tester completes create → back up → get test coins → receive → send → restore
   → spend; the 1-atomic, large-balance and 13-decimal cases behave as above; the
   network label matches the node's reported network; keyboard-only and screen
   reader passes; signing status and the tested OS/arch are reported from
   execution evidence only.

Privacy and capability constraints are pending from the Wallet & Transport
Privacy specialist (TJS-1994). An independent design critique is pending as
well. Both will be folded into this section.
