# Compressed evidence privacy gate

Before handing a milestone's evidence to review, run from the repository root:

```sh
python3 -B vanguard/network/integration/evidence/check_compressed_privacy.py --self-test
python3 -B vanguard/network/integration/evidence/check_compressed_privacy.py \
  --exclude-from vanguard/network/integration/evidence/compressed-privacy/publication-exclusions.txt
```

The second command is a required gate: any nonzero exit prevents a clean privacy
handoff. It scans gzip files, all concatenated gzip streams and nested gzip members
in tar archives. It refuses `/home/`, `/Users/` and unreadable members. Bare handles
pass by default, as Security ruled in TJS-4402 round 1 (review revision
`aa872913-a25d-4d74-b0d2-ff003a2daa21`). Repeated `--deny-user` arguments optionally
deny additional literal identifiers, including public references and tar ownership.
Diagnostics identify members without printing private matching content.

`--exclude-from FILE` accepts exact repository-relative paths, one per line, with
blank lines and `#` comment lines allowed. It does not expand globs or directory
prefixes. Every skipped gzip file is listed in `skipped`; `gzip_files` counts all
files and `scanned_gzip_files` counts those examined. `--root` selects an evidence
directory or a copy of that directory; exclusion paths remain repository-relative.
Nothing is excluded unless the caller supplies a list. A missing list file fails.

`publication-exclusions.txt` records the 14 evidence entries of the lead's TJS-3919
drop list, confirmed by Security. These private frozen archives must be removed
from **every** public commit. Skipping a file for this gate grants no publication
authority. A leaky sibling of an excluded path still fails the gate.

## Correction and verification

The comparison revision is `ff3a8031`; the task base `24e8fbb6` has identical evidence
bytes. The 14 drop-listed gzip files and six JSON files that bind them are restored
to exact comparison-revision bytes. Their attachment identities, lossless-retention
claims, frozen source hashes and matching provenance copies remain valid. They
intentionally retain private paths and must stay drop-listed.

All 126 included gzip files retain their bytes from the reviewed candidate
`2854343e39b021188fe78eac651f6aef809ae4cb`. The 52 changed gzip files still decode to
the specified path substitution of `ff3a8031`: the primary checkout prefix becomes
`<repo>` and other Linux home-directory prefixes become `~/`. There are no extra
substitutions. All other included gzip bytes and all three activation manifests
remain unchanged from that candidate. No workload or measured claim was rerun.

`verification.json` inventories all 140 gzip files with before/after encoded and
decoded hashes and sizes, publication inclusion, exact substitution comparisons,
restored JSON hashes and the four pre-existing manifest checks. This packet's
manifest additionally binds the gate and the new evidence files.

- `focused-tests.log`: 15 passing tests, including macOS home paths, exclusions
  through the CLI, a leaky sibling and the CLI's empty default identifier list.
- `privacy-scan.json`: exit 0, 126 gzip files scanned, 14 skipped, zero findings.
- `planted-leak-scan.json`: exit 1 on an isolated temporary copy with one extra
  gzip containing a synthetic Linux home path; only that member fails.
- `gate-runs.json`: commands, exit statuses and temporary-copy cleanup.
- `history-blob-map.tsv`: Security's original 36-row map, preserved byte-for-byte;
  every redacted target blob is verified against this candidate's bytes.

## Independent review and replay

Security independently re-reviews this correction. The lead owns integration and
public replay after acceptance. The history condition from round 1 still applies:
none of the 36 original leaky blobs may be reachable from the new public head,
and a decompressing scan must cover every newly reachable blob relative to
`e9833810`, across all commits. A clean tip-tree scan alone cannot establish that.

Only evidence paths change. `launch_ready` and `public_launch` remain false.
No activation or public push occurred.

Needs TJ: None.
