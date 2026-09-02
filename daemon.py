# -*- coding: utf-8 -*-
"""
协作系统自动巡检daemon
后台定时运行：check_done（回收已完成/已失败任务）+ sync（增量同步经验）
用法：python daemon.py [--interval 300] [--once]
"""
import sys, io, os, time, subprocess, json, datetime, argparse
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
PROJECT = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
LOG_FILE = os.path.join(PROJECT, "_daemon.log")

def log(msg):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + "\n")

def run(cmd_args, timeout=60):
    try:
        r = subprocess.run([PY] + cmd_args, capture_output=True, text=True,
                          timeout=timeout, encoding='utf-8', cwd=PROJECT)
        return r.stdout.strip()
    except Exception as e:
        return f"ERROR: {e}"

def cycle():
    log("=== 巡检开始 ===")
    # 1. check_done（回收任务+自动同步经验）
    out = run(["check_done.py"], timeout=60)
    log(f"check_done: {out[:200]}")
    # 2. watchdog（重置超时任务）
    out2 = run(["sharedtask.py", "watchdog", "--auto"], timeout=30)
    log(f"watchdog: {out2[:100]}")
    log("=== 巡检结束 ===\n")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--interval", type=int, default=300, help="巡检间隔秒数，默认300")
    p.add_argument("--once", action="store_true", help="只跑一次")
    a = p.parse_args()
    
    if a.once:
        cycle()
        return
    
    log(f"daemon启动，间隔{a.interval}秒")
    while True:
        try:
            cycle()
        except Exception as e:
            log(f"巡检异常: {e}")
        time.sleep(a.interval)

if __name__ == "__main__":
    main()
