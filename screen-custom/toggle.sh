#!/bin/sh
# Adapted for the GL-style fork. Runtime state comes from procd, not `running`
# on rc.common (which can return true for a registered but crashed instance).
service_running() {
    ubus call service list "{\"name\":\"$1\"}" | lua -e 'local j=require"cjson";local x=j.decode(io.read("*a"));for _,s in pairs(x) do for _,i in pairs(s.instances or {}) do if i.running then os.exit(0) end end end;os.exit(1)'
}
case "$1" in
    on)
        /etc/init.d/gl_screen stop
        for pid in $(pidof gl_screen); do
            case "$(tr '\0' ' ' < /proc/$pid/cmdline 2>/dev/null)" in /usr/bin/gl_screen*) kill -KILL "$pid" 2>/dev/null;; esac
        done
        /etc/init.d/gl_screen disable
        /etc/init.d/citydash enable
        if ! /etc/init.d/citydash start; then
            /etc/init.d/citydash disable
            /etc/init.d/gl_screen enable
            /etc/init.d/gl_screen start
            exit 1
        fi
        echo 'custom screen selected (factory files retained)'
        ;;
    off)
        /etc/init.d/citydash stop
        /etc/init.d/citydash disable
        for pid in $(pidof python3); do
            case "$(tr '\0' ' ' < /proc/$pid/cmdline 2>/dev/null)" in
                'python3 /root/dashboard/main.py '*|'/usr/bin/python3 /root/dashboard/main.py '*) kill -KILL "$pid" 2>/dev/null;;
            esac
        done
        /etc/init.d/gl_screen enable
        /etc/init.d/gl_screen start
        echo 'factory screen restored'
        ;;
    status)
        if service_running citydash; then echo 'custom screen: running';else echo 'custom screen: stopped';fi
        if service_running gl_screen; then echo 'factory screen: running';else echo 'factory screen: stopped';fi
        ;;
    *) echo 'usage: toggle.sh on|off|status';exit 1;;
esac
