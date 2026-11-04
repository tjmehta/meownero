# Readline normalization and private skeleton boundary

Authority: authenticated answered interaction463159fd-99f1-423a-b45f-f3be3a8411c4,
question startup_timeout_next_scope; Meownero lead8f050fb0, runeb9a155d;
report commentde2ac1ea-14a2-45b7-a683-c44c8982fcfb. Description-only adoption
preserved owner, stages, holds, routing and monitor state. Baseline818a4fc646d74b177f2981045b1c1eb125998a9b,
tree888dd8ec9f99b30cb87b9cbe0ec02396036953e9. Owned paths vanguard/network/.
First edit2026-11-04T20:36:53.938618Z; deadline21:36:53.938618Z. One implementation
pass, one correction pass maximum. Qualification records actual pass consumption.

The preceding61f43dcc native attempt remains consumed: ATTEMPTED_FAIL at initial
STARTUP_WALLET_PROMPT, nine of sixteen functional rows PASS, seven wallet rows
NOT_RUN. The actual console has never been opened. Readline is a source-supported
hypothesis, not the observed cause. No native attempt, admission, build, original
heavy-lock open/flock, wallet secret inspection, or raw console inspection is
part of this source round.

All upstream citations below bind e151643c5269c83bf24a83b2548e2493876026b2:

| Boundary | Source evidence and resulting implementation |
| --- | --- |
| Readline enabled in the retained CLI | Published build.json NEEDED libreadline.so.8, authenticated by the lead; CMakeLists.txt:1014 defaults USE_READLINE ON. |
| Prompt formatting | contrib/epee/include/console_handler.h:344-349 wraps the prompt in byte01/ESC color/byte02 markers. contrib/epee/src/readline_buffer.cpp:98-101 redisplays a blank prompt then the actual prompt. |
| Exact prompt and mining question | src/simplewallet/simplewallet.cpp:9068-9080, 5210-5266; prior wallet-background-refusal audit preserves the complete strings and negative branch. No answer or command changes. |
| Mnemonic dictionary | src/mnemonics/english.h:55 onward, all1626 entries copied into the in-driver helper with the complete source license. Tests compare the embedded sequence to the exact Git object and exercise every word in bounded batches. |
| Real-format public privacy fixtures | tests/functional_tests/wallet.py:69-99 supplies the25-word English seed, standard/subaddress and64-hex view/spend keys. integrated_address.py:63 supplies the106-character integrated address. These are upstream public fixtures, never native wallet data. |

Only cli()/expect() and the new private _cli_skeleton helper change in the native
driver. An exact818a4fc AST scope assertion protects every other statement;
historical guard-call multisets, command literals, password writes and rows remain
identical. The standard-library APIs follow existing private-file/PTY patterns;
real PTY, os.open(mode0600), os.replace and symlink tests exercise the relevant
installed Python3.12/3.15 behavior. No new dependency or runtime input is needed.

Before both normal and mining-question matching, normalization removes complete
CSI (including ?2004h/l) and OSC (BEL or ESC-backslash terminators), removes01/02
markers, handles backspace, converts CRLF to newline, and resets the current line
at a bare CR. Thus redisplay retains only text after the last CR on each physical
line. The same exact wallet regex and full four-line mining question remain.
Literal n+newline is still permitted only once at startup. Altered, repeated,
command-time and unknown confirmation/password prompts still refuse. Unknown
wallet prompt text times out. No command, credential, network, workload or mining
behavior changes.

Every cli/expect exception, including preparation and post-exit assertions,
reaches the new private helper after the existing cleanup path. It considers only
the last8192 transcript bytes, discarding any incomplete first line so a clipped
label/secret cannot cross the cutoff. It drops entire lines containing seed,
mnemonic, key or password (case-insensitive, including across CSI/control markers),
or the loaded password contents. It masks pinned English words as <w>, base58
runs >=12 as <b58>, and hex runs >=16 as <hex>. Overlapping sensitive spans merge;
English words win equal-span ties. Literal and displayed lexical offset maps recognize CSI/OSC-split
secrets and protect overwritten literal words; every control/escape byte in retained lines, including inside masked
spans, renders as <0xXX>. Original LF bytes also have visible tokens and layout
newlines. Non-ASCII bytes render visibly as well. Output is deterministic.

The helper creates an exclusive0600 private temporary file and atomically replaces
cli-skeleton.private in the owned private root. A preexisting destination symlink
is replaced without touching its target. No skeleton or raw transcript is added
to public exports, schema, row vocabulary, or controller receipts. The existing
raw private transcript remains inaccessible to model inspection. Any later granted
same-run inspection may open only the skeleton, post at most2048 bytes verbatim,
and must perform exact staging deletion before that run ends. This source packet
contains only fixture output and source, never a native skeleton or transcript.

Connected controls use actual cli()/expect() with a disposable Python PTY fixture:
colored blank/real redisplay, private CSI, both OSC terminators, markers/backspace,
normal create/reopen and full mining question. Exact known-bad818a4fc times out
or refuses the same two readline replays before any negative answer; candidate
passes. Adverse wrapped questions still refuse and reap; only a repeated mining
question gets the first n. The failure fixture verifies skeleton creation and
removal of dictionary words, address-length base58,64-hex material and the actual
synthetic password file contents. Public upstream25-word seed/address/key
fixtures, every dictionary word, mixed case, all C0/DEL/C1 controls, CSI-split
secrets, tail truncation and destination-symlink replacement are also checked.
These model contracts do not establish the actual native prompt or wallet rows.

Source diagnostics tables move by207 lines only; their code/schema vocabulary is
unchanged. The review packet separately binds pinned english.h,
integrated_address.py and readline_buffer.cpp. reference-inputs.json remains
unchanged because the frozen build_identity includes that complete object;
adding review-only references there would incorrectly invalidate reuse. An
existing reuse test now compares the exact818a4fc build identity to this candidate. Freezer code, build.sh,
run-profile.py, profile/overlay/crypto pins, daemon RPC, authentication,17-denial,
rotation, export schema, caps and actual compiled identity remain unchanged.
The seven preexisting unowned bytecodes are neither staged nor altered.

Consult Platform first on this exact committed packet, then Security on the new
privacy seam and controls (lead items2/3). P2P retains implementation/cleanup
ownership and a self-owned blocked waiting path. Only both source acceptances can
precede a separate fresh exact900-second --reuse-build grant, using published
retained authority3eedebc0 and digest1b2815e21fb4c41ccd269e73f3eca3f905c872900e69d5a6d1c24537406275d6.
No earlier grant is reusable. A further native startup failure requires the
bounded skeleton and a concrete fix returned to the lead; no blind new patch.
Core stagebab7a7aa/decision47234b59/count2 and later formal Security18129dc4 remain
unchanged. Full matrix, independent native acceptance and accepted-only lead
integration remain open. launch_ready=false; public_launch=false. Needs TJ: None.
