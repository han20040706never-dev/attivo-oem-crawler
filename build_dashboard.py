# -*- coding: utf-8 -*-
"""生成自包含HTML可视化看板，零token查看"""
import json, os

DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(DIR, "viz_data.json"), encoding="utf-8") as f:
    v = json.load(f)

html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AttivoX 销售看板</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0f1923;color:#e0e6ed;font-family:-apple-system,"Microsoft YaHei",sans-serif;padding:20px}
h1{text-align:center;font-size:22px;margin-bottom:20px;color:#4fc3f7}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;max-width:1400px;margin:0 auto}
.card{background:#1a2a3a;border-radius:10px;padding:16px;box-shadow:0 2px 8px rgba(0,0,0,.3)}
.card.full{grid-column:1/-1}
.card h3{font-size:14px;color:#78909c;margin-bottom:8px;font-weight:500}
.chart{width:100%;height:320px}
.kpi-row{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px;max-width:1400px;margin-left:auto;margin-right:auto}
.kpi{background:#1a2a3a;border-radius:10px;padding:16px;text-align:center}
.kpi .num{font-size:28px;font-weight:700;color:#4fc3f7}
.kpi .label{font-size:12px;color:#78909c;margin-top:4px}
@media(max-width:768px){.grid{grid-template-columns:1fr}.kpi-row{grid-template-columns:repeat(2,1fr)}}
</style>
</head>
<body>
<h1>AttivoX 大陆销售看板 (2026.6-8)</h1>
<div class="kpi-row">
<div class="kpi"><div class="num">""" + f'{sum(v["by_month"].values()):,.0f}' + """</div><div class="label">总销售额(元)</div></div>
<div class="kpi"><div class="num">""" + str(sum(v["region_orders"].values())) + """</div><div class="label">订单总数</div></div>
<div class="kpi"><div class="num">""" + str(len(v["by_salesperson"])) + """</div><div class="label">销售人员</div></div>
<div class="kpi"><div class="num">""" + str(len(v["by_category"])) + """</div><div class="label">品类数</div></div>
</div>
<div class="grid">
<div class="card"><h3>月度销售趋势</h3><div id="c1" class="chart"></div></div>
<div class="card"><h3>地区销售占比</h3><div id="c2" class="chart"></div></div>
<div class="card"><h3>销售人员业绩</h3><div id="c3" class="chart"></div></div>
<div class="card"><h3>品类销售占比</h3><div id="c4" class="chart"></div></div>
<div class="card full"><h3>地区×品类交叉分析</h3><div id="c5" class="chart" style="height:400px"></div></div>
<div class="card full"><h3>畅销产品TOP15</h3><div id="c6" class="chart" style="height:450px"></div></div>
</div>
<script>
var D = """ + json.dumps(v, ensure_ascii=False) + """;
var C = ['#4fc3f7','#66bb6a','#ffa726','#ef5350','#ab47bc','#26c6da','#ffca28','#8d6e63'];
function init(id,opt){var c=echarts.init(document.getElementById(id),'dark');c.setOption(opt);window.addEventListener('resize',function(){c.resize()});return c}

init('c1',{backgroundColor:'transparent',tooltip:{trigger:'axis'},grid:{left:60,right:20,top:30,bottom:30,containLabel:true},
 xAxis:{type:'category',data:Object.keys(D.by_month),axisLabel:{color:'#78909c'}},
 yAxis:{type:'value',axisLabel:{color:'#78909c',formatter:function(v){return(v/10000).toFixed(1)+'万'}}},
 series:[{type:'bar',data:Object.values(D.by_month),itemStyle:{color:'#4fc3f7',borderRadius:[4,4,0,0]},
  label:{show:true,position:'top',color:'#e0e6ed',formatter:function(p){return(p.value/10000).toFixed(1)+'万'}}}]});

init('c2',{backgroundColor:'transparent',tooltip:{trigger:'item',formatter:'{b}: ¥{c} ({d}%)'},
 series:[{type:'pie',radius:['40%','70%'],center:['50%','55%'],
  data:Object.entries(D.by_region).map(function(e,i){return{name:e[0],value:Math.round(e[1]),itemStyle:{color:C[i%C.length]}}}),
  label:{color:'#e0e6ed',fontSize:11}}]});

init('c3',{backgroundColor:'transparent',tooltip:{trigger:'axis'},grid:{left:100,right:30,top:20,bottom:30,containLabel:true},
 xAxis:{type:'value',axisLabel:{color:'#78909c',formatter:function(v){return(v/10000).toFixed(1)+'万'}}},
 yAxis:{type:'category',data:Object.keys(D.by_salesperson).reverse(),axisLabel:{color:'#78909c'}},
 series:[{type:'bar',data:Object.values(D.by_salesperson).reverse(),itemStyle:{color:'#66bb6a',borderRadius:[0,4,4,0]}}]});

init('c4',{backgroundColor:'transparent',tooltip:{trigger:'item',formatter:'{b}: ¥{c} ({d}%)'},
 series:[{type:'pie',radius:'65%',center:['50%','55%'],
  data:Object.entries(D.by_category).map(function(e,i){return{name:e[0],value:Math.round(e[1]),itemStyle:{color:C[i%C.length]}}}),
  label:{color:'#e0e6ed',fontSize:11}}]});

var cats=Object.keys(D.by_category),regions=Object.keys(D.by_region);
init('c5',{backgroundColor:'transparent',tooltip:{position:'top'},
 grid:{left:120,right:60,top:10,bottom:80,containLabel:true},
 xAxis:{type:'category',data:regions,axisLabel:{color:'#78909c',rotate:20,fontSize:10}},
 yAxis:{type:'category',data:cats,axisLabel:{color:'#78909c'}},
 visualMap:{min:0,max:15000,calculable:true,orient:'horizontal',left:'center',bottom:0,
  textStyle:{color:'#78909c'},inRange:{color:['#1a2a3a','#4fc3f7','#ffa726','#ef5350']}},
 series:[{type:'heatmap',label:{show:true,color:'#e0e6ed',fontSize:10,formatter:function(p){return p.value[2]>0?(p.value[2]/10000).toFixed(1)+'万':''}},
  data:cats.flatMap(function(c,ci){return regions.map(function(r,ri){return[ri,ci,Math.round((D.by_category_region[c]||{})[r]||0)]})})}]});

init('c6',{backgroundColor:'transparent',tooltip:{trigger:'axis',axisPointer:{type:'shadow'}},
 grid:{left:200,right:60,top:20,bottom:30,containLabel:true},
 xAxis:{type:'value',axisLabel:{color:'#78909c',formatter:function(v){return(v/10000).toFixed(1)+'万'}}},
 yAxis:{type:'category',data:D.top_products.map(function(p){return p.name}).reverse(),axisLabel:{color:'#78909c',fontSize:10,width:180,overflow:'truncate'}},
 series:[{type:'bar',data:D.top_products.map(function(p){return Math.round(p.amount)}).reverse(),
  itemStyle:{color:'#ffa726',borderRadius:[0,4,4,0]},
  label:{show:true,position:'right',color:'#e0e6ed',fontSize:10,formatter:function(p){return'¥'+p.value.toLocaleString()}}}]});
</script>
</body>
</html>"""

out = os.path.join(DIR, "sales_dashboard.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(html)
print(f"看板已生成: {out} ({os.path.getsize(out)//1024}KB)")
