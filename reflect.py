# -*- coding: utf-8 -*-
"""
reflect.py — 自动反思检查器（文件层+行为层）
每次完成任务后运行，自动发现问题：
文件层：临时文件、硬编码、大文件、重复脚本
行为层：最近造轮子数量、脚本不合规(无try/except/无argparse)、重复函数定义、铁律违反
"""
import sys, io, os, glob, re, datetime, hashlib
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')

PROJECT = os.path.dirname(os.path.abspath(__file__))
ISSUES = []

def add(level, category, msg):
    ISSUES.append((level, category, msg))

def check_temp_files():
    now = datetime.datetime.now()
    for ext in ("_*.py", "_*.json", "_*.txt", "_*.html", "_*.csv"):
        for f in glob.glob(os.path.join(PROJECT, ext)):
            mtime = datetime.datetime.fromtimestamp(os.path.getmtime(f))
            age = (now - mtime).total_seconds() / 3600
            if age > 1:
                add("WARN", "临时文件", f"{os.path.basename(f)} 已存在{age:.0f}h，应删除")

def check_hardcoded():
    patterns = [
        (r'base_token\s*=\s*["\']MYQ', "飞书base_token硬编码"),
        (r'table_id\s*=\s*["\']tbl', "飞书table_id硬编码"),
        (r'ODOO_PWD\s*=\s*["\'][^"\']+["\']', "Odoo密码硬编码"),
        (r'api_key\s*=\s*["\'][a-zA-Z0-9]{20,}', "API key硬编码"),
        (r'["\'][a-f0-9]{40}["\']', "疑似token硬编码"),
    ]
    for f in glob.glob(os.path.join(PROJECT, "*.py")):
        if os.path.basename(f) in ("config.py", "config.example.py"):
            continue
        try:
            content = open(f, 'r', encoding='utf-8').read()
            for pat, desc in patterns:
                if re.search(pat, content):
                    add("WARN", "硬编码", f"{os.path.basename(f)}: {desc}")
        except:
            pass

def check_large_files():
    for f in glob.glob(os.path.join(PROJECT, "*.*")):
        if os.path.isfile(f):
            size = os.path.getsize(f) / 1024 / 1024
            if size > 10 and not f.endswith(('.db', '.json', '.m4a', '.zip', '.xlsx', '.pdf')):
                add("INFO", "大文件", f"{os.path.basename(f)} {size:.1f}MB")

def check_behavior():
    """行为层检查：脚本合规性、重复造轮子、铁律违反"""
    py_files = glob.glob(os.path.join(PROJECT, "*.py"))
    now = datetime.datetime.now()
    
    # 1. 最近24h新建的脚本（可能在重复造轮子）
    recent = []
    for f in py_files:
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(f))
        if (now - mtime).total_seconds() < 86400:
            recent.append(os.path.basename(f))
    if len(recent) > 5:
        add("WARN", "重复造轮子", f"最近24h新建/修改{len(recent)}个脚本: {', '.join(recent[:8])}，确认是否有重复功能")
    
    # 2. 脚本不合规：无try/except（违反"脚本try/except自消化"）
    for f in py_files:
        if os.path.basename(f).startswith("_") or os.path.basename(f) == "config.py":
            continue
        try:
            content = open(f, 'r', encoding='utf-8').read()
            if 'def ' in content and 'try:' not in content and len(content) > 200:
                add("INFO", "脚本不合规", f"{os.path.basename(f)}: 无try/except，违反自消化铁律")
        except:
            pass
    
    # 3. 重复函数定义（不同脚本里定义了同名函数，可能该合并）
    func_map = {}
    for f in py_files:
        if os.path.basename(f) in ("config.py",):
            continue
        try:
            content = open(f, 'r', encoding='utf-8').read()
            for m in re.finditer(r'^def (\w+)\(', content, re.MULTILINE):
                fname = m.group(1)
                if fname.startswith("_"):
                    continue
                func_map.setdefault(fname, []).append(os.path.basename(f))
        except:
            pass
    for fname, files in func_map.items():
        if len(files) > 2 and fname not in ("main", "cli", "add", "cell"):
            add("INFO", "重复函数", f"函数'{fname}'在{len(files)}个脚本中定义: {', '.join(set(files))}，考虑提取到公共模块")

def check_iron_rules():
    """铁律违反痕迹检查"""
    # 检查项目里有没有PowerShell内联Python的痕迹（.ps1文件里有python -c）
    for f in glob.glob(os.path.join(PROJECT, "*.ps1")):
        try:
            content = open(f, 'r', encoding='utf-8').read()
            if 'python -c' in content or 'python.exe -c' in content:
                add("WARN", "铁律违反", f"{os.path.basename(f)}: 含python -c内联，违反'写.py文件再执行'铁律")
        except:
            pass

def check_reuse():
    """复用/省token: 能力地图是否最新、norm 是否重复实现、临时脚本是否堆积。"""
    pys = [f for f in glob.glob(os.path.join(PROJECT, "*.py"))]
    idx = os.path.join(PROJECT, "SCRIPT_INDEX.md")
    if os.path.exists(idx):
        it = os.path.getmtime(idx)
        stale = [os.path.basename(f) for f in pys if os.path.getmtime(f) > it and not os.path.basename(f).startswith("_") and "backup" not in os.path.basename(f).lower()]
        if stale:
            add("WARN", "复用", "SCRIPT_INDEX 落后于脚本 %s，跑 build_script_index.py 刷新" % stale[:6])
    else:
        add("WARN", "复用", "缺 SCRIPT_INDEX.md，跑 python build_script_index.py 建能力地图(新任务先查它再动手)")
    dup = []
    for f in pys:
        bn = os.path.basename(f)
        if bn == "cn_stock.py" or bn.startswith("_"):
            continue
        t = open(f, encoding="utf-8", errors="ignore").read()
        if re.search(r"def norm\(", t) and "cn_stock" not in t and ("MARTYR" in t or re.search(r"-0\{?2", t)):
            dup.append(bn)
    if dup:
        add("INFO", "复用", "自定义 norm 未委托 cn_stock(口径漂移风险): %s" % dup)
    tmp = [os.path.basename(f) for f in pys if os.path.basename(f).startswith("_") and "backup" not in os.path.basename(f).lower()]
    if len(tmp) > 6:
        add("WARN", "复用", "%d 个 _ 临时脚本未清: %s" % (len(tmp), tmp[:8]))


def main():
    print("=" * 55)
    print("自动反思检查", datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    print("=" * 55)
    check_temp_files()
    check_hardcoded()
    check_large_files()
    check_behavior()
    check_iron_rules()
    check_reuse()
    if not ISSUES:
        print("\n✓ 未发现问题")
    else:
        for level, cat, msg in ISSUES:
            icon = {"ERROR": "✗", "WARN": "⚠", "INFO": "ℹ"}[level]
            print(f"  {icon} [{cat}] {msg}")
        e = len([i for i in ISSUES if i[0]=="ERROR"])
        w = len([i for i in ISSUES if i[0]=="WARN"])
        info = len([i for i in ISSUES if i[0]=="INFO"])
        print(f"\n汇总: {e}错误, {w}警告, {info}提示")
    print("=" * 55)

if __name__ == "__main__":
    main()
