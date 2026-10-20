set -eu
trap 'cat /sys/fs/cgroup/memory.peak > /out/memory.peak; cat /sys/fs/cgroup/memory.events > /out/memory.events; cat /sys/fs/cgroup/cpu.stat > /out/cpu.stat' EXIT
rustc -V > /out/container-rustc.txt
cargo -V > /out/container-cargo.txt
cmake --version > /out/container-cmake.txt
g++ --version > /out/container-gxx.txt
cmake -S /src -B /src/build/network -D CMAKE_BUILD_TYPE=Release -D ARCH=default -D BUILD_TESTS=ON -D USE_DEVICE_TREZOR=OFF -D MANUAL_SUBMODULES=ON > /out/cmake.log 2>&1
cmake --build /src/build/network --target vanguard_network_policy --parallel 1 > /out/make.log 2>&1
sha256sum /src/build/network/tests/vanguard-policy/vanguard_network_policy > /out/binary.sha256
timeout 60 /src/build/network/tests/vanguard-policy/vanguard_network_policy /out/db-policy01 > /out/policy01.json 2> /out/policy01.stderr.log
timeout 60 /src/build/network/tests/vanguard-policy/vanguard_network_policy /out/db-policy02 > /out/policy02.json 2> /out/policy02.stderr.log
cmp /out/policy01.json /out/policy02.json
