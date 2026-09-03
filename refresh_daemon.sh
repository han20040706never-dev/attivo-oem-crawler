#!/bin/bash
# ============================================================
# daemon token 刷新重启脚本（由【云电脑平台定时任务】每 20 分钟调用）
#
# 背景：lark-cli 的 user token 由豆包平台通过环境变量
#   DOUBAO_OFFICE_USER_ACCESS_TOKEN 注入，约 2 小时过期；
#   setsid nohup 后台常驻的 daemon 只继承启动那一刻的旧 token，
#   过期后任务认领/完成全部 token_invalid（心跳走 GitHub 不受影响）。
# 解法：平台定时任务在【全新 shell】里跑本脚本 -> 新 shell 带最新 token，
#   杀掉旧 daemon、用新 token 重启，daemon 便永远不过期。
#
# 用法: bash refresh_daemon.sh "实例名"
# ============================================================

INSTANCE="${1:-开发助手}"
DIR="$HOME/attivo-collab"
RAW="https://raw.githubusercontent.com/han20040706never-dev/attivo-oem-crawler/main"

echo "=== refresh_daemon [$INSTANCE] $(date '+%F %T') ==="

# token 是否存在（诊断用）
if [ -n "$DOUBAO_OFFICE_USER_ACCESS_TOKEN" ]; then
    echo "当前shell已注入新token(长度${#DOUBAO_OFFICE_USER_ACCESS_TOKEN})"
else
    echo "WARN: 当前shell未检测到 DOUBAO_OFFICE_USER_ACCESS_TOKEN，重启后lark仍可能失效"
fi

mkdir -p "$DIR"; cd "$DIR" || { echo "FAIL 无法进入 $DIR"; exit 1; }

# 1) daemon 在跑时，仅当【空闲】才重启，避免打断正在执行的任务（最长5分钟）
if pgrep -f "daemon.py" >/dev/null 2>&1; then
    BUSY=0
    if [ -f /tmp/daemon.log ]; then
        # 日志180秒内有更新 且 尾部出现任务执行痕迹 => 忙碌
        LOG_AGE=$(( $(date +%s) - $(stat -c %Y /tmp/daemon.log 2>/dev/null || echo 0) ))
        if [ "$LOG_AGE" -lt 180 ] && tail -25 /tmp/daemon.log 2>/dev/null | grep -qE "自动认领|自动执行|执行中|代码开发|DeepSeek"; then
            BUSY=1
        fi
    fi
    if [ "$BUSY" -eq 1 ]; then
        echo "daemon 正在执行任务（日志180秒内活跃），跳过本次刷新，下轮再换token"
        exit 0
    fi
    echo "daemon 空闲，杀掉旧进程(旧token)准备重启..."
    pkill -f "daemon.py"
    sleep 3
fi

# 2) 拉最新核心代码（失败用本地版本，不阻塞）
python3 -c "
import requests
for f in ['daemon.py','sharedtask.py','common.py','shared_mem.py','check_done.py','self_heal.sh']:
    try:
        r=requests.get('$RAW/'+f,timeout=20)
        if r.status_code==200: open(f,'wb').write(r.content)
    except Exception: pass
" 2>/dev/null
echo "代码已同步到最新"

# 3) 前置检查
[ -f config.py ] || { echo "FAIL: config.py 缺失"; exit 1; }
python3 -m py_compile daemon.py 2>/tmp/ce || { echo "FAIL daemon语法错误:"; cat /tmp/ce; exit 1; }

# 4) 用当前 shell（含最新token环境变量）脱离会话启动
setsid nohup python3 daemon.py --instance "$INSTANCE" --interval 300 >/tmp/daemon.log 2>&1 &
sleep 4

if pgrep -f "daemon.py" >/dev/null 2>&1; then
    echo "OK token刷新重启成功 PID=$(pgrep -f daemon.py | head -1)"
    exit 0
else
    echo "FAIL 重启失败，daemon.log尾部:"; tail -15 /tmp/daemon.log 2>/dev/null
    exit 1
fi
