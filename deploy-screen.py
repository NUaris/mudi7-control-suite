from pathlib import Path
from router_tool import connect, put, execute

base=Path(__file__).parent
upstream=base/'screen-upstream'
custom=base/'screen-custom'
client=connect()
try:
    status=execute(client,'test ! -e /root/dashboard && test ! -e /etc/init.d/citydash && test ! -e /etc/init.d/homebutton && mkdir -m 700 /root/dashboard')
    if status:raise RuntimeError('Screen install path exists; inspect before retrying')
    for name in ['dashboard.py','button_watch.py','screen_sleep.sh','LICENSE']:
        put(client,str(upstream/name),'/root/dashboard/'+name,'755' if name.endswith('.sh') else '600')
    for name in ['backend.py','mudi_ui.py','main.py','repeater-connect.lua','test_screen.py','verify-device.py','prepare-live.py','run.sh','toggle.sh','UPSTREAM.json']:
        put(client,str(custom/name),'/root/dashboard/'+name,'755' if name.endswith('.sh') else '600')
    put(client,str(custom/'citydash'),'/etc/init.d/citydash','755')
    put(client,str(upstream/'homebutton'),'/etc/init.d/homebutton','755')
    put(client,str(base/'sysupgrade.paths'),'/tmp/mudi7-sysupgrade.paths','600')
    if execute(client, '''while IFS= read -r path; do
case "$path" in ''|'#'*) continue;; esac
grep -qxF "$path" /etc/sysupgrade.conf || printf '%s\\n' "$path" >> /etc/sysupgrade.conf
done < /tmp/mudi7-sysupgrade.paths'''):
        raise RuntimeError('Could not merge sysupgrade paths')
    put(client,str(base/'radio-parse.lua'),'/etc/mudi7-management/radio-parse.lua','644')
    status=execute(client,'''cd /root/dashboard && python3 -m py_compile backend.py mudi_ui.py main.py dashboard.py button_watch.py && python3 test_screen.py && python3 verify-device.py && sh -n run.sh toggle.sh screen_sleep.sh && lua -e 'assert(loadfile("/root/dashboard/repeater-connect.lua"));assert(loadfile("/etc/mudi7-management/radio-parse.lua"));print("Lua bridge syntax OK")' ''' )
    if status:raise SystemExit(status)
    print('Screen files installed and tested. Physical screen NOT switched yet.')
finally:
    client.close()
