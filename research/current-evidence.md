# Current Meownero evidence and acceptance

As of 2026-10-09, accepted tester-kit integration is
`9a913b88eb8084660d6f174a6f7836d62825e2b1`, with exact reviewed tree
`33223a376c02b1ed965a40c58a5947b3ee5b0704`. Its parents are the prior integrated
base `86393a36b11d2eb3d395bb63a96ea405a8059520` and accepted tester candidate
`89c873b5fdbcc678236d285a4f1920143f314e00`. This later index-only update records
acceptance and parent verification; it does not change the measured tester code.
Use this index for current acceptance. Historical writer reports are preserved
and can still say review or integration was pending at their publication time.

| Work | Current disposition | Authoritative evidence |
| --- | --- | --- |
| Longer local ARM64 payment/recovery trials | Independently accepted and integrated; closed | [TJS-1816 review](<private-tracker>/TJS/issues/TJS-1816#document-independent-review), revision `815b81ff-1093-4967-8707-eebb9670eb0e`, candidate `c6620342328f313e1e9bdfb79570d5245e669090`; [parent integration receipt](<private-tracker>/TJS/issues/TJS-1816#comment-f3cbb95c-09a9-4793-b26b-d359578a84e0) |
| Four-payment Railway/build-mac native recovery witness | Independently accepted, local integration independently verified; closed | [TJS-1856 verdict](<private-tracker>/TJS/issues/TJS-1856#document-review-verdict), revision `b17b8ba8-9b63-42e4-9734-d4407d141755`, candidate `be33beb62e5e97089dd2e204bce68da2cfd1478b`; [integration verification](<private-tracker>/TJS/issues/TJS-1856#comment-a3416904-98c5-42ab-b44e-ef5e885ad988), merge `86393a3`, exact tree `c776cbd027278977ff00793c61d442b2221cb693` |
| Local Vanguard tester kit | Independently accepted and locally integrated; parent tree, ancestry and all 1,163 pre-existing file/symlink hashes verified. Fresh payment/receive/restore/later-spend journey passed in 63.646 seconds; F1–F4 resolved. Supported build-mac ARM64 profile only; closed | [TJS-1870 acceptance](<private-tracker>/TJS/issues/TJS-1870#document-review-verdict), revision `66791105-ffe2-413f-b2dd-182976a05698`, exact candidate `89c873b5fdbcc678236d285a4f1920143f314e00`; [local integration receipt](<private-tracker>/TJS/issues/TJS-1870#comment-775b155e-7dd1-4f5e-9320-1d13d2817d8c), merge `9a913b88eb8084660d6f174a6f7836d62825e2b1`; [tester guide](../docs/vanguard-tester.md) |
| Historical selected-policy 9/90 testnet-v0 journey | Separate accepted local policy witness; not current FCMP++/CARROT integration | [Historical journey](../chain/testnet-v0/journey.md), [writer receipt](testnet-v0-journey-tjs313-2026-09-22.md) |
| Restricted wallet controller | Completed 52-case bounded checkpoint | [Recovery index](recovery-index-2026-09-13.md), [milestones](../docs/milestones.md) |

The first two rows do not need another soak or Railway/auth recreation. Their
native evidence concerns accelerated upstream regtest, not the selected 9/90
Meownero policy. `UNVERIFIED_LIVE_TIPS` remains the limit of post-run receipt
reconciliation. The previous full x86 load/backlog suite gap, current-lineage
selected-policy integration, portability and public-testnet/production readiness
remain explicit. Accepted local evidence does not close those gates.

Parent verification at 2026-10-09 11:09 UTC found the merge's exact parents and
reviewed tree, no committed candidate-to-merge difference, and all 1,163 original
entries unchanged (219,978,931 bytes hashed; zero changed or missing paths).
Independent acceptance attachment SHA256
`903fad2451225a985e2bd3883fb757f682b247669120b2f0bdc0d4280f5cc1d0`
was read back: all 15 outer manifest members, 39 native evidence members and 14
candidate-source hashes match. Full offline verification passed with
`UNVERIFIED_LIVE_TIPS` retained. The timestamped reviewer cleanup receipt records
eight exact owned containers absent and six successful private paths removed;
failed diagnostic controls remain preserved. No public push, installer, new
native workload, cloud service or credential operation was part of integration.

Observed behavior: historical writer reports retain the state at handoff; current
Paperclip reviewer verdicts and parent receipts establish later acceptance and
integration. Update this index when those records change, rather than rewriting
the historical writer reports.
