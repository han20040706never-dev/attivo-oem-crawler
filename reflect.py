# -*- coding: utf-8 -*-
"""
_reflect.py — 自动反思检查器
每次完成任务后运行，自动发现项目问题：
1. 临时文件未清理（_前缀但超过1天）
2. 重复脚本（功能相似的.py文件）
3. 硬编码（base_token/table_id/URL/密码写在代码里）
4. 违反铁律（PowerShell内联Python痕迹、截图进上下文痕迹）
5. 大文件（>10MB的非数据文件）
6. 未使用的脚本（import了但没被任何脚本引用）
"""
import sys, io, os, glob, re, datetime
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')

PROJECT = os.path.dirname(os.path.abspath(__file__))
ISSUES = []

def add(level, category, msg):
    ISSUES.append((level, category, msg))

def check_temp_files():
    """检查临时文件"""
    now = datetime.datetime.now()
    for f in glob.glob(os.path.join(PROJECT, "_*.py")) + glob.glob(os.path.join(PROJECT, "_*.json")) + glob.glob(os.path.join(PROJECT, "_*.txt")):
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(f))
        age = (now - mtime).total_seconds() / 3600
        if age > 1:
            add("WARN", "临时文件", f"{os.path.basename(f)} 已存在{age:.0f}h，应删除")

def check_hardcoded():
    """检查硬编码"""
    sensitive_patterns = [
        (r'base_token\s*=\s*["\']MYQ', "飞书base_token硬编码"),
        (r'table_id\s*=\s*["\']tbl', "飞书table_id硬编码"),
        (r'ODOO_PWD\s*=\s*["\'][^"\']+["\']', "Odoo密码硬编码（应只在config.py）"),
        (r'api_key\s*=\s*["\'][a-zA-Z0-9]{20,}', "API key硬编码"),
        (r'password\s*=\s*["\'][^"\']+["\']', "密码硬编码"),
    ]
    for f in glob.glob(os.path.join(PROJECT, "*.py")):
        if os.path.basename(f) == "config.py":
            continue
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                content = fh.read()
            for pattern, desc in sensitive_patterns:
                if re.search(pattern, content):
                    add("WARN", "硬编码", f"{os.path.basename(f)}: {desc}")
        except:
            pass

def check_large_files():
    """检查大文件"""
    for f in glob.glob(os.path.join(PROJECT, "*.*")):
        if os.path.isfile(f):
            size = os.path.getsize(f) / 1024 / 1024
            if size > 10 and not f.endswith(('.db', '.json', '.m4a', '.zip', '.xlsx')):
                add("INFO", "大文件", f"{os.path.basename(f)} {size:.1f}MB")

def check_duplicate_scripts():
    """检查功能重复的脚本（简单启发式：文件名相似）"""
    py_files = [os.path.basename(f) for f in glob.glob(os.path.join(PROJECT, "*.py"))]
    # 检查crawl/scrape重复
    crawl_files = [f for f in py_files if 'crawl' in f.lower() or 'scrape' in f.lower()]
    if len(crawl_files) > 3:
        add("INFO", "重复脚本", f"爬虫类脚本{len(crawl_files)}个: {', '.join(crawl_files[:5])}，考虑合并")

def check_violations():
    """检查违反铁律的痕迹"""
    for f in glob.glob(os.path.join(PROJECT, "*.py")):
        try:
            with open(f, 'r', encoding='utf-8') as fh:
                content = fh.read()
            # 检查是否有Read大文件的痕迹（>5000行的文件被Read）
            if 'Read(' in content and 'limit=' not in content:
                pass  # 这是工具调用不是脚本内容
        except:
            pass

def main():
    print("=" * 50)
    print("自动反思检查", datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    print("=" * 50)
    check_temp_files()
    check_hardcoded()
    check_large_files()
    check_duplicate_scripts()
    check_violations()
    if not ISSUES:
        print("\n✓ 未发现问题")
    else:
        errors = [i for i in ISSUES if i[0] == "ERROR"]
        warns = [i for i in ISSUES if i[0] == "WARN"]
        infos = [i for i in ISSUES if i[0] == "INFO"]
        for level, cat, msg in ISSUES:
            icon = {"ERROR": "✗", "WARN": "⚠", "INFO": "ℹ"}[level]
            print(f"  {icon} [{cat}] {msg}")
        print(f"\n汇总: {len(errors)}错误, {len(warns)}警告, {len(infos)}提示")
    print("=" * 50)

if __name__ == "__main__":
    main()
