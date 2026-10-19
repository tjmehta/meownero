set -eu
trap 'cat /sys/fs/cgroup/memory.peak > /out/memory.peak; cat /sys/fs/cgroup/memory.events > /out/memory.events; cat /sys/fs/cgroup/cpu.stat > /out/cpu.stat' EXIT
rustc -V > /out/container-rustc.txt
cargo -V > /out/container-cargo.txt
cmake --version > /out/container-cmake.txt
g++ --version > /out/container-gxx.txt
cmake -S /src -B /src/build/network -D CMAKE_BUILD_TYPE=Release -D ARCH=default -D BUILD_TESTS=ON -D USE_DEVICE_TREZOR=OFF -D MANUAL_SUBMODULES=ON > /out/cmake.log 2>&1
cmake --build /src/build/network --target vanguard_network_genesis --parallel 1 > /out/make.log 2>&1
/src/build/network/tests/vanguard-network/vanguard_network_genesis > /out/recipe1.json 2> /out/recipe1.stderr.log
/src/build/network/tests/vanguard-network/vanguard_network_genesis > /out/recipe2.json 2> /out/recipe2.stderr.log
cmp /out/recipe1.json /out/recipe2.json
sha256sum /src/build/network/tests/vanguard-network/vanguard_network_genesis > /out/binary.sha256
