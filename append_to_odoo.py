# -*- coding: utf-8 -*-
"""
安全追加HTML到Odoo备注（绝不覆盖原文）
用法:
  python append_to_odoo.py <lead_id> <html_file> [--field description]
  python append_to_odoo.py 155 阿良_summary.html
"""
import sys, io, os, argparse

sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from odoo.client import OdooClient
from config import ODOO_URL, ODOO_DB, ODOO_UID, ODOO_PWD


def main():
    parser = argparse.ArgumentParser(description="安全追加HTML到Odoo备注")
    parser.add_argument("lead_id", type=int, help="商机/线索ID")
    parser.add_argument("html_file", help="HTML文件路径")
    parser.add_argument("--model", default="crm.lead", help="模型(默认crm.lead)")
    parser.add_argument("--field", default="description", help="字段(默认description)")
    args = parser.parse_args()

    if not os.path.exists(args.html_file):
        print(f"FAIL: 文件不存在 {args.html_file}")
        sys.exit(1)

    html = open(args.html_file, encoding="utf-8").read()
    if len(html.strip()) < 10:
        print("FAIL: HTML内容为空")
        sys.exit(1)

    odoo = OdooClient(ODOO_URL, ODOO_DB, ODOO_UID, ODOO_PWD)

    # 先读原记录确认存在
    records = odoo.read(args.model, [args.lead_id], ["id", "name", args.field])
    if not records:
        print(f"FAIL: 记录不存在 {args.model} ID={args.lead_id}")
        sys.exit(1)
    rec = records[0]
    old_len = len(rec.get(args.field) or "")
    print(f"目标: {rec['name']} (ID={args.lead_id})")
    print(f"原备注长度: {old_len}")

    # 安全追加
    ok, old_l, new_l = odoo.append_html(args.model, args.lead_id, args.field, html)
    if ok:
        print(f"OK: 追加成功 {old_l} → {new_l} (+{new_l - old_l})")
    else:
        print(f"FAIL: 追加失败")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"FAIL {type(e).__name__}: {e}")
