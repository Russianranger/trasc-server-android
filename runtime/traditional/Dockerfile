FROM debian:bookworm-slim
ENV DEBIAN_FRONTEND=noninteractive
# This is a separate Traditional build/runtime image. Custom runtime-v1 is unchanged.
RUN printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d && chmod +x /usr/sbin/policy-rc.d \
 && apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates python3 mariadb-server mariadb-client git curl cmake ninja-build \
    build-essential pkg-config binutils file openssl luajit \
    libboost-dev libboost-system-dev libboost-filesystem-dev libboost-program-options-dev \
    libcereal-dev rapidjson-dev libfmt-dev libglm-dev libluajit-5.1-dev \
    librecast-dev libuv1-dev libmariadb-dev libmariadb-dev-compat \
    libssl-dev libsodium-dev libperl-dev libjson-perl libdbi-perl libdbd-mysql-perl \
    zlib1g-dev uuid-dev libcurl4-openssl-dev libmbedtls-dev \
    tar gzip unzip zip xz-utils procps \
 && openssl list -providers -provider default -provider legacy \
 && test -f /usr/lib/aarch64-linux-gnu/ossl-modules/legacy.so \
 && apt-get clean && rm -rf /var/lib/apt/lists/* /var/lib/mysql/* /var/log/* \
 && mkdir -p /work /opt/trasc /tmp /var/lib/mysql \
 && printf '{"format":1,"architecture":"arm64","distribution":"debian-bookworm","runtime":"traditional-1.0","profile":"traditional","build_adapter":1}\n' > /etc/trasc-runtime.json \
 && dpkg-query -W > /etc/trasc-packages.txt
WORKDIR /work
CMD ["/bin/bash"]
