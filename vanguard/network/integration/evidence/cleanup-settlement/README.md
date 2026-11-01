# Cleanup and settlement correction evidence

Writer: P2P/Mining run `3fa97f53-f96a-4717-8681-f4315e075725`.
Base: `cc711dba521cc2225f79fb21ffb7deb9d044e2c8`.
Read `../../cleanup-settlement.md` and `summary.json` first.

`lead-authorization.json` records the adopted 90-minute, one implementation plus
one correction continuation. `first-edit.json` and `correction-start.json` record
pass boundaries. No prior unused allowance was carried forward.

`cleanup-baseline.py` ran on the base and corrected candidate. The two JSON
receipts retain both effects on the base and the corrected status3 refusals.
`implementation-tests.log` retains an initial source-index race: tests began
before the asynchronous source freeze completed. `implementation-diagnostic.log`
and `implementation-source-check.log` identify and close that harness ordering
error. The bound implementation then passed24 checks. The correction added the
launcher settlement-receipt confirmation and adverse controls; its focused suite
passed27. The completed source suite passed206/61.135s with no skips.

`publication-freeze.log` binds the final metadata/index. Executable hashes did
not change after the206 tests. Four targeted final-index checks passed after the
metadata update. `final-binding-audit.json` checks58 candidate,32 reference and28
manager hashes and the unchanged original packet, units, helper and negative
baseline. The unchanged older rollback reproducer still exits1; its retained
log is expected failure evidence, not a passing protection claim.

Fixtures fork disposable producers/receivers and traverse the actual root main,
constructor, ingress, staged layout, local journal and surviving admission. They
inject every OS effect and installed authority. They do not qualify installation,
host survival, actual conditional cleanup or native acceptance. All temporary
fixture processes, files, sockets and descriptors use fixture cleanup.
