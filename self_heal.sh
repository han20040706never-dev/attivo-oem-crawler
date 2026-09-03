#!/bin/bash
# ============================================================
# daemon 自愈脚本 v2（幂等 + 自带诊断输出）
# 由【云电脑平台定时任务】每 15-20 分钟调用；也可手动执行看输出
# 用法: bash self_heal.sh "实例名"
# ============================================================

INSTANCE="${1:-开发助手}"
DIR="$HOME/attivo-collab"
RAW="https://raw.githubusercontent.com/han20040706never-dev/attivo-oem-crawler/main"

echo "=== self_heal [$INSTANCE] $(date '+%F %T') ==="

# 1) 已在运行 -> 幂等跳过
if pgrep -f "daemon.py" >/dev/null 2>&1; then
    echo "OK daemon 已在运行 PID=$(pgrep -f daemon.py | head -1)，跳过"
    exit 0
fi
echo "daemon 未运行，开始自愈..."

# 2) 目录不存在则创建
mkdir -p "$DIR"
cd "$DIR" || { echo "FAIL 无法进入 $DIR"; exit 1; }

# 3) 拉最新核心代码（python3 -c 单行，避免 heredoc 兼容问题；失败不阻塞）
python3 -c "
import requests
files=['daemon.py','sharedtask.py','common.py','shared_mem.py','check_done.py']
for f in files:
    try:
        r=requests.get('$RAW/'+f,timeout=20)
        if r.status_code==200: open(f,'wb').write(r.content)
    except Exception as e: print('  下载跳过',f,e)
" 2>&1 | grep -v "^$" || true
echo "代码拉取步骤完成"

# 4) config.py 必须存在（部署时写入，含密钥，不在 git）
if [ ! -f config.py ]; then
    echo "FAIL: $DIR/config.py 不存在，daemon 无法启动（需先部署写入密钥配置）"
    ls -la "$DIR" | head -20
    exit 1
fi
echo "config.py 存在"

# 5) daemon.py 必须存在
if [ ! -f daemon.py ]; then
    echo "FAIL: daemon.py 不存在，GitHub 下载可能失败（网络/代理问题）"
    exit 1
fi

# 6) 语法预检（避免启动即崩）
if ! python3 -m py_compile daemon.py 2>/tmp/compile_err; then
    echo "FAIL: daemon.py 语法错误:"; cat /tmp/compile_err; exit 1
fi
echo "daemon.py 语法OK"

# 7) 脱离会话启动
setsid nohup python3 daemon.py --instance "$INSTANCE" --interval 300 >/tmp/daemon.log 2>&1 &
sleep 4

# 8) 启动结果验证 + 失败诊断
if pgrep -f "daemon.py" >/dev/null 2>&1; then
    echo "OK 自愈成功 PID=$(pgrep -f daemon.py | head -1)"
    exit 0
else
    echo "FAIL daemon 启动后立即退出，daemon.log 最后15行:"
    tail -15 /tmp/daemon.log 2>/dev/null
    exit 1
fi
