#!/bin/sh
if [ "${1:-}" = once ] || [ "${1:-}" = baseline ]; then
    exec lua /usr/libexec/mudi7-dns-sync.lua "$1"
fi
while :; do
    lua /usr/libexec/mudi7-dns-sync.lua once
    sleep 4
done
