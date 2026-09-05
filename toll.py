# -*- coding: utf-8 -*-
"""
toll.py —— 通行费报销一条龙（一条命令，本地OCR零token，不重复造轮子）

典型附件（一次出差的每笔通行费通常3个文件）：
  1) PDF  = 通行费电子发票
  2) 付款记录截图（微信/支付宝，证明已付）
  3) 高速小程序明细截图（写有 入口站/出口站/时间/车牌/金额）——备注以它为准
  另外可能混有“我的发票/全选”这类【列表截图】，自动识别并忽略、不挂附件。

规则（与会计/用户约定）：
  - 备注格式：入口站 / 出口站 / YYYY-MM-DD  HH:MM / 车牌 / ¥金额（金额仅供参考，费用金额栏留空给会计填）
  - 标题按半月周期：X.1-X.15 或 X.16-X月末（build_expense_name）
  - 审批人 He JiaLei（config EXPENSE_MANAGER_ID，create_expense内已带重试）
  - 防重复：同员工+同日期+同入口站已存在则跳过

用法：
  python toll.py <文件夹>            # 预览计划并直接创建草稿（有防重复，可安全重跑）
  python toll.py <文件夹> --dry-run  # 只预览不创建
  python toll.py <文件夹> --merge    # 整批合并成一条费用
"""
import os
import re
import sys
import io
import argparse
from datetime import datetime, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8")

import create_expense as ce
from odoo import OdooClient, HRExpense
from config import *

PLATE_RE = re.compile(r"[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼使领][A-Z][A-Z0-9]{4,5}[A-Z0-9挂学警港澳]?")
ROUTE_RE = re.compile(r"([一-龥A-Za-z（）()]+?站)\s*[-—一~–到至]\s*([一-龥A-Za-z（）()]+?站)")
LIST_KW = ("我的发票", "全选", "导出发票", "查询发票", "获取发票")
PAY_KW = ("支付", "付款", "商户", "零钱", "银行卡", "微信", "支付宝", "收单", "交易")


def parse_mini_detail(text):
    """从高速小程序【明细】截图文本提取 路线/车牌/时间/金额；提取不到返回None。"""
    routes = ROUTE_RE.findall(text)
    plate = PLATE_RE.search(text)
    # 金额：50.00元 或 ¥50.00
    amount = None
    m = re.search(r"(\d+\.\d{2})\s*元", text) or re.search(r"[¥￥]\s*(\d+\.\d{2})", text)
    if m:
        amount = float(m.group(1))
    # 时间：兼容 2026-08-29 13:02:18 和 2026-08-2913:02:18（OCR丢空格）
    dt = None
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})\D{0,2}(\d{1,2}):(\d{2})(?::(\d{2}))?", text)
    if m:
        y, mo, d, hh, mi = (int(m.group(i)) for i in range(1, 6))
        dt = datetime(y, mo, d, hh, mi)
    if not routes and not plate:
        return None
    entry, exit_ = (routes[0] if routes else ("", ""))
    return {"entry": entry, "exit": exit_, "plate": plate.group(0) if plate else "",
            "amount": amount, "datetime": dt, "n_routes": len(routes)}


def classify_image(path):
    """返回 (kind, data)；kind ∈ mini/pay/list/unknown。"""
    ocr = ce.ocr_payment_screenshot(path)   # 复用：拿金额/日期
    res, _ = ce.get_ocr()(path)
    texts = [t[1] for t in res] if res else []
    full = " ".join(texts)
    detail = parse_mini_detail(full)
    is_list = (detail and detail["n_routes"] >= 2) or any(k in full for k in LIST_KW)
    if is_list:
        return "list", None
    if detail and (detail["plate"] or detail["entry"]):
        detail["pay_amount"] = ocr.get("amount")
        return "mini", detail
    if any(k in full for k in PAY_KW):
        return "pay", {"amount": ocr.get("amount")}
    return "unknown", {"amount": ocr.get("amount")}


def build_week_title(dt):
    """按自然周（周一为一周起始）生成标题：2026.M.D-M.D销售出差报销通行费"""
    monday = dt - timedelta(days=dt.weekday())
    sunday = monday + timedelta(days=6)
    if monday.year == sunday.year:
        title = f"{monday.year}.{monday.month}.{monday.day}-{sunday.month}.{sunday.day}销售出差报销通行费"
    else:
        title = f"{monday.year}.{monday.month}.{monday.day}-{sunday.year}.{sunday.month}.{sunday.day}销售出差报销通行费"
    return title


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--merge", action="store_true")
    a = ap.parse_args()

    if not os.path.isdir(a.folder):
        print("文件夹不存在:", a.folder); sys.exit(1)
    pdfs = sorted(f for f in os.listdir(a.folder) if f.lower().endswith(".pdf"))
    imgs = sorted(f for f in os.listdir(a.folder)
                  if f.lower().endswith((".jpg", ".jpeg", ".png")))
    if not pdfs:
        print("未找到PDF发票"); sys.exit(0)

    # 1) PDF 发票
    invoices = []
    for f in pdfs:
        text = ce.extract_text_from_pdf(os.path.join(a.folder, f))
        info = ce.extract_toll_info(text) if ce.detect_invoice_type(text) == "toll" else \
               {"amount": None, "entry": "", "exit": "", "datetime": None, "plate": "", "type": "toll"}
        invoices.append({"file": f, "info": info})

    # 2) 图片分类
    minis, pays, lists = [], [], []
    for f in imgs:
        kind, data = classify_image(os.path.join(a.folder, f))
        print(f"  图片 {f[:20]}… -> {kind}")
        if kind == "mini":
            minis.append({"file": f, "d": data})
        elif kind in ("pay", "unknown"):
            pays.append({"file": f, "amount": (data or {}).get("amount")})
        elif kind == "list":
            lists.append(f)  # 多路线汇总明细图,仅作凭证附件(merge整批挂一条)

    client = OdooClient(ODOO_URL, ODOO_DB, ODOO_UID, ODOO_PWD, dry_run=a.dry_run)
    exp = HRExpense(client, {
        "product_id": EXPENSE_PRODUCT_ID, "employee_id": EXPENSE_EMPLOYEE_ID,
        "company_id": EXPENSE_COMPANY_ID, "manager_id": EXPENSE_MANAGER_ID,
        "account_id": EXPENSE_ACCOUNT_ID, "currency_id": EXPENSE_CURRENCY_ID,
        "payment_mode": EXPENSE_PAYMENT_MODE,
        "description_prefix": "销售出差报销通行费"})

    used_mini, used_pay = set(), set()
    created, skipped = [], []

    # ========== MERGE 模式 ==========
    if a.merge:
        merged_lines = []
        all_attachments = []
        total_amount = 0.0
        earliest_dt = None
        idx = 0
        for inv in invoices:
            info = inv["info"]
            # 3) 按金额匹配小程序明细（备注以它为准）
            mini = None
            cand = [m for m in minis if m["file"] not in used_mini]
            if info["amount"] is not None:
                same = [m for m in cand if m["d"]["amount"] == info["amount"]]
                if same:
                    mini = same[0]
            if mini is None and cand:
                mini = cand[0]
            if mini:
                used_mini.add(mini["file"]); d = mini["d"]
                info["entry"] = info["entry"] or d["entry"]
                info["exit"] = info["exit"] or d["exit"]
                info["plate"] = info["plate"] or d["plate"]
                if not info.get("datetime") and d["datetime"]:
                    info["datetime"] = d["datetime"]
                if info["amount"] is None:
                    info["amount"] = d["amount"]
            # 付款记录按金额匹配
            pay = None
            if info["amount"] is not None:
                pc = [p for p in pays if p["file"] not in used_pay and p["amount"] == info["amount"]]
                if pc:
                    pay = pc[0]
            if pay is None:
                pc = [p for p in pays if p["file"] not in used_pay]
                if pc and len(pc) == len(invoices):  # 数量恰好一一对应才兜底
                    pay = pc[0]
            if pay:
                used_pay.add(pay["file"])

            if not info.get("datetime"):
                print(f"[警告] {inv['file']} 缺时间，默认今天")
                dt = datetime.now()
            else:
                dt = info["datetime"]
            if earliest_dt is None or dt < earliest_dt:
                earliest_dt = dt
            idx += 1
            desc_line = ce.build_description(info)
            merged_lines.append(f"{idx}. {desc_line}")
            if info["amount"] is not None:
                total_amount += info["amount"]
            atts = [inv["file"]] + ([mini["file"]] if mini else []) + ([pay["file"]] if pay else [])
            for af in atts:
                if af not in all_attachments:
                    all_attachments.append(af)

        if earliest_dt is None:
            print("未解析到任何有效通行费记录"); sys.exit(0)

        # 多路线汇总明细图(list)作为凭证一并挂到合并单
        for _lf in lists:
            if _lf not in all_attachments:
                all_attachments.append(_lf)

        week_title = build_week_title(earliest_dt)
        merged_desc = "\n".join(merged_lines) + f"\n合计 ¥{total_amount:.2f}（金额栏留空，由会计填写）"
        exp_date = earliest_dt.strftime("%Y-%m-%d")

        # 防重复：批次维度
        dup = client.search("hr.expense",
                            [["employee_id", "=", EXPENSE_EMPLOYEE_ID],
                             ["name", "=", week_title]], limit=1)
        if dup:
            print(f"[跳过-已存在合并单] {week_title}")
            skipped = [inv["file"] for inv in invoices]
        else:
            print(f"[计划] {week_title} | 最早日期 {exp_date} | 共 {len(invoices)} 笔 | 合计 ¥{total_amount:.2f}")
            print(f"        附件: {all_attachments}")
            if a.dry_run:
                print(f"[MERGE计划] 将合并为 1 条")
                print(f"周标题: {week_title}")
                print(f"最早日期: {exp_date}")
                print(f"合并后的完整描述:\n{merged_desc}")
                print(f"去重后的全部附件文件列表:")
                for af in all_attachments:
                    print(f"  - {af}")
            else:
                try:
                    eid = exp.create_expense(merged_desc, date=exp_date, name=week_title)
                    for af in all_attachments:
                        try:
                            exp.attach_file(eid, os.path.join(a.folder, af))
                        except Exception as e:
                            print(f"  [警告] 附件 {af} 挂载失败: {e}")
                    created.append(eid)
                    print(f"  ✓ ID={eid} 已挂{len(all_attachments)}个附件")
                except Exception as e:
                    print(f"  [错误] 创建合并单失败: {e}")

        print("=" * 46)
        print(f"完成：合并新建 {len(created)} 条 {created if created else ''}，含 {len(invoices)} 笔、{len(all_attachments)} 个附件，跳过 {len(skipped)} 条")
        if len(used_mini) < len(minis):
            print("提示：有未匹配的小程序明细图：", [m['file'] for m in minis if m['file'] not in used_mini])
        return

    # ========== 非 MERGE 模式（原有逻辑） ==========
    for inv in invoices:
        info = inv["info"]
        # 3) 按金额匹配小程序明细（备注以它为准）
        mini = None
        cand = [m for m in minis if m["file"] not in used_mini]
        if info["amount"] is not None:
            same = [m for m in cand if m["d"]["amount"] == info["amount"]]
            if same:
                mini = same[0]
        if mini is None and cand:
            mini = cand[0]
        if mini:
            used_mini.add(mini["file"]); d = mini["d"]
            info["entry"] = info["entry"] or d["entry"]
            info["exit"] = info["exit"] or d["exit"]
            info["plate"] = info["plate"] or d["plate"]
            if not info.get("datetime") and d["datetime"]:
                info["datetime"] = d["datetime"]
            if info["amount"] is None:
                info["amount"] = d["amount"]
        # 付款记录按金额匹配
        pay = None
        if info["amount"] is not None:
            pc = [p for p in pays if p["file"] not in used_pay and p["amount"] == info["amount"]]
            if pc:
                pay = pc[0]
        if pay is None:
            pc = [p for p in pays if p["file"] not in used_pay]
            if pc and len(pc) == len(invoices):  # 数量恰好一一对应才兜底
                pay = pc[0]
        if pay:
            used_pay.add(pay["file"])

        if not info.get("datetime"):
            print(f"[警告] {inv['file']} 缺时间，默认今天")
        exp_date = info["datetime"].strftime("%Y-%m-%d") if info.get("datetime") else \
            datetime.now().strftime("%Y-%m-%d")
        desc = ce.build_description(info)
        name = ce.build_expense_name(info)

        # 4) 防重复：同员工+同日期+同入口站
        dup = client.search("hr.expense",
                            [["employee_id", "=", EXPENSE_EMPLOYEE_ID],
                             ["date", "=", exp_date],
                             ["description", "ilike", info["entry"] or "___none___"]], limit=1)
        plan = f"{name} | {info['entry']}→{info['exit']} | {exp_date} | {info['plate']} | ¥{info['amount']}"
        atts = [inv["file"]] + ([mini["file"]] if mini else []) + ([pay["file"]] if pay else [])
        if dup:
            print(f"[跳过-已存在] {plan}"); skipped.append(inv["file"]); continue
        print(f"[计划] {plan}\n        附件: {atts}")
        if a.dry_run:
            continue
        # 5) 创建+挂附件（金额栏留空，会计填）
        eid = exp.create_expense(desc, date=exp_date, name=name)
        for af in atts:
            exp.attach_file(eid, os.path.join(a.folder, af))
        created.append(eid)
        print(f"  ✓ ID={eid} 已挂{len(atts)}个附件")

    print("=" * 46)
    print(f"完成：新建 {len(created)} 条 {created if created else ''}，跳过 {len(skipped)} 条")
    if len(used_mini) < len(minis):
        print("提示：有未匹配的小程序明细图：", [m['file'] for m in minis if m['file'] not in used_mini])


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"FAIL {type(e).__name__}: {e}")