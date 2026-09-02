# -*- coding: utf-8 -*-
"""
healthcheck.py — 协作系统健康自检
主动诊断：任务卡死、经验冗余、配置完整性、版本最新性、API可用性
不需要用户提醒，定期运行即可发现问题
"""
import sys, io, os, json, subprocess, datetime
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
PROJECT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT)
from common import cli, cell
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE = "MYQybnKkZaXY2Yswagyc7pKNnRf"
TASK_TABLE = "tblGwGpuGna0zGQG"
MEM_TABLE = "tbl2oncwMgoSEUl4"
REPO = "han20040706never-dev/attivo-oem-crawler"

def check_tasks():
    """检查任务：卡死、无认领者、长期待处理"""
    issues = []
    data = cli(["+record-list", "--base-token", BASE, "--table-id", TASK_TABLE,
                "--limit", "100", "--format", "json", "--as", "user"])
    if not data.get("ok"):
        return [("任务表", "ERROR", "无法读取任务表")]
    d = data.get("data", {})
    rows, cols = d.get("data", []), d.get("fields", [])
    idx = {name: i for i, name in enumerate(cols)}
    now = datetime.datetime.now()
    for row in rows:
        def g(name):
            i = idx.get(name, -1)
            return row[i] if 0 <= i < len(row) else ""
        rid = d.get("record_id_list", [])[rows.index(row)] if rows.index(row) < len(d.get("record_id_list", [])) else "?"
        status = cell(g("状态"))
        title = cell(g("任务标题"))
        upd = cell(g("更新时间"))
        assignee = cell(g("指派给"))
        remark = cell(g("备注"))
        claimer = ""
        for line in remark.split("\n"):
            if "认领者:" in line:
                claimer = line.split("认领者:")[-1].strip()
        try:
            upd_time = datetime.datetime.fromisoformat(upd.replace("Z", "").replace("+00:00", "").replace("+08:00", ""))
            hours = (now - upd_time).total_seconds() / 3600
        except:
            hours = -1
        if status == "处理中" and hours > 24:
            issues.append(("任务卡死", "WARN", f"{rid} {title} 处理中{hours:.0f}h 认领者:{claimer}"))
        if status == "待处理" and hours > 72:
            issues.append(("任务积压", "INFO", f"{rid} {title} 待处理{hours:.0f}h 指派:{assignee}"))
        if status == "处理中" and not claimer:
            issues.append(("无认领者", "WARN", f"{rid} {title} 处理中但无认领者记录"))
    return issues

def check_memory():
    """检查共享记忆：冗余、空内容"""
    issues = []
    data = cli(["+record-list", "--base-token", BASE, "--table-id", MEM_TABLE,
                "--limit", "100", "--format", "json", "--as", "user"])
    if not data.get("ok"):
        return [("记忆表", "ERROR", "无法读取记忆表")]
    d = data.get("data", {})
    rows, cols = d.get("data", []), d.get("fields", [])
    idx = {name: i for i, name in enumerate(cols)}
    titles = []
    for row in rows:
        def g(name):
            i = idx.get(name, -1)
            return row[i] if 0 <= i < len(row) else ""
        title = cell(g("标题"))
        content = cell(g("内容"))
        if title:
            titles.append(title)
        if not content or len(content) < 10:
            issues.append(("记忆空内容", "INFO", f"标题:{title} 内容过短"))
    # 检测重复标题
    seen = {}
    for t in titles:
        seen[t] = seen.get(t, 0) + 1
    for t, c in seen.items():
        if c > 1:
            issues.append(("记忆重复", "INFO", f"标题'{t}'出现{c}次"))
    return issues

def check_config():
    """检查配置完整性"""
    issues = []
    cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.py")
    if not os.path.exists(cfg_path):
        return [("配置", "ERROR", "config.py不存在")]
    with open(cfg_path, 'r', encoding='utf-8') as f:
        content = f.read()
    required = ["DEEPSEEK", "GITHUB_PAT", "ODOO"]
    for key in required:
        if key not in content:
            issues.append(("配置缺失", "WARN", f"config.py中未找到{key}"))
    return issues

def check_version():
    """检查版本是否最新"""
    issues = []
    try:
        import requests
        r = requests.get(f"https://raw.githubusercontent.com/{REPO}/main/VERSION", timeout=5)
        latest = r.text.strip()
        local = "1.2.0"
        vfile = os.path.join(os.path.dirname(os.path.abspath(__file__)), "VERSION")
        if os.path.exists(vfile):
            with open(vfile, 'r') as f:
                local = f.read().strip()
        if latest != local:
            issues.append(("版本过期", "WARN", f"本地{local}，最新{latest}，运行cloud_setup.ps1更新"))
        else:
            issues.append(("版本", "OK", f"v{local} 已是最新"))
    except Exception as e:
        issues.append(("版本检查", "INFO", f"无法检查: {e}"))
    return issues

def check_apis():
    """检查关键API可用性"""
    issues = []
    # DeepSeek
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from ai_router import chat
        r = chat("回复OK", provider="zhipu")
        if r and "OK" in r.upper():
            issues.append(("智谱API", "OK", "正常"))
        else:
            issues.append(("智谱API", "WARN", "响应异常"))
    except Exception as e:
        issues.append(("智谱API", "WARN", f"不可用: {e}"))
    return issues

def main():
    print("=" * 50)
    print("协作系统健康自检", datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    print("=" * 50)
    all_issues = []
    for name, check_fn in [("任务", check_tasks), ("记忆", check_memory),
                           ("配置", check_config), ("版本", check_version),
                           ("API", check_apis)]:
        print(f"\n--- {name} ---")
        try:
            issues = check_fn()
            if not issues:
                print("  无问题")
            for level, sev, msg in issues:
                icon = {"OK": "✓", "WARN": "⚠", "ERROR": "✗", "INFO": "ℹ"}.get(sev, "?")
                print(f"  {icon} [{sev}] {msg}")
            all_issues.extend(issues)
        except Exception as e:
            print(f"  检查失败: {e}")
    print("\n" + "=" * 50)
    errors = [i for i in all_issues if i[1] == "ERROR"]
    warns = [i for i in all_issues if i[1] == "WARN"]
    print(f"汇总: {len(errors)}个错误, {len(warns)}个警告, {len(all_issues)-len(errors)-len(warns)}个提示")
    if errors:
        print("结论: 有严重问题，需要立即处理")
    elif warns:
        print("结论: 基本正常，有警告需关注")
    else:
        print("结论: 系统健康")

if __name__ == "__main__":
    main()
