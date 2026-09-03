#!/bin/bash
# ============================================================
# daemon 自愈脚本（幂等）：daemon 在运行就退出，不在就拉最新代码并启动
# 由【云电脑平台定时任务】每 15-20 分钟调用一次 —— 这是唯一能在
# 容器被平台回收后自动恢复的机制（容器内 supervisord/watchdog 会随容器一起死）
#
# 用法: bash self_heal.sh "实例名"
#   bash self_heal.sh "开发助手"
#   bash self_heal.sh "云电脑 价格监控"
#   bash self_heal.sh "云电脑 爬虫脚本"
# ============================================================

INSTANCE="${1:-开发助手}"
DIR="$HOME/attivo-collab"
RAW="https://raw.githubusercontent.com/han20040706never-dev/attivo-oem-crawler/main"

mkdir -p "$DIR"
cd "$DIR" || exit 0

# 1) 已在运行 -> 什么都不做（幂等，绝不重复启动）
if pgrep -f "daemon.py" >/dev/null 2>&1; then
    echo "$(date '+%F %T') [$INSTANCE] daemon 已在运行(PID $(pgrep -f daemon.py | head -1))，跳过" >> /tmp/self_heal.log
    exit 0
fi

echo "$(date '+%F %T') [$INSTANCE] daemon 不在，开始自愈..." >> /tmp/self_heal.log

# 2) 拉最新核心代码（失败则用本地已有版本，不阻塞启动）
python3 - <<'PYEOF' 2>/dev/null
import requests, os
RAW = "https://raw.githubusercontent.com/han20040706never-dev/attivo-oem-crawler/main"
files = ["daemon.py", "sharedtask.py", "common.py", "shared_mem.py", "check_done.py"]
for f in files:
    try:
        r = requests.get(f"{RAW}/{f}", timeout=20)
        if r.status_code == 200:
            open(f, "wb").write(r.content)
    except Exception:
        pass
PYEOF

# 3) 确保 config.py 存在（不存在则无法启动，日志记录；config 由部署时写入，不在 git）
if [ ! -f config.py ]; then
    echo "$(date '+%F %T') [$INSTANCE] 缺 config.py，无法启动" >> /tmp/self_heal.log
    exit 1
fi

# 4) 脱离会话启动 daemon（标签不传，daemon 内置映射兜底）
setsid nohup python3 daemon.py --instance "$INSTANCE" --interval 300 >/tmp/daemon.log 2>&1 &
sleep 3

if pgrep -f "daemon.py" >/dev/null 2>&1; then
    echo "$(date '+%F %T') [$INSTANCE] 自愈成功(PID $(pgrep -f daemon.py | head -1))" >> /tmp/self_heal.log
else
    echo "$(date '+%F %T') [$INSTANCE] 自愈失败，daemon 未起来，日志尾部:" >> /tmp/self_heal.log
    tail -5 /tmp/daemon.log >> /tmp/self_heal.log 2>/dev/null
fi
