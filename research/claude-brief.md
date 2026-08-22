# Planning brief for Claude Fable

You are the technical planning owner for Meownero. This is a planning-only pass: do not implement cryptocurrency code, vendor an upstream codebase, or create a remote repository.

Read every file currently in this repository, including the PDF and image under `assets/` and all `research/` notes. Treat `research/chat-transcript.md` as the product-history record and `research/whitepaper-notes.md` as a warning that the January draft contains obsolete or unsupported technical claims.

Write a single decisive `PLAN.md` that can guide a credible first engineering phase. It must:

1. State the product thesis and non-negotiables from the chat: independent coin, mandatory privacy, fair/honest launch, meme-worthy brand, no premine/founder tax, and no cosmetic rename.
2. Compare at least these implementation directions using current primary technical sources where useful:
   - a modern Monero-derived fork,
   - a Zcash-derived design with privacy mandatory,
   - Pirate Chain as a cautionary comparison,
   - a clean-room/new-chain approach only if justified.
3. Make a recommended architecture decision or an explicitly bounded Phase 0 decision process. Do not pretend unresolved cryptographic or consensus questions are settled.
4. Audit merge-mining feasibility with modern Monero/RandomX. Treat the whitepaper's CryptoNight/AuxPoW claims as unproven until verified.
5. Recommend privacy primitives based on current upstream reality (including FCMP++-era Monero work and modern Zcash shielded-pool technology), not the stale Kovri/ring-size language in the draft.
6. Propose a fair emission and launch process. Address perpetual security budget, early-holder advantage, dev funding, genesis distribution, disclosure, reproducibility, and mining-pool incentives.
7. Include threat model, legal/compliance questions to obtain counsel on, upstream licenses/attribution, supply-chain security, reproducible builds, key management, testnet/mainnet gates, wallets, node/miner tooling, explorer constraints for a private chain, and incident response.
8. Define milestones with observable exit criteria, starting with a short throwaway feasibility spike before any fork is blessed.
9. Separate fun branding/launch work from consensus-critical engineering, while preserving the "Much Meow" voice.
10. End with a concrete first 10 issues suitable for GitHub and a short list of questions TJ/the whitepaper author must decide.

Be blunt about flaws in the historical whitepaper. Prefer correctness and credible scope over hype. Include links to primary sources in a references section. The deliverable is complete when `PLAN.md` exists, is internally coherent, and `git diff --check` passes.
