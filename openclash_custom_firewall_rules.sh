#!/bin/sh
# Read this router's ULA instead of publishing a device-specific IPv6 prefix.
# Merge into existing hooks rather than overwriting other firewall additions.
mudi7_ula=$(uci -q get network.globals.ula_prefix)
if printf '%s\n' "$mudi7_ula" | grep -Eq '^[fF][dD][[:xdigit:]:]+/[0-9]{1,3}$'; then
    nft "add element inet fw4 localnetwork6 { $mudi7_ula }" 2>/dev/null
fi
for mudi7_chain in openclash_mangle openclash_mangle_v6; do
    nft "insert rule inet fw4 $mudi7_chain meta l4proto { tcp, udp } th dport 53 counter return comment \"Mudi7 DNS to AdGuard\"" 2>/dev/null
done

exit 0
