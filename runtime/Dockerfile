FROM debian:bookworm-slim
ENV DEBIAN_FRONTEND=noninteractive
RUN printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d && chmod +x /usr/sbin/policy-rc.d \
 && apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates python3 mariadb-server mariadb-client git curl cmake ninja-build \
    build-essential pkg-config libboost-dev libboost-system-dev libboost-filesystem-dev \
    libboost-program-options-dev liblua5.1-0-dev libmariadb-dev libmariadb-dev-compat \
    libssl-dev libsodium-dev libperl-dev zlib1g-dev libcurl4-openssl-dev libmbedtls-dev \
    tar gzip unzip zip xz-utils procps \
 && apt-get clean && rm -rf /var/lib/apt/lists/* /var/lib/mysql/* /var/log/* \
 && mkdir -p /work /opt/trasc /tmp /var/lib/mysql \
 && printf '{"format":1,"architecture":"arm64","distribution":"debian-bookworm","runtime":"1"}\n' > /etc/trasc-runtime.json \
 && dpkg-query -W > /etc/trasc-packages.txt
WORKDIR /work
CMD ["/bin/bash"]
