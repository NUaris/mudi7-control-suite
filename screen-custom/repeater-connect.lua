-- Root-only stdin bridge; no password in argv, stdout, logs or browser APIs.
local json=require'cjson'
local raw=io.read(8193)
assert(raw and #raw<=8192,'oversized payload')
local a=json.decode(raw)
assert(type(a)=='table')
for k in pairs(a) do assert(k=='ssid' or k=='bssid' or k=='key' or k=='remember','invalid argument') end
assert(type(a.ssid)=='string' and #a.ssid>0 and #a.ssid<=128)
assert(type(a.bssid)=='string' and a.bssid:match('^%x%x:%x%x:%x%x:%x%x:%x%x:%x%x$'))
assert(a.remember==true)
assert(a.key==nil or type(a.key)=='string' and #a.key<=128)
local bus=assert(require'ubus'.connect())
local result=bus:call('repeater','connect',a)
bus:close()
assert(type(result)=='table','connection request failed')
print(json.encode({err_code=result.err_code or 0}))
