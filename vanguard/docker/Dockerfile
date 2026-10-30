ARG COMPILED_IMAGE=fetched
FROM ubuntu:24.04@sha256:786a8b558f7be160c6c8c4a54f9a57274f3b4fb1491cf65146521ae77ff1dc54 AS fetched
ARG INVOCATION=manual
LABEL meownero.build-invocation=$INVOCATION
ENV DEBIAN_FRONTEND=noninteractive
# Bootstrap only the exact verified CA archive from APT's signed base-release
# index. Extract its roots without installing any floating dependencies.
RUN apt-get update && cd /tmp && apt-get download ca-certificates=20240203 \
    && echo '641de77d8f142cfd62a1a6f964ba67b20754d3337c480efb529d086075a06c9a  ca-certificates_20240203_all.deb' | sha256sum -c - \
    && dpkg-deb -x ca-certificates_20240203_all.deb /tmp/trust \
    && mkdir -p /etc/ssl/certs \
    && cat /tmp/trust/usr/share/ca-certificates/mozilla/*.crt > /etc/ssl/certs/ca-certificates.crt \
    && rm -rf /tmp/trust /tmp/ca-certificates_20240203_all.deb /var/lib/apt/lists/*
RUN printf 'APT::Snapshot "20261009T000000Z";\n' > /etc/apt/apt.conf.d/50snapshot \
    && apt-get update && apt-get install -y --no-install-recommends \
       build-essential cmake pkg-config autoconf automake libtool bison curl git \
       ca-certificates python3 xz-utils patch gperf \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /recipe
COPY vanguard/source-lock.json vanguard/source-lock.json
COPY vanguard/portable_licenses.py vanguard/portable_provenance.py vanguard/package-portable.py vanguard/portable-tester.py vanguard/
COPY vanguard/licenses vanguard/licenses
COPY docs/vanguard-portable-tester.md docs/vanguard-portable-tester.md
COPY vanguard/docker vanguard/docker
RUN python3 -B vanguard/docker/fetch.py

# build.py compiles the fetched image in a separately owned, offline container
# with explicit CPU/memory/PID/time limits, then supplies its exact image ID.
FROM ${COMPILED_IMAGE} AS compiled

FROM ubuntu:24.04@sha256:786a8b558f7be160c6c8c4a54f9a57274f3b4fb1491cf65146521ae77ff1dc54 AS runtime
ARG INVOCATION=manual
LABEL meownero.build-invocation=$INVOCATION
ENV DEBIAN_FRONTEND=noninteractive PYTHONDONTWRITEBYTECODE=1 HOME=/state
COPY --from=fetched /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt
RUN printf 'APT::Snapshot "20261009T000000Z";\n' > /etc/apt/apt.conf.d/50snapshot \
    && apt-get update && apt-get install -y --no-install-recommends python3 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=compiled /package/meownero-vanguard-x86_64 /opt/tester
COPY --from=compiled /build/docker-build.json /opt/docker-build.json
COPY vanguard/docker/entrypoint.py /opt/entrypoint.py
RUN mkdir /state /output && chmod 1777 /state && chmod -R a+rX /opt
USER 65532:65532
WORKDIR /opt/tester
STOPSIGNAL SIGTERM
ENTRYPOINT ["python3", "-B", "/opt/entrypoint.py"]
