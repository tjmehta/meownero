# Meownero desktop wallet: concept and prototype

Design candidate for TJS-1992 (2026-10-10), revision 5. [`prototype.html`](prototype.html)
is a self-contained interactive prototype: open it in any current browser. It
uses mock data only, talks to no node or wallet, and has no remote fonts,
scripts or tracking. It is not a release and does not describe tested software.

The HTML is the **design-review artifact** for layout, states and copy. The
shipping UI is native: Qt Quick/QML with a C++ controller, per the studio's
decision in TJS-1996 (see [Native direction](#native-direction-tjs-1996)). No
WebView shell is proposed, and the prototype's markup is not meant to be ported.

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
  that does not exist. Every money figure that matters (the spendable balance,
  the review step, the Sent result and payment details) also carries a "Test
  coins" tag, so even a cropped screenshot says test (critique R1).
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
| Outgoing payment | preparing (exact transaction built, nothing sent) → review of the exact fee → submitting → waiting to confirm → *n* of 10 confirmations → confirmed. Change returns after 10 confirmations, so spendable can drop by more than was sent; the Sent result says so. Branches: edit, or leaving Send while it is preparing (prepared transaction discarded; the form keeps what was typed; prepared and reviewed again); node refuses (nothing sent, balance unchanged); connection drops (**submission status unknown**: never shown as sent or failed, never retried automatically, and new payments are blocked until wallet and node reconcile, which resolves to waiting-to-confirm or **not sent**, with the coins returned. It leaves that state only on evidence: found in the pool or a block, or proven absent by checking with the node. A new block without it proves nothing. Every resolution is announced). A submission already under way finishes even if the user leaves Send; its outcome is announced without moving focus |
| Incoming payment | pending → *n* of 10 → spendable. Mined coins: unlocking for 60 blocks |
| Chain reorganization | confirmed → pending → confirmed, with a banner explaining the balance change |
| New wallet | name and password → recovery words (hidden until revealed, hidden again on leaving, no copy) → word check → ready |
| Restore | words (count, word list and check-word errors) → starting block (future-block error) and new password → scanning → restored, with the note that local notes do not return |
| Wallet file | locked ↔ unlocked; wrong password error |
| Node and engine | connecting → node catching up → wallet scanning → synced; unreachable (last-known balance, sending and test-coin mining paused); wrong network or incompatible node version (nothing loaded); wallet engine stopped, or engine refused the app's credentials (sending paused, restart offered). Every paused reason names the part at fault, node or wallet engine, and the Node screen has its own status text for each state. Someone else's node: explicitly untrusted and not offered on the local regtest. A node change applies only on an explicit Connect; picking a choice, by click or arrow key, changes nothing until then. "Connect to someone else's node…" opens a confirmation dialog that shows the approved exposure explanation in full, with "Keep current node" (initial focus) and "Connect to someone else's node". Only that last button connects; Keep, Escape and clicking outside change nothing. Going back to your own node is one Connect with no dialog. While connected to someone else's node, the explanation stays on the Node screen above any Connect control |

**Amount rule (TJ decision):** amounts are integers of atomic units (12 decimal
places). Compact display shows at most four decimals, *truncated* and marked
with "…" when digits are hidden; amounts below 0.0001 show every digit, so
1 atomic unit reads `0.000000000001`. "Show every digit" and every review and
detail view show the lossless value. Input with more than 12 decimals is
refused with a message, never rounded. Input accepts only digits and the system
locale's decimal separator. Grouping separators, spaces and the other decimal
mark are refused with a message, so `0,5` can never be read as 5 (critique D1).
The prototype includes a 1-atomic-unit wallet, a 3,153,600.123456789012 balance,
a 13-decimal input and `PARSER_CASES`, which is checked at load and must be
ported with the parser. Send is disabled when the spendable balance can't cover a
network fee, and the app says why on Overview and on the Send page itself.

**Focus and announcements (critique D3, D4, D8, R4):**
- Dialogs are named by their heading and are modal: the background is inert,
  Tab stays inside, Escape closes, and focus returns to the control that opened
  them. A dialog that asks for consent is also described by its explanation, and
  its initial focus is on the choice that changes nothing.
- Navigation moves focus to the new page heading. In-place actions keep focus on
  the same control.
- One polite live region announces preparing, submitting, every send outcome,
  reconciliation results, copy results and node-state changes, however the
  change happens. The toast is visual only, so nothing is spoken twice.
- Field errors are linked to their field, and focus moves to the first invalid
  field (for missing recovery words, the first empty box).
- Radio choices are one Tab stop moved with the arrow keys. Toggles keep a
  constant label and report state as pressed.
- Copy reports failure instead of always saying "Copied".

**Shared tokens:** warm neutrals from the site (`site/src/app/globals.css`), one
network accent (`--net`) with soft and on-accent variants per network and
appearance, separate warning and danger colours, and no success green except the
connection dot. The warning hue sits at 45°, well away from coin gold at 85°
(T1). The "…" for hidden digits uses the muted text colour to meet 4.5:1
contrast (D9). Fonts are the platform's system font, with monospace for
addresses and IDs. Radius is 8 px for controls and 12 px for cards. Motion:
180 ms ease-out page entry and 200 ms sheets. Under reduced motion nothing moves:
the spinner pulses in opacity only, and the toast doesn't slide (D10). Recovery
word cells fit the longest upstream English word, "verification", and the sample
words include it (D2).

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
or signed. Platform conventions (T2):
- Dialog button order comes from the platform: primary first on Windows, last on
  macOS and GNOME. Qt's standard dialog button box does this.
- Shortcuts: Ctrl/⌘+1–6 for the sections, ⌘, for settings on macOS, Ctrl/⌘+L
  to lock, Escape to close dialogs, and the standard copy shortcut on a focused
  address or ID.
- Minimum window 880 × 600. The prototype's layout holds down to an 828-pixel
  window. The prototype window is a fixed 740 px tall, so the 600-px height was
  checked by overriding it in the test harness, not through a prototype control.

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
- **Network**, **Node and sync** (including engine stopped, refused credentials
  and incompatible node), **Wallet contents**, **Chain** (add blocks, reorg),
  **Next send result** and **Unknown payment resolves as** change the live state,
  so a payment can be followed from review to confirmed or not sent. **Unknown
  payment resolves as** sets what "Check with node" finds, and whether the
  unknown payment shows up in the next added block.
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
| 6 | Explicit `--trusted-daemon` only for the user's own node; explicit untrusted mode otherwise | The node screen's trust row reflects the user's choice; a node change applies only on an explicit Connect (rev 4), and someone else's node only after its confirmation dialog (rev 5); "Someone else's node" is disabled on regtest, and switching the prototype to regtest leaves it (rev 5) |
| 7–9 | Password before reveal; no seed copy; hide on leave/lock; capture protection where the OS allows | Reveal is gated by the password and hidden again on leaving; recording warning before reveal; no copy button |
| 10 | Allowlist diagnostics; no seed or keys in logs or crash reports; no zeroization claims | Handoff item 4 |
| 11 | Explain observer boundaries without anonymity claims | The approved remote-node sentence, in full, in the confirmation before connecting and on the Node screen while connected; approved privacy wording in the About sheet |
| 12 | Tor/I2P and OpenAlias disabled; literal addresses only | Tor/I2P shown disabled; `validate_address {any_net_type:false, allow_openalias:false}` in the handoff |
| 13 | A seed restores on-chain funds, not notes, labels or contacts | Approved restore wording; restore-height guidance ("a block before your first payment") |
| 14 | Distinguish prepared, submitting, unknown, in pool, confirmed and unlocked; reconcile before another payment | New preparing step, "Submission status unknown" with send gating and "Check with node" |
| 15 | Exact fee from the prepared transaction, never rebuilt after approval; banned claims | Review shows the prepared fee (no "estimate"), editing re-prepares; banned words are absent (checked across 128 renders) |

## Native direction (TJS-1996)

The Meownero Studio Lead owns the stack decision and published it as the
TJS-1996 `architecture-decision`. The board verified revision
`30797108-8f10-4ca1-b098-927b7880aba4` (SHA-256 `df6a9297…7011f2`). The current
revision `2360ff83-d6a0-4bc6-808e-ddd782c9c673` adds measurement results and a
publication note; its recommendation is unchanged.

- **Decision:** Qt Quick/QML 6.12.0, with a shared C++ application controller
  that drives the unchanged pinned wallet core through a narrow, authenticated
  loopback RPC. The runner-up is Slint 1.18.1 through its C++ API. Tauri, Wails
  and Electron are rejected because they are WebView or browser shells.
- **Status:** this is the studio's recommendation, not an accepted wallet. QML
  draws its own controls in a native app. It is neither a WebView nor a promise
  of OS-native widgets.
- **What exists:** mocked Linux x86_64 (X11) Qt and Slint windows with keyboard
  and AT-SPI action probes.
- **What does not exist:** a real wallet connection, an audible screen-reader
  journey, NVDA or VoiceOver, IME, high-DPI or reduced-motion checks, real
  create, import or seed reveal, the fee-review relay, a C++ Qt package,
  macOS or Windows builds, signing or updates.

**Carrying this design into QML:**
- The tokens become one theme object keyed by the network the node reports.
- Use the standard Qt Quick Controls with custom styling, and add no custom
  safety-critical controls.
- The C++ controller owns atomic integers, `parseAmount` and `fmt` (with
  `PARSER_CASES`), the session and an allowlist of RPC methods. QML receives
  display models and actions only: no credentials, no arbitrary RPC, no
  WebEngine and no remote QML.

**Native acceptance checks beyond this prototype** (TJS-1996 and the studio's
note on TJS-1992):
1. Inactive pages are hidden from assistive technology. Qt's tree still
   included inactive-page nodes in the mock.
2. Focus, dialog and announcement behaviour as in the experience contract.
3. Platform shortcuts and dialog button order.
4. The system reduced-motion setting is honoured.
5. The review shows exactly the prepared transaction, and the same transaction
   is relayed.
6. One real screen-reader journey per target (Orca, NVDA, VoiceOver) through
   create, back up, receive, send and restore.
7. IME and high-DPI work.
8. Consent text is on screen before the control that acts on it. At the
   minimum window size, the remote-node explanation is fully visible, measured
   by geometry rather than by presence in the accessibility tree, before anything
   can connect.

## Design critique (TJS-1999)

The independent critique of `3fc9e0c` (`review-verdict` revision
`f998ded8-2a73-4cae-bd36-7195294a8bdd`) found the concept met all seven brief
items: **accept with findings**. This table records how each finding was
handled. A fix counts only after an independent re-check.

| Finding | Disposition |
| --- | --- |
| **D1** a comma or space silently changed the amount | Fixed in rev 3: separators are refused, the locale decimal rule is in the contract, and `PARSER_CASES` covers `0,5`, `2,5`, `1.000,5`, `1 000`, `1_0` |
| **D2** long seed words overflowed | Fixed in rev 3: cells fit "verification", the word screens and recovery sheet are wider, and the sample includes "laboratory" and "verification" |
| **D3** dialogs were unnamed, not modal, and lost focus | Fixed in rev 3: named by heading, background inert, Tab trapped, focus returned |
| **D4** focus was lost after actions, and outcomes weren't announced | Fixed in rev 3: focus kept or moved to the heading; live region for outcomes |
| **R1** a cropped money figure had no network marker | Fixed in rev 3: "Test coins" tag on the balance, review, Sent and details |
| D5 the regtest ribbon contradicted a remote node | Fixed in rev 2: someone else's node is disabled on regtest |
| D6 "Get test coins" was enabled while offline | Fixed in rev 3: disabled, with the reason given |
| D7 actions that did nothing; About omitted tier-B features | Fixed in rev 2–3: unbuilt actions are disabled, and About lists "designed, not yet tested with the kit" |
| D8 errors weren't linked outside Send | Fixed in rev 3 |
| D9 ellipsis contrast | Fixed in rev 3 (muted colour) |
| D10 motion under reduced motion | Fixed in rev 3 |
| D11 a balance too small for any fee could still start a send | Partly fixed in rev 3 (Overview only, per TJS-2002); completed in rev 4 (author-verified) |
| D12 staged wrong pick wasn't marked | Fixed in rev 3 |
| D13 "Coming later" testnet promise | Fixed in rev 2: the network is shown, never chosen |
| D14 radio and toggle semantics | Fixed in rev 2–3: no welcome radios, node radios are one Tab stop with arrow keys, constant toggle label, exact name for the balance |
| R2 testnet preview could look live | Fixed in rev 2: the ribbon says "Design preview … not live" |
| R3 change after sending was never shown | Fixed in rev 3: change is modelled and explained on Sent |
| R4 node changes weren't announced | Partly fixed in rev 3 (reviewer control only, per TJS-2002); completed in rev 4 (author-verified) |
| R5 copy always said "Copied" | Fixed in rev 3 |
| R6 privacy wording to confirm | Fixed in rev 2–3 with the TJS-1994 approved wording; the own-node line no longer claims nothing leaves the computer |
| T1 warning colour close to gold | Accepted: hue moved |
| T2 per-platform conventions | Accepted: see Platforms |
| T3 tiers used for open policy questions | Accepted: those labels were removed in rev 2 |
| T4 "Works today" could mean the GUI | Accepted: it is now "Engine today" |
| Coverage: wallet engine down, RPC authentication failure, incompatible node, unknown resolving to not sent | Added in rev 3 |

**Coverage deferred to implementation.** These are not built in the prototype.
Each is specified here in one line, and design lead reviews it in the
implementation's journey QA:
- **Open a wallet file:** a system file chooser. A missing or corrupt file, or
  one from another network, gets a plain refusal that names the file and
  network; nothing is modified.
- **Restore edge cases:**
  - A restore that finds no payments says so and shows the scanned range.
  - Quitting mid-scan resumes on the next launch.
  - A wallet name that already exists is refused, without overwriting.
- **Re-run the word check later** from Wallet → Backup.
- **Import by keys or view-only:** out of scope for this test build and absent
  from the UI.
- **Payment requests with an amount and integrated addresses:** absent while
  regtest forbids payment links (TJS-1994 #2). Revisit with a distinct network
  identity.
- **Other send failures:** fee above balance, transaction too large, node busy.
  Each says "Nothing was sent" plus the node's reason, keeping the
  refused-payment layout.
- **Disk full or a failed write** during create or restore: nothing is
  half-written, and the error names the folder.

## Re-check (TJS-2002)

The design critic's independent re-check of `4bd99fd` (`recheck-verdict`
revision `97566108-ecc2-4b79-8c2a-d37fbe824995`) found that **D1, D2, D3, D4 and
R1 pass** on observed behaviour: **accept with findings**. It also passed the
TJS-1996 wording above and the TJS-1994 approved strings. It reported nine new
minor findings, recommended N1–N3 before the handoff is final, and left the rest
to the design lead.

Revision 4 handles all of them. These fixes are **author-verified only**; the
studio lead re-runs the critic's repros before accepting.

| Finding | Disposition in rev 4 |
| --- | --- |
| **N1** the Node screen read "undefined" for engine stopped, refused credentials and incompatible node | Fixed: each state has its own status text. The incompatible node shows "—" for height and peers. Send, Overview and Receive name the wallet engine when it is at fault |
| **N2** leaving Send while a payment was being prepared still opened the review over another page | Fixed: leaving discards the prepared payment, as Edit does, and the form keeps what was typed. The rule is in the contract |
| **N3** the regtest refusal called any address not starting with `4` a Meownero testnet address | Fixed: only a `T…` address is called testnet. Monero `8…`, `5…` and `9…` addresses get the kit-wallet rule |
| N4 adding a block resolved an unknown payment whatever the control said | Fixed: with "Reached the node" the next block contains it, and that is announced. With "Not sent", blocks change nothing until "Check with node". The evidence rule is in the contract |
| N5 activating the large balance moved focus to the header toggle | Fixed: focus stays on the balance |
| N6 "Try again" and "Restart wallet engine" changed node state silently | Fixed: every node-state change is announced, however it happens |
| N7 ticking the backup checkbox threw a script error | Fixed: the console stays clean |
| N8 the marker dropped "Interactive prototype ·" in windows of 1040 px or less, and overlapped the title in windows of 601–700 px | Fixed: the full approved phrase shows in every window wider than 800 px, wrapping to at most two lines, with no overlap or title truncation on any platform or network (measured 808–1112 px). In smaller windows, below the 828 px layout minimum, it is hidden and the page caption carries it |
| N9 reconciliation was announced by both the toast and the live region | Fixed: the toast is visual only |
| D11 residual: the Send page reached from the sidebar didn't say why a dust balance can't be sent | Fixed: "Review payment" is disabled with the reason |
| R4 residual: app-made node changes weren't announced | Fixed with N6 |
| R-A arrow keys in the node choice switched straight to someone else's node (testnet preview) | Fixed: the radios only pick, and nothing changes until an explicit Connect. The studio review found the explanation could be clipped below Connect; rev 5 moves it into a confirmation dialog (see Studio review) |

## Studio review (revision 4)

The Meownero Studio Lead reviewed `fdb081c` (`studio-review` revision
`82a1bf2f-6427-48b1-99ed-72839206500d`): 40 independent checks passed and one
failed, so **changes requested**. N1–N9, D1, D3, D11 and the native-direction
reconciliation passed.

| Finding | Disposition in rev 5 |
| --- | --- |
| **R-A disclosure visibility.** At a 1280 × 900 viewport (908 × 740 window), the full exposure explanation sat below "Connect to someone else's node" and was entirely clipped, and a real pointer click connected without it ever being visible | Fixed with the confirmation-dialog option the review offered. "Connect to someone else's node…" now opens a named, modal dialog. The dialog is described by the approved TJS-1994 sentence, shows the node and its untrusted status, and starts focus on "Keep current node". Only its "Connect to someone else's node" button connects; Keep, Escape and clicking outside change nothing, and Escape returns focus to the Connect button. On the Node screen the explanation shows while connected, above any Connect row. Picking a choice now scrolls the whole Connect row into view. Going back to your own node stays one Connect. The reviewer's "Synced via someone else's node" control is disabled on regtest, and switching to regtest leaves someone else's node |

**Author verification on revision 5** (scripted Chromium; real keyboard and
pointer input; visibility checked geometrically, inside every clipping ancestor,
the window and the viewport, and not covered):
- 128 of 128 R-A checks pass. They cover the 1280 × 900 viewport (908 × 740
  window) and the 880 × 600 minimum window (simulated, see Platforms), on macOS,
  Windows and Linux window styles, with keyboard and pointer input.
  - In the dialog, the explanation sits at y 315–373 at 1280 × 900 and y 221–279
    at 880 × 600, above its Connect button, with no scrolling inside the dialog.
  - Nothing connects on a pick, on opening the dialog, on Keep, on Escape, or on
    clicking outside.
  - The dialog's Connect sets "Untrusted, by your choice" and is announced.
  - On regtest, someone else's node can't be picked.
- 31 of 31 earlier repair checks (N1–N9, D11 and R-A) pass after the R-A update.
- 320 renders are clean: every screen and error state, both networks, light and
  dark, every node state on five screens, plus the new dialog. None has a script
  error, "undefined", banned wording, an unnamed dialog or horizontal scroll.
  Every request stayed on loopback.

These results are author-verified only; the studio lead re-runs the R-A check
before accepting. No screen reader was used.

## Implementation handoff

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
3. **Stack: Qt Quick/QML 6.12.0 with a C++ controller** (TJS-1996, above),
   following TJ's direction of 2026-10-10 10:22 PDT: native rendering, shared
   code, no Electron. The studio lead assigns the single implementation owner.
   The HTML prototype is the review artifact. The build must reproduce the
   experience contract, including the network-bound accent, test-coin tags,
   platform conventions, focus and announcements, and every listed state.
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
   point. Port `parseAmount` and `fmt` semantics with `PARSER_CASES`, adapting
   the decimal separator to the system locale and refusing every grouping
   separator.
6. **States:** implement every transition in the experience contract,
   especially the unknown-relay branch and the reorg banner, before visual
   polish.
7. **Acceptance for the build:** on the actual packaged binary per target, a
   tester completes create → back up → get test coins → receive → send → restore
   → spend; the 1-atomic, large-balance and 13-decimal cases behave as above; the
   network label matches the node's reported network; the native acceptance
   checks above pass, including one real screen-reader journey per target;
   signing status and the tested OS and architecture are reported from execution
   evidence only.

**Status:** both critique passes are complete: TJS-1999 and TJS-2002, each
accept with findings. The studio review of revision 4 passed everything except
the R-A disclosure placement, which revision 5 fixes. Every finding has a
disposition above. The design returns to the Meownero Studio Lead for accepted
integration. The revision-5 fix is author-verified, and the studio lead re-runs
its R-A check before accepting.
