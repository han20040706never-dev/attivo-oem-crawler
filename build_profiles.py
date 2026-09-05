# -*- coding: utf-8 -*-
"""客户行为态度档案 customer_profile.json 生成器(v2 对齐销售SOP)。
SOP要求字段全覆盖: P4首单14项 / P5D+3收货 / P6D+10使用 / P7-8需求库存 / P9SKU地图 /
P10 1带3 / P12消耗节奏 / P14未复购原因 / P20五个数字。能自动填的自动填, 要问客户的标"待补"。
态度层(temp/trust/concerns/quotes/timeline)由微信记录增量养。"""
import sys, io, os, re, json
from collections import defaultdict, Counter
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
T = r"C:\Users\guobi\Doubao\chats\2026-08-16\new-chat\attivo-odoo-tools"
os.chdir(T)
from datetime import datetime
TODAY = datetime.now().date()

MANUAL = {
 608:("旺","已认可待放量","常态补货:小马力齿轮月耗20-30套,要案例/要货都优先"),
 179:("淡","谨慎观望","宁德养殖崩盘没船修,齿轮没装机;10月海参季前一周再联系,现在别催"),
 301:("平","比价低意向","跟刘航月结多年,有需求按需报价即可,不投入"),
 174:("平","谨慎自测(大代理)","留了67F齿轮装自机测1-2个月,到期主动问测试结果,重点齿轮/高压油泵/叶轮"),
 744:("平","试样验证中","被国产坑过认可品质,跟进促成首单"),
 216:("平","有意深度合作","6折经销档(63D轴6折343);想建闽南中转仓可备2-3万货,谈滞销退换+材质检测背书"),
 602:("平","试样验证中","起初怀疑后已买620元,问装机结果,鲍鱼大户场景推台产"),
 298:("旺","试样验证中","诏安小马力生意最好但店里忙没装机,尽快催装机拿反馈"),
 180:("平","有原厂渠道不迫切","有尤先生4折原厂渠道,只从稀缺件(铃木四冲)切入,维持"),
 708:("旺","已认可待放量","技术权威、习惯5-10套批量,9月新品到货深度合作"),
 810:("平","高度认可台产","二手销量暴跌但只要台产;请他转介绍四川杨文(川黔桂流动修),油管报价单跟进"),
 166:("平","试样验证中","拿了手油泵10个/油管样,问使用反馈;内机为主挂机随缘"),
 255:("平","试样验证中","等8/15开海试60以上件,开海后跟进,自己会贴牌要留意"),
 121:("平","谨慎(只补缺口)","年采尤先生500万,只做他缺的:30高压油泵/后操拉线/新款大马力齿轮"),
 624:("平","谨慎(想换渠道)","想替换刘航、要正规增值税发票,对公报价+开票,转大客户"),
 122:("淡","试样验证中","拿了60齿轮试样,问装机;金穗65折渠道,性价比要够"),
 754:("平","观望(被假台产坑)","蓝包装台产爆齿过,发齐手册报价重建信任"),
 735:("淡(海参季旺)","低价走量试样","拿6-65折走量;现在非海参季没活不催,10月旺季前推;要极致性价比和外观辨识度"),
 156:("淡(10月旺季)","新店备货","刚开店没生意,10月旺季前跟开店首批备货,预算1万+"),
 220:("平","试样验证中","样品轴螺纹小缺陷但认可媲美原厂,问68V驱动轴装机,流水大可培育"),
 228:("平","按需采购","出租业务下滑、二手机外销广东,有维修需求时跟,不压货"),
 703:("旺","已认可复购","平潭旅游钓鱼艇,常态维护+顺带易损件"),
 719:("旺","已认可加码","精品二机、核心件只认原厂,从保养件小批量切,长期稳定"),
 184:("平","低意向(只认原厂)","说台产价高无优势,低成本挂着"),
 688:("平","谨慎(二冲为主)","85曲轴报价跟进,要日本轴承级品质"),
 697:("平","试样验证中","拿了手压泵+60齿轮试样,9月开海后问反馈"),
 168:("淡","谨慎不备货","维修活少、用到才拿,等68V(90/115)齿轮到货再推"),
 594:("平","试样验证中","拿了油管试,问反馈;水星齿轮/油泵是痛点"),
 218:("旺","试样转放量","平潭月修30波箱占70%、旺季,已拿10水泵套+2齿轮,重点跟装机趁热放量"),
 597:("淡","低意向(摆烂)","当地萧条摆烂、滤芯没用,低成本维护"),
 578:("平","试样验证中","油管试用、要300马力低压油泵,问油管反馈+报低压油泵"),
 483:("旺","试样验证中","东山外海高负荷、当场装机测试,尽快要装机结果,优质潜力"),
}
def norm_trust(t):
    if t.startswith("已认可") or t=="试样转放量": return ("稳定放量期","热")
    if t=="有意深度合作": return ("深度洽谈期","热")
    if t=="高度认可台产": return ("认可但需求弱","温")
    if t=="试样验证中" or t=="低价走量试样" or t=="新店备货": return ("试样自测期","温")
    if t.startswith("谨慎") or t=="观望(被假台产坑)": return ("谨慎考察期","平")
    if t=="按需采购": return ("按需维持","平")
    return ("低意向/维持","凉")
TIER=[("张希航","6折"),("林友生","6折"),("林茂念","6折"),("涂先生","6折"),("黄福安","6折"),("赖福洲","6折"),
 ("王为左","6折"),("兴旺","6折"),("陈灿锦","6折"),("阿良","6折"),("晨海","65折"),("季总","65折"),
 ("许先生","65折"),("海狗","65折"),("何勇斌","7折"),("洪先生","7折"),("潘先生","7折"),("何斌","7折"),
 ("郭先生","7折"),("兴洋","7折"),("杨佳胜","75折"),("魏思正","75折"),("张耀航","75折"),("蔡晓峰","75折"),
 ("陈显洪","8折"),("王明营","8折"),("兰先生","零售1.15")]
def tier_of(n):
    for k,v in TIER:
        if k in n: return v
    return ""
def ctype(nm,qty,n):
    if re.search(r"贸易|进出口|批发|转卖|二手|回收",nm): return "二道贩子"
    if re.search(r"商行|经营部|设备|机电|船艇|舷外机|动力|机械|销售|经销",nm): return "经销商"
    if re.search(r"维修|修配|修理|修船|快修|服务|船外机",nm): return "维修师傅"
    if qty>=8 or n>=3: return "维修师傅(行为推断)"
    return "待确认"
# SOP P12 消耗节奏: 快(2-4周)/中(1-2月)/慢(按项目)
def consume_kind(name):
    t=str(name).lower()
    if re.search(r"滤芯|滤|叶轮|油封|o圈|型圈|阳极|碳刷|断路器|断电器|火花塞|impeller|filter|anode|vedação|anel|junta",t): return "快速(2-4周)"
    if re.search(r"齿轮|传动轴|驱动轴|螺旋桨|曲轴|浆轴|桨轴|齿轮箱|波箱|engren|eixo|virabrequim|gear|shaft",t): return "慢速(按维修项目)"
    if re.search(r"水泵|轴承|线圈|燃油|油泵|套件|维修包|bomba|rolamento|kit|bomb",t): return "中等(1-2月)"
    return ""
CROSS=[("叶轮",["水泵维修套件","油封","轴承"]),("水泵",["叶轮","油封","轴承"]),
       ("传动轴",["套齿/齿轮","轴承","油封"]),("驱动轴",["齿轮","轴承","油封"]),
       ("齿轮",["齿轮组成套","轴承","油封"]),("滤芯",["燃油滤","机油滤","油封"])]
def cross_of(names):
    s=set()
    for nm in names:
        for k,v in CROSS:
            if k in str(nm): s.update(v)
    return sorted(s)
def brand_of(code):
    c=str(code)
    if re.match(r"^(0928|154|165|174|151|152|573|575|257)",c): return "铃木"
    if re.match(r"^(26-|47-|35-|8M|88|80|19210)",c): return "水星/本田"
    if re.match(r"^[0-9A-Z]{3,5}-",c): return "雅马哈"
    return ""
def sop_stage(gap, n):
    if n==0: return "未成交"
    if gap<=5: return "D+3确认收货"
    if gap<=14: return "D+7~10确认使用"
    if gap<=35: return "D+15~30摸需求/库存"
    if gap<=60: return "复购跟进期"
    return "60天+沉默激活"

sd=json.load(open("sales_data.json",encoding="utf-8"))
P={int(k):v for k,v in sd["partners"].items()}
byO={o["id"]:o for o in sd["orders"]}
og=defaultdict(list); lg=defaultdict(list)
for o in sd["orders"]: og[o["partner"]].append(o)
for l in sd["lines"]: lg[l["order"]].append(l)

profiles={}
for pid,(boom,trust_raw,point) in MANUAL.items():
    p=P.get(pid,{}); nm=p.get("name","(待补名:%d)"%pid); city=p.get("city","")
    os_=sorted(og.get(pid,[]),key=lambda x:x["date"])
    n=len(os_); amt=round(sum(o["total"] for o in os_))
    allnames=[]; qty=0; first_sku=[]; brands=Counter(); ckinds=Counter()
    for o in os_:
        for l in lg.get(o["id"],[]):
            q=l.get("qty",0) or 0; qty+=q; ln=l.get("name","")
            m=re.search(r"\[([^\]]+)\]",ln); code=m.group(1) if m else ""
            allnames.append(ln)
            b=brand_of(code)
            if b: brands[b]+=1
            ck=consume_kind(ln)
            if ck: ckinds[ck]+=1
            if o==os_[0]: first_sku.append("%s×%g"%(code or ln[:14],q))
    last=os_[-1]["date"] if os_ else ""
    gap=(TODAY-datetime.strptime(last,"%Y-%m-%d").date()).days if last else None
    stage,temp=norm_trust(trust_raw)
    ckmode=ckinds.most_common(1)[0][0] if ckinds else "待问"
    # P9 SKU地图: 买过的件先建条目(已采购✓/需求待问/我方供✓)
    sku_map={}
    seen=set()
    for o in os_:
        for l in lg.get(o["id"],[]):
            m=re.search(r"\[([^\]]+)\]",l.get("name",""))
            if not m: continue
            c=m.group(1)
            if c in seen: continue
            seen.add(c); sku_map[c]={"已采购":"是","有需求":"待问","ATTIVOX供":"是"}
    profiles[str(pid)]={
      # —— P4 首单登记 ——
      "pid":pid,"name":nm,"area":city,
      "contact":"待补","contact_way":"待补(微信/电话)",
      "identity":ctype(nm,qty,n),"usage":"待问(自用维修/批发/转卖)",
      "main_brand":(brands.most_common(1)[0][0] if brands else "待问"),
      "stroke":"待问(2冲/4冲)","main_hp":"待问(主要维修马力段)","focus_machines":"",
      "first_order_sku":first_sku,"other_suppliers":"待问(是否同时采其他品牌/原厂渠道)",
      "focus_price":"待问(高/中/低)","focus_quality":"待问(高/中/低)","focus_delivery":"次日达?",
      # —— P20 五个数字 ——
      "stock_left":"待问(当前还剩多少)","monthly_use":"待问(每月用多少)","runout_date":"待问(预计用完)",
      "main_brand_hp":"待问(主要维修品牌/马力=④)","next_buy_date":"待问(预计下次采购,明确到月)",
      # —— P12 消耗节奏 / P13复购时点 ——
      "consume_type":ckmode,"next_followup":"待设",
      # —— P5/P6/P8 节点状态 ——
      "sop_stage":(sop_stage(gap,n) if gap is not None else "未成交"),
      "receive_status":"待确认(已收/未收/异常)","use_status":"待问(已用/未用+P8的ABCD)","satisfaction":"待问",
      # —— 态度层(微信记录养) ——
      "temp":temp,"temp_trend":"→","trust_stage":stage,"trust_raw":trust_raw,"region_boom":boom,
      "concerns":[],"behavior":[],"quotes":[],
      # —— P9/P10/P14 SKU经营 ——
      "sku_map":sku_map,"cross_sell":cross_of(allnames),"no_rebuy_reason":"",
      # —— 管理 ——
      "price_tier":tier_of(nm),"cur_judge":point,"next_action":"","risk":"",
      "timeline":([{"d":last,"ch":"订单","sum":"累计%d单/%d件/¥%d,末单%s,当前SOP节点:%s"%(n,int(qty),amt,last,sop_stage(gap,n)),"delta":""}] if os_ else []),
      "source":"b2b_ledger精读备注+sales_data自动,v2对齐SOP 2026-09-05","updated":"2026-09-05"}
json.dump({"_schema":"客户档案(对齐销售复购SOP): 基础/机型/五个数字/消耗节奏/SOP节点状态/态度层(temp信任,微信记录养)/SKU地图1带3/管理。'待问/待补'=下次要向客户问清的字段,微信记录回来即填","profiles":profiles},
   open("customer_profile.json","w",encoding="utf-8"),ensure_ascii=False,indent=1)
print("v2建档",len(profiles),"户")
miss=Counter()
for v in profiles.values():
    for k,x in v.items():
        if isinstance(x,str) and x.startswith(("待问","待补","待设","待确认")): miss[k]+=1
print("待问字段Top(=下次要补的SOP信息):")
for k,c in miss.most_common(12): print("  %-16s %d户缺"%(k,c))
