FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl build-essential ninja-build pkg-config python3 python3-pip \
    python3-mako python3-yaml python3-packaging bison flex glslang-tools \
    libexpat1-dev zlib1g-dev libzstd-dev libx11-dev libx11-xcb-dev libxcb1-dev \
    libxcb-dri3-dev libxcb-present-dev libxcb-randr0-dev libxcb-shm0-dev \
    libxcb-sync-dev libxcb-xfixes0-dev libxshmfence-dev libvulkan-dev \
 && pip3 install --break-system-packages meson==1.5.2
WORKDIR /build
RUN curl -fL --retry 3 https://archive.mesa3d.org/mesa-24.3.4.tar.xz -o mesa.tar.xz \
 && echo 'e641ae27191d387599219694560d221b7feaa91c900bcec46bf444218ed66025  mesa.tar.xz' | sha256sum -c - \
 && tar -xf mesa.tar.xz \
 && meson setup mesa-build mesa-24.3.4 --buildtype=release \
    -Dplatforms=x11 -Dvulkan-drivers=freedreno -Dfreedreno-kmds=kgsl \
    -Dgallium-drivers= -Dglx=disabled -Degl=disabled -Dgbm=disabled \
    -Dopengl=false -Dgles1=disabled -Dgles2=disabled -Dllvm=disabled \
    -Dvideo-codecs= -Dbuild-tests=false \
 && ninja -C mesa-build -j2
COPY vulkan_probe.c /build/vulkan_probe.c
RUN cc -O2 -Wall -Wextra -Werror vulkan_probe.c -o vulkan-probe -lvulkan -lX11 \
 && mkdir /out \
 && cp mesa-build/src/freedreno/vulkan/libvulkan_freedreno.so /out/turnip.so \
 && cp vulkan-probe /out/ \
 && strip /out/turnip.so /out/vulkan-probe \
 && ldd /out/turnip.so && ldd /out/vulkan-probe
