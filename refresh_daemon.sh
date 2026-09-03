#!/bin/bash
# ============================================================
# daemon token 刷新重启脚本（由【云电脑平台定时任务】每 20 分钟调用）
#
# 背景：lark-cli 的 user token 由豆包平台通过环境变量
#   DOUBAO_OFFICE_USER_ACCESS_TOKEN 注入到每个新shell，约2小时过期；
#   setsid nohup 后台常驻 daemon 只继承启动那一刻的旧token，
#   过期后任务认领/完成全部 token_invalid（心跳走GitHub不受影响）。
# 解法：平台定时任务在全新shell跑本脚本 -> 新shell带最新token，
#   杀掉旧daemon、用新token重启，daemon便永远不过期。
#
# 已修坑（云电脑实测反馈）：
#   1. 不用 pkill -f daemon.py（会匹配并误杀执行命令的bash自身,exit143），
#      改为遍历pgrep结果、只杀 /proc/<pid>/comm 为 python* 的进程。
#   2. 自动探测真实部署目录（不写死 ~/attivo-collab）。
#   3. 按实例名补全 --tags。
#
# 用法: bash refresh_daemon.sh "实例名"
# ============================================================

INSTANCE="${1:-开发助手}"
RAW="https://raw.githubusercontent.com/han20040706never-dev/attivo-oem-crawler/main"

echo "=== refresh_daemon [$INSTANCE] $(date '+%F %T') ==="
[ -n "$DOUBAO_OFFICE_USER_ACCESS_TOKEN" ] && echo "新shell已注入token(长度${#DOUBAO_OFFICE_USER_ACCESS_TOKEN})" || echo "WARN: 未检测到token环境变量"

# ---- 精确找出真正的 daemon python 进程（排除bash/sh自身）----
daemon_pids() {
  for p in $(pgrep -f "daemon.py" 2>/dev/null); do
    c="$(cat /proc/$p/comm 2>/dev/null)"
    case "$c" in python*) echo "$p" ;; esac
  done
}

# ---- 自动定位部署目录：脚本所在目录优先，再找常见候选 ----
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
DIR=""
for d in "$SELF_DIR" "$HOME/attivo-collab" "$HOME/.super_doubao/super-doubao-runtime/workspace/attivo-collab" "$(pwd)"; do
  [ -f "$d/daemon.py" ] && DIR="$d" && break
done
[ -z "$DIR" ] && DIR="$SELF_DIR"
mkdir -p "$DIR"; cd "$DIR" || { echo "FAIL 无法进入 $DIR"; exit 1; }
echo "部署目录: $DIR"

# ---- 按实例名映射标签 ----
case "$INSTANCE" in
  "开发助手") TAGS="代码开发,重构,bug修复,脚本优化" ;;
  *价格监控*)  TAGS="价格监控,公开信息调研,数据整理" ;;
  *爬虫*)      TAGS="爬虫,数据整理,配件查询" ;;
  *)           TAGS="" ;;
esac

# 1) daemon 在跑时，仅当【空闲】才重启，避免打断正在执行的任务（最长5分钟）
PIDS="$(daemon_pids)"
if [ -n "$PIDS" ]; then
    BUSY=$(python3 -c "
import json,datetime,sys
try:
    s=json.load(open('$DIR/_busy.json'))
    if s.get('busy'):
        t=datetime.datetime.fromisoformat(s.get('since',''))
        if datetime.datetime.now()-t < datetime.timedelta(minutes=5):
            print('1'); sys.exit()
    print('0')
except Exception:
    print('0')
" 2>/dev/null)
    if [ "$BUSY" = "1" ]; then
        echo "daemon 正在执行任务(_busy.json)，跳过本次刷新，下轮再换token"
        exit 0
    fi
    echo "daemon 空闲，精确杀掉旧python进程(PID:$PIDS)..."
    for p in $PIDS; do kill "$p" 2>/dev/null; done
    sleep 3
    for p in $(daemon_pids); do kill -9 "$p" 2>/dev/null; done
fi

# 2) 拉最新核心代码（失败用本地版本，不阻塞）
python3 -c "
import requests
for f in ['daemon.py','sharedtask.py','common.py','shared_mem.py','check_done.py']:
    try:
        r=requests.get('$RAW/'+f,timeout=20)
        if r.status_code==200: open(f,'wb').write(r.content)
    except Exception: pass
" 2>/dev/null
echo "代码已同步到最新"

# 3) 前置检查
[ -f config.py ] || { echo "FAIL: config.py 缺失(目录是否正确?)"; ls -la; exit 1; }
python3 -m py_compile daemon.py 2>/tmp/ce || { echo "FAIL daemon语法错误:"; cat /tmp/ce; exit 1; }

# 4) 用当前 shell（含最新token环境变量）脱离会话启动，补全参数
TAG_ARG=""; [ -n "$TAGS" ] && TAG_ARG="--tags $TAGS"
setsid nohup python3 daemon.py --instance "$INSTANCE" $TAG_ARG --interval 300 >/tmp/daemon.log 2>&1 &
sleep 4

NEWPIDS="$(daemon_pids)"
if [ -n "$NEWPIDS" ]; then
    echo "OK token刷新重启成功 PID:$NEWPIDS tags:[$TAGS]"
    exit 0
else
    echo "FAIL 重启失败，daemon.log尾部:"; tail -15 /tmp/daemon.log 2>/dev/null
    exit 1
fi
