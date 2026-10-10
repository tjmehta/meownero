# Studio review of revision 5

Approve the design and prototype handoff on [TJS-1992](/TJS/issues/TJS-1992), with one nonblocking reviewer-control finding. The R-A disclosure repair passes independent checks. This accepts the mocked design artifact for subsequent integration and native implementation.

## Changed

Reviewed branch `TJS-1992-meownero-native-gui-wallet-design-concept-and-interactive-prototype` at `986ae4cf416c3a95ffdb7a0d51ba10498b72df7e`, parent `fdb081c5dcaa7a9029339cefc949fbe8b89bb1df`. No product files were edited or merged.

Published attachments match the candidate byte for byte:
- Prototype SHA-256 `5a420e7d000be4a1b0da3c35ffba42c3281e0c579e5cc0eef867a173d25ac075`, attachment `96949e49-27cf-4979-91f0-02a8dfe35d96`.
- README SHA-256 `b7b8bb709f05690b8d5f4a33fcae19cde4a509d47601aeef289837923a575116`, attachment `fa05a1c9-1601-406f-8db7-4ec0e203f6fc`.

The same handoff records Qt Quick/QML 6.12.0 with a shared C++ controller and narrow authenticated loopback RPC to the unchanged pinned core, with Slint 1.18.1/C++ as runner-up. It supersedes the former WebView recommendation. Read [TJS-1996 architecture-decision](/TJS/issues/TJS-1996#document-architecture-decision), current revision `2360ff83-d6a0-4bc6-808e-ddd782c9c673`, retaining previously verified revision `30797108-8f10-4ca1-b098-927b7880aba4`, SHA-256 `df6a9297345386a8d9fd3561896f9689bc296fdb3d226c071817dc2fbf7011f2`. Qt remains a studio recommendation, without a guarantee of OS-native widgets or wallet acceptance.

## Verified

Independent Chromium 153.0.8010.12 checks on Linux covered 24 combinations of two window sizes, three platform styles, light/dark and keyboard/pointer input. Windows were 908 x 740 in a 1280 x 900 viewport and a simulated minimum 880 x 600 in a 928 x 900 viewport. Minimum height was imposed by the harness, as the README discloses.

- Picking a node changes no connection and reveals the full Connect row.
- Connect opens a named, described modal with the exact approved exposure sentence. Initial focus is on Keep current node. Tab and Shift+Tab stay inside; the app background is inert.
- The complete explanation is visible above the final Connect button, inside all clipping ancestors and the viewport, without dialog scrolling. In the macOS-style light window it spans y=314.5 to 373.2, before Connect at y=468.0. The minimum dark screenshot was also visually inspected.
- Escape, backdrop and Keep preserve the connection; Escape and backdrop restore focus. Only final consent connects, sets explicit untrusted status and writes the expected announcement.
- While connected, disclosure precedes the Connect row. Returning to the own node is one explicit Connect.
- Regtest disables remote choice in both app and reviewer controls; arrow selection stays local.
- No script/console errors or HTTP/external requests occurred. The artifact was loaded from a local file in an isolated browser context.

The behavioral suite has 362 passing checks. Its 24 initial button-occlusion flags were harness false positives: samples fell in the transparent rounded button corners. A separate geometry rerun samples button interiors at a 12px inset, keeps text samples at 2px and retains all clipping bounds. That rerun passes 24 of 24. Raw first-run results and the correction remain in the bundle. Together, 386 acceptance-relevant checks pass; the single residual below is recorded separately.

The revision-4 independent review already checked N1-N9, D1, D3, D11 and native wording. The diff is confined to the consent repair and reviewer regtest restrictions. Existing [TJS-1999 critique](/TJS/issues/TJS-1999#document-review-verdict), revision `f998ded8-2a73-4cae-bd36-7195294a8bdd`, and [TJS-2002 re-check](/TJS/issues/TJS-2002#document-recheck-verdict), revision `97566108-ecc2-4b79-8c2a-d37fbe824995`, remain the independent design evidence. Privacy constraints remain [TJS-1994](/TJS/issues/TJS-1994#document-privacy-constraints), revision `4a98299b-dfa7-4ac8-82f9-c959af5f43eb`.

## Nonblocking finding

The reviewer tools can change the mock network while remote-node consent is pending. Selecting regtest and then confirming the stale dialog stages `net=regtest, node=remote`, contradicting the ordinary regtest restriction. Repro: reset, testnet preview, Node, Someone else's node, Connect, reviewer Local regtest, dialog Connect.

This is a scenario-control limitation outside the wallet UI. The accepted shipping contract exposes the network reported by the node and offers no user network switch, so this does not block the repaired consent flow or native design handoff. Preserve the finding in implementation QA: the native controller must invalidate pending consent and other prepared actions when the session or verified network identity changes. The design writer may close stale dialogs on reviewer network changes as a later artifact polish fix; no new issue or extra review panel is needed.

## Unconfirmed/next

Studio owns accepted base integration, the next single native implementation writer, independent code and journey QA, native packaging and the existing website-delivery path. Existing dependency wakes on [TJS-1996](/TJS/issues/TJS-1996) and [TJS-1245](/TJS/issues/TJS-1245) carry that continuation. This review performs no merge or native implementation.

The artifact is mocked HTML. These checks provide no real-wallet, audible screen-reader, macOS/Windows execution, native package, signing or download acceptance. Platform styles are simulations on Linux. No Docker work or new group attachments occurred.

Observed behavior: explicit consent now follows the full visible exposure explanation. Scenario controls can invalidate a pending dialog; native pending actions must remain tied to their verified session identity.

Needs TJ: None.

[Independent evidence bundle](/api/attachments/3ac4291b-6021-4217-a175-89763bb1fc70/content).
