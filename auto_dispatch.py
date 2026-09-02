# -*- coding: utf-8 -*-
"""智能任务派发器 v1.2（dsh审查修复版）"""
import sys, io, os, json, subprocess, argparse, re
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
PROJECT = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

TYPE_RULES = [
    (r"代码|脚本|工具|开发|debug|修复|重构|封装|基类|优化|bug|函数|模块|api", "代码开发"),
    (r"爬|爬虫|crawl|抓取|scrape|采集", "数据整理"),
    (r"价格|监控|比价|行情|多少钱", "信息调研"),
    (r"整理|统计|分析|报表|数据清洗", "数据整理"),
    (r"文案|朋友圈|海报|教程|FAQ|话术", "内容生产"),
    (r"转换|压缩|重命名|水印|转码|批量", "文件处理"),
    (r"调研|搜索|查一下|公开信息|供应商", "信息调研"),
]

# 机密词：用整词边界防误判（客户端≠客户，密码学≠密码，tokenizer≠token）
CONFIDENTIAL = [
    (r"\bodoo\b", "odoo"), (r"商机", "商机"), (r"线索", "线索"),
    (r"底价", "底价"), (r"折扣", "折扣"), (r"价格表", "价格表"),
    (r"报销", "报销"), (r"发票", "发票"), (r"录音", "录音"),
    (r"转写", "转写"), (r"手机号", "手机号"), (r"报价", "报价"),
    (r"\bconfig\b", "config"), (r"密钥", "密钥"),
    (r"(?<!客户端)客户(?!端)", "客户"),  # 客户但不是客户端
    (r"(?<!密码学)密码(?!学)", "密码"),  # 密码但不是密码学
    (r"\btoken\b", "token"), (r"\bapi key\b", "api key"),
]
PUBLIC_CONTEXT = ["公开", "调研", "市场", "行业", "新闻", "上市公司", "财报", "年报", "供应商", "竞品", "参数", "型号"]

TAG_KEYWORDS = {
    "爬虫": ["爬", "爬虫", "crawl", "抓取", "采集"],
    "价格监控": ["价格", "监控", "比价", "行情", "多少钱"],
    "公开信息调研": ["调研", "搜索", "查一下", "公开信息", "供应商"],
    "数据整理": ["整理", "统计", "分析", "报表", "清洗"],
    "配件查询": ["配件", "查询", "零件", "型号", "兼容"],
    "代码开发": ["代码", "脚本", "开发", "debug", "修复", "重构", "封装", "基类", "优化", "bug", "函数", "模块"],
    "重构": ["重构", "封装", "基类", "统一", "消除重复"],
    "bug修复": ["bug", "修复", "debug", "错误", "异常", "崩溃"],
    "脚本优化": ["优化", "性能", "速度", "内存", "效率"],
}

def classify(desc):
    for pattern, typ in TYPE_RULES:
        if re.search(pattern, desc.lower()):
            return typ
    return "其他"

def is_confidential(desc):
    has_public = any(kw in desc for kw in PUBLIC_CONTEXT)
    hits = sum(1 for pat, _ in CONFIDENTIAL if re.search(pat, desc, re.I))
    threshold = 2 if has_public else 1
    return hits >= threshold

def recommend_instance(task_type, description, return_all=False):
    """推荐实例。return_all=True时返回所有实例评分排名[(name, score), ...]"""
    try:
        with open(os.path.join(PROJECT, "instances.json"), 'r', encoding='utf-8') as f:
            instances = json.load(f).get("instances", {})
    except:
        return (None, 0) if not return_all else []
    text = f"{task_type} {description}".lower()
    scores = []
    for name, inst in instances.items():
        score = 0
        tags = inst.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",")]
        for tag in tags:
            if tag.lower() in text:
                score += 10
                continue
            for kw in TAG_KEYWORDS.get(tag, []):
                if kw.lower() in text:
                    score += 10
                    break
        # 成功率加成
        completed = inst.get("completed", 0)
        failed = inst.get("failed", 0)
        if completed + failed > 0:
            score += int(completed / (completed + failed) * 5)
        # 负载因子：处理中任务多的降权
        active = inst.get("active_tasks", 0)
        if active > 0:
            score -= active * 5
        # 心跳状态：在线的加分，超时的减分
        last_seen = inst.get("last_seen", "")
        if last_seen:
            try:
                import datetime
                lt = datetime.datetime.fromisoformat(last_seen.replace("Z", "+00:00").replace("+08:00", ""))
                elapsed = (datetime.datetime.now() - lt).total_seconds() / 60
                if elapsed <= 30:
                    score += 5  # 在线加分
                elif elapsed > 120:
                    score -= 10  # 长时间超时减分
            except:
                pass
        scores.append((name, score))
    scores.sort(key=lambda x: x[1], reverse=True)
    if return_all:
        return scores
    if scores and scores[0][1] >= 10:
        return scores[0]
    return None, 0

def _ai_judge(desc, question):
    """规则不确定时调用免费AI判断（智谱/通义，零成本），返回是/否"""
    try:
        sys.path.insert(0, PROJECT)
        from ai_router import extract
        result = extract(f"任务描述: {desc}\n问题: {question}\n只回答'是'或'否'", ["判断"], provider=None)
        if result:
            return "是" in str(result)
    except Exception:
        pass
    return None

def _set_assignee(record_id, instance_name):
    """push任务后自动设置指派给字段"""
    try:
        sys.path.insert(0, PROJECT)
        from sharedtask import cli, BASE, TABLE
        cli(["+record-batch-update", "--base-token", BASE, "--table-id", TABLE,
             "--json", json.dumps({"update_records": {record_id: {"指派给": instance_name}}}, ensure_ascii=False),
             "--as", "user"])
        return True
    except Exception as e:
        print(f"设置指派人失败: {e}")
        return False

def dispatch(description, title=None, dry_run=False):
    print(f"任务: {description}")
    # 机密判断：规则初筛，边界情况用AI确认
    conf_hits = sum(1 for pat, _ in CONFIDENTIAL if re.search(pat, description, re.I))
    has_public = any(kw in description for kw in PUBLIC_CONTEXT)
    threshold = 2 if has_public else 1
    if conf_hits >= threshold:
        # 边界情况（刚好等于阈值且有公开上下文）用AI确认
        if conf_hits == threshold and has_public:
            ai_result = _ai_judge(description, "这个任务是否包含客户隐私、底价、密钥、录音等不能外传的机密信息？")
            if ai_result is False:
                print("AI确认: 无机密，可派发")
            else:
                print("⚠️  机密（AI确认），留本地")
                return None
        else:
            print("⚠️  机密，留本地")
            return None
    task_type = classify(description)
    # 类型不确定时用AI分类
    if task_type == "其他":
        try:
            sys.path.insert(0, PROJECT)
            from ai_router import extract
            ai_type = extract(f"任务: {description}\n从以下类型选一个: 信息调研/内容生产/文件处理/代码开发/数据整理/其他", ["类型"], provider=None)
            if ai_type and str(ai_type).strip() in ["信息调研", "内容生产", "文件处理", "代码开发", "数据整理"]:
                task_type = str(ai_type).strip()
                print(f"AI分类: {task_type}")
        except Exception:
            pass
    print(f"类型: {task_type}")
    # 全实例评分排名
    all_scores = recommend_instance(task_type, description, return_all=True)
    if all_scores:
        print("实例评分:")
        for name, score in all_scores:
            marker = " ← 推荐" if score == all_scores[0][1] and score >= 10 else ""
            print(f"  {name}: {score}分{marker}")
    instance, score = recommend_instance(task_type, description)
    if not instance or score < 10:
        print("⚠️  无匹配实例，留本地")
        return None
    confidence = "高" if score >= 25 else ("中" if score >= 15 else "低")
    print(f"派发: {instance} (分:{score}, 置信度:{confidence})")
    if dry_run:
        return None
    task_title = title or description[:30]
    r = subprocess.run([PY, "sharedtask.py", "push", task_type, task_title, description,
                        "智能派发"], capture_output=True, text=True,
                       timeout=30, encoding='utf-8', cwd=PROJECT)
    output = r.stdout.strip()
    print(f"结果: {output}")
    # 提取record_id并自动设置指派人
    import re as _re
    m = _re.search(r'(rec[A-Za-z0-9]{6,})', output)
    if m:
        rid = m.group(1)
        _set_assignee(rid, instance)
        print(f"已指派给: {instance}")
    return output

def main():
    p = argparse.ArgumentParser()
    p.add_argument("description")
    p.add_argument("--title")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    dispatch(a.description, a.title, a.dry_run)

if __name__ == "__main__":
    main()
