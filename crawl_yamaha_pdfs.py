# -*- coding: utf-8 -*-
"""雅马哈原厂PDF零件目录批量下载解析 - 零token"""
import sys, io, os, re, json, time, sqlite3, requests
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')

DIR = os.path.dirname(os.path.abspath(__file__))
PDF_DIR = os.path.join(DIR, 'yamaha_pdfs')
DB = os.path.join(DIR, 'yamaha_pdf_parts.db')
os.makedirs(PDF_DIR, exist_ok=True)
H = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def db():
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS part(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        part_no TEXT, name TEXT, model TEXT, source TEXT)""")
    con.execute("CREATE INDEX IF NOT EXISTS idx_ypart_no ON part(part_no)")
    return con

def download(url, path):
    if os.path.exists(path) and os.path.getsize(path) > 10000:
        return True
    for i in range(3):
        try:
            r = requests.get(url, headers=H, timeout=60)
            if r.status_code == 200 and len(r.content) > 10000:
                open(path, 'wb').write(r.content)
                return True
        except:
            time.sleep(2)
    return False

def extract_parts(pdf_path, model):
    """用pdfplumber提取零件号（雅马哈格式：5位-5位 或 3位-5位-2位-2位）"""
    try:
        import pdfplumber
    except ImportError:
        os.system(f'"{sys.executable}" -m pip install pdfplumber -q')
        import pdfplumber
    parts = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ''
                # 雅马哈零件号格式：61N-W0093-00, 68V-45560-00, 93317-330U2, 90119-06291-00
                for m in re.finditer(r'\b([A-Z0-9]{2,5}-[A-Z0-9]{3,6}(?:-[A-Z0-9]{2,4}){0,2})\b', text):
                    pn = m.group(1)
                    if len(pn) >= 8 and '-' in pn and not pn.startswith('http'):
                        # 提取零件名（同行或附近文本）
                        start = max(0, m.start() - 80)
                        context = text[start:m.end() + 80].replace('\n', ' ')
                        parts.append((pn, model, context[:100]))
    except Exception as e:
        print(f'  解析失败 {model}: {e}')
    return parts

def main():
    urls = json.load(open(os.path.join(DIR, 'yamaha_pdf_urls.json')))
    con = db()
    total = 0
    for i, url in enumerate(urls):
        fname = url.split('/')[-1]
        model = fname.replace('.pdf', '').replace('-2024', '').replace('-2023', '').replace('-2015', '').replace('-2014', '').replace('-2012', '').replace('-2010', '').replace('-2013', '')
        path = os.path.join(PDF_DIR, fname)
        # 检查是否已解析
        existing = con.execute("SELECT COUNT(*) FROM part WHERE model=?", (model,)).fetchone()[0]
        if existing > 0:
            print(f'[{i+1}/{len(urls)}] {model} 已解析({existing}零件)，跳过')
            continue
        print(f'[{i+1}/{len(urls)}] 下载 {fname}...', end=' ', flush=True)
        if not download(url, path):
            print('下载失败')
            continue
        size = os.path.getsize(path) // 1024
        print(f'{size}KB 解析...', end=' ', flush=True)
        parts = extract_parts(path, model)
        # 去重
        seen = set()
        for pn, mod, ctx in parts:
            if pn not in seen:
                seen.add(pn)
                con.execute("INSERT INTO part(part_no,name,model,source) VALUES(?,?,?,?)",
                           (pn, '', mod, 'yamaha_pdf'))
        con.commit()
        total += len(seen)
        print(f'{len(seen)}零件')
        time.sleep(0.5)
    distinct = con.execute("SELECT COUNT(DISTINCT part_no) FROM part").fetchone()[0]
    total_parts = con.execute("SELECT COUNT(*) FROM part").fetchone()[0]
    print(f'\n完成! 总记录{total_parts}, 不同零件号{distinct}')
    con.close()

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"FAIL {type(e).__name__}: {e}")
