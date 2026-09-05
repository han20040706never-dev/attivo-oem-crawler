# -*- coding: utf-8 -*-
"""
中国大陆需求清单一键填写工具
用法:
  python add_demand.py <编号> "<描述>" "<客户>" [编号2 描述2 客户2 ...]
  python add_demand.py 63V-W0093-00 "二冲15雅马哈化油器维修包" "浙江绍兴黄先生（好好船外机）"
  python add_demand.py "68V-45560-00/68V-45571-00" "雅马哈4冲115齿轮组" "浙江台州三门王先生"
  python add_demand.py 93317-330U2 "轴承" "客户A" 93341-93020 "轴承" "客户A"
"""
import sys, io, os, re, requests, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from odoo.client import OdooClient
from config import ODOO_URL, ODOO_DB, ODOO_UID, ODOO_PWD

TASK_ID = 58  # 中国大陆需求清单
CROSSREF_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "part_crossref.json")


def _load_crossref():
    if os.path.exists(CROSSREF_PATH):
        with open(CROSSREF_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _crossref_note(pn):
    """返回互换款提示文本"""
    cr = _load_crossref()
    info = cr.get(pn.upper())
    if not info:
        return ""
    parts = []
    if info.get("replaced_by"):
        parts.append("被" + "/".join(info["replaced_by"]) + "替代")
    if info.get("replaces"):
        parts.append("替代" + "/".join(info["replaces"]))
    if info.get("note"):
        parts.append(info["note"])
    return "；".join(parts) if parts else ""


def _today():
    t = time.localtime()
    return f"{t.tm_year}.{t.tm_mon}.{t.tm_mday}"


H = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
     'Accept-Language': 'zh-CN,zh;q=0.9'}


def check_part(pn, today=None):
    """查attivox官网，返回(库存文本, 产品名)。pn支持/分隔多个编号。"""
    if today is None:
        today = _today()
    # 多编号合并一行
    if "/" in pn:
        parts = pn.split("/")
        results = []
        names = []
        for p in parts:
            r, n = check_part(p.strip(), today)
            # 去掉日期后缀，合并后统一加
            r_clean = re.sub(r'（\d{4}\.\d+\.\d+）$', '', r)
            results.append(r_clean)
            if n:
                names.append(n)
        return "/".join(results) + f"（{today}）", names[0] if names else None

    s = requests.Session()
    s.headers.update(H)
    s.cookies.set('selected_region', 'SG', domain='.attivox.com')
    s.cookies.set('frontend_lang', 'zh_CN', domain='.attivox.com')

    try:
        r = s.get(f"https://www.attivox.com/shop?search={pn}", timeout=20)
        cards = re.split(r'class="oe_product_cart', r.text)[1:]

        best = None
        for card in cards:
            m = re.search(r'href="/shop/([^"]+?)-(\d+)"', card)
            if not m:
                continue
            slug, pid = m.group(1), m.group(2)
            nm = re.search(r'o_wsale_product_information_text[^>]*>.*?<a[^>]*>(.*?)</a>', card, re.S)
            name = re.sub(r'<[^>]+>', '', nm.group(1)).strip() if nm else ""
            if pn.lower().replace("-", "") in slug.lower().replace("-", ""):
                best = (slug, pid, name)
                break

        if not best:
            note = _crossref_note(pn)
            suffix = f"；{note}" if note else ""
            return f"否，系统中未录入（{today}）{suffix}", None

        slug, pid, name = best
        r2 = s.get(f"https://www.attivox.com/shop/{slug}-{pid}", timeout=20)
        stock_m = re.search(r'id="stock-status-text"[^>]*data-stock="(\d+)"', r2.text)
        stock = int(stock_m.group(1)) if stock_m else 0

        note = _crossref_note(pn)
        suffix = f"；{note}" if note else ""
        if stock > 0:
            return f"是，{name}，新加坡库存{stock}（{today}）{suffix}", name
        else:
            return f"是，{name}，新加坡无库存（{today}）{suffix}", name
    except Exception as e:
        return f"查询失败（{today}）", None


def main():
    args = sys.argv[1:]
    if len(args) < 3 or len(args) % 3 != 0:
        print("用法: python add_demand.py <编号> <描述> <客户> [编号2 描述2 客户2 ...]")
        print("  编号可用/分隔多个，如 68V-45560-00/68V-45571-00")
        sys.exit(1)

    today = _today()
    items = []
    for i in range(0, len(args), 3):
        pn, desc, customer = args[i], args[i+1], args[i+2]
        print(f"查询: {pn} ...", end=" ", flush=True)
        stock, name = check_part(pn, today)
        print(stock)
        items.append({"pn": pn, "desc": desc, "customer": customer, "stock": stock})

    odoo = OdooClient(ODOO_URL, ODOO_DB, ODOO_UID, ODOO_PWD)
    task = odoo.jsonrpc_call("project.task", "read", [[TASK_ID], ["description"]])
    desc = task[0]["description"]

    rows_html = ""
    for it in items:
        rows_html += (
            '<tr style="height: 38px;">'
            f'<td style="width: 204.038px;"><div>{it["pn"]}</div></td>'
            f'<td style="width: 254.425px;"><div>{it["desc"]}</div></td>'
            f'<td style="width: 452.561px;"><div>{it["customer"]}</div></td>'
            f'<td style="width: 452.569px;"><div>{it["stock"]}</div></td>'
            '<td style="width: 127.021px;"><div><br></div></td>'
            '</tr>'
        )

    desc = desc.replace("</tbody>", rows_html + "</tbody>")
    result = odoo.safe_write_jsonrpc("project.task", [TASK_ID], {"description": desc})

    if result:
        print(f"\nOK: 已追加{len(items)}条到需求清单")
    else:
        print("\nFAIL: 写入失败")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"FAIL {type(e).__name__}: {e}")
