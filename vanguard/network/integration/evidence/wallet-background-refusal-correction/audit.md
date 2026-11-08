# Wallet startup mining refusal correction

Authority: adopted lead interaction `7c011923-32e9-49c2-8abc-1af68a51b5ed`.
This is the previously unused correction pass of the wallet setup round whose
first edit was 2026-11-04 18:39:53.627327 UTC; absolute deadline 19:39:53.627327 UTC.
Base `4ba03433bef62708781a7302361c23b64883eba9`. Owned paths: vanguard/network only.

The one native runtime-only grant93d99660 was consumed at this base. Its controller
exports show nine functional PASS rows and seven wallet-dependent NOT_RUN rows.
The permitted locally selected traceback ends at the initial expect(), with
`ValueError: unknown CLI prompt; input refused`. The actual console/transcript
was never opened. Background mining is a source-supported explanation, not an
observed identification of that private prompt. Same-run exact CID/label/name
absence and staging deletion completed; original evidence remains immutable.
Native evidence attachment6c887dad-e955-4238-8e95-1be68dc76ca4 is separate from this
source packet. No native retry or further admission is authorized.

All upstream references below are pinned to e151643c5269c83bf24a83b2548e2493876026b2.
The prior complete per-option/command audit remains in wallet-setup-correction/audit.md.
Its startup conclusion omitted this branch and is superseded here:

| Premise / behavior | Pinned source | Finding / disposition |
| --- | --- | --- |
| Loopback daemon defaults to trusted | src/wallet/wallet2.cpp:458-480 | Local address detection assigns trusted=true unless explicitly configured otherwise. No trust option changes. |
| Fresh wallets default to asking about background mining | src/wallet/wallet2.cpp:1264 | m_setup_background_mining(BackgroundMiningMaybe); prior audit missed this default. |
| Startup calls mining setup before returning to command prompt | src/simplewallet/simplewallet.cpp:4537-4539 | When no positional command is provided, check_background_mining(password) runs. Our interactive CLI follows this path. |
| Setup question is conditional | simplewallet.cpp:5210-5256 | Trusted wallet, not already active, default Maybe. Full fixed three-line explanation followed by Do you want to do it now? is emitted. Exact native condition/prompt remains unobserved. |
| Confirmation syntax | simplewallet.cpp:277-285 | input_line adds space+[y/N]+colon+space. Full source literals are required together; a shared final question alone is insufficient. |
| Negative response disables future background setup | simplewallet.cpp:5257-5261 | Non-yes sets BackgroundMiningNo, rewrites wallet, prints disabled and returns before any start_background_mining(). |
| Positive branch must remain unreachable | simplewallet.cpp:5264-5266 | Our sole new response is literal n+newline, never yes. No mining API or native workload is added. |

The implementation in cli()/expect() recognizes the complete pinned four-line
question only while waiting for STARTUP_WALLET_PROMPT. It sends n once per CLI
process, clears the consumed prompt buffer and continues waiting for the same
wallet prompt. Unknown, altered, repeated, command-time, password and other
confirmation prompts retain the existing refusal path. A complete wallet prompt
still wins the existing match. No assertion, command list, credential write,
RPC login behavior, row witness, public code/schema, native workload or cap changes.
Diagnostic line anchors move by eight only; vocabulary is byte-for-byte unchanged.

Four connected tests use the actual cli()/expect() and disposable Python PTY CLI:
accepted4ba03433 refuses the exact startup question; candidate answers n and
completes create/reopen; a repeat gets only the first negative answer; altered or
command-time questions get no answer. The fixture records only synthetic literal
n, never a real credential or native transcript. The original unknown-confirmation,
password, EOF/EIO, save/exit, daemon Digest, 17-denial, rotation and export tests remain.
Pinned-source checks bind the full question strings, default and startup call to
Git objects. These fixtures do not prove native prompt behavior or wallet rows.

The original lock path/device/inode is guarded before any open/flock during source
checks. Runner/freezer/build.sh/source-lock, noncandidate inputs, actual compiled
identity, row assertions and seven pre-existing unowned bytecodes must remain
unchanged. Source checks use substituted native/Docker/admission effects.

Platform source consultation first. The lead's conditional Security follow-up
applies if Platform identifies a changed auth/credential/isolation/export surface.
Any finding beyond the exhausted round or requiring assertions/contracts returns
to lead. Only accepted exact source can receive a separate fresh900s runtime-only
reuse grant bound to published retained authority3eedebc0/digest1b2815e2. This
correction grants no native execution. Core47234b59/count2 and later formal
Security are unchanged; full native matrix/independent acceptance/lead integration
remain open. launch_ready=false;public_launch=false. Needs TJ: None.
