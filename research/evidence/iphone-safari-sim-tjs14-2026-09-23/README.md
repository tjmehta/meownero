# TJS-14 M1b: meownero.com signup on iOS Simulator Mobile Safari (2026-09-23)

TJ authorized this run in comment 5e3a23b5 on TJS-14: "you can use a simulator on
build-mac". It ran the tester sheet
[`docs/testing/iphone-safari-signup-checklist.md`](../../../docs/testing/iphone-safari-signup-checklist.md)
(e1ecf1b) against the live site. This is **simulator evidence, not a physical-iPhone
result**. "What this did not cover" below says what a real device would still add.

## Identity

| What | Value |
|---|---|
| Site | `https://meownero.com/`, the live production deploy; nothing was redeployed |
| Deployment | `dpl_CVg1M68fvLwjUQaSz1ZYsqsQRJ5w`, etag `"0068eba20dccac19619e0e3e39ad9173"`, confirmed at 19:08 UTC and again at 19:24 UTC. This is the deploy the checklist names. |
| Device | iOS Simulator `ios-agent-01` on build-mac: iPhone 17 (`iPhone18,3`), iOS 26.5 (23F77), UDID `6711093B-9016-4C80-B311-90E1D83EAC4C` |
| Browser | MobileSafari 8624.2.5.10.4, first launch on this simulator (fresh profile) |
| Claim | `ios sim claim` token `9a9ea03d-…`, owner `tjs14-safari-signup`; released after the run |
| Driving | cua-driver taps on the Simulator window. The address and keystrokes were entered by tapping the on-screen keyboard; no `openurl`, and no paste. |
| Network | build-mac's host network (the simulator has no cellular or Wi-Fi stack of its own) |

## Result per checklist row

Times are in `tjs14-run-402w.mp4`.

| # | Row | Result | Evidence |
|---|---|---|---|
| 1 | Cold load: dark page, gold "Coming soon" badge, headline, coin | **Pass** | `screenshots/row1-2-after-load.png`; video 194.7 s (Go) → 195.3 s (first paint) |
| 2 | First paint → form appears once, no flash or swap | **Pass (on reload)** | The dark page paints first, then coin, headline, paragraph and form fade in once. After that the form stays the same (`frames/reload-paint-496_0s.png`, top strip of `frames/form-stable-after-reload-and-first-load.png`). On the first load, Safari's first-run "View Bookmarks…" tip covered the form area during that window (`frames/first-load-paint-195_3s.png`), so the reload at 496.2 s is the clean view. |
| 3 | Field placeholder `you@example.com`, gold "Notify me", helper text | **Pass** | `screenshots/row3-4-signup-area.png` |
| 4 | No push CTA, no "Use email instead", no notification text | **Pass** | `screenshots/row3-4-signup-area.png`, and the whole page in the video |
| 5 | Email keyboard with `@` and `.`; field and button stay visible; no zoom | **Pass (simulator keyboard)** | `screenshots/row5-keyboard-open.png` |
| 6 | Landscape and back: one line, nothing cut off, no sideways scroll | **Pass (visual)** | `screenshots/row6-landscape.png`, `screenshots/row6-portrait-back.png`, `frames/rotate-and-reload-events.png`. Judged from the layout fitting the viewport; no horizontal swipe was attempted. |
| 7 | Reload: rows 2–4 again, nothing remembered, no "You are on the list" | **Pass** | Real repaint at 496.2 s (`frames/reload-paint-496_0s.png`), `screenshots/row7-after-reload.png` |
| 8 | Invalid `test` → validation bubble or "Enter a valid email."; nothing stored | **Pass** | Typed `t`,`e`,`s`,`t` (533.6–549.4 s). Notify me at 563.4 s showed Safari's native bubble "Enter an email address" and left the field unchanged (`screenshots/row8-invalid-test.png`, `frames/row8-keystrokes-and-bubble.png`). Native validation blocks the submit before any request; the notify store was not read. |

The "do not" rules were kept: no real email address was entered, no push button
exists or was tapped, and no submission reached the server.

Artifacts that are not site findings:

- Safari showed first-run "Continue" screens and a "View Bookmarks…" tip, which I
  dismissed.
- One extra device rotation left the simulator in upside-down portrait, which Safari
  does not rotate into. I rotated through that back to portrait.
- The macOS pointer appears in the cua screenshots, not in the simulator video.

## What this did not cover

- **A physical iPhone.** The simulator uses the same WebKit and Safari UI, but it runs
  on a Mac. It had no real touch digitizer or hardware keyboard, no cellular or Wi-Fi
  latency, no carrier, no Low Power Mode, no content blockers, and not TJ's own device,
  iOS version, settings or Safari profile. The first-paint timing here reflects
  build-mac's network, not a phone's.
- A valid-address submission and its delivery or storage. The checklist forbids it,
  and I made none.
- Other iOS versions, device sizes, Dynamic Type or text-size settings, and VoiceOver.
- Private Browsing, and a second visit on a warm cache beyond the one reload.

## Files

- `tjs14-run-402w.mp4`: the whole 593 s recording re-encoded to 402 px wide (H.264, CRF 30).
  The raw capture `tjs14-run.mov` (1206×2622 H.264, 400874256 bytes,
  sha256 `1d8b15f04914488c488771e757de46180c96fa7ec281310885cde5d60ecfa421`) is too
  large for git. It is kept with the Paperclip run d512e3ec-32d4-4e60-b190-63ea96655762
  output, not in this repo.
- `screenshots/`: cua window captures (Simulator window, 456×972 portrait or 910×518 landscape).
- `frames/`: contact sheets cut from the raw capture at the times cited above.
- `MANIFEST.sha256`: hashes of every file here.
