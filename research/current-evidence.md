# Current Meownero evidence and acceptance

As of 2026-10-09, integrated base is `86393a36b11d2eb3d395bb63a96ea405a8059520`.
Use this index for current acceptance. Historical writer reports are preserved
and can still say review or integration was pending at their publication time.

| Work | Current disposition | Authoritative evidence |
| --- | --- | --- |
| Longer local ARM64 payment/recovery trials | Independently accepted and integrated; closed | [TJS-1816 review](<private-tracker>/TJS/issues/TJS-1816#document-independent-review), revision `815b81ff-1093-4967-8707-eebb9670eb0e`, candidate `c6620342328f313e1e9bdfb79570d5245e669090`; [parent integration receipt](<private-tracker>/TJS/issues/TJS-1816#comment-f3cbb95c-09a9-4793-b26b-d359578a84e0) |
| Four-payment Railway/build-mac native recovery witness | Independently accepted, local integration independently verified; closed | [TJS-1856 verdict](<private-tracker>/TJS/issues/TJS-1856#document-review-verdict), revision `b17b8ba8-9b63-42e4-9734-d4407d141755`, candidate `be33beb62e5e97089dd2e204bce68da2cfd1478b`; [integration verification](<private-tracker>/TJS/issues/TJS-1856#comment-a3416904-98c5-42ab-b44e-ef5e885ad988), merge `86393a3`, exact tree `c776cbd027278977ff00793c61d442b2221cb693` |
| Local Vanguard tester kit | Implementation/rehearsal in progress; independent reproduction and integration pending | [TJS-1870](<private-tracker>/TJS/issues/TJS-1870), [tester guide](../docs/vanguard-tester.md) |
| Historical selected-policy 9/90 testnet-v0 journey | Separate accepted local policy witness; not current FCMP++/CARROT integration | [Historical journey](../chain/testnet-v0/journey.md), [writer receipt](testnet-v0-journey-tjs313-2026-09-22.md) |
| Restricted wallet controller | Completed 52-case bounded checkpoint | [Recovery index](recovery-index-2026-09-13.md), [milestones](../docs/milestones.md) |

The first two rows do not need another soak or Railway/auth recreation. Their
native evidence concerns accelerated upstream regtest, not the selected 9/90
Meownero policy. `UNVERIFIED_LIVE_TIPS` remains the limit of post-run receipt
reconciliation. The previous full x86 load/backlog suite gap, current-lineage
selected-policy integration, portability and public-testnet/production readiness
remain explicit. Accepted local evidence does not close those gates.

Observed behavior: historical writer reports retain the state at handoff; current
Paperclip reviewer verdicts and parent receipts establish later acceptance and
integration. Update this index when those records change, rather than rewriting
the historical writer reports.
