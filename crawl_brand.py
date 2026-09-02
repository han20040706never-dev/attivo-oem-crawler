# -*- coding: utf-8 -*-
"""crawl_brand.py — 单品牌无人值守爬虫（可与主进程并行，写独立db文件）
v2.0: 适配crawl_oem_tree.py的OEMTreeCrawler类
用法: python crawl_brand.py --brand suzuki --db oemkb_suzuki.db --delay 1.5 --quiet
"""
import sys, io, os, time, traceback, json, argparse, datetime
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from crawl_oem_tree import OEMTreeCrawler

ap = argparse.ArgumentParser()
ap.add_argument("--brand", required=True, choices=["yamaha", "suzuki"])
ap.add_argument("--db", default=None, help="独立db文件名，默认oemkb_<brand>.db")
ap.add_argument("--delay", type=float, default=1.2, help="请求间隔秒，并行时调大防封")
ap.add_argument("--quiet", action="store_true")
args = ap.parse_args()

QUIET = args.quiet
STATS = f"crawl_stats_{args.brand}.json"
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       args.db or f"oemkb_{args.brand}.db")


def log(m):
    if not QUIET:
        print(m, flush=True)


def write_stats(crawler, stage=""):
    try:
        d = {"updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
             "brand": args.brand, "stage": stage}
        for t in ("family", "unit", "section", "part"):
            d[t] = crawler.con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        d["distinct_parts"] = crawler.con.execute("SELECT COUNT(DISTINCT part_no) FROM part").fetchone()[0]
        json.dump(d, open(STATS, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except Exception:
        pass


with OEMTreeCrawler(db_path=DB_PATH, delay=args.delay) as c:
    for stage, fn in [
        ("families", lambda: c.stage_families(args.brand)),
        ("units",    lambda: c.stage_units(args.brand, None)),
        ("sections", lambda: c.stage_sections(args.brand, None, only_target=True)),
        ("parts",    lambda: c.stage_parts(args.brand, None)),
    ]:
        for attempt in range(3):
            try:
                log(f"===== {args.brand}/{stage} try{attempt+1} =====")
                fn()
                c.con.commit()
                write_stats(c, f"{args.brand}/{stage}")
                break
            except Exception:
                traceback.print_exc()
                time.sleep(5)
    write_stats(c, "done")
    log(f"{args.brand} done")
