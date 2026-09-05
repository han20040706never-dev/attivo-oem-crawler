# -*- coding: utf-8 -*-
"""
crawl_bg.py — OEM爬虫多profile后台启动器（AI全程只发一条命令，不盯梢）
  python crawl_bg.py start [profile]   profile: full(默认, yamaha+suzuki顺序) / suzuki / yamaha
  python crawl_bg.py status [profile]
  python crawl_bg.py stop [profile]
零token：脚本分离进程自己跑，AI只读*_stats.json，不读日志。
"""
import sys, io, os, json, subprocess, time, ctypes
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

PROFILES = {
    "full":   {"script": "crawl_full.py",  "args": ["--quiet"],
               "pid": "crawl.pid", "log": "crawl.log", "stats": "crawl_stats.json"},
    "suzuki": {"script": "crawl_brand.py", "args": ["--brand","suzuki","--db","oemkb_suzuki.db","--delay","1.5","--quiet"],
               "pid": "crawl_suzuki.pid", "log": "crawl_suzuki.log", "stats": "crawl_stats_suzuki.json"},
    "yamaha": {"script": "crawl_brand.py", "args": ["--brand","yamaha","--db","oemkb.db","--delay","0.8","--quiet"],
               "pid": "crawl_yamaha.pid", "log": "crawl_yamaha.log", "stats": "crawl_stats_yamaha.json"},
}

def alive(pid):
    try:
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if h: ctypes.windll.kernel32.CloseHandle(h); return True
    except Exception: pass
    return False

def prof(name):
    return PROFILES.get(name, PROFILES["full"])

def cmd_start(name):
    p = prof(name)
    pidf = os.path.join(HERE, p["pid"])
    if os.path.exists(pidf):
        old = int(open(pidf).read().strip() or 0)
        if old and alive(old):
            print(f"[{name}] 已在运行 PID={old}，先 stop 再重启"); return
    log = open(os.path.join(HERE, p["log"]), "ab")
    DETACHED = 0x00000008 | 0x00000200
    proc = subprocess.Popen([PY, p["script"]] + p["args"],
                            cwd=HERE, stdout=log, stderr=subprocess.STDOUT,
                            creationflags=DETACHED)
    open(pidf, "w").write(str(proc.pid))
    print(f"[{name}] 已后台启动 PID={proc.pid} 日志={p['log']} 进度={p['stats']}（AI只读stats，不读日志）")

def cmd_status(name):
    p = prof(name)
    pidf = os.path.join(HERE, p["pid"])
    pid = int(open(pidf).read().strip() or 0) if os.path.exists(pidf) else 0
    run = alive(pid) if pid else False
    print(f"[{name}] 运行中: {'是 PID='+str(pid) if run else '否'}")
    sf = os.path.join(HERE, p["stats"])
    if os.path.exists(sf):
        print("进度:", json.dumps(json.load(open(sf, encoding="utf-8")), ensure_ascii=False))
    else:
        print("进度: 尚无stats")
    lf = os.path.join(HERE, p["log"])
    if os.path.exists(lf):
        lines = open(lf, encoding="utf-8", errors="replace").read().splitlines()
        if lines:
            print("日志末尾:")
            for l in lines[-3:]: print("  " + l[-120:])

def cmd_stop(name):
    p = prof(name)
    pidf = os.path.join(HERE, p["pid"])
    pid = int(open(pidf).read().strip() or 0) if os.path.exists(pidf) else 0
    if not pid or not alive(pid):
        print(f"[{name}] 未在运行"); os.path.exists(pidf) and os.remove(pidf); return
    subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    time.sleep(1)
    print(f"[{name}] 已停止 PID={pid}" if not alive(pid) else f"[{name}] 停止失败 PID={pid}")
    os.path.exists(pidf) and os.remove(pidf)

if __name__ == "__main__":
    try:
        cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
        name = sys.argv[2] if len(sys.argv) > 2 else "full"
        {"start": cmd_start, "status": cmd_status, "stop": cmd_stop}.get(cmd, cmd_status)(name)
    except Exception as e:
        print(f"FAIL {type(e).__name__}: {e}")
