FROM node:lts-alpine as npm_builder

WORKDIR /ytptube
COPY frontend ./
RUN npm ci && npm run build

FROM python:3.11-alpine as python_builder

ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONFAULTHANDLER 1

# Use sed to strip carriage-return characters from the entrypoint script (in case building on Windows)
# Install dependencies
RUN apk add --update coreutils curl gcc g++ musl-dev libffi-dev openssl-dev && pip install pipenv

WORKDIR /app

COPY ./Pipfile* .

RUN PIPENV_VENV_IN_PROJECT=1 pipenv install --deploy

FROM python:3.11-alpine

ARG TZ=UTC
ARG USER_ID=1000
ENV IN_CONTAINER=1
ENV UMASK=022
ENV YTP_CONFIG_PATH=/config
ENV YTP_TEMP_PATH=/tmp
ENV YTP_DOWNLOAD_PATH=/downloads
ENV YTP_PORT=8081

# removed ffmpeg as 6.1.0 is broken with DASH protocal downloads
COPY --from=mwader/static-ffmpeg:6.1.1 /ffmpeg /usr/bin/
COPY --from=mwader/static-ffmpeg:6.1.1 /ffprobe /usr/bin/

RUN mkdir /config /downloads && ln -snf /usr/share/zoneinfo/${TZ} /etc/localtime && echo ${TZ} > /etc/timezone && \
  apk add --update --no-cache bash mkvtoolnix patch aria2 coreutils curl shadow sqlite tzdata libmagic && \
  useradd -u ${USER_ID:-1000} -U -d /app -s /bin/bash app && \
  rm -rf /var/cache/apk/*

COPY entrypoint.sh /

RUN sed -i 's/\r$//g' /entrypoint.sh && chmod +x /entrypoint.sh

COPY --chown=app:app ./app /app/app
COPY --chown=app:app --from=npm_builder /ytptube/dist /app/frontend/dist
COPY --chown=app:app --from=python_builder /app/.venv /app/.venv
COPY --chown=app:app ./healthcheck.sh /usr/local/bin/healthcheck

ENV PATH="/app/.venv/bin:$PATH"

RUN chown -R app:app /config /downloads && chmod +x /usr/local/bin/healthcheck

VOLUME /config
VOLUME /downloads

EXPOSE 8081

USER app

WORKDIR /tmp

HEALTHCHECK --interval=10s --timeout=20s --start-period=10s --retries=3 CMD [ "/usr/local/bin/healthcheck" ]

ENTRYPOINT ["/entrypoint.sh"]

CMD ["/app/.venv/bin/python", "/app/app/main.py", "--mainprocess"]
