# -*- coding: utf-8 -*-
"""common.py — 公共函数模块，消除重复代码"""
import sys, io, os, json, sqlite3
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')

PROJECT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(PROJECT, "oemkb.db")

def db():
    """打开OEM知识库SQLite连接，返回(conn, cur)"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn, conn.cursor()

def load_json(path, default=None):
    """安全加载JSON文件，不存在返回default"""
    if default is None:
        default = {}
    try:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        print(f"load_json失败 {path}: {e}")
    return default

def save_json(path, data):
    """安全保存JSON文件"""
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"save_json失败 {path}: {e}")
        return False

def safe_request(url, headers=None, timeout=15, retries=3):
    """带重试的安全HTTP请求"""
    import requests
    if headers is None:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    for i in range(retries):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            if r.status_code == 200:
                return r
            print(f"  请求{url}状态{r.status_code}，重试{i+1}/{retries}")
        except Exception as e:
            print(f"  请求{url}异常: {e}，重试{i+1}/{retries}")
    return None
