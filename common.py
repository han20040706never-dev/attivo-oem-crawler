# -*- coding: utf-8 -*-
"""
common.py — 公共函数模块，消除重复代码
包含：cli, cell, log, run, _norm, _atomic_write, _fetch_github_file, parse_matrix,
      load_json, save_json, db, safe_request
"""
import sys
import io
import os
import json
import sqlite3
import datetime
import subprocess

# 确保stdout支持UTF-8
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
except Exception:
    pass

PROJECT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(PROJECT, 'oemkb.db')
DEFAULT_LOG_FILE = os.path.join(PROJECT, '_daemon.log')
DEFAULT_REPO = 'han20040706never-dev/attivo-oem-crawler'
DEFAULT_RAW_PREFIX = 'https://raw.githubusercontent.com/'
LARK_CLI = 'lark-cli'
LARK_BASE = 'base'


def db():
    """打开OEM知识库SQLite连接，返回(conn, cur)"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA journal_mode=WAL')
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
        print(f'load_json失败 {path}: {e}')
    return default


def save_json(path, data):
    """安全保存JSON文件"""
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f'save_json失败 {path}: {e}')
        return False


def safe_request(url, headers=None, timeout=15, retries=3):
    """带重试的安全HTTP请求，成功返回response对象，失败返回None"""
    import requests
    if headers is None:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    for i in range(retries):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            if r.status_code == 200:
                return r
            print(f'请求{url}状态{r.status_code}，重试{i+1}/{retries}')
        except Exception as e:
            print(f'请求{url}异常: {e}，重试{i+1}/{retries}')
    return None


def cli(args, timeout=120):
    """
    统一封装lark-cli base调用，返回解析后的JSON，失败返回None
    args: 命令行参数列表
    timeout: 超时时间（秒）
    """
    try:
        r = subprocess.run(
            [LARK_CLI, LARK_BASE] + args,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=timeout
        )
        if r.returncode != 0:
            print(f'LARK_ERR: {(r.stderr or r.stdout)[-400:]}')
            return None
        if r.stdout.strip().startswith('{'):
            return json.loads(r.stdout)
        return None
    except subprocess.TimeoutExpired:
        print(f'CLI超时: {" ".join(args)[:100]}')
        return None
    except Exception as e:
        print(f'CLI错误: {e}')
        return None


def cell(v):
    """
    将值转换为字符串表示，处理list和dict类型
    list: 用'/'连接非空元素
    dict: 优先取text字段，其次name字段，最后str()
    None: 返回空字符串
    """
    if isinstance(v, list):
        return '/'.join(cell(x) for x in v if x)
    if isinstance(v, dict):
        return v.get('text') or v.get('name') or str(v)
    return '' if v is None else str(v)


def log(msg, log_file=None):
    """
    日志记录函数，支持控制台输出和文件写入，带1MB轮转
    msg: 日志消息
    log_file: 日志文件路径，默认使用_daemon.log
    """
    if log_file is None:
        log_file = DEFAULT_LOG_FILE

    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] {msg}'

    # 控制台输出
    try:
        print(line, flush=True)
    except Exception:
        pass

    # 文件写入
    try:
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(line + '\n')

        # 日志轮转：超过1MB则截断保留最近500行
        if os.path.getsize(log_file) > 1024 * 1024:
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                with open(log_file, 'w', encoding='utf-8') as f:
                    f.writelines(lines[-500:])
            except Exception:
                pass
    except OSError:
        pass


def run(cmd_args, timeout=120, project=None):
    """
    运行Python子进程命令，返回stdout或错误信息
    cmd_args: 命令行参数列表（不含python解释器）
    timeout: 超时时间（秒）
    project: 工作目录，默认使用PROJECT
    """
    if project is None:
        project = PROJECT

    try:
        r = subprocess.run(
            [sys.executable] + cmd_args,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding='utf-8',
            cwd=project
        )
        if r.returncode != 0:
            err = (r.stderr or r.stdout or '').strip()
            return f'ERROR(exit {r.returncode}): {err[-300:]}'
        return r.stdout.strip()
    except subprocess.TimeoutExpired:
        return f'ERROR(timeout>{timeout}s): {" ".join(cmd_args)[:100]}'
    except Exception as e:
        return f'ERROR: {e}'


def _norm(b):
    """统一换行符为\n"""
    return b.replace(b'\r\n', b'\n').replace(b'\r', b'\n')


def _atomic_write(path, data):
    """原子写入文件，避免写入中断导致文件损坏"""
    tmp = path + f'.tmp{os.getpid()}'
    with open(tmp, 'wb') as f:
        f.write(data)
    os.replace(tmp, path)


def _fetch_github_file(fname, repo=None, raw_prefix=None):
    """
    从GitHub获取文件内容，先raw再api.github.com备用，返回bytes或None
    fname: 文件名或路径
    repo: 仓库名，格式为'owner/repo'，默认使用DEFAULT_REPO
    raw_prefix: raw URL前缀，默认使用DEFAULT_RAW_PREFIX
    """
    import requests
    import base64

    if repo is None:
        repo = DEFAULT_REPO
    if raw_prefix is None:
        raw_prefix = DEFAULT_RAW_PREFIX

    # 通道1: raw.githubusercontent.com（快但常超时）
    try:
        url = f'{raw_prefix}{repo}/main/{fname}'
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return r.content
    except Exception:
        pass

    # 通道2: api.github.com contents API（base64，更稳定）
    try:
        sys.path.insert(0, PROJECT)
        import config
        headers = {
            'Authorization': f'token {config.GITHUB_PAT}',
            'Accept': 'application/vnd.github.v3+json'
        }
        url = f'https://api.github.com/repos/{repo}/contents/{fname}'
        r2 = requests.get(url, headers=headers, timeout=15)
        if r2.status_code == 200:
            return base64.b64decode(r2.json()['content'])
    except Exception:
        pass

    return None


def parse_matrix(data):
    """
    解析record-list --format json返回的矩阵数据
    data: API返回的JSON数据
    返回: [(record_id, {字段名: 值}), ...]列表
    """
    d = (data or {}).get('data', {})
    rows = d.get('data', [])
    cols = d.get('fields', [])
    rids = d.get('record_id_list', [])

    out = []
    for i, row in enumerate(rows):
        f = {cols[j]: row[j] for j in range(min(len(cols), len(row)))}
        out.append((rids[i] if i < len(rids) else '', f))
    return out
