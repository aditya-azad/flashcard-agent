# syntax=docker/dockerfile:1

# flashcard-agent MCP server + Anki (desktop) + AnkiConnect.
#
# Anki runs headless under Xvfb inside the container; AnkiWeb credentials are
# read from the environment (e.g. a .env file passed via `docker compose
# env_file` or `docker run --env-file`). The MCP server is served over
# Streamable HTTP on port 8000 (see docker/entrypoint.sh).

FROM python:3.14-slim

ARG ANKI_VERSION=26.09.3
ARG TARGETARCH

ENV PYTHONUNBUFFERED=1 \
    ANKI_BASE=/data/anki \
    DISPLAY=:99 \
    LANG=C.UTF-8 \
    # QtWebEngine (used by newer Anki) cannot use its Chromium sandbox in a
    # default-seccomp Docker container.
    QTWEBENGINE_DISABLE_SANDBOX=1

# Runtime deps for the Anki desktop build (Qt6 under Xvfb) plus download tools.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        zstd \
        xvfb \
        fonts-dejavu-core \
        libgl1 \
        libegl1 \
        libopengl0 \
        libxkbcommon0 \
        libxkbcommon-x11-0 \
        libxcb1 \
        libxcb-cursor0 \
        libxcb-icccm4 \
        libxcb-image0 \
        libxcb-keysyms1 \
        libxcb-render0 \
        libxcb-render-util0 \
        libxcb-shape0 \
        libxcb-xinerama0 \
        libxcb-xkb1 \
        libfontconfig1 \
        libdbus-1-3 \
        libglib2.0-0 \
        libnss3 \
        libnspr4 \
        libx11-6 \
        libx11-xcb1 \
        libxcomposite1 \
        libxcursor1 \
        libxdamage1 \
        libxext6 \
        libxfixes3 \
        libxi6 \
        libxrandr2 \
        libxrender1 \
        libxtst6 \
        libasound2t64 \
    && rm -rf /var/lib/apt/lists/*

# Official Anki desktop release (self-contained: bundles its own Python and
# Qt, and the `anki` library that docker/ankiweb_login.py runs against).
RUN case "$TARGETARCH" in \
        arm64) ARCH=aarch64 ;; \
        *) ARCH=x86_64 ;; \
    esac \
    && curl -fsSL \
        "https://github.com/ankitects/anki/releases/download/${ANKI_VERSION}/anki-${ANKI_VERSION}-linux-${ARCH}.tar.zst" \
        | tar --zstd -x -C /opt \
    && mv /opt/anki-*linux-*.tar /opt/anki \
    && ln -s /opt/anki/anki /usr/local/bin/anki

# AnkiConnect add-on, staged so the entrypoint can install it into the
# (possibly volume-mounted) Anki base dir on every start.
RUN mkdir -p /opt/AnkiConnect \
    && curl -fsSL "https://github.com/FooSoft/anki-connect/archive/refs/heads/master.tar.gz" \
        | tar xz -C /tmp \
    && cp -r /tmp/anki-connect-*/plugin/. /opt/AnkiConnect/ \
    && rm -rf /tmp/anki-connect-*

COPY docker/entrypoint.sh /usr/local/bin/entrypoint

# Non-root user owning the Anki data dir (QtWebEngine also refuses to run as
# root).
RUN useradd --create-home --uid 1000 anki \
    && mkdir -p /data/anki \
    && chown -R anki:anki /data/anki \
    && chmod +x /usr/local/bin/entrypoint

WORKDIR /app
COPY --chown=anki:anki . .
RUN pip install --no-cache-dir .

USER anki
EXPOSE 8000
ENTRYPOINT ["entrypoint"]
