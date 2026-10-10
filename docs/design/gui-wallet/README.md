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
- **The network is always named.** A ribbon under the title bar reads "Local
  regtest · Test coins only" (wording approved in TJS-1994). The title bar, the
  sidebar, the receive card, the review step and the first-run screen repeat it,
  and none of them can be dismissed. The network is shown, never chosen: there is
  no mainnet or testnet switch. The label comes from the node's reported network, not from the
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
| Outgoing payment | preparing (exact transaction built, nothing sent) → review of the exact fee → submitting → waiting to confirm → *n* of 10 confirmations → confirmed. Branches: edit (prepared transaction discarded, prepared and reviewed again); node refuses (nothing sent, balance unchanged); connection drops (**submission status unknown**: never shown as sent or failed, never retried automatically, and new payments are blocked until wallet and node reconcile) |
| Incoming payment | pending → *n* of 10 → spendable. Mined coins: unlocking for 60 blocks |
| Chain reorganization | confirmed → pending → confirmed, with a banner explaining the balance change |
| New wallet | name and password → recovery words (hidden until revealed, hidden again on leaving, no copy) → word check → ready |
| Restore | words (count, word list and check-word errors) → starting block (future-block error) and new password → scanning → restored, with the note that local notes do not return |
| Wallet file | locked ↔ unlocked; wrong password error |
| Node | connecting → node catching up → wallet scanning → synced; unreachable (last-known balance, sending paused); wrong network (nothing loaded); someone else's node (explicitly untrusted, exposure explained; not offered on the local regtest) |

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
| **A** | Backend behaviour exercised in the accepted Vanguard kit (TJS-1870) through the named RPC. Never a completed native integration | `create_wallet`, `get_address`, `query_key` (mnemonic; the reveal UI is C), `restore_deterministic_wallet` with restore height, `rescan_blockchain`/`refresh`, `get_balance` (total vs unlocked; unlock 60 mined / 10 received blocks from pinned source), `transfer` to one or two recipients, `transfer` with `do_not_relay` (exact prepared fee), `incoming_transfers` and `get_transfers {pool:true}`, reorg rollback and same-key-image refusal (scenario-bounded), daemon `get_connections`/`get_last_block_header`, regtest `generateblocks` |
| **B** | Upstream RPC exists, but it is not exercised in the current kit, or only in the older RingCT `chain/` lineage | daemon `get_info`, full in/out/failed `get_transfers` history, wallet `relay_tx` of the reviewed transaction, wallet password and `change_wallet_password`, `open_wallet`/`close_wallet`, wallet and daemon RPC authentication, `validate_address` (literal only), subaddresses (`create_address`), Max (`sweep_all`), untrusted remote node mode |
| **C** | Prototype only: GUI behaviour with nothing behind it yet | first run, word check, secure seed reveal, compact amount display, grouped mined blocks, local notes, kit-wallet recipient list, QR (testnet preview only), offline/wrong-network handling, submission-unknown reconciliation, testnet (not live), Tor/I2P (untested), file location |

The in-app "About this test build" panel lists only tier A, as what the wallet engine does in the current kit; it does not call the desktop app working.

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

## Privacy and capability constraints (TJS-1994)

The Wallet & Transport Privacy specialist's `privacy-constraints` document
(TJS-1994, revision `4a98299b-dfa7-4ac8-82f9-c959af5f43eb`) is accepted in full.
The numbers below match its constraints.

| # | Constraint | Applied in revision 2 |
| --- | --- | --- |
| 1 | Label everything as local accelerated regtest; no network switching; no implied cross-platform release | Approved ribbon wording; the welcome screen shows the network and offers no choice; the testnet view is a reviewer-only, labelled design preview; an in-window "Interactive prototype · Wallet actions are simulated" marker |
| 2 | Show the exact `4…` RPC address; no `M…`/`T…` substitution; no `monero:` links; regtest sends only to session-known disposable wallets | Approved receive warning; **QR removed on regtest**; Send offers the kit's test wallets and refuses any other address on regtest |
| 3 | Unlock 60/10 blocks from pinned source; no clock-time promises | Unlock copy uses blocks only; the testnet minute estimate was removed |
| 4–5 | Loopback-only RPC with Digest auth, no `--disable-rpc-login`, no published container RPC ports, Unix-socket RPC unproven | Handoff items 2 and 4 |
| 6 | Explicit `--trusted-daemon` only for the user's own node; explicit untrusted mode otherwise | The node screen's trust row reflects the user's choice; "Someone else's node" is disabled on regtest |
| 7–9 | Password before reveal; no seed copy; hide on leave/lock; capture protection where the OS allows | Reveal is gated by the password and hidden again on leaving; recording warning before reveal; no copy button |
| 10 | Allowlist diagnostics; no seed or keys in logs or crash reports; no zeroization claims | Handoff item 4 |
| 11 | Explain observer boundaries without anonymity claims | Approved remote-node and privacy wording in the node screen and the About sheet |
| 12 | Tor/I2P and OpenAlias disabled; literal addresses only | Tor/I2P shown disabled; `validate_address {any_net_type:false, allow_openalias:false}` in the handoff |
| 13 | A seed restores on-chain funds, not notes, labels or contacts | Approved restore wording; restore-height guidance ("a block before your first payment") |
| 14 | Distinguish prepared, submitting, unknown, in pool, confirmed and unlocked; reconcile before another payment | New preparing step, "Submission status unknown" with send gating and "Check with node" |
| 15 | Exact fee from the prepared transaction, never rebuilt after approval; banned claims | Review shows the prepared fee (no "estimate"), editing re-prepares; banned words are absent (checked across 128 renders) |

## Implementation handoff (draft; final after the design critique)

1. **Drive the proven boundary; do not reimplement it.** The GUI is a native
   shell over the exact `monero-wallet-rpc` and `monerod` methods in tier A.
   Wallet and crypto logic stay in those programs. Tier B items need their own
   implementation evidence before they ship enabled; tier C items are GUI work.
2. **First blockers, owned by implementation:**
   - There are no native per-OS wallet-engine binaries. Today's accepted
     binaries are ARM64 Linux ELF in a container. The GUI needs
     `monero-wallet-rpc` (or the wallet library) built natively for each
     packaging target.
   - **Open decision: how the native GUI reaches the kit's node.** The kit's
     container is network-disabled, and TJS-1994 #4 forbids publishing container
     RPC ports. The options are a loopback-only published port with RPC
     authentication (needs the privacy specialist's acceptance), a mounted Unix
     socket (unproven, #5), or a native node on the host. The implementation
     owner proposes one; the privacy specialist accepts or rejects it.
3. **Stack: decided in TJS-1996, not here.** TJ (WhatsApp, 2026-10-10 10:22
   PDT) asked for a native cross-platform UI with shared code, no Electron, and
   native rendering preferred over a web wrapper. The studio lead owns that
   decision in TJS-1996. This HTML prototype is a review artifact for layout,
   states and copy. Its markup is not meant to ship. Whatever stack is chosen
   must reproduce the experience contract above: network-bound accent, platform
   title bars and system fonts, appearance that follows the system, keyboard and
   screen-reader access, and every listed state.
4. **Boundaries (TJS-1994):**
   - Wallet RPC is bound to explicit loopback with Digest auth and fresh
     credentials kept away from the UI layer.
   - Trust flags are always passed explicitly.
   - Before `query_key`, the GUI checks the wallet password itself, because the
     RPC doesn't.
   - Diagnostics are allowlisted, never redacted after the fact.
   - Addresses go through `validate_address {any_net_type:false, allow_openalias:false}`.
   - Payments are prepared with `do_not_relay`, reviewed, then the same
     transaction is relayed.
   - On a dropped submit, the attempt's identity is kept and reconciled before
     any other payment.
5. **Amounts:** carry atomic units as strings or 64-bit integers end to end
   (use RPC `wide_*` fields where totals can exceed u64). Never use floating
   point. Port `parseAmount`/`fmt` semantics and their test cases from the
   prototype.
6. **States:** implement every transition in the experience contract,
   especially the unknown-relay branch and the reorg banner, before visual
   polish.
7. **Acceptance for the build:** on the actual packaged binary per target, a
   tester completes create → back up → get test coins → receive → send → restore
   → spend; the 1-atomic, large-balance and 13-decimal cases behave as above; the
   network label matches the node's reported network; keyboard-only and screen
   reader passes; signing status and the tested OS/arch are reported from
   execution evidence only.

The independent design critique (TJS-1999) reviews candidate `3fc9e0c`. Its
findings will be mapped onto this revision and resolved here.
