#!/bin/sh
# Privileged entry point invoked by the polkit action.
export XDG_CONFIG_HOME="${ETC_CONFIG_HOME:-/var/lib/etc-netguard}"
exec /usr/lib/etc-netguard/etc-netguard-bin "$@"
