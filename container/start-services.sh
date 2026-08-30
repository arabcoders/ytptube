#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -eq 0 ]; then
  echo "ERROR: No YTPTube command was provided." >&2
  exit 2
fi

case "${YTP_BGUTIL_ENABLED:-true}" in
  1 | true | yes | on)
    ;;
  *)
    exec "$@"
    ;;
esac

pids=()

stop_services() {
  trap - TERM INT
  kill -TERM "${pids[@]}" 2>/dev/null || true
  wait "${pids[@]}" 2>/dev/null || true
}

wait_services() {
  trap - TERM INT
  wait "${pids[@]}" 2>/dev/null || true
}

trap 'wait_services; exit 0' TERM INT

/usr/bin/deno run \
  --allow-env \
  --allow-net \
  --allow-ffi=/opt/bgutil-provider/node_modules \
  --allow-read=/opt/bgutil-provider/node_modules \
  /opt/bgutil-provider/src/main.ts &
pids+=("$!")

"$@" &
pids+=("$!")

status=0
wait -n "${pids[@]}" || status=$?
if [ "$status" -eq 0 ]; then
  status=1
fi

stop_services
exit "$status"
