#!/usr/bin/env bash
set -e

echo "Setting umask to ${UMASK}"
umask ${UMASK}

echo_err() { cat <<< "$@" 1>&2; }

if [ ! -w "${YTP_CONFIG_PATH}" ]; then
  CH_USER=$(stat -c "%u" "${YTP_CONFIG_PATH}")
  CH_GRP=$(stat -c "%g" "${YTP_CONFIG_PATH}")
  echo_err "ERROR: Unable to write to [${YTP_CONFIG_PATH}] data directory. Current user id [${UID}] while directory owner is [${CH_USER}]"
  echo_err "[Running under docker]"
  echo_err "change docker-compose.yaml user: to user:\"${CH_USER}:${CH_GRP}\""
  echo_err "Run the following command to change the directory ownership"
  echo_err "chown -R \"${CH_USER}:${CH_GRP}\" ./config"
  echo_err "[Running under podman]"
  echo_err "change docker-compose.yaml user: to user:\"0:0\""
  exit 1
fi

exec "${@}"
