# -*- coding: utf-8 -*-
"""
check_done.py — 本地主动轮询：自动回收云电脑已完成的任务
运行：python check_done.py
功能：查飞书任务表中"已完成"但本地未回收的任务，自动拉取结果+经验，标记已回收
"""
import sys, io, os, json, subprocess, datetime
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')

PROJECT = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(PROJECT, "done_cache.json")

def load_cache():
    try:
        if os.path.exists(CACHE):
            with open(CACHE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {"processed": [], "last_check": ""}

def save_cache(cache):
    with open(CACHE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def cli(args):
    try:
        r = subprocess.run(["lark-cli", "base"] + args, capture_output=True, text=True, timeout=30, encoding='utf-8')
        return json.loads(r.stdout) if r.stdout.strip().startswith("{") else None
    except Exception as e:
        print(f"CLI错误: {e}")
        return None

def cell(v):
    if isinstance(v, list):
        return " ".join(str(x.get("text", "")) if isinstance(x, dict) else str(x) for x in v)
    return str(v) if v else ""

def main():
    BASE = "MYQybnKkZaXY2Yswagyc7pKNnRf"
    TABLE = "tblGwGpuGna0zGQG"
    cache = load_cache()
    processed = set(cache.get("processed", []))
    
    # 查已完成任务
    data = cli(["+record-list", "--base-token", BASE, "--table-id", TABLE,
                "--filter-json", json.dumps({"logic": "and", "conditions": [["状态", "==", "已完成"]]}, ensure_ascii=False),
                "--limit", "20", "--format", "json", "--as", "user"])
    if not data or not data.get("ok"):
        print("查询失败"); return
    
    d = data.get("data", {})
    rows, cols = d.get("data", []), d.get("fields", [])
    if not rows:
        print("无已完成任务"); return
    
    new_done = []
    for i, row in enumerate(rows):
        fmap = {cols[j]: row[j] for j in range(min(len(cols), len(row)))}
        rid = d.get("record_id_list", [])[i] if i < len(d.get("record_id_list", [])) else ""
        title = cell(fmap.get("任务标题"))
        result = cell(fmap.get("结果"))
        remark = cell(fmap.get("备注"))
        
        if rid and rid not in processed:
            new_done.append((rid, title, result, remark))
    
    if not new_done:
        print(f"无新完成任务（缓存中已处理{len(processed)}个）")
    else:
        print(f"发现{len(new_done)}个新完成任务：")
        for rid, title, result, remark in new_done:
            print(f"\n  【{title}】")
            if result:
                print(f"  结果: {result[:200]}")
            try:
                note = f"[本地已回收 {datetime.datetime.now().strftime('%m-%d %H:%M')}]"
                new_remark = (remark + "\n" + note).strip() if remark else note
                cli(["+record-batch-update", "--base-token", BASE, "--table-id", TABLE,
                     "--json", json.dumps({"records": [{"record_id": rid, "fields": {"备注": new_remark}}]}, ensure_ascii=False),
                     "--as", "user"])
            except:
                pass
            processed.add(rid)
        cache["processed"] = list(processed)
        save_cache(cache)
        print(f"\n已回收{len(new_done)}个任务，缓存累计{len(processed)}个")
    
    # 无论有无新任务，都触发经验增量同步
    print("\n--- 经验同步 ---")
    try:
        r = subprocess.run([sys.executable, os.path.join(PROJECT, "shared_mem.py"), "sync"],
                          capture_output=True, text=True, timeout=30, encoding='utf-8')
        print(r.stdout.strip() if r.stdout else "同步完成")
    except Exception as e:
        print(f"经验同步失败: {e}")

if __name__ == "__main__":
    main()
