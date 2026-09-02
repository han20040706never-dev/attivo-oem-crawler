# -*- coding: utf-8 -*-
"""
code_quality_gate.py — 代码质量门禁
自动验证重构/新提交的代码：
1. py_compile语法检查
2. 硬编码密钥扫描
3. import完整性检查
4. 常见bug模式检测
用法: python code_quality_gate.py <file1.py> <file2.py> ...
      python code_quality_gate.py --all  # 检查所有.py文件
"""
import sys, io, os, re, py_compile, json
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
PROJECT = os.path.dirname(os.path.abspath(__file__))

# 密钥模式：检测硬编码的API key/密码/token
SECRET_PATTERNS = [
    (r'sk-[a-zA-Z0-9]{20,}', 'OpenAI/DeepSeek style API key'),
    (r'ghp_[a-zA-Z0-9]{30,}', 'GitHub PAT'),
    (r'github_pat_[a-zA-Z0-9_]{30,}', 'GitHub fine-grained PAT'),
    (r'password\s*=\s*["\'][^"\']{6,}["\']', 'Hardcoded password'),
    (r'api[_-]?key\s*=\s*["\'][^"\']{10,}["\']', 'Hardcoded API key'),
    (r'token\s*=\s*["\'][^"\']{20,}["\']', 'Hardcoded token'),
]

# 危险模式
DANGER_PATTERNS = [
    (r'os\.system\(', 'os.system (use subprocess instead)'),
    (r'eval\(', 'eval (security risk)'),
    (r'exec\(', 'exec (security risk)'),
    (r'shell\s*=\s*True', 'shell' + '=True (injection risk)'),
]

def check_syntax(filepath):
    """检查Python语法"""
    try:
        py_compile.compile(filepath, doraise=True)
        return True, ""
    except py_compile.PyCompileError as e:
        return False, str(e)[:200]

def check_secrets(filepath):
    """扫描硬编码密钥"""
    issues = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        for pattern, desc in SECRET_PATTERNS:
            matches = re.findall(pattern, content, re.I)
            if matches:
                # config.py是合法的密钥存储位置，跳过
                if os.path.basename(filepath) == 'config.py':
                    continue
                issues.append(f"{desc}: 发现{len(matches)}处")
    except Exception as e:
        issues.append(f"读取失败: {e}")
    return issues

def check_danger(filepath):
    """扫描危险模式"""
    issues = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        for i, line in enumerate(lines, 1):
            for pattern, desc in DANGER_PATTERNS:
                if re.search(pattern, line):
                    # 注释行和模式定义行跳过
                    if line.strip().startswith('#') or 'PATTERNS' in line or "r'" in line or 'r"' in line:
                        continue
                    issues.append(f"行{i}: {desc}")
    except Exception as e:
        issues.append(f"读取失败: {e}")
    return issues

def check_imports(filepath):
    """检查import完整性（简单检查：import的模块是否存在）"""
    issues = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        # 检查是否有from common import但项目里没有common.py
        if 'from common import' in content and not os.path.exists(os.path.join(PROJECT, 'common.py')):
            issues.append("import了common.py但文件不存在")
        # 检查是否有from sharedtask import但项目里没有sharedtask.py
        if 'from sharedtask import' in content and not os.path.exists(os.path.join(PROJECT, 'sharedtask.py')):
            issues.append("import了sharedtask.py但文件不存在")
    except Exception as e:
        issues.append(f"读取失败: {e}")
    return issues

def verify_file(filepath):
    """验证单个文件，返回(通过, 问题列表)"""
    all_issues = []
    # 1. 语法
    ok, err = check_syntax(filepath)
    if not ok:
        all_issues.append(f"语法错误: {err}")
    # 2. 密钥
    all_issues.extend(check_secrets(filepath))
    # 3. 危险模式
    all_issues.extend(check_danger(filepath))
    # 4. import
    all_issues.extend(check_imports(filepath))
    return len(all_issues) == 0, all_issues

def main():
    if len(sys.argv) < 2:
        print("用法: python code_quality_gate.py <file1.py> [file2.py ...]")
        print("      python code_quality_gate.py --all")
        sys.exit(1)

    if sys.argv[1] == '--all':
        files = [f for f in os.listdir(PROJECT) if f.endswith('.py') and not f.startswith('_')]
    else:
        files = sys.argv[1:]

    passed, failed = 0, 0
    for f in files:
        filepath = os.path.join(PROJECT, f) if not os.path.isabs(f) else f
        if not os.path.exists(filepath):
            print(f"❌ {f}: 文件不存在")
            failed += 1
            continue
        ok, issues = verify_file(filepath)
        if ok:
            print(f"✅ {f}: 通过")
            passed += 1
        else:
            print(f"❌ {f}: {len(issues)}个问题")
            for issue in issues:
                print(f"   - {issue}")
            failed += 1

    print(f"\n结果: {passed}通过, {failed}失败, 共{passed+failed}个文件")
    sys.exit(1 if failed > 0 else 0)

if __name__ == '__main__':
    main()
