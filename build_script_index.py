# -*- coding: utf-8 -*-
"""扫描本目录所有 .py，自动生成《脚本能力地图 SCRIPT_INDEX.md》。
面对新任务先查能力地图 + `ax route`，禁止重复造轮子；新增/重命名脚本后重跑：python build_script_index.py
好脚本留存机制的一部分。纯标准库 ast 静态解析，不执行被扫描脚本。"""
import sys, io, os, ast, re, datetime
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8")
TOOL = os.path.dirname(os.path.abspath(__file__))

# 分类规则: (类别, 文件名正则)
CATS = [
    ("CRM/Odoo 操作", r"crm|odoo|opp|lead|customer|match_opp|append|region|corrections|fix_typos|cleanup_legacy|nophone|fill_phone|b2b|sop_followup|visit_pipeline"),
    ("销售分析/带货推荐", r"sales|recommend|analyze|customer_score|build_loadout|build_dashboard|build_profiles|customer_summary|gen_evidence|gen_lookup"),
    ("配件/库存/OEM知识库", r"part|stock|seal|cn_stock|oem|crossref|scrape|yamamotor"),
    ("OEM 爬虫", r"crawl|probe|crawler_base"),
    ("AI 路由/DeepSeek/反思", r"ai_router|multi_ai|ds_harness|smart|reflect|code_quality|profile_tool|extract_sop|learn_taxonomy|fill_from_notes|tx"),
    ("云协作/共享任务/健康", r"shared|cloud|daemon|auto_dispatch|health|check_done|gh_push|common"),
    ("报销/费用", r"toll|expense|create_expense"),
    ("录音/转写", r"transcribe|record|asr"),
    ("微信联系人采集", r"wx_"),
    ("Excel/文件/通用工具", r"xlsx|card_ocr|longshot_ocr|patch_file|build_script_index|search_github"),
]


def classify(fn):
    for cat, pat in CATS:
        if re.search(pat, fn, re.I):
            return cat
    return "其他"


def scan(fp):
    try:
        src = open(fp, encoding="utf-8").read()
        tree = ast.parse(src)
    except Exception as e:
        return None, [f"<解析失败:{str(e)[:30]}>"]
    doc = ast.get_docstring(tree) or ""
    doc = doc.strip().splitlines()[0] if doc else ""
    funcs = [n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and not n.name.startswith("_")]
    classes = [n.name for n in tree.body if isinstance(n, ast.ClassDef)]
    api = (classes + funcs)[:8]
    return doc, api


def main():
    rows = {}
    for fn in sorted(os.listdir(TOOL)):
        if not fn.endswith(".py"):
            continue
        if fn.startswith(("config.", "_backup", "sop_followup_backup")) or "backup" in fn.lower():
            continue  # 密钥/备份不进索引
        doc, api = scan(os.path.join(TOOL, fn))
        if doc is None:
            continue
        rows.setdefault(classify(fn), []).append((fn[:-3], doc, ", ".join(api)))
    out = ["# 脚本能力地图（自动生成，勿手改）",
           f"> 生成时间 {datetime.datetime.now():%Y-%m-%d %H:%M} · 生成器 `python build_script_index.py`",
           "> **新任务铁律**：先在本地图找现成脚本/函数 → 再 `ax route` → 都没有才写新脚本；新脚本必须有模块 docstring，写完重跑本生成器入库。",
           f"> 共 {sum(len(v) for v in rows.values())} 个脚本，分 {len(rows)} 类。", ""]
    for cat in [c for c, _ in CATS] + ["其他"]:
        if cat not in rows:
            continue
        out.append(f"\n## {cat}（{len(rows[cat])}）")
        out.append("| 脚本 | 用途 | 主要入口/函数 |")
        out.append("|---|---|---|")
        for fn, doc, api in rows[cat]:
            out.append(f"| `{fn}` | {doc or '（无docstring，待补）'} | {api} |")
    txt = "\n".join(out) + "\n"
    p = os.path.join(TOOL, "SCRIPT_INDEX.md")
    open(p, "w", encoding="utf-8").write(txt)
    print(f"OK SCRIPT_INDEX.md 已生成, {sum(len(v) for v in rows.values())}脚本 / {len(rows)}类")
    # 打印缺 docstring 的脚本(复用治理重点)
    miss = [fn for cat in rows.values() for fn, d, _ in cat if not d]
    print("缺docstring待补:", miss)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"FAIL {type(e).__name__}: {e}")
