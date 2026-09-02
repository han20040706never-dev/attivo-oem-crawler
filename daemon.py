# -*- coding: utf-8 -*-
"""
协作系统自动巡检daemon v3.0（dsh agent深度审查后修复版）
修复（A1-A15）：
  🔴 非原子写入→_atomic_write(tmp+os.replace)，硬杀不损坏文件
  🔴 执行限额→install脚本默认60分钟（爬虫600s+开销）
  🔴 多daemon并发→msvcrt跨进程互斥锁
  🔴 万能"爬"自动执行→should_auto_execute只认OEM收尾特征
  🟠 run吞错误→非零退出返回ERROR标记
  🟠 claim TOCTOU→认领后view回读校验
  🟠 空标签全量抢单→有实例无标签时跳过认领
  🟠 pending解析脆→split(" | ",5)+rid校验+assignee过滤
  🟡 失败也标完成→ERROR开头走fail
  🟡 auto_update节流→30分钟内不重复检查
  🟡 缺失文件不创建→本地不存在也下载
"""
import sys, io, os, time, subprocess, json, datetime, argparse, re, hashlib, tempfile
try:
    import msvcrt
except ImportError:
    msvcrt = None
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w', encoding='utf-8')
else:
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
    except Exception:
        pass

PROJECT = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
LOG_FILE = os.path.join(PROJECT, "_daemon.log")
INSTANCE_NAME = os.environ.get("DAEMON_INSTANCE", "")
INSTANCE_TAGS = os.environ.get("DAEMON_TAGS", "")
GITHUB_RAW = "https://raw.githubusercontent.com/han20040706never-dev/attivo-oem-crawler/main/"
AUTO_UPDATE_FILES = ["daemon.py", "sharedtask.py", "shared_mem.py", "check_done.py", "common.py", "install_daemon_task.py", "auto_dispatch.py"]
_LOCK_FILE = os.path.join(PROJECT, ".daemon.lock")
RID_RE = re.compile(r'^rec[A-Za-z0-9]{6,}$')
CRAWL_MARKERS = ("剩余", "收尾", "OEM", "oem", "section", "零件抓取", "_remaining_sections")

TAG_KEYWORDS = {
    "爬虫": ["爬", "爬虫", "crawl", "抓取", "采集", "scrape"],
    "价格监控": ["价格", "监控", "比价", "行情", "多少钱", "售价"],
    "公开信息调研": ["调研", "搜索", "查一下", "公开信息", "供应商", "资讯"],
    "数据整理": ["整理", "统计", "分析", "报表", "数据清洗", "清洗"],
    "配件查询": ["配件", "查询", "零件", "型号", "兼容", "替代"],
}

def log(msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    try:
        print(line, flush=True)
    except Exception:
        pass
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(line + "\n")
    except OSError:
        pass

def run(cmd_args, timeout=120):
    try:
        r = subprocess.run([PY] + cmd_args, capture_output=True, text=True,
                           timeout=timeout, encoding='utf-8', cwd=PROJECT)
        if r.returncode != 0:
            err = (r.stderr or r.stdout or "").strip()
            return f"ERROR(exit {r.returncode}): {err[-300:]}"
        return r.stdout.strip()
    except subprocess.TimeoutExpired:
        return f"ERROR(timeout>{timeout}s): {' '.join(cmd_args)[:100]}"
    except Exception as e:
        return f"ERROR: {e}"

def acquire_cycle_lock():
    if msvcrt is None:
        return "nolock"
    fd = os.open(_LOCK_FILE, os.O_CREAT | os.O_RDWR)
    try:
        if os.fstat(fd).st_size == 0:
            os.write(fd, b'\x00')
        os.lseek(fd, 0, 0)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        return fd
    except OSError:
        try:
            os.close(fd)
        except OSError:
            pass
        return None

def release_cycle_lock(fd):
    if fd is None or fd == "nolock":
        return
    try:
        os.lseek(fd, 0, 0)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    except OSError:
        pass
    try:
        os.close(fd)
    except OSError:
        pass

def _norm(b):
    return b.replace(b'\r\n', b'\n').replace(b'\r', b'\n')

def _atomic_write(path, data):
    tmp = path + f".tmp{os.getpid()}"
    with open(tmp, 'wb') as f:
        f.write(data)
    os.replace(tmp, path)

def auto_update():
    try:
        import requests
        stamp = os.path.join(PROJECT, ".auto_update_stamp")
        try:
            if os.path.exists(stamp) and time.time() - os.path.getmtime(stamp) < 1800:
                return []
        except OSError:
            pass
        pending, failures = [], []
        for fname in AUTO_UPDATE_FILES:
            try:
                r = requests.get(GITHUB_RAW + fname, timeout=5)
            except Exception as e:
                failures.append(f"{fname}:{type(e).__name__}")
                continue
            if r.status_code != 200:
                continue
            remote_bytes = r.content
            try:
                local_bytes = open(os.path.join(PROJECT, fname), 'rb').read() if os.path.exists(os.path.join(PROJECT, fname)) else b''
            except OSError:
                local_bytes = b''
            if _norm(local_bytes) == _norm(remote_bytes):
                continue
            pending.append((fname, remote_bytes))
        validated = []
        for fname, remote_bytes in pending:
            try:
                compile(remote_bytes.decode('utf-8'), fname, 'exec')
                validated.append((fname, remote_bytes))
            except (SyntaxError, UnicodeDecodeError) as e:
                log(f"  自动更新跳过 {fname}：语法错误 {e}")
        updated = []
        for fname, remote_bytes in validated:
            try:
                _atomic_write(os.path.join(PROJECT, fname), remote_bytes)
                updated.append(fname)
            except OSError as e:
                failures.append(f"{fname}:写入失败 {e}")
        try:
            open(stamp, 'wb').close()
        except OSError:
            pass
        if updated:
            log(f"  自动更新: {', '.join(updated)}")
        if failures:
            log(f"  自动更新部分失败: {'; '.join(failures)}")
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
        return False
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

def get_pending_tasks(max_tasks=5):
    out = run(["sharedtask.py", "pending"], timeout=30)
    if not out or out.startswith("ERROR"):
        if out:
            log(f"  pending查询失败: {out[:200]}")
        return []
    tasks, skipped = [], 0
    for line in out.split("\n"):
        line = line.strip()
        if not line or not line.startswith("["):
            continue
        m = re.match(r'^\[([^\]]+)\]\s?(.*)$', line)
        if not m:
            skipped += 1
            continue
        rid, rest = m.group(1), m.group(2)
        if not RID_RE.match(rid):
            skipped += 1
            continue
        parts = rest.split(" | ", 5)
        if len(parts) != 6:
            skipped += 1
            continue
        pri, no, status, src, typ, title_part = [p.strip() for p in parts]
        if status != "待处理":
            continue
        assignee = ""
        if " \u2192 " in title_part:
            title_part, assignee = title_part.split(" \u2192 ", 1)
        title = title_part.strip()
        if not title:
            continue
        tasks.append((rid, title, typ, "", assignee))
        if len(tasks) >= max_tasks:
            break
    if skipped:
        log(f"  pending解析跳过{skipped}行异常格式")
    return tasks

def should_auto_execute(title, task_type):
    t = f"{title} {task_type}"
    is_crawl = ("爬" in title) or ("crawl" in title.lower()) or ("抓取" in title)
    return is_crawl and any(mk in t for mk in CRAWL_MARKERS)

def auto_execute_crawl(rid, title, content):
    log(f"  自动执行OEM收尾爬虫: {title}")
    script = os.path.join(PROJECT, "_auto_crawl.py")
    sections_file = os.path.join(PROJECT, "_remaining_sections.json")
    try:
        import requests
        r = requests.get(GITHUB_RAW + "_remaining_sections.json", timeout=30)
        if r.status_code != 200:
            return f"ERROR: 无法下载section列表({r.status_code})"
        sections = r.json()
        if not isinstance(sections, list) or not sections:
            return "ERROR: section列表为空或格式非法"
        with open(sections_file, 'w', encoding='utf-8') as f:
            json.dump(sections, f, ensure_ascii=False)
        with open(script, 'w', encoding='utf-8') as f:
            f.write('''# -*- coding: utf-8 -*-
import sys, io, json, requests, sqlite3, time, re
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
with open('_remaining_sections.json','r',encoding='utf-8') as f:
    sections = json.load(f)
conn = sqlite3.connect('oemkb.db', timeout=30)
c = conn.cursor()
headers = {'User-Agent':'Mozilla/5.0'}
ok = err = 0
for sec in sections:
    try:
        url = sec['url']
        rr = requests.get(url, headers=headers, timeout=30)
        if rr.status_code != 200:
            err += 1
            continue
        blocks = rr.text.split('class="part"')[1:]
        ins = 0
        for b in blocks:
            mnum = re.search(r'class="num"[^>]*>(.*?)</td>', b, re.S)
            mname = re.search(r'class="name"[^>]*>(.*?)</td>', b, re.S)
            if not (mnum and mname):
                continue
            pno = re.sub(r'<[^>]+>', '', mnum.group(1)).strip()
            desc = re.sub(r'<[^>]+>', '', mname.group(1)).strip()
            if not pno:
                continue
            c.execute('INSERT OR IGNORE INTO part (sec_url, item, part_no, "desc", qty) VALUES (?,?,?,?,?)',
                      (url, '', pno, desc, 1))
            ins += max(0, c.execute('SELECT changes()').fetchone()[0])
        if ins > 0:
            c.execute('UPDATE section SET part_done=1 WHERE url=?', (url,))
            ok += 1
        else:
            err += 1
        conn.commit()
        time.sleep(0.5)
    except Exception:
        err += 1
conn.close()
print(f"DONE: {ok}/{len(sections)} ok, {err} errors")
''')
        result = run([script], timeout=600)
        if result.startswith("ERROR"):
            return f"ERROR: 爬虫脚本运行失败 {result[-150:]}"
        if not result.startswith("DONE"):
            return f"ERROR: 异常输出 {result[-150:]}"
        return f"自动爬取完成: {result[-200:]}"
    except Exception as e:
        return f"ERROR: 自动爬取失败 {e}"
    finally:
        for p in (script, sections_file):
            try:
                if os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass

def try_auto_execute(rid, title, task_type, content):
    if should_auto_execute(title, task_type):
        return auto_execute_crawl(rid, title, content)
    return None

def _cycle():
    log("=== 巡检开始 ===")
    sync_out = run(["shared_mem.py", "sync"], timeout=60)
    log(f"经验同步: {sync_out[:120]}")
    if INSTANCE_NAME and not INSTANCE_TAGS:
        log("  未配置标签，跳过自动认领（防全量抢单）")
    elif INSTANCE_NAME:
        for rid, title, typ, content, assignee in get_pending_tasks():
            if assignee and assignee != INSTANCE_NAME:
                log(f"  跳过(指派给{assignee}): {title}")
                continue
            if not task_matches_tags(typ, title, INSTANCE_TAGS):
                continue
            if not should_auto_execute(title, typ):
                log(f"  非OEM收尾任务，留给AI: {title}")
                # 指派给本实例的非自动任务，写本地待办通知，云电脑AI可读
                if not assignee or assignee == INSTANCE_NAME:
                    try:
                        pending_file = os.path.join(PROJECT, "_pending_ai_tasks.txt")
                        with open(pending_file, 'a', encoding='utf-8') as f:
                            f.write(f"[{datetime.datetime.now().strftime('%m-%d %H:%M')}] {rid} | {typ} | {title}\n")
                    except OSError:
                        pass
                continue
            log(f"  自动认领: {title} ({rid})")
            claim_out = run(["sharedtask.py", "claim", rid, INSTANCE_NAME], timeout=30)
            if "OK" not in claim_out or claim_out.startswith("ERROR"):
                log(f"  认领失败: {claim_out[:120]}")
                continue
            ver = run(["sharedtask.py", "view", rid], timeout=20)
            if "处理中" not in ver:
                log(f"  认领校验失败: {ver[:120]}")
                continue
            result = try_auto_execute(rid, title, typ, content)
            if result is None:
                log(f"  需AI处理: {title}")
                continue
            if result.startswith("ERROR"):
                run(["sharedtask.py", "fail", rid, result[:500]], timeout=60)
                log(f"  执行失败已上报: {title}")
            else:
                run(["sharedtask.py", "complete", rid, result[:500]], timeout=60)
                log(f"  自动完成: {title}")
    out = run(["check_done.py"], timeout=60)
    log(f"check_done: {out[:150]}")
    out2 = run(["sharedtask.py", "watchdog", "--auto"], timeout=30)
    log(f"watchdog: {out2[:100]}")
    log("=== 巡检结束 ===")

def cycle():
    fd = acquire_cycle_lock()
    if fd is None:
        log("另一daemon正在巡检，跳过本轮")
        return
    try:
        _cycle()
    except Exception as e:
        log(f"巡检异常: {e}")
    finally:
        release_cycle_lock(fd)

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
        log(f"daemon v3.0启动，实例={INSTANCE_NAME}, 标签={INSTANCE_TAGS}")
    else:
        log("daemon v3.0启动（仅回收模式）")
    auto_update()
    boot_out = run(["shared_mem.py", "bootstrap"], timeout=120)
    log(f"启动经验同步: {boot_out[:150]}")
    if a.once:
        try:
            cycle()
        except Exception as e:
            log(f"once模式异常: {e}")
        return
    while True:
        try:
            cycle()
        except Exception as e:
            log(f"巡检异常: {e}")
        time.sleep(a.interval)

if __name__ == "__main__":
    main()
