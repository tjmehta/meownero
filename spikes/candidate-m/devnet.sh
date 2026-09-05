#!/usr/bin/env bash
# Candidate M control: 3-node private Meownero-M devnet in Docker. Feasibility only, never security.
#
# Usage:  devnet.sh <monero-src-dir-with-build> <workdir> [blocks]
#   builds nothing; expects build/release/bin/{monerod,monero-wallet-cli} inside <monero-src-dir>
#   (produced by the meownero-monero-builder image, see README.md).
# Result: three monerod containers on a private docker network mine on node1, sync to node2/node3,
#         and the script prints per-block reward and the cumulative supply check supply(h) == h * 0.9.
set -euo pipefail
SRC=$(realpath "$1"); WORK=$(realpath "$2"); BLOCKS=${3:-30}
IMG=meownero-monero-builder
NET=meow-m-net
BIN=/src/build/release/bin
mkdir -p "$WORK"/{wallet,n1,n2,n3}
docker network inspect $NET >/dev/null 2>&1 || docker network create $NET >/dev/null

run() { docker run --rm -v "$SRC:/src:ro" -v "$WORK:/work" -w /work --network $NET "$@"; }

# 1. offline wallet -> Meownero mainnet address (must start with "M")
if [ ! -s "$WORK/wallet/address" ]; then
  run $IMG bash -c "echo exit | $BIN/monero-wallet-cli --offline --generate-new-wallet /work/wallet/meow --password '' --mnemonic-language English --log-file /work/wallet/wallet.log 2>&1 | grep -oE 'M[1-9A-HJ-NP-Za-km-z]{94}' | head -1 > /work/wallet/address"
fi
ADDR=$(cat "$WORK/wallet/address"); echo "miner address: $ADDR"
case "$ADDR" in M*) ;; *) echo "address prefix wrong: $ADDR"; exit 1;; esac

# 2. three daemons (node1 mines). No seeds exist; peers are explicit.
common="--non-interactive --no-igd --hide-my-port --confirm-external-bind --log-level 1 --p2p-bind-ip 0.0.0.0 --rpc-bind-ip 0.0.0.0 --disable-dns-checkpoints --check-updates disabled --fixed-difficulty 1 --db-sync-mode fastest:async:250000"
docker rm -f meow-n1 meow-n2 meow-n3 >/dev/null 2>&1 || true
docker run -d --name meow-n1 -v "$SRC:/src:ro" -v "$WORK:/work" --network $NET $IMG \
  $BIN/monerod $common --data-dir /work/n1 --start-mining "$ADDR" --mining-threads 1 >/dev/null
docker run -d --name meow-n2 -v "$SRC:/src:ro" -v "$WORK:/work" --network $NET $IMG \
  $BIN/monerod $common --data-dir /work/n2 --add-exclusive-node meow-n1:19080 >/dev/null
docker run -d --name meow-n3 -v "$SRC:/src:ro" -v "$WORK:/work" --network $NET $IMG \
  $BIN/monerod $common --data-dir /work/n3 --add-exclusive-node meow-n2:19080 >/dev/null

rpc() { docker exec "$1" curl -s -X POST http://127.0.0.1:19081/json_rpc -H 'content-type: application/json' --data "$2"; }
height() { rpc "$1" '{"jsonrpc":"2.0","id":"0","method":"get_block_count"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["result"]["count"]-1)'; }

# 3. wait for BLOCKS on node1
for i in $(seq 1 600); do h=$(height meow-n1 2>/dev/null || echo 0); [ "$h" -ge "$BLOCKS" ] && break; sleep 2; done
echo "node1 height: $h"

# 4. supply check on node1: every block's coinbase pays exactly 0.9 MEOW; genesis pays 0
python3 - "$h" <<'EOF' > "$WORK/supply-check.txt"
import sys, json, subprocess
h = int(sys.argv[1]); R = 900_000_000_000
def rpc(m, p): return json.loads(subprocess.check_output(["docker","exec","meow-n1","curl","-s","-X","POST","http://127.0.0.1:19081/json_rpc","-H","content-type: application/json","--data",json.dumps({"jsonrpc":"2.0","id":"0","method":m,"params":p})]))["result"]
total = 0
for ht in range(0, h+1):
    b = rpc("get_block", {"height": ht})
    hdr = b["block_header"]; reward = hdr["reward"]
    total += reward
    expect = 0 if ht == 0 else R
    assert reward == expect, (ht, reward, expect)
    if ht in (0,1,2,h): print(f"height {ht}: reward {reward} major_version {hdr['major_version']} hash {hdr['hash'][:16]}")
assert total == h * R, (total, h*R)
print(f"supply after {h} blocks = {total} atomic = {total/1e12:.1f} MEOW = {h} * 0.9  OK")
print("already_generated_coins (node view):", rpc("get_block", {"height": h})["block_header"].get("already_generated_coins"))
EOF
cat "$WORK/supply-check.txt"

# 5. sync check on the two followers
sleep 15
for n in meow-n2 meow-n3; do echo "$n height: $(height $n)"; done
