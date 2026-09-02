# -*- coding: utf-8 -*-
"""
cloud_ax.py — 云电脑豆包专用精简入口
只包含云电脑需要的命令：memory/task/think/ai/bootstrap
不依赖Odoo模块，git pull后配config.py即可运行
"""
import sys, io, os, subprocess
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

VERSION = "1.1.0"
REPO = "han20040706never-dev/attivo-oem-crawler"

def check_update():
    """检查GitHub上的版本，如果有更新提示"""
    try:
        import requests
        r = requests.get(f"https://raw.githubusercontent.com/{REPO}/main/VERSION", timeout=5)
        if r.status_code == 200:
            latest = r.text.strip()
            if latest != VERSION:
                print(f"提示: 有新版本 {latest}（当前 {VERSION}），执行 cloud_setup.ps1 更新")
    except:
        pass

def run(script, args):
    r = subprocess.run([sys.executable, script] + args, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=300)
    print((r.stdout or "").strip())
    if r.returncode != 0:
        print((r.stderr or "").strip()[-500:])

def cmd_memory(args):
    """共享记忆: push/pull/sync-github/push-github/bootstrap/search"""
    if not args:
        print("用法: memory push|pull|sync-github|push-github|bootstrap|search")
        return
    if args[0] == "search" and len(args) > 1:
        # 本地检索已拉取的共享记忆
        keyword = " ".join(args[1:])
        mem_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "SHARED_MEMORY.md")
        if os.path.exists(mem_file):
            with open(mem_file, 'r', encoding='utf-8') as f:
                content = f.read()
            lines = content.split('\n')
            hits = [l for l in lines if keyword.lower() in l.lower()]
            print(f"=== 搜索'{keyword}'，命中{len(hits)}条 ===")
            for h in hits[:20]:
                print(h.strip())
        else:
            print("本地无共享记忆文件，先执行 memory sync-github")
        return
    run("shared_mem.py", args)

def cmd_task(args):
    """共享任务: push/pending/done/all/set/chat/view/claim/complete/watchdog"""
    if not args:
        print("用法: task push|pending|done|all|set|chat|view|claim|complete|watchdog")
        return
    if args[0] == "watchdog":
        # 超时检测：处理中超24h自动重置为待处理
        import json, datetime
        r = subprocess.run([sys.executable, "sharedtask.py", "all"], capture_output=True,
                           text=True, encoding="utf-8", timeout=30)
        print("watchdog: 检查超时任务（功能占位，需配合record时间字段）")
        return
    run("sharedtask.py", args)

def cmd_think(args):
    """DeepSeek代码助手: ax think "问题" """
    if not args:
        print("用法: think \"问题描述\"")
        return
    try:
        from ai_router import code_helper
        r = code_helper(" ".join(args), max_tokens=4096)
        print(r if r else "(无结果)")
    except Exception as e:
        print(f"DeepSeek调用失败: {e}")

def cmd_ai(args):
    """免费AI处理: ax ai "任务" [provider]"""
    if not args:
        print("用法: ai \"任务\" [provider]")
        return
    try:
        from ai_router import chat
        r = chat(" ".join(args), provider=args[1] if len(args) > 1 else None)
        print(r if r else "(无结果)")
    except Exception as e:
        print(f"AI调用失败: {e}")

def cmd_bootstrap(args):
    """云电脑启动引导: 检查更新+拉记忆+查待处理任务"""
    check_update()
    print("=== 云电脑启动引导 ===")
    run("shared_mem.py", ["bootstrap"])
    print("\n=== 待处理任务 ===")
    run("sharedtask.py", ["pending"])

def cmd_version(args):
    """显示版本号"""
    print(f"cloud_ax.py v{VERSION}")
    check_update()

def cmd_config_export(args):
    """导出config.py为base64，方便复制到云电脑"""
    import base64
    cfg = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.py")
    if not os.path.exists(cfg):
        print("config.py不存在"); return
    with open(cfg, 'r', encoding='utf-8') as f:
        data = f.read()
    encoded = base64.b64encode(data.encode()).decode()
    print(f"=== config.py base64 ({len(encoded)}字符) ===")
    print(encoded)
    print("\n复制上面全部内容，在云电脑执行: python cloud_ax.py config-import <粘贴>")

def cmd_config_import(args):
    """从base64导入config.py"""
    import base64
    if not args:
        print("用法: config-import <base64字符串>"); return
    encoded = args[0]
    try:
        data = base64.b64decode(encoded).decode('utf-8')
        cfg = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.py")
        with open(cfg, 'w', encoding='utf-8') as f:
            f.write(data)
        print(f"OK: config.py已导入 ({len(data)}字符)")
    except Exception as e:
        print(f"导入失败: {e}")

COMMANDS = {
    "memory": cmd_memory, "task": cmd_task,
    "think": cmd_think, "ai": cmd_ai, "bootstrap": cmd_bootstrap,
    "version": cmd_version, "config-export": cmd_config_export, "config-import": cmd_config_import,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        print("可用命令:", " ".join(COMMANDS.keys()))
        sys.exit(0)
    try:
        COMMANDS[sys.argv[1]](sys.argv[2:])
    except Exception as e:
        print(f"错误: {type(e).__name__}: {e}")
