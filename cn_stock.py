# -*- coding: utf-8 -*-
"""Odoo 中国仓实时库存轻量查询模块。

提供中国仓(浙江远致泽昌WH2, 库位根1563)的实时库存查询与缓存功能。
"""

import os
import re
import sys
import json
import time

TOOL = os.path.dirname(os.path.abspath(__file__))
CN_ROOT = 1563  # 中国仓=浙江远致泽昌WH2, stock.location 库位根1563
CACHE = os.path.join(TOOL, '_cn_stock_cache.json')

_client = None
_internal_locs_cache = None


def norm(code):
    """标准化件号: 去括号、转大写、循环去品牌/油品后缀(MARTYR/RIKEN/OIL/BEST-xx)、去尾部-00；材质后缀 AL(铝)/ZN(锌)/COPPER(铜)与 -W/H 保留(不同SKU，不能合并)。

    Args:
        code: 原始件号字符串

    Returns:
        标准化后的件号字符串
    """
    if not code:
        return ''
    try:
        s = str(code)
        # 去括号及其内容
        s = re.sub(r"\(.*?\)", "", s)
        # 转大写
        s = s.upper()
        # 去【品牌/供应商/油品】尾缀，循环去链式后缀(如 -AL-MARTYR)；AL/ZN/COPPER 是材质=不同SKU，必须保留(否则铝/锌阳极库存混算)
        for _ in range(3):
            t = re.sub(r"-(MARTYR|RIKEN|OIL|O|BEST-[A-Z0-9]+)$", "", s)
            if t == s:
                break
            s = t
        # 去尾部 -00/-000(仅真正结尾；以 -AL/-ZN/-W/H 结尾时保留)
        s = re.sub(r"-0{2,3}$", "", s)
        return s.strip()
    except Exception:
        return str(code).strip().upper()


def _get_client():
    """获取 OdooClient 单例实例。

    Returns:
        OdooClient 实例
    """
    global _client
    if _client is not None:
        return _client
    try:
        sys.path.insert(0, TOOL)
        from config import ODOO_URL, ODOO_DB, ODOO_UID, ODOO_PWD
        from odoo.client import OdooClient
        _client = OdooClient(ODOO_URL, ODOO_DB, ODOO_UID, ODOO_PWD)
        return _client
    except Exception as e:
        print(f"FAIL: 初始化Odoo客户端失败: {e}")
        return None


def _internal_locs(cli):
    """获取中国仓所有 internal 子库位 id 集合(单例缓存)。

    Args:
        cli: OdooClient 实例

    Returns:
        set 包含所有 internal 库位 id
    """
    global _internal_locs_cache
    if _internal_locs_cache is not None:
        return _internal_locs_cache
    try:
        locs = cli.search_read(
            'stock.location',
            [('id', 'child_of', CN_ROOT), ('usage', '=', 'internal')],
            ['id'],
            limit=5000
        )
        _internal_locs_cache = {loc['id'] for loc in locs}
        return _internal_locs_cache
    except Exception as e:
        print(f"FAIL: 获取内部库位失败: {e}")
        return set()


def live_qty(codes):
    """实时查询中国仓库存数量。

    高效做法: 先获取所有产品(约2946条)建立 norm->pid 映射,
    再按 pids 查询 stock.quant 并累加 internal 库位数量。

    Args:
        codes: 原始件号字符串列表

    Returns:
        dict {norm件号: 数量float保留1位}, 异常返回 {}
    """
    try:
        cli = _get_client()
        if cli is None:
            return {}

        # 目标 norm 集合
        want = set()
        for c in codes:
            n = norm(c)
            if n:
                want.add(n)
        if not want:
            return {}

        # 获取所有产品建立映射
        products = cli.search_read(
            'product.product',
            [],
            ['id', 'default_code'],
            limit=60000
        )
        norm_to_pids = {}
        for p in products:
            dc = p.get('default_code') or ''
            n = norm(dc)
            if n in want:
                norm_to_pids.setdefault(n, []).append(p['id'])

        # 收集所有 pids
        all_pids = []
        for pids in norm_to_pids.values():
            all_pids.extend(pids)

        result = {n: 0.0 for n in want}
        if not all_pids:
            return result

        # 查询 stock.quant
        quants = cli.search_read(
            'stock.quant',
            [('product_id', 'in', all_pids)],
            ['product_id', 'location_id', 'quantity'],
            limit=100000
        )

        internal_ids = _internal_locs(cli)
        if not internal_ids:
            return {}

        # 累加数量
        pid_to_norm = {}
        for n, pids in norm_to_pids.items():
            for pid in pids:
                pid_to_norm[pid] = n

        qty_sum = {}
        for q in quants:
            pid = q['product_id'][0] if isinstance(q['product_id'], (list, tuple)) else q['product_id']
            loc_id = q['location_id'][0] if isinstance(q['location_id'], (list, tuple)) else q['location_id']
            if loc_id in internal_ids and pid in pid_to_norm:
                n = pid_to_norm[pid]
                qty_sum[n] = qty_sum.get(n, 0.0) + float(q.get('quantity') or 0.0)

        for n in want:
            result[n] = round(qty_sum.get(n, 0.0), 1)

        return result
    except Exception as e:
        print(f"FAIL: 实时查询库存失败: {e}")
        return {}


def load_cache():
    """从缓存文件加载库存数据。

    Returns:
        dict 结构 {norm: {'cn':..,'gl':..,'name':..}}, 损坏/不存在返回 {}
    """
    try:
        if not os.path.exists(CACHE):
            return {}
        with open(CACHE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        st = data.get('ST', {})
        return st if isinstance(st, dict) else {}
    except Exception:
        return {}


def qty_with_verify(codes, verify_zero=True):
    """查询库存数量, 缓存为0或缺失时实时复核。

    Args:
        codes: 原始件号字符串列表
        verify_zero: 是否对缓存值<=0的件号进行实时复核

    Returns:
        dict {原始code: {'qty': float, 'src': 'cache'|'live'}}
    """
    result = {}
    try:
        cache = load_cache()
        need_live = []
        norm_map = {}

        for code in codes:
            n = norm(code)
            if not n:
                result[code] = {'qty': 0.0, 'src': 'live'}
                continue
            norm_map[code] = n
            cached = cache.get(n, {})
            cn_qty = cached.get('cn', 0.0) if isinstance(cached, dict) else 0.0
            if verify_zero and cn_qty <= 0:
                need_live.append(code)
            else:
                result[code] = {'qty': float(cn_qty), 'src': 'cache'}

        if need_live:
            live_result = live_qty(need_live)
            for code in need_live:
                n = norm_map.get(code, norm(code))
                qty = live_result.get(n, 0.0)
                result[code] = {'qty': float(qty), 'src': 'live'}

        return result
    except Exception as e:
        print(f"FAIL: 查询库存失败: {e}")
        return {code: {'qty': 0.0, 'src': 'live'} for code in codes}


def main():
    """命令行入口: 查询指定件号的中国仓库存。"""
    try:
        # Windows 中文环境 stdout 编码处理
        if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
            sys.stdout = sys.stdout.detach() if hasattr(sys.stdout, 'detach') else sys.stdout

        args = sys.argv[1:]
        fresh = False
        if '--fresh' in args:
            fresh = True
            args.remove('--fresh')

        if not args:
            print("用法: python cn_stock.py [--fresh] 件号1 [件号2 ...]")
            return

        if fresh:
            # 忽略缓存全部实时
            live_result = live_qty(args)
            for code in args:
                n = norm(code)
                qty = live_result.get(n, 0.0)
                print(f"{code}  {qty}  [live]")
        else:
            result = qty_with_verify(args)
            for code in args:
                info = result.get(code, {'qty': 0.0, 'src': 'live'})
                print(f"{code}  {info['qty']}  [{info['src']}]")
    except Exception as e:
        print(f"FAIL: {e}")


if __name__ == '__main__':
    main()
