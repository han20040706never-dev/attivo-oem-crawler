# -*- coding: utf-8 -*-
"""
shared_mem.py — 本地↔云电脑共享记忆同步
飞书共享记忆表 + GitHub SHARED_MEMORY.md 双通道
用法: python shared_mem.py push "标题" "类型" "内容" "标签1,标签2"
      python shared_mem.py pull [数量]
      python shared_mem.py sync-github
"""
import sys, io, os, json, subprocess, datetime
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

BASE_TOKEN = "MYQybnKkZaXY2Yswagyc7pKNnRf"
TABLE_ID = "tbl2oncwMgoSEUl4"
GH_REPO = "han20040706never-dev/attivo-oem-crawler"
GH_PATH = "SHARED_MEMORY.md"

def push(title, mtype, content, tags="", source="本地豆包"):
    """写入飞书共享记忆表"""
    record = {
        "标题": title,
        "类型": [mtype],
        "内容": content,
        "来源": [source],
        "时间": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    if tags:
        record["标签"] = tags.split(",")
    payload = json.dumps({"create_records": [record]}, ensure_ascii=False)
    try:
        r = subprocess.run(
            ["lark-cli", "base", "+record-batch-create",
             "--base-token", BASE_TOKEN, "--table-id", TABLE_ID,
             "--json", payload, "--as", "user"],
            capture_output=True, text=True, timeout=30, encoding='utf-8')
        data = json.loads(r.stdout) if r.stdout else {}
        if data.get("ok"):
            print(f"OK: 已写入共享记忆 - {title}")
        else:
            print(f"FAIL: {data.get('error',{}).get('message', r.stderr[:200])}")
    except Exception as e:
        print(f"FAIL: {e}")

def search(keyword):
    """按关键词检索本地共享记忆文件+飞书表"""
    import os
    mem_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "SHARED_MEMORY.md")
    hits = []
    if os.path.exists(mem_file):
        with open(mem_file, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f, 1):
                if keyword.lower() in line.lower():
                    hits.append(f"[GitHub L{i}] {line.strip()[:120]}")
    print(f"=== 搜索'{keyword}'，命中{len(hits)}条 ===")
    for h in hits[:20]:
        print(h)
    if not os.path.exists(mem_file):
        print("本地无共享记忆文件，先执行 sync-github")


def relevant(keywords, top_n=5):
    """多关键词相关度检索：同义词扩展+按匹配数量排序"""
    kws = [k.strip().lower() for k in keywords.split() if k.strip()]
    if not kws:
        print("请提供关键词"); return
    # 同义词扩展
    syn_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "synonyms.json")
    expanded = set(kws)
    if os.path.exists(syn_file):
        try:
            with open(syn_file, 'r', encoding='utf-8') as f:
                syns = json.load(f)
            for kw in kws:
                for term, alist in syns.items():
                    if kw == term.lower() or kw in [a.lower() for a in alist]:
                        expanded.add(term.lower())
                        for a in alist:
                            expanded.add(a.lower())
        except:
            pass
    expanded = list(expanded)
    mem_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "SHARED_MEMORY.md")
    results = []
    if os.path.exists(mem_file):
        with open(mem_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        for i, line in enumerate(lines):
            score = sum(1 for kw in expanded if kw in line.lower())
            if score > 0:
                start = max(0, i - 1)
                end = min(len(lines), i + 3)
                context = "".join(lines[start:end]).strip()[:200]
                results.append((score, "[GitHub]", context))
    # 飞书记忆表
    try:
        r = subprocess.run(
            ["lark-cli", "base", "+record-list",
             "--base-token", BASE_TOKEN, "--table-id", TABLE_ID,
             "--limit", "200", "--format", "json", "--as", "user"],
            capture_output=True, text=True, timeout=30, encoding='utf-8')
        data = json.loads(r.stdout) if r.stdout.strip() else {}
        if data.get("ok"):
            d = data.get("data", {})
            rows, cols = d.get("data", []), d.get("fields", [])
            idx = {name: i for i, name in enumerate(cols)}
            for row in rows:
                def g(name):
                    i = idx.get(name, -1)
                    v = row[i] if 0 <= i < len(row) else ""
                    if isinstance(v, list): v = v[0] if v else ""
                    return str(v) if v else ""
                title = g("标题")
                content = g("内容")
                mtype = g("类型")
                text = f"{title} {content}".lower()
                score = sum(1 for kw in expanded if kw in text)
                if score > 0:
                    results.append((score, f"[飞书|{mtype}]", f"{title}: {content[:150]}"))
    except Exception as e:
        print(f"飞书检索失败: {e}")
    results.sort(key=lambda x: -x[0])
    print(f"=== 相关经验（原始词:{kws}，扩展后{len(expanded)}词，命中{len(results)}条，Top{top_n}） ===")
    for score, src, ctx in results[:top_n]:
        print(f"  匹配{score}词 {src} {ctx}")
    if not results:
        print("  无相关经验")
    return results[:top_n]


def pull(limit=10):
    """读取飞书共享记忆表最新记录"""
    r = subprocess.run(
        ["lark-cli", "base", "+record-list",
         "--base-token", BASE_TOKEN, "--table-id", TABLE_ID,
         "--page-size", str(limit), "--format", "json", "--as", "user"],
        capture_output=True, text=True, timeout=30, encoding='utf-8')
    try:
        data = json.loads(r.stdout)
        d = data.get("data", {})
        rows = d.get("data", [])
        cols = d.get("fields", [])
        # 用字段名映射，不依赖顺序
        idx = {name: i for i, name in enumerate(cols)} if cols else {}
        def g(row, name):
            i = idx.get(name, -1)
            return row[i] if i >= 0 and i < len(row) else ""
        print(f"=== 共享记忆最新{len(rows)}条 ===")
        for row in rows:
            title = g(row, "标题")
            content = g(row, "内容")
            source = g(row, "来源")
            mtype = g(row, "类型")
            if isinstance(source, list): source = source[0] if source else ""
            if isinstance(mtype, list): mtype = mtype[0] if mtype else ""
            print(f"[{mtype}|{source}] {title}")
            if content:
                print(f"  {content[:120]}")
    except Exception as e:
        print(f"FAIL: {e}")
        print(r.stdout[:300] if r.stdout else r.stderr[:300])

def sync_github(direction="pull"):
    """同步GitHub SHARED_MEMORY.md"""
    import requests, base64
    url = f"https://api.github.com/repos/{GH_REPO}/contents/{GH_PATH}"
    headers = {"Authorization": f"token {config.GITHUB_PAT}", "Accept": "application/vnd.github.v3+json"}
    r = requests.get(url, headers=headers, timeout=15)
    if r.status_code == 200:
        content = base64.b64decode(r.json()["content"]).decode('utf-8')
        local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "SHARED_MEMORY.md")
        with open(local_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"OK: 已拉取GitHub SHARED_MEMORY.md ({len(content)}字) -> {local_path}")
    else:
        print(f"FAIL: GitHub获取失败 {r.status_code}")

def sync():
    """轻量增量同步：检测GitHub和飞书变更，只拉新内容，输出变更摘要"""
    import requests, base64, datetime
    state_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".mem_state.json")
    state = {}
    if os.path.exists(state_file):
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
        except:
            pass
    
    changes = []
    # 1. 检测GitHub SHARED_MEMORY.md变更（通过commit SHA）
    try:
        url = f"https://api.github.com/repos/{GH_REPO}/commits?path={GH_PATH}&per_page=1"
        headers = {"Authorization": f"token {config.GITHUB_PAT}", "Accept": "application/vnd.github.v3+json"}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200 and r.json():
            latest_sha = r.json()[0]["sha"]
            if latest_sha != state.get("github_sha"):
                sync_github("pull")
                state["github_sha"] = latest_sha
                changes.append("GitHub记忆已更新")
    except Exception as e:
        print(f"GitHub检测失败: {e}")
    
    # 2. 检测飞书新记录
    try:
        r = subprocess.run(
            ["lark-cli", "base", "+record-list",
             "--base-token", BASE_TOKEN, "--table-id", TABLE_ID,
             "--page-size", "5", "--format", "json", "--as", "user"],
            capture_output=True, text=True, timeout=30, encoding='utf-8')
        data = json.loads(r.stdout)
        d = data.get("data", {})
        rows, cols = d.get("data", []), d.get("fields", [])
        if rows and cols:
            idx = {name: i for i, name in enumerate(cols)}
            latest_time = ""
            for row in rows:
                t = row[idx.get("创建时间", -1)] if "创建时间" in idx else ""
                if isinstance(t, list) and t: t = t[0]
                if t and str(t) > latest_time:
                    latest_time = str(t)
            if latest_time and latest_time > state.get("feishu_last", ""):
                # 有新记录，拉最新3条
                pull(3)
                state["feishu_last"] = latest_time
                changes.append("飞书有新记忆")
    except Exception as e:
        print(f"飞书检测失败: {e}")
    
    state["last_sync"] = datetime.datetime.now().isoformat()
    with open(state_file, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    
    if changes:
        print(f"\n同步完成: {', '.join(changes)}")
    else:
        print("无变更，记忆已是最新")


def bootstrap():
    """启动引导：增量拉取飞书共享记忆+GitHub记忆，输出汇总供AI注入上下文"""
    import os, json, datetime
    state_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".mem_state.json")
    last_sync = ""
    if os.path.exists(state_file):
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                last_sync = json.load(f).get("last_sync", "")
        except:
            pass
    print("=== 启动引导：增量拉取共享记忆 ===")
    # 1. GitHub（用SHA判断是否更新）
    import requests, base64
    url = f"https://api.github.com/repos/{GH_REPO}/contents/{GH_PATH}"
    headers = {"Authorization": f"token {config.GITHUB_PAT}", "Accept": "application/vnd.github.v3+json"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            content = base64.b64decode(r.json()["content"]).decode('utf-8')
            print(f"\n--- GitHub共享记忆 ({len(content)}字) ---")
            print(content[:3000])
            if len(content) > 3000:
                print(f"...(共{len(content)}字，已截断，完整文件已同步到本地)")
            # 存本地
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "SHARED_MEMORY.md"), 'w', encoding='utf-8') as f:
                f.write(content)
    except Exception as e:
        print(f"GitHub拉取失败: {e}")
    # 1.5 下载云电脑AI操作指南（如不存在）
    guide_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "CLOUD_AI_GUIDE.md")
    if not os.path.exists(guide_path):
        try:
            guide_url = f"https://raw.githubusercontent.com/{GH_REPO}/main/CLOUD_AI_GUIDE.md"
            gr = requests.get(guide_url, timeout=10)
            if gr.status_code == 200:
                with open(guide_path, 'w', encoding='utf-8') as f:
                    f.write(gr.text)
                print(f"已下载云电脑AI操作指南: CLOUD_AI_GUIDE.md（{len(gr.text)}字），启动时请先阅读")
        except Exception:
            pass
    elif os.path.exists(guide_path):
        print("云电脑AI操作指南已存在: CLOUD_AI_GUIDE.md（启动时请先阅读）")
    # 2. 飞书增量拉取（只拉最近10条，新对话看最新就够）
    print("\n--- 飞书共享记忆最新10条 ---")
    pull(10)
    # 3. 记录同步时间
    with open(state_file, 'w', encoding='utf-8') as f:
        json.dump({"last_sync": datetime.datetime.now().isoformat()}, f)
    print("\n=== 引导完成 ===")


def push_github(section, content):
    """追加内容到GitHub SHARED_MEMORY.md指定section并push"""
    import requests, base64, datetime
    url = f"https://api.github.com/repos/{GH_REPO}/contents/{GH_PATH}"
    headers = {"Authorization": f"token {config.GITHUB_PAT}", "Accept": "application/vnd.github.v3+json"}
    r = requests.get(url, headers=headers, timeout=15)
    if r.status_code != 200:
        print(f"FAIL: 获取GitHub文件失败 {r.status_code}")
        return
    sha = r.json()["sha"]
    current = base64.b64decode(r.json()["content"]).decode('utf-8')
    # 在指定section下追加
    marker = f"## {section}"
    entry = f"\n- [{datetime.datetime.now().strftime('%m-%d %H:%M')}] {content}"
    if marker in current:
        updated = current.replace(marker, marker + "\n" + entry, 1)
    else:
        updated = current + f"\n\n## {section}\n{entry}\n"
    # 更新最后更新时间
    import re
    updated = re.sub(r'\*最后更新：.*?\*', f'*最后更新：{datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}*', updated)
    payload = {
        "message": f"sync: {section} - {content[:40]}",
        "content": base64.b64encode(updated.encode()).decode(),
        "sha": sha
    }
    r2 = requests.put(url, headers=headers, json=payload, timeout=15)
    if r2.status_code in (200, 201):
        print(f"OK: 已push到GitHub SHARED_MEMORY.md [{section}]")
    else:
        print(f"FAIL: push失败 {r2.status_code}: {r2.text[:150]}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: push <标题> <类型> <内容> [标签] | pull [数量] | sync-github | push-github <section> <内容>")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "push" and len(sys.argv) >= 5:
        push(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5] if len(sys.argv)>5 else "")
    elif cmd == "pull":
        pull(int(sys.argv[2]) if len(sys.argv)>2 else 10)
    elif cmd == "sync-github":
        sync_github()
    elif cmd == "push-github" and len(sys.argv) >= 4:
        push_github(sys.argv[2], sys.argv[3])
    elif cmd == "bootstrap":
        bootstrap()
    elif cmd == "sync":
        sync()
    elif cmd == "search" and len(sys.argv) >= 3:
        search(" ".join(sys.argv[2:]))
    elif cmd == "relevant" and len(sys.argv) >= 3:
        relevant(" ".join(sys.argv[2:]))
    else:
        print("参数错误")
