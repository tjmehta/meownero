# Original-byte and mnemonic-prefix skeleton correction

Authority: authenticated lead interaction 17b49b3b-84b7-4e73-83ce-629f10682b3a,
resolved by Meownero lead 8f050fb0-7908-4b7f-be53-45d17272cec7 in run
0da800eb-462c-4d8a-b00a-9bc860e788ff at 2026-11-04T21:11:38.501Z.
The exact answer is lead-decision.md and was adopted by a description-only issue
PATCH. This supersedes the pending decision in plan section117.

Reviewed base: 19c0401ae2ff79c36f26b4917173ffc12156deb0, tree
844d12aa2053bfd56e7aadf30d5d69413b45d1f0.
One implementation and one correction pass, maximum2700 seconds from
2026-11-04T21:16:10.360959Z. qualification.json records completion and elapsed
time. The correction changes test expectations and a dependent numeric anchor;
there was one production implementation edit. Both passes are accounted for.
Only vanguard/network/ is changed. No push or merge.

## Finding and correction

Platform's F1 showed that joined and displayed lexical views remove separators
or erase a preceding character. Exact dictionary lookup could then miss a word
which original-byte rendering subsequently emitted. Pinned upstream
src/mnemonics/english.h:52 uses English unique-prefix length3. A truncated or
overwritten word's first three letters can therefore disclose a mnemonic even
when its complete spelling differs.

profile-integration.py:539 derives prefixes from the existing pinned dictionary.
At550, the original byte sequence and identity offset map join the two existing
lexical maps. ASCII runs split at every nonletter, including C0/DEL/C1. At573,
every view masks the entire ASCII letter run when length>=3 and its first three
lowercase letters identify a pinned English word. At555/557 the skeleton's
lexical scanner also recognizes C1 CSI/OSC and C1 ST, retaining split-secret
coverage. The CLI prompt normalizer is byte-for-byte unchanged.

At575-587, matches map back to original byte offsets, union with existing masks,
and render solely from the original sequence. Reconstructed lexical text never
enters output. Brackets, colon and visible control tokens survive, including
controls inside masked spans. The existing password/sensitive-line dropping,
base58>=12 and hex>=16 masks, last8KiB cutoff with incomplete-first-line drop,
exclusive no-follow0600 temporary file, atomic replacement and public-export
exclusion remain. Heavy mnemonic-prefix masking may remove ordinary prompt
prose, intentionally; the skeleton is for structural diagnosis.

## Evidence and scope

test_direct_profile.py WalletCLI controls reproduce all three exact F1 leaks on
the exact19c0401a helper and prove the candidate masks them: abbey CR ready,
abbey BS x, aces NUL acidic. Tests also cover abbey BS x, abb DEL ey,
mixed-case/truncated prefixes, CSI/OSC/C1 splits, every C0/DEL/C1 separator,
all1626 pinned English three-letter prefixes, and a public upstream real-format
25-word seed interleaved with every control family. No three-letter mnemonic
prefix remains in the resulting skeleton. Public fixture material comes from
the pinned upstream tests/functional_tests/wallet.py, not private native output.

The connected disposable PTY fixture runs actual cli()/expect() failure and
checks original bracket/colon/control structure, including the fixture's
original123ABZ BS C bytes. Existing full redactor/address/key/password/tail,
atomic-write/symlink, PTY refusal/background-n, daemon/auth/17-denial/rotation
and export controls remain in the qualified suites. Python processes/files/PTYs
are real test fixtures; native executables, Docker, admissions and grants are
substituted. These tests do not establish actual native wallet acceptance.

An exact baseline comparison removes only _cli_skeleton from the driver and
requires every other byte to match. runtime_diagnostics.py changes only numeric
line anchors by2; the main/PRIVATE.mkdir test anchors follow that growth.
Commands, credentials, normalizer, prompt/refusal/answer behavior, guards, row
witnesses, schema and code vocabulary are unchanged. Runner/freezer/build.sh,
reference inputs, profile/policy/public contract and all noncandidate input
sections are exact baseline bytes. The actual runner build_identity is equal
to baseline, retaining compatibility with the existing compiled build.

qualification.json and logs disclose the initial fixture expectation failure
and the full-suite/index-refresh overlap. The stable source rerun is the
qualified result. Every guarded suite forbids original heavy-lock opens before
the call and checks aliases/descriptors before flock; zero attempts and unchanged
metadata are required. Seven pre-existing unowned bytecode hashes are preserved.

## Continuation

Platform assesses this exact immutable source tuple first. Security then
assesses lead items2/3, the mnemonic-prefix/original-only rendering privacy seam.
Ordinary findings stay with P2P under the lead's finite per-round bounds;
the same finding failing a second time returns to the lead. No runtime is
authorized by source review. Both acceptances precede one separately fresh
exact900-second runtime-only reuse grant, under every existing condition.

Published retained authority remains original Platform grant3eedebc0's root:
<agent-scratch>
and published receipt digest
1b2815e21fb4c41ccd269e73f3eca3f905c872900e69d5a6d1c24537406275d6.
No retained manifest, binary, private native file or raw wallet output was
opened. No lock acquisition, capacity/admission probe, Docker or native action
occurred. Every prior native grant, including61f43dcc, remains consumed.
If a future authorized startup fails again, inspect only the private skeleton
under the existing <=2KiB cause-post and same-run exact staging-deletion rules,
then return to the lead.

Core stagebab7a7aa, decision47234b59, changes_requested count2, later formal
Security18129dc4, holds/routing/monitor are preserved. No formal review re-entry.
New candidate native NOT_RUN; historical native ATTEMPTED_FAIL with9/16
functionalPASS and7walletNOT_RUN. Full consensus/maturity/payment/persistence/
recovery matrix, independent native acceptance and accepted-only lead
integration remain unfinished. launch_ready=false; public_launch=false.
Needs TJ: None.
