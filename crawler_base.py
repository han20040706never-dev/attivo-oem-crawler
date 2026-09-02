# -*- coding: utf-8 -*-
"""
crawler_base.py — 爬虫统一基类 v1.0
消除15个爬虫脚本的重复代码：HTTP请求/重试/代理回退/限速/SQLite/断点续爬/进度打印
用法:
    from crawler_base import CrawlerBase
    class MyCrawler(CrawlerBase):
        def run(self):
            html = self.get("https://example.com")
            self.db.execute("...")
            self.progress(i, total, "sections")
"""
import sys, io, os, re, time, random, sqlite3, html as ihtml
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
import requests

DEFAULT_PROXY = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}
DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


class CrawlerBase:
    """爬虫基类：统一HTTP、DB、限速、断点续爬"""

    def __init__(self, db_path, delay=0.7, proxy=None, user_agent=None):
        self.db_path = db_path
        self.delay = delay
        self.proxy = proxy or DEFAULT_PROXY
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent or DEFAULT_UA})
        self._con = None
        self.stats = {"requests": 0, "success": 0, "fail": 0, "rows": 0}

    # ---- HTTP ----
    def get(self, url, tries=3, timeout=30):
        """带重试的GET，代理失败回退直连"""
        last = ""
        for k in range(tries):
            try:
                r = self.session.get(url, timeout=timeout, proxies=self.proxy)
                self.stats["requests"] += 1
                if r.status_code == 200:
                    self.stats["success"] += 1
                    return r.text
                last = f"HTTP{r.status_code}"
            except Exception as e:
                last = str(e)[:50]
                # 回退直连
                try:
                    r = self.session.get(url, timeout=timeout)
                    self.stats["requests"] += 1
                    if r.status_code == 200:
                        self.stats["success"] += 1
                        return r.text
                except Exception:
                    pass
            self.stats["fail"] += 1
            time.sleep(1.2 * (k + 1))
        print(f"  [FAIL] {url} {last}")
        return None

    def get_json(self, url, tries=3, timeout=30):
        """带重试的JSON GET"""
        text = self.get(url, tries, timeout)
        if text:
            try:
                import json
                return json.loads(text)
            except Exception:
                pass
        return None

    def sleep(self, jitter=0.2):
        """礼貌延时，带随机抖动"""
        time.sleep(self.delay * random.uniform(1 - jitter, 1 + jitter))

    # ---- SQLite ----
    @property
    def con(self):
        """惰性数据库连接"""
        if self._con is None:
            self._con = sqlite3.connect(self.db_path)
        return self._con

    def init_db(self, schema_sql):
        """初始化数据库表"""
        self.con.executescript(schema_sql)
        self.con.commit()

    def insert_many(self, sql, rows):
        """批量插入，自动统计"""
        if rows:
            self.con.executemany(sql, rows)
            self.con.commit()
            self.stats["rows"] += len(rows)

    # ---- HTML解析 ----
    @staticmethod
    def links_on(html, base_url="", contain=None):
        """提取页面链接，返回[(url, text), ...]"""
        out = []
        for href, txt in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, re.S):
            t = re.sub(r"<[^>]+>", "", txt)
            t = ihtml.unescape(re.sub(r"\s+", " ", t)).strip()
            if href.startswith("/") and base_url:
                href = base_url.rstrip("/") + href
            if contain and contain not in href:
                continue
            out.append((href, t))
        return out

    @staticmethod
    def clean_text(html):
        """去除HTML标签，清理空白"""
        t = re.sub(r"<[^>]+>", " ", html)
        return ihtml.unescape(re.sub(r"\s+", " ", t)).strip()

    # ---- 进度 ----
    def progress(self, i, total, label="", interval=10):
        """每interval个打印一次进度"""
        if (i + 1) % interval == 0 or i + 1 == total:
            pct = (i + 1) / total * 100 if total else 0
            print(f"  {label} {i+1}/{total} ({pct:.0f}%)")

    def print_stats(self):
        """打印爬取统计"""
        print(f"统计: 请求{self.stats['requests']} 成功{self.stats['success']} "
              f"失败{self.stats['fail']} 写入{self.stats['rows']}行")

    # ---- 上下文管理 ----
    def __enter__(self):
        return self

    def __exit__(self, *args):
        if self._con:
            self._con.close()
            self._con = None
