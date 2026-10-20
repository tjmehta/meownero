#!/bin/bash
set -eu
export CARGO_HOME=/out/cargo-home CARGO_NET_OFFLINE=true CARGO_BUILD_JOBS=1
export PATH=/opt/rust/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export PYTHONDONTWRITEBYTECODE=1 LC_ALL=C HOME=/out/tmp
if [ -f /out/BUILD_COMPLETE ]; then
  exec timeout --signal=TERM --kill-after=5 600 python3 -B /out/harness/profile-integration.py
fi
rustc -V > /out/rustc.txt
cargo -V > /out/cargo.txt
cmake --version > /out/cmake-version.txt
cmake -S /out/source -B /out/build -D CMAKE_BUILD_TYPE=Release -D ARCH=default -D BUILD_TESTS=OFF -D USE_DEVICE_TREZOR=OFF -D MANUAL_SUBMODULES=ON > /out/configure.log 2>&1
cmake --build /out/build --target daemon simplewallet wallet_rpc_server --parallel 1 > /out/build.log 2>&1
python3 -B /out/harness/freeze-profile.py --built /out/build
