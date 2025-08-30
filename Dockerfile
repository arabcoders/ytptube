# syntax=docker/dockerfile:1.4
FROM node:lts-alpine AS node_builder

WORKDIR /app
COPY ui ./
RUN if [ ! -f "/app/exported/index.html" ]; then npm install --production --prefer-offline --frozen-lockfile && npm run generate; else echo "Skipping UI build, already built."; fi

FROM python:3.13-slim AS python_builder

ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONFAULTHANDLER=1
ENV PIP_NO_CACHE_DIR=off
ENV PIP_CACHE_DIR=/root/.cache/pip
ENV UV_CACHE_DIR=/root/.cache/uv

# Install build dependencies and uv
RUN apt-get update && apt-get install -y --no-install-recommends \
  build-essential libffi-dev libssl-dev curl ca-certificates pkg-config \
  && pip install --no-cache-dir uv

WORKDIR /opt/

COPY ./pyproject.toml ./uv.lock ./
RUN --mount=type=cache,target=/root/.cache/pip,id=pip-cache \
  --mount=type=cache,target=/root/.cache/uv,id=uv-cache \
  uv -vv venv --system-site-packages --relocatable ./python && \
  VIRTUAL_ENV=/opt/python uv -vv sync --link-mode=copy --active

FROM python:3.13-slim

ARG TZ=UTC
ARG USER_ID=1000
ENV IN_CONTAINER=1
ENV UMASK=0002
ENV YTP_CONFIG_PATH=/config
ENV YTP_TEMP_PATH=/tmp
ENV YTP_DOWNLOAD_PATH=/downloads
ENV YTP_PORT=8081
ENV XDG_CONFIG_HOME=/config
ENV XDG_CACHE_HOME=/tmp
ENV PYDEVD_DISABLE_FILE_VALIDATION=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONFAULTHANDLER=1

RUN mkdir /config /downloads && ln -snf /usr/share/zoneinfo/${TZ} /etc/localtime && echo ${TZ} > /etc/timezone && \
  apt-get update && apt-get install -y --no-install-recommends \
  bash mkvtoolnix patch aria2 curl ca-certificates xz-utils git sqlite3 tzdata file libmagic1 \
  && useradd -u ${USER_ID:-1000} -U -d /app -s /bin/bash app \
  && rm -rf /var/lib/apt/lists/*

COPY entrypoint.sh /

RUN sed -i 's/\r$//g' /entrypoint.sh && chmod +x /entrypoint.sh

COPY --chown=app:app ./app /app/app
COPY --chown=app:app --from=node_builder /app/exported /app/ui/exported
COPY --chown=app:app --from=python_builder /opt/python /opt/python
COPY --from=ghcr.io/arabcoders/alpine-mp4box /usr/bin/mp4box /usr/bin/mp4box
COPY --chown=app:app ./healthcheck.sh /usr/local/bin/healthcheck

ENV PATH="/opt/python/bin:$PATH"

RUN chown -R app:app /config /downloads && chmod +x /usr/local/bin/healthcheck /usr/bin/mp4box

# Install Jellyfin portable ffmpeg (per-arch)
ARG JELLYFIN_FFMPEG_VERSION=7.1.1-7
RUN set -eux \
  && arch="$(dpkg --print-architecture)" \
  && case "$arch" in \
  amd64) jf_arch="linux64" ;; \
  arm64) jf_arch="linuxarm64" ;; \
  *) echo "Unsupported architecture: $arch" >&2; exit 1 ;; \
  esac \
  && url="https://github.com/jellyfin/jellyfin-ffmpeg/releases/download/v${JELLYFIN_FFMPEG_VERSION}/jellyfin-ffmpeg_${JELLYFIN_FFMPEG_VERSION}_portable_${jf_arch}-gpl.tar.xz" \
  && echo "Downloading $url" \
  && curl -fsSL "$url" -o /tmp/jf-ffmpeg.tar.xz

RUN mkdir -p /tmp/jf-ffmpeg && tar -xJf /tmp/jf-ffmpeg.tar.xz -C /tmp/jf-ffmpeg \
  && ls -la /tmp/jf-ffmpeg \
  && install -m 0755 /tmp/jf-ffmpeg/ffmpeg /usr/bin/ffmpeg \
  && install -m 0755 /tmp/jf-ffmpeg/ffprobe /usr/bin/ffprobe \
  && /usr/bin/ffmpeg -version >/dev/null \
  && /usr/bin/ffprobe -version >/dev/null \
  && rm -rf /tmp/jf-ffmpeg.tar.xz /tmp/jf-ffmpeg

VOLUME /config
VOLUME /downloads

EXPOSE 8081

USER app

WORKDIR /tmp

HEALTHCHECK --interval=10s --timeout=20s --start-period=10s --retries=3 CMD [ "/usr/local/bin/healthcheck" ]

ENTRYPOINT ["/entrypoint.sh"]

CMD ["/opt/python/bin/python", "/app/app/main.py", "--ytp-process"]
