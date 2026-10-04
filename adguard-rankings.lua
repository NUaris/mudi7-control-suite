-- Keep the API's existing ranking order and all other JSON bytes unchanged.
-- Do not re-encode empty arrays with this firmware's lua-cjson as empty objects.
local M={}
local function limit_field(raw,field,count)
    local _,first=raw:find('"'..field..'"%s*:%s*%[')
    if not first then return raw end
    local depth=1
    local quoted=false
    local escaped=false
    local items=1
    local cut
    for i=first+1,#raw do
        local c=raw:sub(i,i)
        if quoted then
            if escaped then escaped=false
            elseif c=='\\' then escaped=true
            elseif c=='"' then quoted=false end
        elseif c=='"' then quoted=true
        elseif c=='[' or c=='{' then depth=depth+1
        elseif c==']' or c=='}' then
            depth=depth-1
            if depth==0 then
                if cut then return raw:sub(1,cut-1)..']'..raw:sub(i+1) end
                return raw
            end
        elseif c==',' and depth==1 then
            if items==count then cut=i end
            items=items+1
        end
    end
    -- Malformed/truncated upstream response: never emit a rewritten fragment.
    return raw
end
function M.limit(raw,count)
    assert(type(raw)=='string')
    assert(type(count)=='number' and count>=1 and count%1==0)
    raw=limit_field(raw,'top_queried_domains',count)
    return limit_field(raw,'top_blocked_domains',count)
end
return M
