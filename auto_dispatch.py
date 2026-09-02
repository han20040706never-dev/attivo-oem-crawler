# -*- coding: utf-8 -*-
"""
智能任务派发器 v1.1（DeepSeek审查后修复版）
修复：
  - is_confidential误判：加公开上下文排除，"客户"单独出现不算机密
  - 标签关键词匹配与daemon一致
用法：python auto_dispatch.py "帮我爬一下boats.net的雅马哈配件价格"
"""
import sys, io, os, json, subprocess, argparse, re
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
PROJECT = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

TYPE_RULES = [
    (r"爬|爬虫|crawl|抓取|scrape|采集", "数据整理"),
    (r"价格|监控|比价|行情|多少钱", "信息调研"),
    (r"整理|统计|分析|报表|数据清洗", "数据整理"),
    (r"文案|朋友圈|海报|脚本|教程|FAQ|话术", "内容生产"),
    (r"转换|压缩|重命名|水印|转码|批量", "文件处理"),
    (r"代码|脚本|工具|开发|debug|修复", "代码开发"),
    (r"调研|搜索|查一下|公开信息|供应商", "信息调研"),
]

CONFIDENTIAL_KEYWORDS = [
    "odoo", "商机", "线索", "底价", "折扣", "价格表",
    "报销", "发票", "录音", "转写", "手机号",
    "config", "密钥", "密码", "token", "api key",
]
PUBLIC_CONTEXT = [
    "公开", "调研", "市场", "行业", "新闻", "上市公司",
    "财报", "年报", "供应商", "竞品", "参数", "型号",
]

TAG_KEYWORDS = {
    "爬虫": ["爬", "爬虫", "crawl", "抓取", "采集", "scrape"],
    "价格监控": ["价格", "监控", "比价", "行情", "多少钱", "售价"],
    "公开信息调研": ["调研", "搜索", "查一下", "公开信息", "供应商", "资讯"],
    "数据整理": ["整理", "统计", "分析", "报表", "数据清洗", "清洗"],
    "配件查询": ["配件", "查询", "零件", "型号", "兼容", "替代"],
    "内容生产": ["文案", "朋友圈", "海报", "脚本", "教程", "FAQ", "话术"],
    "文件处理": ["转换", "压缩", "重命名", "水印", "转码", "批量"],
    "代码开发": ["代码", "脚本", "工具", "开发", "debug", "修复"],
}

def classify(description):
    desc_lower = description.lower()
    for pattern, typ in TYPE_RULES:
        if re.search(pattern, desc_lower):
            return typ
    return "其他"

def is_confidential(description):
    desc_lower = description.lower()
    has_public = any(kw.lower() in desc_lower for kw in PUBLIC_CONTEXT)
    threshold = 2 if has_public else 1
    hits = sum(1 for kw in CONFIDENTIAL_KEYWORDS if kw.lower() in desc_lower)
    if "客户" in description and hits == 0:
        if any(op in description for op in ["更新", "修改", "删除", "录入", "备注", "总结"]):
            return True
        return False
    return hits >= threshold

def recommend_instance(task_type, description):
    try:
        with open(os.path.join(PROJECT, "instances.json"), 'r', encoding='utf-8') as f:
            instances = json.load(f).get("instances", {})
    except:
        return None, 0
    desc_lower = description.lower()
    best, best_score = None, 0
    for name, inst in instances.items():
        score = 0
        for tag in inst.get("tags", []):
            if tag.lower() in desc_lower:
                score += 10
                continue
            for kw in TAG_KEYWORDS.get(tag, []):
                if kw.lower() in desc_lower:
                    score += 10
                    break
        completed = inst.get("completed", 0)
        failed = inst.get("failed", 0)
        if completed + failed > 0:
            score += int(completed / (completed + failed) * 5)
        if score > best_score:
            best_score, best = score, name
    return best, best_score

def dispatch(description, title=None, dry_run=False):
    print(f"任务描述: {description}")
    if is_confidential(description):
        print("⚠️  包含机密信息，留本地处理")
        return None
    task_type = classify(description)
    print(f"任务类型: {task_type}")
    instance, score = recommend_instance(task_type, description)
    if not instance or score < 10:
        print("⚠️  无匹配云电脑实例，留本地处理")
        return None
    print(f"推荐实例: {instance} (匹配分:{score})")
    if dry_run:
        print("(dry-run，不实际派发)")
        return None
    task_title = title or description[:30]
    r = subprocess.run(
        [PY, "sharedtask.py", "push", task_type, task_title, description,
         "智能派发", instance, "中"],
        capture_output=True, text=True, timeout=30, encoding='utf-8', cwd=PROJECT
    )
    print(f"派发结果: {r.stdout.strip()}")
    return r.stdout.strip()

def main():
    p = argparse.ArgumentParser()
    p.add_argument("description")
    p.add_argument("--title")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    dispatch(a.description, a.title, a.dry_run)

if __name__ == "__main__":
    main()
