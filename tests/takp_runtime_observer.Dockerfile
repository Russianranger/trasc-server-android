# Build only an observation tool. The published client rootfs is not altered.
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libc6-dev libx11-dev libxi-dev \
 && apt-get clean && rm -rf /var/lib/apt/lists/*
COPY native/presentation/takp-xinput-observe.c /source/takp-xinput-observe.c
COPY native/presentation/observe-log.h /source/observe-log.h
RUN mkdir /out && gcc -std=c11 -O2 -Wall -Wextra -Werror \
    /source/takp-xinput-observe.c -o /out/takp-xinput-observe -lX11 -ldl
