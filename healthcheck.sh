#!/usr/bin/env bash
set -euuo pipefail

LOCAL_PORT="${YTP_PORT:-8081}"
BASE_PATH="${YTP_BASE_PATH:-/}"

curl_args=(-f)

if [[ -n "${YTP_AUTH_USERNAME:-}" && -n "${YTP_AUTH_PASSWORD:-}" ]]; then
  cred=$(printf '%s:%s' "${YTP_AUTH_USERNAME}" "${YTP_AUTH_PASSWORD}" | base64 | tr -d '\n')
  curl_args+=(-H "Authorization: Basic ${cred}")
fi

# strip trailing slashes from BASE_PATH
BASE_PATH=$(echo "${BASE_PATH}" | sed 's:/*$::')

curl_args+=("http://localhost:${LOCAL_PORT}${BASE_PATH}/api/ping")
/usr/bin/curl "${curl_args[@]}"
