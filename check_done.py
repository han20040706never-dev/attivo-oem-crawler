# -*- coding: utf-8 -*-
"""
check_done.py — 本地主动轮询：自动回收云电脑已完成的任务
运行：python check_done.py
功能：查飞书任务表中"已完成"但本地未回收的任务，自动拉取结果+经验，标记已回收
"""
import sys, io, os, json, subprocess, datetime
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
PROJECT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT)
from common import cli, cell
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')

PROJECT = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(PROJECT, "done_cache.json")
NOTIF = os.path.join(PROJECT, "_notifications.json")

def load_notifications():
    try:
        if os.path.exists(NOTIF):
            with open(NOTIF, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return []

def save_notifications(notifs):
    with open(NOTIF, 'w', encoding='utf-8') as f:
        json.dump(notifs, f, ensure_ascii=False, indent=2)

def add_notification(title, result, status):
    notifs = load_notifications()
    notifs.append({
        "time": datetime.datetime.now().isoformat(),
        "type": "task_result",
        "msg": f"[{status}] {title}: {result[:200] if result else ''}",
    })
    # 只保留最近20条
    save_notifications(notifs[-20:])

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

def main():
    BASE = "MYQybnKkZaXY2Yswagyc7pKNnRf"
    TABLE = "tblGwGpuGna0zGQG"
    cache = load_cache()
    processed = set(cache.get("processed", []))
    
    # 查已完成+已失败任务
    all_rows, all_cols, all_rids = [], [], []
    for status in ["已完成", "已失败"]:
        data = cli(["+record-list", "--base-token", BASE, "--table-id", TABLE,
                    "--filter-json", json.dumps({"logic": "and", "conditions": [["状态", "==", status]]}, ensure_ascii=False),
                    "--limit", "20", "--format", "json", "--as", "user"])
        if data and data.get("ok"):
            d = data.get("data", {})
            rows, cols = d.get("data", []), d.get("fields", [])
            rids = d.get("record_id_list", [])
            if not all_cols:
                all_cols = cols
            all_rows.extend(rows)
            all_rids.extend(rids)
    
    if not all_rows:
        print("无已完成/已失败任务")
    else:
        new_done = []
        for i, row in enumerate(all_rows):
            fmap = {all_cols[j]: row[j] for j in range(min(len(all_cols), len(row)))}
            rid = all_rids[i] if i < len(all_rids) else ""
            title = cell(fmap.get("任务标题"))
            result = cell(fmap.get("结果"))
            remark = cell(fmap.get("备注"))
            status = cell(fmap.get("状态"))
            if rid and rid not in processed:
                new_done.append((rid, title, result, remark, status))
        
        if not new_done:
            print(f"无新完成/失败任务（缓存中已处理{len(processed)}个）")
        else:
            print(f"发现{len(new_done)}个新任务：")
            for rid, title, result, remark, status in new_done:
                tag = "✓" if status == "已完成" else "✗失败"
                print(f"\n  {tag}【{title}】")
                if result:
                    print(f"  结果: {result[:200]}")
                add_notification(title, result, status)
                # 代码开发任务完成时自动跑代码质量门禁
                task_type = cell(fmap.get("类型"))
                if status == "已完成" and task_type == "代码开发":
                    print(f"  🔍 自动代码质量检查...")
                    try:
                        cq = subprocess.run([sys.executable, os.path.join(PROJECT, "code_quality_gate.py"), "--all"],
                                            capture_output=True, text=True, timeout=60, encoding='utf-8', cwd=PROJECT)
                        cq_out = cq.stdout.strip()
                        print(f"  {cq_out[-300:]}")
                        if "失败" in cq_out and "0失败" not in cq_out:
                            notifs = load_notifications()
                            notifs.append({
                                "time": datetime.datetime.now().isoformat(),
                                "type": "code_quality",
                                "msg": f"⚠️ 代码质量门禁未通过: {title} - {cq_out[-200:]}",
                            })
                            save_notifications(notifs[-20:])
                    except Exception as e:
                        print(f"  代码质量检查失败: {e}")
                try:
                    note = f"[本地已回收 {datetime.datetime.now().strftime('%m-%d %H:%M')}]"
                    new_remark = (remark + "\n" + note).strip() if remark else note
                    cli(["+record-batch-update", "--base-token", BASE, "--table-id", TABLE,
                         "--json", json.dumps({"update_records": {rid: {"备注": new_remark}}}, ensure_ascii=False),
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

    # 检查云电脑待回复问题
    print("\n--- 待回复问题 ---")
    try:
        r = subprocess.run([sys.executable, os.path.join(PROJECT, "sharedtask.py"), "questions"],
                          capture_output=True, text=True, timeout=30, encoding='utf-8')
        out = r.stdout.strip()
        if out and "无待回复" not in out:
            print(out)
            # 写入通知
            notifs = load_notifications()
            notifs.append({
                "time": datetime.datetime.now().isoformat(),
                "type": "question",
                "msg": f"云电脑有待回复问题: {out[:200]}",
            })
            save_notifications(notifs[-20:])
        else:
            print("无待回复问题")
    except Exception as e:
        print(f"问题检查失败: {e}")

if __name__ == "__main__":
    main()
