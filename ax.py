# -*- coding: utf-8 -*-
"""
统一工作流入口 - 所有操作走这里，强制省token模式
用法: python ax.py <command> [args]

查询类:
  query <model> <domain_json> [fields] [limit]  - 查Odoo
  part <关键词>                                  - 查配件库（本地零token）
  stock <编号>                                   - 查attivox官网实时库存（零token）
  customer <名字>                                - 查客户
  sales [月份]                                   - 销售数据

AI类（不占豆包token）:
  ai <prompt>                                    - 调免费AI处理
  think <问题>                                   - 让DeepSeek思考复杂问题
  summarize <文件路径> [指令]                    - 总结文件
  fetch <url> [关键词]                           - 抓网页+AI总结

操作类:
  sync                                           - 同步商机备注到联系人
  demand <编号> <描述> <客户> [...]              - 填中国大陆需求清单（自动查库存）
  expense <发票文件夹>                           - 创建报销草稿
  newlead <名称> [--tag X] [--source X]         - 新建线索（自动解析省份城市）
  toll <文件夹> [--dry-run]                       - 通行费报销一条龙(PDF+付款+小程序截图)
  tag <ID1,ID2,...> <标签名>                     - 批量打标签
  source <ID1,ID2,...> <来源名>                  - 批量设来源
  checktags                                      - 检查缺标签/来源的记录
  opp <关键词>                                   - 搜索名下商机/线索
  transcribe <音频文件或文件夹> [base/small/medium] - 本地转写+AI总结
  summarize-rec <transcript.txt> [联系人名]      - DeepSeek出录音总结初稿（省token）
  crossref <编号> [编号2...]                     - 爬megazip查互换款
  cardphone <名片截图或文件夹>                    - 本地OCR提微信名片手机号(零token零风险)
  setphone <ID> <手机号> | --cards cards.json    - 补线索/商机+联系人手机号(默认预览,--apply写入)
  status                                         - 查看系统状态
  agent "任务"                                   - 智能路由（NLP→免费API/代码→dsh agent/业务→豆包）

所有命令只输出结果，不输出过程。
"""
import sys, os, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def cmd_query(args):
    from odoo.client import OdooClient
    from config import ODOO_URL, ODOO_DB, ODOO_UID, ODOO_PWD
    if len(args) < 2:
        print("用法: ax query <model> <domain_json> [fields] [limit]")
        return
    model, domain = args[0], json.loads(args[1])
    fields = args[2].split(",") if len(args) > 2 else ["id", "name"]
    limit = int(args[3]) if len(args) > 3 else 20
    odoo = OdooClient(ODOO_URL, ODOO_DB, ODOO_UID, ODOO_PWD)
    rows = odoo.search_read(model, domain, fields, limit=limit)
    for row in rows:
        print(" | ".join(str(row.get(f, ""))[:60] for f in fields))
    print(f"[{len(rows)}条]")

def cmd_part(args):
    if not args:
        print("用法: ax part <关键词>")
        return
    kw = " ".join(args).lower().replace("-", "").replace(" ", "")
    def norm(s):
        return str(s).lower().replace("-", "").replace(" ", "")
    # yamamotor
    try:
        with open("yamamotor_parts.json", encoding="utf-8") as f:
            data = json.load(f)
        parts = data.get("products", data) if isinstance(data, dict) else data
        hits = []
        for p in parts:
            if not isinstance(p, dict): continue
            blob = norm(p.get("part_no","") + p.get("category","") + p.get("remark","") + p.get("brand",""))
            if kw in blob:
                hits.append(p)
        for p in hits[:15]:
            print(f"{p.get('part_no','')} | {p.get('brand','')} | {p.get('category','')} | {p.get('remark','')[:50]}")
        print(f"[yamamotor {len(hits)}条]")
    except Exception as e:
        print(f"yamamotor: {e}")
    # shop
    try:
        with open("shop_products.json", encoding="utf-8") as f:
            shop = json.load(f)
        sp = shop.get("products", shop) if isinstance(shop, dict) else shop
        hits2 = []
        for p in sp:
            if not isinstance(p, dict): continue
            blob = norm(p.get("title","") + p.get("sku","") + str(p.get("categories","")))
            if kw in blob:
                hits2.append(p)
        for p in hits2[:10]:
            print(f"{p.get('sku','')} | {p.get('title','')[:60]}")
        print(f"[shop {len(hits2)}条]")
    except Exception:
        pass

def cmd_customer(args):
    from odoo.client import OdooClient
    from config import ODOO_URL, ODOO_DB, ODOO_UID, ODOO_PWD
    if not args:
        print("用法: ax customer <名字>")
        return
    name = " ".join(args)
    odoo = OdooClient(ODOO_URL, ODOO_DB, ODOO_UID, ODOO_PWD)
    ids = odoo.name_search("res.partner", name)
    if not ids:
        print("未找到")
        return
    rows = odoo.read("res.partner", [i[0] for i in ids[:10]],
                     ["id", "name", "phone", "mobile", "city", "comment", "category_id"])
    for r in rows:
        tags = ", ".join(t[1] for t in (r.get("category_id") or []))
        print(f"ID:{r['id']} | {r.get('name','')} | {r.get('city','')} | {r.get('phone','')} | 标签:{tags}")
        c = (r.get("comment") or "")[:100]
        if c:
            print(f"  备注: {c}")

def cmd_sales(args):
    """销售数据概览"""
    from odoo.client import OdooClient
    from config import ODOO_URL, ODOO_DB, ODOO_UID, ODOO_PWD
    odoo = OdooClient(ODOO_URL, ODOO_DB, ODOO_UID, ODOO_PWD)
    # 查已确认销售订单
    orders = odoo.search_read("sale.order",
        [["state","in",["sale","done"]]],
        ["id", "name", "partner_id", "amount_total", "date_order", "user_id"],
        limit=500)
    from collections import defaultdict
    by_month = defaultdict(float)
    by_user = defaultdict(float)
    for o in orders:
        m = str(o.get("date_order",""))[:7]
        by_month[m] += o.get("amount_total", 0)
        u = (o.get("user_id") or ["","未知"])[1] if isinstance(o.get("user_id"), list) else "未知"
        by_user[u] += o.get("amount_total", 0)
    print("=== 按月销售额 ===")
    for m in sorted(by_month):
        print(f"  {m}: ¥{by_month[m]:,.0f}")
    print("=== 按业务员 ===")
    for u, a in sorted(by_user.items(), key=lambda x: -x[1]):
        print(f"  {u}: ¥{a:,.0f}")
    print(f"[共{len(orders)}单]")

def _parse_out(args):
    """从参数中提取--out文件，返回(real_args, out_file)"""
    out_file = None
    real_args = []
    i = 0
    while i < len(args):
        if args[i] == "--out" and i+1 < len(args):
            out_file = args[i+1]; i += 2
        elif args[i].startswith("--out="):
            out_file = args[i].split("=", 1)[1]; i += 1
        else:
            real_args.append(args[i]); i += 1
    return real_args, out_file

def _ai_output(result, out_file):
    """AI结果输出：--out写文件只打印OK，否则打印全文"""
    if not result:
        print("(无结果)"); return
    if out_file:
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"OK -> {out_file} ({len(result)}字)")
    else:
        print(result)

def cmd_ai(args):
    from ai_router import chat
    real_args, out_file = _parse_out(args)
    if not real_args:
        print("用法: ax ai <prompt> [--out 文件]"); return
    r = chat(" ".join(real_args), max_tokens=4096)
    _ai_output(r, out_file)

def cmd_think(args):
    from ai_router import code_helper
    real_args, out_file = _parse_out(args)
    if not real_args:
        print("用法: ax think <问题> [--out 文件]"); return
    r = code_helper(" ".join(real_args), max_tokens=4096)
    _ai_output(r, out_file)

def cmd_summarize(args):
    from ai_router import summarize
    real_args, out_file = _parse_out(args)
    if not real_args:
        print("用法: ax summarize <文件路径> [指令] [--out 文件]"); return
    path = real_args[0]
    instr = " ".join(real_args[1:]) if len(real_args) > 1 else "总结要点"
    if not os.path.exists(path):
        print(f"文件不存在: {path}"); return
    with open(path, encoding="utf-8", errors="ignore") as f:
        text = f.read()[:30000]
    r = summarize(text, instr)
    _ai_output(r, out_file)

def cmd_fetch(args):
    import requests
    from ai_router import chat, summarize
    real_args, out_file = _parse_out(args)
    if not real_args:
        print("用法: ax fetch <url> [关键词] [--out 文件]"); return
    url, query = real_args[0], " ".join(real_args[1:])
    try:
        r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        text = r.text[:30000]
        if query:
            result = chat(f"从以下网页提取关于「{query}」的信息，简洁回答：\n\n{text}", max_tokens=2048)
        else:
            result = summarize(text, "总结核心内容")
        _ai_output(result, out_file)
    except Exception as e:
        print(f"失败: {e}")

def cmd_sync(args):
    import subprocess
    r = subprocess.run([sys.executable, "sync_leads.py"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    out = (r.stdout or "").strip().split("\n")
    print("\n".join(out[-10:]))
    if r.returncode != 0:
        print(f"[exit {r.returncode}]")

def cmd_expense(args):
    if not args:
        print("用法: ax expense <发票文件夹>")
        return
    import subprocess
    folder = args[0]
    env = os.environ.copy()
    env["EXPENSE_FOLDER"] = folder
    r = subprocess.run([sys.executable, "create_expense.py", folder], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=120)
    out = (r.stdout or "").strip().split("\n")
    print("\n".join(out[-15:]))

def cmd_toll(args):
    """通行费报销一条龙：PDF发票+付款记录+高速小程序截图 -> 草稿（防重复，可重跑）"""
    if not args:
        print("用法: ax toll <发票文件夹> [--dry-run]")
        return
    import subprocess
    folder = args[0]
    extra = args[1:]
    r = subprocess.run([sys.executable, "toll.py", folder] + extra, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=600)
    print((r.stdout or "").strip())
    if r.returncode != 0:
        print((r.stderr or "").strip()[-600:])

def cmd_oem(args):
    """零token本地配件查询: ax oem --brand yamaha --hp 115 --keyword 齿轮"""
    import subprocess
    r = subprocess.run([sys.executable, "oem_query.py"] + args, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=60)
    print((r.stdout or "").strip()); print((r.stderr or "").strip()[-300:])

def cmd_nophone(args):
    """陈国标签线/商机缺手机号清单 -> 缺手机号清单.md"""
    import subprocess
    out = args[0] if args else "缺手机号清单.md"
    r = subprocess.run([sys.executable, "nophone.py", out], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=300)
    print((r.stdout or "").strip()); print((r.stderr or "").strip()[-300:])

def cmd_task(args):
    """豆包Agent共享任务库(飞书多维表格): push/pending/done/all/set"""
    import subprocess
    if not args:
        print("用法: ax task push|pending|done|all|set ...  (见 sharedtask.py)")
        return
    r = subprocess.run([sys.executable, "sharedtask.py"] + args, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=180)
    print((r.stdout or "").strip())
    if r.returncode != 0:
        print((r.stderr or "").strip()[-500:])

def cmd_stock(args):
    """查attivox官网实时库存"""
    if not args:
        print("用法: ax stock <编号> [编号2 ...]")
        return
    from add_demand import check_part
    for pn in args:
        stock, name = check_part(pn)
        print(f"{pn}: {stock}")

def cmd_demand(args):
    """填中国大陆需求清单"""
    if len(args) < 3 or len(args) % 3 != 0:
        print("用法: ax demand <编号> <描述> <客户> [编号2 描述2 客户2 ...]")
        print("  编号可用/分隔多个，如 68V-45560-00/68V-45571-00")
        return
    import subprocess
    r = subprocess.run([sys.executable, "add_demand.py"] + args,
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    print(r.stdout.strip())
    if r.returncode != 0:
        print(r.stderr.strip()[-500:])

def cmd_summarize_rec(args):
    """已废弃: 录音总结必须豆包亲自做，用 visit_pipeline.py asr/append"""
    print("已废弃: 录音总结必须豆包亲自读转写文本后写。用 visit_pipeline.py:")
    print("  python visit_pipeline.py asr <音频> [名称]")
    print("  python visit_pipeline.py append crm.lead <id> <总结.html> --title <关键词>")

def cmd_crossref(args):
    """爬megazip查互换款"""
    if not args:
        print("用法: ax crossref <编号> [编号2...] | --file parts.txt | --all")
        return
    import subprocess
    cmd = [sys.executable, "crawl_crossref.py"] + args
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=600)
    print(r.stdout.strip()[-2000:])
    if r.returncode != 0:
        print(r.stderr.strip()[-500:])

def cmd_clean(args):
    """清理_前缀临时文件和__pycache__"""
    import glob, shutil
    removed = 0
    for f in glob.glob(os.path.join(BASE, "_*")):
        if os.path.isfile(f):
            os.remove(f); removed += 1
    for d in glob.glob(os.path.join(BASE, "**", "__pycache__"), recursive=True):
        shutil.rmtree(d, ignore_errors=True); removed += 1
    print(f"已清理 {removed} 个临时文件/目录")

def cmd_status(args):
    from ai_router import available_providers, stats
    print("AI providers:", available_providers())
    print("AI usage:", stats())
    # 代理状态
    import requests
    try:
        r = requests.get("https://www.google.com", proxies={"http":"http://127.0.0.1:7890","https":"http://127.0.0.1:7890"}, timeout=5)
        print("代理(7890): OK" if r.status_code == 200 else "代理: 异常")
    except Exception:
        print("代理(7890): 未运行")
    # Odoo状态
    try:
        from odoo.client import OdooClient
        from config import ODOO_URL, ODOO_DB, ODOO_UID, ODOO_PWD
        odoo = OdooClient(ODOO_URL, ODOO_DB, ODOO_UID, ODOO_PWD)
        n = odoo.call("crm.lead", "search_count", [])
        print(f"Odoo: OK (商机总数{n})")
    except Exception as e:
        print(f"Odoo: {e}")

def cmd_transcribe(args):
    import subprocess
    if not args:
        print("用法: ax transcribe <音频文件或文件夹> [base/small/medium]")
        return
    cmd = [sys.executable, "transcribe.py", args[0]]
    if len(args) > 1:
        cmd.append(args[1])
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=600)
    out = (r.stdout or "").strip().split("\n")
    print("\n".join(out[-30:]))

def cmd_newlead(args):
    from crm_ops import cmd_newlead as _cmd
    _cmd(args)

def cmd_fixleads(args):
    from crm_ops import cmd_fixleads as _cmd
    _cmd(args)

def cmd_note(args):
    from crm_ops import cmd_note as _cmd
    _cmd(args)

def cmd_pricelist(args):
    from crm_ops import cmd_pricelist as _cmd
    _cmd(args)

def cmd_tag(args):
    from crm_ops import cmd_tag as _cmd
    _cmd(args)

def cmd_source(args):
    from crm_ops import cmd_source as _cmd
    _cmd(args)

def cmd_checktags(args):
    from crm_ops import cmd_checktags as _cmd
    _cmd(args)

def cmd_opp(args):
    from crm_ops import cmd_opp as _cmd
    _cmd(args)

def cmd_close(args):
    from crm_ops import cmd_close as _cmd
    _cmd(args)

def cmd_setphone(args):
    from crm_ops import cmd_setphone as _cmd
    _cmd(args)

def cmd_cardphone(args):
    """名片截图本地OCR提手机号（零token零风险）"""
    if not args:
        print("用法: ax cardphone <图片或文件夹> [--out cards.json]")
        return
    import subprocess
    r = subprocess.run([sys.executable, "card_ocr.py"] + args,
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=300)
    print(r.stdout.strip())
    if r.returncode != 0:
        print(r.stderr.strip()[-500:])

def cmd_agent(args):
    """智能路由: ax agent "任务" 自动选执行器（NLP→免费API / 代码→dsh agent / 业务→提示豆包）"""
    import subprocess
    if not args:
        print("用法: ax agent \"任务描述\""); return
    task = " ".join(args)
    BASE = os.path.dirname(os.path.abspath(__file__))

    # 1. 关键词分类（零token）
    t = task.lower()
    biz_kw = ['odoo','报销','录音','erp','crm','发票','审批','库存','采购','销售订单','线索','商机','联系人','价格表','通行费']
    code_kw = ['写脚本','写代码','开发','debug','调试','爬虫','抓取','自动化','脚本','函数','api','接口','数据库','sql','python','重构','修复bug','报错','异常','优化代码','工具']
    nlp_kw = ['分类','提取','摘要','翻译','情感','关键词','命名实体','改写','润色','总结']
    if any(k in t for k in biz_kw):
        print(f"[业务操作] {task[:50]}... → 此类任务涉及业务系统，豆包亲自处理不外包")
        return
    code_score = sum(1 for k in code_kw if k in t)
    nlp_score = sum(1 for k in nlp_kw if k in t)

    # 2. NLP任务 → 免费API
    if nlp_score > 0 and code_score == 0:
        from ai_router import chat
        print(f"[NLP→免费API] {task[:50]}...")
        try:
            r = chat(task, max_tokens=2048)
            print(r if r else "(无结果)")
        except Exception as e:
            print(f"FAIL: {e}")
        return

    # 3. 代码任务 → dsh官方agent → 自研ds → DeepSeek单轮（三级兜底）
    print(f"[代码→dsh agent] {task[:50]}...")
    dsh_bat = os.path.join(BASE, "dsh24.bat")
    # 3.1 dsh官方agent
    if os.path.exists(dsh_bat):
        try:
            r = subprocess.run([dsh_bat, "--profile", "headless", task],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=180, cwd=BASE,
                               env={**os.environ, "DSH_HOME": os.path.expanduser("~/.dsh")})
            out = (r.stdout or "").strip()
            if r.returncode == 0 and out:
                print(out[-3000:]); return
            print(f"dsh失败(exit={r.returncode}): {(r.stderr or '')[-200:]}")
        except subprocess.TimeoutExpired:
            print("dsh超时(180s)")
        except Exception as e:
            print(f"dsh异常: {e}")
    else:
        print("dsh24.bat不存在，跳过")
    # 3.2 兜底1: 自研ds_harness
    print("→ 切换自研ds_harness...")
    try:
        r = subprocess.run([sys.executable, "ds_harness.py", task],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=120, cwd=BASE)
        out = (r.stdout or "").strip()
        if r.returncode == 0 and out:
            print(out[-3000:]); return
        print(f"ds_harness失败: {(r.stderr or '')[-200:]}")
    except Exception as e:
        print(f"ds_harness异常: {e}")
    # 3.3 兜底2: DeepSeek单轮
    print("→ 切换DeepSeek单轮...")
    try:
        from ai_router import code_helper
        r = code_helper(task, max_tokens=4096)
        print(r if r else "(无结果)")
    except Exception as e:
        print(f"全部失败: {e}")

def cmd_ds(args):
    """DeepSeek多轮迭代编码harness: ax ds "任务" [--file a.py] [--iter 3] [--out x.py] [--auto]"""
    if not args:
        print("用法: ax ds \"任务描述\" [--file 文件] [--iter N] [--out 输出.py] [--auto]")
        return
    import subprocess
    r = subprocess.run([sys.executable, "ds_harness.py"] + args,
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=600)
    print(r.stdout.strip())
    if r.returncode != 0:
        print(r.stderr.strip()[-500:])

def cmd_memory(args):
    """共享记忆同步: ax memory push "标题" "类型" "内容" [标签] | pull [N] | sync-github | push-github "section" "内容" """
    import subprocess
    r = subprocess.run([sys.executable, "shared_mem.py"] + args,
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=60)
    print(r.stdout.strip())
    if r.returncode != 0:
        print(r.stderr.strip()[-300:])

COMMANDS = {
    "query": cmd_query, "part": cmd_part, "stock": cmd_stock,
    "customer": cmd_customer, "sales": cmd_sales,
    "ai": cmd_ai, "think": cmd_think,
    "summarize": cmd_summarize, "fetch": cmd_fetch,
    "sync": cmd_sync, "demand": cmd_demand, "expense": cmd_expense, "toll": cmd_toll,
    "newlead": cmd_newlead, "fixleads": cmd_fixleads, "note": cmd_note,
    "pricelist": cmd_pricelist, "tag": cmd_tag, "source": cmd_source,
    "checktags": cmd_checktags, "opp": cmd_opp, "close": cmd_close,
    "setphone": cmd_setphone, "cardphone": cmd_cardphone,
    "transcribe": cmd_transcribe, "summarize-rec": cmd_summarize_rec,
    "crossref": cmd_crossref, "clean": cmd_clean, "status": cmd_status, "task": cmd_task, "nophone": cmd_nophone, "oem": cmd_oem, "ds": cmd_ds, "agent": cmd_agent, "memory": cmd_memory,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(0)
    try:
        COMMANDS[sys.argv[1]](sys.argv[2:])
    except Exception as e:
        print(f"错误: {type(e).__name__}: {e}")
