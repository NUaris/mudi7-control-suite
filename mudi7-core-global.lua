local fs=require'nixio.fs'
local j=require'cjson'
local uci=require'uci'
if uci.cursor():get('openclash','config','proxy_mode')~='global' then return end
local function cmd(s)local f=assert(io.popen(s));local v=f:read('*a');f:close();return(v:gsub('%s+$',''))end
local secret=cmd([[ruby -ryaml -e 'v=YAML.load_file("/etc/openclash/doggygo-sub.yaml",aliases:true);print v["secret"]']])
local group=cmd([[ruby -ryaml -e 'v=YAML.load_file("/etc/openclash/doggygo-sub.yaml",aliases:true);print v["proxy-groups"].first["name"]']])
assert(group~='' and not secret:find('[\r\n"]'),'Invalid controller configuration')
local header='/tmp/mudi7-global-curl.conf'
local f=assert(io.open(header,'w'));f:write('header = "Authorization: Bearer '..secret..'"\n');f:close();fs.chmod(header,'600')
local raw=cmd('curl -fsS --max-time 5 -K '..header..' http://127.0.0.1:9090/proxies/GLOBAL')
local current=j.decode(raw)
if current.now=='DIRECT' or current.now=='REJECT' then
    local p='/tmp/mudi7-global-payload';f=assert(io.open(p,'w'));f:write(j.encode({name=group}));f:close();fs.chmod(p,'600')
    cmd('curl -fsS --max-time 5 -K '..header..' -X PUT -H "Content-Type: application/json" --data-binary @'..p..' http://127.0.0.1:9090/proxies/GLOBAL')
    current=j.decode(cmd('curl -fsS --max-time 5 -K '..header..' http://127.0.0.1:9090/proxies/GLOBAL'))
    assert(current.now==group,'Global group selection failed')
    fs.unlink(p)
end
fs.unlink(header)
