#!/bin/bash
# Linux云电脑一键保活脚本
# 运行一次即可，用screen+nohup实现持久化，容器重启后也能自动恢复

WORKDIR=~/attivo-collab
INSTANCE="${1:-开发助手}"
TAGS="${2:-代码开发,重构,bug修复,脚本优化}"

echo "========================================"
echo " Linux云电脑一键保活配置"
echo " 实例: $INSTANCE"
echo " 标签: $TAGS"
echo "========================================"

cd "$WORKDIR" || { echo "错误: 工作目录不存在"; exit 1; }

# 1. 创建保活脚本（循环检查，daemon死了就重启）
cat > keepalive.sh << 'EOF'
#!/bin/bash
WORKDIR=~/attivo-collab
INSTANCE="开发助手"
TAGS="代码开发,重构,bug修复,脚本优化"
cd "$WORKDIR"
while true; do
    if ! pgrep -f "daemon.py --instance $INSTANCE" > /dev/null 2>&1; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] daemon未运行，启动中..." >> "$WORKDIR/keepalive.log"
        nohup python3 daemon.py --instance "$INSTANCE" --tags "$TAGS" --interval 300 >> "$WORKDIR/daemon.log" 2>&1 &
        sleep 5
    fi
    sleep 60
done
EOF
chmod +x keepalive.sh

# 替换实例名和标签
sed -i "s/INSTANCE=\"开发助手\"/INSTANCE=\"$INSTANCE\"/" keepalive.sh
sed -i "s/TAGS=\"代码开发,重构,bug修复,脚本优化\"/TAGS=\"$TAGS\"/" keepalive.sh

# 2. 用screen启动保活脚本（screen比nohup更持久）
if command -v screen &> /dev/null; then
    screen -dmS attivo_keepalive bash keepalive.sh
    echo "[成功] 保活脚本已在screen会话中运行: attivo_keepalive"
elif command -v tmux &> /dev/null; then
    tmux new-session -d -s attivo_keepalive "bash keepalive.sh"
    echo "[成功] 保活脚本已在tmux会话中运行: attivo_keepalive"
else
    # 没有screen/tmux，用nohup+setsid
    setsid nohup bash keepalive.sh > /dev/null 2>&1 &
    echo "[成功] 保活脚本已用setsid nohup启动"
fi

# 3. 立即启动daemon
sleep 3
if pgrep -f "daemon.py --instance $INSTANCE" > /dev/null 2>&1; then
    echo "[成功] daemon已启动，保活脚本每60秒检查一次"
    echo "以后daemon崩溃会自动重启，无需手动操作"
else
    echo "[警告] daemon启动中，请稍等几秒后检查: pgrep -f daemon.py"
fi

echo ""
echo "查看状态: pgrep -af daemon.py"
echo "查看日志: tail -f $WORKDIR/daemon.log"
