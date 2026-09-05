# -*- coding: utf-8 -*-
"""通用 GitHub 内容推送(无git环境): python gh_push.py 文件1 [文件2 ...]
contents API: 先 GET 取 sha(更新) 再 PUT(新建/更新)。走 config.PROXIES 代理。
好脚本留存复用; config.py 已 .gitignore 不上传。"""
import sys, io, os, time, base64, requests
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import GITHUB_PAT, PROXIES

OWNER, REPO, BRANCH = "han20040706never-dev", "attivo-oem-crawler", "main"
H = {"Authorization": f"token {GITHUB_PAT}", "Accept": "application/vnd.github+json"}
BASE = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/"


def push(local, repo_path=None):
    repo_path = repo_path or os.path.basename(local)
    url = BASE + repo_path
    with open(local, "rb") as f:
        content = base64.b64encode(f.read()).decode()
    def _req(method, **kw):
        for attempt in range(3):
            try:
                return requests.request(method, url, headers=H, proxies=PROXIES, **kw)
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(1.5)
    sha = None
    try:
        r = _req("GET", params={"ref": BRANCH}, timeout=30)
        if r.status_code == 200:
            sha = r.json().get("sha")
        elif r.status_code != 404:
            print(f"WARN {repo_path} GET sha HTTP {r.status_code}, 按新建处理")
    except Exception as e:
        print(f"SKIP {repo_path} GET sha 连续失败: {str(e)[:60]} (不盲PUT)")
        return False
    body = {"message": f"update {repo_path} via gh_push", "content": content,
            "branch": BRANCH}
    if sha:
        body["sha"] = sha
    try:
        r = _req("PUT", json=body, timeout=60)
    except Exception as e:
        print(f"FAIL {repo_path} PUT 连续失败: {str(e)[:60]}")
        return False
    if r.status_code in (200, 201):
        print(f"OK {repo_path} {'更新' if sha else '新建'} -> {r.json()['content']['html_url']}")
        return True
    print(f"FAIL {repo_path} {r.status_code} {r.text[:120]}")
    return False


if __name__ == "__main__":
    try:
        args = [a for a in sys.argv[1:] if not a.startswith("-")]
        ok = 0
        for a in args:
            p = a if os.path.isabs(a) else os.path.join(os.path.dirname(os.path.abspath(__file__)), a)
            if os.path.exists(p) and push(p):
                ok += 1
        print(f"完成 {ok}/{len(args)}")
    except Exception as e:
        print(f"FAIL {type(e).__name__}: {e}")
