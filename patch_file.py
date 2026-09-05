# -*- coding: utf-8 -*-
"""
通用“定点补丁”工具 —— 替代每次手写 str.replace 驱动，规避 PowerShell 命令行引号 / f-string 花括号转义地狱。

用法示例:
    python patch_file.py 补丁.json
        # json = [{"file": "a.py", "subs": [["旧串", "新串"], ...]}, ...]
        # 可一次多文件多组

    python patch_file.py a.py --old-file o.txt --new-file n.txt
        # 单组、长文本走文件，不在命令行内联

规则:
- file 相对路径相对 TOOL，也接受绝对路径。
- 每个文件：先读源码 s；对每组 (old, new) 断言 s.count(old)==1，
  若不等于1，打印 FAIL 及实际命中次数并【完全不写该文件】
  (多组时在内存依次 apply，全部恰好命中1次才落盘，保证半失败不留脏文件)。
- 落盘前自动备份到 <file>.backup_YYYYMMDD (已存在同名备份则不重复覆盖)。
- 目标文件名以 .py 结尾时，落盘前先写到临时文件 py_compile.compile(doraise=True)，
  编译失败则回滚(用备份还原)并打印 FAIL+错误前80字符；通过才 os.replace。
- 非 .py 文件直接写。结尾打印每个文件 OK 文件名 替换N组，以及总 OK/FAIL 数；
  有任何 FAIL 进程退出码=1。
- json 用 utf-8 读；--old-file/--new-file 用 utf-8 读，原样保留换行。
"""

import sys
import os
import io
import json
import shutil
import datetime
import tempfile
import py_compile

# stdout 用 utf-8 包装，避免 Windows 控制台编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8')

TOOL = os.path.dirname(os.path.abspath(__file__))


def _backup_file(filepath):
    """生成备份文件名并执行备份（若备份已存在则不重复覆盖）。"""
    date_str = datetime.datetime.now().strftime('%Y%m%d')
    backup_path = f"{filepath}.backup_{date_str}"
    if not os.path.exists(backup_path):
        shutil.copy2(filepath, backup_path)
    return backup_path


def _apply_subs(content, subs):
    """在内存中依次应用所有替换，全部恰好命中1次才返回新内容，否则返回 None。"""
    new_content = content
    for old, new in subs:
        cnt = new_content.count(old)
        if cnt != 1:
            print(f"FAIL: 替换串命中次数={cnt} (期望1) | 旧串前40字符: {old[:40]!r}")
            return None
        new_content = new_content.replace(old, new)
    return new_content


def _write_py_file_safely(filepath, new_content):
    """对 .py 文件：先写临时文件并 py_compile 验证，通过才 os.replace；失败回滚。"""
    backup_path = _backup_file(filepath)
    tmp_fd, tmp_path = tempfile.mkstemp(suffix='.py', dir=os.path.dirname(filepath) or '.')
    try:
        with os.fdopen(tmp_fd, 'w', encoding='utf-8') as f:
            f.write(new_content)
        # 编译验证
        try:
            py_compile.compile(tmp_path, doraise=True)
        except py_compile.PyCompileError as e:
            err_msg = str(e)[:80]
            # 回滚：用备份还原原文件
            shutil.copy2(backup_path, filepath)
            print(f"FAIL: py_compile 错误 | {filepath} | {err_msg}")
            return False
        # 编译通过，替换原文件
        os.replace(tmp_path, filepath)
        return True
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def _write_non_py_file(filepath, new_content):
    """非 .py 文件直接写（先备份）。"""
    _backup_file(filepath)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)
    return True


def process_one_file(filepath, subs):
    """处理单个文件，返回 (ok, group_count)。"""
    if not os.path.isabs(filepath):
        filepath = os.path.join(TOOL, filepath)
    if not os.path.isfile(filepath):
        print(f"FAIL: 文件不存在 {filepath}")
        return False, 0

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"FAIL: 读取文件错误 {filepath} | {str(e)[:80]}")
        return False, 0

    new_content = _apply_subs(content, subs)
    if new_content is None:
        # 不写文件，直接失败
        return False, len(subs)

    # 落盘
    try:
        if filepath.endswith('.py'):
            ok = _write_py_file_safely(filepath, new_content)
        else:
            ok = _write_non_py_file(filepath, new_content)
        return ok, len(subs)
    except Exception as e:
        print(f"FAIL: 写入文件错误 {filepath} | {str(e)[:80]}")
        return False, len(subs)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    # 解析参数
    if sys.argv[1].endswith('.json'):
        # JSON 模式
        json_path = sys.argv[1]
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                tasks = json.load(f)
        except Exception as e:
            print(f"FAIL: 读取 JSON 失败 {json_path} | {str(e)[:80]}")
            sys.exit(1)
    else:
        # 单文件模式: python patch_file.py a.py --old-file o.txt --new-file n.txt
        if len(sys.argv) != 5 or '--old-file' not in sys.argv or '--new-file' not in sys.argv:
            print("用法: python patch_file.py <file> --old-file <old.txt> --new-file <new.txt>")
            sys.exit(1)
        file_arg = sys.argv[1]
        old_file = sys.argv[sys.argv.index('--old-file') + 1]
        new_file = sys.argv[sys.argv.index('--new-file') + 1]
        try:
            with open(old_file, 'r', encoding='utf-8') as f:
                old_str = f.read()
            with open(new_file, 'r', encoding='utf-8') as f:
                new_str = f.read()
        except Exception as e:
            print(f"FAIL: 读取 old/new 文件失败 | {str(e)[:80]}")
            sys.exit(1)
        tasks = [{"file": file_arg, "subs": [[old_str, new_str]]}]

    total_ok = 0
    total_fail = 0

    for task in tasks:
        filepath = task.get('file', '')
        subs = task.get('subs', [])
        if not filepath or not subs:
            print(f"FAIL: 任务缺少 file 或 subs | {filepath}")
            total_fail += 1
            continue
        ok, group_count = process_one_file(filepath, subs)
        if ok:
            print(f"OK {filepath} 替换{group_count}组")
            total_ok += 1
        else:
            total_fail += 1

    print(f"\n总计: OK={total_ok} FAIL={total_fail}")
    if total_fail > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
