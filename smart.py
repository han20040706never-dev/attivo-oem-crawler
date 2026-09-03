# -*- coding: utf-8 -*-
"""smart.py - 省token智能中枢"""
import argparse, os, sys, re, subprocess, traceback, py_compile, difflib
from datetime import datetime
from config import DEEPSEEK_KEY

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "smart_err.log")

def _log_err(e):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n[{datetime.now()}] {traceback.format_exc()}")

def _fail(msg):
    print(f"FAIL: {msg}")
    sys.exit(1)

def _try_import(mod_name):
    try:
        return __import__(mod_name)
    except Exception as e:
        _log_err(e)
        return None

# ============ 路由规则 ============
ROUTE_RULES = [
    # (关键词列表, 通道, 命令模板)
    (["录音转写", "录音总结", "业务判断", "最终判断", "决策", "odoo写入", "odoo写", "写入odoo"], "豆包亲自", "豆包亲自(铁律不外包)"),
    (["代码", "debug", "调试", "报错", "异常", "重构", "脚本", "函数", "正则", "bug", "修复", "优化", "syntaxerror", "exception", "traceback", "崩溃", "跑不起来", "跑不通", "语法错", "改代码", "写脚本"], "DeepSeek", "python ds_harness.py"),
    (["分类", "抽取", "摘要", "翻译", "打标签", "标签", "总结", "概括", "归纳"], "免费AI", "python ax.py ai"),
    (["通行费", "高速费"], "本地", "python ax.py toll"),
    (["爬虫", "抓取", "公开信息", "价格监控", "价格", "长耗时", "数据整理"], "云电脑", "sharedtask.push"),
    (["odoo线索", "商机", "联系人", "报销", "备注", "价格表", "库存", "配件", "线索", "客户"], "本地", "ax.py"),
]

def decide(desc):
    """智能路由决策，返回一行结论"""
    desc_lower = desc.lower()
    for keywords, channel, cmd in ROUTE_RULES:
        for kw in keywords:
            if kw.lower() in desc_lower:
                if channel == "云电脑":
                    assignee = "云电脑 爬虫脚本" if any(k in desc for k in ["爬虫", "抓取"]) else "云电脑 价格监控"
                    return f"云电脑 -> python -c \"import sharedtask; sharedtask.push('数据整理','{desc[:50]}','{desc}',assignee='{assignee}')\""
                if channel == "本地":
                    return f"本地 -> python ax.py {_match_ax_cmd(desc)}"
                return f"{channel} -> {cmd}"
    return "豆包亲自 -> 豆包亲自(铁律不外包)"

def _match_ax_cmd(desc):
    """匹配本地ax.py命令"""
    mapping = {
        "线索": "newlead", "商机": "opp", "联系人": "customer",
        "报销": "expense", "备注": "note", "价格表": "pricelist",
        "库存": "stock", "配件": "sync", "客户": "customer"
    }
    for k, v in mapping.items():
        if k in desc:
            return v
    return "sync"

# ============ dsedit ============
def _strip_code_fence(text):
    """剥离markdown代码围栏"""
    text = re.sub(r'^\s*$', '', text, flags=re.MULTILINE)
    return text.strip()

def _gen_diff(old, new, filepath):
    """生成unified diff"""
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff = difflib.unified_diff(old_lines, new_lines, fromfile=f"{filepath} (old)", tofile=f"{filepath} (new)")
    return ''.join(diff)

def ds_edit(files, requirement, apply=False):
    """多文件AI编辑"""
    ai_router = _try_import("ai_router")
    if not ai_router:
        _fail("ai_router模块不可用")

    for fpath in files:
        try:
            if not os.path.exists(fpath):
                print(f"FAIL: {fpath} 不存在")
                continue
            with open(fpath, "r", encoding="utf-8") as f:
                original = f.read()
            orig_lines = len(original.splitlines())

            prompt = f"请修改以下文件以满足需求。只输出完整修改后的文件内容，不要markdown代码围栏，不要任何解释。\n需求: {requirement}\n\n文件内容:\n{original}"
            result = ai_router.code_helper(prompt, max_tokens=8000)
            if not result:
                print(f"FAIL: {fpath} AI无返回")
                continue

            new_content = _strip_code_fence(result)
            if new_content == original:
                print(f"{fpath} 原{orig_lines}行->新{orig_lines}行 diff 0行 (无变化)")
                continue

            new_lines = len(new_content.splitlines())
            diff_text = _gen_diff(original, new_content, fpath)
            diff_lines = len(diff_text.splitlines())

            new_file = fpath + ".new"
            diff_file = fpath + ".diff"
            with open(new_file, "w", encoding="utf-8") as f:
                f.write(new_content)
            with open(diff_file, "w", encoding="utf-8") as f:
                f.write(diff_text)

            if apply:
                try:
                    py_compile.compile(new_file, doraise=True)
                    os.replace(new_file, fpath)
                    os.remove(diff_file)
                    print(f"{fpath} 原{orig_lines}行->新{new_lines}行 diff {diff_lines}行 (已应用)")
                except Exception as e:
                    print(f"FAIL: {fpath} 编译错误: {str(e)[:50]}")
            else:
                print(f"{fpath} 原{orig_lines}行->新{new_lines}行 diff {diff_lines}行 (新增/删除)")
        except Exception as e:
            _log_err(e)
            print(f"FAIL: {fpath} {str(e)[:50]}")

# ============ 自测 ============
def _selftest_route():
    """路由自测"""
    test_cases = [
        ("帮我写个python函数计算斐波那契", "DeepSeek"),
        ("这段代码报错了，帮我debug", "DeepSeek"),
        ("把这段英文翻译成中文", "免费AI"),
        ("总结一下这个文档的要点", "免费AI"),
        ("爬取京东上的配件价格", "云电脑"),
        ("监控亚马逊的价格变化", "云电脑"),
        ("新建一个odoo线索", "本地"),
        ("添加一个客户联系人", "本地"),
        ("录音转写后的总结", "豆包亲自"),
        ("这个业务决策你来判断", "豆包亲自"),
        ("优化一下这个正则表达式", "DeepSeek"),
        ("给这些配件打标签", "免费AI"),
    ]
    passed = 0
    for desc, expected in test_cases:
        result = decide(desc)
        ok = expected in result
        if ok:
            passed += 1
        else:
            print(f"FAIL: '{desc}' -> '{result}' (期望{expected})")
    print(f"路由自测: {passed}/{len(test_cases)} 通过")
    return passed == len(test_cases)

def _selftest_dsedit():
    """dsedit干跑自测"""
    if not bool(DEEPSEEK_KEY):
        print("SKIP: 无DEEPSEEK_KEY，跳过dsedit自测")
        return True
    # 创建临时测试文件
    test_file = "_test_tmp.py"
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("def hello():\n    return 'old'\n")
    try:
        ds_edit([test_file], "把返回值改成'new'", apply=False)
        # 检查.new文件
        if os.path.exists(test_file + ".new"):
            print("dsedit干跑: PASS")
            os.remove(test_file + ".new")
            if os.path.exists(test_file + ".diff"):
                os.remove(test_file + ".diff")
            return True
        else:
            print("dsedit干跑: FAIL")
            return False
    finally:
        if os.path.exists(test_file):
            os.remove(test_file)

def selftest():
    """完整自测"""
    route_ok = _selftest_route()
    dsedit_ok = _selftest_dsedit()
    if route_ok and dsedit_ok:
        print("全部自测通过")
    else:
        print("部分自测失败")

# ============ main ============
def main():
    parser = argparse.ArgumentParser(description="smart.py 省token智能中枢")
    subparsers = parser.add_subparsers(dest="command")

    # route子命令
    p_route = subparsers.add_parser("route", help="智能路由")
    p_route.add_argument("desc", help="任务描述")
    p_route.add_argument("--self-test", action="store_true", help="运行路由自测")

    # dsedit子命令
    p_dsedit = subparsers.add_parser("dsedit", help="AI编辑文件")
    p_dsedit.add_argument("files", nargs="+", help="要编辑的文件")
    p_dsedit.add_argument("-m", "--message", required=True, help="修改需求")
    p_dsedit.add_argument("--apply", action="store_true", help="应用修改")

    # selftest子命令
    subparsers.add_parser("selftest", help="运行自测")

    args = parser.parse_args()

    try:
        if args.command == "route":
            if args.self_test:
                _selftest_route()
            else:
                print(decide(args.desc))
        elif args.command == "dsedit":
            ds_edit(args.files, args.message, args.apply)
        elif args.command == "selftest":
            selftest()
        else:
            parser.print_help()
    except Exception as e:
        _log_err(e)
        _fail(str(e)[:80])

if __name__ == "__main__":
    main()