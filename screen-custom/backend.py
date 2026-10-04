"""Local-only GL/Mudi integration. No listener, web token, or arbitrary command API."""
import hmac
import json
import os
import re
import subprocess
import time
import urllib.request
from pathlib import Path

STATE = Path('/root/dashboard')
ATTEMPTS = Path('/tmp/mudi7-screen-private/attempts.json')
ALLOWED = {
    ('openclash', 'get_status'), ('openclash', 'set_config'), ('openclash', 'refresh_subscription'),
    ('radio-scan', 'get_status'), ('radio-scan', 'start_scan'),
    ('adguardhome', 'get_config'), ('adguardhome', 'set_config'),
    ('cable', 'get_ports_config'), ('cable', 'get_ports_status'), ('cable', 'set_port_config'),
    ('repeater', 'get_status'), ('screen', 'get_config'), ('screen', 'set_config'), ('screen','get_unlock_attempts'),
}

def array(v):
    return v if isinstance(v, list) else []

def safe_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default if default is not None else {}

def save_private(path, value):
    path = Path(path)
    path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    if path.parent.is_symlink() or (hasattr(os,'geteuid') and path.parent.stat().st_uid!=os.geteuid()):
        raise RuntimeError('私有目录权限异常')
    os.chmod(path.parent,0o700)
    with open(str(path)+'.new', 'w', encoding='utf-8') as f:
        os.chmod(f.name, 0o600)
        json.dump(value, f, ensure_ascii=False)
    os.replace(str(path)+'.new', path)

def command(args, timeout=8):
    p = subprocess.run(args, capture_output=True, timeout=timeout)
    if p.returncode:
        raise RuntimeError('设备接口调用失败')
    return p.stdout.decode('utf-8', errors='replace').strip()

def uci(key, default=''):
    try:
        return command(['uci', '-q', 'get', key])
    except (RuntimeError, subprocess.TimeoutExpired, OSError):
        return default

def rpc(module, method, args=None, timeout=12):
    if (module, method) not in ALLOWED:
        raise ValueError('接口不在固定允许清单中')
    body = json.dumps({'jsonrpc':'2.0','id':1,'method':'call',
                       'params':['',module,method,args or {}]}).encode()
    request = urllib.request.Request('http://127.0.0.1/rpc', body,
        {'glinet':'1','Content-Type':'application/json'})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.load(response)
    if result.get('error'):
        raise RuntimeError('原厂接口拒绝请求')
    value = result.get('result', {})
    if isinstance(value, list) and value and isinstance(value[0], int):
        if value[0] != 0:
            raise RuntimeError('原厂接口执行失败')
        value = value[1] if len(value)>1 else {}
    if isinstance(value, dict) and (value.get('success') is False or value.get('err_code',0)):
        raise RuntimeError(value.get('error') or value.get('err_msg') or '设置未完成')
    return value

def pin_settings():
    # GL's key/value STRING format stores surrounding JSON quotes in UCI.
    raw = uci('gl_screen.generic.PASSCODE')
    try:
        pin = json.loads(raw)
    except ValueError:
        pin = raw
    enabled = uci('gl_screen.generic.ENABLE_PASSCODE', '1') == '1'
    valid = isinstance(pin, str) and re.fullmatch(r'\d{4}', pin) is not None
    try:
        seconds = int(uci('gl_screen.generic.AUTO_LOCK_TIME', '60'))
    except ValueError:
        seconds = 60
    try:
        native_lockout=bool(rpc('screen','get_unlock_attempts').get('unlock_attempt_exceed_limit'))
    except Exception:
        native_lockout=True  # Never bypass an unreadable vendor lockout state.
    return {'enabled':enabled,'valid':valid,'pin':pin if valid else '',
            'native_lockout':native_lockout,'always_on':uci('gl_screen.generic.ALWAYS_ON','0')=='1',
            'timeout':max(0,min(seconds,3600))}

class PinGuard:
    def __init__(self, provider=pin_settings, store=ATTEMPTS, clock=time.time):
        self.provider, self.store, self.clock = provider, Path(store), clock

    def remaining(self):
        v=safe_json(self.store)
        return max(0,int(v.get('until',0)-self.clock()+0.999))

    def check(self, entry):
        settings=self.provider()
        if not settings['valid']:
            return False, '密码读取异常，请切回原厂'
        if settings.get('native_lockout'):
            return False, '原厂已限制解锁，请稍候'
        if self.remaining():
            return False, '请稍候再试'
        if isinstance(entry,str) and hmac.compare_digest(entry,settings['pin']):
            save_private(self.store,{'failed':0,'until':0})
            return True, ''
        state=safe_json(self.store)
        failed=int(state.get('failed',0))+1
        until=self.clock()+min(300,60*(2**min(2,failed//5-1))) if failed>=5 else 0
        save_private(self.store,{'failed':failed,'until':until})
        return False, '密码错误' if failed<5 else '尝试过多，请稍候'

def scan_status(kind):
    if kind not in ('wifi','cellular'):
        raise ValueError('不支持的扫描类型')
    return rpc('radio-scan','get_status',{'kind':kind})

def scan_start(kind):
    if kind not in ('wifi','cellular'):
        raise ValueError('不支持的扫描类型')
    return rpc('radio-scan','start_scan',{'kind':kind})

def agh_stats():
    authorization=Path('/etc/mudi7-management/adguard-api.authorization').read_text().strip()
    if not re.fullmatch(r'Basic [A-Za-z0-9+/=]+',authorization):
        raise RuntimeError('AGH 本机授权缺失')
    request=urllib.request.Request('http://127.0.0.1:3000/control/stats',headers={'Authorization':authorization})
    with urllib.request.urlopen(request,timeout=8) as response:
        raw=json.load(response)
    return {k:raw.get(k) for k in ('num_dns_queries','num_blocked_filtering') } | {
        k:array(raw.get(k))[:5] for k in ('top_queried_domains','top_blocked_domains')}

def agh_set(enabled):
    if type(enabled) is not bool:
        raise ValueError('无效开关')
    rpc('adguardhome','set_config',{'enabled':enabled},timeout=20)
    # Keep existing loopback AGH -> Clash DNS coordination, not a new DNS stack.
    subprocess.run(['/usr/libexec/mudi7-dns-sync'],capture_output=True,timeout=20,check=True)
    if rpc('adguardhome','get_config').get('enabled') is not enabled:
        raise RuntimeError('AGH 开关尚未应用')

def oc_set(**args):
    allowed={'enabled','mode','operation_mode','ipv6_enabled'}
    if not args or set(args)-allowed:
        raise ValueError('无效 OpenClash 设置')
    return rpc('openclash','set_config',args)

def core_request(path, method='GET', payload=None):
    # Runtime YAML alone contains the effective API secret on this device.
    if path not in ('/proxies','/configs') and not re.fullmatch(r'/proxies/[^/]+',path):
        raise ValueError('无效核心接口')
    name=Path(uci('openclash.config.config_path')).name
    if not name or name in ('.','..') or not name.endswith(('.yaml','.yml')):
        raise RuntimeError('核心配置名称无效')
    key=command(['ruby','-ryaml','-e','print YAML.load_file(ARGV[0],aliases:true)["secret"]','/etc/openclash/'+name])
    port=uci('openclash.config.cn_port','9090')
    if not port.isdigit() or not 1<=int(port)<=65535:
        raise RuntimeError('核心端口无效')
    body=json.dumps(payload).encode() if payload is not None else None
    request=urllib.request.Request('http://127.0.0.1:'+port+path,body,
        {'Authorization':'Bearer '+key,'Content-Type':'application/json'},method=method)
    with urllib.request.urlopen(request,timeout=8) as response:
        data=response.read()
        return json.loads(data) if data else {}

def proxy_groups():
    values=core_request('/proxies').get('proxies',{})
    return [{'name':name,'now':v.get('now',''),'all':array(v.get('all')),'type':v.get('type')}
            for name,v in values.items() if v.get('type')=='Selector' and array(v.get('all'))]

def proxy_select(group,node):
    from urllib.parse import quote
    groups=proxy_groups()
    current=next((x for x in groups if x['name']==group),None)
    if not current or node not in current['all']:
        raise ValueError('节点已变更，请刷新列表')
    core_request('/proxies/'+quote(group,safe=''),'PUT',{'name':node})
    verified=next((x for x in proxy_groups() if x['name']==group),{})
    if verified.get('now')!=node:
        raise RuntimeError('节点切换未确认')

def port_info():
    configs=array(rpc('cable','get_ports_config').get('ports'))
    states=array(rpc('cable','get_ports_status').get('ports'))
    choices=[p for p in configs if p.get('name')=='wan' and str(p.get('support_wan'))=='1']
    if len(choices)!=1:
        raise RuntimeError('未找到本机可切换的 Ethernet 网口')
    p=choices[0].copy()
    state=next((x for x in states if x.get('name')==p['name']),{})
    return dict(p,state=state)

def port_payload(mode,info,saved):
    if mode not in ('lan','wan') or info.get('name')!='wan':
        raise ValueError('无效网口参数')
    payload={'name':'wan','mode':mode}
    if mode=='wan':
        mac=info.get('macaddr') or {}
        # Preserve existing MAC choice; do not invent/spoof an address.
        if mac.get('mode') not in ('default','clone','manual') or not mac.get('macaddr'):
            raise RuntimeError('需在原厂网页先确认 MAC 设置')
        payload['macaddr']={'mode':mac['mode'],'macaddr':mac['macaddr']}
    else:
        state=info.get('state',{}) if info.get('mode')=='lan' else saved
        if not state or state.get('vlan_mode') not in ('Standard','Multiple VLANs'):
            raise RuntimeError('缺少原 LAN/VLAN 配置，请使用原厂网页')
        for k in ('vlan_mode','pvid','trunk_tag'):
            if k in state:
                payload[k]=state[k]
    return payload

def port_set(mode):
    info=port_info()
    if info['mode']==mode:
        return
    file=STATE/'port-lan-state.json'
    saved=safe_json(file)
    payload=port_payload(mode,info,saved)
    if info['mode']=='lan':
        save_private(file,{k:v for k,v in info['state'].items() if k in ('vlan_mode','pvid','trunk_tag')})
    rpc('cable','set_port_config',payload,timeout=60)
    for _ in range(10):
        if port_info()['mode']==mode:
            return
        time.sleep(1)
    raise RuntimeError('网口切换尚未确认，请到原厂网页核对')

def repeater_status():
    raw=rpc('repeater','get_status')
    result={k:raw.get(k) for k in ('ssid','bssid','connected','state','state_s','signal','fail_type','band')}
    # `connected` is a human-readable duration, NOT a state string in 4.10.
    result['is_connected']=raw.get('state_s')=='connected'
    return result

def repeater_connect(ap,password):
    rows=array(scan_status('wifi').get('rows'))
    current=next((x for x in rows if x.get('bssid')==ap.get('bssid') and x.get('ssid')==ap.get('ssid')),None)
    if not current or not current.get('ssid'):
        raise ValueError('扫描记录已变化或 SSID 隐藏，请重新扫描')
    if not isinstance(password,str) or len(password)>128:
        raise ValueError('Wi-Fi 密码无效')
    args={'ssid':current['ssid'],'bssid':current['bssid'],'remember':True}
    if password:
        args['key']=password
    # Password is passed on stdin, never in process argv, error text or logs.
    result=subprocess.run(['lua','/root/dashboard/repeater-connect.lua'],
        input=json.dumps(args).encode(),capture_output=True,timeout=30)
    if result.returncode:
        raise RuntimeError('中继接口未接受连接请求')
    try:
        value=json.loads(result.stdout or b'{}')
    except ValueError:
        raise RuntimeError('中继接口响应无效')
    if value.get('err_code',0):
        raise RuntimeError('中继连接请求失败')
    for _ in range(30):
        status=repeater_status()
        if str(status.get('bssid') or '').lower()==current['bssid'].lower() and status.get('is_connected'):
            return
        if status.get('fail_type') not in (None,'','none') and status.get('state') not in (1,2):
            raise RuntimeError('连接未成功，请检查密码或信号')
        time.sleep(1)
    raise RuntimeError('连接未确认，请检查原厂中继页面')

def saved_key(ssid):
    # Parse JSON from Lua UCI instead of fragile shell quoting. Never expose keys.
    script='local c=require"uci".cursor();local j=require"cjson";local t={};c:foreach("repeater","network",function(s) if s.ssid and s.key then t[s.ssid]=s.key end end);print(j.encode(t))'
    try:
        return json.loads(command(['lua','-e',script])).get(ssid)
    except (ValueError,RuntimeError):
        return None
