set -eu
trap 'cat /sys/fs/cgroup/memory.peak > /out/memory.peak; cat /sys/fs/cgroup/memory.events > /out/memory.events; cat /sys/fs/cgroup/cpu.stat > /out/cpu.stat' EXIT
rustc -V > /out/container-rustc.txt
cargo -V > /out/container-cargo.txt
cmake --version > /out/container-cmake.txt
g++ --version > /out/container-gxx.txt
cmake -S /src -B /src/build/network -D CMAKE_BUILD_TYPE=Release -D ARCH=default -D BUILD_TESTS=ON -D USE_DEVICE_TREZOR=OFF -D MANUAL_SUBMODULES=ON > /out/cmake.log 2>&1
cmake --build /src/build/network --target vanguard_network_admission --parallel 1 > /out/make.log 2>&1
sha256sum /src/build/network/tests/vanguard-network/vanguard_network_admission > /out/binary.sha256
status=0
timeout 45 /src/build/network/tests/vanguard-network/vanguard_network_admission /out/db-positive positive > /out/positive.stdout.log 2> /out/positive.stderr.log || status=$?
echo "$status" > /out/positive.exit
status=0
timeout 45 /src/build/network/tests/vanguard-network/vanguard_network_admission /out/db-positive-reward positive-reward > /out/positive-reward.stdout.log 2> /out/positive-reward.stderr.log || status=$?
echo "$status" > /out/positive-reward.exit
status=0
timeout 45 /src/build/network/tests/vanguard-network/vanguard_network_admission /out/db-wrong-height wrong-height > /out/wrong-height.stdout.log 2> /out/wrong-height.stderr.log || status=$?
echo "$status" > /out/wrong-height.exit
status=0
timeout 45 /src/build/network/tests/vanguard-network/vanguard_network_admission /out/db-wrong-unlock wrong-unlock > /out/wrong-unlock.stdout.log 2> /out/wrong-unlock.stderr.log || status=$?
echo "$status" > /out/wrong-unlock.exit
status=0
timeout 45 /src/build/network/tests/vanguard-network/vanguard_network_admission /out/db-empty-outputs empty-outputs > /out/empty-outputs.stdout.log 2> /out/empty-outputs.stderr.log || status=$?
echo "$status" > /out/empty-outputs.exit
status=0
timeout 45 /src/build/network/tests/vanguard-network/vanguard_network_admission /out/db-wrong-version wrong-version > /out/wrong-version.stdout.log 2> /out/wrong-version.stderr.log || status=$?
echo "$status" > /out/wrong-version.exit
status=0
timeout 45 /src/build/network/tests/vanguard-network/vanguard_network_admission /out/db-identity identity > /out/identity.stdout.log 2> /out/identity.stderr.log || status=$?
echo "$status" > /out/identity.exit
status=0
timeout 45 /src/build/network/tests/vanguard-network/vanguard_network_admission /out/db-small-order small-order > /out/small-order.stdout.log 2> /out/small-order.stderr.log || status=$?
echo "$status" > /out/small-order.exit
status=0
timeout 45 /src/build/network/tests/vanguard-network/vanguard_network_admission /out/db-malformed malformed > /out/malformed.stdout.log 2> /out/malformed.stderr.log || status=$?
echo "$status" > /out/malformed.exit
status=0
timeout 45 /src/build/network/tests/vanguard-network/vanguard_network_admission /out/db-historical-torsion historical-torsion > /out/historical-torsion.stdout.log 2> /out/historical-torsion.stderr.log || status=$?
echo "$status" > /out/historical-torsion.exit
