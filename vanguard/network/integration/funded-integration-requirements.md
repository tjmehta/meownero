# Item-5 package / wallet integration requirement report — current F1 boundary

This is the current addendum to `../remaining-integration.md` and the launch
sheet's exact package/wallet integration requirements. It preserves those
historical source records and accepted tester/distribution trials. No package
writer, CI/build helper, upstream native code or release gate is changed.

| Requirement / integration owner | Current evidence or prepared path | Remaining gate |
| --- | --- | --- |
| Exact selected-profile native artifacts / P2P then existing package owner | b6f54326 genesis boundary PASS; three retained production binaries from unchanged e151643c + ten-file9/90 overlay, published retained authority3eedebc0/digest1b2815e2 | F1 source review and native run; existing package owner must carry accepted profile/overlay/binary manifests into the existing launcher/distribution. No upstream regtest package/config substitution |
| Native network identity and startup / P2P, Core/Security | Prior UUID/chain-request and launcher-manifest negatives, no-fallback genesis, native handshake and reopen are accepted only as early premise | Advancing-chain and final topology evidence; foreign DB remains upstream limitation with one-profile/one-root rule; formal Core accepts/rejects mitigation |
| Checkpoint refusal / Core | Source-established N/A: core initializes defaults only for MAINNET and update_checkpoints returns before non-MAINNET work | Formal Core concurrence, no native checkpoint row and no false claim that upstream checkpoints.cpp has an empty TESTNET table |
| Wallet activation/timing / P2P, Core/Privacy | Prior CLI height0/store/separate getter and native address/denial/rotation rows passed; F1 reuses exact helpers | F1 funded online path; offline-wallet fork agreement remains NOT_RUN. Height defaults, date conversion, general offline restoration/gamma semantics and custom unlock vectors are not certified |
| Authenticated signer / P2P, Security | Separate private loopback signer RPC with native generated login, explicit height0 mnemonic restore, no auth-disable or restricted transfer; fixed closed public witnesses | Platform→Core source consultation→Security acceptance, fresh grant, native F1 confirmation. Source fixtures do not certify native privacy/security |
| Payment/receive/restore/later spend / P2P, Core | F1 source binds b1 maturity N60/61/62, payment b61, restored output/key image, received-output spend b71 confirmed N72, finish b72 admitted at N73; native estimator and serialized FCMP++/CARROT checks | Native F1 NOT_RUN; fresh grant after serial reviews; exact80-count/10-transaction ceiling. Proof/output/legacy-ring adverse matrix remains NOT_RUN |
| Consensus/projection/tree/cache / P2P, Core/Privacy | Existing helper and source consultations retained; unchanged lock conversion and zero-premine9/90 policy | Rule8/nonzero vectors, wrong coinbase unlocks, all pool/supplement/main/alternative/cache routes, native projection59/60/61 controls, roots/layers/IDs/reorg, foreign differential and corruption remain NOT_RUN |
| Persistent seeds/operator/release / lead and Platform/native-release owner | Current finite recipe in funded-operators.md; preparation-only primary/recovery placeholders retained | Assigned persistent operators and capacity, third independent client/seed topology, incident/withdrawal/backup qualification, public checksum/key custodian, signed final manifest/downloads and activation. No public launch |

Review sequence is source Platform, source Core F1 semantics, source Security,
then separately fresh Platform runtime grant. Only after native F1 PASS should
the reconciled full matrix go to formal Core (current decision47234b59/count2),
then formal Security18129dc4 and accepted-only lead integration. Any remaining
adverse rows become a later milestone or explicit limits by Core's ruling;
they are not silently waived by F1. launch_ready=false; public_launch=false.
