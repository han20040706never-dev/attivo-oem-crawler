# -*- coding: utf-8 -*-
"""一键系统健康检查：输出本地daemon、云电脑实例、任务、零件库、token、通知全貌"""
import sys, io, os, json, datetime, subprocess, time
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
PROJECT = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

def run(args, timeout=30):
    try:
        r = subprocess.run([PY] + args, capture_output=True, text=True, timeout=timeout, encoding='utf-8', cwd=PROJECT)
        return r.stdout.strip()
    except Exception as e:
        return f"ERROR: {e}"

print("=" * 60)
print(f"  协作系统健康报告  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 60)

# 1. 本地daemon状态（用日志最后修改时间判断，避免psutil权限问题）
print("\n【本地daemon】")
log_file = os.path.join(PROJECT, "_daemon.log")
if os.path.exists(log_file):
    mtime = os.path.getmtime(log_file)
    age = (time.time() - mtime) / 60
    status = "运行中" if age < 10 else f"可能已停止({age:.0f}分钟无日志)"
    print(f"  状态: {status}")
else:
    print("  状态: 无日志文件")

# 2. 云电脑实例状态
print("\n【云电脑实例】")
try:
    reg_file = os.path.join(PROJECT, "instances.json")
    if os.path.exists(reg_file):
        reg = json.load(open(reg_file, 'r', encoding='utf-8'))
        now = datetime.datetime.now()
        for name, info in reg.get("instances", {}).items():
            last = info.get("last_seen", "")
            tags = info.get("tags", [])
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",")]
            completed = info.get("completed", 0)
            failed = info.get("failed", 0)
            active = info.get("active_tasks", 0)
            if last:
                try:
                    lt = datetime.datetime.fromisoformat(last.replace("Z", "+00:00").replace("+08:00", ""))
                    elapsed = (now - lt).total_seconds() / 60
                    status = "在线" if elapsed <= 30 else f"超时({elapsed:.0f}分钟)"
                except:
                    status = "心跳解析失败"
            else:
                status = "无心跳记录"
            print(f"  {name}: {status} | 完成{completed} 失败{failed} 进行中{active} | 标签:{','.join(tags)}")
except Exception as e:
    print(f"  读取失败: {e}")

# 3. 任务统计
print("\n【任务统计】")
try:
    pending_out = run(["sharedtask.py", "pending"], timeout=30)
    pending_count = pending_out.count("待处理") if "待处理" in pending_out else 0
    print(f"  待处理: {pending_count}")
    if pending_count > 0:
        for line in pending_out.split("\n")[:5]:
            if "待处理" in line:
                print(f"    {line[:80]}")
        if pending_count > 5:
            print(f"    ...还有{pending_count - 5}个")
except Exception as e:
    print(f"  查询失败: {e}")

# 4. 零件库
print("\n【零件库】")
try:
    import sqlite3
    db_path = os.path.join(PROJECT, "oemkb.db")
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM part")
        parts = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM section WHERE part_done=1")
        done = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM section")
        total = cur.fetchone()[0]
        conn.close()
        print(f"  零件数: {parts:,}")
        print(f"  分区进度: {done}/{total} ({done/total*100:.1f}%)" if total else "  分区进度: 无数据")
    else:
        print("  oemkb.db不存在")
except Exception as e:
    print(f"  查询失败: {e}")

# 5. 最近通知
print("\n【最近通知】")
try:
    notif_file = os.path.join(PROJECT, "_notifications.json")
    if os.path.exists(notif_file):
        notifs = json.load(open(notif_file, 'r', encoding='utf-8'))
        for n in notifs[-3:]:
            t = n.get("time", "")[:16]
            msg = n.get("msg", "")[:80]
            print(f"  [{t}] {msg}")
    else:
        print("  无通知")
except Exception as e:
    print(f"  读取失败: {e}")

# 6. 代码质量
print("\n【代码质量】")
try:
    cq_files = ["daemon.py", "sharedtask.py", "shared_mem.py", "auto_dispatch.py", "ai_router.py", "common.py", "code_quality_gate.py"]
    cq_existing = [f for f in cq_files if os.path.exists(os.path.join(PROJECT, f))]
    import py_compile
    cq_pass, cq_fail = 0, 0
    for f in cq_existing:
        try:
            py_compile.compile(os.path.join(PROJECT, f), doraise=True)
            cq_pass += 1
        except Exception:
            cq_fail += 1
            print(f"  ❌ {f}: 语法错误")
    print(f"  语法检查: {cq_pass}通过, {cq_fail}失败 (共{len(cq_existing)}个核心文件)")
    # 硬编码密钥扫描（config.py除外）
    import re
    secret_hits = 0
    for f in cq_existing:
        if f == "config.py":
            continue
        content = open(os.path.join(PROJECT, f), 'r', encoding='utf-8').read()
        if re.search(r'sk-[a-zA-Z0-9]{20,}', content) or re.search(r'ghp_[a-zA-Z0-9]{30,}', content):
            secret_hits += 1
            print(f"  ⚠️  {f}: 疑似硬编码密钥")
    if secret_hits == 0:
        print(f"  密钥扫描: 无硬编码密钥")
except Exception as e:
    print(f"  检查失败: {e}")

# 7. Token用量
print("\n【AI Token用量】")
try:
    token_file = os.path.join(PROJECT, "_token_usage.jsonl")
    if os.path.exists(token_file):
        lines = open(token_file, 'r', encoding='utf-8').readlines()
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        today_calls = sum(1 for l in lines if today in l)
        total_input = sum(json.loads(l).get("input_tokens", 0) for l in lines if l.strip())
        total_output = sum(json.loads(l).get("output_tokens", 0) for l in lines if l.strip())
        cost = total_input / 1e6 * 1 + total_output / 1e6 * 2  # DeepSeek价格
        print(f"  总调用: {len(lines)}次 (今日{today_calls}次)")
        print(f"  总token: 输入{total_input:,} + 输出{total_output:,}")
        print(f"  估算费用: ¥{cost:.2f} (DeepSeek API)")
    else:
        print("  无用量记录")
except Exception as e:
    print(f"  读取失败: {e}")

# 8. 云电脑待办AI任务
print("\n【云电脑待办AI任务】")
try:
    for inst_name in ["云电脑 价格监控", "云电脑 爬虫脚本", "开发助手"]:
        pending_file = os.path.join(PROJECT, f"_pending_ai_tasks.txt")
        if os.path.exists(pending_file):
            lines = [l.strip() for l in open(pending_file, 'r', encoding='utf-8').readlines() if l.strip()]
            if lines:
                print(f"  {inst_name}: {len(lines)}个待AI处理")
                for l in lines[:2]:
                    print(f"    {l[:70]}")
            else:
                print(f"  {inst_name}: 无待办")
        else:
            print(f"  {inst_name}: 无待办文件")
except Exception as e:
    print(f"  检查失败: {e}")

# 9. 代码版本
print("\n【代码版本】")
try:
    ver_file = os.path.join(PROJECT, "VERSION")
    if os.path.exists(ver_file):
        print(f"  版本: {open(ver_file).read().strip()}")
    # 检查关键文件是否存在
    key_files = ["daemon.py", "sharedtask.py", "shared_mem.py", "auto_dispatch.py", "ai_router.py", "check_done.py", "config.py"]
    missing = [f for f in key_files if not os.path.exists(os.path.join(PROJECT, f))]
    print(f"  关键文件: {'全部存在' if not missing else '缺失: ' + ','.join(missing)}")
except Exception as e:
    print(f"  检查失败: {e}")

print("\n" + "=" * 60)
