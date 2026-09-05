# -*- coding: utf-8 -*-
"""plan.py — 动手前"节能/复用"规划器(零token, 新任务第一步)。
接到任务先 ax plan "任务", 强制三问:
  1) 有现成的吗?  -> script_match 现有脚本 + task_memory 历史方案
  2) 会重复吗?    -> 命中重复信号: 直接写【参数化可复用脚本】(带入口+try), 不写一次性临时码
  3) 烧token吗?   -> 命中重信号: 文件/截图/批量/长文本走本地脚本只回传结果, 不进豆包上下文, 用缓存
最后给 AI 通道建议 + 提醒做完 ax did 沉淀。
用法: python plan.py "任务描述"  或  import plan; plan.plan("任务")
"""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 重复信号: 出现就说明这事大概率要再做, 值得一次做成可复用脚本
REPEAT_SIGNALS = ["每次", "每天", "每周", "每月", "定期", "定时", "例行", "常规", "批量",
                  "一批", "多个", "所有", "全部", "逐个", "逐一", "统一", "又", "再", "经常",
                  "报表", "台账", "清单", "汇总", "周报", "月报", "每次都", "各家", "每个客户"]
# 烧token信号: 直接进上下文会爆, 必须本地脚本/缓存/OCR 只回传结果
HEAVY_SIGNALS = ["截图", "长图", "图片", "照片", "扫描件", "pdf", "大文件", "上千", "1400",
                 "大量", "整个文件夹", "所有文件", "网页", "爬", "全文翻译", "录音", "视频",
                 "excel", "表格", "通讯录", "聊天记录", "几百行", "几千行", "整本"]


def assess(query):
    q = (query or "").lower()
    rep = sorted({w for w in REPEAT_SIGNALS if w in q})
    heavy = sorted({w for w in HEAVY_SIGNALS if w in q})
    return rep, heavy


def plan(query):
    rep, heavy = assess(query)
    print(f"◆ 动手前规划: {query}\n" + "-" * 50)

    # 1) 现成方案
    try:
        import script_match, task_memory
        sm = script_match.find(query)
        hist = task_memory.recall(query)
        if hist:
            print("① 历史做过(自学习召回), 优先复用:")
            for s, sc, note, n, ts in hist:
                print(f"   [{s:.2f}|{n}次] {sc}")
        if sm:
            print("② 现有脚本可直接用(别新写):")
            for sc, name, cat, usage in sm[:3]:
                print(f"   [{sc:.2f}] {name}.py — {usage[:42]}")
        if not hist and not sm:
            print("①② 无现成脚本, 确认后再新写")
    except Exception as e:
        print(f"①② 复用检索跳过({type(e).__name__})")

    # 2) 重复性
    if rep:
        print(f"③ 会重复(信号:{','.join(rep)}) → 直接写成【参数化可复用脚本】"
              f"(带 __main__ 入口+try/except+用法docstring), 不写一次性临时码; 入参化、别硬编码")
    else:
        print("③ 一次性任务 → 临时脚本 _ 前缀, 用完即删; 若发现其实会再做, 立即升级为正式脚本")

    # 4) 烧token
    if heavy:
        print(f"④ 高token(信号:{','.join(heavy)}) → 本地脚本处理, 只把结果/关键行回传, "
              f"原始内容不进豆包上下文; 截图走本地OCR、大表走openpyxl、列表走磁盘缓存+增量")
    else:
        print("④ token量可控, 正常处理")

    # 5) AI通道
    try:
        import smart
        print(f"⑤ AI通道: {smart.decide(query)}")
    except Exception:
        print("⑤ AI通道: 代码/debug走DeepSeek(dsh免费优先), 分类摘要走免费模型, 业务判断豆包亲自")

    # 6) 沉淀提醒
    tail = "⑥ 做完 ax did \"任务\" \"用的脚本/命令\" \"结果\" 沉淀, 供下次自动召回"
    if rep or heavy:
        tail += " (本任务值得复用, 务必沉淀)"
    print(tail)
    print("-" * 50)
    return {"repeat": rep, "heavy": heavy}


def main():
    if len(sys.argv) < 2:
        print('用法: ax plan "任务描述"  — 动手前先判断重复性/token成本/现成脚本')
        return
    plan(" ".join(sys.argv[1:]))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"FAIL {type(e).__name__}: {e}")
        sys.exit(1)
