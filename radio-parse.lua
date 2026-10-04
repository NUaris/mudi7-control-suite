-- Pure parsers: no device access, commands, credentials or location lookups.
local M = {}
function M.clean(v)
    if type(v) ~= 'string' then return '' end
    local out, i, count = {}, 1, 0
    while i <= #v and count < 80 do
        local b=v:byte(i); local n=1
        if b>=194 and b<=223 then n=2 elseif b>=224 and b<=239 then n=3 elseif b>=240 and b<=244 then n=4 elseif b>=128 then n=0 end
        if n>1 then
            for j=1,n-1 do local c=v:byte(i+j); if not c or c<128 or c>191 then n=0;break end end
            local c=v:byte(i+1)
            if b==224 and c and c<160 or b==237 and c and c>159 or b==240 and c and c<144 or b==244 and c and c>143 then n=0 end
        end
        if n==0 then out[#out+1]='�';i=i+1 else out[#out+1]=(b<32 or b==127) and ' ' or v:sub(i,i+n-1);i=i+n end
        count=count+1
    end
    return table.concat(out)
end
local function num(v,lo,hi)
    v=tonumber(v); if not v or v~=v or v<lo or v>hi then return nil end;return v
end
function M.wifi(x)
    assert(type(x)=='table' and type(x.survey)=='table','invalid Wi-Fi response')
    local rows={}; local seen={}
    for _,s in ipairs(x.survey) do
        if type(s)=='table' then
            local bssid=M.clean(s.bssid):lower()
            local channel=num(s.channel,1,233)
            local freq=num(s.freq,2300,7200)
            if bssid:match('^%x%x:%x%x:%x%x:%x%x:%x%x:%x%x$') and channel and not seen[bssid] then
                seen[bssid]=true
                rows[#rows+1]={ssid=M.clean(s.ssid),bssid=bssid,channel=channel,frequency=freq,
                    band=freq and (freq>=5925 and '6 GHz' or freq>=4900 and '5 GHz' or '2.4 GHz') or M.clean(s.band),
                    signal=num(s.signal,-150,0), security=type(s.rsn)=='table' and next(s.rsn) and 'WPA2/3 (RSN)' or type(s.wpa)=='table' and next(s.wpa) and 'WPA' or '开放/未知',dfs=s.dfs==true,
                    open=type(s.caps)=='table' and s.caps.PRIVACY==false}
            end
            if #rows>=256 then break end
        end
    end
    table.sort(rows,function(a,b) local av,bv=a.signal or -999,b.signal or -999;if av==bv then return a.bssid<b.bssid end;return av>bv end)
    return rows
end
function M.csv(s)
    local fields,buf,quoted={},'',false;local i=1
    while i<=#s do
        local c=s:sub(i,i)
        if c=='"' then if quoted and s:sub(i+1,i+1)=='"' then buf=buf..'"';i=i+1 else quoted=not quoted end
        elseif c==',' and not quoted then fields[#fields+1]=buf:match('^%s*(.-)%s*$');buf=''
        else buf=buf..c end
        i=i+1
    end
    fields[#fields+1]=buf:match('^%s*(.-)%s*$');return fields
end
function M.cells(serving,neighbors,operator)
    local result={serving={},neighbors={},state='',operator=''}
    local function row(f,o,radio,idx)
        local r={radio=radio,role=o,channel=num(f[idx.channel],0,4000000),pci=num(f[idx.pci],0,1007),
            band=idx.band and num(f[idx.band],1,512) or nil,rsrp=num(f[idx.rsrp],-160,-20),
            rsrq=num(f[idx.rsrq],-50,0),sinr=num(f[idx.sinr],-30,60)}
        if r.channel and r.pci then return r end
    end
    for line in (serving or ''):gmatch('[^\r\n]+') do
        local text=line:match('^%s*%+QENG:%s*(.*)$')
        if text then
            local f=M.csv(text);local r
            if f[1]=='servingcell' then result.state=M.clean(f[2]);
                if f[3]=='LTE' then r=row(f,'服务小区','LTE',{pci=8,channel=9,band=10,rsrp=14,rsrq=15,sinr=17})
                elseif f[3]=='NR5G-SA' then r=row(f,'服务小区','NR5G-SA',{pci=8,channel=10,band=11,rsrp=13,rsrq=14,sinr=15}) end
            elseif f[1]=='LTE' then r=row(f,'LTE 锚点','LTE',{pci=6,channel=7,band=8,rsrp=12,rsrq=13,sinr=15})
            elseif f[1]=='NR5G-NSA' then r=row(f,'5G 载波','NR5G-NSA',{pci=4,channel=8,band=9,rsrp=5,rsrq=7,sinr=6}) end
            if r then result.serving[#result.serving+1]=r end
        end
    end
    local qengRows,unknown=0,0
    for line in (neighbors or ''):gmatch('[^\r\n]+') do
        local text=line:match('^%s*%+QENG:%s*(.*)$')
        if text then
            qengRows=qengRows+1;local f=M.csv(text);local r
            if (f[1]=='neighbourcell intra' or f[1]=='neighbourcell inter') and f[2]=='LTE' then
                r=row(f,f[1]=='neighbourcell intra' and '同频邻区' or '异频邻区','LTE',{channel=3,pci=4,rsrq=5,rsrp=6,sinr=8})
            end
            if r then result.neighbors[#result.neighbors+1]=r else unknown=unknown+1 end
        end
        if #result.neighbors>=128 then break end
    end
    local cops=(operator or ''):match('%+COPS:%s*([^\r\n]+)')
    if cops then local f=M.csv(cops);result.operator=M.clean(f[3]) end
    result.neighbor_note=unknown>0 and '设备返回了尚未支持解析的邻区格式，未猜测字段。' or #result.neighbors==0 and '调制解调器本次未报告可显示的 LTE 邻区；不代表周围没有基站。' or ''
    return result
end
return M
