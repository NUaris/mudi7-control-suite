from pathlib import Path
from router_tool import connect, put, execute

base = Path(__file__).parent
files = {
    'radio-parse.lua': '/etc/mudi7-management/radio-parse.lua',
    'radio-scan.lua': '/etc/mudi7-management/radio-scan.lua',
    'radio-scan-rpc.lua': '/usr/lib/oui-httpd/rpc/radio-scan',
    'mudi7-wifi-scan.lua': '/usr/libexec/mudi7-wifi-scan.lua',
    'mudi7-cellular-scan.lua': '/usr/libexec/mudi7-cellular-scan.lua',
    'radio-scan-menu.json': '/usr/share/oui/menu.d/radio-scan.json',
    'gl-sdk4-ui-radio-scan.common.js': '/www/views/gl-sdk4-ui-radio-scan.common.js',
}
client = connect()
try:
    for local, remote in files.items():
        put(client, str(base / local), remote, '644')
        print('installed=' + remote)
    put(client, str(base / 'sysupgrade.paths'), '/tmp/mudi7-sysupgrade.paths', '600')
    result = execute(client, '''
set -e
lua -e 'for _,p in ipairs({"/etc/mudi7-management/radio-parse.lua","/etc/mudi7-management/radio-scan.lua","/usr/lib/oui-httpd/rpc/radio-scan","/usr/libexec/mudi7-wifi-scan.lua","/usr/libexec/mudi7-cellular-scan.lua"}) do assert(loadfile(p)) end;print("Lua syntax OK")' && nginx -t && /etc/init.d/nginx reload
while IFS= read -r path; do
    case "$path" in ''|'#'*) continue;; esac
    grep -qxF "$path" /etc/sysupgrade.conf || printf '%s\\n' "$path" >> /etc/sysupgrade.conf
done < /tmp/mudi7-sysupgrade.paths
''')
    if result:
        raise SystemExit(result)
finally:
    client.close()
