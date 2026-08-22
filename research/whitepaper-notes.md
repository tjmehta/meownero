# Whitepaper notes

The canonical PDF is titled **MEOWNERO WHITEPAPER: The Future of Private Transactions, Meow With More Fur**, version 1.1, January 2026, merge-mined edition. It is seven pages.

## Proposed design in the draft

- Mandatory private transactions.
- RingCT, stealth addresses, ring signatures, and network-layer privacy.
- Two-minute blocks.
- Merge-mining with Monero using AuxPoW.
- One MEOW per block forever: 720/day and 262,800/year.
- No premine, founder reward, or developer tax.
- Community governance and funding.
- Full-node, remote-node, mobile, and hardware-wallet roadmap.

## Required corrections before implementation

- The draft says CryptoNight, but modern Monero uses RandomX. Merge-mining compatibility must be researched and proven rather than assumed.
- Kovri is obsolete; network privacy should evaluate current Monero/I2P/Tor approaches.
- The claim that an attacker must control both Monero and Meownero hashrate is too strong. AuxPoW security and parent-chain miner incentives need a proper threat model.
- Ring-size language predates FCMP++-era Monero design. Do not freeze legacy privacy assumptions into the fork.
- the whitepaper author's latest direction (2026-08-22) is to avoid a cosmetic Monero copy: consider a Zcash-like architecture with privacy mandatory and a fair, non-sketchy emission.
- Treat the whitepaper as product vision and historical context, not an implementation specification.
