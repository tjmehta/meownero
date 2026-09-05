FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake pkg-config libssl-dev libzmq3-dev libunbound-dev libsodium-dev \
    libunwind8-dev liblzma-dev libreadline-dev libexpat1-dev libpgm-dev libhidapi-dev \
    libusb-1.0-0-dev libprotobuf-dev protobuf-compiler libudev-dev libboost-chrono-dev \
    libboost-date-time-dev libboost-filesystem-dev libboost-locale-dev libboost-program-options-dev \
    libboost-regex-dev libboost-serialization-dev libboost-system-dev libboost-thread-dev \
    ccache git ca-certificates python3 && rm -rf /var/lib/apt/lists/*
WORKDIR /src
