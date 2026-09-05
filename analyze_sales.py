# -*- coding: utf-8 -*-
"""本地聚合分析销售数据，输出紧凑结论"""
import json, os
from collections import defaultdict
from datetime import datetime

DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(DIR, "sales_data.json"), encoding="utf-8") as f:
    d = json.load(f)

orders = d["orders"]
lines = d["lines"]
partners = d["partners"]
products = d["products"]

# 地区推断：从联系人城市/州 + 订单名称 + 客户名
def infer_region(order):
    pid = order.get("ship") or order.get("partner")
    p = partners.get(pid, {})
    state = p.get("state", "")
    city = p.get("city", "")
    name = p.get("name", "")
    oname = order.get("name", "")
    salesperson = order.get("user", "")
    text = f"{state} {city} {name} {oname}"

    # 业务员区域映射（已知划分）
    sp_region = {
        "陈国标": ["福建", "浙江"],
        "王路杨": ["山东", "辽宁", "河北", "天津"],
        "李白羽": ["广东", "广西", "海南"],
        "Chen Mingjin": ["湖南", "江苏", "上海"],
    }
    # 先从文本关键词匹配
    province_map = {
        "福建": ["福建","福州","厦门","宁德","泉州","漳州","莆田","平潭","南平","龙岩","三明","长乐","漳浦","古雷","云霄","东山","福安","溪南","猴屿","狗屿"],
        "浙江": ["浙江","台州","宁波","温州","杭州","舟山","嘉兴","绍兴","金华","玉环","温岭","瑞安","乐清","宁海","下沙","苍南"],
        "江苏": ["江苏","南京","苏州","无锡","常州","南通","泰州","扬州","镇江","徐州","连云港","盐城"],
        "山东": ["山东","青岛","烟台","威海","日照","潍坊","东营","滨州"],
        "广东": ["广东","广州","深圳","珠海","汕头","湛江","茂名","阳江","惠州","东莞","中山","江门","汕尾","潮州"],
        "广西": ["广西","北海","钦州","防城港","南宁"],
        "海南": ["海南","海口","三亚"],
        "上海": ["上海","松江"],
        "湖北": ["湖北","武汉","孝感"],
        "湖南": ["湖南","长沙"],
        "江西": ["江西","南昌","九江"],
        "安徽": ["安徽","安庆","合肥"],
        "辽宁": ["辽宁","大连","沈阳","丹东","锦州","营口","盘锦","葫芦岛"],
        "河北": ["河北","秦皇岛","唐山"],
        "天津": ["天津"],
        "新加坡": ["新加坡","Singapore"],
    }
    for prov, keywords in province_map.items():
        for kw in keywords:
            if kw in text:
                return prov
    # 文本匹配不到，用业务员区域
    if salesperson in sp_region:
        regions = sp_region[salesperson]
        if len(regions) == 1:
            return regions[0]
        return f"{salesperson}区域({'/'.join(regions)})"
    return "未知"

# 产品分类推断
def infer_category(line):
    pname = line.get("name", "").lower()
    pcode = ""
    pid = line.get("product")
    if pid and pid in products:
        pcode = products[pid].get("code", "").lower()
        pcat = products[pid].get("categ", "")
        if pcat: return pcat
    text = f"{pname} {pcode}"
    if any(k in text for k in ["齿轮", "gear", "69g", "69j", "6k7", "6e5", "68v", "6ek", "6fj", "6r5"]):
        return "齿轮组"
    if any(k in text for k in ["轴", "shaft", "drive shaft", "propeller shaft", "45501", "45510"]):
        return "轴类"
    if any(k in text for k in ["油管", "fuel", "hose", "pipe", "管"]):
        return "油管/管路"
    if any(k in text for k in ["螺旋桨", "propeller", "prop", "桨"]):
        return "螺旋桨"
    if any(k in text for k in ["轴承", "bearing", "油封", "seal", "o-ring", "o ring", "垫片", "gasket"]):
        return "轴承/密封件"
    if any(k in text for k in ["活塞", "piston", "环", "ring", "缸", "cylinder", "liner"]):
        return "活塞/缸套"
    if any(k in text for k in ["启动", "starter", "电机", "motor", "线圈", "coil", "cdi", "ecu", "电器", "电"]):
        return "电器件"
    if any(k in text for k in ["水泵", "water pump", "叶轮", "impeller", "节温器", "thermostat"]):
        return "冷却系统"
    if any(k in text for k in ["化油器", "carburetor", "喷油", "injector", "fuel pump"]):
        return "燃油系统"
    if any(k in text for k in ["壳体", "housing", "case", "盖", "cover", "座"]):
        return "壳体/盖类"
    return "其他配件"

# 聚合
by_month = defaultdict(float)
by_region = defaultdict(float)
by_region_month = defaultdict(lambda: defaultdict(float))
by_salesperson = defaultdict(float)
by_category = defaultdict(float)
by_category_region = defaultdict(lambda: defaultdict(float))
by_product = defaultdict(lambda: {"qty": 0, "amount": 0, "name": ""})
region_orders = defaultdict(int)
order_count_month = defaultdict(int)

for o in orders:
    date = o.get("date", "")
    if len(date) >= 7:
        month = date[:7]
    else:
        month = "未知"
    region = infer_region(o)
    salesperson = o.get("user", "未知")
    total = o.get("total", 0) or 0
    
    by_month[month] += total
    by_region[region] += total
    by_region_month[region][month] += total
    by_salesperson[salesperson] += total
    region_orders[region] += 1
    order_count_month[month] += 1

for l in lines:
    if not l.get("order"): continue
    order = next((o for o in orders if o["id"] == l["order"]), None)
    if not order: continue
    region = infer_region(order)
    cat = infer_category(l)
    amt = l.get("subtotal", 0) or 0
    qty = l.get("qty", 0) or 0
    
    by_category[cat] += amt
    by_category_region[cat][region] += amt
    
    pid = l.get("product")
    pname = products.get(pid, {}).get("name", l.get("name", ""))[:50]
    by_product[pid or l["name"][:30]]["qty"] += qty
    by_product[pid or l["name"][:30]]["amount"] += amt
    by_product[pid or l["name"][:30]]["name"] = pname

# 输出结论
print("=" * 60)
print("一、月度销售趋势")
print("=" * 60)
for m in sorted(by_month.keys()):
    if m >= "2026-05":
        print(f"  {m}: ¥{by_month[m]:>10,.0f}  ({order_count_month[m]}单)")

print(f"\n{'='*60}")
print("二、地区销售分布")
print("=" * 60)
for r, amt in sorted(by_region.items(), key=lambda x: -x[1]):
    print(f"  {r:<8} ¥{amt:>10,.0f}  ({region_orders[r]}单)")

print(f"\n{'='*60}")
print("三、销售人员业绩")
print("=" * 60)
for s, amt in sorted(by_salesperson.items(), key=lambda x: -x[1]):
    print(f"  {s:<12} ¥{amt:>10,.0f}")

print(f"\n{'='*60}")
print("四、品类销售")
print("=" * 60)
for c, amt in sorted(by_category.items(), key=lambda x: -x[1]):
    print(f"  {c:<14} ¥{amt:>10,.0f}")

print(f"\n{'='*60}")
print("五、地区×品类交叉")
print("=" * 60)
for cat in sorted(by_category.keys(), key=lambda c: -by_category[c]):
    regions = by_category_region[cat]
    top = sorted(regions.items(), key=lambda x: -x[1])[:3]
    top_str = ", ".join(f"{r}¥{a:,.0f}" for r, a in top if a > 0)
    print(f"  {cat:<14} {top_str}")

print(f"\n{'='*60}")
print("六、畅销产品TOP15")
print("=" * 60)
top_prods = sorted(by_product.values(), key=lambda x: -x["amount"])[:15]
for p in top_prods:
    print(f"  {p['qty']:>5.0f}件 ¥{p['amount']:>9,.0f}  {p['name'][:50]}")

# 保存聚合数据给可视化
viz = {
    "months": sorted([m for m in by_month.keys() if m >= "2026-01"]),
    "by_month": {m: round(by_month[m]) for m in sorted(by_month.keys()) if m >= "2026-01"},
    "by_region": dict(sorted(by_region.items(), key=lambda x: -x[1])),
    "by_salesperson": dict(sorted(by_salesperson.items(), key=lambda x: -x[1])),
    "by_category": dict(sorted(by_category.items(), key=lambda x: -x[1])),
    "by_category_region": {k: dict(v) for k, v in by_category_region.items()},
    "region_orders": dict(region_orders),
    "top_products": [{"name": p["name"], "qty": p["qty"], "amount": round(p["amount"])}
                     for p in top_prods],
}
with open(os.path.join(DIR, "viz_data.json"), "w", encoding="utf-8") as f:
    json.dump(viz, f, ensure_ascii=False, indent=1)
print(f"\n可视化数据已保存: viz_data.json")
