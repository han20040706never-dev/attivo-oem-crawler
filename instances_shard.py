# -*- coding: utf-8 -*-
"""
instances_shard.py — 心跳分片模块
解决多实例同时写 instances.json 导致的并发覆盖问题。

设计：
- 每个实例只写自己的分片文件 heartbeats/<实例名>.json 到 GitHub
- 读取时聚合所有分片，合并成全局视图
- 兼容旧 instances.json（过渡期同时读）

用法：
  python instances_shard.py beat <实例名> <标签>    # 写入本实例心跳
  python instances_shard.py status                    # 聚合所有实例状态
  python instances_shard.py stale <分钟>              # 列出超时实例
"""
import sys, io, os, json, datetime, requests, base64, re

sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import config
except ImportError:
    config = None

PROJECT = os.path.dirname(os.path.abspath(__file__))
REPO = 'han20040706never-dev/attivo-oem-crawler'
SHARD_DIR = 'heartbeats'
LEGACY_FILE = 'instances.json'
HEARTBEAT_TIMEOUT_MIN = 30


def _gh_headers():
    token = getattr(config, 'GITHUB_PAT', '') if config else ''
    return {'Authorization': f'token {token}', 'Accept': 'application/vnd.github.v3+json'}


def _sanitize(name):
    """实例名转安全文件名：空格转下划线，去除特殊字符"""
    return re.sub(r'[^\w\u4e00-\u9fff]+', '_', name).strip('_')


def _shard_path(instance_name):
    return f"{SHARD_DIR}/{_sanitize(instance_name)}.json"


def write_beat(instance_name, tags="", completed=0, failed=0, extra=None):
    """写入本实例心跳分片到 GitHub（只写自己的分片，不影响其他实例）"""
    now = datetime.datetime.now().isoformat()
    data = {
        "instance": instance_name,
        "tags": tags,
        "last_seen": now,
        "completed": completed,
        "failed": failed,
        "version": "shard-v1",
    }
    if extra:
        data.update(extra)

    path = _shard_path(instance_name)
    content = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
    url = f'https://api.github.com/repos/{REPO}/contents/{path}'
    H = _gh_headers()

    try:
        r = requests.get(url, headers=H, timeout=15)
        sha = r.json().get('sha') if r.status_code == 200 else None
        payload = {
            'message': f'heartbeat: {instance_name}',
            'content': base64.b64encode(content).decode(),
        }
        if sha:
            payload['sha'] = sha
        r2 = requests.put(url, headers=H, json=payload, timeout=15)
        if r2.status_code in (200, 201):
            # 同时写本地缓存
            local = os.path.join(PROJECT, SHARD_DIR)
            os.makedirs(local, exist_ok=True)
            with open(os.path.join(local, f"{_sanitize(instance_name)}.json"), 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True, now
        return False, f"HTTP {r2.status_code}: {r2.text[:100]}"
    except Exception as e:
        return False, str(e)


def list_shards():
    """列出 GitHub 上所有心跳分片文件"""
    url = f'https://api.github.com/repos/{REPO}/contents/{SHARD_DIR}'
    H = _gh_headers()
    try:
        r = requests.get(url, headers=H, timeout=15)
        if r.status_code == 200:
            return [f['name'] for f in r.json() if f['name'].endswith('.json')]
        return []
    except Exception:
        return []


def read_shard(instance_name):
    """读取单个实例的心跳分片"""
    path = _shard_path(instance_name)
    url = f'https://api.github.com/repos/{REPO}/contents/{path}'
    H = _gh_headers()
    try:
        r = requests.get(url, headers=H, timeout=10)
        if r.status_code == 200:
            return json.loads(base64.b64decode(r.json()['content']).decode('utf-8'))
    except Exception:
        pass
    return None


def aggregate():
    """聚合所有分片 + 旧 instances.json，返回全局实例状态字典"""
    instances = {}
    now = datetime.datetime.now()

    # 1. 读所有分片
    shards = list_shards()
    for fname in shards:
        inst_name = fname.replace('.json', '')
        data = read_shard(inst_name)
        if data and 'instance' in data:
            name = data['instance']
            instances[name] = {
                "tags": data.get("tags", ""),
                "last_seen": data.get("last_seen", ""),
                "completed": data.get("completed", 0),
                "failed": data.get("failed", 0),
                "source": "shard",
            }

    # 2. 兼容旧 instances.json（分片数据优先，旧数据只补充缺失的实例）
    try:
        r = requests.get(f'https://raw.githubusercontent.com/{REPO}/main/{LEGACY_FILE}', timeout=10)
        if r.status_code == 200:
            legacy = r.json()
            for name, info in legacy.get("instances", {}).items():
                if name not in instances:
                    instances[name] = {
                        "tags": info.get("tags", ""),
                        "last_seen": info.get("last_seen", ""),
                        "completed": info.get("completed", 0),
                        "failed": info.get("failed", 0),
                        "source": "legacy",
                    }
    except Exception:
        pass

    # 3. 计算超时状态
    for name, info in instances.items():
        last = info.get("last_seen", "")
        if last:
            try:
                lt = datetime.datetime.fromisoformat(last.replace("Z", "+00:00").replace("+08:00", ""))
                elapsed = (now - lt).total_seconds() / 60
                info["elapsed_min"] = round(elapsed, 1)
                info["status"] = "online" if elapsed <= HEARTBEAT_TIMEOUT_MIN else "stale"
            except Exception:
                info["elapsed_min"] = None
                info["status"] = "unknown"
        else:
            info["elapsed_min"] = None
            info["status"] = "no_heartbeat"

    return instances


def get_stale(timeout_min=HEARTBEAT_TIMEOUT_MIN):
    """返回超时实例列表 [(name, elapsed_min, info), ...]"""
    instances = aggregate()
    stale = []
    for name, info in instances.items():
        if info.get("status") == "stale" and info.get("elapsed_min", 0) > timeout_min:
            stale.append((name, info["elapsed_min"], info))
    return stale


def status_report():
    """打印状态报告"""
    instances = aggregate()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"=== 实例心跳状态（分片聚合） {now} ===")
    print(f"共 {len(instances)} 个实例\n")

    online = [n for n, i in instances.items() if i.get("status") == "online"]
    stale = [(n, i) for n, i in instances.items() if i.get("status") == "stale"]

    if online:
        print(f"🟢 在线 ({len(online)}):")
        for n in online:
            i = instances[n]
            print(f"  {n} | {i.get('elapsed_min', '?')}分钟前 | 完成{i.get('completed', 0)} 失败{i.get('failed', 0)} | {i.get('source', '')}")
    if stale:
        print(f"\n🔴 超时 ({len(stale)}):")
        for n, i in stale:
            print(f"  {n} | {i.get('elapsed_min', '?')}分钟无心跳 | 完成{i.get('completed', 0)} 失败{i.get('failed', 0)} | {i.get('source', '')}")

    no_hb = [n for n, i in instances.items() if i.get("status") in ("no_heartbeat", "unknown")]
    if no_hb:
        print(f"\n⚪ 无心跳记录 ({len(no_hb)}): {', '.join(no_hb)}")

    return instances


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: beat <实例名> [标签] | status | stale [分钟]")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "beat" and len(sys.argv) >= 3:
        ok, result = write_beat(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
        print(f"{'OK' if ok else 'FAIL'}: {result}")
    elif cmd == "status":
        status_report()
    elif cmd == "stale":
        timeout = int(sys.argv[2]) if len(sys.argv) > 2 else HEARTBEAT_TIMEOUT_MIN
        stale = get_stale(timeout)
        print(f"=== 超时{timeout}分钟以上的实例 ({len(stale)}) ===")
        for name, elapsed, info in stale:
            print(f"  {name}: {elapsed:.0f}分钟 | 标签={info.get('tags', '')}")
    else:
        print("参数错误")
