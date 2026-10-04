-- Apply the DNS integration to the actual running file, after native generation.
local fs=require'nixio.fs'
local j=require'cjson'
local c=require'uci'.cursor()
local configured=assert(c:get('openclash','config','config_path'))
local path='/etc/openclash/'..assert(configured:match('([^/]+)$'))
local function quote(s)return "'"..s:gsub("'","'\\''").."'"end
local function cmd(s)
    local f=assert(io.popen(s));local v=f:read('*a');f:close();return(v:gsub('%s+$',''))
end
local key=cmd([[ruby -ryaml -e 'v=YAML.load_file(ARGV[0],aliases:true);print v["secret"]' ]]..quote(path))
assert(not key:find('[\r\n"]'),'Invalid controller key')
local header='/tmp/mudi7-apply-curl.conf'
local payload='/tmp/mudi7-apply-payload'
local function write(p,s)local f=assert(io.open(p,'w'));f:write(s);f:close();fs.chmod(p,'600')end
write(header,'header = "Authorization: Bearer '..key..'"\n')
local ok,err=pcall(function()
    local status=os.execute('ruby /etc/mudi7-management/openclash-dns-overwrite.rb '..quote(path)..' >/tmp/mudi7-core-overwrite.log 2>&1')
    assert(status==0,'DNS overwrite failed')
    write(payload,j.encode({path=path}))
    local code=cmd('curl -sS --max-time 10 -K '..header..' -X PUT -H "Content-Type: application/json" --data-binary @'..payload..' -o /tmp/mudi7-core-apply-response -w "%{http_code}" "http://127.0.0.1:9090/configs?force=true"')
    assert(code=='204' or code=='200','Core rejected DNS configuration')
end)
fs.unlink(header);fs.unlink(payload);fs.unlink('/tmp/mudi7-core-apply-response')
assert(ok,err)
