#!/bin/bash
set -euo pipefail
umask 077
install -d -m 700 /var/lib/tjs1882/qualification
cd /var/lib/tjs1882/qualification
. /etc/os-release
test "$ID:$VERSION_ID" = ubuntu:22.04
test "$(uname -m)" = aarch64
test "$(getconf GNU_LIBC_VERSION)" = 'glibc 2.35'
dpkg-query -W -f='${binary:Package}=${Version}\n' > packages-before.txt
apt-get -o Acquire::Retries=1 -o Acquire::http::Timeout=30 update
apt-get -o Acquire::Retries=1 -o Acquire::http::Timeout=30 -o APT::Keep-Downloaded-Packages=true --download-only install -y --no-install-recommends docker.io build-essential libssl-dev zlib1g-dev libbz2-dev liblzma-dev libffi-dev libsqlite3-dev libreadline-dev uuid-dev git ca-certificates curl xz-utils
sha256sum /var/cache/apt/archives/*.deb > downloaded-debs.sha256
DEBIAN_FRONTEND=noninteractive apt-get --no-download install -y --no-install-recommends docker.io build-essential libssl-dev zlib1g-dev libbz2-dev liblzma-dev libffi-dev libsqlite3-dev libreadline-dev uuid-dev git ca-certificates curl xz-utils
dpkg-query -W -f='${binary:Package}=${Version}\n' > packages-after.txt
sha256sum /var/lib/apt/lists/*InRelease > repository-inrelease.sha256
curl --fail --location --proto '=https' --proto-redir '=https' --tlsv1.2 --max-time 180 --output Python-3.13.16.tar.xz https://www.python.org/ftp/python/3.13.16/Python-3.13.16.tar.xz
echo 'f4b1bfb3c79b5bb11b8d228a12504163b4c0dab4d679828d8f5f26b6cb6ab35d  Python-3.13.16.tar.xz' | sha256sum -c -
tar -xJf Python-3.13.16.tar.xz
cd Python-3.13.16
./configure --prefix=/opt/tjs1882-python --without-ensurepip --disable-test-modules
make -j2
make -j2 altinstall
/opt/tjs1882-python/bin/python3.13 -I -c 'import platform,hashlib,tarfile,lzma,bz2,ssl,sqlite3,urllib.request; print(platform.python_version(),platform.machine(),ssl.OPENSSL_VERSION)'
sha256sum /opt/tjs1882-python/bin/python3.13 > ../python-executable.sha256
systemctl is-active docker
printf '%s\n' PASS_GUEST_PREPARATION
