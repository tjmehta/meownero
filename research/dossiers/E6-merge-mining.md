# E6 — Merge-mining with Monero

**Exploration:** Launch merge-mined, solo, or hybrid — and what does the merge-mining precedent record actually support? · **Status:** Draft · **Date:** 2026-08-22

## 1. Draft verdict (DRAFT)

The precedent record is now three-sided and unusually instructive. **Longevity:** AuxPoW itself is old and stable — Namecoin has merge-mined with Bitcoin since 2011–12, Dogecoin with Litecoin since block 371,337 (2014-09-11), and Dogecoin is the model *success*: most major Litecoin pools carry it, its hashrate jumped ~1500% in the first month, and it has been effectively attack-free since — but that maturity took years and began from an existential low-hashrate crisis. **Sabotage:** CoiledCoin (2012) confirms the zero-cost-attacker class — the Eligius pool unilaterally merge-mined it and killed it with empty blocks; academic work (Judmayer et al., "Merged Mining: Curse or Cure?") generalizes the pattern. **Centralization:** Namecoin's own materials admit single pools have repeatedly held ~80% of its hashrate — merge-mining can *concentrate* as easily as it secures. **RandomX/Monero specifically:** exactly one production precedent, Tari (mainnet May 2025, ~15 months) — mechanism verified against Tari RFC-0132 (aux commitment in Monero coinbase `tx_extra`, zero Monero consensus changes, aux chain validates a Monero PoW package including seed tracking). Verdict direction: merge-mining remains a genuine *decision*, not a default — the Dogecoin trajectory shows the model can mature into real security; CoiledCoin and Namecoin show a young, low-participation aux chain is at the mercy of any large parent pool. A solo-RandomX launch with merge-mining as a later, audited upgrade (Dogecoin itself added AuxPoW ten months post-launch) is the emerging conservative shape — to be decided at ADR-001, per PLAN.md.

**PLAN.md impact:** none structural — §6's audit holds and gains the Dogecoin-timeline nuance ("added later" is itself precedented). One correction candidate: PLAN.md §6.2 says FCMP++ does not change Monero's PoW — still believed true, but with FCMP++ now confirmed as *not yet on mainnet* (stressnet-only, v0.19-alpha; hf milestone draft/no date), the "verify against shipped hard-fork code" task cannot complete until upstream ships. Merge-mining validation code would target today's 0.18.x mainnet rules and must track the eventual v0.20.

## 2. Production precedents & maturity evidence

- **Namecoin (2011/12–present):** oldest AuxPoW deployment; full Bitcoin parent header + coinbase committed in the Namecoin block's AuxPoW structure. Participation is a *subset* of Bitcoin hashrate; Namecoin presentations concede three different pools have each at times held ~80% of its hashrate. No catastrophic public double-spend on record, but the concentration is the documented risk. `[SECONDARY]` — Namecoin QCon 2017 presentation + merged-mining literature; pin the presentation PDF.
- **Dogecoin (2014–present):** AuxPoW activated at block 371,337 on 2014-09-11, ten months after launch, in response to declining standalone hashrate; major Litecoin pools adopted quickly; network hashrate rose ~1500% within the first month; regarded as the successful maturation case, with the caveat that its security is concentrated in a handful of Scrypt pools. `[SECONDARY]` — CoinDesk 2014 activation coverage, Binance Research merged-mining case study, litecoinpool.org announcements; multiple independent outlets agree, upgradeable if load-bearing.
- **CoiledCoin (2012):** Eligius operator unilaterally enabled merge-mining and stalled the chain with majority-hash empty blocks; project died. The canonical zero-marginal-cost sabotage precedent. `[SECONDARY]` — Judmayer et al. (SBA Research, CBT 2017) + contemporaneous accounts; the academic paper is the citable source.
- **Academic synthesis:** Judmayer et al., "Merged Mining: Curse or Cure?" — child chains inherit pool centralization; miners may value child rewards at ~zero and defend accordingly; independent attackability of child chains. `[VERIFIED-PRIMARY]` — publications.sba-research.org PDF.
- **Tari (May 2025–present):** the only RandomX/Monero production precedent; ~50% of blocks via Monero merge-mining, ~50% SHA3 solo (hybrid); mechanism per RFC-0132: Blake2b-256 aux-header hash in the Monero coinbase `tx_extra` merge-mining subfield → binds into Monero's tx merkle root → `MoneroPowData` package (header fields, RandomX VM key, coinbase merkle proof, coinbase extra) validated by Tari nodes against Tari's own difficulty; **no Monero consensus changes**. `[VERIFIED-PRIMARY]` — rfc.tari.com RFC-0132 (fetched 2026-08-21); ~15 months of production `[SECONDARY]` for incident record — check Tari's post-mainnet history for reorgs/incidents.
- **Monero context:** FCMP++ not on mainnet (beta stressnet since 2026-05-06; v0.19.0.0-alpha builds; Trail of Bits + Cypher Stack phase-1 audits complete; "fcmp++ hf" milestone draft, no due date; mainnet expected late 2026–2027). Merge-mining mechanism unaffected by FCMP++ per current design (PoW untouched), revalidate at v0.20. `[SECONDARY, consistent across technical sources]` — pin from monero-project milestone + MRL notes.

## 3. Consensus/crypto delta

No new cryptography. Moderate consensus delta on either candidate: validation of the Monero PoW package including **tracking valid Monero RandomX key-block seeds** (Tari's `MoneroPowData` pattern), plus multi-aux support — the coinbase `tx_extra` merge-mining field is a shared resource; pools already carrying Tari can only add Meownero via an aux merkle tree in that field. `[OPEN — verify Tari's multi-aux handling in code, not just RFC]` On Candidate Z this compounds with E5's RandomX integration; on Candidate M it follows the Tari template more directly.

## 4. Security assumptions introduced

- Parent-chain miner behavior: the zero-cost-attacker class is **accepted, not mitigated**, by choosing merge-mining (CoiledCoin is the proof; Dogecoin's safety came from majority-parent participation that took years).
- Meaningful pool opt-in at launch — otherwise security is a rounding error of Monero's hashrate while the attack cost for any large pool stays ~zero.
- Multi-aux coexistence with Tari works as designed.

## 5. Audit burden

The Monero-PoW-package validation path is consensus-critical: full adversarial review + fuzzing (malformed proofs, stale seeds, fake aux merkle branches). Proxy is non-consensus but supply-chain-relevant. Hybrid mode (Tari-style) roughly doubles the mining-path review surface.

## 6. Kill criteria (unchanged from PLAN.md §5 E6)

§6.3 security model judged unacceptable for a young chain; or insufficient pool commitment (soundings, not hope); or the delta fails the minimal-delta bar on the chosen lineage.

## 7. Safest fallback

Solo-mined RandomX launch — now *positively precedented as a sequencing strategy*: Dogecoin launched solo and added AuxPoW at month 10 when the need was proven and the ecosystem ready. Merge-mining can be a later, properly audited upgrade.

## 8. Open verification tasks

- [ ] Pool-commitment soundings: which Monero pools (and P2Pool) would realistically carry a second aux chain, and under what conditions.
- [ ] Verify Tari's multi-aux/`tx_extra` handling and seed-tracking implementation in tari-project code (RFC → code check).
- [ ] Tari post-mainnet incident review (reorgs, difficulty events) — 15 months of history to read.
- [ ] Pin Dogecoin AuxPoW activation (block 371,337 / 2014-09-11) and the hashrate-jump figure from primary-era sources.
- [ ] Pin the "fcmp++ hf" milestone state and re-check at ADR-001 (affects fork-point timing for Candidate M and revalidation timing for merge-mining code).
- [ ] Confirm current Monero mainnet hashrate from a live source (whitepaper's "~2 GH/s" remains unverified).

## 9. Sources

Primary: rfc.tari.com/RFC-0132_Merge_Mining_Monero · publications.sba-research.org (Judmayer et al., CBT 2017) · github.com/monero-project/monero milestone/1 · lib.rs/crates/minotari_merge_mining_proxy
Secondary (to upgrade or accept): CoinDesk 2014-09-11 Dogecoin AuxPoW activation coverage · Binance Research merged-mining case study · litecoinpool.org news #59/#60 · Namecoin QCon London 2017 presentation · en.bitcoin.it Merged_mining_specification · TU Wien merged-mining thesis (repositum.tuwien.at)
