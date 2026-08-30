#!/usr/bin/env bash
set -e

echo "Setting umask to '${UMASK}', to change it set the UMASK environment variable"
umask ${UMASK}

echo_err() { cat <<<"$@" 1>&2; }

permission_help() {
  local owner="$1"
  local group="$2"
  local path="$3"

  if [ "${container:-}" = "podman" ] || [ -f /run/.containerenv ]; then
    echo_err "[Running under podman]"
    echo_err "replace the compose.yaml user line with userns_mode: keep-id"
  elif [ -f /.dockerenv ]; then
    echo_err "[Running under docker]"
    echo_err "change compose.yaml user to \"${owner}:${group}\""
  fi

  echo_err "Run the following command to change the directory ownership"
  echo_err "chown -R \"\$(id -u):\$(id -g)\" ./${path}"
}

if [ ! -w "${YTP_CONFIG_PATH}" ]; then
  CH_USER=$(stat -c "%u" "${YTP_CONFIG_PATH}")
  CH_GRP=$(stat -c "%g" "${YTP_CONFIG_PATH}")
  echo_err "ERROR: Unable to write to '${YTP_CONFIG_PATH}' data directory. Current user id '${UID}' while directory owner is '${CH_USER}'."
  permission_help "${CH_USER}" "${CH_GRP}" "config"
  exit 1
fi

if [ "${YTP_DOWNLOAD_PATH}" != "/" ] && [ ! -w "${YTP_DOWNLOAD_PATH}" ]; then
  CH_USER=$(stat -c "%u" "${YTP_DOWNLOAD_PATH}")
  CH_GRP=$(stat -c "%g" "${YTP_DOWNLOAD_PATH}")
  echo_err "ERROR: Unable to write to '${YTP_DOWNLOAD_PATH}' downloads directory. Current user id '${UID}' while directory owner is '${CH_USER}'."
  permission_help "${CH_USER}" "${CH_GRP}" "downloads"
  exit 1
fi

###########
# Run yt-dlp upgrader
# This will update yt-dlp to the latest version
###########
/opt/python/bin/python /app/app/upgrader.py

exec /usr/local/bin/start-services "${@}"
