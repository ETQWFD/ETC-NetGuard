#!/bin/sh
# ETC NetGuard Linux launcher.
# The app must run as root: it writes /etc/hosts and binds 127.0.0.1:80.
BIN=/usr/lib/etc-netguard/etc-netguard-bin

if [ "$(id -u)" -eq 0 ]; then
    export XDG_CONFIG_HOME="${ETC_CONFIG_HOME:-/var/lib/etc-netguard}"
    exec "$BIN" "$@"
fi

if command -v pkexec >/dev/null 2>&1; then
    # launch-root.sh sets the system config directory and then execs the app.
    # The polkit action carries allow_gui=true, so DISPLAY/XAUTHORITY survive
    # the privilege transition on X11 desktops.
    exec pkexec /usr/lib/etc-netguard/launch-root.sh "$@"
fi

echo "ETC NetGuard 需要管理员权限来修改 hosts 和绑定 80 端口。" >&2
echo "请用: sudo etc-netguard" >&2
exit 1
