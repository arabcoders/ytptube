#!/usr/bin/env bash
set -euuo pipefail

LOCAL_PORT="${YTP_PORT:-8081}"

curl_args=(-f)

if [[ -n "${YTP_AUTH_USERNAME:-}" && -n "${YTP_AUTH_PASSWORD:-}" ]]; then
  cred=$(printf '%s:%s' "${YTP_AUTH_USERNAME}" "${YTP_AUTH_PASSWORD}" | base64 | tr -d '\n')
  curl_args+=(-H "Authorization: Basic ${cred}")
fi

curl_args+=("http://localhost:${LOCAL_PORT}/api/ping")
/usr/bin/curl "${curl_args[@]}"
