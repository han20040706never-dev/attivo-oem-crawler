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
    """共享记忆: push/pull/sync-github/push-github/bootstrap/search/relevant"""
    if not args:
        print("用法: memory push|pull|sync-github|push-github|bootstrap|search|relevant")
        return
    if args[0] == "search" and len(args) > 1:
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
    if args[0] == "relevant" and len(args) > 1:
        run("shared_mem.py", ["relevant"] + args[1:])
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
    """云电脑启动引导: 检查更新+拉记忆+查待处理任务+自动注入相关经验"""
    check_update()
    print("=== 云电脑启动引导 ===")
    run("shared_mem.py", ["bootstrap"])
    print("\n=== 待处理任务 ===")
    r = subprocess.run([sys.executable, "sharedtask.py", "pending"], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=30)
    print(r.stdout)
    # 自动检索相关经验：从待处理任务标题提取关键词
    import re
    titles = re.findall(r'\| ([^|]+)$', r.stdout, re.MULTILINE)
    if titles:
        # 取第一个任务标题做关键词
        first_title = titles[0].strip()
        # 提取中文词和英文词作为关键词
        keywords = " ".join(re.findall(r'[\u4e00-\u9fa5]{2,}|[a-zA-Z]{3,}', first_title))
        if keywords:
            print(f"\n=== 自动检索相关经验（关键词:{keywords}） ===")
            run("shared_mem.py", ["relevant", keywords])

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

def cmd_healthcheck(args):
    """系统健康自检：任务卡死/记忆冗余/配置/版本/API"""
    run("healthcheck.py", [])

def cmd_odoo(args):
    """Odoo只读查询: odoo customer <关键词> | odoo product <关键词> | odoo lead <关键词>
    只查不写，安全。需要config.py里有ODOO配置。
    """
    if not args or args[0] not in ("customer", "product", "lead"):
        print("用法: odoo customer|product|lead <关键词>")
        return
    model_map = {"customer": "res.partner", "product": "product.product", "lead": "crm.lead"}
    model = model_map[args[0]]
    keyword = " ".join(args[1:]) if len(args) > 1 else ""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import config
        from odoo.client import OdooClient
        client = OdooClient(config.ODOO_URL, config.ODOO_DB, config.ODOO_UID, config.ODOO_PWD)
        domain = []
        if keyword:
            if model == "res.partner":
                domain = ["|", ("name", "ilike", keyword), ("phone", "ilike", keyword)]
            elif model == "product.product":
                domain = ["|", ("name", "ilike", keyword), ("default_code", "ilike", keyword)]
            elif model == "crm.lead":
                domain = ["|", ("name", "ilike", keyword), ("contact_name", "ilike", keyword)]
        domain.append(("user_id", "=", 18))
        fields = ["name", "phone", "city"] if model == "res.partner" else \
                 ["name", "default_code", "qty_available"] if model == "product.product" else \
                 ["name", "contact_name", "phone", "city"]
        ids = client.search(model, domain, limit=20)
        if not ids:
            print("无结果"); return
        records = client.read(model, ids, fields)
        print(f"=== {args[0]}查询结果（{len(records)}条） ===")
        for r in records:
            name = r.get("name", "")
            extra = ""
            if model == "res.partner":
                extra = f" 电话:{r.get('phone','')} 城市:{r.get('city','')}"
            elif model == "product.product":
                extra = f" 编号:{r.get('default_code','')} 库存:{r.get('qty_available','')}"
            elif model == "crm.lead":
                extra = f" 联系人:{r.get('contact_name','')} 电话:{r.get('phone','')}"
            print(f"  [{r['id']}] {name}{extra}")
    except Exception as e:
        print(f"Odoo查询失败: {e}")

COMMANDS = {
    "memory": cmd_memory, "task": cmd_task,
    "think": cmd_think, "ai": cmd_ai, "bootstrap": cmd_bootstrap,
    "version": cmd_version, "config-export": cmd_config_export, "config-import": cmd_config_import,
    "healthcheck": cmd_healthcheck, "odoo": cmd_odoo,
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
