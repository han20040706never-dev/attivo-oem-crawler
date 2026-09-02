# -*- coding: utf-8 -*-
"""
sharedtask.py —— 豆包Agent共享任务库（飞书多维表格）命令行封装，省token。
表：任务队列。铁律：只放公开信息/任务描述，禁止客户数据、底价、密钥。

用法：
  python sharedtask.py push <类型> <标题> <内容> [备注]   # 本地豆包发任务(来源=本地豆包,状态=待处理)
  python sharedtask.py pending                            # 列待处理
  python sharedtask.py done                               # 列已完成(带结果)
  python sharedtask.py all                                # 列全部(精简)
  python sharedtask.py set <record_id> <状态> [结果]       # 改状态/回传结果
  python sharedtask.py chat <record_id> <消息> [发送者]    # 追加对话消息(AI间交流)
  python sharedtask.py view <record_id>                   # 查看任务详情+对话日志
  python sharedtask.py claim <record_id> <实例名>          # 云电脑认领任务(带实例名区分)
  python sharedtask.py complete <record_id> <结果> [经验]   # 完成任务+自动回收经验到共享记忆
类型∈信息调研/内容生产/文件处理/代码开发/数据整理/其他；状态∈待处理/处理中/已完成/已取消
"""
import sys, io, json, subprocess, argparse
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8")

BASE = "MYQybnKkZaXY2Yswagyc7pKNnRf"
TABLE = "tblGwGpuGna0zGQG"
TYPES = {"信息调研", "内容生产", "文件处理", "代码开发", "数据整理", "其他"}
STATUSES = {"待处理", "处理中", "已完成", "已取消"}
FIELDS = ["任务编号", "任务标题", "任务类型", "任务内容", "来源", "状态", "结果", "备注", "对话日志"]


def cli(args):
    r = subprocess.run(["lark-cli", "base"] + args, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=120)
    if r.returncode != 0:
        print("LARK_ERR:", (r.stderr or r.stdout)[-400:]); return None
    try:
        return json.loads(r.stdout)
    except Exception:
        print(r.stdout[:800]); return None


def parse_matrix(data):
    """record-list --format json 返回矩阵：data.data行 + data.fields列名 + record_id_list，按索引对齐"""
    d = (data or {}).get("data", {})
    rows, cols, rids = d.get("data", []), d.get("fields", []), d.get("record_id_list", [])
    out = []
    for i, row in enumerate(rows):
        f = {cols[j]: row[j] for j in range(min(len(cols), len(row)))}
        out.append((rids[i] if i < len(rids) else "", f))
    return out


def cell(v):
    if isinstance(v, list):
        return "/".join(cell(x) for x in v if x)
    if isinstance(v, dict):
        return v.get("text") or v.get("name") or str(v)
    return "" if v is None else str(v)


def list_by_status(status=None):
    args = ["+record-list", "--base-token", BASE, "--table-id", TABLE,
            "--sort-json", json.dumps([{"field": "创建时间", "desc": True}], ensure_ascii=False),
            "--limit", "100", "--format", "json", "--as", "user"]
    for fld in FIELDS:
        args += ["--field-id", fld]
    if status:
        args += ["--filter-json", json.dumps(
            {"logic": "and", "conditions": [["状态", "==", status]]}, ensure_ascii=False)]
    data = cli(args)
    recs = parse_matrix(data)
    if not recs:
        print("（无记录）"); return
    for rid, f in recs:
        no = cell(f.get("任务编号"))
        st = cell(f.get("状态")); src = cell(f.get("来源")); tp = cell(f.get("任务类型"))
        title = cell(f.get("任务标题"))
        print(f"[{rid}] {no} | {st} | {src} | {tp} | {title}")
        if status == "已完成" and cell(f.get("结果")):
            print("    结果:", cell(f.get("结果"))[:500])


def push(typ, title, content, remark=""):
    if typ not in TYPES:
        print("类型非法，可选:", "/".join(TYPES)); return
    fields = {"任务标题": title, "任务类型": [typ], "任务内容": content,
              "来源": ["本地豆包"], "状态": ["待处理"]}
    if remark:
        fields["备注"] = remark
    data = cli(["+record-batch-create", "--base-token", BASE, "--table-id", TABLE,
                "--json", json.dumps({"create_records": [fields]}, ensure_ascii=False),
                "--as", "user"])
    rid = (((data or {}).get("data") or {}).get("record_id_list") or ["?"])[0]
    print("已发任务:", rid)


def set_status(rid, status, result=None):
    if status not in STATUSES:
        print("状态非法，可选:", "/".join(STATUSES)); return
    fields = {"状态": [status]}
    if result:
        fields["结果"] = result
    data = cli(["+record-batch-update", "--base-token", BASE, "--table-id", TABLE,
                "--json", json.dumps({"update_records": {rid: fields}}, ensure_ascii=False),
                "--as", "user"])
    print("已更新", rid, "->", status, "" if data is None else "OK")


def chat(rid, message, sender="本地豆包"):
    """追加对话消息到任务的对话日志，实现AI间交流"""
    import datetime
    data = cli(["+record-get", "--base-token", BASE, "--table-id", TABLE,
                "--record-id", rid, "--format", "json", "--as", "user"])
    current = ""
    if data and data.get("ok"):
        d = data.get("data", {})
        rows, cols = d.get("data", []), d.get("fields", [])
        if rows and cols:
            fmap = {cols[j]: rows[0][j] for j in range(min(len(cols), len(rows[0])))}
            raw = fmap.get("对话日志", "")
            if isinstance(raw, list):
                current = "".join(x.get("text","") for x in raw if isinstance(x,dict))
            elif isinstance(raw, str):
                current = raw
    ts = datetime.datetime.now().strftime("%m-%d %H:%M")
    new_log = (current + f"\n[{sender} {ts}] {message}").strip()
    cli(["+record-batch-update", "--base-token", BASE, "--table-id", TABLE,
         "--json", json.dumps({"update_records": {rid: {"对话日志": new_log}}}, ensure_ascii=False),
         "--as", "user"])
    print(f"OK: [{sender}] 消息已追加到 {rid}")


def view(rid):
    """查看任务详情含对话日志"""
    data = cli(["+record-get", "--base-token", BASE, "--table-id", TABLE,
                "--record-id", rid, "--format", "json", "--as", "user"])
    if not data or not data.get("ok"):
        print("获取失败"); return
    d = data.get("data", {})
    rows = d.get("data", [])
    cols = d.get("fields", [])
    if not rows or not cols:
        print("无数据"); return
    row = rows[0]
    f = {cols[j]: row[j] for j in range(min(len(cols), len(row)))}
    print(f"=== {cell(f.get('任务标题'))} ===")
    print(f"编号: {cell(f.get('任务编号'))} | 类型: {cell(f.get('任务类型'))} | 状态: {cell(f.get('状态'))} | 来源: {cell(f.get('来源'))}")
    print(f"内容: {cell(f.get('任务内容'))}")
    if cell(f.get("结果")):
        print(f"结果: {cell(f.get('结果'))}")
    chat_log = cell(f.get("对话日志"))
    if chat_log:
        print(f"\n--- 对话日志 ---")
        print(chat_log)


def complete(rid, result, experience=""):
    """完成任务并自动回收经验到共享记忆"""
    set_status(rid, "已完成", result)
    data = cli(["+record-get", "--base-token", BASE, "--table-id", TABLE,
                "--record-id", rid, "--format", "json", "--as", "user"])
    title = ""
    chat_log = ""
    if data and data.get("ok"):
        d = data.get("data", {})
        rows, cols = d.get("data", []), d.get("fields", [])
        if rows and cols:
            fmap = {cols[j]: rows[0][j] for j in range(min(len(cols), len(rows[0])))}
            title = cell(fmap.get("任务标题"))
            chat_log = cell(fmap.get("对话日志"))
    exp = result[:300]
    if experience:
        exp += f"\n经验: {experience}"
    if chat_log:
        lines = [l for l in chat_log.split("\n") if l.strip()]
        if len(lines) > 3:
            exp += "\n关键对话:\n" + "\n".join(lines[-3:])
    try:
        import subprocess
        subprocess.run([sys.executable, "shared_mem.py", "push",
                        f"[任务完成] {title}", "已完成任务", exp, "脚本"],
                       capture_output=True, text=True, timeout=30, encoding="utf-8")
        print("经验已回收到共享记忆")
    except Exception as e:
        print(f"经验回收失败: {e}")


def claim(rid, instance_name):
    """云电脑认领任务：标记处理中+对话日志声明身份+备注记录实例名"""
    set_status(rid, "处理中")
    chat(rid, f"我是【{instance_name}】，已认领此任务，开始执行", instance_name)
    # 备注里记录认领者
    data = cli(["+record-get", "--base-token", BASE, "--table-id", TABLE,
                "--record-id", rid, "--format", "json", "--as", "user"])
    remark = ""
    if data and data.get("ok"):
        d = data.get("data", {})
        rows, cols = d.get("data", []), d.get("fields", [])
        if rows and cols:
            fmap = {cols[j]: rows[0][j] for j in range(min(len(cols), len(rows[0])))}
            remark = cell(fmap.get("备注"))
    new_remark = f"{remark}\n认领者: {instance_name}".strip()
    cli(["+record-batch-update", "--base-token", BASE, "--table-id", TABLE,
         "--json", json.dumps({"update_records": {rid: {"备注": new_remark}}}, ensure_ascii=False),
         "--as", "user"])
    print(f"OK: 【{instance_name}】已认领任务 {rid}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action")
    p.add_argument("rest", nargs="*")
    a = p.parse_args()
    if a.action == "push":
        push(a.rest[0], a.rest[1], a.rest[2], a.rest[3] if len(a.rest) > 3 else "")
    elif a.action == "pending":
        list_by_status("待处理")
    elif a.action == "done":
        list_by_status("已完成")
    elif a.action == "all":
        list_by_status(None)
    elif a.action == "set":
        set_status(a.rest[0], a.rest[1], a.rest[2] if len(a.rest) > 2 else None)
    elif a.action == "chat":
        # chat <record_id> <消息> [sender]
        sender = a.rest[2] if len(a.rest) > 2 else "本地豆包"
        chat(a.rest[0], a.rest[1], sender)
    elif a.action == "view":
        view(a.rest[0])
    elif a.action == "complete":
        # complete <record_id> <结果> [经验]
        complete(a.rest[0], a.rest[1], a.rest[2] if len(a.rest) > 2 else "")
    elif a.action == "claim":
        # claim <record_id> <实例名>
        claim(a.rest[0], a.rest[1])
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
