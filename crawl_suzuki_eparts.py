# -*- coding: utf-8 -*-
"""铃木原厂eParts爬虫 - API方式，零token，断点续爬"""
import sys, io, os, time, random, json, re, sqlite3, requests
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')

DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(DIR, 'suzuki_eparts.db')
H = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
     'Accept': 'application/json', 'Referer': 'https://www.suzuki.co.id/eparts/'}
API = 'https://api-web-corp.suzuki.co.id/api/v1'
TYPES = ['body', 'electrical', 'engine', 'suspension', 'transmission']
DELAY = 0.3

def db():
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS vehicle(
        id INTEGER PRIMARY KEY, slug TEXT, name TEXT, parent_id INTEGER, vin TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS figure(
        id INTEGER PRIMARY KEY, vehicle_id INTEGER, type_slug TEXT,
        name TEXT, file_url TEXT, done INTEGER DEFAULT 0)""")
    con.execute("""CREATE TABLE IF NOT EXISTS part(
        id INTEGER PRIMARY KEY, figure_id INTEGER, part_no TEXT, name TEXT,
        qty INTEGER, price REAL, tag_no TEXT, remarks TEXT)""")
    con.execute("CREATE INDEX IF NOT EXISTS idx_part_no ON part(part_no)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_fig_veh ON figure(vehicle_id)")
    return con

def api_get(path, params=None):
    for i in range(3):
        try:
            r = requests.get(API + path, params=params, headers=H, timeout=20)
            if r.status_code == 200:
                d = r.json()
                if d.get('status') == 'success':
                    return d.get('data')
            return None
        except Exception:
            time.sleep(2)
    return None

def get_vehicle_id(slug):
    """从机型页HTML提取vehicle_id"""
    try:
        r = requests.get(f'https://www.suzuki.co.id/eparts/{slug}/engine', headers=H, timeout=20)
        m = re.search(r'var\s+vehicle_id\s*=\s*(\d+)', r.text)
        if m:
            return int(m.group(1)), slug.replace('-', ' ')
    except Exception:
        pass
    return None, ''

def main():
    con = db()
    # 1. 机型列表
    vehs = api_get('/eparts/vehicles/ajax/vehicles',
                   {'type': 'marine', 'return': 'slug', 'vehicle': ''})
    slugs = []
    if vehs and vehs.get('options'):
        for opt in vehs['options']:
            slug = opt.get('value', '')
            name = opt.get('label', '')
            if slug and slug not in ('', 'DF-Series', 'DT-Series'):
                slugs.append((slug, name))
        print(f"机型: {len(slugs)}个")
    
    # 获取每个机型的numeric id
    vehicles = []
    for slug, name in slugs:
        existing = con.execute("SELECT id FROM vehicle WHERE slug=?", (slug,)).fetchone()
        if existing and existing[0]:
            vehicles.append((existing[0], slug, name))
            continue
        vid, real_name = get_vehicle_id(slug)
        if vid:
            vname = real_name or name
            con.execute("INSERT OR REPLACE INTO vehicle(id,slug,name) VALUES(?,?,?)",
                       (vid, slug, vname))
            con.commit()
            vehicles.append((vid, slug, vname))
            print(f"  {slug} -> id={vid}")
        else:
            print(f"  {slug} -> 无法获取id，跳过")
        time.sleep(0.2)
    print(f"有效机型: {len(vehicles)}")

    # 2. 每个机型每个类型抓分区（API一次返回全部分区，不支持翻页）
    for vid, slug, vname in vehicles:
        for tslug in TYPES:
            existing = con.execute("SELECT COUNT(*) FROM figure WHERE vehicle_id=? AND type_slug=?",
                                  (vid, tslug)).fetchone()[0]
            if existing > 0:
                continue
            data = api_get('/eparts/figures/ajax',
                          {'type_slug': tslug, 'vehicle_id': vid,
                           'keyword': '', 'page': 1, 'sort': ''})
            if data and data.get('figures'):
                for fig in data['figures']:
                    con.execute("INSERT OR IGNORE INTO figure(id,vehicle_id,type_slug,name,file_url) VALUES(?,?,?,?,?)",
                               (fig['id'], vid, tslug, fig.get('name',''), fig.get('file_url','')))
                con.commit()
                print(f"  {vname}/{tslug}: {len(data['figures'])}分区")
            time.sleep(DELAY * random.uniform(0.8, 1.2))
        print(f"  {vname}: 分区收集完成")
    
    # 3. 抓零件
    todo = con.execute("SELECT id, name FROM figure WHERE done=0").fetchall()
    print(f"\n待抓零件分区: {len(todo)}")
    done = 0
    for fid, fname in todo:
        parts = api_get('/eparts/parts/figure/detail', {'figure_id': fid})
        if parts:
            for p in parts:
                con.execute("INSERT OR IGNORE INTO part(id,figure_id,part_no,name,qty,price,tag_no,remarks) VALUES(?,?,?,?,?,?,?,?)",
                           (p.get('id'), fid, p.get('part_no',''), (p.get('name') or '').strip(),
                            p.get('qty',0), p.get('price',0), p.get('tag_no',''), (p.get('remarks') or '').strip()))
        con.execute("UPDATE figure SET done=1 WHERE id=?", (fid,))
        done += 1
        if done % 50 == 0:
            con.commit()
            total_parts = con.execute("SELECT COUNT(*) FROM part").fetchone()[0]
            print(f"  零件进度: {done}/{len(todo)} (共{total_parts}零件)")
        time.sleep(DELAY * random.uniform(0.8, 1.2))
    con.commit()
    
    total_fig = con.execute("SELECT COUNT(*) FROM figure").fetchone()[0]
    total_part = con.execute("SELECT COUNT(*) FROM part").fetchone()[0]
    distinct = con.execute("SELECT COUNT(DISTINCT part_no) FROM part").fetchone()[0]
    print(f"\n完成! 分区{total_fig}, 零件{total_part}, 不同零件号{distinct}")
    con.close()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"FAIL {type(e).__name__}: {e}")
