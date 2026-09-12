#!/usr/bin/env bash
# Candidate M control: 3-node private Meownero-M devnet in Docker. Feasibility only, never security.
#
# Usage:  devnet.sh <monero-src-dir-with-build> <workdir> [blocks]
#   builds nothing; expects build/release/bin/{monerod,monero-wallet-cli} inside <monero-src-dir>
#   Uses the chain builder by default; MEOW_BUILDER_IMAGE accepts an immutable image ID.
# Result: three monerod containers on a private docker network mine on node1, sync to node2/node3,
#         and the script prints per-block reward and the cumulative supply check supply(h) == h * 0.9.
set -euo pipefail
SRC=$(realpath "$1"); WORK=$(realpath "$2"); BLOCKS=${3:-30}
IMG=${MEOW_BUILDER_IMAGE:-meownero-chain-builder}
IMG=$(docker image inspect "$IMG" --format '{{.Id}}')
NET=meow-m-$$
N1=$NET-n1; N2=$NET-n2; N3=$NET-n3
[[ "$BLOCKS" =~ ^[1-9][0-9]*$ ]] || { echo "blocks must be positive" >&2; exit 1; }
BIN=/src/build/release/bin
# Refuse reuse instead of deleting caller data. No ports or external networking.
mkdir -p "$WORK"
[ -z "$(ls -A "$WORK")" ] || { echo "workdir must be empty" >&2; exit 1; }
mkdir -p "$WORK"/{wallet,n1,n2,n3}
cleanup() {
  docker rm -f "$N1" "$N2" "$N3" >/dev/null 2>&1 || true
  docker network rm "$NET" >/dev/null 2>&1 || true
}
trap cleanup EXIT
docker network create --internal "$NET" >/dev/null
printf '%s\n' "$IMG" > "$WORK/BUILDER_IMAGE_ID"

run() { docker run --rm -v "$SRC:/src:ro" -v "$WORK:/work" -w /work --network $NET "$@"; }

# 1. offline wallet -> Meownero mainnet address (must start with "M")
if [ ! -s "$WORK/wallet/address" ]; then
  # NB: an empty --password '' is ignored by monero-wallet-cli and it prompts instead (consuming stdin), so use an explicit one.
  run $IMG bash -c "echo exit | $BIN/monero-wallet-cli --offline --generate-new-wallet /work/wallet/meow --password meow --mnemonic-language English --restore-height 0 --log-file /work/wallet/wallet.log 2>&1 | grep -oE 'M[1-9A-HJ-NP-Za-km-z]{94}' | head -1 > /work/wallet/address"
fi
ADDR=$(cat "$WORK/wallet/address"); echo "miner address: $ADDR"
case "$ADDR" in M*) ;; *) echo "address prefix wrong: $ADDR"; exit 1;; esac

# 2. three daemons (node1 mines). No seeds exist; peers are explicit.
common=(--non-interactive --no-igd --hide-my-port --confirm-external-bind --log-level 1 --p2p-bind-ip 0.0.0.0 --rpc-bind-ip 0.0.0.0 --disable-dns-checkpoints --check-updates disabled --fixed-difficulty 1 --db-sync-mode fastest:async:250000)
docker run -d --name $N1 -v "$SRC:/src:ro" -v "$WORK:/work" --network "$NET" "$IMG" \
  "$BIN/monerod" "${common[@]}" --data-dir /work/n1 --start-mining "$ADDR" --mining-threads 1 >/dev/null
docker run -d --name $N2 -v "$SRC:/src:ro" -v "$WORK:/work" --network "$NET" "$IMG" \
  "$BIN/monerod" "${common[@]}" --data-dir /work/n2 --add-exclusive-node $N1:19080 >/dev/null
docker run -d --name $N3 -v "$SRC:/src:ro" -v "$WORK:/work" --network "$NET" "$IMG" \
  "$BIN/monerod" "${common[@]}" --data-dir /work/n3 --add-exclusive-node $N2:19080 >/dev/null

# the builder image has python3 but no curl
rpc() { docker exec "$1" python3 -c 'import sys,json,urllib.request; r=urllib.request.Request("http://127.0.0.1:19081/json_rpc",data=sys.argv[1].encode(),headers={"content-type":"application/json"}); print(urllib.request.urlopen(r, timeout=20).read().decode())' "$2"; }
height() { rpc "$1" '{"jsonrpc":"2.0","id":"0","method":"get_block_count"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["result"]["count"]-1)'; }

# 3. wait for BLOCKS on node1
for _ in $(seq 1 600); do h=$(height $N1 2>/dev/null || echo 0); [ "$h" -ge "$BLOCKS" ] && break; sleep 2; done
[ "$h" -ge "$BLOCKS" ] || { echo "mining timeout: $h < $BLOCKS" >&2; exit 1; }
docker exec "$N1" python3 -c 'import urllib.request; urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:19081/stop_mining", b"{}", {"content-type":"application/json"}), timeout=20).read()'
h=$(height "$N1")
echo "node1 stopped at height: $h"

# 4. supply check on node1: every block's coinbase pays exactly 0.9 MEOW; genesis pays 0
python3 - "$h" "$N1" <<'EOF' > "$WORK/supply-check.txt"
import sys, json, subprocess
h = int(sys.argv[1]); R = 900_000_000_000
PY = 'import sys,json,urllib.request; r=urllib.request.Request("http://127.0.0.1:19081/json_rpc",data=sys.argv[1].encode(),headers={"content-type":"application/json"}); print(urllib.request.urlopen(r, timeout=20).read().decode())'
def rpc(m, p): return json.loads(subprocess.check_output(["docker","exec",sys.argv[2],"python3","-c",PY,json.dumps({"jsonrpc":"2.0","id":"0","method":m,"params":p})]))["result"]
total = 0
heights = list(range(0, min(h, 200)+1)) + list(range(300, h+1, 100)) + ([h] if h > 200 else [])
for ht in sorted(set(heights)):
    b = rpc("get_block", {"height": ht})
    hdr = b["block_header"]; reward = hdr["reward"]
    total += reward
    expect = 0 if ht == 0 else R
    assert reward == expect, (ht, reward, expect)
    if ht in (0,1,2,h): print(f"height {ht}: reward {reward} major_version {hdr['major_version']} hash {hdr['hash'][:16]}")
cs = rpc("get_coinbase_tx_sum", {"height": 0, "count": h + 1})
emitted = cs["emission_amount"]; fees = cs["fee_amount"]
assert emitted == h * R, ("emission_amount", emitted, h*R)
print(f"sampled {len(heights)} blocks: every reward == 0.9 MEOW (genesis 0)")
print(f"node's get_coinbase_tx_sum over heights 0..{h}: emission {emitted} atomic = {emitted/1e12:.1f} MEOW = {h} * 0.9  OK; fees {fees}")
EOF
cat "$WORK/supply-check.txt"

# 5. All nodes must reach the same stopped tip, not merely print heights.
for n in "$N2" "$N3"; do
  for _ in $(seq 1 120); do
    [ "$(height "$n" 2>/dev/null || echo 0)" -eq "$h" ] && break
    sleep 1
  done
  [ "$(height "$n")" -eq "$h" ] || { echo "sync timeout: $n" >&2; exit 1; }
  tip=$(rpc "$n" '{"jsonrpc":"2.0","id":"0","method":"get_last_block_header"}')
  primary=$(rpc "$N1" '{"jsonrpc":"2.0","id":"0","method":"get_last_block_header"}')
  python3 -c 'import json,sys; assert json.loads(sys.argv[1])["result"]["block_header"]["hash"] == json.loads(sys.argv[2])["result"]["block_header"]["hash"]' "$tip" "$primary"
  echo "PASS: $n synced to height $h and identical tip"
done
