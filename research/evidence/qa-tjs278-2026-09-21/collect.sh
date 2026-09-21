#!/usr/bin/env bash
# TJS-278 QA acceptance evidence collection. Read-only against the candidate; no lock, no daemon, no container.
# Run from the repository root: bash research/evidence/qa-tjs278-2026-09-21/collect.sh
set -u
E=research/evidence/qa-tjs278-2026-09-21
W=build/testnet-v0-payment-tjs230-03
C=research/evidence/testnet-v0-payment-tjs230-2026-09-20
{
  echo "utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"; echo "head=$(git rev-parse HEAD)"; echo "branch=$(git rev-parse --abbrev-ref HEAD)"
  echo "manifest_sha256=$(sha256sum $C/MANIFEST.sha256 | cut -d' ' -f1) entries=$(wc -l < $C/MANIFEST.sha256)"
  echo "report_sha256=$(sha256sum research/testnet-v0-payment-tjs230-2026-09-20.md | cut -d' ' -f1)"
  echo "monerod=$(sha256sum $W/../repro-selected-20260918/selected-9-90/first/source/build/release/bin/monerod | cut -d' ' -f1)"
  echo "wallet_rpc=$(sha256sum $W/../repro-selected-20260918/selected-9-90/first/source/build/release/bin/monero-wallet-rpc | cut -d' ' -f1)"
  echo "launch_py_pins:"; grep -E "^(IMAGE|BINARY_SHA) =" chain/testnet-v0/launch.py
  echo "docker_image=$(docker image inspect sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e --format '{{.Id}}' 2>&1)"
} > $E/binding.txt
( cd $C && sha256sum -c MANIFEST.sha256; echo "exit=$?" ) > $E/manifest-check.txt 2>&1
( cd $W && sha256sum -c EVIDENCE.sha256; echo "exit=$?" ) > $E/evidence-check.txt 2>&1
( sha256sum -c $W/INPUTS.sha256; echo "exit=$?" ) > $E/inputs-check.txt 2>&1
{ for f in $C/attempt-03/*; do b=$(basename "$f"); if cmp -s "$f" "$W/$b"; then echo "EQUAL $b"; else echo "DIFF  $b"; fi; done; } > $E/attempt03-vs-workdir.txt
{ while read -r h f; do if git cat-file -e "HEAD:$f" 2>/dev/null; then g=$(git show "HEAD:$f" | sha256sum | cut -d' ' -f1); [ "$g" = "$h" ] && echo "TRACKED-EQUAL   $f" || echo "TRACKED-DIFFERS $f"; else echo "UNTRACKED-AT-HEAD $f"; fi; done < $W/INPUTS.sha256; } > $E/inputs-git-lineage.txt
python3 $E/rederive.py $W $E/rederive-result.json > $E/rederive.txt 2>&1; echo "exit=$?" >> $E/rederive.txt
T1=4e28f52f188ec63a63e9c61b36a1370436dd5765839544f7ddb3993511bd6122; T2=4fa2aa1ce64b6d1524acded265f2b564350d4999cba53dde01c11bb86295fc47
B101=67711ae518be31c6e34aa774d2f7b5f7ff58b48a7fcb6b61860df1409b60666b; B113=3f69e38921ff292eeb2658129aff79fce06aa1f07a7b7d131b810c88254573b1; TIP=2ccf565487abc19e433e1925a50a5a8a3bb756f6b0577da644488f8c731bb3d3
{
  for n in 0 1; do L=$W/peer$n.log; echo "===== peer$n.log lines=$(wc -l < $L) sha256=$(sha256sum $L | cut -d' ' -f1)"
    echo "mentions tx1=$(grep -c $T1 $L) tx2=$(grep -c $T2 $L) b101=$(grep -c $B101 $L) b113=$(grep -c $B113 $L) tip=$(grep -c $TIP $L)"
    grep -E "$T1|$T2|$B101|$B113|$TIP" $L | cut -c1-230
    echo "counts: REORGANIZE=$(grep -ci 'reorganize' $L) alternative=$(grep -ci 'alternative' $L) ERROR=$(grep -c 'ERROR' $L) WARNING=$(grep -c 'WARNING' $L) found_block=$(grep -ci 'found block' $L) block_added=$(grep -c 'BLOCK ADDED\|BLOCK SUCCESSFULLY ADDED' $L)"
    echo "ERROR lines:"; grep 'ERROR' $L | cut -c1-200; echo "first: $(head -1 $L | cut -c1-120)"; echo "last:  $(tail -1 $L | cut -c1-120)"; done
  echo "===== peer0.stdout.log found_block=$(grep -ci 'found block' $W/peer0.stdout.log) first=$(grep -m1 -i 'found block' $W/peer0.stdout.log | cut -c1-120)"
  echo "===== peer1.stdout.log found_block=$(grep -ci 'found block' $W/peer1.stdout.log)"
} > $E/daemon-log-crosscheck.txt 2>&1
python3 - > $E/lock-probe.txt 2>&1 <<'PY'
import fcntl, time, subprocess
p='/tmp/meownero-swarm-20260912-heavy.lock'
print('utc', time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
f=open(p,'a')
try:
    fcntl.flock(f, fcntl.LOCK_EX|fcntl.LOCK_NB); print('lock FREE (probe released immediately)'); fcntl.flock(f, fcntl.LOCK_UN)
except BlockingIOError: print('lock BUSY')
print('meow containers:', subprocess.run(['docker','ps','--format','{{.Names}}'],capture_output=True,text=True).stdout.split())
print('decision: fresh ~10,000 s run NOT started; TJS-242 (M3) worker live in herdr tab w1V:tF; accept on receipts')
PY
( cd $E && rm -f MANIFEST.sha256 && sha256sum $(ls | grep -v MANIFEST.sha256 | sort) > MANIFEST.sha256 )
echo "collected: $(ls $E | wc -l) files; MANIFEST sha256=$(sha256sum $E/MANIFEST.sha256 | cut -d' ' -f1)"
