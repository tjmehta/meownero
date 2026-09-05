# Traffic playbook for meownero.com (brand track)

**Date:** 2026-09-05 · **Track:** brand/launch (PLAN.md §11) · **Status:** working notes, not ratified

Purpose: what actually gets attention for a new fair-launch, mandatory-privacy PoW coin, so the teaser at meownero.com starts pulling real traffic instead of drive-by hits. Sourced from a Perplexity research pass on 2026-09-05 (Bitcointalk threads, r/gpumining and r/cpumining guides, MiningPoolStats, Kaspa/Tari/Zephyr launch coverage). Tagged [SECONDARY] unless noted.

## 1. Who shows up first, and where they look

Miners arrive before anyone else. They monitor a short list of places:

- **Bitcointalk, Announcements (Altcoins).** The canonical launch document. Miners on r/gpumining call it "the main source" for new coins. Spam rules are enforced: one structured, technical thread, then milestone replies.
- **Mining stats sites.** MiningPoolStats "New PoW Coins" and minerstat "Coins to mine". A coin appears once a pool reports it.
- **r/gpumining, r/cpumining.** One detailed, low-hype guide post with full disclosure is welcome; repeated promotion is not.
- **Pool operators' social accounts.** Miners follow pools to see when a new coin gets a pool.

Privacy communities come second and are hostile to shilling:

- **r/Monero** requires affiliation disclosure and caps promotional posts at one per two weeks.
- **r/CryptoCurrency** bans promo links and removes project shilling; only neutral technical comments from an account with real history survive.
- **r/privacy** and similar: technical threat-model discussion only.

## 2. What content pulls traffic (in order of impact)

1. **Bitcointalk ANN thread**: overview, why another privacy coin, consensus and privacy mechanism, emission, mining guide, links (site, repo, explorer), roadmap, no-premine/no-presale disclaimer.
2. **Mining guide** ("5-minute MEOW mining"): download, config, pool endpoints, hardware suitability.
3. **Reproducible binaries with published hashes and signatures** before genesis, plus independent builders confirming them. This is the single strongest anti-scam signal for miners.
4. **Public testnet with worthless coins** and short milestone updates (Zephyr's pattern).
5. **Explorer and at least one pool** live at genesis.
6. **Whitepaper v2** in the plan's voice (PLAN.md §11), linked from the ANN.

## 3. Search intent to match

Miners search phrases like "new coins to mine", "new PoW coin fair launch no premine", "new privacy coin to mine", "CPU friendly PoW privacy coin", "mandatory privacy proof of work". The teaser now targets: fair-launch privacy coin, proof of work, no premine, Meownero, MEOW. Add "mineable", the algorithm name, and block time once ADR-001 fixes them.

## 4. Credibility signals vs scam signals

| Builds trust | Reads as scam |
|---|---|
| No premine, no presale, no team allocation, stated everywhere | Any presale, "marketing allocation", vague launch mechanics |
| Public repo, tagged genesis release, reproducible builds | Closed binaries, no hashes |
| Exact genesis time (UTC), initial difficulty, block reward published ahead | Surprise launch, secret mining window |
| Testnet milestones and a roadmap | Hype-only ANN with images and no technicals |
| Disclosed affiliation when posting | Bot amplification, mass tagging, repetitive hashtags (already vetoed in PLAN.md §11) |

## 5. Precedents

- **Kaspa (2021):** fair launch, no premine, transparent emission pages; the fairness story is what built the community.
- **Tari (mainnet 2025-05-06):** ex-Monero contributors, RandomX merge mining, one-click desktop miner; press followed the accessible-mining angle.
- **Zephyr (2023):** public testnet, staged updates, ANN kept current through hard forks.

## 6. What the teaser can and cannot do today

Done on the site: entity-first copy, title and description matching miner search intent, Organization/WebSite JSON-LD with no personal fields, llms.txt, sitemap, robots explicitly allowing AI crawlers, OG image, security headers, no analytics or third-party scripts.

Blocked until the chain exists (Stage 2 / ADR-001): ANN thread, mining guide, testnet binaries, genesis date, explorer, pool. Each of those is a new page or section on the site when it lands.

Open group decisions that gate outreach: public identities (#7), ticker collision (#6), which channels to open and who moderates them. Until then the site deliberately has no social links and no email capture: a privacy coin collecting emails on day one is the wrong first impression.

## 7. Sequence

1. Now: teaser live, indexable. No outreach yet.
2. ADR-001 signed: add "how it works" section (algorithm, block time, emission) and a repo link.
3. Testnet: publish mining guide and testnet binaries, open Bitcointalk ANN, one post each in r/cpumining or r/gpumining.
4. Genesis minus two weeks (PLAN.md §1.1 item 4): exact UTC time on the site, reproducible binaries with hashes, explorer, pool commitments, ANN update.
5. Post-genesis: mining-stats listings, media briefings on the fair-launch and reproducible-build angle.
