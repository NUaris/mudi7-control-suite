-- Only numeric, authenticated subscription metadata is returned to the browser.
local fs = require 'nixio.fs'
local uci = require 'uci'
local json = require 'cjson'
local M = {}
local CACHE = '/tmp/mudi7-subscription-info.json'
local LOCK = '/tmp/mudi7-subscription-info.lock'
local function read(path)
    local f = io.open(path, 'rb'); if not f then return nil end
    local s = f:read('*a'); f:close(); return s
end
local function write(path, s)
    local f = assert(io.open(path, 'wb')); f:write(s); f:close(); assert(fs.chmod(path, '600'))
end
local function command(s)
    local p = io.popen(s); if not p then return '' end
    local v = p:read('*a'); p:close(); return v:gsub('%s+$', '')
end
local function source()
    local c = uci.cursor()
    local name = (c:get('openclash', 'config', 'config_path') or ''):match('([^/]+)$') or ''
    local stem = name:gsub('%.ya?ml$', '')
    local found
    c:foreach('openclash', 'config_subscribe', function(s)
        if s.name == stem and s.enabled == '1' and not found and s['.name']:match('^[%w_]+$') then
            local url = s.address
            if type(url) == 'table' then if #url == 1 then url = url[1] else url = nil end end
            if type(url) == 'string' and #url <= 4096 and url:match('^https://[^/]+/') and not url:find('[%s%c"\\]') then
                local hash = command("uci -q get 'openclash." .. s['.name'] .. ".address' | sha256sum") :match('^(%x+)')
                if hash and #hash == 64 then found = {name=name, url=url, identity=name .. ':' .. hash} end
            end
        end
    end)
    return found
end
local function cached(src)
    local ok, v = pcall(json.decode, read(CACHE) or '')
    if ok and type(v) == 'table' and src and v.identity == src.identity then return v end
    return {}
end
local function clean()
    for _, n in ipairs({'pid', 'curl.conf', 'headers'}) do fs.unlink(LOCK .. '/' .. n) end
    fs.rmdir(LOCK)
end
local function busy()
    local st = fs.stat(LOCK); if not st then return false end
    local pid = (read(LOCK .. '/pid') or ''):match('^(%d+)$')
    if pid and (read('/proc/' .. pid .. '/cmdline') or ''):find('/usr/libexec/mudi7-subscription-info.lua', 1, true) then return true end
    if os.time() - st.mtime < 35 then return true end
    clean(); return fs.access(LOCK) and true or false
end
function M.request(force)
    local src = source(); if not src then return {success=false, error='当前配置没有可读取的 HTTPS 单一订阅'} end
    local old = cached(src)
    if busy() then return {success=true, busy=true} end
    local age = os.time() - (tonumber(old.attempted_at) or 0)
    if age >= 0 and age < (force and 30 or 900) then return {success=true, busy=false} end
    if not fs.mkdir(LOCK, '700') then return {success=true, busy=true} end
    local result = os.execute('umask 077; nohup lua /usr/libexec/mudi7-subscription-info.lua >/dev/null 2>&1 </dev/null &')
    if result ~= 0 and result ~= true then clean(); return {success=false, error='订阅信息刷新任务启动失败'} end
    return {success=true, busy=true}
end
function M.status()
    local src = source(); if not src then return {available=false, error='当前配置没有可读取的 HTTPS 单一订阅', refreshing=false} end
    local old = cached(src)
    M.request(false)
    local valid = type(old.upload) == 'number' and type(old.download) == 'number' and type(old.total) == 'number'
    return {available=valid, upload=old.upload, download=old.download, total=old.total,
        expire=old.expire, updated_at=old.updated_at, error=old.error or '', refreshing=busy(),
        stale=valid and (os.time() - (old.updated_at or 0) > 900 or os.time() < (old.updated_at or 0)) or false}
end
function M.run()
    local src = source()
    local old = cached(src)
    local ok, err = pcall(function()
        if not src then error('当前配置没有可读取的 HTTPS 单一订阅') end
        write(LOCK .. '/pid', tostring(require('nixio').getpid()))
        write(LOCK .. '/curl.conf', 'url = "' .. src.url .. '"\nuser-agent = "clash.meta"\n')
        local values, code
        for _, verb in ipairs({'--head', ''}) do
            code = command('curl --config ' .. LOCK .. '/curl.conf --silent --location --proto =https --proto-redir =https --max-redirs 3 --connect-timeout 5 --max-time 15 --max-filesize 4194304 ' .. verb .. ' --dump-header ' .. LOCK .. '/headers --output /dev/null --write-out "%{http_code}" 2>/dev/null')
            fs.chmod(LOCK .. '/headers', '600')
            -- Only inspect the final response block (never an earlier redirect header).
            local block = ''
            for line in ((read(LOCK .. '/headers') or '') .. '\n'):gmatch('([^\n]*)\n') do
                if line:match('^HTTP/') then block = '' else block = block .. line .. '\n' end
            end
            local header
            for line in block:gmatch('[^\r\n]+') do
                local key, v = line:match('^([^:]+):%s*(.*)$')
                if key and key:lower() == 'subscription-userinfo' then header = v end
            end
            if code == '200' and header then
                values = {}
                for key, n in header:gmatch('([%a]+)%s*=%s*(%d+)') do
                    n = tonumber(n)
                    if (key == 'upload' or key == 'download' or key == 'total' or key == 'expire') and n and n <= 9007199254740991 then values[key] = n end
                end
                if values.upload and values.download and values.total then break else values = nil end
            end
        end
        if not values then error(code == '200' and '订阅服务未提供完整流量信息' or '无法取得订阅信息，请稍后重试') end
        values.identity = src.identity
        values.updated_at = os.time(); values.attempted_at = values.updated_at; values.error = ''
        write(CACHE .. '.new', json.encode(values)); assert(fs.rename(CACHE .. '.new', CACHE))
    end)
    if not ok and src then
        old.identity = src.identity; old.attempted_at = os.time()
        -- Do not leak exceptions, URLs, response bodies or curl error text.
        old.error = tostring(err):match('订阅服务未提供完整流量信息') or '无法取得订阅信息，请稍后重试'
        pcall(write, CACHE .. '.new', json.encode(old)); fs.rename(CACHE .. '.new', CACHE)
    end
    clean()
end
return M
