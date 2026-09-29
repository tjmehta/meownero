#!/usr/bin/env bash
set -euo pipefail
runbase=<agent-scratch>
src="$runbase/scratch/exact/build/vanguard-src"
out="$runbase/scratch/rebuild"
mkdir -p "$out" "$src/monero-fcmp/build/vanguard"
flock -n /tmp/meownero-swarm-20260912-heavy.lock docker run --rm --name tjs1003-qa-clean-build --pull=never --network=none --cap-drop=ALL --security-opt=no-new-privileges --cpus=2 --memory=4g --memory-swap=4g --pids-limit=256 --ulimit core=0 -u "$(id -u):$(id -g)" -v "$src/monero-fcmp:/src" -v "$src/cargo-home:/cargo-home" -v ~/.rustup/toolchains/stable-x86_64-unknown-linux-gnu:/opt/rust:ro -v "$out:/out" -e CARGO_HOME=/cargo-home -e CARGO_NET_OFFLINE=true -e PATH=/opt/rust/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin -w /out sha256:10a15debf7142412a29cb4cd77fd1bdfa6081b24b94a867b3c19e62ec7061c3e bash -euc 'trap '\''cat /sys/fs/cgroup/memory.peak > /out/build.memory; cat /sys/fs/cgroup/memory.events > /out/build.memory-events; cat /sys/fs/cgroup/cpu.stat > /out/build.cpu'\'' EXIT
cd /src/build/vanguard
timeout 1700 cmake -D CMAKE_BUILD_TYPE=Release -D ARCH=default -D BUILD_TESTS=ON -D USE_DEVICE_TREZOR=OFF -D MANUAL_SUBMODULES=ON ../.. > /out/cmake.log 2>&1
timeout 1700 make -j1 daemon wallet_rpc_server > /out/make.log 2>&1'
sha256sum "$src/monero-fcmp/build/vanguard/bin/monerod" "$src/monero-fcmp/build/vanguard/bin/monero-wallet-rpc" > "$out/binary.sha256"
