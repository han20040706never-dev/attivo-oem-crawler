# -*- coding: utf-8 -*-
"""
DeepSeek Harness - 多轮迭代编码助手
用法:
  python ds_harness.py "任务描述" [--file a.py --file b.py] [--iter 3] [--out result.py] [--auto]
  ax ds "任务描述" --file xxx.py --iter 3 --auto

流程: 注入文件上下文 → DeepSeek生成代码 → 提取代码块 → (可选)执行 → 报错回传 → 迭代修复
"""
import sys, io, os, re, json, argparse, subprocess, tempfile
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ai_router import code_helper, _call_openai, PROVIDERS

SYSTEM_PROMPT = """你是资深Python开发者，精通Odoo XML-RPC/JSON-RPC API、Windows PowerShell、爬虫和自动化脚本。
规则:
1. 只输出可直接运行的Python代码，用```python ... ```包裹
2. 代码必须: UTF-8编码、try/except自消化错误、argparse接口、进度输出、写完可直接跑
3. 如果任务需要读文件，用open(encoding='utf-8')
4. Windows路径用os.path.join，不要硬编码反斜杠
5. 报错时给出具体修复后的完整代码，不要只说"修改xxx行"
6. 不解释，直接给代码"""


def extract_code(text):
    """从回复中提取第一个python代码块"""
    m = re.search(r'```python\s*\n(.*?)```', text, re.DOTALL)
    if m:
        return m.group(1).strip()
    m = re.search(r'```\s*\n(.*?)```', text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return None


def run_code(code, timeout=60):
    """执行Python代码，返回(stdout, stderr, returncode)"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
        f.write('# -*- coding: utf-8 -*-\nimport sys, io\nsys.stdout=io.TextIOWrapper(sys.stdout.detach(),encoding="utf-8")\n')
        f.write(code)
        path = f.name
    try:
        r = subprocess.run(
            [sys.executable, path],
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            timeout=timeout, cwd=os.path.dirname(os.path.abspath(__file__))
        )
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except subprocess.TimeoutExpired:
        return "", "TIMEOUT after %ds" % timeout, -1
    finally:
        try: os.unlink(path)
        except: pass


def build_context(files):
    """读取相关文件内容作为上下文"""
    ctx = []
    for f in files:
        if os.path.exists(f):
            content = open(f, encoding='utf-8', errors='replace').read()
            if len(content) > 8000:
                content = content[:8000] + "\n...(截断，共%d字)" % len(content)
            ctx.append("=== %s ===\n%s" % (os.path.basename(f), content))
        else:
            ctx.append("=== %s === (文件不存在)" % f)
    return "\n\n".join(ctx)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("task", help="任务描述")
    ap.add_argument("--file", action="append", default=[], help="相关文件路径（可多次）")
    ap.add_argument("--iter", type=int, default=2, help="最大迭代次数（默认2）")
    ap.add_argument("--out", default=None, help="最终代码保存路径")
    ap.add_argument("--auto", action="store_true", help="自动执行并回传报错迭代修复")
    ap.add_argument("--model", default=None, help="指定provider（默认deepseek）")
    args = ap.parse_args()

    context = build_context(args.file)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]
    user_msg = args.task
    if context:
        user_msg += "\n\n相关文件:\n" + context
    messages.append({"role": "user", "content": user_msg})

    final_code = None
    for i in range(1, args.iter + 1):
        print("=== 迭代 %d/%d ===" % (i, args.iter))
        # 直接用_call_openai走deepseek，支持多轮messages
        provider = args.model or "deepseek"
        p = PROVIDERS.get(provider)
        if not p or not p.get("key"):
            print("FAIL: provider %s 不可用" % provider)
            return
        reply = _call_openai(provider, messages, max_tokens=4096, temperature=0.3)
        if not reply:
            print("FAIL: DeepSeek无回复")
            return
        messages.append({"role": "assistant", "content": reply})
        code = extract_code(reply)
        if not code:
            print("回复中无代码块，原始回复:")
            print(reply[:500])
            return
        final_code = code
        print("生成代码 %d 字" % len(code))

        if not args.auto:
            break  # 非自动模式，只生成一次

        # 自动执行
        stdout, stderr, rc = run_code(code, timeout=120)
        if rc == 0:
            print("执行成功!")
            if stdout:
                print("stdout:", stdout[:500])
            break
        else:
            print("执行失败 (rc=%d)" % rc)
            print("stderr:", stderr[:800])
            # 回传报错，请求修复
            messages.append({
                "role": "user",
                "content": "代码执行失败，报错如下，请给出修复后的完整代码:\n\nSTDERR:\n%s\n\nSTDOUT:\n%s" % (stderr[:1500], stdout[:500])
            })
            print("回传报错，请求修复...")
    else:
        print("达到最大迭代次数，仍有错误")

    if final_code:
        if args.out:
            with open(args.out, 'w', encoding='utf-8') as f:
                f.write('# -*- coding: utf-8 -*-\n')
                f.write(final_code)
            print("代码已保存: %s" % args.out)
        else:
            print("\n=== 最终代码 ===")
            print(final_code)


if __name__ == "__main__":
    main()
