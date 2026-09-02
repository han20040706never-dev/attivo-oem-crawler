# -*- coding: utf-8 -*-
"""
协作系统自动巡检daemon（v2.0 智能自动版）
功能：
  1. 自动认领匹配本机标签的待处理任务（无需人工触发）
  2. 自动执行标准化任务（爬虫/数据整理等）
  3. 回收已完成任务+同步经验
  4. 重置超时任务
用法：
  python daemon.py --instance "云电脑 爬虫脚本" --tags "爬虫,数据整理,配件查询" --interval 300
  python daemon.py --once  # 只跑一次
"""
import sys, io, os, time, subprocess, json, datetime, argparse, re
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
PROJECT = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
LOG_FILE = os.path.join(PROJECT, "_daemon.log")
INSTANCE_NAME = os.environ.get("DAEMON_INSTANCE", "")
INSTANCE_TAGS = os.environ.get("DAEMON_TAGS", "")

def log(msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + "\n")

def run(cmd_args, timeout=120):
    try:
        r = subprocess.run([PY] + cmd_args, capture_output=True, text=True,
                          timeout=timeout, encoding='utf-8', cwd=PROJECT)
        return r.stdout.strip()
    except Exception as e:
        return f"ERROR: {e}"

def get_pending_tasks():
    """获取待处理任务列表，返回[(rid, title, typ, content)]"""
    out = run(["sharedtask.py", "pending"], timeout=30)
    tasks = []
    for line in out.split("\n"):
        m = re.match(r'\[(rec\w+)\]\s+\S+\s+\|\s+(\S+)\s+\|\s+\S+\s+\|\s+(\S+)\s+\|\s+(.*)', line)
        if m:
            tasks.append((m.group(1), m.group(4).strip(), m.group(3), ""))
    return tasks

def load_instance_stats():
    """加载instances.json获取各实例历史完成率"""
    try:
        with open(os.path.join(PROJECT, "instances.json"), 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get("instances", {})
    except:
        return {}

def task_matches_tags(task_type, title, tags):
    """判断任务是否匹配本机标签（带历史完成率加权）"""
    if not tags:
        return True
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    text = f"{task_type} {title}"
    score = 0
    for tag in tag_list:
        if tag in text or tag in task_type:
            score += 10
    # 历史完成率加成
    stats = load_instance_stats()
    inst = stats.get(INSTANCE_NAME, {})
    completed = inst.get("completed", 0)
    failed = inst.get("failed", 0)
    if completed + failed > 0:
        rate = completed / (completed + failed)
        score += int(rate * 5)
    return score >= 10

def auto_execute_crawl(rid, title, content):
    """自动执行爬虫任务"""
    log(f"  自动执行爬虫任务: {title}")
    # 下载剩余section列表
    try:
        import requests
        url = "https://raw.githubusercontent.com/han20040706never-dev/attivo-oem-crawler/main/_remaining_sections.json"
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            sections = r.json()
            log(f"  下载到{len(sections)}个section")
            # 写一个临时爬虫脚本抓这些section
            script = os.path.join(PROJECT, "_auto_crawl_remaining.py")
            with open(script, 'w', encoding='utf-8') as f:
                f.write('''# -*- coding: utf-8 -*-
import sys, io, json, requests, sqlite3, time, re
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.path.insert(0, '.')
PROJECT = '.'
with open('_remaining_sections.json','r',encoding='utf-8') as f:
    sections = json.load(f)
conn = sqlite3.connect('oemkb.db')
c = conn.cursor()
headers = {'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
ok = 0
for i, sec in enumerate(sections):
    try:
        url = sec['url']
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code != 200:
            print(f"[{i+1}/{len(sections)}] FAIL {r.status_code} {sec['name']}")
            continue
        # 解析零件行
        parts = re.findall(r'class="part"[^>]*>.*?<td class="num"[^>]*>(.*?)</td>.*?<td class="name"[^>]*>(.*?)</td>', r.text, re.S)
        for item, pno, desc in parts:
            c.execute("INSERT OR IGNORE INTO part (sec_url, item, part_no, desc, qty) VALUES (?,?,?,?,?)",
                     (url, item.strip(), pno.strip(), re.sub('<[^>]+>','',desc).strip(), 1))
        c.execute("UPDATE section SET part_done=1 WHERE url=?", (url,))
        conn.commit()
        ok += 1
        print(f"[{i+1}/{len(sections)}] OK {sec['name']} ({len(parts)} parts)")
        time.sleep(0.5)
    except Exception as e:
        print(f"[{i+1}/{len(sections)}] ERROR {e}")
conn.close()
print(f"DONE: {ok}/{len(sections)} sections crawled")
''')
            result = run([script], timeout=600)
            log(f"  爬虫结果: {result[-300:]}")
            # 清理临时脚本
            if os.path.exists(script):
                os.remove(script)
            return f"自动爬取完成: {result[-200:]}"
    except Exception as e:
        return f"自动爬取失败: {e}"

def try_auto_execute(rid, title, task_type, content):
    """尝试自动执行任务，成功返回结果字符串，失败返回None"""
    if "爬虫" in title or "crawl" in title.lower() or "爬" in title:
        return auto_execute_crawl(rid, title, content)
    # 其他类型暂不自动执行，留给AI处理
    return None

def cycle():
    log("=== 巡检开始 ===")
    
    # 0. 双向同步经验（pull新经验 + push本地新经验）
    sync_out = run(["shared_mem.py", "sync"], timeout=60)
    log(f"经验同步: {sync_out[:150]}")
    
    # 1. 自动认领匹配标签的任务
    if INSTANCE_NAME:
        tasks = get_pending_tasks()
        for rid, title, typ, content in tasks:
            if task_matches_tags(typ, title, INSTANCE_TAGS):
                log(f"  自动认领任务: {title} ({rid})")
                claim_out = run(["sharedtask.py", "claim", rid, INSTANCE_NAME], timeout=30)
                if "OK" in claim_out:
                    # 尝试自动执行
                    result = try_auto_execute(rid, title, typ, content)
                    if result:
                        run(["sharedtask.py", "complete", rid, result], timeout=60)
                        log(f"  任务自动完成: {title}")
                    else:
                        log(f"  任务需AI处理: {title}")
                else:
                    log(f"  认领失败: {claim_out[:100]}")
    
    # 2. check_done（回收任务+自动同步经验）
    out = run(["check_done.py"], timeout=60)
    log(f"check_done: {out[:200]}")
    
    # 3. watchdog（重置超时任务）
    out2 = run(["sharedtask.py", "watchdog", "--auto"], timeout=30)
    log(f"watchdog: {out2[:100]}")
    
    log("=== 巡检结束 ===\n")

def main():
    global INSTANCE_NAME, INSTANCE_TAGS
    p = argparse.ArgumentParser()
    p.add_argument("--instance", type=str, default="", help="本机实例名称")
    p.add_argument("--tags", type=str, default="", help="本机专长标签，逗号分隔")
    p.add_argument("--interval", type=int, default=300, help="巡检间隔秒数，默认300")
    p.add_argument("--once", action="store_true", help="只跑一次")
    a = p.parse_args()
    
    if a.instance:
        INSTANCE_NAME = a.instance
    if a.tags:
        INSTANCE_TAGS = a.tags
    
    if INSTANCE_NAME:
        log(f"daemon启动，实例={INSTANCE_NAME}, 标签={INSTANCE_TAGS}, 间隔{a.interval}秒")
    else:
        log(f"daemon启动（仅回收模式，不自动认领）, 间隔{a.interval}秒")
    
    # 启动时自动bootstrap：拉取所有历史经验（教学相长）
    boot_out = run(["shared_mem.py", "bootstrap"], timeout=120)
    log(f"启动经验同步: {boot_out[:200]}")
    
    if a.once:
        cycle()
        return
    
    while True:
        try:
            cycle()
        except Exception as e:
            log(f"巡检异常: {e}")
        time.sleep(a.interval)

if __name__ == "__main__":
    main()
