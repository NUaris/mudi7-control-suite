"""Read-only device integration checks. Never print PIN, API keys or Wi-Fi keys."""
import json
from pathlib import Path
import backend as api
import mudi_ui as ui

s=api.pin_settings()
assert s['enabled'] and s['valid'] and not s['native_lockout']
oc=api.rpc('openclash','get_status')
agh=api.rpc('adguardhome','get_config')
stats=api.agh_stats()
port=api.port_info()
repeater=api.repeater_status()
wifi=api.scan_status('wifi')
cellular=api.scan_status('cellular')
groups=api.proxy_groups()
assert oc['running'] and agh['enabled']
assert port['mode'] in ('lan','wan') and repeater['is_connected']
assert groups
assert len(api.array(stats['top_queried_domains']))<=5
assert len(api.array(stats['top_blocked_domains']))<=5
print(json.dumps({'pin_reused':True,'pin_enabled':s['enabled'],'native_lockout':s['native_lockout'],
    'auto_lock_seconds':s['timeout'],'clash_running':oc['running'],'agh_enabled':agh['enabled'],
    'subscription_available':oc.get('subscription',{}).get('available'),'selector_count':len(groups),
    'repeater_connected':repeater['is_connected'],'ethernet_mode':port['mode'],
    'wifi_records':len(api.array(wifi.get('rows'))),'cellular_serving':len(api.array(cellular.get('serving'))),
    'cellular_neighbors':len(api.array(cellular.get('neighbors'))),
    'queried_rank_count':len(api.array(stats['top_queried_domains'])),
    'blocked_rank_count':len(api.array(stats['top_blocked_domains']))}))
store=ui.Store();store.values={'oc':oc,'agh':agh,'stats':stats,'port':port,'repeater':repeater,
    'wifi':wifi,'cellular':cellular,'groups':groups,'battery':ui.hardware.get_battery()}
app=ui.App(store,s,preview=True)
out=Path('/tmp/mudi7-screen-render');out.mkdir(mode=0o700,exist_ok=True)
app.render().save(out/'lock.png');app.locked=False
for page in ['home','settings','oc','subscription','agh','rank','wifi','repeater','cellular','port']:
    app.page=page;app.page_number=0;app.render().save(out/(page+'.png'))
print('Read-only real-data preview rendered; framebuffer unchanged')
