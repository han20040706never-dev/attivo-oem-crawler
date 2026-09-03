# -*- coding: utf-8 -*-
"""Odoo商机备注 → 联系人备注 增量同步（JSON-RPC版）

用法:
  python sync_leads.py              # 增量同步（按时间戳+内容hash跳过未变）
  python sync_leads.py --dry-run    # 只预览不写入
  python sync_leads.py --full       # 全量同步（忽略时间戳，仍按hash跳过未变）
  python sync_leads.py --rebuild    # 强制重建（忽略时间戳和hash，用富文本HTML重写所有块）

特点：
- 保留商机富文本格式（h2/h3标题、strong加粗、列表、表格、span字号），联系人comment
  与商机description一样有分行/加粗/段落，不再剥成粘连纯文本。
- 分隔块标题加粗，且块识别正则同时兼容历史“纯文本块”和新“HTML块”，--rebuild可干净覆盖旧块。
- 全部走JSON-RPC，逐条写入+回读验证，只有全部成功才更新时间戳。
"""
import os
import re
import sys
import time
import json
import hashlib
import logging
from datetime import datetime, timezone

from odoo.client import OdooClient

try:
    from config import *
except ImportError:
    print("错误: 请复制 config.example.py 为 config.py 并填入配置")
    sys.exit(1)

BASE = os.path.dirname(os.path.abspath(__file__))
LAST_SYNC_FILE = os.path.join(BASE, "_last_sync.txt")
HASH_FILE = os.path.join(BASE, "sync_hashes.json")
LOG_FILE = os.path.join(BASE, "sync_log.txt")

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ]
)
log = logging.info


def strip_html(text):
    """把HTML转纯文本（备用，主同步已改用 sanitize_lead_html 保留格式）"""
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"</p>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# 富文本白名单标签 -> 允许保留的排版属性
_ALLOWED_HTML = {
    'h1': ['style', 'class', 'align'], 'h2': ['style', 'class', 'align'],
    'h3': ['style', 'class', 'align'], 'h4': ['style', 'class', 'align'],
    'b': ['style', 'class'], 'strong': ['style', 'class'],
    'i': ['style', 'class'], 'em': ['style', 'class'],
    'u': ['style', 'class'], 's': ['style', 'class'], 'strike': ['style', 'class'],
    'sub': ['style', 'class'], 'sup': ['style', 'class'], 'mark': ['style', 'class'],
    'br': [], 'hr': ['style', 'class'], 'blockquote': ['style', 'class'],
    'p': ['style', 'class', 'align'], 'div': ['style', 'class', 'align'],
    'span': ['style', 'class'], 'font': ['style', 'class', 'color', 'face', 'size'],
    'ol': ['style', 'class', 'type', 'start'], 'ul': ['style', 'class', 'type'],
    'li': ['style', 'class', 'value'],
    'a': ['style', 'class', 'href', 'target', 'rel'],
    'img': ['style', 'class', 'src', 'alt', 'width', 'height'],
    'table': ['style', 'class', 'border', 'cellpadding', 'cellspacing', 'width'],
    'thead': ['style', 'class'], 'tbody': ['style', 'class'], 'tfoot': ['style', 'class'],
    'tr': ['style', 'class'], 'td': ['style', 'class', 'colspan', 'rowspan', 'width', 'align'],
    'th': ['style', 'class', 'colspan', 'rowspan', 'width', 'align'],
    'caption': ['style', 'class'], 'colgroup': ['span'], 'col': ['span', 'style', 'width'],
}
_TAG_RE = re.compile(r'<(/?)([a-zA-Z0-9]+)([^>]*)>')
_ATTR_RE = re.compile(r'([a-zA-Z-:]+)\s*=\s*("[^"]*"|\'[^\']*\'|[^\s>]+)')


def sanitize_lead_html(description):
    """清理商机HTML：保留富文本排版(标题/加粗/列表/表格/span字号样式)，
    去掉Odoo编辑器历史元数据与script/on事件等危险内容，输出安全HTML片段。"""
    if not description:
        return ""
    s = description
    # 1. 去掉最外层包裹div的编辑器历史元数据（两种属性顺序）
    s = re.sub(r'<div\s+data-oe-version="[^"]*"\s+data-last-history-steps="[^"]*"\s*>',
               '<div>', s, count=1)
    s = re.sub(r'<div\s+data-last-history-steps="[^"]*"\s+data-oe-version="[^"]*"\s*>',
               '<div>', s, count=1)
    s = re.sub(r'\s+data-oe-version="[^"]*"', '', s)
    s = re.sub(r'\s+data-last-history-steps="[^"]*"', '', s)
    # 2. 删除危险标签及其内容
    s = re.sub(r'<(script|style|iframe|object|embed|form|input|button)\b[^>]*>.*?</\1>',
               '', s, flags=re.DOTALL | re.IGNORECASE)
    s = re.sub(r'<(script|style|iframe|object|embed|form|input|button)\b[^>]*/>',
               '', s, flags=re.IGNORECASE)
    # 3. 删除 on* 事件属性
    s = re.sub(r'\s+on\w+\s*=\s*("[^"]*"|\'[^\']*\'|[^\s>]+)', '', s, flags=re.IGNORECASE)

    def _clean_tag(m):
        closing, tag, attrs = m.group(1), m.group(2).lower(), m.group(3)
        if tag not in _ALLOWED_HTML:
            return ''  # 非白名单标签：去标签留内容
        if closing:
            return '</%s>' % tag
        kept = []
        for am in _ATTR_RE.finditer(attrs):
            an, av = am.group(1).lower(), am.group(2)
            if an not in _ALLOWED_HTML[tag]:
                continue
            if an in ('href', 'src') and re.search(r'javascript:', av, re.IGNORECASE):
                continue
            kept.append('%s=%s' % (an, av))
        return '<%s>' % tag if not kept else '<%s %s>' % (tag, ' '.join(kept))

    s = _TAG_RE.sub(_clean_tag, s)
    s = re.sub(r'\n{3,}', '\n\n', s)
    s = s.strip()
    # 裸文本正文（非标签开头）按换行包成 div，避免在HTML字段里和标题/上段粘连
    if s and not s.lstrip().startswith('<'):
        parts = [p.strip() for p in re.split(r'\n+', s) if p.strip()]
        s = ''.join('<div>%s</div>' % p for p in parts) if parts else '<div>%s</div>' % s
    return s


# 分隔块（新格式标题加粗）。SEP_PATTERN 的 <strong> 可有可无，兼容历史纯文本块。
SEP_PREFIX = '<div><br></div><div><strong>========== 来自商机：'
SEP_SUFFIX = ' ==========</strong></div>'
SEP_PATTERN = re.compile(
    r'(?:<div><br></div>)?<div>(?:<strong>)?\s*={5,}\s*来自商机：\s*(.*?)\s*={5,}\s*(?:</strong>)?</div>',
    re.DOTALL
)


def jsonrpc_search_read(client, model, domain, fields, limit=500):
    """走JSON-RPC的search_read"""
    return client.jsonrpc_call(model, "search_read", [domain], {"fields": fields, "limit": limit}) or []


def jsonrpc_read(client, model, ids, fields):
    """走JSON-RPC的read"""
    return client.jsonrpc_call(model, "read", [ids, fields]) or []


def make_sync_block(lead_name, description):
    """生成同步块（标题加粗 + 富文本HTML正文）"""
    return f'{SEP_PREFIX}{lead_name}{SEP_SUFFIX}{description}'


def update_partner_comment(old_comment, lead_name, new_description):
    """更新联系人备注中指定商机的同步块。
    - 正则同时兼容旧纯文本块和新HTML块；
    - 已有同名块（含历史重复块）全部删除后追加新块；
    - 保留其他商机块和联系人原有备注。"""
    new_block = make_sync_block(lead_name, new_description)
    matches = list(SEP_PATTERN.finditer(old_comment))
    if not matches:
        return (old_comment + new_block) if old_comment else new_block

    lead_name_stripped = lead_name.strip()
    same_blocks = [(i, m) for i, m in enumerate(matches)
                   if m.group(1).strip() == lead_name_stripped]
    if same_blocks:
        result = old_comment
        for i, m in reversed(same_blocks):
            start = m.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(result)
            result = result[:start] + result[end:]
        return (result + new_block) if result else new_block

    return old_comment + new_block


def main():
    dry_run = "--dry-run" in sys.argv
    full_sync = "--full" in sys.argv
    rebuild = "--rebuild" in sys.argv

    client = OdooClient(ODOO_URL, ODOO_DB, ODOO_UID, ODOO_PWD, dry_run=dry_run)

    log("========== 同步开始%s%s%s ==========",
        " [DRY-RUN]" if dry_run else "",
        " [全量]" if full_sync else "",
        " [强制重建]" if rebuild else "")

    incremental = os.path.exists(LAST_SYNC_FILE) and not full_sync and not rebuild
    last_sync = None
    if incremental:
        with open(LAST_SYNC_FILE, "r") as f:
            last_sync = f.read().strip()
        log("增量同步: write_date > %s", last_sync)
    else:
        log("全量同步")

    lead_fields = ["id", "name", "partner_id", "description", "write_date", "user_id", "active"]
    if incremental:
        domain = [["user_id", "=", ODOO_UID], ["write_date", ">", last_sync]]
    else:
        domain = [["user_id", "=", ODOO_UID]]

    try:
        leads = jsonrpc_search_read(client, "crm.lead", domain, lead_fields, limit=500)
    except Exception as e:
        log("读取商机失败: %s", e)
        return

    log("读取到 %d 个商机", len(leads))

    candidates = [
        l for l in leads
        if l.get("partner_id") and l.get("description")
        and len(l["description"]) > 10
    ]
    log("候选商机: %d 个", len(candidates))

    # 内容hash跳过未变（rebuild 忽略hash，强制全部重写以修复旧纯文本块）
    try:
        with open(HASH_FILE, encoding="utf-8") as f:
            known_hashes = json.load(f)
    except Exception:
        known_hashes = {}

    filtered = []
    for l in candidates:
        if rebuild:
            filtered.append(l)
            known_hashes[str(l["id"])] = hashlib.md5(
                (l.get("description") or "").encode("utf-8")).hexdigest()
            continue
        h = hashlib.md5((l.get("description") or "").encode("utf-8")).hexdigest()
        if known_hashes.get(str(l["id"])) == h:
            continue
        known_hashes[str(l["id"])] = h
        filtered.append(l)
    candidates = filtered
    log("需处理: %d 个", len(candidates))

    if not candidates:
        if not dry_run:
            now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            with open(LAST_SYNC_FILE, "w") as f:
                f.write(now_utc)
        log("无更新，时间戳更新")
        return

    partner_ids = list(set(l["partner_id"][0] for l in candidates))
    log("读取 %d 个联系人...", len(partner_ids))
    try:
        partners_data = jsonrpc_read(client, "res.partner", partner_ids, ["id", "name", "comment"])
    except Exception as e:
        log("读取联系人失败: %s", e)
        return

    partners = {p["id"]: p.get("comment") or "" for p in partners_data}

    # 一个联系人可能有多个商机，依次套用 update_partner_comment 合并
    updates = {}
    partner_names = {}
    for l in candidates:
        pid = l["partner_id"][0]
        lname = l.get("name", "")
        desc = sanitize_lead_html(l["description"])
        partner_names[pid] = l["partner_id"][1]
        old_comment = updates.get(pid, partners.get(pid, ""))
        new_comment = update_partner_comment(old_comment, lname, desc)
        if new_comment != old_comment:
            updates[pid] = new_comment

    log("需写入: %d 条", len(updates))

    if not updates:
        if not dry_run:
            now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            with open(LAST_SYNC_FILE, "w") as f:
                f.write(now_utc)
            with open(HASH_FILE, "w", encoding="utf-8") as f:
                json.dump(known_hashes, f)
        log("备注已是最新，时间戳更新")
        return

    if dry_run:
        for pid, new_comment in updates.items():
            log("  [DRY-RUN] %s (partner %d): %d字", partner_names.get(pid, "?"), pid, len(new_comment))
        log("========== 同步完成 [DRY-RUN] ==========")
        return

    success, fail = 0, 0
    failed_pids = []
    for pid, new_comment in updates.items():
        try:
            client.safe_write_jsonrpc("res.partner", pid, {"comment": new_comment})
            verify = jsonrpc_read(client, "res.partner", [pid], ["comment"])
            if verify and len(verify[0].get("comment") or "") >= len(new_comment) - 50:
                success += 1
                log("  OK: %s (partner %d)", partner_names.get(pid, "?"), pid)
            else:
                fail += 1
                failed_pids.append(pid)
                log("  VERIFY FAIL: %s (partner %d)", partner_names.get(pid, "?"), pid)
        except Exception as e:
            fail += 1
            failed_pids.append(pid)
            log("  ERROR: %s (partner %d): %s", partner_names.get(pid, "?"), pid, str(e)[:100])
        time.sleep(0.1)

    log("========== 同步完成: 成功=%d, 失败=%d ==========", success, fail)

    if fail == 0:
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        with open(LAST_SYNC_FILE, "w") as f:
            f.write(now_utc)
        with open(HASH_FILE, "w", encoding="utf-8") as f:
            json.dump(known_hashes, f)
        log("时间戳更新为 %s", now_utc)
    else:
        log("有 %d 条失败，时间戳不更新，下次会重试", fail)


if __name__ == "__main__":
    main()
