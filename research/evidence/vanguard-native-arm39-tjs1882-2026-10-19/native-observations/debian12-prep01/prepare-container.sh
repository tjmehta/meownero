set -e
trap 'cat /sys/fs/cgroup/memory.peak > /out/preparation.memory; cat /sys/fs/cgroup/memory.events > /out/preparation.memory-events' EXIT
test "$(. /etc/os-release; echo "$ID:$VERSION_ID")" = debian:12
apt-get -o Acquire::Retries=1 -o Acquire::http::Timeout=30 update
apt-get -o Acquire::Retries=1 -o Acquire::http::Timeout=30 -o APT::Keep-Downloaded-Packages=true --download-only install -y --no-install-recommends python3 ca-certificates
sha256sum /var/cache/apt/archives/*.deb > /out/downloaded-debs.sha256
DEBIAN_FRONTEND=noninteractive apt-get --no-download install -y --no-install-recommends python3 ca-certificates
dpkg-query -W -f='${binary:Package}=${Version}\n' | sort > /out/packages.txt
sha256sum /var/lib/apt/lists/*InRelease > /out/apt-inrelease.sha256
cat /etc/os-release > /out/environment.txt
getconf GNU_LIBC_VERSION >> /out/environment.txt
python3 --version >> /out/environment.txt
command -v bash tar python3
