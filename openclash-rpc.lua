-- Authenticated by GL.iNet's existing OUI root session.
local uci = require "uci"
local fs = require "nixio.fs"
local cjson = require "cjson"
local M = {}
local LOCK = "/tmp/mudi7-openclash.lock"
local RESULT = "/tmp/mudi7-openclash-result.json"
local subscription = assert(loadfile('/etc/mudi7-management/subscription.lua'))()

local function read(path)
    local f = io.open(path, "rb")
    if not f then return nil end
    local s = f:read("*a"); f:close(); return s
end

local function write(path, data)
    local f = assert(io.open(path, "wb"))
    f:write(data); f:close()
end

local function command(cmd)
    local f = io.popen(cmd)
    if not f then return "" end
    local s = f:read("*a"); f:close()
    return s:gsub("%s+$", "")
end

local function core_version()
    local st = fs.stat('/etc/openclash/core/clash_meta')
    if not st then return '' end
    local signature = tostring(st.mtime) .. ':' .. tostring(st.size)
    local cached = read('/tmp/mudi7-openclash-version') or ''
    local previous, version = cached:match('^([^\n]+)\n([^\r\n]+)')
    if previous == signature then return version end
    -- Executing this large core solely for its version costs ~1.4 CPU seconds.
    -- Cache by binary identity instead of doing it for every status poll.
    version = command('timeout 3 /etc/openclash/core/clash_meta -v 2>/dev/null | head -n 1')
    if version ~= '' then
        pcall(function()
            write('/tmp/mudi7-openclash-version', signature .. '\n' .. version)
            fs.chmod('/tmp/mudi7-openclash-version', '600')
        end)
    end
    return version
end

local function clear_lock()
    fs.unlink(LOCK .. "/previous")
    fs.unlink(LOCK .. "/pid")
    return fs.rmdir(LOCK)
end

local function lock_busy()
    local stat = fs.stat(LOCK)
    if not stat then return false end
    local pid = (read(LOCK .. "/pid") or ""):match("^(%d+)%s*$")
    if pid then
        local cmdline = read("/proc/" .. pid .. "/cmdline") or ""
        if cmdline:find("/usr/libexec/mudi7-openclash", 1, true) then return true end
    elseif os.time() - (stat.mtime or 0) < 30 then
        -- Allow the RPC process to finish committing and the worker to start.
        return true
    end
    -- A dead worker (including a zombie) must not leave the UI permanently busy.
    pcall(write, RESULT, cjson.encode({message="上一次设置未完成", error="上一次应用进程已退出，请重新保存设置或检查日志"}))
    clear_lock()
    return fs.access(LOCK) and true or false
end

function M.get_status()
    local c = uci.cursor()
    local busy = lock_busy()
    local running = command("pidof clash 2>/dev/null") ~= ""
    local version = core_version()
    local last = {}
    local raw = read(RESULT)
    if raw then
        local ok, value = pcall(cjson.decode, raw)
        if ok and type(value) == "table" then last = value end
    end
    local enabled = c:get("openclash", "config", "enable") == "1"
    local dashboard_port = tonumber(c:get("openclash", "config", "cn_port")) or 9090
    if dashboard_port < 1 or dashboard_port > 65535 or dashboard_port % 1 ~= 0 then dashboard_port = 9090 end
    return {
        installed = fs.access("/etc/init.d/openclash") and fs.access("/etc/openclash/core/clash_meta") or false,
        enabled = enabled,
        running = running,
        boot_enabled = enabled and fs.access('/etc/rc.d/S99openclash') or false,
        mode = c:get("openclash", "config", "proxy_mode") or "rule",
        operation_mode = c:get("openclash", "config", "operation_mode") or "fake-ip",
        ipv6_enabled = c:get("openclash", "config", "ipv6_enable") == "1",
        ipv6_dns = c:get("openclash", "config", "ipv6_dns") == "1",
        core_version = version,
        config_name = (c:get("openclash", "config", "config_path") or ""):match("([^/]+)$") or "",
        dashboard_port = dashboard_port,
        dashboard_path = fs.access('/usr/share/openclash/ui/metacubexd/index.html') and '/ui/metacubexd/' or '/ui/',
        busy = busy,
        dns_chain = read("/tmp/mudi7-dns-state") or "正在检查 DNS 链路",
        last_error = last.error or "",
        last_message = last.message or "",
        subscription = subscription.status(),
    }
end

function M.refresh_subscription(args)
    if type(args) ~= 'table' or next(args) then return {success=false, error='刷新订阅信息不接受参数'} end
    return subscription.request(true)
end

function M.set_config(args)
    if type(args) ~= "table" then return {success=false, error="参数格式错误"} end
    local modes = {rule=true, global=true, direct=true}
    local dns_modes = {["fake-ip"]=true, ["redir-host"]=true}
    local permitted = {enabled=true, mode=true, operation_mode=true, ipv6_enabled=true}
    for k in pairs(args) do
        if not permitted[k] then return {success=false, error="不支持的设置参数"} end
    end
    if args.enabled ~= nil and type(args.enabled) ~= "boolean" then return {success=false, error="开关参数必须是布尔值"} end
    if args.ipv6_enabled ~= nil and type(args.ipv6_enabled) ~= "boolean" then return {success=false, error="IPv6 参数必须是布尔值"} end
    if args.mode ~= nil and not modes[args.mode] then return {success=false, error="不支持的策略模式"} end
    if args.operation_mode ~= nil and not dns_modes[args.operation_mode] then return {success=false, error="不支持的 DNS 模式"} end
    if not fs.access("/etc/init.d/openclash") or not fs.access("/etc/openclash/core/clash_meta") then
        return {success=false, error="OpenClash 或核心未安装"}
    end
    if not fs.access("/usr/libexec/mudi7-openclash", "x") then
        return {success=false, error="OpenClash 管理组件未安装完整"}
    end
    local c = uci.cursor()
    local path = c:get("openclash", "config", "config_path") or ""
    if (args.enabled == true) and not fs.access(path) then return {success=false, error="请先在高级页面导入有效配置"} end
    if lock_busy() then return {success=false, error="正在应用设置，请等待完成"} end
    if not fs.mkdir(LOCK, "700") then return {success=false, error="正在应用设置，请等待完成"} end
    local ok, err = pcall(function()
        write(LOCK .. "/previous", assert(read("/etc/config/openclash")))
        write(LOCK .. "/pid", "pending")
        write(RESULT, cjson.encode({message="正在应用设置", error=""}))
        if args.enabled ~= nil then c:set("openclash", "config", "enable", args.enabled and "1" or "0") end
        if args.mode ~= nil then c:set("openclash", "config", "proxy_mode", args.mode) end
        if args.operation_mode ~= nil then
            c:set("openclash", "config", "operation_mode", args.operation_mode)
            c:set("openclash", "config", "en_mode", args.operation_mode)
            c:set("openclash", "config", "en_mode_tun", "0")
        end
        if args.ipv6_enabled ~= nil then
            c:set("openclash", "config", "ipv6_enable", args.ipv6_enabled and "1" or "0")
            c:set("openclash", "config", "ipv6_dns", args.ipv6_enabled and "1" or "0")
        end
        c:set("openclash", "config", "ipv6_mode", "0")
        c:set("openclash", "config", "enable_v6_udp_proxy", "1")
        c:set("openclash", "config", "fakeip_range6", "fdfe:dcba:9876::1/64")
        c:set("openclash", "config", "china_ip6_route", "0")
        c:set("openclash", "config", "enable_redirect_dns", "0")
        c:set("openclash", "config", "dns_port", "7874")
        assert(c:commit("openclash"), "UCI commit failed")
        local launched = os.execute("umask 077; nohup /usr/libexec/mudi7-openclash apply >/tmp/mudi7-openclash-apply.log 2>&1 </dev/null &")
        assert(launched ~= false and (type(launched) ~= "number" or launched == 0), "Worker launch failed")
    end)
    if not ok then
        local previous = read(LOCK .. "/previous")
        if previous then pcall(write, "/etc/config/openclash", previous) end
        pcall(write, RESULT, cjson.encode({message="保存设置失败", error="保存设置失败，请重新尝试"}))
        clear_lock()
        return {success=false, error="保存设置失败"}
    end
    return {success=true, busy=true, message="已提交，正在应用设置"}
end

return M
