-- The firmware's small Lua nginx module has no body-filter directives.
-- This content handler is mounted only behind the GL token access check.
local endpoint=ngx.var.uri
if endpoint~='/control/stats' and endpoint~='/control/stats_info' then
    return ngx.exit(404)
end
local authorization=ngx.var.mudi7_adguard_authorization or ''
if not authorization:match('^Basic [%w+/=]+$') then return ngx.exit(401) end
local nixio=require'nixio'
local fs=require'nixio.fs'
local root='/tmp/mudi7-adguard-stats'
fs.mkdir(root,'700'); fs.chmod(root,'700')
local header=root..'/curl-'..tostring(nixio.getpid())..'.conf'
local ok,result=pcall(function()
    local f=assert(io.open(header,'w'))
    f:write('header = "Authorization: '..authorization..'"\n')
    f:close();fs.chmod(header,'600')
    f=assert(io.popen('curl -sS --max-time 4 --max-filesize 2097152 -K '..header..
        ' -w "\\n%{http_code}" http://127.0.0.1:3000'..endpoint..' 2>/dev/null'))
    local output=f:read('*a');f:close()
    local raw,code=output:match('^(.*)\n(%d%d%d)$')
    assert(raw and code=='200' and #raw<=2097152,'AGH statistics unavailable')
    assert(pcall(require'cjson'.decode,raw),'Invalid AGH statistics')
    if endpoint=='/control/stats' then
        return dofile('/etc/mudi7-management/adguard-rankings.lua').limit(raw,5)
    end
    return raw
end)
fs.unlink(header)
if not ok then return ngx.exit(503) end
ngx.header['Content-Type']='application/json'
ngx.header['Cache-Control']='no-store'
ngx.say(result)
