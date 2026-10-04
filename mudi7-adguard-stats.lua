-- Preserve GL's authenticated, read-only statistics after AGH gets local users.
-- Only mounted on exact /control/stats and /control/stats_info paths.
if ngx.req.get_method() ~= 'GET' then
    return ngx.exit(ngx.HTTP_NOT_ALLOWED)
end
local cookie=ngx.req.get_headers()['cookie']
if type(cookie)~='string' then return ngx.exit(ngx.HTTP_UNAUTHORIZED) end
local token=cookie:match('^%s*Admin%-Token=([^;]+)') or cookie:match(';%s*Admin%-Token=([^;]+)')
if type(token) ~= 'string' or #token < 16 or #token > 256 or
        not token:match('^[%w_-]+$') then
    return ngx.exit(ngx.HTTP_UNAUTHORIZED)
end
local f = io.open('/tmp/gl_token_' .. token, 'rb')
local bytes
if f then bytes=f:read(4); f:close() end
if not bytes or #bytes ~= 4 then return ngx.exit(ngx.HTTP_UNAUTHORIZED) end
local stamp=0
for i=4,1,-1 do stamp=stamp*256+bytes:byte(i) end
local now=ngx.time()
if stamp > now+60 or now >= stamp+3600 then
    return ngx.exit(ngx.HTTP_UNAUTHORIZED)
end
f=io.open('/etc/mudi7-management/adguard-api.authorization','rb')
local authorization
if f then authorization=f:read('*a'); f:close() end
authorization=(authorization or ''):gsub('%s+$','')
if not authorization:match('^Basic [%w+/=]+$') then
    return ngx.exit(ngx.HTTP_SERVICE_UNAVAILABLE)
end
ngx.var.mudi7_adguard_authorization=authorization
