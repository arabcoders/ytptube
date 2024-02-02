#!/usr/bin/env bash

set -eu pipefail

/usr/bin/curl -f http://localhost:${YTP_PORT:-8081}/ping
