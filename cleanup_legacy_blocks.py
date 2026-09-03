# -*- coding: utf-8 -*-
"""清理/格式化联系人comment里的历史同步块（一次性治理+可复用）。
- 改挂残留：商机现在挂在别的联系人身上 → 删除该联系人身上的冗余块（对方已有新块）
- 孤儿块：商机已删除/改名，旧纯文本块 → 就地转富文本(标题加粗、正文按行包div)，保留历史内容
- 本人旧格式块：同样就地转富文本
用法: python cleanup_legacy_blocks.py [--dry-run|--apply]
"""
import sys, io, os, re, collections
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from odoo.client import OdooClient
from config import ODOO_URL, ODOO_DB, ODOO_UID, ODOO_PWD
from sync_leads import sanitize_lead_html

APPLY = "--apply" in sys.argv
c = OdooClient(ODOO_URL, ODOO_DB, ODOO_UID, ODOO_PWD, dry_run=not APPLY)

TITLE = re.compile(
    r'(?:<div><br></div>)?<div>(?:<strong>)?\s*={5,}\s*来自商机：\s*(.*?)\s*={5,}\s*(?:</strong>)?</div>',
    re.DOTALL)
OLD_TITLE = re.compile(r'(?:<div><br></div>)?<div>\s*={5,}')  # 无strong=旧格式标题(前导br可选)


def fmt_body(b):
    """旧块正文：先sanitize清编辑器元数据/XSS，再按行包div分行，保留历史内容"""
    b = sanitize_lead_html(b)
    lines = [ln.strip() for ln in re.split(r'\n', b) if ln.strip()]
    if not lines:
        return ""
    out = []
    for ln in lines:
        out.append(ln if ln.lstrip().startswith('<') else '<div>%s</div>' % ln)
    return ''.join(out)


def new_title(name):
    return '<div><br></div><div><strong>========== 来自商机：%s ==========</strong></div>' % name


def main():
    leads = c.jsonrpc_call("crm.lead", "search_read", [[["user_id", "=", ODOO_UID]]],
        {"fields": ["id", "name", "partner_id", "active"], "limit": 1000}) or []
    name2owners = collections.defaultdict(set)
    for l in leads:
        if l.get("partner_id"):
            name2owners[l.get("name", "")].add(l["partner_id"][0])

    ps = c.jsonrpc_call("res.partner", "search_read", [[["user_id", "=", ODOO_UID]]],
        {"fields": ["id", "name", "comment"], "limit": 1000}) or []

    n_del = n_fmt = n_touch = 0
    for p in ps:
        cm = p.get("comment") or ""
        if "来自商机" not in cm:
            continue
        ms = list(TITLE.finditer(cm))
        if not ms:
            continue
        # 切块: 前导 + [(标题match, 正文)]
        pieces = [cm[:ms[0].start()]]
        for i, m in enumerate(ms):
            body_end = ms[i + 1].start() if i + 1 < len(ms) else len(cm)
            pieces.append((m, cm[m.end():body_end]))
        out = pieces[0]
        changed = False
        for item in pieces[1:]:
            m, body = item
            name = m.group(1).strip()
            owners = name2owners.get(name)
            title_html = m.group(0)
            is_old = bool(OLD_TITLE.match(title_html))
            if owners is not None and p["id"] not in owners and owners:
                # 改挂残留: 商机明确属于别人 → 删除整块
                out = out  # 不拼接=删除
                n_del += 1; changed = True
                print(f"  [删除改挂残留] {p['name']} <- {name} (现属{sorted(owners)})")
                continue
            if is_old:
                # 旧格式(孤儿或本人): 就地转富文本保留内容
                out += new_title(name) + fmt_body(body)
                n_fmt += 1; changed = True
            else:
                out += title_html + body  # 已是新格式,原样保留
        if changed:
            n_touch += 1
            if APPLY:
                c.safe_write_jsonrpc("res.partner", p["id"], {"comment": out})
    print(f"\n{'[APPLY已写入]' if APPLY else '[DRY-RUN]'} 涉及联系人{n_touch}个, 删除改挂块{n_del}个, 旧块转富文本{n_fmt}个")


if __name__ == "__main__":
    main()
