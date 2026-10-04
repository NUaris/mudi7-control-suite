local j=require'cjson'
local function enc(s)return (s:gsub('[^%w]',function(x)return string.format('%%%02X',x:byte())end))end
local function call(path,body)
    local extra=''
    if body then
        local f=assert(io.open('/tmp/mudi7-core-payload','w'));f:write(j.encode(body));f:close()
        extra=' -X PUT -H "Content-Type: application/json" --data-binary @/tmp/mudi7-core-payload'
    end
    local f=io.popen('curl -fsS --max-time 12 -K /tmp/mudi7-core-curl.conf'..extra..' "http://127.0.0.1:9090'..path..'"')
    local raw=f:read('*a');f:close();return j.decode(raw~='' and raw or '{}')
end
if arg[1]=='select' then print(j.encode(call('/proxies/'..enc('狗狗加速.com'),{name=arg[2]})))
elseif arg[1]=='delay' then print(arg[2]..' '..j.encode(call('/proxies/'..enc(arg[2])..'/delay?timeout=5000&url=https%3A%2F%2Fwww.google.com%2Fgenerate_204')))
else
    local proxies=call('/proxies').proxies
    for name,p in pairs(proxies) do if p.now then print(j.encode({name=name,type=p.type,now=p.now,history=p.history})) end end
    local conf=call('/configs');print(j.encode({mode=conf.mode,ipv6=conf.ipv6}))
end
