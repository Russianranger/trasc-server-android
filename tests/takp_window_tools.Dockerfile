# Compile the new read-only inspector only; all existing companions are reused.
FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev libx11-dev \
 && apt-get clean && rm -rf /var/lib/apt/lists/*
COPY native/presentation/takp-window-inspect.c native/presentation/observe-log.h /source/native/presentation/
COPY tests/takp_window_inspect_property.c /source/tests/takp_window_inspect_property.c
RUN mkdir /out && gcc -std=c11 -O2 -Wall -Wextra -Werror \
    /source/native/presentation/takp-window-inspect.c -o /out/takp-window-inspect -lX11 \
 && gcc -std=c11 -O2 -Wall -Wextra -Werror \
    /source/tests/takp_window_inspect_property.c -o /out/property-test -lX11 \
 && /out/property-test
