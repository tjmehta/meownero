#!/usr/bin/env bash
# TJS-294 QA acceptance evidence collection: the read-only checks against the TJS-287 candidate and the
# retained QA execution. Run from the repository root: bash research/evidence/qa-tjs294-2026-09-21/collect.sh
# The fresh journey itself is NOT re-run here; it was executed once with
#   python3 -B chain/testnet-v0/recover.py --work build/testnet-v0-recover-qa294-01
# and its public receipts are retained under qa294-01/ (see journey-qa294-01.run.txt). The refusal suite
# was run once with test-recover-refusals.py --work build/testnet-v0-recover-qa294-refusals-01.
set -u
E=research/evidence/qa-tjs294-2026-09-21
C=research/evidence/testnet-v0-recover-tjs287-2026-09-21
W=build/testnet-v0-recover-tjs287-run02
Q=$E/qa294-01
BIN=build/repro-selected-20260918/selected-9-90/first/source/build/release/bin
{
  echo "utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"; echo "head=$(git rev-parse HEAD)"; echo "branch=$(git rev-parse --abbrev-ref HEAD)"
  echo "recipe_commit=$(git rev-parse 3bc39cb)"; echo "evidence_commit=$(git rev-parse 93fe9d4)"
  echo "report_sha256=$(sha256sum research/testnet-v0-recover-tjs287-2026-09-21.md | cut -d' ' -f1)"
  echo "manifest_sha256=$(sha256sum $C/MANIFEST.sha256 | cut -d' ' -f1) entries=$(wc -l < $C/MANIFEST.sha256)"
  echo "monerod=$(sha256sum $BIN/monerod | cut -d' ' -f1)"; echo "wallet_rpc=$(sha256sum $BIN/monero-wallet-rpc | cut -d' ' -f1)"
  echo "recover_py_pins:"; grep -E "^(RECIPE_MANIFEST_SHA|WALLET_SHA) =" chain/testnet-v0/recover.py; grep -E "^(IMAGE|BINARY_SHA) =" chain/testnet-v0/launch.py
  echo "docker_image=$(docker image inspect sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e --format '{{.Id}}' 2>&1)"
  echo "recipe_files_3bc39cb_vs_HEAD: $(git diff --stat 3bc39cb HEAD -- chain/testnet-v0 | tail -1)"; echo "(empty above = unchanged)"
  echo "worktree_status_of_candidate:"; git status --short chain/testnet-v0 research/testnet-v0-recover-tjs287-2026-09-21.md $C | sed 's/^/  /'; echo "(empty = clean)"
} > $E/binding.txt 2>&1
( cd $C && sha256sum -c MANIFEST.sha256 > /tmp/qa294-m.txt 2>&1; echo "exit=$?" >> /tmp/qa294-m.txt ); { grep -c ': OK$' /tmp/qa294-m.txt | sed 's/^/ok=/'; grep -v ': OK$' /tmp/qa294-m.txt; } > $E/manifest-check.txt; rm -f /tmp/qa294-m.txt
( cd $C/recover && sha256sum -c EVIDENCE.sha256; echo "exit=$?" ) > $E/evidence-check-evidence-dir.txt 2>&1
( cd $W && sha256sum -c EVIDENCE.sha256; echo "exit=$?" ) > $E/evidence-check-workdir.txt 2>&1
( sha256sum -c $C/recover/INPUTS.sha256; echo "exit=$?" ) > $E/inputs-check.txt 2>&1
( cd $C/refusals && sha256sum -c MANIFEST.sha256; echo "exit=$?" ) > $E/refusals-manifest-check.txt 2>&1
( cd $C/run01-history-order-refused && sha256sum -c EVIDENCE.sha256; echo "exit=$?" ) > $E/run01-evidence-check.txt 2>&1
{ for f in $C/recover/*; do b=$(basename "$f"); if cmp -s "$f" "$W/$b"; then echo "EQUAL $b"; else echo "DIFF  $b"; fi; done
  echo "workdir-only public files:"; for f in $W/*; do b=$(basename "$f"); [ -f "$C/recover/$b" ] || echo "  $b"; done; } > $E/evidence-vs-workdir.txt
{ while read -r h f; do if git cat-file -e "HEAD:$f" 2>/dev/null; then g=$(git show "HEAD:$f" | sha256sum | cut -d' ' -f1); [ "$g" = "$h" ] && echo "TRACKED-EQUAL   $f" || echo "TRACKED-DIFFERS $f"; else echo "UNTRACKED-AT-HEAD $f"; fi; done < $C/recover/INPUTS.sha256
  echo "--- recipe files at 3bc39cb vs INPUTS pins:"; for n in recover.py verify-recover.py test-recover-refusals.py recover-journey.md; do g=$(git show 3bc39cb:chain/testnet-v0/$n | sha256sum | cut -d' ' -f1); p=$(grep " chain/testnet-v0/$n\$" $C/recover/INPUTS.sha256 | cut -d' ' -f1); [ "$g" = "$p" ] && echo "3bc39cb-EQUAL $n" || echo "3bc39cb-DIFFERS $n $g $p"; done
  echo "--- run01 INPUTS vs run02 INPUTS:"; diff $C/run01-history-order-refused/INPUTS.sha256 $C/recover/INPUTS.sha256; echo "diff_exit=$?"; } > $E/inputs-git-lineage.txt 2>&1
python3 $E/rederive.py $C/recover $E/rederive-run02-result.json > $E/rederive-run02.txt 2>&1; echo "exit=$?" >> $E/rederive-run02.txt
python3 $E/rederive.py $Q $E/rederive-qa294-01-result.json > $E/rederive-qa294-01.txt 2>&1; echo "exit=$?" >> $E/rederive-qa294-01.txt
( python3 -B chain/testnet-v0/verify-recover.py $C/recover; echo "exit=$?" ) > $E/verify-run02-evidence-dir.txt 2>&1
( python3 -B chain/testnet-v0/verify-recover.py $W; echo "exit=$?" ) > $E/verify-run02-workdir.txt 2>&1
( python3 -B chain/testnet-v0/verify-recover.py $Q; echo "exit=$?" ) > $E/verify-qa294-01.txt 2>&1
( python3 -B chain/testnet-v0/verify-recover.py $C/run01-history-order-refused; echo "exit=$?" ) > $E/verify-run01-negative.txt 2>&1
( cd $Q && sha256sum -c EVIDENCE.sha256; echo "exit=$?" ) > $E/evidence-check-qa294-01.txt 2>&1
( sha256sum -c build/testnet-v0-recover-qa294-01/INPUTS.sha256; echo "exit=$?" ) > $E/inputs-check-qa294-01.txt 2>&1
S=${PAPERCLIP_RUN_SCRATCH_DIR:-${PAPERCLIP_SCRATCH_DIR:-/tmp}}/qa294-tamper; rm -rf "$S"; mkdir -p "$S"
python3 - $C/recover "$S" > $E/tamper-refusal.txt 2>&1 <<'PY'
import json, shutil, subprocess, sys, hashlib
from pathlib import Path
src, out = Path(sys.argv[1]), Path(sys.argv[2])
def copy(name):
    d = out / name; shutil.copytree(src, d); return d
def resign(d):
    files = sorted(p for p in d.iterdir() if p.is_file() and p.name != 'EVIDENCE.sha256')
    (d / 'EVIDENCE.sha256').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in files))
def run(d):
    p = subprocess.run([sys.executable, '-B', 'chain/testnet-v0/verify-recover.py', str(d)], capture_output=True, text=True)
    return p.returncode, (p.stderr.strip() or p.stdout.strip().splitlines()[0])[:160]
def edit(d, name, fn):
    j = json.loads((d / name).read_text()); fn(j); (d / name).write_text(json.dumps(j, indent=2, sort_keys=True) + '\n')
d = copy('faithful'); resign(d); print('faithful copy, re-signed        ->', run(d))
d = copy('unsigned-edit'); edit(d, 'wallet-restart.json', lambda j: j['wallet_after'].__setitem__('balance', {'balance': 45000000000001, 'unlocked_balance': 0})); print('edit without re-sign            ->', run(d))
def t1(j): j['wallet_after_cold_restore']['balance']['balance'] += 1
d = copy('wallet-after-restore-plus-1'); edit(d, 'wallet-restart.json', t1); resign(d); print('wallet_after_cold_restore +1    ->', run(d))
def t2(j): j['restored_manifest_equal'] = False
d = copy('restored-manifest-false'); edit(d, 'cold-restore.json', t2); resign(d); print('restored_manifest_equal=false   ->', run(d))
def t3(j): j['stored_tip_at_open'] = 4
d = copy('restore-open-tip-4'); edit(d, 'cold-restore.json', t3); resign(d); print('restore stored_tip_at_open=4     ->', run(d))
def t4(j): j[1][7]['hash'] = '00' * 32
d = copy('peer1-tip-hash'); edit(d, 'headers.json', t4); resign(d); print('peer1 header[7].hash altered     ->', run(d))
def t5(j): j['peer1']['submit_block'] = 1
d = copy('peer1-submit-block'); edit(d, 'rpc-methods.json', t5); resign(d); print('peer1 submit_block count added   ->', run(d))
def t6(j): j['peer1-restore'][0] = '/binary/monerod2'
d = copy('restore-command-differs'); edit(d, 'process-commands.json', t6); resign(d); print('peer1-restore command differs    ->', run(d))
def t7(j): j['wallet_before']['incoming'][0][0] = 'ab' * 32
d = copy('history-txid-not-coinbase'); edit(d, 'wallet-restart.json', t7); resign(d); print('W history txid != miner_tx_hash  ->', run(d))
def t8(j): j['tip_mined_while_destroyed']['height'] = 6; j['blocks_missed'] = 1
d = copy('offline-one-block'); edit(d, 'cold-restore.json', t8); resign(d); print('only 1 block while destroyed     ->', run(d))
PY
rm -rf "$S"
python3 - > $E/fresh-vs-run02.txt <<'PY'
import json
from pathlib import Path
A, B = Path('research/evidence/testnet-v0-recover-tjs287-2026-09-21/recover'), Path('research/evidence/qa-tjs294-2026-09-21/qa294-01')
rd = lambda d, n: json.loads((d / n).read_text())
ra, rb = rd(A, 'result.json'), rd(B, 'result.json')
print('result keys equal:', sorted(ra) == sorted(rb)); print('phases/scope/delivery equal:', all(ra[k] == rb[k] for k in ('phases', 'scope', 'delivery')))
print('run02 tip:', ra['peers'][0]); print('qa294 tip:', rb['peers'][0])
print('run02 rejoin_s %.3f  qa294 rejoin_s %.3f' % (ra['restore_rejoin_s'], rb['restore_rejoin_s']))
print('archive sha differs (fresh chain):', ra['backup_archive_sha256'] != rb['backup_archive_sha256'])
ha, hb = rd(A, 'headers.json')[0], rd(B, 'headers.json')[0]
print('genesis equal:', ha[0] == hb[0]); print('mined hashes all differ:', not ({h['hash'] for h in ha[1:]} & {h['hash'] for h in hb[1:]}))
print('run02 difficulties', [h['difficulty'] for h in ha]); print('qa294 difficulties', [h['difficulty'] for h in hb])
print('process-commands equal:', rd(A, 'process-commands.json') == rd(B, 'process-commands.json'))
ca, cb = rd(A, 'container-command.json'), rd(B, 'container-command.json')
print('container command equal except --name and -v work path:', [x for x in ca if x not in cb], [x for x in cb if x not in ca])
pa, pb = rd(A, 'profile-readback.json'), rd(B, 'profile-readback.json')
print('profile-readback genesis/fork/template equal:', all(pa[n][k] == pb[n][k] for n in ('0', '1') for k in ('genesis', 'fork')) and all(pa[n]['template']['expected_reward'] == pb[n]['template']['expected_reward'] for n in ('0', '1')))
resa, resb = rd(A, 'resources.json'), rd(B, 'resources.json')
print('run02 elapsed %.1f peak %d ; qa294 elapsed %.1f peak %d' % (resa['elapsed_seconds'], int(resa['memory.peak']), resb['elapsed_seconds'], int(resb['memory.peak'])))
print('qa294 exits', resb['daemon_exit_codes'])
cr = rd(B, 'cold-restore.json'); print('qa294 backup files', {k: v['bytes'] for k, v in cr['source_manifest'].items()}, 'archive bytes', cr['archive']['bytes'])
print('qa294 wallet heights', [rd(B, 'wallet-restart.json')[k] for k in ('wallet_height_before', 'wallet_height_after', 'wallet_height_after_cold_restore')])
PY
{ for run in "$C/recover" "$Q"; do echo "===== $run"
  for f in peer0.log peer1.log; do L=$run/$f; echo "$f lines=$(wc -l < $L) sha256=$(sha256sum $L | cut -d' ' -f1) REORGANIZE=$(grep -ci reorganize $L) alternative=$(grep -ci alternative $L) ERROR=$(grep -c ERROR $L) WARNING=$(grep -c WARNING $L) found_block=$(grep -ci 'found block' $L) db_open=$(grep -c 'Blockchain initialized' $L) deinit_core=$(grep -c 'Deinitializing core\.\.\.' $L)"; done
  echo "peer0 Found block:"; grep -i 'found block' $run/peer0.log | sed 's/.*Found/Found/' | cut -c1-120
  echo "peer1 DB opens:"; grep -h 'Blockchain initialized' $run/peer1.log | sed 's/.*Blockchain/Blockchain/' | cut -c1-90
  echo "peer1 stdout DB opens: peer1=$(grep -c 'Blockchain initialized' $run/peer1.stdout.log) restart=$(grep -c 'Blockchain initialized' $run/peer1-restart.stdout.log) restore=$(grep -c 'Blockchain initialized' $run/peer1-restore.stdout.log)"
  H6=$(python3 -c "import json; print(json.load(open('$run/headers.json'))[0][6]['hash'])"); H7=$(python3 -c "import json; print(json.load(open('$run/headers.json'))[0][7]['hash'])")
  echo "peer1.log lines mentioning offline blocks 6/7 after third DB open:"; awk -v s="$(grep -n 'Blockchain initialized' $run/peer1.log | tail -1 | cut -d: -f1)" -v a="$H6" -v b="$H7" 'NR>s && (index($0,a)||index($0,b))' $run/peer1.log | sed 's/^[^\t]*\t[^\t]*\t//' | cut -c1-150 | head -6
  echo "peer1.log ERROR lines (unique, trimmed):"; grep ERROR $run/peer1.log | sed 's/^[^\t]*\t[^\t]*\t//' | sed 's/127.0.0.1:[0-9]*/127.0.0.1:PORT/' | cut -c1-150 | sort -u
  echo "peer0.log WARNING lines (unique, trimmed):"; grep WARNING $run/peer0.log | sed 's/^[^\t]*\t[^\t]*\t//' | cut -c1-140 | sort -u | head -5; done; } > $E/daemon-log-crosscheck.txt 2>&1
{ echo "addresses (base58, 95 chars, M-prefix) in public receipts, first 12 chars:"; for d in $C/recover $Q; do echo "$d: $(cat $d/* 2>/dev/null | grep -oE '\bM[1-9A-HJ-NP-Za-km-z]{94}\b' | sort -u | cut -c1-12 | tr '\n' ' ')"; done
  echo "fixture prefix M9Lds8CcBgCJ"; echo "seed/key markers excluding pruning_seed and RandomX seed hash:"; cat $C/recover/* $Q/* 2>/dev/null | grep -i 'mnemonic\|spend_key\|view_key\|electrum\|seed' | grep -v 'pruning seed\|pruning_seed\|RandomX new main seed hash' | cut -c1-120 | sort -u; echo "(end)"; } > $E/address-privacy-grep.txt 2>&1
( cd $E && rm -f MANIFEST.sha256 && find . -type f ! -name MANIFEST.sha256 | sed 's#^\./##' | sort | xargs sha256sum > MANIFEST.sha256 )
echo "collected: $(find $E -type f | wc -l) files; MANIFEST sha256=$(sha256sum $E/MANIFEST.sha256 | cut -d' ' -f1)"
