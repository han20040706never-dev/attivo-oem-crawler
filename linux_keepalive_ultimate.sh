#!/bin/bash
# ============================================================
# Linux 终极保活：三层防护，一次执行永久生效（三台云电脑通用）
# 层1: ~/.bashrc + ~/.profile 自启（容器回收后新开shell自动恢复）
# 层2: supervisord 进程保活（daemon崩溃秒级重启）
# 层3: watchdog循环脚本（60秒兜底检查）
# 用法:
#   开发助手:  bash linux_keepalive_ultimate.sh "开发助手" "代码开发,重构,bug修复,脚本优化"
#   价格监控:  bash linux_keepalive_ultimate.sh "云电脑 价格监控" "价格监控,公开信息调研,数据整理"
#   爬虫脚本:  bash linux_keepalive_ultimate.sh "云电脑 爬虫脚本" "爬虫,数据整理,配件查询"
# ============================================================

INSTANCE="${1:-开发助手}"
TAGS="${2:-代码开发,重构,bug修复,脚本优化}"
COLLAB_DIR="$HOME/attivo-collab"

echo "=== Linux终极保活: $INSTANCE ==="

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
MARKER="# attivo-daemon-autostart"
# 先清除旧的自启块，再写入新的（带正确实例名）
for rcfile in "$HOME/.bashrc" "$HOME/.profile"; do
    touch "$rcfile"
    python3 - "$rcfile" "$INSTANCE" "$TAGS" <<'PYEOF'
import sys, re
rcfile, instance, tags = sys.argv[1], sys.argv[2], sys.argv[3]
with open(rcfile, 'r') as f:
    content = f.read()
# 删除旧块
content = re.sub(r'\n?# attivo-daemon-autostart.*?# attivo-daemon-autostart-end\n?', '\n', content, flags=re.DOTALL)
# 写入新块
block = f"""
# attivo-daemon-autostart
if ! pgrep -f "daemon.py" > /dev/null 2>&1; then
    cd ~/attivo-collab 2>/dev/null && nohup python3 daemon.py --instance "{instance}" --tags "{tags}" --interval 300 > /tmp/daemon.log 2>&1 &
fi
# attivo-daemon-autostart-end
"""
content = content.rstrip() + "\n" + block
with open(rcfile, 'w') as f:
    f.write(content)
print(f"   {rcfile} 已配置")
PYEOF
done

# ---------- 层3: watchdog循环脚本 ----------
echo "3. 创建watchdog循环脚本..."
python3 - "$COLLAB_DIR/watchdog_loop.sh" "$INSTANCE" "$TAGS" <<'PYEOF'
import sys
path, instance, tags = sys.argv[1], sys.argv[2], sys.argv[3]
script = f'''#!/bin/bash
# 兜底watchdog：每60秒检查daemon，不在就启动
COLLAB=~/attivo-collab
while true; do
    if ! pgrep -f "daemon.py" > /dev/null 2>&1; then
        cd "$COLLAB"
        python3 -c "
import requests
try:
    r = requests.get('https://raw.githubusercontent.com/han20040706never-dev/attivo-oem-crawler/main/daemon.py', timeout=30)
    if r.status_code == 200: open('daemon.py','wb').write(r.content)
except: pass
"
        nohup python3 daemon.py --instance "{instance}" --tags "{tags}" --interval 300 > /tmp/daemon.log 2>&1 &
        echo "$(date) daemon重启" >> /tmp/watchdog.log
    fi
    sleep 60
done
'''
with open(path, 'w') as f:
    f.write(script)
PYEOF
chmod +x "$COLLAB_DIR/watchdog_loop.sh"

pkill -f "watchdog_loop.sh" 2>/dev/null || true
sleep 1
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

pkill -f "daemon.py" 2>/dev/null || true
supervisorctl shutdown 2>/dev/null || true
sleep 3

if command -v supervisord &> /dev/null; then
    setsid supervisord -c "$COLLAB_DIR/supervisord.conf" 2>/dev/null || true
    echo "   supervisord已启动"
else
    setsid nohup python3 daemon.py --instance "$INSTANCE" --tags "$TAGS" --interval 300 > /tmp/daemon.log 2>&1 &
    echo "   无supervisord，直接启动daemon (watchdog保活)"
fi

sleep 3

# ---------- 验证 ----------
echo "5. 验证..."
if pgrep -f "daemon.py" > /dev/null; then
    echo "   OK daemon运行中 (PID $(pgrep -f daemon.py | head -1))"
else
    echo "   FAIL daemon未启动，日志:"
    tail -10 /tmp/daemon.log 2>/dev/null || tail -10 /tmp/daemon_sup_err.log 2>/dev/null
fi
if pgrep -f "watchdog_loop.sh" > /dev/null; then
    echo "   OK watchdog运行中 (PID $(pgrep -f watchdog_loop | head -1))"
fi

echo ""
echo "=== 保活配置完成: $INSTANCE ==="
