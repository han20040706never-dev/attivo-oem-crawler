# -*- coding: utf-8 -*-
"""task_memory.py — 零token本地"任务模式库"(自学习闭环)。
- did    : 完成任务后沉淀 "任务描述 -> 用了什么脚本/方案 -> 结果"
- recall : 新任务自动召回历史相似方案(复用 script_match 分词, Jaccard 相似度)
- hints  : 同类任务重复>=2次且仍靠临时手写 -> 提示沉淀成正式脚本(自动升级)
相似任务自动归并并累加次数、用最新方案覆盖(方案迭代自学习)。完全本地、不调AI。
用法:
  python task_memory.py did "任务" "脚本/方案" ["结果要点"]
  python task_memory.py recall "新任务"
  python task_memory.py hints
"""
import sys, io, os, json, datetime
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from script_match import _tokens, _expand

TOOL = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(TOOL, "_task_memory.json")
SIM_MERGE = 0.40   # 原始词overlap>=此值且共同原始词>=3 视为同一模式(自学习归并)
SIM_RECALL = 0.22  # 召回阈值(原始词overlap); 同义词扩展仅作小权重加分, 不主导


def _load():
    if os.path.exists(DB):
        try:
            return json.load(io.open(DB, encoding="utf-8"))
        except Exception:
            pass
    return {"records": []}


def _save(d):
    tmp = DB + ".tmp"
    io.open(tmp, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=1))
    os.replace(tmp, DB)


def _qtoks(q):
    return _tokens(q) | _expand(q)


def _sim(a, b):
    return len(a & b) / len(a | b) if (a and b) else 0


def _overlap(a, b, min_hit):
    """交集占较小集合比例(对中文词序/长短不一更鲁棒), 共同词<min_hit 记0防单词误并。"""
    if not a or not b:
        return 0
    hit = len(a & b)
    if hit < min_hit:
        return 0
    return hit / min(len(a), len(b))


def did(query, script, note=""):
    """完成任务后沉淀; 与历史模式高度相似则归并(次数+1, 方案更新为最新)。
    相似度只看原始词(2-gram/英文), 同义词扩展不参与归并判定, 防泛化词误并。"""
    d = _load()
    bt, et = _tokens(query), _expand(query)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    for r in d["records"]:
        rb = set(r.get("btoks", r.get("toks", [])))
        if _overlap(bt, rb, 3) >= SIM_MERGE:
            r["n"] = r.get("n", 1) + 1
            r["script"] = script
            if note:
                r["note"] = note
            r["ts"] = now
            r["q"] = query
            r["btoks"] = sorted(bt)
            r["etoks"] = sorted(et)
            _save(d)
            print(f"OK 归并历史模式(第{r['n']}次, 方案已迭代): {script}")
            return
    d["records"].append({"q": query, "btoks": sorted(bt), "etoks": sorted(et),
                         "script": script, "note": note, "ts": now, "n": 1})
    _save(d)
    print(f"OK 新增任务模式: {script}")


def recall(query, topn=3):
    """召回历史相似任务方案 [(score, script, note, n, ts)]。
    原始词overlap为主, 同义词扩展重合作0.1小权重加分。"""
    d = _load()
    bt, et = _tokens(query), _expand(query)
    scored = []
    for r in d["records"]:
        rb = set(r.get("btoks", r.get("toks", [])))
        bo = _overlap(bt, rb, 1)
        if bo < SIM_RECALL:
            continue
        re_ = set(r.get("etoks", []))
        eb = (len(et & re_) / max(1, min(len(et), len(re_)))) if (et and re_) else 0
        scored.append((round(bo + 0.1 * eb, 3), r))
    scored.sort(key=lambda x: x[0] + 0.03 * x[1].get("n", 1), reverse=True)
    return [(s, r["script"], r.get("note", ""), r.get("n", 1), r.get("ts", ""))
            for s, r in scored[:topn]]


def _is_temp(script):
    s = (script or "").lower().strip()
    if s.startswith("ax ") or s.startswith("python ax") or s.startswith("python script"):
        return False
    if any(m in s for m in ("temp", "tmp", "一次性", "手写", "inline", "内联")):
        return True
    base = s.split()[0] if s else ""
    return base.startswith("_") and base.endswith(".py")


def upgrade_hints():
    """重复>=2次且方案仍是临时手写 -> 建议沉淀正式脚本(自动升级信号)。"""
    d = _load()
    return [r for r in d["records"]
            if r.get("n", 1) >= 2 and _is_temp(r.get("script", ""))]


def main():
    if len(sys.argv) < 2:
        print("用法: did \"任务\" \"方案\" [要点] | recall \"任务\" | hints")
        return
    cmd = sys.argv[1]
    if cmd == "did":
        did(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "",
            sys.argv[4] if len(sys.argv) > 4 else "")
    elif cmd == "recall":
        res = recall(" ".join(sys.argv[2:]))
        if not res:
            print("无历史相似任务")
            return
        print("历史相似任务方案(自学习召回):")
        for s, sc, note, n, ts in res:
            print(f"  [{s:.2f}|{n}次|{ts}] {sc}{(' — ' + note) if note else ''}")
    elif cmd == "hints":
        h = upgrade_hints()
        if not h:
            print("无待沉淀的重复模式")
            return
        print("【自动升级】以下任务重复出现且仍靠临时手写, 建议沉淀成正式脚本:")
        for r in sorted(h, key=lambda x: -x.get("n", 1)):
            print(f"  x{r['n']} {r['q']}  (当前: {r['script']})")
    else:
        print("未知子命令: did / recall / hints")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"FAIL {type(e).__name__}: {e}")
        sys.exit(1)
