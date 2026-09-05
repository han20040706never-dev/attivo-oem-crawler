# -*- coding: utf-8 -*-
"""
asr_rolemap.py — 录音转写后、豆包总结前的【说话人角色标定】工具（零外部AI，省token）
输入 ASR 转出的带说话人文本（每行形如 [1] 内容；也兼容 [Speaker1] / 1: 内容）。
输出：每个 speaker 的句数、提问数、我方/客户线索命中、代表句，并给出建议角色；
同时写出 <输入名>.byspk.txt（按说话人归并，方便豆包分段读、不串话）。

用法: python asr_rolemap.py _trans_xxx.txt
"""
import sys, io, re, os, argparse, collections
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')

# 我方业务员线索（对客户用“您”、介绍自家、发资料、报价）
OUR_CUES = ["您这边", "您现在", "您修", "您客户", "您一般", "您那边", "我们公司", "我们官网",
            "台湾台中", "我们这个", "我们产品", "我们做", "我们老板", "我们仓库", "我发你",
            "我加你", "手册", "价目表", "报价", "宁波仓", "我们台湾", "我跟您", "给您"]
# 客户线索（讲自己厂/拿货/成本/卖给谁）
CUST_CUES = ["我厂里", "我这边", "我们厂", "我买", "我卖", "我用", "我供", "我们做的",
             "成本", "我给你", "我们出厂", "我拿货", "我一年", "我现在用", "我的客户"]
Q_CUES = ["吗", "呢", "是不是", "多少", "哪个", "有没有", "怎么", "什么", "？", "?"]


def parse(path):
    spk = collections.OrderedDict()
    pat = re.compile(r'^\s*\[?(?:speaker)?\s*(\d+)\]?[\s:：]*(.*)$', re.I)
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        m = pat.match(line)
        if not m:
            continue
        sid, txt = m.group(1), m.group(2).strip()
        if not txt:
            continue
        spk.setdefault(sid, []).append(txt)
    return spk


def score(lines):
    our = sum(any(k in t for k in OUR_CUES) for t in lines)
    cust = sum(any(k in t for k in CUST_CUES) for t in lines)
    q = sum(any(k in t for k in Q_CUES) for t in lines)
    polite = sum(t.count("您") for t in lines)
    return our, cust, q, polite


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("txt")
    ap.add_argument("--sample", type=int, default=8)
    a = ap.parse_args()
    spk = parse(a.txt)
    print(f"共 {len(spk)} 个说话人：{list(spk.keys())}\n")
    scored = {}
    for sid, lines in spk.items():
        our, cust, q, polite = score(lines)
        scored[sid] = (our, cust, q, polite)
    # 我方=线索分最高者（通常“您”和提问最多）
    our_rank = sorted(spk, key=lambda s: (scored[s][0] + scored[s][3] / 20 + scored[s][2] / 10),
                      reverse=True)
    suggested_our = our_rank[0] if our_rank else None
    grouped = []
    for sid, lines in spk.items():
        our, cust, q, polite = scored[sid]
        if sid == suggested_our:
            role = "★建议=我方业务员(陈国标)"
        elif our >= cust:
            role = "?偏旁人/待豆包定"
        else:
            role = "候选客户/对方人员"
        chars = sum(len(t) for t in lines)
        print(f"===== Speaker {sid} | {len(lines)}句 {chars}字 | 提问{q} 我方线索{our} 客户线索{cust} 您x{polite} | {role}")
        for t in lines[:a.sample]:
            print("   ", t[:70])
        print()
        grouped.append(f"########## Speaker {sid} | {role} ##########")
        grouped.extend(lines)
        grouped.append("")
    out = os.path.splitext(a.txt)[0] + ".byspk.txt"
    open(out, "w", encoding="utf-8").write("\n".join(grouped))
    print(f"按说话人归并已写出: {out}")
    print("\n豆包下一步：先定映射『业务员=S?、主客户=S?、其余=旁人』，再按speaker归属写总结；")
    print("业务员说的评价/报价/战略不算客户观点；归属存疑标待确认。")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"FAIL {type(e).__name__}: {e}")
