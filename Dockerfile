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

RUN mkdir /config /downloads && ln -snf /usr/share/zoneinfo/${TZ} /etc/localtime && echo ${TZ} > /etc/timezone && \
  apk add --update --no-cache bash ffmpeg mkvtoolnix patch aria2 coreutils curl shadow sqlite tzdata && \
  useradd -u ${USER_ID:-1000} -U -d /app -s /bin/bash app && \
  rm -rf /var/cache/apk/*

COPY entrypoint.sh /

RUN sed -i 's/\r$//g' /entrypoint.sh && chmod +x /entrypoint.sh

COPY --chown=app:app ./app /app/app
COPY --chown=app:app --from=npm_builder /ytptube/dist /app/frontend/dist
COPY --chown=app:app --from=python_builder /.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH"

RUN chown -R app:app /config /downloads

VOLUME /config
VOLUME /downloads

EXPOSE 8081

# Switch to user
#
USER app

WORKDIR /tmp

ENTRYPOINT ["/entrypoint.sh"]

CMD ["/app/.venv/bin/python", "/app/app/main.py"]
