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
import sys, io, os, json, subprocess, argparse
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8")

BASE = "MYQybnKkZaXY2Yswagyc7pKNnRf"
TABLE = "tblGwGpuGna0zGQG"
TYPES = {"信息调研", "内容生产", "文件处理", "代码开发", "数据整理", "其他"}
STATUSES = {"待处理", "处理中", "已完成", "已取消", "已失败"}
FIELDS = ["任务编号", "任务标题", "任务类型", "任务内容", "来源", "状态", "结果", "备注", "对话日志", "指派给", "优先级"]
PRIORITY_ORDER = {"高": 0, "中": 1, "低": 2}


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
    # 按优先级排序：高→中→低，同优先级按创建时间
    def sort_key(item):
        rid, f = item
        pri = cell(f.get("优先级")) or "中"
        return (PRIORITY_ORDER.get(pri, 1), cell(f.get("任务编号")))
    recs.sort(key=sort_key)
    for rid, f in recs:
        no = cell(f.get("任务编号"))
        st = cell(f.get("状态")); src = cell(f.get("来源")); tp = cell(f.get("任务类型"))
        title = cell(f.get("任务标题"))
        assignee = cell(f.get("指派给"))
        pri = cell(f.get("优先级")) or "中"
        pri_icon = {"高": "🔴", "中": "🟡", "低": "🟢"}.get(pri, "⚪")
        line = f"[{rid}] {pri_icon}{pri} | {no} | {st} | {src} | {tp} | {title}"
        if assignee:
            line += f" → {assignee}"
        print(line)
        if status == "已完成" and cell(f.get("结果")):
            print("    结果:", cell(f.get("结果"))[:500])


def push(typ, title, content, remark="", assignee="", priority="中"):
    if typ not in TYPES:
        print("类型非法，可选:", "/".join(TYPES)); return
    if priority not in PRIORITY_ORDER:
        priority = "中"
    fields = {"任务标题": title, "任务类型": [typ], "任务内容": content,
              "来源": ["本地豆包"], "状态": ["待处理"], "优先级": [priority]}
    if remark:
        fields["备注"] = remark
    if assignee:
        fields["指派给"] = assignee
    data = cli(["+record-batch-create", "--base-token", BASE, "--table-id", TABLE,
                "--json", json.dumps({"create_records": [fields]}, ensure_ascii=False),
                "--as", "user"])
    rid = (((data or {}).get("data") or {}).get("record_id_list") or ["?"])[0]
    print("已发任务:", rid, f"指派给:{assignee}" if assignee else "")


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


def _bump_instance(instance_name, field="completed"):
    """更新实例完成/失败计数"""
    try:
        reg_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instances.json")
        reg = {}
        if os.path.exists(reg_file):
            with open(reg_file, 'r', encoding='utf-8') as f:
                reg = json.load(f)
        inst = reg.get("instances", {}).get(instance_name, {"tags": [], "completed": 0, "failed": 0})
        inst[field] = inst.get(field, 0) + 1
        reg.setdefault("instances", {})[instance_name] = inst
        with open(reg_file, 'w', encoding='utf-8') as f:
            json.dump(reg, f, ensure_ascii=False, indent=2)
        _push_instances()
    except:
        pass


def complete(rid, result, experience=""):
    """完成任务并用免费AI提取结构化经验回收到共享记忆"""
    set_status(rid, "已完成", result)
    data = cli(["+record-get", "--base-token", BASE, "--table-id", TABLE,
                "--record-id", rid, "--format", "json", "--as", "user"])
    title = ""
    chat_log = ""
    task_content = ""
    if data and data.get("ok"):
        d = data.get("data", {})
        rows, cols = d.get("data", []), d.get("fields", [])
        if rows and cols:
            fmap = {cols[j]: rows[0][j] for j in range(min(len(cols), len(rows[0])))}
            title = cell(fmap.get("任务标题"))
            chat_log = cell(fmap.get("对话日志"))
            task_content = cell(fmap.get("任务内容"))
    # 用免费AI提取结构化经验
    exp_text = result
    if experience:
        exp_text += f"\n\n手动补充经验: {experience}"
    if chat_log:
        exp_text += f"\n\n对话日志:\n{chat_log}"
    structured = ""
    try:
        from ai_router import extract
        structured = extract(exp_text, ["可复用经验", "踩坑教训", "可复用代码或脚本名", "产出数据文件路径"], provider=None)
        if structured:
            structured = str(structured)
    except Exception as e:
        print(f"AI经验提取失败({e})，用原始结果")
        structured = result[:500]
    final_exp = f"任务: {task_content[:100]}\n结果: {result[:300]}\n\n=== AI提取经验 ===\n{structured[:800]}"
    try:
        import subprocess
        subprocess.run([sys.executable, "shared_mem.py", "push",
                        f"[任务完成] {title}", "已完成任务", final_exp, "脚本"],
                       capture_output=True, text=True, timeout=60, encoding="utf-8")
        print("经验已AI提取并回收到共享记忆")
    except Exception as e:
        print(f"经验回收失败: {e}")
    # 更新实例完成计数
    claimant = ""
    try:
        for line in cell(fmap.get("备注", "")).split("\n"):
            if "认领者:" in line:
                claimant = line.split("认领者:")[-1].strip()
    except:
        pass
    if claimant:
        _bump_instance(claimant, "completed")


def claim(rid, instance_name):
    """云电脑认领任务：先检查状态，已处理中则拒绝（防冲突锁）"""
    # 先读当前状态
    data = cli(["+record-get", "--base-token", BASE, "--table-id", TABLE,
                "--record-id", rid, "--field-id", "状态", "--field-id", "备注",
                "--format", "json", "--as", "user"])
    current_status = ""
    remark = ""
    if data and data.get("ok"):
        d = data.get("data", {})
        rows, cols = d.get("data", []), d.get("fields", [])
        if rows and cols:
            fmap = {cols[j]: rows[0][j] for j in range(min(len(cols), len(rows[0])))}
            current_status = cell(fmap.get("状态"))
            remark = cell(fmap.get("备注"))
    # 锁检查：已处理中则拒绝
    if current_status == "处理中":
        existing_claimant = ""
        for line in remark.split("\n"):
            if "认领者:" in line:
                existing_claimant = line.split("认领者:")[-1].strip()
        print(f"FAIL: 任务{rid}已被【{existing_claimant}】认领，请勿重复认领")
        return False
    if current_status not in ("待处理",):
        print(f"FAIL: 任务{rid}状态为{current_status}，只能认领待处理任务")
        return False
    # 认领
    set_status(rid, "处理中")
    # 回读校验：确认状态真的变成了处理中（防假OK）
    verify = cli(["+record-get", "--base-token", BASE, "--table-id", TABLE,
                  "--record-id", rid, "--field-id", "状态",
                  "--format", "json", "--as", "user"])
    verified = False
    if verify and verify.get("ok"):
        d = verify.get("data", {})
        rows, cols = d.get("data", []), d.get("fields", [])
        if rows and cols:
            fmap = {cols[j]: rows[0][j] for j in range(min(len(cols), len(rows[0])))}
            verified = cell(fmap.get("状态")) == "处理中"
    if not verified:
        print(f"FAIL: 任务{rid}认领后状态未变更，写入可能失败")
        return False
    chat(rid, f"我是【{instance_name}】，已认领此任务，开始执行", instance_name)
    new_remark = f"{remark}\n认领者: {instance_name}".strip()
    cli(["+record-batch-update", "--base-token", BASE, "--table-id", TABLE,
         "--json", json.dumps({"update_records": {rid: {"备注": new_remark}}}, ensure_ascii=False),
         "--as", "user"])
    print(f"OK: 【{instance_name}】已认领任务 {rid}")
    # 自动注册实例到instances.json
    try:
        import datetime
        reg_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instances.json")
        reg = {}
        if os.path.exists(reg_file):
            with open(reg_file, 'r', encoding='utf-8') as f:
                reg = json.load(f)
        inst = reg.get("instances", {}).get(instance_name, {"tags": [], "completed": 0, "failed": 0})
        inst["last_seen"] = datetime.datetime.now().isoformat()
        reg.setdefault("instances", {})[instance_name] = inst
        with open(reg_file, 'w', encoding='utf-8') as f:
            json.dump(reg, f, ensure_ascii=False, indent=2)
        _push_instances()
    except:
        pass
    return True


def rate(rid, score, feedback=""):
    """给完成的任务评分1-5，<=2分自动创建改进任务"""
    score = int(score)
    if score < 1 or score > 5:
        print("评分必须1-5"); return
    # 读取任务信息
    data = cli(["+record-get", "--base-token", BASE, "--table-id", TABLE,
                "--record-id", rid, "--format", "json", "--as", "user"])
    title = ""
    if data and data.get("ok"):
        d = data.get("data", {})
        rows, cols = d.get("data", []), d.get("fields", [])
        if rows and cols:
            fmap = {cols[j]: rows[0][j] for j in range(min(len(cols), len(rows[0])))}
            title = cell(fmap.get("任务标题"))
    # 追加评分到对话日志
    chat(rid, f"【本地豆包评分】{score}/5 {'⭐'*score} {feedback}", "本地豆包")
    print(f"已评分: {rid} {score}/5")
    if score <= 2:
        # 自动创建改进任务
        push("代码开发", f"改进:{title}",
             f"原任务结果质量不佳（评分{score}/5）。反馈：{feedback}\n请重新执行或改进方法，参考原任务对话日志。",
             f"原任务:{rid}", "")
        print("低分自动创建改进任务")


def ask(rid, question, instance_name="云电脑"):
    """云电脑向本地提问：追加带【待本地回复】标记的消息，bootstrap时自动显示"""
    chat(rid, f"【待本地回复】{question}", instance_name)
    print(f"OK: 问题已提交，等待本地回复")


def _push_instances():
    """把instances.json推到GitHub，两边同步"""
    try:
        import requests, base64
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import config
        H = {'Authorization': f'token {config.GITHUB_PAT}', 'Accept': 'application/vnd.github.v3+json'}
        REPO = 'han20040706never-dev/attivo-oem-crawler'
        reg_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instances.json")
        content = open(reg_file, 'r', encoding='utf-8').read()
        r = requests.get(f'https://api.github.com/repos/{REPO}/contents/instances.json', headers=H, timeout=10)
        sha = r.json().get('sha') if r.status_code == 200 else None
        p = {'message': 'sync instances.json', 'content': base64.b64encode(content.encode()).decode()}
        if sha: p['sha'] = sha
        requests.put(f'https://api.github.com/repos/{REPO}/contents/instances.json', headers=H, json=p, timeout=15)
    except:
        pass


def register(instance_name, tags_str=""):
    """云电脑实例注册：记录名称、专长标签、活跃度"""
    import datetime
    reg_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instances.json")
    try:
        with open(reg_file, 'r', encoding='utf-8') as f:
            reg = json.load(f)
    except:
        reg = {"instances": {}}
    tags = [t.strip() for t in tags_str.split(",") if t.strip()] if tags_str else []
    inst = reg["instances"].get(instance_name, {"tags": [], "completed": 0, "failed": 0})
    inst["tags"] = tags or inst.get("tags", [])
    inst["last_seen"] = datetime.datetime.now().isoformat()
    reg["instances"][instance_name] = inst
    with open(reg_file, 'w', encoding='utf-8') as f:
        json.dump(reg, f, ensure_ascii=False, indent=2)
    print(f"OK: 实例【{instance_name}】已注册，标签: {', '.join(inst['tags']) or '无'}")
    _push_instances()


def recommend(task_type=""):
    """智能推荐：根据任务类型匹配最合适的云电脑实例"""
    reg_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instances.json")
    try:
        with open(reg_file, 'r', encoding='utf-8') as f:
            reg = json.load(f)
    except:
        print("无实例注册"); return
    instances = reg.get("instances", {})
    if not instances:
        print("无已注册实例"); return
    # 按完成数+标签匹配排序
    scored = []
    for name, info in instances.items():
        score = info.get("completed", 0)
        if task_type:
            score += sum(10 for t in info.get("tags", []) if task_type in t or t in task_type)
        scored.append((score, name, info))
    scored.sort(reverse=True)
    print(f"=== 任务类型【{task_type or '通用'}】推荐实例 ===")
    for score, name, info in scored[:5]:
        tags = ", ".join(info.get("tags", [])) or "无标签"
        print(f"  {name} | 完成{info.get('completed',0)}个 | 标签:{tags} | 匹配分:{score}")


def fail(rid, reason, instance_name="云电脑"):
    """任务失败上报：标记失败+记录原因+push踩坑经验到共享记忆"""
    # 读取任务信息
    data = cli(["+record-get", "--base-token", BASE, "--table-id", TABLE,
                "--record-id", rid, "--format", "json", "--as", "user"])
    title = ""
    task_content = ""
    if data and data.get("ok"):
        d = data.get("data", {})
        rows, cols = d.get("data", []), d.get("fields", [])
        if rows and cols:
            fmap = {cols[j]: rows[0][j] for j in range(min(len(cols), len(rows[0])))}
            title = cell(fmap.get("任务标题"))
            task_content = cell(fmap.get("任务内容"))
    # 标记失败
    set_status(rid, "已失败")
    chat(rid, f"【{instance_name}】任务失败: {reason}", instance_name)
    # push踩坑经验到共享记忆
    try:
        import subprocess
        exp = f"任务: {task_content[:100]}\n失败原因: {reason}\n执行者: {instance_name}"
        subprocess.run([sys.executable, "shared_mem.py", "push",
                        f"[任务失败] {title}", "踩坑教训", exp, "脚本"],
                       capture_output=True, text=True, timeout=60, encoding="utf-8")
        print("失败原因已记录到共享记忆(踩坑教训)")
    except Exception as e:
        print(f"经验记录失败: {e}")
    print(f"FAIL: 任务{rid}已标记失败 - {reason}")
    _bump_instance(instance_name, "failed")


def list_templates():
    """列出可用任务模板"""
    import os
    tpl_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "task_templates.json")
    if not os.path.exists(tpl_file):
        print("无模板文件"); return
    with open(tpl_file, 'r', encoding='utf-8') as f:
        tpls = json.load(f)
    print("=== 可用任务模板 ===")
    for name, tpl in tpls.items():
        print(f"  {name}: {tpl['title'][:50]}")

def use_template(tpl_name, params_str="", assignee=""):
    """用模板创建任务: use_template <模板名> <参数key=value,...> [指派给]"""
    import os
    tpl_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "task_templates.json")
    if not os.path.exists(tpl_file):
        print("无模板文件"); return
    with open(tpl_file, 'r', encoding='utf-8') as f:
        tpls = json.load(f)
    if tpl_name not in tpls:
        print(f"模板'{tpl_name}'不存在，可用:", "/".join(tpls.keys())); return
    tpl = tpls[tpl_name]
    # 解析参数
    params = {}
    for kv in params_str.split(","):
        if "=" in kv:
            k, v = kv.split("=", 1)
            params[k.strip()] = v.strip()
    title = tpl["title"]
    content = tpl["content"]
    remark = tpl.get("remark", "")
    for k, v in params.items():
        title = title.replace("{" + k + "}", v)
        content = content.replace("{" + k + "}", v)
    push(tpl["type"], title, content, remark, assignee)


def dashboard():
    """任务仪表盘：按状态统计+最近活动"""
    data = cli(["+record-list", "--base-token", BASE, "--table-id", TABLE,
                "--limit", "100", "--format", "json", "--as", "user"])
    if not data or not data.get("ok"):
        print("dashboard: 查询失败"); return
    recs = parse_matrix(data)
    stats = {"待处理": [], "处理中": [], "已完成": [], "已取消": []}
    for rid, f in recs:
        st = cell(f.get("状态"))
        title = cell(f.get("任务标题"))
        tp = cell(f.get("任务类型"))
        assignee = cell(f.get("指派给"))
        remark = cell(f.get("备注"))
        claimer = ""
        for line in remark.split("\n"):
            if "认领者:" in line:
                claimer = line.split("认领者:")[-1].strip()
        entry = f"[{rid}] {title} ({tp})"
        if claimer: entry += f" 认领:{claimer}"
        if assignee: entry += f" 指派:{assignee}"
        if st in stats:
            stats[st].append(entry)
        else:
            stats.setdefault(st, []).append(entry)
    print("=" * 50)
    print("任务仪表盘")
    print("=" * 50)
    for st, items in stats.items():
        if items:
            print(f"\n【{st}】{len(items)}个")
            for item in items[:5]:
                print(f"  {item}")
            if len(items) > 5:
                print(f"  ...还有{len(items)-5}个")
    total = sum(len(v) for v in stats.values())
    print(f"\n总计: {total}个任务")


def watchdog(hours=24, auto_reset=False):
    """检测超时任务：处理中超过N小时未完成的，列出并可选自动重置"""
    import datetime
    data = cli(["+record-list", "--base-token", BASE, "--table-id", TABLE,
                "--filter-json", json.dumps({"logic": "and", "conditions": [["状态", "==", "处理中"]]}, ensure_ascii=False),
                "--limit", "50", "--format", "json", "--as", "user"])
    if not data or not data.get("ok"):
        print("watchdog: 查询失败"); return
    recs = parse_matrix(data)
    if not recs:
        print("watchdog: 无处理中任务"); return
    now = datetime.datetime.now()
    stuck = []
    for rid, f in recs:
        upd = cell(f.get("更新时间"))
        title = cell(f.get("任务标题"))
        remark = cell(f.get("备注"))
        claimer = ""
        for line in remark.split("\n"):
            if "认领者:" in line:
                claimer = line.split("认领者:")[-1].strip()
        try:
            upd_time = datetime.datetime.fromisoformat(upd.replace("Z", "").replace("+00:00", "").replace("+08:00", ""))
            elapsed = (now - upd_time).total_seconds() / 3600
            if elapsed > hours:
                stuck.append((rid, title, claimer, elapsed))
        except:
            stuck.append((rid, title, claimer, -1))
    if stuck:
        print(f"watchdog: 发现{len(stuck)}个超时任务(>{hours}h):")
        for rid, title, claimer, elapsed in stuck:
            print(f"  {rid} | {title} | 认领者:{claimer} | 已过{elapsed:.1f}h")
            if auto_reset:
                set_status(rid, "待处理")
                chat(rid, f"【系统】超时{elapsed:.0f}h，自动重置为待处理", "系统")
                print(f"    -> 已自动重置为待处理")
    else:
        print("watchdog: 无超时任务")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action")
    p.add_argument("rest", nargs="*")
    a = p.parse_args()
    if a.action == "push":
        # push <类型> <标题> <内容> [备注] [指派给] [优先级:高/中/低]
        push(a.rest[0], a.rest[1], a.rest[2],
             a.rest[3] if len(a.rest) > 3 else "",
             a.rest[4] if len(a.rest) > 4 else "",
             a.rest[5] if len(a.rest) > 5 else "中")
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
    elif a.action == "watchdog":
        # watchdog [小时数] [--auto]
        hrs = int(a.rest[0]) if a.rest and a.rest[0].isdigit() else 24
        auto = "--auto" in a.rest
        watchdog(hrs, auto)
    elif a.action == "dashboard":
        dashboard()
    elif a.action == "templates":
        list_templates()
    elif a.action == "template":
        # template <模板名> [key=value,...] [指派给]
        use_template(a.rest[0], a.rest[1] if len(a.rest) > 1 else "",
                     a.rest[2] if len(a.rest) > 2 else "")
    elif a.action == "rate":
        # rate <record_id> <1-5> [反馈]
        rate(a.rest[0], a.rest[1], " ".join(a.rest[2:]) if len(a.rest) > 2 else "")
    elif a.action == "fail":
        # fail <record_id> <原因>
        fail(a.rest[0], " ".join(a.rest[1:]), "云电脑")
    elif a.action == "ask":
        # ask <record_id> <问题>
        ask(a.rest[0], " ".join(a.rest[1:]), "云电脑")
    elif a.action == "register":
        # register <实例名> [标签1,标签2]
        register(a.rest[0], ",".join(a.rest[1:]) if len(a.rest) > 1 else "")
    elif a.action == "recommend":
        # recommend [任务类型]
        recommend(a.rest[0] if a.rest else "")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
