Lead decision, TJ may reverse: adopted with one stricter rule.

**Why stricter.** Pinned `src/mnemonics/english.h:52` declares `English(): Base("English", "English", {}, 3)`, so English seed words are identified by their first 3 letters. Masking whole dictionary words is therefore not enough. A word that a control byte truncates or overwrites (`abbey\bx` displays `abbex`) still leaks the word through its prefix. The skeleton exists to show prompt structure and control bytes, not prose, so heavy masking is acceptable.

**Scope.** You, from clean 19c0401a, in `vanguard/network/` only. One implementation pass and one correction pass, at most 45 minutes from the first edit. The driver exception covers only `_cli_skeleton` and its helper, plus the test anchors and bindings that depend on it.
1. As proposed: compute original-byte letter spans, splitting on every non-letter byte including C0, DEL and C1. Union them with the existing joined and displayed views.
2. Additionally, in every view, mask any ASCII letter run of 3 or more characters whose first 3 lowercase letters equal the first 3 letters of any word in pinned `english.h`. Use `<w>`. This covers truncated, overwritten and split words.
3. Render output only from the original byte sequence with every masked span replaced, so no reconstructed view can bring a word back. Visible control tokens stay.
4. Keep the base58 (12+) and hex (16+) masks, the sensitive and password line dropping, the 8 KiB tail, the atomic 0600 symlink-safe write, and public-export exclusion. Normalizer, prompt, refusal and answer behavior, commands, credentials, guards, rows, schema and codes are unchanged.

**Acceptance.**
- The three exact F1 fixtures fail on 19c0401a and pass on the correction.
- Prefix and overwrite cases are masked: `abbey\bx`, `abb\x7fey` and a seed word split by CSI, OSC or C1.
- A full real-format 25-word seed interleaved with every control family leaves no 3-letter seed prefix in the output.
- A connected `cli()`/`expect()` failure skeleton still shows the prompt's bracket, colon and control structure.
- Existing redactor, PTY, daemon, auth, denial and rotation controls stay green.

**Review.** Platform first, then Security on items 2 and 3, as before. Findings under the per-round bounds are yours to fix. The same finding failing a second time comes back to me. Then one fresh 900 s `--reuse-build` grant on the published retained authority (root from 3eedebc0, digest 1b2815e2…), with every existing condition. If startup fails again, post the skeleton and return to me.

Core decision 47234b59 (count 2) is unchanged. Native ATTEMPTED_FAIL with 9 of 16 functional rows PASS; launch_ready=false; public_launch=false. Needs TJ: None.
