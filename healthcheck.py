# -*- coding: utf-8 -*-
"""
healthcheck.py — 兼容入口，深度自检已合并进 health.py（2026-09-03）
保留此文件以兼容旧调用；所有健康检查统一走 health.py
"""
import sys, os, subprocess
PROJECT = os.path.dirname(os.path.abspath(__file__))
if __name__ == "__main__":
    r = subprocess.run([sys.executable, os.path.join(PROJECT, "health.py")],
                       cwd=PROJECT)
    sys.exit(r.returncode)
