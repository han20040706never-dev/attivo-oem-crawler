# -*- coding: utf-8 -*-
"""
script_match.py — 零token本地脚本智能匹配器。
用法: python script_match.py "任务描述"  或  import script_match; script_match.find("任务")
原理: 解析 SCRIPT_INDEX.md(92脚本/用途/入口), 对任务描述做英文词+中文2-gram+业务同义词扩展,
     与每个脚本索引文本算关键词重合度, 返回 top5。完全本地、不调任何AI、毫秒级。
目的: 新任务先查已有脚本, 命中就直接用, 不重复造轮子、不烧token硬写。
"""
import sys, io, os, re, json
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8")

TOOL = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(TOOL, "SCRIPT_INDEX.md")

# 业务同义词: 任务里出现中文词 -> 补充这些英文/关键词到查询集(船外机+本项目语境)
SYNONYMS = {
    "库存": ["stock", "quant", "cn_stock", "有货", "现货", "中国仓"],
    "有货": ["stock", "cn_stock", "库存"], "现货": ["stock", "库存"], "中国仓": ["cn_stock", "stock"],
    "报销": ["expense", "toll", "费用", "发票"], "费用": ["expense", "toll", "报销"],
    "发票": ["expense", "toll", "ocr"], "通行费": ["toll", "高速"],
    "线索": ["lead", "crm", "商机", "opp"], "商机": ["opp", "lead", "crm", "pipeline"],
    "客户": ["customer", "partner", "联系人"], "联系人": ["partner", "customer", "res.partner"],
    "配件": ["part", "oem", "件号"], "件号": ["part", "oem", "零件"], "零件": ["part", "oem"],
    "备注": ["note", "comment", "description"], "评论": ["comment", "note"],
    "同步": ["sync", "同步"], "爬虫": ["crawl", "scrape", "fetch", "抓取"],
    "抓取": ["crawl", "scrape"], "翻译": ["translate", "中英"],
    "excel": ["xlsx", "sheet", "表格"], "表格": ["xlsx", "sheet", "excel"],
    "油封": ["seal", "密封", "o圈", "o-ring"], "密封": ["seal", "油封"],
    "齿轮": ["gear", "波箱"], "碳刷": ["brush", "断路器"],
    "销售": ["sales", "销量", "复购"], "复购": ["sales", "repurchase", "sop"],
    "录音": ["transcribe", "asr", "record", "转写"], "转写": ["transcribe", "asr", "录音"],
    "微信": ["wechat", "wx"], "手机号": ["phone", "电话", "mobile"], "电话": ["phone", "mobile"],
    "github": ["github", "gh_push", "推送"], "补丁": ["patch", "修改", "edit"],
    "修改": ["patch", "edit"], "odoo": ["odoo", "crm", "partner"],
    "需求清单": ["demand", "需求"], "需求": ["demand"],
    "带货": ["recommend", "loadout", "推荐", "备货"], "推荐": ["recommend", "loadout"],
    "备货": ["loadout", "recommend", "库存"], "能力地图": ["script_index", "index", "脚本"],
    "反思": ["reflect", "自检"], "自检": ["reflect", "health", "健康"],
    "健康": ["health", "healthcheck"], "共享任务": ["sharedtask", "task", "云电脑"],
    "云电脑": ["cloud", "sharedtask", "daemon"], "记忆": ["memory", "shared_mem"],
}


def _tokens(text):
    """从文本提取匹配关键词: 英文词(>=2字母) + 中文2-gram。"""
    text = (text or "").lower()
    toks = set(re.findall(r"[a-z][a-z0-9_]{1,}", text))
    cn = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    for seg in cn:
        for i in range(len(seg) - 1):
            toks.add(seg[i:i+2])
    return toks


def _expand(query):
    """同义词扩展: 任务里命中的中文词 -> 补充对应英文/关键词。"""
    q = query.lower()
    extra = set()
    for kw, syns in SYNONYMS.items():
        if kw in q:
            for s in syns:
                extra.add(s.lower())
    return extra


def load_index():
    """解析 SCRIPT_INDEX.md -> [{name,cat,usage,entries,text}]。"""
    if not os.path.exists(INDEX):
        return []
    rows = []
    cat = ""
    for line in io.open(INDEX, encoding="utf-8"):
        line = line.rstrip("\n")
        m = re.match(r"^## (.+?)（", line)
        if m:
            cat = m.group(1).strip()
            continue
        if line.startswith("| `"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 2 and cells[0] not in ("脚本", "---"):
                name = cells[0].strip("`").strip()
                usage = cells[1] if len(cells) > 1 else ""
                entries = cells[2] if len(cells) > 2 else ""
                text = f"{name} {cat} {usage} {entries}".lower()
                rows.append({"name": name, "cat": cat, "usage": usage,
                             "entries": entries, "toks": _tokens(text)})
    return rows


def find(query, topn=5):
    """返回 topn 匹配脚本 [(score, name, cat, usage)]。"""
    rows = load_index()
    if not rows:
        return []
    qtoks = _tokens(query) | _expand(query)
    if not qtoks:
        return []
    scored = []
    for r in rows:
        hit = qtoks & r["toks"]
        # 脚本名精确命中加权
        name_bonus = 0.3 if r["name"].lower() in query.lower() else 0
        score = len(hit) / max(1, len(qtoks)) + name_bonus
        if score > 0:
            scored.append((round(score, 3), r["name"], r["cat"], r["usage"]))
    DEPRECATED = {"seal_guide": "build_seal_rec", "healthcheck": "health", "multi_ai": "ai_router"}
    fixed = []
    for sc, name, cat, usage in scored:
        if name in DEPRECATED:
            sc = round(sc * 0.4, 3)
            usage = f"[旧版→用{DEPRECATED[name]}] " + usage
        fixed.append((sc, name, cat, usage))
    fixed.sort(reverse=True)
    return fixed[:topn]


def main():
    if len(sys.argv) < 2:
        print("用法: python script_match.py \"任务描述\"  (例: 核一下这个Excel清单的中国仓库存)")
        sys.exit(0)
    query = " ".join(sys.argv[1:])
    res = find(query)
    if not res:
        print("无匹配脚本(能力地图可能过期, 先跑 ax index 刷新); 确认无现成脚本再写新的。")
        return
    print(f"任务: {query}")
    print("已有脚本匹配 top%d (零token本地匹配):" % len(res))
    for i, (sc, name, cat, usage) in enumerate(res, 1):
        u = (usage[:60] + "…") if len(usage) > 60 else usage
        print(f"  {i}. [{sc:.2f}] {name}.py  ({cat})  {u}")
    if res and res[0][0] >= 0.25:
        print(f"\n=> 建议直接用: {res[0][1]}.py (或 ax 对应命令), 不要新写脚本")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"FAIL {type(e).__name__}: {e}")
        sys.exit(1)
