# -*- coding: utf-8 -*-
"""
remote_heal.py — 远程自愈模块
外接大脑检测到实例超时 → 写 restart flag 到 GitHub
云实例 keepalive/daemon 检测到 flag → 执行重启 → 删除 flag

用法：
  python remote_heal.py flag <实例名> [原因]     # 外接大脑：写重启flag
  python remote_heal.py check <实例名>           # 云实例：检查是否有自己的flag
  python remote_heal.py clear <实例名>           # 云实例：重启后清除flag
  python remote_heal.py list                     # 列出所有待处理flag
"""
import sys, io, os, json, datetime, requests, base64, re, time

sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import config
except ImportError:
    config = None

PROJECT = os.path.dirname(os.path.abspath(__file__))
REPO = 'han20040706never-dev/attivo-oem-crawler'
FLAG_DIR = 'restart_flags'
FLAG_TTL_MIN = 60  # flag 60分钟后自动过期（避免误触发）


def _gh_headers():
    token = getattr(config, 'GITHUB_PAT', '') if config else ''
    return {'Authorization': f'token {token}', 'Accept': 'application/vnd.github.v3+json'}


def _sanitize(name):
    return re.sub(r'[^\w\u4e00-\u9fff]+', '_', name).strip('_')


def _flag_path(instance_name):
    return f"{FLAG_DIR}/{_sanitize(instance_name)}.json"


def _gh_get(path):
    url = f'https://api.github.com/repos/{REPO}/contents/{path}'
    try:
        r = requests.get(url, headers=_gh_headers(), timeout=10)
        if r.status_code == 200:
            data = r.json()
            return base64.b64decode(data['content']).decode('utf-8'), data['sha']
    except Exception:
        pass
    return None, None


def _gh_put(path, content, sha=None, message="update"):
    url = f'https://api.github.com/repos/{REPO}/contents/{path}'
    payload = {'message': message, 'content': base64.b64encode(content.encode('utf-8')).decode()}
    if sha:
        payload['sha'] = sha
    try:
        r = requests.put(url, headers=_gh_headers(), json=payload, timeout=15)
        return r.status_code in (200, 201)
    except Exception:
        return False


def _gh_delete(path, sha):
    url = f'https://api.github.com/repos/{REPO}/contents/{path}'
    payload = {'message': f'clear flag', 'sha': sha}
    try:
        r = requests.delete(url, headers=_gh_headers(), json=payload, timeout=10)
        return r.status_code in (200, 204)
    except Exception:
        return False


def write_flag(instance_name, reason="心跳超时", triggered_by="外接大脑"):
    """外接大脑：写重启flag到GitHub"""
    now = datetime.datetime.now().isoformat()
    data = {
        "instance": instance_name,
        "reason": reason,
        "triggered_by": triggered_by,
        "created_at": now,
        "expires_at": (datetime.datetime.now() + datetime.timedelta(minutes=FLAG_TTL_MIN)).isoformat(),
        "version": "heal-v1",
    }
    content = json.dumps(data, ensure_ascii=False, indent=2)
    path = _flag_path(instance_name)

    # 检查是否已有未过期的flag
    existing, sha = _gh_get(path)
    if existing:
        try:
            old = json.loads(existing)
            exp = old.get("expires_at", "")
            if exp:
                exp_time = datetime.datetime.fromisoformat(exp)
                if exp_time > datetime.datetime.now():
                    print(f"SKIP: {instance_name} 已有未过期flag（{old.get('reason', '?')}，创建于{old.get('created_at', '?')}）")
                    return False
        except Exception:
            pass

    ok = _gh_put(path, content, sha, f"heal: restart {instance_name} - {reason[:30]}")
    if ok:
        print(f"OK: 已写重启flag → {instance_name}（原因:{reason}，触发者:{triggered_by}）")
        return True
    print(f"FAIL: 写flag失败 {instance_name}")
    return False


def check_flag(instance_name):
    """云实例：检查是否有针对自己的未过期flag，返回flag数据或None"""
    path = _flag_path(instance_name)
    content, sha = _gh_get(path)
    if not content:
        return None
    try:
        data = json.loads(content)
        exp = data.get("expires_at", "")
        if exp:
            exp_time = datetime.datetime.fromisoformat(exp)
            if exp_time < datetime.datetime.now():
                # 过期了，清除
                _gh_delete(path, sha)
                return None
        data["_sha"] = sha
        return data
    except Exception:
        return None


def clear_flag(instance_name):
    """云实例：重启成功后清除flag"""
    path = _flag_path(instance_name)
    content, sha = _gh_get(path)
    if not sha:
        print(f"SKIP: {instance_name} 无flag需清除")
        return True
    ok = _gh_delete(path, sha)
    if ok:
        print(f"OK: 已清除 {instance_name} 的重启flag")
    else:
        print(f"FAIL: 清除flag失败 {instance_name}")
    return ok


def list_flags():
    """列出所有待处理flag"""
    url = f'https://api.github.com/repos/{REPO}/contents/{FLAG_DIR}'
    try:
        r = requests.get(url, headers=_gh_headers(), timeout=10)
        if r.status_code != 200:
            print("无flag目录或为空")
            return []
        flags = []
        now = datetime.datetime.now()
        for f in r.json():
            if not f['name'].endswith('.json'):
                continue
            content, _ = _gh_get(f"{FLAG_DIR}/{f['name']}")
            if content:
                try:
                    data = json.loads(content)
                    exp = data.get("expires_at", "")
                    expired = False
                    if exp:
                        expired = datetime.datetime.fromisoformat(exp) < now
                    flags.append({
                        "instance": data.get("instance", f['name']),
                        "reason": data.get("reason", ""),
                        "created_at": data.get("created_at", ""),
                        "expired": expired,
                    })
                except Exception:
                    pass
        print(f"=== 待处理重启flag ({len(flags)}) ===")
        for f in flags:
            status = "❌已过期" if f["expired"] else "🟡待执行"
            print(f"  {status} {f['instance']} | {f['reason']} | {f['created_at']}")
        return flags
    except Exception as e:
        print(f"FAIL: 列出flag失败 {e}")
        return []


def auto_heal_stale_instances(timeout_min=30):
    """外接大脑：扫描所有超时实例，自动写重启flag"""
    sys.path.insert(0, PROJECT)
    try:
        from instances_shard import get_stale
        stale = get_stale(timeout_min)
    except Exception:
        # fallback: 读旧 instances.json
        stale = []
        try:
            r = requests.get(f'https://raw.githubusercontent.com/{REPO}/main/instances.json', timeout=10)
            if r.status_code == 200:
                reg = r.json()
                now = datetime.datetime.now()
                for name, info in reg.get("instances", {}).items():
                    last = info.get("last_seen", "")
                    if last:
                        try:
                            lt = datetime.datetime.fromisoformat(last.replace("Z", "+00:00").replace("+08:00", ""))
                            elapsed = (now - lt).total_seconds() / 60
                            if elapsed > timeout_min:
                                stale.append((name, elapsed, info))
                        except Exception:
                            pass
        except Exception:
            pass

    if not stale:
        print("无超时实例，无需自愈")
        return []

    flagged = []
    for name, elapsed, info in stale:
        if name == "外接大脑":
            continue  # 不重启自己
        ok = write_flag(name, f"心跳超时{elapsed:.0f}分钟", "外接大脑自动自愈")
        if ok:
            flagged.append(name)
        time.sleep(0.3)  # 避免GitHub API限流

    print(f"\n自愈完成: 对 {len(flagged)}/{len(stale)} 个超时实例下发了重启flag")
    return flagged


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: flag <实例名> [原因] | check <实例名> | clear <实例名> | list | auto-heal [超时分钟]")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "flag" and len(sys.argv) >= 3:
        write_flag(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "心跳超时")
    elif cmd == "check" and len(sys.argv) >= 3:
        flag = check_flag(sys.argv[2])
        if flag:
            print(f"🟡 检测到重启flag: {flag.get('reason')}（触发者:{flag.get('triggered_by')}）")
        else:
            print("🟢 无重启flag")
    elif cmd == "clear" and len(sys.argv) >= 3:
        clear_flag(sys.argv[2])
    elif cmd == "list":
        list_flags()
    elif cmd == "auto-heal":
        timeout = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        auto_heal_stale_instances(timeout)
    else:
        print("参数错误")
