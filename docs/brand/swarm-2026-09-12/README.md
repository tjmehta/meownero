# Local visual directions and explainer

**Economics disclosure for future materials:** TJ selected perpetual issuance with zero premine and no hard cap: target 9 MEOW/90 s, conditional fallback 12 MEOW/120 s. Both target 3,153,600 MEOW/year before penalties. From zero initial supply, year 2 adds 100%, year 11 adds 10%, year 51 adds 2%. No adoption neutrality or guaranteed security claim. [Decision](../../../research/decision-2026-09-12-issuance.md). Existing demo accounting remains the tested historical control.

Private review materials, September 12, 2026. No identity, ticker, launch timing
or funded campaign decision. [Mood-board contact sheet](moodboards.svg) and
[six-frame storyboard](storyboard.svg) are original vector assets with text
equivalents below. No remote fonts, scripts, tracking pixels or embedded media.
Reference links are for human inspection; no third-party art is redistributed.

## Three distinct directions — proposed choices, not factual findings

| Direction | Visual language and material | Real reference and specific lesson | Use / avoid |
| --- | --- | --- | --- |
| A. Field notes | Warm paper `#F5F0DF`, forest `#163E35`, vermilion `#BA432B`; restrained serif titles, sans labels; numbered steps, printed fold lines | [NPS oral history on the Unigrid system](https://home.nps.gov/subjects/oralhistory/podcasts-episode-4.htm): welcoming voice and a standardized information structure. Use the navigable hierarchy, not NPS branding. Primary search excerpt verified; full-page fetch timed out. | Best for the recovery guide: approachable, specific, readable on paper. Avoid rustic cat folklore, distressed textures and national-park endorsement cues. |
| B. Proof instrument | Pale blue `#E8EFF7`, deep blue `#17375E`, brass `#8C5B22`; monospaced measurements, fine line diagrams, ruled scales | [NASA's Golden Record cover explanation](https://science.nasa.gov/mission/voyager/golden-record-cover/): an object accompanied by instructions for decoding it. Use explanatory annotation, not its actual symbols or a “cosmic currency” story. | Best for engineering challenge material. Exact quantities and boundaries remain visible. Avoid pretending a schematic is a security proof or alien/cypherpunk lore. |
| C. Everyday receipt | Warm white `#FFF9F1`, plum `#432F46`, coral `#D6664D`, mint `#B9D9C7`; large plain numerals, a single receipt strip, friendly geometric punctuation | [Monero press kit](https://www.getmonero.org/press-kit/): inspect how simple geometry stays recognizable in reduced formats. Borrow clarity and restraint, not the Monero mark, endorsement or a settled Meownero identity. | Best for the payment explainer: an ordinary amount received and recovered. Avoid gambling, speculative price screens, mascot-led lore or making privacy look illicit. |

The contact sheet visualizes original layouts and palette proposals; it is not
a collage of unlicensed source images. The titles name directions, not products.
Choose A for a how-to and B for a technical benchmark; C is a separate consumer
communication experiment. The decision is normative and remains open. Generic
black backgrounds, alley cats, glowing eyes and invented mythology are rejected
because they obscure the payment/recovery behavior this artifact can demonstrate.

## 54-second explainer storyboard

Working title: **A payment. A fresh wallet. The same balance.**

Use large captions and a persistent “Local prototype · disposable wallets” label.
The static SVG is the accessible, reduced-motion version; motion below is a
production proposal, not an implemented video. Read left to right, then next row.

| Time / frame | Picture and motion | Spoken line / caption | Evidence or claim boundary |
| --- | --- | --- | --- |
| 0–7 s / 1. Set up | Two plainly labeled wallet outlines on paper; recipient reads zero. No real addresses or seed words. | “Two disposable wallets, on a local test chain.” | Exact current15 hashes and network isolation in demo provenance/runner. Do not call this public mainnet. |
| 7–16 s / 2. Pay | Move a receipt labeled `0.123456789012` from sender panel to recipient panel. Show fee separately, with “varies by transaction.” | “The sender makes a payment. The wallet records the amount and fee.” | `transfer` with amount `123456789012` atomic. Example run fee `64950000` atomic; do not freeze this as a universal price. |
| 16–26 s / 3. Two views | Split labeled “Wallet owner” and “Public transaction data.” Owner sees amount. Public panel shows commitments / ring references; no legible amount substituted into public fields. | “The recipient wallet reads its amount. Public transaction amount fields are not plain payment values.” | Version 2, RingCT type 6, zero public amount fields and 16 offsets verified. This tiny controlled chain does not establish meaningful anonymity. No “untraceable,” “invisible,” or network privacy claim. |
| 26–35 s / 4. Start fresh | Close recipient process. Remove a folder icon. Display a separate seed card with abstract blank lines, never a usable mnemonic. | “Now remove the recipient's wallet files and start a fresh process.” | Original recipient directory is deleted before restoration. Show a deliberate test reset, never imply users should delete their only backup. |
| 35–46 s / 5. Recover | Seed card points to a new wallet; chain scan resolves to the same address marker and amount. Note field remains empty. | “The seed recovers the received payment. The local note does not return.” | Same address, incoming transaction/height/amount/type and unlocked balance; same after reopen. Outgoing-history recovery and spending from the recovered wallet are outside this demo. |
| 46–54 s / 6. Verify | Paper result sheet: “Payment ✓ · Recovery ✓ · Reopen ✓”; link to runner and evidence. Hold instead of flashing a call to invest. | “Run the local demo. Check the result and its limits.” | End on source/evidence paths, not an adoption promise, launch countdown or economics claim. FCMP++ is not demonstrated. |

Frame 3 must retain observer labels; mixing owner-visible and public values would
misrepresent privacy. A ring is sixteen referenced outputs, not sixteen people.
All outputs here are controlled by the tester. Production timing, anonymity
transport and real-network observer tests require separate evidence.

## Attention snapshots — inherited closed evidence

The supplied September 12 decision record already verified these platform
counts; this track does not repeat that scrape or claim current counts:

- [December 9, 2024 FCMP++ explainer](https://x.com/monero/status/1866208203299537117):
  692,534 views (about 692.5K); credited there to VostoEmisio and xenumonero.
- [August 4, 2026 Cuprate release post](https://x.com/monero/status/2084713001362326004):
  49,774 views (about 49.8K).
- [August 21, 2026 cryptography audit post](https://x.com/monero/status/2090873589503324399):
  36,500 views. Component-audit attention is not whole-system assurance.

Different ages and exposure make these dated attention snapshots, not evidence
that an explainer, optimization, audit or supply policy caused adoption. The
explainer is a reference for making technical ideas legible, not permission to
copy its footage or claim the same reach. No follower funnel or telemetry added.

For source-scoped optimization claims, see the
[factual correction in the challenge](../../../demos/private-payment/challenge.md#factual-correction-from-the-monero-precedent).
For actual demo evidence and remaining integration, see the
[track report](../../../research/swarm-demo-2026-09-12.md).
