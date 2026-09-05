# -*- coding: utf-8 -*-
"""船外机配件业务知识库。

纯常量+纯函数, 无网络无第三方依赖。
"""

import re
import unicodedata


def norm(code):
    """标准化件号: 去括号内容、转大写、去尾缀(-OIL/-ZN等)、去尾部-00/-000。

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
        # 去尾缀
        s = re.sub(r"-(OIL|ZN|AL|O|MARTYR|RIKEN|COPPER|BEST-[A-Z0-9]+)$", "", s)
        # 去尾部 -00/-000
        s = re.sub(r"-0{2,3}$", "", s)
        return s.strip()
    except Exception:
        return str(code).strip().upper()


# 部位纠正映射: 93106系列=水泵侧水路油封(封冷却水)
# 93101=齿轮箱油封(28M16驱动轴/30M17车叶轴,封齿轮油)
# 93102=曲轴油封
PART_POS_FIX = {
    '93106-09014': '水路油封',
}


def fix_pos(code, pos):
    """根据件号纠正部位描述。

    Args:
        code: 原始件号
        pos: 原始部位描述

    Returns:
        纠正后的部位描述
    """
    try:
        n = norm(code)
        if n in PART_POS_FIX:
            return PART_POS_FIX[n]
        return pos
    except Exception:
        return pos


# 碳刷配对: 64E-43891=碳刷, 64E-43892=碳刷+断路器, 二者成对=一组
# 6H1-43891 当前中国仓无货不要推荐 (2026-09 用户确认)
BRUSH_PAIR = ('64E-43891', '64E-43892')


def brush_note(code):
    """返回碳刷相关说明。

    Args:
        code: 原始件号

    Returns:
        说明文字或空字符串
    """
    try:
        n = norm(code)
        if n == '64E-43891':
            return '碳刷(需与64E-43892配对使用)'
        elif n == '64E-43892':
            return '碳刷+断路器(需与64E-43891配对使用)'
        elif n == '6H1-43891':
            return '6H1-43891 当前中国仓无货, 不建议推荐'
        return ''
    except Exception:
        return ''


# 老款油封集合: 适配老机型, 不当"新品可带"推荐 (2026-09 用户确认)
OLD_PARTS = {
    '93101-25M03',
    '93101-22M60',
}


def is_old(code):
    """判断是否为老款配件。

    Args:
        code: 原始件号

    Returns:
        True 表示是老款配件
    """
    try:
        n = norm(code)
        return n in OLD_PARTS
    except Exception:
        return False


# 葡语→中文品类词典 (2026-09 用户确认)
PT_BR = {
    'ESCOVA': '碳刷',
    'DISJUNTOR': '断路器/继电器',
    'RELÉ': '继电器',
    'ROLAMENTO': '轴承',
    'MANCAL': '轴承座',
    'VEDAÇÃO DE ÓLEO': '油封',
    'OIL SEAL': '油封',
    'RETENTOR': '油封',
    'PINO': '销',
    'JUNTA': '垫片',
    'GASKET': '垫片',
    'TERMOSTATO': '恒温器',
    'CORREIA': '皮带',
    'ANODO': '阳极',
    'IMPULSIONADOR': '叶轮',
    'ROTOR': '叶轮',
    'BOMBA DE ÁGUA': '水泵',
    'FILTRO': '滤芯',
    'MANGUEIRA': '软管/油管',
    'PARAFUSO': '螺栓',
}


def _remove_accents(s):
    """去除字符串中的重音符号。

    Args:
        s: 输入字符串

    Returns:
        去除重音后的字符串
    """
    try:
        if not s:
            return ''
        nfkd = unicodedata.normalize('NFD', s)
        return nfkd.encode('ascii', 'ignore').decode('ascii')
    except Exception:
        return s


def categorize(code, name=''):
    """综合判断配件品类。

    优先级: 件号前缀 > 中文名 > 葡语名

    Args:
        code: 原始件号
        name: 配件名称(可为中文或葡语)

    Returns:
        中文品类字符串
    """
    try:
        n = norm(code)
        name_upper = _remove_accents((name or '').upper())

        # 件号优先判断
        if '82181' in n:
            return '断路器/继电器'
        if '43891' in n or '43892' in n:
            return '碳刷'
        if '44352' in n or '叶轮' in name or 'IMPULSIONADOR' in name_upper or 'ROTOR' in name_upper:
            return '叶轮'
        if 'W0078' in n or '水泵维修包' in name:
            return '水泵维修包'
        if n.startswith('93102'):
            return '曲轴油封'
        if n.startswith('93101') or n.startswith('93106') or '油封' in name or 'RETENTOR' in name_upper or 'OIL SEAL' in name_upper:
            return '油封'
        if n.startswith('93210') or n.startswith('93211') or 'O型圈' in name or 'ANEL' in name_upper:
            return 'O型圈'
        if n.startswith('45251') or n.startswith('45371') or n.startswith('11325') or '阳极' in name or 'ANODO' in name_upper:
            return '阳极'
        if n.startswith('24410') or n.startswith('13907') or '燃油泵' in name:
            return '燃油泵'
        if n.startswith('24563') or n.startswith('24501') or n.startswith('13440') or 'WS24A' in n or '滤芯' in name or 'FILTRO' in name_upper:
            return '滤芯'

        # 名称判断
        if 'ROLAMENTO' in name_upper:
            return '轴承'
        if 'JUNTA' in name_upper or 'GASKET' in name_upper:
            return '垫片'
        if 'TERMOSTATO' in name_upper:
            return '恒温器'
        if 'CORREIA' in name_upper:
            return '皮带'
        if 'MANGUEIRA' in name_upper:
            return '油管/软管'

        return '其他'
    except Exception:
        return '其他'
