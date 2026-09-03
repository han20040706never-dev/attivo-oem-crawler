#!/bin/bash
# ============================================================
# Linux 保活配置（简化版 v2）：只配置监控机制，绝不 pkill 当前 daemon
# 核心自愈依赖【平台定时任务】调用 self_heal.sh（容器回收后能唤醒）
# 本脚本只做双重保险：1) bashrc/profile 自启  2) watchdog 每60秒兜底
#
# 用法: bash linux_keepalive_ultimate.sh "实例名"
# ============================================================

INSTANCE="${1:-开发助手}"
# 自动探测真实部署目录（脚本所在目录优先，兼容云电脑长路径，最后才用$HOME）
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
COLLAB_DIR=""
for d in "$SELF_DIR" "$HOME/.super_doubao/super-doubao-runtime/workspace/attivo-collab" "$HOME/attivo-collab"; do
  [ -f "$d/daemon.py" ] && COLLAB_DIR="$d" && break
done
[ -z "$COLLAB_DIR" ] && COLLAB_DIR="$SELF_DIR"
RAW="https://raw.githubusercontent.com/han20040706never-dev/attivo-oem-crawler/main"

echo "=== 保活配置 v2: $INSTANCE (目录:$COLLAB_DIR) ==="
mkdir -p "$COLLAB_DIR"
cd "$COLLAB_DIR" || exit 1

# ---------- 1. 拉取最新核心代码（不重启，下次巡检 auto_update 会加载） ----------
echo "1. 拉取最新代码..."
python3 - <<'PYEOF' 2>/dev/null
import requests
RAW = "https://raw.githubusercontent.com/han20040706never-dev/attivo-oem-crawler/main"
for f in ["daemon.py","sharedtask.py","common.py","shared_mem.py","check_done.py","self_heal.sh"]:
    try:
        r = requests.get(f"{RAW}/{f}", timeout=20)
        if r.status_code == 200:
            open(f, "wb").write(r.content)
    except Exception:
        pass
print("   完成")
PYEOF

# ---------- 2. bashrc/profile 自启（容器回收后新 shell 触发） ----------
echo "2. 配置 bashrc/profile 自启..."
MARKER="# attivo-daemon-autostart"
for rcfile in "$HOME/.bashrc" "$HOME/.profile"; do
    touch "$rcfile"
    python3 - "$rcfile" "$INSTANCE" "$COLLAB_DIR" <<'PYEOF'
import sys, re
rcfile, instance, collab = sys.argv[1], sys.argv[2], sys.argv[3]
with open(rcfile) as f: content = f.read()
content = re.sub(r'\n?# attivo-daemon-autostart.*?# attivo-daemon-autostart-end\n?', '\n', content, flags=re.DOTALL)
block = f"""
# attivo-daemon-autostart
if ! pgrep -f "daemon.py" >/dev/null 2>&1; then
    cd "{collab}" 2>/dev/null && bash self_heal.sh "{instance}" >/tmp/self_heal.log 2>&1 &
fi
# attivo-daemon-autostart-end
"""
with open(rcfile, "w") as f: f.write(content.rstrip() + "\n" + block)
print(f"   {rcfile} 已配置")
PYEOF
done

# ---------- 3. watchdog 每60秒兜底（调用 self_heal.sh，幂等） ----------
echo "3. 启动 watchdog..."
cat > "$COLLAB_DIR/watchdog_loop.sh" <<WDEOF
#!/bin/bash
# 兜底 watchdog：每60秒调用 self_heal.sh（幂等，daemon 在就跳过）
while true; do
    bash "$COLLAB_DIR/self_heal.sh" "\$1" >>/tmp/watchdog.log 2>&1
    sleep 60
done
WDEOF
chmod +x "$COLLAB_DIR/watchdog_loop.sh"

# 杀掉旧 watchdog，启动新的（不碰 daemon）
pkill -f "watchdog_loop.sh" 2>/dev/null
sleep 1
setsid nohup bash "$COLLAB_DIR/watchdog_loop.sh" "$INSTANCE" >/tmp/watchdog_loop.log 2>&1 &
echo "   watchdog 已启动 (PID $!)"

# ---------- 4. 验证 ----------
echo "4. 验证..."
pgrep -f "daemon.py" >/dev/null && echo "   OK daemon 运行中 (PID $(pgrep -f daemon.py | head -1))" || echo "   ⚠ daemon 当前未运行，watchdog/平台定时任务会在60秒内拉起"
pgrep -f "watchdog_loop.sh" >/dev/null && echo "   OK watchdog 运行中" || echo "   ⚠ watchdog 未运行"

echo ""
echo "=== 保活配置完成: $INSTANCE ==="
echo "核心自愈 = 平台定时任务(每20分钟) + watchdog(每60秒) + bashrc自启(三重保险)"
