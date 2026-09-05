# -*- coding: utf-8 -*-
"""
crawl_boatsnet.py — boats.net 船外机零件爬虫（playwright绕过Cloudflare）
结构: /catalog/{brand}/outboard → 年份 → 马力/机型 → 分区 → 零件
断点续爬: 每个URL只爬一次，存boatsnet.db
"""
import asyncio, sys, io, os, re, json, time, random, sqlite3
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
from playwright.async_api import async_playwright

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "boatsnet.db")
BRANDS = ["yamaha", "suzuki"]
BASE = "https://www.boats.net"
DELAY = (1.0, 2.5)

def db():
    conn = sqlite3.connect(DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS pages(
        url TEXT PRIMARY KEY, status TEXT DEFAULT 'pending',
        brand TEXT, year TEXT, model TEXT, section TEXT,
        data TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS parts(
        id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT,
        part_no TEXT, name TEXT, price TEXT, qty TEXT,
        brand TEXT, year TEXT, model TEXT, section TEXT,
        UNIQUE(url, part_no))""")
    conn.commit()
    return conn

def is_done(conn, url):
    r = conn.execute("SELECT status FROM pages WHERE url=?", (url,)).fetchone()
    return r is not None and r[0] == 'done'

def mark(conn, url, status='done', **kw):
    cols = ['url','status'] + list(kw.keys())
    vals = [url, status] + list(kw.values())
    placeholders = ','.join(['?']*len(cols))
    update = ','.join(f"{k}=excluded.{k}" for k in cols if k != 'url')
    conn.execute(f"INSERT INTO pages({','.join(cols)}) VALUES({placeholders}) "
                 f"ON CONFLICT(url) DO UPDATE SET {update}", vals)
    conn.commit()

def save_parts(conn, url, parts, brand, year, model, section):
    for p in parts:
        conn.execute("""INSERT OR IGNORE INTO parts(url,part_no,name,price,qty,brand,year,model,section)
                        VALUES(?,?,?,?,?,?,?,?,?)""",
                     (url, p.get('part_no',''), p.get('name',''), p.get('price',''),
                      p.get('qty',''), brand, year, model, section))
    conn.commit()

def extract_path_info(url):
    """从URL提取brand/year/model/section"""
    m = re.search(r'/catalog/(\w+)/outboard(?:/(\d{4}))?(?:/([^/]+))?(?:/([^/]+))?', url)
    if m:
        return m.group(1) or '', m.group(2) or '', m.group(3) or '', m.group(4) or ''
    return '', '', '', ''

async def crawl():
    conn = db()
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}, locale="en-US")
        page = await context.new_page()
        await page.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")

        # 先访问首页拿cookie
        print("访问首页获取Cloudflare cookie...")
        try:
            await page.goto(BASE, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(4)
            print("OK")
        except Exception as e:
            print(f"首页访问失败: {e}")

        # BFS队列
        queue = []
        for brand in BRANDS:
            start = f"{BASE}/catalog/{brand}/outboard"
            if not is_done(conn, start):
                queue.append(start)

        visited = set()
        count = 0
        while queue:
            url = queue.pop(0)
            if url in visited or is_done(conn, url):
                continue
            visited.add(url)
            brand, year, model, section = extract_path_info(url)

            for attempt in range(3):
                try:
                    await page.goto(url, wait_until="commit", timeout=90000)
                    await asyncio.sleep(random.uniform(*DELAY))
                    break
                except Exception as e:
                    if attempt < 2:
                        await asyncio.sleep(3 * (attempt+1))
                    else:
                        print(f"FAIL {url}: {e}")
                        mark(conn, url, 'failed', brand=brand, year=year, model=model, section=section)
                        continue

            # 提取子链接
            try:
                links = await page.evaluate("""() => {
                    const out = [];
                    document.querySelectorAll('a[href]').forEach(a => {
                        let h = a.href;
                        if (h.startsWith('https://www.boats.net/catalog/') && h.includes('/outboard'))
                            out.push(h.split('#')[0]);
                    });
                    return [...new Set(out)];
                }""")
            except:
                links = []

            # 提取零件（如果页面有零件表格）
            parts = []
            try:
                parts = await page.evaluate("""() => {
                    const out = [];
                    // 尝试多种选择器
                    document.querySelectorAll('tr, .part-item, [data-part-number], .product-item').forEach(el => {
                        const text = el.innerText || '';
                        const partNo = el.getAttribute('data-part-number') || 
                            el.querySelector('.part-number, .sku, [class*=part-no]')?.textContent?.trim() || '';
                        const name = el.querySelector('.part-name, .name, [class*=part-name]')?.textContent?.trim() || '';
                        const price = el.querySelector('.price, [class*=price]')?.textContent?.trim() || '';
                        const qty = el.querySelector('.qty, [class*=qty]')?.textContent?.trim() || '';
                        // 用正则从文本中提取零件号
                        if (!partNo) {
                            const m = text.match(/\\b[A-Z0-9]{2,5}-[A-Z0-9]{3,6}-[A-Z0-9]{2}(?:-[A-Z0-9]{2})?\\b/);
                            if (m) out.push({part_no: m[0], name: text.substring(0,80).replace(/\\n/g,' '), price: price, qty: qty});
                        } else if (partNo) {
                            out.push({part_no: partNo, name: name || text.substring(0,80), price: price, qty: qty});
                        }
                    });
                    return out;
                }""")
            except:
                pass

            if parts:
                save_parts(conn, url, parts, brand, year, model, section)

            mark(conn, url, 'done', brand=brand, year=year, model=model, section=section,
                 data=json.dumps({"links": len(links), "parts": len(parts)}, ensure_ascii=False))

            # 子链接入队
            for l in links:
                if l not in visited and not is_done(conn, l):
                    queue.append(l)

            count += 1
            if count % 20 == 0:
                total_parts = conn.execute("SELECT COUNT(*) FROM parts").fetchone()[0]
                done_pages = conn.execute("SELECT COUNT(*) FROM pages WHERE status='done'").fetchone()[0]
                print(f"进度: {count}页, 队列{len(queue)}, 已完成{done_pages}, 零件{total_parts} | {url[:80]}")

        total_parts = conn.execute("SELECT COUNT(*) FROM parts").fetchone()[0]
        done_pages = conn.execute("SELECT COUNT(*) FROM pages WHERE status='done'").fetchone()[0]
        print(f"\n完成! 页面{done_pages}, 零件{total_parts}")
        await browser.close()
        conn.close()

if __name__ == "__main__":
    try:
        asyncio.run(crawl())
    except Exception as e:
        print(f"FAIL {type(e).__name__}: {e}")
