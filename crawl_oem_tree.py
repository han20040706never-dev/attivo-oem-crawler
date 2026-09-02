# -*- coding: utf-8 -*-
"""
crawl_oem_tree.py — megazip 船外机机型树爬虫（Yamaha/Suzuki）
v2.0: 继承CrawlerBase，消除重复HTTP/DB/限速代码
层级: 品牌->马力组->机型族->具体版本(带年份/序列号)->爆炸图分区->零件
"""
import sys, io, os, re, argparse
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
from crawler_base import CrawlerBase

ROOT = "https://www.megazip.net"
OB = "/zapchasti-dlya-lodochnyh-motorov"
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "oemkb.db")
TARGET_SEC = ("lower-casing-drive", "crankshaft-piston")
PN_RE = re.compile(r'\b[0-9A-Z]{3}-[0-9A-Z]{5}-[0-9A-Z]{2}(?:-[0-9A-Z]{2})?\b')

SCHEMA = """
CREATE TABLE IF NOT EXISTS family(brand TEXT, hp TEXT, name TEXT, url TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS unit(family_url TEXT, version TEXT, url TEXT PRIMARY KEY,
    year TEXT, serial TEXT, sec_done INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS section(unit_url TEXT, name TEXT, url TEXT PRIMARY KEY,
    target INTEGER, part_done INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS part(sec_url TEXT, item TEXT, part_no TEXT, desc TEXT, qty TEXT);
CREATE INDEX IF NOT EXISTS idx_part_pn ON part(part_no);
CREATE TABLE IF NOT EXISTS fetched(url TEXT PRIMARY KEY, ts TEXT);
"""


class OEMTreeCrawler(CrawlerBase):
    def __init__(self, db_path=None, delay=0.7):
        super().__init__(db_path=db_path or DB, delay=delay)
        self.init_db(SCHEMA)

    def stage_families(self, brand):
        h = self.get(f"{ROOT}{OB}/{brand}")
        if not h:
            return
        pat = re.compile(rf'/{re.escape(OB.split("/")[-1])}/{brand}/([A-Za-z0-9]+)-\d+/([A-Za-z0-9-]+)-\d+(?:[?#]|$)')
        rows = []
        for href, t in self.links_on(h, ROOT, f"/{OB.split('/')[-1]}/{brand}/"):
            m = pat.search(href)
            if not m:
                continue
            hp = m.group(1)
            rows.append((brand, hp, t, href))
        self.insert_many("INSERT OR REPLACE INTO family VALUES(?,?,?,?)", rows)
        print(f"{brand}: 机型族入库 {len(rows)}")

    def stage_units(self, brand, hp=None):
        q = "SELECT url,name FROM family WHERE brand=?" + (" AND hp=?" if hp else "")
        args = (brand, hp) if hp else (brand,)
        fams = self.con.execute(q, args).fetchall()
        rows = []
        for furl, fname in fams:
            h = self.get(furl); self.sleep()
            if not h:
                continue
            for href, t in self.links_on(h, ROOT, furl):
                if href.rstrip('/') == furl.rstrip('/'):
                    continue
                if href.count('/') > furl.count('/') and re.search(r'-\d+$', href):
                    rows.append((furl, t, href))
        self.insert_many("INSERT OR IGNORE INTO unit(family_url,version,url) VALUES(?,?,?)", rows)
        print(f"{brand}{(' '+hp) if hp else ''}: 版本入库 {len(rows)}")

    @staticmethod
    def parse_unit_head(h):
        year = ""
        m = re.search(r'\b(19[89]\d|20[0-3]\d)\b', h)
        if m:
            year = m.group(1)
        serial = ""
        m = re.search(r'\(([A-Z0-9]{3,6})\s*[;,]', h)
        if m:
            serial = m.group(1)
        return year, serial

    def stage_sections(self, brand, hp=None, only_target=True):
        q = """SELECT u.url FROM unit u JOIN family f ON u.family_url=f.url
               WHERE f.brand=? AND u.sec_done=0""" + (" AND f.hp=?" if hp else "")
        args = (brand, hp) if hp else (brand,)
        units = self.con.execute(q, args).fetchall()
        print(f"待抓版本 {len(units)}")
        for i, (uurl,) in enumerate(units):
            h = self.get(uurl); self.sleep()
            if not h:
                continue
            year, serial = self.parse_unit_head(h)
            sec_rows = []
            for href, t in self.links_on(h, ROOT, uurl):
                if href.rstrip('/') == uurl.rstrip('/') or href.count('/') <= uurl.count('/'):
                    continue
                tgt = 1 if any(k in href for k in TARGET_SEC) else 0
                if only_target and not tgt:
                    continue
                sec_rows.append((uurl, t, href, tgt))
            self.insert_many("INSERT OR REPLACE INTO section VALUES(?,?,?,?,0)", sec_rows)
            self.con.execute("UPDATE unit SET year=?,serial=?,sec_done=1 WHERE url=?", (year, serial, uurl))
            self.con.commit()
            self.progress(i, len(units), "sections", interval=20)

    @staticmethod
    def parse_part_rows(h):
        rows = []
        for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', h, re.S):
            cells = [CrawlerBase.clean_text(c) for c in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', tr, re.S)]
            joined = " ".join(cells)
            m = PN_RE.search(joined)
            if not m:
                continue
            pn = m.group(0)
            item = cells[0] if cells and re.match(r'^\d', cells[0]) else ""
            desc = joined.replace(pn, " ")
            desc = re.sub(r'US\s*\$[\d,\.]+', ' ', desc)
            desc = re.sub(r'\bShow\b', ' ', desc)
            desc = re.sub(r'\s+from\s*$', ' ', desc, flags=re.I)
            desc = re.sub(r'\s+', ' ', desc).strip(' 0123456789')
            rows.append((item, pn, desc[:120], ""))
        return rows

    def stage_parts(self, brand, hp=None):
        q = """SELECT s.url FROM section s JOIN unit u ON s.unit_url=u.url
               JOIN family f ON u.family_url=f.url
               WHERE f.brand=? AND s.target=1 AND s.part_done=0""" + (" AND f.hp=?" if hp else "")
        args = (brand, hp) if hp else (brand,)
        secs = self.con.execute(q, args).fetchall()
        print(f"待抓零件分区 {len(secs)}")
        for i, (surl,) in enumerate(secs):
            h = self.get(surl); self.sleep()
            if not h:
                continue
            rows = self.parse_part_rows(h)
            self.con.execute("DELETE FROM part WHERE sec_url=?", (surl,))
            self.insert_many("INSERT INTO part VALUES(?,?,?,?,?)", [(surl, *r) for r in rows])
            self.con.execute("UPDATE section SET part_done=1 WHERE url=?", (surl,))
            self.con.commit()
            self.progress(i, len(secs), "parts", interval=10)

    def stats(self):
        for t in ("family", "unit", "section", "part"):
            n = self.con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"{t}: {n}")
        print("目标分区已抓零件:",
              self.con.execute("SELECT COUNT(*) FROM section WHERE target=1 AND part_done=1").fetchone()[0])
        print("不同零件编号:", self.con.execute("SELECT COUNT(DISTINCT part_no) FROM part").fetchone()[0])
        self.print_stats()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["families", "units", "sections", "parts", "all", "stats"])
    ap.add_argument("--brand", default="yamaha")
    ap.add_argument("--hp", default=None)
    ap.add_argument("--all-sec", action="store_true", help="不只目标分区")
    p = ap.parse_args()
    with OEMTreeCrawler() as c:
        if p.stage == "families":
            c.stage_families(p.brand)
        elif p.stage == "units":
            c.stage_units(p.brand, p.hp)
        elif p.stage == "sections":
            c.stage_sections(p.brand, p.hp, only_target=not p.all_sec)
        elif p.stage == "parts":
            c.stage_parts(p.brand, p.hp)
        elif p.stage == "all":
            c.stage_families(p.brand)
            c.stage_units(p.brand, p.hp)
            c.stage_sections(p.brand, p.hp, only_target=not p.all_sec)
            c.stage_parts(p.brand, p.hp)
        c.stats()


if __name__ == "__main__":
    main()
