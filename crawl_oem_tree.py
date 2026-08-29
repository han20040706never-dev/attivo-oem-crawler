# -*- coding: utf-8 -*-
"""
crawl_oem_tree.py — megazip 船外机机型树爬虫（Yamaha/Suzuki）
层级: 品牌->马力组->机型族->具体版本(带年份/序列号)->爆炸图分区->零件
SQLite 断点续爬，礼貌延时，代理失败回退直连。只爬目标分区(默认齿轮箱/曲轴)。

用法:
  python crawl_oem_tree.py families --brand yamaha
  python crawl_oem_tree.py families --brand suzuki
  python crawl_oem_tree.py units --brand yamaha --hp 115
  python crawl_oem_tree.py sections --brand yamaha --hp 115
  python crawl_oem_tree.py parts --brand yamaha --hp 115
  python crawl_oem_tree.py all --brand yamaha --hp 115      # 一条跑完该马力
  python crawl_oem_tree.py stats
"""
import sys, io, os, re, time, sqlite3, argparse, html as ihtml
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
import requests

ROOT = "https://www.megazip.net"
OB = "/zapchasti-dlya-lodochnyh-motorov"
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "oemkb.db")
PX = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}
DELAY = 0.7
# 业务核心分区关键词（齿轮组/驱动轴/桨轴在下箱，曲轴单独）
TARGET_SEC = ("lower-casing-drive", "crankshaft-piston")
PN_RE = re.compile(r'\b[0-9A-Z]{3}-[0-9A-Z]{5}-[0-9A-Z]{2}(?:-[0-9A-Z]{2})?\b')

S = requests.Session()
S.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})


def db():
    con = sqlite3.connect(DB)
    con.executescript("""
    CREATE TABLE IF NOT EXISTS family(brand TEXT, hp TEXT, name TEXT, url TEXT PRIMARY KEY);
    CREATE TABLE IF NOT EXISTS unit(family_url TEXT, version TEXT, url TEXT PRIMARY KEY,
        year TEXT, serial TEXT, sec_done INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS section(unit_url TEXT, name TEXT, url TEXT PRIMARY KEY,
        target INTEGER, part_done INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS part(sec_url TEXT, item TEXT, part_no TEXT, desc TEXT, qty TEXT);
    CREATE INDEX IF NOT EXISTS idx_part_pn ON part(part_no);
    CREATE TABLE IF NOT EXISTS fetched(url TEXT PRIMARY KEY, ts TEXT);
    """)
    return con


def get(url, tries=3):
    for k in range(tries):
        try:
            r = S.get(url, timeout=30, proxies=PX)
            if r.status_code == 200:
                return r.text
            last = f"HTTP{r.status_code}"
        except Exception as e:
            last = str(e)[:50]
            try:
                r = S.get(url, timeout=30)
                if r.status_code == 200:
                    return r.text
            except Exception:
                pass
        time.sleep(1.2 * (k + 1))
    print(f"  [FAIL] {url} {last}")
    return None


def links_on(h, contain=None):
    out = []
    for href, txt in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', h, re.S):
        t = re.sub(r"<[^>]+>", "", txt)
        t = ihtml.unescape(re.sub(r"\s+", " ", t)).strip()
        if href.startswith("/"):
            href = ROOT + href
        if contain and contain not in href:
            continue
        out.append((href, t))
    return out


def stage_families(con, brand):
    # 品牌页直接给两级机型族链接: /brand/<马力>-id/<族>-id
    h = get(f"{ROOT}{OB}/{brand}")
    if not h:
        return
    pat = re.compile(rf'/{re.escape(OB.split("/")[-1])}/{brand}/([A-Za-z0-9]+)-\d+/([A-Za-z0-9-]+)-\d+(?:[?#]|$)')
    n = 0
    for href, t in links_on(h, f"/{OB.split('/')[-1]}/{brand}/"):
        m = pat.search(href)
        if not m:
            continue
        hp = m.group(1)
        con.execute("INSERT OR REPLACE INTO family VALUES(?,?,?,?)",
                    (brand, hp, t, href)); n += 1
    con.commit()
    print(f"{brand}: 机型族入库 {n}")


def stage_units(con, brand, hp=None):
    q = "SELECT url,name FROM family WHERE brand=?" + (" AND hp=?" if hp else "")
    args = (brand, hp) if hp else (brand,)
    fams = con.execute(q, args).fetchall()
    n = 0
    for furl, fname in fams:
        h = get(furl); time.sleep(DELAY)
        if not h:
            continue
        for href, t in links_on(h, furl):
            if href.rstrip('/') == furl.rstrip('/'):
                continue
            if href.count('/') > furl.count('/') and re.search(r'-\d+$', href):
                con.execute("INSERT OR IGNORE INTO unit(family_url,version,url) VALUES(?,?,?)",
                            (furl, t, href)); n += 1
        con.commit()
    print(f"{brand}{(' '+hp) if hp else ''}: 版本入库 {n}")


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


def stage_sections(con, brand, hp=None, only_target=True):
    q = """SELECT u.url FROM unit u JOIN family f ON u.family_url=f.url
           WHERE f.brand=? AND u.sec_done=0""" + (" AND f.hp=?" if hp else "")
    args = (brand, hp) if hp else (brand,)
    units = con.execute(q, args).fetchall()
    print(f"待抓版本 {len(units)}")
    for i, (uurl,) in enumerate(units):
        h = get(uurl); time.sleep(DELAY)
        if not h:
            continue
        year, serial = parse_unit_head(h)
        for href, t in links_on(h, uurl):
            if href.rstrip('/') == uurl.rstrip('/') or href.count('/') <= uurl.count('/'):
                continue
            tgt = 1 if any(k in href for k in TARGET_SEC) else 0
            if only_target and not tgt:
                continue
            con.execute("INSERT OR REPLACE INTO section VALUES(?,?,?,?,0)",
                        (uurl, t, href, tgt))
        con.execute("UPDATE unit SET year=?,serial=?,sec_done=1 WHERE url=?",
                    (year, serial, uurl))
        con.commit()
        if (i + 1) % 20 == 0:
            print(f"  sections {i+1}/{len(units)}")


def parse_part_rows(h):
    rows = []
    for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', h, re.S):
        cells = [ihtml.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c))).strip()
                 for c in re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', tr, re.S)]
        joined = " ".join(cells)
        m = PN_RE.search(joined)
        if not m:
            continue
        pn = m.group(0)
        nums = re.findall(r'^\d+[A-Z]?$', cells[0]) if cells else []
        item = cells[0] if cells and re.match(r'^\d', cells[0]) else ""
        # 描述：去掉编号/价格/数量后的英文部分
        desc = joined.replace(pn, " ")
        desc = re.sub(r'US\s*\$[\d,\.]+', ' ', desc)
        desc = re.sub(r'\bShow\b', ' ', desc)
        desc = re.sub(r'\s+from\s*$', ' ', desc, flags=re.I)
        desc = re.sub(r'\s+', ' ', desc).strip(' 0123456789')
        rows.append((item, pn, desc[:120], ""))
    return rows


def stage_parts(con, brand, hp=None):
    q = """SELECT s.url FROM section s JOIN unit u ON s.unit_url=u.url
           JOIN family f ON u.family_url=f.url
           WHERE f.brand=? AND s.target=1 AND s.part_done=0""" + (" AND f.hp=?" if hp else "")
    args = (brand, hp) if hp else (brand,)
    secs = con.execute(q, args).fetchall()
    print(f"待抓零件分区 {len(secs)}")
    for i, (surl,) in enumerate(secs):
        h = get(surl); time.sleep(DELAY)
        if not h:
            continue
        rows = parse_part_rows(h)
        con.execute("DELETE FROM part WHERE sec_url=?", (surl,))
        con.executemany("INSERT INTO part VALUES(?,?,?,?,?)",
                        [(surl, *r) for r in rows])
        con.execute("UPDATE section SET part_done=1 WHERE url=?", (surl,))
        con.commit()
        if (i + 1) % 10 == 0:
            print(f"  parts {i+1}/{len(secs)}")


def stats(con):
    for t in ("family", "unit", "section", "part"):
        n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"{t}: {n}")
    print("目标分区已抓零件:",
          con.execute("SELECT COUNT(*) FROM section WHERE target=1 AND part_done=1").fetchone()[0])
    print("不同零件编号:", con.execute("SELECT COUNT(DISTINCT part_no) FROM part").fetchone()[0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["families", "units", "sections", "parts", "all", "stats"])
    ap.add_argument("--brand", default="yamaha")
    ap.add_argument("--hp", default=None)
    ap.add_argument("--all-sec", action="store_true", help="不只目标分区")
    p = ap.parse_args()
    con = db()
    if p.stage == "families":
        stage_families(con, p.brand)
    elif p.stage == "units":
        stage_units(con, p.brand, p.hp)
    elif p.stage == "sections":
        stage_sections(con, p.brand, p.hp, only_target=not p.all_sec)
    elif p.stage == "parts":
        stage_parts(con, p.brand, p.hp)
    elif p.stage == "all":
        stage_families(con, p.brand)
        stage_units(con, p.brand, p.hp)
        stage_sections(con, p.brand, p.hp, only_target=not p.all_sec)
        stage_parts(con, p.brand, p.hp)
    stats(con)


if __name__ == "__main__":
    main()
