#!/bin/bash
# ============================================================
# Linux 终极保活：三层防护，一次执行永久生效
# 层1: ~/.bashrc + ~/.profile 自启（容器回收后新开shell自动恢复）
# 层2: supervisord 进程保活（daemon崩溃秒级重启）
# 层3: watchdog循环脚本（supervisord也挂了的兜底）
# 用法: curl -s https://raw.githubusercontent.com/han20040706never-dev/attivo-oem-crawler/main/linux_keepalive_ultimate.sh | bash
# ============================================================

set -e
COLLAB_DIR="$HOME/attivo-collab"
INSTANCE="开发助手"
TAGS="代码开发,重构,bug修复,脚本优化"

echo "=== Linux终极保活配置 ==="

# 确保目录存在
mkdir -p "$COLLAB_DIR"
cd "$COLLAB_DIR"

# ---------- 拉取最新代码 ----------
echo "1. 拉取最新代码..."
python3 -c "
import requests
files = ['daemon.py','sharedtask.py','common.py','health.py','auto_dispatch.py',
         'crawler_base.py','code_quality_gate.py','ds_harness.py','ai_router.py',
         'shared_mem.py','check_done.py','install_daemon_task.py']
for f in files:
    try:
        r = requests.get(f'https://raw.githubusercontent.com/han20040706never-dev/attivo-oem-crawler/main/{f}', timeout=30)
        if r.status_code == 200:
            open(f,'wb').write(r.content)
    except: pass
print('   代码拉取完成')
"

# ---------- 层1: bashrc/profile 自启 ----------
echo "2. 配置bashrc/profile自动启动..."
AUTOSTART_MARKER="# attivo-daemon-autostart"
AUTOSTART_BLOCK=$(cat <<'BLOCK'

# attivo-daemon-autostart
if ! pgrep -f "daemon.py" > /dev/null 2>&1; then
    cd ~/attivo-collab 2>/dev/null && nohup python3 daemon.py --instance "开发助手" --tags "代码开发,重构,bug修复,脚本优化" --interval 300 > /tmp/daemon.log 2>&1 &
fi
# attivo-daemon-autostart-end
BLOCK
)

for rcfile in "$HOME/.bashrc" "$HOME/.profile"; do
    touch "$rcfile"
    if ! grep -q "$AUTOSTART_MARKER" "$rcfile"; then
        echo "$AUTOSTART_BLOCK" >> "$rcfile"
        echo "   $rcfile 已添加自启"
    else
        # 替换旧的自启块
        python3 -c "
import re
with open('$rcfile','r') as f: c = f.read()
c = re.sub(r'# attivo-daemon-autostart.*?# attivo-daemon-autostart-end', '''$AUTOSTART_BLOCK''', c, flags=re.DOTALL)
with open('$rcfile','w') as f: f.write(c)
"
        echo "   $rcfile 自启已更新"
    fi
done

# ---------- 层3: watchdog循环脚本 ----------
echo "3. 创建watchdog循环脚本..."
cat > "$COLLAB_DIR/watchdog_loop.sh" <<'WDL'
#!/bin/bash
# 兜底watchdog：每60秒检查daemon，不在就启动
COLLAB=~/attivo-collab
while true; do
    if ! pgrep -f "daemon.py" > /dev/null 2>&1; then
        cd "$COLLAB"
        # 拉最新daemon.py
        python3 -c "
import requests
try:
    r = requests.get('https://raw.githubusercontent.com/han20040706never-dev/attivo-oem-crawler/main/daemon.py', timeout=30)
    if r.status_code == 200: open('daemon.py','wb').write(r.content)
except: pass
"
        nohup python3 daemon.py --instance "开发助手" --tags "代码开发,重构,bug修复,脚本优化" --interval 300 > /tmp/daemon.log 2>&1 &
        echo "$(date) daemon重启" >> /tmp/watchdog.log
    fi
    sleep 60
done
WDL
chmod +x "$COLLAB_DIR/watchdog_loop.sh"

# 杀掉旧watchdog，启动新的
pkill -f "watchdog_loop.sh" 2>/dev/null || true
sleep 1
# 用setsid确保watchdog不受终端退出影响
setsid nohup bash "$COLLAB_DIR/watchdog_loop.sh" > /tmp/watchdog_loop.log 2>&1 &
echo "   watchdog循环已启动 (PID $!)"

# ---------- 层2: supervisord ----------
echo "4. 配置supervisord..."
cat > "$COLLAB_DIR/supervisord.conf" <<SUP
[program:attivo-daemon]
command=python3 daemon.py --instance "$INSTANCE" --tags "$TAGS" --interval 300
directory=$COLLAB_DIR
autostart=true
autorestart=true
startsecs=5
stdout_logfile=/tmp/daemon_sup.log
stderr_logfile=/tmp/daemon_sup_err.log
SUP

# 杀掉旧daemon和supervisord
pkill -f "daemon.py" 2>/dev/null || true
supervisorctl shutdown 2>/dev/null || true
sleep 3

# 启动supervisord（如果可用）
if command -v supervisord &> /dev/null; then
    setsid supervisord -c "$COLLAB_DIR/supervisord.conf" 2>/dev/null || true
    echo "   supervisord已启动"
else
    # 没有supervisord，直接启动daemon（watchdog会保活）
    cd "$COLLAB_DIR"
    setsid nohup python3 daemon.py --instance "$INSTANCE" --tags "$TAGS" --interval 300 > /tmp/daemon.log 2>&1 &
    echo "   无supervisord，直接启动daemon (watchdog保活)"
fi

sleep 3

# ---------- 验证 ----------
echo "5. 验证..."
if pgrep -f "daemon.py" > /dev/null; then
    echo "   ✅ daemon运行中 (PID $(pgrep -f daemon.py | head -1))"
else
    echo "   ❌ daemon未启动，查看日志:"
    tail -10 /tmp/daemon.log 2>/dev/null || tail -10 /tmp/daemon_sup_err.log 2>/dev/null
fi

if pgrep -f "watchdog_loop.sh" > /dev/null; then
    echo "   ✅ watchdog运行中 (PID $(pgrep -f watchdog_loop | head -1))"
fi

echo ""
echo "=== 三层保活配置完成 ==="
echo "层1: bashrc/profile自启（新shell自动恢复）"
echo "层2: supervisord进程保活（崩溃秒级重启）"
echo "层3: watchdog循环兜底（60秒检查）"
echo ""
echo "建议再让云电脑豆包创建一个平台定时任务，每5分钟运行:"
echo "  bash ~/attivo-collab/watchdog_loop.sh"
echo "这样容器回收后平台定时任务会触发bashrc自启+watchdog，彻底免手动。"
