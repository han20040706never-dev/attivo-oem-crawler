#!/bin/bash
# 一键修复重启（已统一走 refresh_daemon.sh，避免多份逻辑不一致）
# 用法：bash fix_restart.sh ["实例名"]；不带实例名则自动探测或默认开发助手
RAW="https://raw.githubusercontent.com/han20040706never-dev/attivo-oem-crawler/main"

# 实例名：优先参数，其次 .env / supervisord.conf 推断，最后默认开发助手
INSTANCE="${1:-}"
if [ -z "$INSTANCE" ]; then
  INSTANCE="$(grep -oP 'DAEMON_INSTANCE=\K.*' .env 2>/dev/null | head -1)"
fi
if [ -z "$INSTANCE" ]; then
  INSTANCE="$(grep -oP 'DAEMON_INSTANCE="\K[^"]+' supervisord.conf 2>/dev/null | head -1)"
fi
[ -z "$INSTANCE" ] && INSTANCE="开发助手"

echo "=== fix_restart -> refresh_daemon [$INSTANCE] ==="
curl -sL "$RAW/refresh_daemon.sh" -o /tmp/refresh_daemon.sh
bash /tmp/refresh_daemon.sh "$INSTANCE"
