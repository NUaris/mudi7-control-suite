#!/bin/sh
# Recover a saved native "enabled" setting when its worker never started procd.
task_lock=/tmp/mudi7-adguard-start.lock
mkdir "$task_lock" 2>/dev/null || exit 0
trap 'rmdir "$task_lock" 2>/dev/null' EXIT INT TERM
[ "$(uci -q get adguardhome.config.enabled)" = 1 ] || exit 0
pidof AdGuardHome >/dev/null 2>&1 && exit 0
/etc/init.d/adguardhome start
if [ "$(uci -q get adguardhome.config.enabled)" != 1 ]; then
    /etc/init.d/adguardhome stop
fi
