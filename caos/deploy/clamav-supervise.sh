#!/bin/sh
# The pinned image's /init prepares signatures and starts FreshClam, but then
# execs tail forever. Keep that initialization and make daemon death observable
# to Docker's restart policy. PING readiness must not restart a busy scanner.
set -eu

/bin/sh /init &
initializer=$!
trap 'kill -TERM "$initializer" 2>/dev/null || true' EXIT
trap 'exit 0' INT TERM

started=false
while kill -0 "$initializer" 2>/dev/null; do
    alive=false
    for pid in $(pgrep -x clamd || true); do
        started=true
        # /init's tail does not reap its child: pgrep/kill -0 alone also
        # match a dead clamd waiting as a zombie. Inspect the process state.
        if read -r process_id command state rest 2>/dev/null < "/proc/$pid/stat" \
            && [ "$state" != Z ] && [ "$state" != X ]; then
            alive=true
            break
        fi
    done
    if [ "$started" = true ] && [ "$alive" = false ]; then
        echo "ClamAV daemon exited; restarting scanner container." >&2
        exit 1
    fi
    sleep 1
done

echo "ClamAV initializer exited; restarting scanner container." >&2
exit 1
