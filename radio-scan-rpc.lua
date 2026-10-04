local scanner=assert(loadfile('/etc/mudi7-management/radio-scan.lua'))()
local M={}
local function kind(args)
    if type(args)~='table' then return nil end
    for k in pairs(args) do if k~='kind' then return nil end end
    if args.kind=='wifi' or args.kind=='cellular' then return args.kind end
end
function M.get_status(args)
    local k=kind(args);if not k then return {success=false,error='仅支持 Wi-Fi 或蜂窝查询'} end
    return scanner.status(k)
end
function M.start_scan(args)
    local k=kind(args);if not k then return {success=false,error='仅支持 Wi-Fi 或蜂窝查询，不接受命令或设备参数'} end
    local ok,value=pcall(scanner.start,k)
    return ok and value or {success=false,error='扫描任务启动失败，请稍后重试'}
end
return M
