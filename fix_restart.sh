#!/bin/bash
# 一键修复：杀掉旧daemon，保活脚本自动重启，重启后加载global bug修复
# 用法：curl -s https://raw.githubusercontent.com/han20040706never-dev/attivo-oem-crawler/main/fix_restart.sh | bash

echo "=== 一键修复启动 ==="
cd ~/attivo-collab 2>/dev/null || cd /root/attivo-collab 2>/dev/null || { echo "找不到attivo-collab目录"; exit 1; }

echo "1. 杀掉旧daemon进程..."
pkill -f "daemon.py" 2>/dev/null
sleep 3

echo "2. 确认进程已杀..."
if pgrep -f "daemon.py" > /dev/null; then
    echo "   还有残留，强杀..."
    pkill -9 -f "daemon.py"
    sleep 2
fi

echo "3. 拉取最新代码..."
python3 -c "
import requests, os
files = ['daemon.py', 'sharedtask.py', 'common.py', 'health.py', 'auto_dispatch.py']
for f in files:
    try:
        r = requests.get(f'https://raw.githubusercontent.com/han20040706never-dev/attivo-oem-crawler/main/{f}', timeout=30)
        if r.status_code == 200:
            open(f, 'wb').write(r.content)
            print(f'   {f} OK')
    except Exception as e:
        print(f'   {f} 失败: {e}')
" 2>&1

echo "4. 验证daemon.py语法..."
python3 -m py_compile daemon.py && echo "   语法OK" || echo "   语法错误!"

echo "5. 启动daemon（保活脚本会接管）..."
INSTANCE_NAME=$(grep -oP 'DAEMON_INSTANCE=\K.*' .env 2>/dev/null || echo "")
if [ -z "$INSTANCE_NAME" ]; then
    # 从supervisord或启动脚本中推断
    INSTANCE_NAME=$(cat supervisord.conf 2>/dev/null | grep -oP 'environment=DAEMON_INSTANCE="\K[^"]+' || echo "开发助手")
fi
echo "   实例名: $INSTANCE_NAME"

# 后台启动
nohup python3 daemon.py --instance "$INSTANCE_NAME" --tags "代码开发,重构,bug修复,脚本优化" --interval 300 > /tmp/daemon.log 2>&1 &
sleep 3

if pgrep -f "daemon.py" > /dev/null; then
    echo "   daemon已启动 (PID $(pgrep -f daemon.py | head -1))"
else
    echo "   启动失败，查看日志:"
    tail -20 /tmp/daemon.log
fi

echo "=== 修复完成，5分钟内心跳会更新 ==="
