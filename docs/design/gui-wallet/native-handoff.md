# Accepted native wallet handoff

TJS-1996, 2026-10-10. Meownero Studio Lead, run
`648366c8-827d-431e-bb9c-d7c5c808ddf2`.

The architecture and design are ready for one native implementation owner.
Use Qt Quick/QML 6.12.0 with a shared C++ application controller. Slint
1.18.1/C++ remains the runner-up. The native app uses Qt's renderer and
standard Qt Quick Controls, with the accepted visual styling. It does not
use Electron, WebEngine, Tauri, Wails or remote QML.

## Accepted evidence

- [Architecture decision](../../adr/ADR-002-native-wallet-ui.md), verbatim
  snapshot of TJS-1996 `architecture-decision`, revision
  `2360ff83-d6a0-4bc6-808e-ddd782c9c673`.
- [Experience contract and capability matrix](README.md), accepted design
  revision 5 at `986ae4cf416c3a95ffdb7a0d51ba10498b72df7e`. README SHA-256
  `b7b8bb709f05690b8d5f4a33fcae19cde4a509d47601aeef289837923a575116`.
  [Prototype](prototype.html) SHA-256
  `5a420e7d000be4a1b0da3c35ffba42c3281e0c579e5cc0eef867a173d25ac075`.
  The HTML is a mocked design-review artifact.
- [Studio acceptance](studio-review.md), verbatim snapshot of TJS-1992
  `studio-review`, revision `b09f861d-3803-4d53-a171-8fc1e026768e`.
  The recorded independent Linux Chromium checks accept the final consent
  repair. They are not native-wallet QA.
- [Privacy constraints](privacy-constraints.md), verbatim snapshot of
  TJS-1994 `privacy-constraints`, revision
  `4a98299b-dfa7-4ac8-82f9-c959af5f43eb`. This reuses the existing advisory;
  it creates no new privacy verdict.
- Independent design critic TJS-1999 `review-verdict`, revision
  `f998ded8-2a73-4cae-bd36-7195294a8bdd`, and TJS-2002 `recheck-verdict`,
  revision `97566108-ecc2-4b79-8c2a-d37fbe824995`, remain the critique
  references. Studio accepted the subsequent repairs on the final hash.
- [Native Qt/Slint experiment evidence](<private-tracker>/api/attachments/e32ea6ee-4166-42ad-9887-5bf371ca0024/content?download=1),
  SHA-256 `7e3bcaad289c2a4f130a1f2487ddeca979568cd6613723c8c9b0fbd7826a9ee9`.
  Linux x86_64 only, no connected wallet. AT-SPI actions do not establish
  an audible screen-reader journey. Reuse the measurements and their limits.

## One owner and the first deliverable

Assign the registered UI engineer, `8dd6b664-9570-437a-b363-e442847c917a`,
as the sole writer of the native shell and controller. Design lead retains
creative ownership. Studio owns integration and acceptance. Platform engineer
remains the sole Docker writer on TJS-1882 and receives no additional writing
scope from this handoff.

The first deliverable is a compiled C++/QML application with the accepted core
journeys and a deterministic, explicitly simulated backend. It must run as a
native window on an actually available desktop. This is an implementation of
the selected design, not another toolkit comparison or static screenshot.
No wallet, daemon, real address, genuine seed or real coin is connected in
this slice. Do not accept or persist personal recovery words.

Own `wallet-ui/` and its local build instructions, plus native evidence under
`research/evidence/`. Inspect existing code before creating these paths. Keep
the shared controller and state model in C++; keep QML bindings limited to
display models and explicit actions. Avoid speculative abstraction and extra
dependencies. Do not modify `vanguard/`, `chain/`, Docker, the website,
CI configuration, source locks or existing backend processes.

Build the early vertical slice through overview/sync, receive and prepared
send review first. Complete safe simulated create/import, backup/restore,
activity, lock, offline/error and unknown-submit recovery in the same task.
Use the accepted system fonts, network-bound accent, exact amount rules,
minimum 880 x 600 layout, test-coin labels and standard controls. Keep
reviewer fixtures visibly separate from the app's interaction model.

The future production boundary remains UI -> typed C++ controller -> narrow
authenticated local RPC -> unchanged pinned C++ wallet core. An implemented
mock seam does not prove that boundary. The current native engine binaries
and a host-to-isolated-kit administrative RPC route are unavailable evidence.
There is no authorization here to publish container ports, alter runtime
authentication, start native CI or weaken isolation.

## State and safety checks

1. Carry exact integer atomic units through parsing, totals and formatting.
   Port the accepted `PARSER_CASES`; test one atomic unit, large balances,
   locale decimal separators, rejected grouping separators and 13 decimals.
   QML must not convert payment values through floating point.
2. Review recipient, amount, fee and total from one prepared object bound to
   the verified session identity. Confirm must consume that same object.
   Editing, leaving Send before preparation completes, locking, wallet
   changes, node changes or network/session identity changes invalidate
   pending consent and prepared actions. Late callbacks cannot reopen stale
   review. A submission already underway retains its attempt identity.
3. A dropped submission stays unknown, blocks another payment and never
   retries automatically. Reconcile only on positive evidence for the
   recorded attempt or a defined, sufficient absence proof. A new block
   alone cannot establish failure. Simulated evidence must be labeled.
4. Separate total from unlocked funds and node catch-up from wallet scanning.
   Show last-known data when offline. Wrong network or incompatible versions
   load no wallet data. Every error names the failing node or wallet engine.
5. Hide simulated recovery words on navigation, lock and background. Disable
   seed copy/export and prefetch while locked. Diagnostics use an allowlist
   and exclude recovery words, passwords and private transaction metadata.
   Do not claim framework-wide memory erasure or OS capture protection.
6. Real regtest sends remain restricted to disposable recipients known to
   the isolated session. No mainnet/public-testnet switch, interoperable
   payment link, personal seed import, Tor/I2P or OpenAlias enablement.
7. In any explicitly simulated future remote-node scenario, show the exact
   approved exposure sentence fully before final consent. Start focus on
   Keep current node. Choice, Escape and dismissal do not connect. The
   disclosure must fit at 880 x 600, measured against clipping and occlusion.
   Regtest never offers someone else's node.

The final studio review found a nonblocking stale consent dialog in the
HTML review tools when their network changed. Carry that finding into check
2. The native controller must reject stale consent even if the UI failed to
close the dialog.

## Independent acceptance and evidence

The writer hands the exact branch/head, native executable hash, reproducible
build commands and evidence to independent code/security review and journey
QA. Reviewers do not edit the candidate. Design lead assesses rendered
fidelity against the accepted contract. Studio resolves findings and accepts
the integrated result; author checks alone do not approve it.

- Exercise the complete simulated create -> backup -> receive -> send ->
  restore journey, plus cancellation, stale callback, unknown-submit,
  wrong-network, engine-auth refusal and offline recovery failures.
- Check actual keyboard navigation, platform shortcuts, dialog order,
  focus restoration and announcement behavior. Inactive pages and hidden
  recovery content must be unreachable to assistive technology.
- Honor the system reduced-motion setting. Inspect light/dark, long
  addresses, large text, minimum window size, high-DPI and IME where the
  available desktop permits them.
- Run one real screen-reader journey on the actually tested OS when tooling
  permits it. Retain the exact limitation if unavailable; an AT-SPI action
  or accessibility-tree dump cannot pass this check.
- Report tested OS/architecture/toolchain, startup measurement method,
  idle sample duration, RSS and measured local package/tooling footprint.
  No one-host result establishes Windows/macOS/Linux support or a shipping
  installer size. Reuse appropriate tooling and retain failed probes.
- Include Qt module/license inventory, source/toolchain hashes and the
  unsigned/local status. There is no updater, signing, paid license or
  public distribution in this slice.

For a material state, privacy or authorization change, reuse the existing
Wallet & Transport Privacy specialist for the exact new boundary. Do not
commission a duplicate general review. Never enable a real connector before
the current-lineage authentication, isolation, password and exact wallet
`relay_tx {hex}` metadata path have execution evidence and independent
acceptance. The daemon's relay-by-txid is a different method.

## Next integrated decision

After the first native slice passes independent review and journey QA,
Studio retains this UI engineer for the next real-wallet integration slice.
The owner must propose a route compatible with the network-disabled kit and
the existing constraints. The privacy specialist accepts or rejects that
specific route before a separate authorized runtime change. If no such route
is available, keep the connector disabled and record the named prerequisite;
do not change Docker to make the mock appear connected.

Native per-OS engine builds, signing, secure updates and website downloads
remain later evidence gates. The parent operator owns distribution. Mobile
is an extension-path comparison only. No additional tester-matrix runs,
native-CI work, release uploads or WhatsApp attachments are authorized here.

Needs TJ: None for the native mock implementation and accepted handoff.
