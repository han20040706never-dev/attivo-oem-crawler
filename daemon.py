# -*- coding: utf-8 -*-
"""
协作系统自动巡检daemon v2.3（DeepSeek审查后修复版）
修复：
  - get_pending_tasks正则适配6字段输出
  - auto_update md5比较前统一换行符（Windows CRLF vs GitHub LF）
  - 标签关键词匹配与auto_dispatch一致
"""
import sys, io, os, time, subprocess, json, datetime, argparse, re, hashlib, py_compile, tempfile
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
PROJECT = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
LOG_FILE = os.path.join(PROJECT, "_daemon.log")
INSTANCE_NAME = os.environ.get("DAEMON_INSTANCE", "")
INSTANCE_TAGS = os.environ.get("DAEMON_TAGS", "")
GITHUB_RAW = "https://raw.githubusercontent.com/han20040706never-dev/attivo-oem-crawler/main/"
AUTO_UPDATE_FILES = ["daemon.py", "sharedtask.py", "shared_mem.py", "check_done.py", "common.py", "install_daemon_task.py", "auto_dispatch.py"]

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

def _norm(content_bytes):
    """统一换行符为LF，避免Windows CRLF导致md5永远不一致"""
    return content_bytes.replace(b'\r\n', b'\n').replace(b'\r', b'\n')

def auto_update():
    try:
        import requests
        updated = []
        for fname in AUTO_UPDATE_FILES:
            local_path = os.path.join(PROJECT, fname)
            if not os.path.exists(local_path):
                continue
            r = requests.get(GITHUB_RAW + fname, timeout=8)
            if r.status_code != 200:
                continue
            remote_bytes = r.content
            local_bytes = open(local_path, 'rb').read()
            if _norm(local_bytes) == _norm(remote_bytes):
                continue
            tmp_path = os.path.join(tempfile.gettempdir(), f"_update_{fname}")
            with open(tmp_path, 'wb') as f:
                f.write(remote_bytes)
            try:
                py_compile.compile(tmp_path, doraise=True)
            except py_compile.PyCompileError:
                log(f"  自动更新跳过 {fname}：语法验证失败")
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                continue
            with open(local_path, 'wb') as f:
                f.write(remote_bytes)
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            updated.append(fname)
        if updated:
            log(f"  自动更新: {', '.join(updated)}")
        return updated
    except Exception as e:
        log(f"  自动更新检查失败: {e}")
        return []

def load_instance_stats():
    try:
        with open(os.path.join(PROJECT, "instances.json"), 'r', encoding='utf-8') as f:
            return json.load(f).get("instances", {})
    except:
        return {}

def task_matches_tags(task_type, title, tags):
    if not tags:
        return True
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    text = f"{task_type} {title}".lower()
    score = 0
    for tag in tag_list:
        if tag.lower() in text:
            score += 10
            continue
        for kw in TAG_KEYWORDS.get(tag, []):
            if kw.lower() in text:
                score += 10
                break
    stats = load_instance_stats()
    inst = stats.get(INSTANCE_NAME, {})
    completed = inst.get("completed", 0)
    failed = inst.get("failed", 0)
    if completed + failed > 0:
        score += int(completed / (completed + failed) * 5)
    return score >= 10

def get_pending_tasks():
    out = run(["sharedtask.py", "pending"], timeout=30)
    tasks = []
    # 格式: [rid] 优先级 | 任务号 | 状态 | 来源 | 类型 | 标题 → 指派人
    for line in out.split("\n"):
        m = re.match(r'\[(rec\w+)\]\s+\S+\s+\|\s+\S+\s+\|\s+\S+\s+\|\s+\S+\s+\|\s+(\S+)\s+\|\s+(.*)', line)
        if m:
            rid = m.group(1)
            typ = m.group(2)
            title = m.group(3).split(" \u2192 ")[0].strip()
            tasks.append((rid, title, typ, ""))
    return tasks

def auto_execute_crawl(rid, title, content):
    log(f"  自动执行爬虫任务: {title}")
    try:
        import requests
        url = GITHUB_RAW + "_remaining_sections.json"
        r = requests.get(url, timeout=30)
        if r.status_code != 200:
            return f"爬虫失败：无法下载section列表({r.status_code})"
        sections = r.json()
        with open("_remaining_sections.json", 'w', encoding='utf-8') as f:
            json.dump(sections, f, ensure_ascii=False)
        script = os.path.join(PROJECT, "_auto_crawl.py")
        with open(script, 'w', encoding='utf-8') as f:
            f.write('''# -*- coding: utf-8 -*-
import sys, io, json, requests, sqlite3, time, re
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
with open('_remaining_sections.json','r',encoding='utf-8') as f:
    sections = json.load(f)
conn = sqlite3.connect('oemkb.db')
c = conn.cursor()
headers = {'User-Agent':'Mozilla/5.0'}
ok = 0
for i, sec in enumerate(sections):
    try:
        url = sec['url']
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code != 200:
            continue
        parts = re.findall(r'class="part"[^>]*>.*?<td class="num"[^>]*>(.*?)</td>.*?<td class="name"[^>]*>(.*?)</td>', r.text, re.S)
        for item, pno, desc in parts:
            c.execute("INSERT OR IGNORE INTO part (sec_url, item, part_no, desc, qty) VALUES (?,?,?,?,?)",
                     (url, item.strip(), pno.strip(), re.sub('<[^>]+>','',desc).strip(), 1))
        c.execute("UPDATE section SET part_done=1 WHERE url=?", (url,))
        conn.commit()
        ok += 1
        time.sleep(0.5)
    except:
        pass
conn.close()
print(f"DONE: {ok}/{len(sections)}")
''')
        result = run([script], timeout=600)
        if os.path.exists(script):
            os.remove(script)
        if os.path.exists("_remaining_sections.json"):
            os.remove("_remaining_sections.json")
        return f"自动爬取完成: {result[-200:]}"
    except Exception as e:
        return f"自动爬取失败: {e}"

def try_auto_execute(rid, title, task_type, content):
    if "爬虫" in title or "crawl" in title.lower() or "爬" in title:
        return auto_execute_crawl(rid, title, content)
    return None

def cycle():
    log("=== 巡检开始 ===")
    sync_out = run(["shared_mem.py", "sync"], timeout=60)
    log(f"经验同步: {sync_out[:120]}")
    if INSTANCE_NAME:
        tasks = get_pending_tasks()
        for rid, title, typ, content in tasks:
            if task_matches_tags(typ, title, INSTANCE_TAGS):
                log(f"  自动认领: {title} ({rid})")
                claim_out = run(["sharedtask.py", "claim", rid, INSTANCE_NAME], timeout=30)
                if "OK" in claim_out:
                    result = try_auto_execute(rid, title, typ, content)
                    if result:
                        run(["sharedtask.py", "complete", rid, result], timeout=60)
                        log(f"  自动完成: {title}")
                    else:
                        log(f"  需AI处理: {title}")
                else:
                    log(f"  认领失败: {claim_out[:80]}")
    out = run(["check_done.py"], timeout=60)
    log(f"check_done: {out[:150]}")
    out2 = run(["sharedtask.py", "watchdog", "--auto"], timeout=30)
    log(f"watchdog: {out2[:80]}")
    log("=== 巡检结束 ===\n")

def main():
    global INSTANCE_NAME, INSTANCE_TAGS
    p = argparse.ArgumentParser()
    p.add_argument("--instance", type=str, default="")
    p.add_argument("--tags", type=str, default="")
    p.add_argument("--interval", type=int, default=300)
    p.add_argument("--once", action="store_true")
    a = p.parse_args()
    if a.instance:
        INSTANCE_NAME = a.instance
    if a.tags:
        INSTANCE_TAGS = a.tags
    if INSTANCE_NAME:
        log(f"daemon启动，实例={INSTANCE_NAME}, 标签={INSTANCE_TAGS}")
    else:
        log("daemon启动（仅回收模式）")
    auto_update()
    boot_out = run(["shared_mem.py", "bootstrap"], timeout=120)
    log(f"启动经验同步: {boot_out[:150]}")
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
