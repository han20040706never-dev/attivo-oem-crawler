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

def _fetch_github_file(fname):
    """从GitHub获取文件内容，先raw再api.github.com备用，返回bytes或None"""
    import requests, base64
    # 通道1: raw.githubusercontent.com（快但常超时）
    try:
        r = requests.get(GITHUB_RAW + fname, timeout=5)
        if r.status_code == 200:
            return r.content
    except Exception:
        pass
    # 通道2: api.github.com contents API（base64，更稳定）
    try:
        sys.path.insert(0, PROJECT)
        import config
        H = {'Authorization': f'token {config.GITHUB_PAT}', 'Accept': 'application/vnd.github.v3+json'}
        r2 = requests.get(f'https://api.github.com/repos/han20040706never-dev/attivo-oem-crawler/contents/{fname}',
                          headers=H, timeout=15)
        if r2.status_code == 200:
            return base64.b64decode(r2.json()['content'])
    except Exception:
        pass
    return None


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
            remote_bytes = _fetch_github_file(fname)
            if remote_bytes is None:
                failures.append(f"{fname}:双通道均失败")
                continue
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
        # 验证：解析DONE输出，ok=0说明全部失败，不应标成功
        import re
        m = re.search(r'DONE: (\d+)/(\d+) ok', result)
        if m and int(m.group(1)) == 0:
            return f"ERROR: 爬虫0成功({result[-150:]})"
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

def should_auto_selfcheck(title):
    """自检任务自动执行：标题含'自检'或'心跳更新'"""
    return ("自检" in title) or ("心跳更新" in title)

def auto_selfcheck(rid, title):
    """云电脑自检：更新心跳+报告状态+代码版本"""
    try:
        import datetime, platform
        # 更新心跳
        update_heartbeat()
        # 收集状态
        status = []
        status.append(f"时间: {datetime.datetime.now().isoformat()}")
        status.append(f"实例: {INSTANCE_NAME}")
        status.append(f"标签: {INSTANCE_TAGS}")
        status.append(f"Python: {platform.python_version()}")
        status.append(f"工作目录: {PROJECT}")
        # 检查关键文件
        for f in ["daemon.py", "sharedtask.py", "shared_mem.py", "config.py"]:
            fp = os.path.join(PROJECT, f)
            if os.path.exists(fp):
                mtime = datetime.datetime.fromtimestamp(os.path.getmtime(fp)).strftime("%m-%d %H:%M")
                status.append(f"  {f}: 存在(更新于{mtime})")
            else:
                status.append(f"  {f}: 缺失!")
        # 检查oemkb.db
        db = os.path.join(PROJECT, "oemkb.db")
        if os.path.exists(db):
            import sqlite3
            conn = sqlite3.connect(db, timeout=10)
            cnt = conn.execute("SELECT COUNT(*) FROM part").fetchone()[0]
            conn.close()
            status.append(f"  oemkb.db: {cnt}零件")
        result = "自检完成:\n" + "\n".join(status)
        log(f"  自检完成: {result[:200]}")
        return result
    except Exception as e:
        return f"ERROR: 自检失败 {e}"

def try_auto_execute(rid, title, task_type, content):
    if should_auto_selfcheck(title):
        return auto_selfcheck(rid, title)
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
            if not should_auto_execute(title, typ) and not should_auto_selfcheck(title):
                log(f"  非自动任务，留给AI: {title}")
                # 指派给本实例的非自动任务，写本地待办通知，云电脑AI可读
                if not assignee or assignee == INSTANCE_NAME:
                    try:
                        pending_file = os.path.join(PROJECT, "_pending_ai_tasks.txt")
                        existing = ""
                        if os.path.exists(pending_file):
                            with open(pending_file, 'r', encoding='utf-8') as f:
                                existing = f.read()
                        if rid not in existing:
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
    sync_memory()
    sync_local_memory()
    update_heartbeat()
    check_heartbeat()
    check_stale_tasks()
    check_token_usage()
    update_state()
    log("=== 巡检结束 ===")


def sync_memory():
    """增量同步GitHub共享记忆到本地（节流30分钟），让relevant搜索用最新经验"""
    try:
        stamp = os.path.join(PROJECT, ".mem_sync_stamp")
        now = time.time()
        if os.path.exists(stamp):
            if now - os.path.getmtime(stamp) < 1800:
                return
        out = run(["shared_mem.py", "sync"], timeout=60)
        # 同时拉取本地豆包记忆LOCAL_MEMORY.md（云电脑运行期间也能获取本地最新经验）
        try:
            lm_bytes = _fetch_github_file("LOCAL_MEMORY.md")
            if lm_bytes and len(lm_bytes) > 100:
                lm_path = os.path.join(PROJECT, "LOCAL_MEMORY.md")
                old = open(lm_path, 'rb').read() if os.path.exists(lm_path) else b''
                if old != lm_bytes:
                    _atomic_write(lm_path, lm_bytes)
                    log(f"本地记忆已更新: {len(lm_bytes)}字")
        except Exception:
            pass
        with open(stamp, 'w') as f:
            f.write(str(now))
        log(f"共享记忆同步: {out[:100]}")
    except Exception as e:
        log(f"共享记忆同步失败: {e}")


def update_heartbeat():
    """每次巡检更新本实例的last_seen到instances.json并push到GitHub（pull-merge-push防冲突）"""
    if not INSTANCE_NAME:
        return
    try:
        import datetime, requests
        reg_file = os.path.join(PROJECT, "instances.json")
        # pull最新
        try:
            r = requests.get(GITHUB_RAW + "instances.json", timeout=15)
            if r.status_code == 200:
                remote = r.json()
                with open(reg_file, 'w', encoding='utf-8') as f:
                    json.dump(remote, f, ensure_ascii=False, indent=2)
        except:
            pass
        # merge更新
        with open(reg_file, 'r', encoding='utf-8') as f:
            reg = json.load(f)
        instances = reg.setdefault("instances", {})
        inst = instances.setdefault(INSTANCE_NAME, {"tags": INSTANCE_TAGS or [], "completed": 0, "failed": 0})
        inst["last_seen"] = datetime.datetime.now().isoformat()
        inst["tags"] = INSTANCE_TAGS or inst.get("tags", [])
        with open(reg_file, 'w', encoding='utf-8') as f:
            json.dump(reg, f, ensure_ascii=False, indent=2)
        # push到GitHub
        try:
            import base64
            sys.path.insert(0, PROJECT)
            import config
            H = {'Authorization': f'token {config.GITHUB_PAT}', 'Accept': 'application/vnd.github.v3+json'}
            REPO = 'han20040706never-dev/attivo-oem-crawler'
            content = open(reg_file, 'rb').read()
            r2 = requests.get(f'https://api.github.com/repos/{REPO}/contents/instances.json', headers=H, timeout=15)
            sha = r2.json().get('sha') if r2.status_code == 200 else None
            p = {'message': f'heartbeat: {INSTANCE_NAME}', 'content': base64.b64encode(content).decode()}
            if sha: p['sha'] = sha
            requests.put(f'https://api.github.com/repos/{REPO}/contents/instances.json', headers=H, json=p, timeout=15)
        except Exception as e:
            log(f"  心跳push失败: {e}")
    except Exception as e:
        log(f"心跳更新失败: {e}")


def sync_local_memory():
    """本地MEMORY.md过滤机密后同步到GitHub LOCAL_MEMORY.md（云电脑bootstrap可拉取），节流30分钟"""
    try:
        stamp = os.path.join(PROJECT, ".local_mem_stamp")
        now = time.time()
        if os.path.exists(stamp):
            if now - os.path.getmtime(stamp) < 1800:
                return
        mem_file = os.path.join(PROJECT, "MEMORY.md")
        if not os.path.exists(mem_file):
            return
        with open(mem_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        # 过滤机密行（含密码/密钥/token/secret/PWD/key等关键词的行）
        SECRET_KEYWORDS = ["密码", "密钥", "token", "secret", "PWD", "password", "api_key", "API_KEY", "private"]
        filtered = []
        for line in lines:
            if not any(kw.lower() in line.lower() for kw in SECRET_KEYWORDS):
                filtered.append(line)
        content = "".join(filtered)
        if len(content.strip()) < 50:
            return
        # push到GitHub
        import requests, base64, hashlib
        sys.path.insert(0, PROJECT)
        import config
        H = {'Authorization': f'token {config.GITHUB_PAT}', 'Accept': 'application/vnd.github.v3+json'}
        REPO = 'han20040706never-dev/attivo-oem-crawler'
        content_bytes = content.encode('utf-8')
        md5 = hashlib.md5(content_bytes).hexdigest()
        # 检查上次同步的md5
        last_md5 = ""
        if os.path.exists(stamp):
            with open(stamp, 'r') as f:
                last_md5 = f.read().strip()
        if md5 == last_md5:
            return
        r = requests.get(f'https://api.github.com/repos/{REPO}/contents/LOCAL_MEMORY.md', headers=H, timeout=15)
        sha = r.json().get('sha') if r.status_code == 200 else None
        p = {'message': f'LOCAL_MEMORY.md sync ({md5[:8]})', 'content': base64.b64encode(content_bytes).decode()}
        if sha: p['sha'] = sha
        r2 = requests.put(f'https://api.github.com/repos/{REPO}/contents/LOCAL_MEMORY.md', headers=H, json=p, timeout=30)
        if r2.status_code in (200, 201):
            with open(stamp, 'w') as f:
                f.write(md5)
            log(f"本地记忆已同步到GitHub ({len(content)}字)")
        else:
            log(f"本地记忆同步失败: {r2.status_code}")
    except Exception as e:
        log(f"本地记忆同步异常: {e}")


def check_heartbeat():
    """检查云电脑实例心跳，先从GitHub拉最新instances.json，last_seen超过30分钟告警"""
    try:
        import json, datetime, requests
        reg_file = os.path.join(PROJECT, "instances.json")
        # 先从GitHub拉最新的instances.json（本地可能是旧的）
        try:
            r = requests.get(GITHUB_RAW + "instances.json", timeout=15)
            if r.status_code == 200:
                remote = r.json()
                with open(reg_file, 'w', encoding='utf-8') as f:
                    json.dump(remote, f, ensure_ascii=False, indent=2)
        except:
            pass
        if not os.path.exists(reg_file):
            return
        with open(reg_file, 'r', encoding='utf-8') as f:
            reg = json.load(f)
        now = datetime.datetime.now()
        stale = []
        for name, info in reg.get("instances", {}).items():
            last = info.get("last_seen", "")
            if not last:
                stale.append((name, "无心跳记录"))
                continue
            try:
                last_time = datetime.datetime.fromisoformat(last.replace("Z", "+00:00").replace("+08:00", ""))
                elapsed = (now - last_time).total_seconds() / 60
                if elapsed > 30:
                    stale.append((name, f"{elapsed:.0f}分钟无心跳"))
            except:
                stale.append((name, "心跳时间解析失败"))
        if stale:
            msg = "实例心跳告警: " + ", ".join(f"{n}({s})" for n, s in stale)
            recovery = "恢复步骤：在对应云电脑上运行 cd C:\\attivo-collab; python daemon.py --instance \"实例名\" --tags \"标签\" --interval 300，或运行 python install_daemon_task.py 注册计划任务保活"
            log(msg)
            log(recovery)
            # 自动创建自检任务唤醒云电脑（每实例30分钟内最多一个，用本地缓存去重）
            try:
                sys.path.insert(0, PROJECT)
                from sharedtask import push
                sc_cache = os.path.join(PROJECT, "_selfcheck_cache.json")
                last_sc = {}
                if os.path.exists(sc_cache):
                    try:
                        last_sc = json.load(open(sc_cache, 'r', encoding='utf-8'))
                    except:
                        last_sc = {}
                for inst_name, _ in stale:
                    last_time = last_sc.get(inst_name, 0)
                    if time.time() - last_time < 1800:  # 30分钟内不重复创建
                        continue
                    rid = push("其他", f"{inst_name}自检+心跳更新",
                               f"云电脑实例【{inst_name}】心跳超时。请执行：\n"
                               f"1. cd C:\\attivo-collab\n"
                               f"2. python daemon.py --instance \"{inst_name}\" --tags \"标签\" --interval 300（后台启动）\n"
                               f"   或 python install_daemon_task.py --instance \"{inst_name}\" --tags \"标签\" --interval 300（注册计划任务保活）\n"
                               f"3. 确认config.py存在且密钥正确\n"
                               f"4. 运行 python sharedtask.py complete <此任务ID> \"自检完成，daemon已启动\" \n"
                               f"这是自动唤醒任务，daemon运行时会auto_selfcheck自动执行。",
                               "本地豆包(自动唤醒)", inst_name, "高")
                    last_sc[inst_name] = time.time()
                    log(f"  已发自检任务唤醒{inst_name}: {rid}")
                with open(sc_cache, 'w', encoding='utf-8') as f:
                    json.dump(last_sc, f, ensure_ascii=False)
            except Exception as e2:
                log(f"  自检任务创建失败: {e2}")
            # 写入通知文件，本地AI对话开始时可读
            notif_file = os.path.join(PROJECT, "_notifications.json")
            notifs = []
            if os.path.exists(notif_file):
                try:
                    notifs = json.load(open(notif_file, 'r', encoding='utf-8'))
                except:
                    notifs = []
            notifs.append({"time": now.isoformat(), "type": "heartbeat", "msg": msg, "recovery": recovery})
            notifs = notifs[-20:]
            with open(notif_file, 'w', encoding='utf-8') as f:
                json.dump(notifs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"心跳检查失败: {e}")


def check_stale_tasks():
    """超过12小时未认领的待处理任务自动提升优先级到高，防止任务被遗忘"""
    try:
        import datetime
        sys.path.insert(0, PROJECT)
        from sharedtask import cli, BASE, TABLE, cell
        cache_file = os.path.join(PROJECT, "_task_first_seen.json")
        first_seen = {}
        if os.path.exists(cache_file):
            try:
                first_seen = json.load(open(cache_file, 'r', encoding='utf-8'))
            except:
                first_seen = {}
        now = time.time()
        # 获取待处理任务列表
        data = cli(["+record-list", "--base-token", BASE, "--table-id", TABLE,
                    "--filter-json", '{"conjunction":"and","conditions":[{"field_name":"状态","operator":"is","value":["待处理"]}]}',
                    "--limit", "50", "--format", "json", "--as", "user"])
        if not data or not data.get("ok"):
            return
        d = data.get("data", {})
        rows, cols = d.get("data", []), d.get("fields", [])
        fmap_idx = {name: i for i, name in enumerate(cols)}
        stale_upgraded = []
        for row in rows:
            rid = row[0] if row else ""
            if not rid:
                continue
            def g3(nm):
                i = fmap_idx.get(nm, -1)
                return cell(row[i]) if 0 <= i < len(row) else ""
            title = g3("任务标题")
            priority = g3("优先级")
            # 记录首次发现时间
            if rid not in first_seen:
                first_seen[rid] = now
            elif now - first_seen[rid] > 43200 and priority != "高":  # 12小时
                # 提升优先级到高
                try:
                    cli(["+record-batch-update", "--base-token", BASE, "--table-id", TABLE,
                         "--json", json.dumps({"update_records": {rid: {"优先级": ["高"]}}}, ensure_ascii=False),
                         "--as", "user"])
                    stale_upgraded.append(title[:40])
                    log(f"  任务老化提升优先级: {title[:40]}")
                except:
                    pass
        # 清理已不存在的任务
        valid_rids = {row[0] for row in rows if row}
        first_seen = {k: v for k, v in first_seen.items() if k in valid_rids}
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(first_seen, f, ensure_ascii=False)
        if stale_upgraded:
            notif_file = os.path.join(PROJECT, "_notifications.json")
            notifs = []
            if os.path.exists(notif_file):
                try:
                    notifs = json.load(open(notif_file, 'r', encoding='utf-8'))
                except:
                    notifs = []
            notifs.append({"time": datetime.datetime.now().isoformat(), "type": "stale_task",
                           "msg": f"{len(stale_upgraded)}个任务超12小时未认领，已自动提升优先级: {', '.join(stale_upgraded[:3])}"})
            with open(notif_file, 'w', encoding='utf-8') as f:
                json.dump(notifs[-20:], f, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"任务老化检查失败: {e}")


def check_token_usage():
    """检查DeepSeek API当天用量，超阈值写告警（DeepSeek充50元，代码专用）"""
    try:
        import datetime
        token_log = os.path.join(PROJECT, "_token_usage.jsonl")
        if not os.path.exists(token_log):
            return
        today = datetime.date.today().isoformat()
        ds_input, ds_output, ds_calls = 0, 0, 0
        with open(token_log, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    rec = json.loads(line.strip())
                    if rec.get("date") == today and "deepseek" in rec.get("model", "").lower():
                        ds_input += rec.get("prompt_tokens", 0)
                        ds_output += rec.get("completion_tokens", 0)
                        ds_calls += 1
                except:
                    continue
        if ds_calls == 0:
            return
        # DeepSeek价格: 输入1元/百万, 输出2元/百万
        cost = ds_input / 1e6 * 1.0 + ds_output / 1e6 * 2.0
        # 每天阈值3元（约占50元总额的6%），超了告警
        if cost > 3.0:
            notif_file = os.path.join(PROJECT, "_notifications.json")
            notifs = []
            if os.path.exists(notif_file):
                try:
                    notifs = json.load(open(notif_file, 'r', encoding='utf-8'))
                except:
                    notifs = []
            # 去重：同一天只告警一次
            today_key = f"token_alert_{today}"
            if not any(n.get("type") == today_key for n in notifs):
                notifs.append({"time": datetime.datetime.now().isoformat(), "type": today_key,
                               "msg": f"DeepSeek API今日用量告警: {ds_calls}次调用, 输入{ds_input}token, 输出{ds_output}token, 约{cost:.2f}元。阈值3元/天，建议减少代码调用或切免费API。"})
                with open(notif_file, 'w', encoding='utf-8') as f:
                    json.dump(notifs[-20:], f, ensure_ascii=False, indent=2)
                log(f"Token用量告警: {cost:.2f}元/{ds_calls}次")
    except Exception as e:
        log(f"Token用量检查失败: {e}")


def update_state():
    """持久化系统运行状态到_state.json，新对话直接读不用重查"""
    try:
        import datetime
        state = {"last_update": datetime.datetime.now().isoformat()}
        # 任务统计
        try:
            pending_out = run(["sharedtask.py", "pending"], timeout=20)
            state["pending_count"] = pending_out.count("待处理") if "待处理" in pending_out else 0
        except:
            state["pending_count"] = -1
        # 实例状态
        try:
            reg_file = os.path.join(PROJECT, "instances.json")
            if os.path.exists(reg_file):
                with open(reg_file, 'r', encoding='utf-8') as f:
                    reg = json.load(f)
                state["instances"] = reg.get("instances", {})
        except:
            pass
        # token用量
        try:
            sys.path.insert(0, PROJECT)
            import ai_router
            state["token_usage_7d"] = ai_router.token_stats(days=7)
        except:
            pass
        # 爬虫进度
        try:
            import sqlite3
            db_path = os.path.join(PROJECT, "oemkb.db")
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM part")
                state["oemkb_parts"] = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM section WHERE part_done=1")
                done = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM section")
                total = cur.fetchone()[0]
                state["oemkb_section_progress"] = f"{done}/{total}"
                conn.close()
        except:
            pass
        # 通知
        try:
            notif_file = os.path.join(PROJECT, "_notifications.json")
            if os.path.exists(notif_file):
                notifs = json.load(open(notif_file, 'r', encoding='utf-8'))
                state["recent_notifications"] = notifs[-5:]
        except:
            pass
        state_file = os.path.join(PROJECT, "_state.json")
        _atomic_write(state_file, json.dumps(state, ensure_ascii=False, indent=2).encode('utf-8'))
        log(f"状态已持久化: pending={state.get('pending_count')} parts={state.get('oemkb_parts', '?')}")
    except Exception as e:
        log(f"状态持久化失败: {e}")

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
