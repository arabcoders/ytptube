#!/usr/bin/env bash

set -eu pipefail

LOCAL_PORT="${YTP_PORT:-8081}"

/usr/bin/curl -f "http://localhost:${LOCAL_PORT}/ping"
