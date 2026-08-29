# -*- coding: utf-8 -*-
"""
crawl_full.py — 无人值守总控：Yamaha+Suzuki 全马力，断点续爬。
随时可 Ctrl+C / 关机，重跑本脚本自动从断点继续（已抓的不重复）。
云电脑: 装好 python + requests 后  python crawl_full.py  即可，megazip 直连无需代理。
"""
import sys, io, time, traceback
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
import crawl_oem_tree as C

BRANDS = ["yamaha", "suzuki"]

def main():
    con = C.db()
    for brand in BRANDS:
        for stage, fn in [
            ("families", lambda: C.stage_families(con, brand)),
            ("units",    lambda: C.stage_units(con, brand, None)),
            ("sections", lambda: C.stage_sections(con, brand, None, only_target=True)),
            ("parts",    lambda: C.stage_parts(con, brand, None)),
        ]:
            for attempt in range(3):
                try:
                    print(f"\n===== {brand} / {stage} (try{attempt+1}) =====", flush=True)
                    fn(); con.commit()
                    break
                except Exception:
                    traceback.print_exc()
                    time.sleep(5)
    print("\n===== 全部完成 ====="); C.stats(con)

if __name__ == "__main__":
    main()
