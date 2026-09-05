# -*- coding: utf-8 -*-
"""
微信名片 / 视频号主页 截图 -> 本地OCR提取手机号（零token、零风险，不碰微信客户端）

两类页面:
  A. 朋友名片：昵称/微信号/地区 + 朋友资料(备注/电话/标签)
  B. 视频号主页：大标题 + 地区性别 + 简介(常含 📞/电话/微信同号) + N条原创内容

号码分层（对应setphone自动填 vs 待确认）:
  phones(A可信): 名片「电话/手机」栏；或带 电话/手机/同号/📞/联系/热线 语境；或视频号主页本人公开号
  suspect(B疑似): 名片里无语境的裸号（如头像水印、签名），只列出待确认
  丢弃: 嵌在微信号里的数字、非11位、非法号段
匹配Odoo以「备注」全名（名片）或「标题」（视频号）为准。
用法: python card_ocr.py <图片或文件夹> [--out cards.json]
"""
import sys, os, io, re, json, argparse, glob

sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')

IMG_EXT = ('.png', '.jpg', '.jpeg', '.bmp', '.webp')
PHONE = re.compile(r'1[3-9]\d{9}')

# 名片上这些标签行里的数字不是手机号（微信号值/视频号名字/日期等）
EXCLUDE_LABELS = ['微信号', '视频号', '昵称', '添加时间', '共同群聊',
                  '朋友圈', '朋友资料', '更多信息', '地区', '来源']
FIELD_LABELS = ['备注', '备注名', '昵称', '微信号', '地区', '电话', '手机', '标签']
# 强语境：出现这些词的号码可信
CTX_WORDS = ['电话', '手机', '同号', '联系', '热线', '致电', '拨打', 'tel', '☎', '📞', '微信同']


def find_phones(s):
    # 先按中文/标点切段，避免门牌号(167号)和手机号粘连；段内去空格连字符后再匹配
    out = []
    for seg in re.split(r'[，,。、；;：:（）()【】\[\]\u4e00-\u9fff]', str(s)):
        d = re.sub(r'[^\d]', '', seg)
        out += PHONE.findall(d)
    return out


def cluster_rows(boxes, y_tol=18):
    bs = sorted(boxes, key=lambda b: (b[1], b[0]))
    rows = []
    for x, y, text in bs:
        for row in rows:
            if abs(row[0] - y) <= y_tol:
                row[1].append((x, text)); break
        else:
            rows.append([y, [(x, text)]])
    out = []
    for y, items in rows:
        items.sort(key=lambda z: z[0])
        out.append((int(y), items))
    return out


def ocr_image(path, ocr):
    res, _ = ocr(path)
    from PIL import Image
    with Image.open(path) as im:
        W, H = im.size
    boxes = [(int(b[0][0]), int(b[0][1]), (t or '').strip())
             for b, t, c in (res or []) if (t or '').strip()]
    rows = cluster_rows(boxes)
    full = ' '.join(t for _, _, t in boxes)

    # 页面类型：视频号主页有“N条原创内容”，名片有“朋友资料/微信号”
    is_channel = ('原创内容' in full) or ('条原创' in full)

    fields = {'备注': '', '昵称': '', '微信号': '', '地区': '', '电话': '', '标签': ''}
    wxid_digits = ''
    trusted, suspect = [], []

    def add(seq, p):
        if p and p not in seq:
            seq.append(p)

    for y, items in rows:
        row_text = ' '.join(t for _, t in items)
        left = items[0][1]
        label = None
        for L in FIELD_LABELS:
            if left == L or left.startswith(L):
                label = '备注' if L == '备注名' else L
                break
        value_text = ' '.join(t for _, t in items[1:]) if label else row_text
        if label and not value_text:
            mm = re.split(r'[:：]', left, maxsplit=1)
            value_text = mm[1] if len(mm) > 1 else ''
        if label in fields:
            fields[label] = (fields[label] + ' ' + value_text).strip() if fields[label] else value_text.strip()
        if label == '微信号' or '微信号' in row_text:
            wm = re.search(r'([A-Za-z][\w\-]{3,})', value_text or row_text)
            if wm:
                wxid_digits += re.sub(r'\D', '', wm.group(1))

        excluded = (not is_channel) and (
            any(left.startswith(k) for k in EXCLUDE_LABELS) or
            any(k in row_text for k in EXCLUDE_LABELS))
        strong_ctx = any(k.lower() in row_text.lower() for k in CTX_WORDS)

        for _, t in items:
            for p in find_phones(t):
                if p in wxid_digits:          # 微信号夹带，丢弃
                    continue
                if is_channel or strong_ctx:
                    add(trusted, p)
                elif excluded:
                    continue
                else:
                    add(suspect, p)

    # 视频号标题：头像右侧(x>22%宽)、顶部40%区域内最长的单个文本块；名片则用备注
    title = fields['备注']
    if not title:
        cands = []
        for x, y, t in boxes:
            if y >= H * 0.40 or x <= W * 0.20 or len(t) < 3:
                continue
            if any(k in t for k in ['原创内容', '关注', 'Ship Blue', '维修', '保养']):
                continue
            if PHONE.search(t.replace(' ', '')):      # 含手机号的块不当标题
                continue
            han = re.findall(r'[\u4e00-\u9fff]', t)
            if len(han) < 3:                           # 标题至少3个汉字
                continue
            cands.append((len(han), t))
        if cands:
            title = max(cands)[1]

    where = '视频号主页' if is_channel else ('电话/语境栏' if trusted else '无')
    return {
        'file': os.path.basename(path),
        'page': '视频号' if is_channel else '名片',
        'remark': title or fields['昵称'],
        'nick': fields['昵称'],
        'wxid': fields['微信号'],
        'region': fields['地区'],
        'tag': fields['标签'],
        'phones': trusted,
        'suspect': suspect,
        'phone_source': where,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('target')
    ap.add_argument('--out', default='cards.json')
    p = ap.parse_args()
    if os.path.isdir(p.target):
        files = [f for f in sorted(glob.glob(os.path.join(p.target, '*')))
                 if f.lower().endswith(IMG_EXT)]
    else:
        files = [p.target]
    if not files:
        print('没有图片'); return
    from rapidocr_onnxruntime import RapidOCR
    ocr = RapidOCR()
    out = []
    for f in files:
        try:
            r = ocr_image(f, ocr)
            out.append(r)
            a = ','.join(r['phones']) if r['phones'] else '无'
            b = (' | 疑似:' + ','.join(r['suspect'])) if r['suspect'] else ''
            print(f"[{r['page']}] {r['file']} | {r['remark']} | 可信={a}{b}")
        except Exception as e:
            print(f"{os.path.basename(f)} FAIL: {type(e).__name__}:{e}")
    with open(p.out, 'w', encoding='utf-8') as fp:
        json.dump(out, fp, ensure_ascii=False, indent=1)
    na = sum(1 for r in out if r['phones'])
    nb = sum(1 for r in out if r['suspect'])
    print(f'\nOK 共{len(out)}张：{na}张有可信号，{nb}张有疑似号 -> {p.out}')


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"FAIL {type(e).__name__}: {e}")
