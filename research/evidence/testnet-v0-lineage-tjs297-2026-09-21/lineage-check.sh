#!/usr/bin/env bash
# Fresh-worktree lineage proof: every INPUTS/MANIFEST/EVIDENCE/BINARY manifest under the testnet v0 and QA evidence
# directories must verify from a clean checkout of COMMIT, and every path pinned by an INPUTS.sha256 must be tracked.
# Usage: bash lineage-check.sh COMMIT OUTDIR   (run from the repository root; OUTDIR must not exist)
set -uo pipefail
COMMIT=$(git rev-parse "${1:?commit}"); OUT=$(realpath -m "${2:?new output directory}"); mkdir "$OUT"
WT=$(mktemp -d /tmp/meownero-lineage-XXXXXX); rmdir "$WT"
git worktree add --detach "$WT" "$COMMIT" > "$OUT/worktree-add.log" 2>&1 || { echo "worktree add failed"; exit 2; }
{ echo "commit $COMMIT"; git -C "$WT" status --porcelain --untracked-files=all | wc -l | sed 's/^/dirty_or_untracked_entries /'; } > "$OUT/worktree.txt"
DIRS=(testnet-v0-launch-tjs229-2026-09-20 testnet-v0-sync-tjs242-2026-09-20 testnet-v0-payment-tjs230-2026-09-20
      testnet-v0-recover-tjs287-2026-09-21 testnet-v0-pool-restart-tjs297-2026-09-21 qa-tjs278-2026-09-21 qa-tjs294-2026-09-21)
: > "$OUT/manifests.tsv"; : > "$OUT/untracked-pins.txt"; fail=0
for d in "${DIRS[@]}"; do
  [ -d "$WT/research/evidence/$d" ] || { echo "MISSING research/evidence/$d" >> "$OUT/manifests.tsv"; fail=1; continue; }
  while IFS= read -r m; do
    rel=${m#"$WT/"}; kind=$(basename "$m")
    case $kind in
      INPUTS.sha256) log=$(cd "$WT" && sha256sum -c "$rel" 2>&1) ;;              # repository-relative pins
      *)             log=$(cd "$(dirname "$m")" && sha256sum -c "$kind" 2>&1) ;;  # directory-relative receipts; BINARY pins are absolute
    esac
    ok=$(grep -c ': OK$' <<< "$log"); bad=$(grep -c ': FAILED' <<< "$log"); miss=$(grep -c 'No such file' <<< "$log")
    printf '%s\t%s\tok=%s\tfailed=%s\tmissing=%s\n' "$rel" "$kind" "$ok" "$bad" "$miss" >> "$OUT/manifests.tsv"
    printf '%s\n' "$log" > "$OUT/$(echo "$rel" | tr '/' '_').log"
    [ "$bad" = 0 ] && [ "$miss" = 0 ] || fail=1
    if [ "$kind" = INPUTS.sha256 ]; then
      while IFS= read -r p; do git -C "$WT" ls-files --error-unmatch "$p" >/dev/null 2>&1 || { echo "$rel	$p" >> "$OUT/untracked-pins.txt"; fail=1; }
      done < <(sed 's/^[0-9a-f]\{64\}  //' "$m")
    fi
  done < <(find "$WT/research/evidence/$d" \( -name INPUTS.sha256 -o -name MANIFEST.sha256 -o -name EVIDENCE.sha256 -o -name BINARY.sha256 \) | sort)
done
git worktree remove --force "$WT" >> "$OUT/worktree-add.log" 2>&1
echo "result $([ $fail = 0 ] && echo PASS || echo FAIL) commit $COMMIT" | tee -a "$OUT/worktree.txt"
exit $fail
