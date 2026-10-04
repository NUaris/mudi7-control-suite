#!/bin/sh
set -u
umask 077
LOCK=/tmp/mudi7-openclash.lock
RESULT=/tmp/mudi7-openclash-result.json
finished=0

finish() {
    finished=1
    MUDI7_RESULT_MESSAGE="$1" MUDI7_RESULT_ERROR="$2" lua -e 'local c=require("cjson");local p="/tmp/mudi7-openclash-result.json";local f=assert(io.open(p..".new","w"));f:write(c.encode({message=os.getenv("MUDI7_RESULT_MESSAGE"),error=os.getenv("MUDI7_RESULT_ERROR")}));f:close();assert(os.rename(p..".new",p))'
    rm -f "$LOCK/previous" "$LOCK/pid"
    rmdir "$LOCK" 2>/dev/null || true
}

proxy_ready() {
    pidof clash >/dev/null 2>&1 || return 1
    netstat -lnt 2>/dev/null | grep -Eq '[.:]7874[[:space:]]' || return 1
    nft list chain inet fw4 openclash 2>/dev/null | grep -Eq 'redirect to :[0-9]+' || return 1
    if [ "$(uci -q get openclash.config.ipv6_enable || echo 0)" = 1 ]; then
        nft list chain inet fw4 openclash_mangle_v6 2>/dev/null | grep -Eq 'tproxy ip6 to :7895' || return 1
    fi
    core_file="/etc/openclash/$(basename "$(uci -q get openclash.config.config_path)")"
    actual_dns=$(ruby -ryaml -e 'v=YAML.load_file(ARGV[0],aliases:true);print v.dig("dns","enhanced-mode")' "$core_file" 2>/dev/null)
    [ "$actual_dns" = "$(uci -q get openclash.config.operation_mode)" ] || return 1
    return 0
}

proxy_stopped() {
    pidof clash >/dev/null 2>&1 && return 1
    nft list chain inet fw4 openclash 2>/dev/null | grep -Eq 'redirect to :[0-9]+' && return 1
    nft list chain inet fw4 openclash_mangle_v6 2>/dev/null | grep -Eq 'tproxy ip6 to :7895' && return 1
    return 0
}

wait_for() {
    count=0
    stable=0
    while [ "$count" -lt 60 ]; do
        if "$1"; then stable=$((stable + 1)); else stable=0; fi
        [ "$stable" -ge 2 ] && return 0
        count=$((count + 1))
        sleep 1
    done
    return 1
}

select_global() {
    if [ "$(uci -q get openclash.config.proxy_mode || echo rule)" = global ]; then
        lua /usr/libexec/mudi7-core-global.lua
    else
        return 0
    fi
}

restore_previous() {
    [ -r "$LOCK/previous" ] && cp "$LOCK/previous" /etc/config/openclash || return 1
    if [ "$(uci -q get openclash.config.enable || echo 0)" = 1 ]; then
        /etc/init.d/openclash enable
        /etc/init.d/openclash stop
        rm -f /tmp/openclash.change
        /etc/init.d/openclash start
        wait_for proxy_ready || return 1
        select_global || return 1
    else
        /etc/init.d/openclash disable
        /etc/init.d/openclash stop
        wait_for proxy_stopped || return 1
    fi
    /usr/libexec/mudi7-dns-sync once
}

on_exit() {
    exit_status=$?
    trap - EXIT INT TERM
    if [ "$finished" != 1 ]; then
        if restore_previous; then
            finish "已恢复之前的配置" "应用过程异常结束，请查看管理日志后重试"
        else
            finish "应用过程异常结束" "恢复之前的配置未完成，请查看管理日志"
        fi
    fi
    exit "$exit_status"
}

if [ "${1:-}" != apply ] || [ ! -d "$LOCK" ]; then exit 1; fi
trap on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
echo $$ > "$LOCK/pid"
enabled=$(uci -q get openclash.config.enable || echo 0)
if [ "$enabled" = 1 ]; then
    /etc/init.d/openclash enable
    /etc/init.d/openclash stop
    rm -f /tmp/openclash.change
    /etc/init.d/openclash start
    if ! wait_for proxy_ready; then
        if restore_previous; then
            finish "已恢复之前的配置" "OpenClash 核心、DNS 或代理规则未就绪，请查看高级页面日志"
        else
            finish "配置恢复未完成" "OpenClash 未就绪且恢复失败，请查看管理日志"
        fi
        exit 1
    fi
    if ! lua /usr/libexec/mudi7-core-apply.lua; then
        if restore_previous; then
            finish "已恢复之前的配置" "代理 DNS 配置应用失败，请查看管理日志"
        else
            finish "配置恢复未完成" "代理 DNS 配置失败且恢复失败，请查看管理日志"
        fi
        exit 1
    fi
    if ! select_global; then
        if restore_previous; then
            finish "已恢复之前的配置" "全局代理出口设置失败，请查看管理日志"
        else
            finish "配置恢复未完成" "全局代理出口设置失败且恢复失败，请查看管理日志"
        fi
        exit 1
    fi
    if ! /usr/libexec/mudi7-dns-sync once; then
        finish "OpenClash 设置已保存" "DNS 链路更新失败，请查看管理日志"
        exit 1
    fi
    finish "设置已生效，OpenClash 正在运行" ""
else
    /etc/init.d/openclash disable
    /etc/init.d/openclash stop
    if ! wait_for proxy_stopped; then
        if restore_previous; then
            finish "已恢复之前的配置" "OpenClash 关闭未完成，请查看高级页面日志"
        else
            finish "配置恢复未完成" "OpenClash 关闭未完成且恢复失败，请查看管理日志"
        fi
        exit 1
    fi
    if ! /usr/libexec/mudi7-dns-sync once; then
        finish "OpenClash 已停止" "DNS 链路更新失败，请查看管理日志"
        exit 1
    fi
    finish "设置已生效，OpenClash 已关闭" ""
fi
