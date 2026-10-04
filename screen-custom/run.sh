#!/bin/sh
# No unconditional respawn: hand the physical screen back after three crashes.
umask 077
child=''
stop_child() {
    [ -n "$child" ] && kill -TERM "$child" 2>/dev/null
    [ -n "$child" ] && wait "$child" 2>/dev/null
    exit 0
}
trap stop_child TERM INT
failures=0
while :; do
    started=$(date +%s)
    python3 /root/dashboard/main.py &
    child=$!
    wait "$child"
    result=$?
    [ "$result" -eq 0 ] && exit 0
    elapsed=$(( $(date +%s) - started ))
    [ "$elapsed" -ge 300 ] && failures=0
    failures=$((failures + 1))
    logger -t citydash "screen process stopped; attempt $failures"
    if [ "$failures" -ge 3 ]; then
        /etc/init.d/citydash disable
        /etc/init.d/gl_screen enable
        /etc/init.d/gl_screen start
        exit 1
    fi
    sleep 2
done
