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
  route <任务描述>                               - 智能路由（同agent）
  dsedit <文件列表> -m <需求> [--apply]          - 用AI编辑文件

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

def cmd_route(args):
    """智能路由: 先零token匹配已有脚本(命中直接用不重写), 再选AI执行通道"""
    import script_match, smart, task_memory
    q = ' '.join(args)
    res = script_match.find(q)
    if res:
        print("【已有脚本】零token本地匹配, 命中就直接用不要新写:")
        for i, (sc, name, cat, usage) in enumerate(res[:3], 1):
            print(f"  {i}. [{sc:.2f}] {name}.py ({cat}) {usage[:45]}")
        if res[0][0] >= 0.2:
            print(f"  => 优先用 {res[0][1]}.py")
        print()
    hist = task_memory.recall(q)
    if hist:
        print("【历史相似任务】自学习召回:")
        for s, sc2, note, n, ts in hist:
            print(f"  [{s:.2f}|{n}次] {sc2}")
        print()
    print("【AI通道】", smart.decide(q))


def cmd_find(args):
    """智能匹配已有脚本: ax find \"任务描述\" (零token, 命中直接用不重复造轮子)"""
    import script_match
    if not args:
        print("用法: ax find \"任务描述\"  例: ax find 核一下这个Excel清单的中国仓库存")
        return
    res = script_match.find(' '.join(args))
    if not res:
        print("无匹配; 先 ax index 刷新能力地图, 确认无现成脚本再写新的")
        return
    for i, (sc, name, cat, usage) in enumerate(res, 1):
        print(f"  {i}. [{sc:.2f}] {name}.py ({cat}) {usage[:55]}")
    if res[0][0] >= 0.2:
        print(f"=> 建议直接用: {res[0][1]}.py (或 ax 对应命令), 不要新写脚本")


def cmd_did(args):
    """完成任务后沉淀方案: ax did \"任务\" \"用的脚本/ax命令\" [\"结果要点\"] (自学习, 供下次相似任务召回)"""
    import task_memory
    if len(args) < 2:
        print('用法: ax did "任务描述" "用的脚本/ax命令" ["结果要点"]')
        return
    task_memory.did(args[0], args[1], args[2] if len(args) > 2 else "")


def _auto_match(q):
    """未知命令/新任务自动匹配: 历史相似方案 + 现有脚本, 零token。"""
    import script_match, task_memory
    if not q.strip():
        print(__doc__); return
    print(f"未识别为命令, 按任务自动匹配: {q}")
    hist = task_memory.recall(q)
    if hist:
        print("【上次相似任务怎么做的】(自学习)")
        for s, sc, note, n, ts in hist:
            print(f"  [{s:.2f}|{n}次|{ts}] {sc}")
    sm = script_match.find(q)
    if sm:
        print("【可直接用的已有脚本】")
        for sc, name, cat, usage in sm[:5]:
            print(f"  [{sc:.2f}] {name}.py ({cat}) {usage[:45]}")
        if sm[0][0] >= 0.2:
            print(f"=> 优先 {sm[0][1]}.py, 别新写; 做完 ax did 沉淀")
    if not hist and not sm:
        print("无现成匹配, 确认后再写新脚本; 完成后 ax did 沉淀方案")


def cmd_recall(args):
    """召回历史相似方案+现有脚本: ax recall \"任务\" (新任务第一步)"""
    _auto_match(" ".join(args))

def cmd_dsedit(args):
    """用AI编辑文件: ax dsedit f.py -m 需求 [--apply]"""
    import smart
    files = []
    message = None
    apply = False
    i = 0
    while i < len(args):
        if args[i] in ("-m", "--message") and i+1 < len(args):
            message = args[i+1]; i += 2
        elif args[i] == "--apply":
            apply = True; i += 1
        else:
            files.append(args[i]); i += 1
    if not files or not message:
        print("用法: ax dsedit <文件列表> -m <需求> [--apply]")
        return
    smart.ds_edit(files, message, apply)

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

def cmd_collab(args):
    """协作系统统一入口: ax collab health | dispatch "任务" [--title T] | pending | instances | quality <files> | tasks
    示例: ax collab health  # 一键健康检查
          ax collab dispatch "爬取boats.net配件数据"  # 智能派发任务
          ax collab pending  # 待处理任务
          ax collab instances  # 云电脑实例状态
          ax collab quality daemon.py sharedtask.py  # 代码质量门禁
    """
    import subprocess, json, os
    PROJECT = os.path.dirname(os.path.abspath(__file__))
    if not args:
        print(cmd_collab.__doc__)
        return
    sub = args[0]
    rest = args[1:]
    if sub == "health":
        r = subprocess.run([sys.executable, "health.py"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, cwd=PROJECT)
        print(r.stdout.strip())
    elif sub == "dispatch":
        r = subprocess.run([sys.executable, "auto_dispatch.py"] + rest, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, cwd=PROJECT)
        print(r.stdout.strip())
        if r.stderr: print(r.stderr.strip()[-300:])
    elif sub == "pending":
        r = subprocess.run([sys.executable, "sharedtask.py", "pending"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30, cwd=PROJECT)
        print(r.stdout.strip())
    elif sub == "instances":
        try:
            inst = json.load(open(os.path.join(PROJECT, "instances.json"), 'r', encoding='utf-8'))
            import datetime
            now = datetime.datetime.now()
            for name, info in inst.get("instances", {}).items():
                last = info.get("last_seen", "")
                tags = info.get("tags", [])
                if isinstance(tags, str): tags = [t.strip() for t in tags.split(",")]
                status = "未知"
                if last:
                    try:
                        lt = datetime.datetime.fromisoformat(last.replace("Z", "+00:00").replace("+08:00", ""))
                        elapsed = (now - lt).total_seconds() / 60
                        status = "在线" if elapsed <= 30 else f"超时({elapsed:.0f}分钟)"
                    except: status = "心跳解析失败"
                print(f"  {name}: {status} | 完成{info.get('completed',0)} 失败{info.get('failed',0)} 进行中{info.get('active_tasks',0)} | 标签:{','.join(tags)}")
        except Exception as e:
            print(f"读取失败: {e}")
    elif sub == "quality":
        if not rest:
            print("用法: ax collab quality <file1.py> [file2.py ...] [--all]")
            return
        r = subprocess.run([sys.executable, "code_quality_gate.py"] + rest, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, cwd=PROJECT)
        print(r.stdout.strip())
    elif sub == "tasks":
        r = subprocess.run([sys.executable, "sharedtask.py", "all"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30, cwd=PROJECT)
        print(r.stdout.strip())
    else:
        print(f"未知子命令: {sub}")
        print(cmd_collab.__doc__)

def _run_script(script, timeout=900):
    """通用：以当前解释器跑同目录独立脚本并透传参数（复用入口，避免每个脚本重复封装）。"""
    def _f(args):
        import subprocess
        r = subprocess.run([sys.executable, script] + list(args), capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=timeout)
        print((r.stdout or "").strip())
        if r.returncode != 0:
            print((r.stderr or "").strip()[-800:])
    return _f


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
    "crossref": cmd_crossref, "clean": cmd_clean, "status": cmd_status, "task": cmd_task, "nophone": cmd_nophone, "oem": cmd_oem, "ds": cmd_ds, "agent": cmd_agent, "memory": cmd_memory, "collab": cmd_collab,
    "route": cmd_route, "dsedit": cmd_dsedit, "find": cmd_find,
    "did": cmd_did, "recall": cmd_recall,
    # 复用工具(2026-09-05)：清单核库存/秒查中国仓/定点补丁/能力地图/推GitHub/反思
    "stocklist": _run_script("stock_check_list.py"), "cnstk": _run_script("cn_stock.py"),
    "patch": _run_script("patch_file.py"), "index": _run_script("build_script_index.py"),
    "ghpush": _run_script("gh_push.py"), "reflect": _run_script("reflect.py"),
}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    if sys.argv[1] not in COMMANDS:
        _auto_match(" ".join(sys.argv[1:]))
        sys.exit(0)
    try:
        COMMANDS[sys.argv[1]](sys.argv[2:])
    except Exception as e:
        print(f"错误: {type(e).__name__}: {e}")