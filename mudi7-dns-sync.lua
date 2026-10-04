-- Keep native AdGuard controls and OpenClash's DNS from bypassing each other.
local fs = require 'nixio.fs'
local cjson = require 'cjson'
local uci = require 'uci'
local ROOT = '/tmp/mudi7-dns-sync'
local BASE = '/etc/mudi7-management/dns-baseline.json'
local AUTH = '/etc/mudi7-management/adguard-api.authorization'
local function read(p)
    local f=io.open(p,'rb'); if not f then return nil end
    local v=f:read('*a'); f:close(); return v
end
local function write(p,v)
    local f=assert(io.open(p,'wb')); f:write(v); f:close(); fs.chmod(p,'600')
end
local function command(s)
    local f=io.popen(s); if not f then return '' end
    local v=f:read('*a'); f:close(); return (v:gsub('%s+$',''))
end
local function array_equal(a,b)
    if type(a)~='table' or type(b)~='table' then return a==b end
    if #a~=#b then return false end
    for i,v in ipairs(a) do if v~=b[i] then return false end end
    return true
end
fs.mkdir(ROOT,'700'); fs.chmod(ROOT,'700')
local token=read(ROOT..'/token')
if not token and not fs.access(AUTH) then
    local f=assert(io.open('/dev/urandom','rb')); local raw=f:read(16); f:close()
    token=raw:gsub('.',function(x)return string.format('%02x',string.byte(x))end)
    write(ROOT..'/token',token)
end
local function api(path,payload)
    local authorization=read(AUTH)
    if authorization then
        authorization=authorization:gsub('%s+$','')
        assert(authorization:match('^Basic [%w+/=]+$'),'invalid local AGH authorization')
        write(ROOT..'/curl.conf','header = "Authorization: '..authorization..'"\n')
    else
        -- Compatibility while migrating the original GL.iNet auth mode.
        local t=os.time(); local bytes={}
        for i=1,4 do bytes[i]=string.char(t%256); t=math.floor(t/256) end
        write('/tmp/gl_token_'..token,table.concat(bytes))
        write(ROOT..'/curl.conf','header = "Cookie: Admin-Token='..token..'"\n')
    end
    local extra=''
    if payload then
        -- This firmware's lua-cjson represents an empty table as an object.
        local encoded=cjson.encode(payload):gsub('"fallback_dns":{}','"fallback_dns":[]')
        write(ROOT..'/payload',encoded)
        extra=' -H "Content-Type: application/json" --data-binary @'..ROOT..'/payload'
    end
    return command('curl -fsS --max-time 4 -K '..ROOT..'/curl.conf'..extra..' http://127.0.0.1:3000/control/'..path..' 2>/dev/null')
end
local function sync()
    local c=uci.cursor()
    local want_ag=c:get('adguardhome','config','enabled')=='1'
    local ag=command('pidof AdGuardHome 2>/dev/null')~='' and want_ag
    if want_ag and not ag and not fs.access('/tmp/mudi7-openclash.lock') then
        local last=tonumber(read(ROOT..'/adguard-start-at') or '0') or 0
        if os.time()-last>=60 then
            write(ROOT..'/adguard-start-at',tostring(os.time()))
            os.execute('nohup /usr/libexec/mudi7-adguard-start >/tmp/mudi7-adguard-start.log 2>&1 </dev/null &')
        end
    end
    local ocpid=command('pidof clash 2>/dev/null')
    local want_oc=c:get('openclash','config','enable')=='1'
    local oc=ocpid~='' and want_oc
    if oc then oc=command("netstat -ln 2>/dev/null | grep ':7874 ' | head -n 1")~='' end
    if oc and not fs.access('/tmp/mudi7-openclash.lock') then
        -- Native AGH start/stop reloads fw4; restore proxy rules immediately.
        local ready=command("nft list chain inet fw4 openclash 2>/dev/null | grep 'redirect to' | head -n 1")~=''
        if not ready then os.execute('/etc/init.d/openclash reload firewall >/tmp/mudi7-firewall-sync.log 2>&1') end
    end
    local state
    if ag then
        local ok,info=pcall(cjson.decode,api('dns_info'))
        if not ok or type(info)~='table' then
            write('/tmp/mudi7-dns-state','AdGuard Home API 暂未就绪；正在重试')
            return
        end
        -- Do not silently resolve outside Clash while its core is restarting.
        local upstream=want_oc and {'127.0.0.1:7874'} or {'223.5.5.5','119.29.29.29'}
        local fallback=want_oc and {} or {'223.6.6.6','119.29.29.29'}
        if not array_equal(info.upstream_dns,upstream) or not array_equal(info.fallback_dns,fallback) or info.cache_size~=0 then
            api('dns_config',{upstream_dns=upstream,fallback_dns=fallback,
                bootstrap_dns={'223.5.5.5','119.29.29.29'},cache_size=0,upstream_timeout=3000000000})
            local ok2,after=pcall(cjson.decode,api('dns_info'))
            if not ok2 or not array_equal(after.upstream_dns,upstream) or not array_equal(after.fallback_dns,fallback) then
                write('/tmp/mudi7-dns-state','AdGuard Home 上游设置失败；正在重试'); return
            end
        end
    end
    local desired={}
    if ag or want_oc then
        desired.server={ag and '127.0.0.1#3053' or '127.0.0.1#7874'}
        desired.noresolv='1'; desired.cachesize='0'; desired.localuse='1'
        desired.resolvfile=cjson.decode(assert(read(BASE))).resolvfile
    else
        desired=cjson.decode(assert(read(BASE)))
    end
    local route=(ag and 'agh' or 'dns')..':'..(oc and ocpid or 'off')..':'..(c:get('openclash','config','operation_mode') or '')
    local transition=read(ROOT..'/route')~=route
    if ag and transition then api('cache_clear',{}) end
    local changed=false
    for _,k in ipairs({'server','noresolv','cachesize','resolvfile','localuse'}) do
        local value=desired[k]
        local current=c:get('dhcp','@dnsmasq[0]',k)
        if not array_equal(current,value) then
            if value==nil or value==cjson.null then c:delete('dhcp','@dnsmasq[0]',k)
            elseif type(value)=='table' then assert(c:set('dhcp','@dnsmasq[0]',k,value))
            else c:set('dhcp','@dnsmasq[0]',k,value) end
            changed=true
        end
    end
    if changed then assert(c:commit('dhcp')) end
    if changed or transition then os.execute('/etc/init.d/dnsmasq restart >/dev/null 2>&1') end
    if transition then write(ROOT..'/route',route) end
    if want_oc and not oc then state='OpenClash 正在恢复；暂不使用外部 DNS'
    elseif ag and oc then state='客户端 → AdGuard Home → OpenClash'
    elseif ag then state='客户端 → AdGuard Home → 外部 DNS（OpenClash 已关闭）'
    elseif oc then state='客户端 → OpenClash（AdGuard Home 已关闭）'
    else state='客户端 → 原厂 DNS（两个服务均已关闭）' end
    write('/tmp/mudi7-dns-state',state)
end
if arg[1]=='baseline' then
    if not fs.access(BASE) then
        local c=uci.cursor(); local v={}
        for _,k in ipairs({'server','noresolv','cachesize','resolvfile','localuse'}) do v[k]=c:get('dhcp','@dnsmasq[0]',k) end
        write(BASE,cjson.encode(v))
    end
    return
end
local lockpath=ROOT..'/lock'
local locked=fs.mkdir(lockpath,'700')
if not locked then
    local stat=fs.stat(lockpath)
    local pid=(read(lockpath..'/pid') or ''):match('^(%d+)%s*$')
    local process=pid and read('/proc/'..pid..'/cmdline') or ''
    if process and process:find('/usr/libexec/mudi7-dns-sync.lua',1,true) then return end
    -- Give a new owner time to record its PID before considering a stale lock.
    if not pid and stat and os.time()-(stat.mtime or 0)<10 then return end
    fs.unlink(lockpath..'/pid'); fs.rmdir(lockpath)
    locked=fs.mkdir(lockpath,'700')
    if not locked then return end
end
write(lockpath..'/pid',tostring(require'nixio'.getpid()))
local ok,err=pcall(sync)
fs.unlink(lockpath..'/pid'); fs.rmdir(lockpath)
if not ok then
    write('/tmp/mudi7-dns-state','DNS 协同检查出错；正在重试')
    io.stderr:write(tostring(err)..'\n')
    os.exit(1)
end
