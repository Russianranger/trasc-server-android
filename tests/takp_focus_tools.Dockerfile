# Build observation/focus companions only; preserve the published runtime.
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libc6-dev libx11-dev libxi-dev \
 && apt-get clean && rm -rf /var/lib/apt/lists/*
COPY native/presentation/takp-xinput-focus.c native/presentation/observe-log.h /source/
RUN mkdir /out \
 && gcc -std=c11 -O2 -Wall -Wextra -Werror /source/takp-xinput-focus.c -o /out/takp-xinput-focus -lX11
