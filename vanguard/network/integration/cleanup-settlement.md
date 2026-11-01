# Cleanup disposition and receiver-exit source correction

This is a bounded source correction to `cc711dba521cc2225f79fb21ffb7deb9d044e2c8`,
under lead interaction `48d2d44f-aed2-46ee-bce4-191e04a15ae5`, answered by
`5187a4f2-ee85-4a05-af3b-ed058e1cd572`. The existing P2P writer has one
implementation and one correction pass, at most 90 minutes from the first edit.
It supplies no installed launch, OS qualification or formal-stage decision.

The original surviving authority now reserves schema version 2. Its journal
binds task, attempt, source/index, boot, original supervisor/control/order/role
identities, namespace identity, contract and original absolute deadlines.
Each issued frozen record gains three monotone flags: consumed, completed and
uncertain. Consumed intent persists before authority delivery; completion
persists before acknowledgement. No recovery transition removes a record or
turns a flag off. Completed and uncertain can both be true when completion
was durable but the receiver then exited abnormally. Any existing disposition
refuses a new issuance with status 3, independently of restored local bytes.

The cursor only describes ordering. Recovery selects the next never-issued
record in the existing frozen recovery route. It does not retry an uncertain
effect or assert that the earlier cleanup succeeded. The connected ingress
obtains that record's position from its original authenticated surviving
authority before local journal admission. The local journal can align to that
position while retaining pending uncertainty and burning the original role
slot. Local journal bytes cannot supply the independent eligibility decision.
The existing backend still must enforce each operation's conditional
preconditions; an unresolved earlier cleanup can prevent later completion.
The unsupervised journal path retains its original strict ordering.

Receiver custody remains outstanding through close and actual exit. Settlement
accepts only the exact awaiting receiver after its PID is absent. A nonzero or
unknown status preserves per-record uncertainty and durably enters recovery-only
before clearing that custody. Settlement itself retains custody until the
original launcher confirms receipt of the durable settlement reply on the same
protected channel. A reply lost after socket send therefore cannot advance
activation. The original launcher can settle the same exited receiver as
uncertain, receive and confirm that result, then use eligible frozen cleanup.
Missing settlement, a wrong or live receiver,
failed persistence and detected lost settlement acknowledgement cannot renew
activation. A persistence failure poisons the surviving instance; subsequent
local restoration cannot repair it. Successful exit 0 plus acknowledged durable
completion retains normal advancement. Record 54 remains separately authorized
and refuses automatic recovery.

The fixture parent uses actual `waitpid` and exit-code conversion for its own
disposable child. The protocol status remains a TEST launcher assertion, not an
installed independent exit sensor. Both detected send failure and withheld
launcher confirmation after successful socket send are covered. The confirmation
is an addition to the existing private owner protocol, with the same identities
and transport; it grants no new record or installed sensor authority.

## Acceptance and evidence

The retained baseline probe observes two effects for uncertain cleanup 44,
settled 44 replay after uncertain 45, and refusal of cleanup after post-close
exit 9. The corrected connected fixtures use the same original producer,
restore all local order/role bytes on their original inodes, wait boundedly for
`entries_closed=true`, and require status 3 with exactly one prior effect.
Equivalent uncertainty controls cover every record 44 through 53, including
injected D-Bus and command effects. Later unused cleanup also traverses without
restoring the local journal. Other controls cover post-close nonzero/unknown
exit, lost close/completion/settlement replies, missing/wrong/live settlement,
concurrent entry, expiry, EIO/ENOSPC before issuance/admission/settlement,
supervisor loss, original-state restoration and separate record 54 refusal.

The prior writer196, Platform17 and Security24 receipts retain their original
attribution. Changed constructor/ingress/journal behavior requires the focused
supervisor/lifecycle checks and the completed 12-module source suite; old passing
receipts cannot establish this correction. First failures and diagnostics are
retained, including the initial source-index/test race. The older
`evidence/startup-custody/reproduce-rollback.py` stays byte-identical and must
still exit 1 as the known-bad unprotected fixture.

All effects, installation authority, manager observations, clocks, accounting
and terminal witnesses remain injected. Actual installed protected original
pre-import launch, independent producer-loss recovery, PID1 same-description
lock/namespace custody, hard external-writer enforcement, conditional OS cleanup
and terminal exit/tail through normal C unmount/release remain unimplemented or
unqualified. The full CID/workload/unit/W/loop/no-image matrix and native rows
remain NOT_RUN. See `connected-producer.md` for the retained partial boundary.

No original heavy-lock, host probe, installation, image/container/build/native
operation, merge or public launch belongs to this correction. Keep all pins,
caps, C/W/A/O custody, original deadlines, grants/two admissions, null bootstrap
and capabilities, empty registries, Core decision/count 2, subsequent independent
Security and accepted-only lead integration unchanged. Next: exact changed-source
Platform and Security assessment on the existing issue; the outside operator
retains the protected installed-launch/custody implementation route.

Python 3.15.2 primary references checked for the existing APIs:
[fsync](https://docs.python.org/3.15/library/os.html#os.fsync),
[waitpid](https://docs.python.org/3.15/library/os.html#os.waitpid) and
[exit-status conversion](https://docs.python.org/3.15/library/os.html#os.waitstatus_to_exitcode).
These API contracts do not attest installed durability, custody or authority.
