FROM node:lts-alpine AS node_builder

WORKDIR /app
COPY ui ./
RUN if [ ! -f "/app/exported/index.html" ]; then yarn install --production --prefer-offline --frozen-lockfile && yarn run generate; else echo "Skipping UI build, already built."; fi

FROM python:3.11-alpine AS python_builder

ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONFAULTHANDLER=1

# Use sed to strip carriage-return characters from the entrypoint script (in case building on Windows)
# Install dependencies
RUN apk add --update coreutils curl gcc g++ musl-dev libffi-dev openssl-dev curl make && pip install pipenv

WORKDIR /app

ARG PIPENV_FLAGS="--deploy"
COPY ./Pipfile* .
RUN PIPENV_VENV_IN_PROJECT=1 pipenv install ${PIPENV_FLAGS}

FROM python:3.11-alpine

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

RUN mkdir /config /downloads && ln -snf /usr/share/zoneinfo/${TZ} /etc/localtime && echo ${TZ} > /etc/timezone && \
  apk add --update --no-cache bash mkvtoolnix patch aria2 coreutils curl shadow sqlite tzdata libmagic ffmpeg rtmpdump && \
  useradd -u ${USER_ID:-1000} -U -d /app -s /bin/bash app && \
  rm -rf /var/cache/apk/*

COPY entrypoint.sh /

RUN sed -i 's/\r$//g' /entrypoint.sh && chmod +x /entrypoint.sh

COPY --chown=app:app ./app /app/app
COPY --chown=app:app --from=node_builder /app/exported /app/ui/exported
COPY --chown=app:app --from=python_builder /app/.venv /opt/python
COPY --chown=app:app --from=ghcr.io/arabcoders/alpine-mp4box /usr/bin/mp4box /usr/bin/mp4box
COPY --chown=app:app ./healthcheck.sh /usr/local/bin/healthcheck

ENV PATH="/opt/python/bin:$PATH"

RUN chown -R app:app /config /downloads && chmod +x /usr/local/bin/healthcheck && \
  sed -i 's$#!\/app\/\.venv\/bin\/python$#!/opt/python/bin/python$' /opt/python/bin/* && \
  sed -i "s%'\/app\/\.venv'%'/opt/python'%" /opt/python/bin/activate* && \
  chmod +x /usr/bin/mp4box

VOLUME /config
VOLUME /downloads

EXPOSE 8081

USER app

WORKDIR /tmp

HEALTHCHECK --interval=10s --timeout=20s --start-period=10s --retries=3 CMD [ "/usr/local/bin/healthcheck" ]

ENTRYPOINT ["/entrypoint.sh"]

ENV PYDEVD_DISABLE_FILE_VALIDATION=1

CMD ["/opt/python/bin/python", "/app/app/main.py", "--ytptube-mp"]
