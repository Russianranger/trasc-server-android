FROM debian:bookworm-slim AS builder
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl git cmake build-essential python3 xz-utils
ARG BOX64_COMMIT=2f130fab1d6e1a4ee8a71dc60cfdfcc839ad192a
RUN git clone https://github.com/ptitSeb/box64.git /src/box64 \
 && cd /src/box64 && git checkout "$BOX64_COMMIT" \
 && cmake -S . -B build -DARM_DYNAREC=ON -DBAD_SIGNAL=ON -DCMAKE_BUILD_TYPE=RelWithDebInfo \
 && cmake --build build --parallel 2
RUN curl -fL --retry 3 -o /tmp/wine.tar.xz https://github.com/Kron4ek/Wine-Builds/releases/download/10.0/wine-10.0-amd64-wow64.tar.xz \
 && echo 'aeebbbf239e548f0136f1cd72a2e109dd9a572a8f703da3c09fa40d74d5c255f  /tmp/wine.tar.xz' | sha256sum -c - \
 && mkdir /wine && tar -xJf /tmp/wine.tar.xz --strip-components=1 -C /wine

FROM debian:bookworm-slim
ENV DEBIAN_FRONTEND=noninteractive
RUN dpkg --add-architecture amd64 && apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates python3 tigervnc-standalone-server xauth xfonts-base mesa-utils \
    libgl1-mesa-dri libglx-mesa0 libgl1 libvulkan1 libsdl2-2.0-0 \
    libx11-6 libxext6 libxrender1 libxrandr2 libxi6 libxfixes3 libxcursor1 libxinerama1 libxxf86vm1 \
    libfontconfig1 libfreetype6 fonts-liberation libasound2 libpulse0 libdbus-1-3 libudev1 \
    libgnutls30 libgcrypt20 libgphoto2-6 libpcap0.8 libjpeg62-turbo libpng16-16 \
    libsane1 libcups2 libusb-1.0-0 libkrb5-3 libunwind8 libopenal1 libosmesa6 procps \
    libgcc-s1:amd64 libstdc++6:amd64 libunwind8:amd64 \
 && apt-get clean && rm -rf /var/lib/apt/lists/* /var/log/* \
 && mkdir -p /client /prefix /session /logs /opt/trasc-client /tmp
COPY --from=builder /src/box64/build/box64 /usr/local/bin/box64
COPY --from=builder /src/box64/system/box64.box64rc /etc/box64.box64rc
COPY --from=builder /src/box64/LICENSE /usr/share/doc/box64/LICENSE
COPY --from=builder /wine /opt/wine
RUN printf '{"format":1,"architecture":"arm64","runtime":"client-1.0","wine":"10.0-wow64","box64":"0.4.4","renderer":"wined3d-llvmpipe"}\n' > /etc/trasc-client-runtime.json \
 && dpkg-query -W > /etc/trasc-client-packages.txt
CMD ["/bin/bash"]
