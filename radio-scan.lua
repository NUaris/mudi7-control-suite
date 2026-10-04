-- Fixed, root-authenticated async queries. No connection/configuration changes.
local fs,json=require'nixio.fs',require'cjson'
local parse=assert(loadfile('/etc/mudi7-management/radio-parse.lua'))()
local M={};local LOCK='/tmp/mudi7-radio-scan.lock'
local function read(p) local f=io.open(p,'rb');if not f then return nil end;local s=f:read('*a');f:close();return s end
local function write(p,s) local f=assert(io.open(p,'wb'));f:write(s);f:close();assert(fs.chmod(p,'600')) end
local function decode(s) local ok,x=pcall(json.decode,s or '');if ok and type(x)=='table' then return x end;return nil end
local function command(s) local f=assert(io.popen(s));local v=f:read('*a');f:close();assert(#v<1048576,'oversized response');return v end
local function path(k) assert(k=='wifi' or k=='cellular');return '/tmp/mudi7-radio-'..k..'.json' end
local function clean() fs.unlink(LOCK..'/pid');fs.unlink(LOCK..'/kind');fs.rmdir(LOCK) end
local function active()
    local st=fs.stat(LOCK);if not st then return nil end
    local kind=(read(LOCK..'/kind') or ''):match('^(%a+)$')
    local pid=(read(LOCK..'/pid') or ''):match('^(%d+)$')
    if pid and (read('/proc/'..pid..'/cmdline') or ''):find('/usr/libexec/mudi7-',1,true) and os.time()-st.mtime<45 then return kind end
    if os.time()-st.mtime<35 then return kind or 'pending' end
    clean();return nil
end
function M.status(k)
    local value=decode(read(path(k))) or {available=false,rows={},serving={},neighbors={},error='',updated_at=0}
    local current=active();value.busy=current==k;value.active_kind=current or '';value.kind=k;return value
end
function M.start(k)
    local value=M.status(k)
    if active() then return {success=false,error='另一个无线查询正在进行，请稍候'} end
    local age=os.time()-(value.attempted_at or 0)
    if age>=0 and age<20 then return {success=false,error='请间隔 20 秒再扫描，避免重复请求'} end
    assert(fs.mkdir(LOCK,'700'),'scan lock unavailable');write(LOCK..'/kind',k)
    local status=os.execute('umask 077; nohup lua /usr/libexec/mudi7-'..(k=='wifi' and 'wifi' or 'cellular')..'-scan.lua worker >/dev/null 2>&1 </dev/null &')
    if status~=0 and status~=true then clean();return {success=false,error='扫描任务启动失败'} end
    return {success=true,busy=true}
end
function M.run(k)
    assert(active()==k,'worker lock missing')
    write(LOCK..'/pid',tostring(require'nixio'.getpid()))
    local old=decode(read(path(k))) or {}
    local ok,value=pcall(function()
        if k=='wifi' then
            local x=decode(command([[timeout 20 ubus call repeater scan '{"cached":false}' 2>/dev/null]]));assert(x,'Wi-Fi query failed')
            return {available=true,rows=parse.wifi(x),source='原厂 repeater 扫描接口'}
        end
        local modem=decode(command([[timeout 4 ubus call cellular.modem status '{"bus":"cpu"}' 2>/dev/null]])) or {}
        local slot=tonumber(modem.current_sim_slot);assert(slot==1 or slot==2,'No active SIM slot')
        local function at(cmd)
            -- Only this private function constructs fixed read-only AT requests.
            -- This modem's raw AT API uses 0 for the unqualified/current context.
            -- A UCI/UI SIM slot number is not an AT sub_id: passing slot=1 made
            -- QENG servingcell return only OK despite an available LTE cell.
            local payload=json.encode({cmd=cmd,timeout=3,source_flag=0,sub_id=0})
            assert(not payload:find("'",1,true))
            local x=decode(command("timeout 7 ubus call modem.CPU.AT get_result_AT '"..payload.."' 2>/dev/null"))
            assert(x and x.channel_status~=false and type(x.data)=='string','AT query failed');return x.data
        end
        local serving=at('AT+QENG="servingcell"')
        -- The vendor AT daemon occasionally reports only OK. Retry that missing
        -- payload twice, but do not retry a valid SEARCH/LIMSRV state or guess it.
        for attempt=1,2 do
            if serving:find('+QENG:',1,true) then break end
            serving=at('AT+QENG="servingcell"')
        end
        local neighbors=at('AT+QENG="neighbourcell"')
        local operator=at('AT+COPS?')
        local v=parse.cells(serving,neighbors,operator)
        v.available=true;v.slot=slot;v.source='Quectel QENG 服务小区/邻区查询'
        if v.state=='NOCONN' or v.state=='CONNECT' then v.registered=true
        elseif v.state=='SEARCH' or v.state=='LIMSRV' then v.registered=false end
        if #v.serving==0 then v.warning='当前 SIM 未返回有效服务小区，可能未注册、无服务或该固件未提供数据；不会显示虚构信号值。' end
        return v
    end)
    if ok then value.error='';value.updated_at=os.time();value.attempted_at=value.updated_at
    else value=old;value.error=k=='wifi' and 'Wi-Fi 扫描失败，请检查无线功能是否开启后重试。' or '蜂窝查询失败，请检查 SIM 和调制解调器状态后重试。';value.attempted_at=os.time() end
    local saved,err=pcall(function() write(path(k)..'.new',json.encode(value));assert(fs.rename(path(k)..'.new',path(k))) end)
    clean();assert(saved,err)
end
return M
