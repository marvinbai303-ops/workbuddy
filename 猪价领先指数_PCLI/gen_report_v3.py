# -*- coding: utf-8 -*-
"""生成 PCLI-Beta v3 升级版交互式报告"""
import json

d = json.load(open('PCLI_v3_result.json', encoding='utf-8'))
rows = d['rows']
summary = d['summary']
csi = d['csi']
hs300 = d['hs300']

# PCLI 完整序列
pcli_months = [r['month'] for r in rows if r['pcli'] is not None]
pcli = [r['pcli'] for r in rows if r['pcli'] is not None]
s1 = [r['s1'] for r in rows if r['pcli'] is not None]
s2 = [r['s2'] for r in rows if r['pcli'] is not None]
s3 = [r['s3'] for r in rows if r['pcli'] is not None]
s4 = [r['s4'] for r in rows if r['pcli'] is not None]
sow_series = [r['sow'] for r in rows if r['pcli'] is not None]

# 中证畜牧 + 相对沪深300（2021-02 起，对齐）
csi_months = sorted(csi.keys())
csi_vals = [round(csi[m],1) for m in csi_months]
hs_vals = [round(hs300[m],1) if m in hs300 else None for m in csi_months]
# 相对强度（比值，基准 100）
rel_strength = []
base = None
for m in csi_months:
    if m in hs300:
        r = csi[m]/hs300[m]
        if base is None: base = r
        rel_strength.append(round(r/base*100, 1))
    else:
        rel_strength.append(None)

# 最新
latest = [r for r in rows if r['pcli'] is not None][-1]
def status(p):
    if p < 55: return 'OFF'
    if p <= 70: return 'WATCH'
    return 'ON'

data_js = json.dumps({
    'pcli_months': pcli_months, 'pcli': pcli, 's1': s1, 's2': s2, 's3': s3, 's4': s4,
    'sow': sow_series,
    'csi_months': csi_months, 'csi': csi_vals, 'rel': rel_strength,
    'summary': summary,
}, ensure_ascii=False)

def fmt(v):
    return '—' if v is None else f"{v['mean']:+.1f}%"

s6abs = summary.get('fwd6_abs', {})
s6rel = summary.get('fwd6_rel', {})
du = summary.get('delta6_rel_up'); dd = summary.get('delta6_rel_down')

html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PCLI-Beta v3 · 五因子定义 + 前瞻性回测</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>
:root{--bg:#f6f7f9;--card:#fff;--ink:#1f2430;--sub:#6b7280;--line:#e5e7eb;--red:#d33a2c;--green:#1a9c63;--blue:#2f6fed;--amber:#e0912f;--purple:#7c5cd6;--teal:#0d9488}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--ink);line-height:1.65;padding:24px}
.wrap{max-width:1120px;margin:0 auto}
h1{font-size:23px;font-weight:700;margin-bottom:4px}
.sub{color:var(--sub);font-size:13px;margin-bottom:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px;margin-bottom:16px}
.card h2{font-size:16px;font-weight:600;margin-bottom:8px}
.card .desc{font-size:12.5px;color:var(--sub);margin-bottom:12px}
.chart{width:100%;height:360px}.chart.tall{height:430px}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left}
th{background:#fafbfc;color:var(--sub);font-weight:600}
td.c{text-align:center}
.badge{display:inline-block;padding:2px 8px;border-radius:6px;font-size:11px;font-weight:600}
.off{background:#e8f5ee;color:var(--green)}.watch{background:#fdf3e3;color:var(--amber)}.on{background:#fdeaea;color:var(--red)}
.formula{background:#f6f8fb;border:1px solid var(--line);border-radius:10px;padding:12px 14px;font-family:ui-monospace,Menlo,monospace;font-size:13px;margin:8px 0;overflow-x:auto}
.warn{background:#fff8e6;border:1px solid #f0d98c;border-radius:10px;padding:12px 14px;font-size:12.5px;color:#7a5b00;margin-top:10px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:14px 0}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px}
.kpi .lab{font-size:12px;color:var(--sub)}.kpi .val{font-size:22px;font-weight:700;margin-top:3px}
.footer{color:var(--sub);font-size:12px;text-align:center;margin-top:20px}
</style>
</head>
<body>
<div class="wrap">
<h1>PCLI-Beta v3 · 五因子定义与前瞻性回测</h1>
<div class="sub">供给领先条件指数（产业层 Beta 过滤器）· 数据源：同花顺 iFinD EDB + Wind EDB + 通达信 · 2026-10-12</div>

<div class="kpis">
  <div class="kpi"><div class="lab">最新 PCLI-Beta（""" + latest['month'] + """）</div><div class="val">""" + f"{latest['pcli']:.1f}" + """ <span class="badge """ + ('watch' if 55<=latest['pcli']<=70 else ('on' if latest['pcli']>70 else 'off')) + """">""" + status(latest['pcli']) + """</span></div></div>
  <div class="kpi"><div class="lab">母猪产能收缩 S1（45%）</div><div class="val">""" + f"{latest['s1']:.0f}" + """</div></div>
  <div class="kpi"><div class="lab">仔猪管线收缩 S2（25%）</div><div class="val">""" + f"{latest['s2']:.0f}" + """</div></div>
  <div class="kpi"><div class="lab">有效供给收缩 S3（20%）</div><div class="val">""" + f"{latest['s3']:.0f}" + """</div></div>
  <div class="kpi"><div class="lab">效率反向修正 S4（10%）</div><div class="val">""" + f"{latest['s4']:.0f}" + """</div></div>
</div>

<div class="card">
<h2>一、五个子因子：计算逻辑、公式、代表含义</h2>
<div class="desc">所有模块信号映射到 0–100（100 = 供给收缩最强）。映射函数统一为 clip(50 − k×同比, 0, 100)，同比下降→高分（S3/S4 变量不同、方向一致）。k 为研究假设斜率。</div>
<table>
<tr><th>因子</th><th class="c">权重</th><th>驱动变量（口径）</th><th>公式</th><th>代表含义</th></tr>
<tr><td><b>S1 母猪产能收缩</b></td><td class="c">45%</td><td>能繁母猪存栏 同比</td><td>clip(50 − 6×能繁YoY)</td><td>远期产能（领先约10个月）去化幅度，母猪↓→高分</td></tr>
<tr><td><b>S2 仔猪管线收缩</b></td><td class="c">25%</td><td>能繁母猪 滞后4月 同比</td><td>clip(50 − 6×能繁<sub>lag4</sub>YoY)</td><td>中期新生仔猪供给（≈4个月前母猪决定）收缩</td></tr>
<tr><td><b>S3 有效供给收缩</b></td><td class="c">20%</td><td>季度官方生猪出栏量 TTM 同比</td><td>clip(50 − 8×出栏TTM YoY)</td><td>当期供给收缩是否兑现（口径干净，替代有偏的屠宰量）</td></tr>
<tr><td><b>S4 效率/体重反向修正</b></td><td class="c">10%</td><td>效率比 = 出栏TTM÷能繁母猪 同比</td><td>clip(50 − 5×效率比YoY)</td><td>扣分项：PSY/体重提升抵消母猪去化的程度，效率↑→低分</td></tr>
<tr><td><b>Stress Index</b></td><td class="c">独立</td><td>自繁自养利润（博亚和讯）</td><td>clip(50 − 0.1×利润)</td><td>养殖亏损压力（去化持续性），不进入 PCLI 主公式</td></tr>
</table>
<div class="formula">PCLI-Beta = 0.45·S1 + 0.25·S2 + 0.20·S3 + 0.10·S4</div>
<div class="warn"><b>⚠️ 关键口径处理</b>：① S3 弃用「定点屠宰量」（其覆盖范围逐年扩大，TTM 同比 3 年 +46% 而官方出栏仅 +6%，严重虚增），改用国家统计局季度出栏量；② 能繁母猪 2020 年监测口径调整（2164→3629 万头），跨口径月份的同比已剔除；③ 能繁母猪 2025-11 起改季度发布，缺口线性插值。全部 k 值、阈值、权重为研究假设，未经无前视回测校准。</div>
</div>

<div class="card">
<h2>二、PCLI-Beta 完整走势（2013 – 2026，月度）</h2>
<div class="desc">红虚线 ON=70、绿虚线 OFF=55。2019 非洲猪瘟 PCLI 冲至 90（强 ON）；2024 年中短暂 ON；2026 年处于 WATCH 上沿。</div>
<div id="c_main" class="chart tall"></div>
</div>

<div class="card">
<h2>三、PCLI vs 中证畜牧（930707）绝对走势</h2>
<div class="desc">左轴 PCLI-Beta，右轴中证畜牧指数点位（2021-02 起，中证畜牧历史序列仅有此区间）。</div>
<div id="c_csi" class="chart tall"></div>
</div>

<div class="card">
<h2>四、中证畜牧相对沪深300超额 vs PCLI</h2>
<div class="desc">右轴为「中证畜牧÷沪深300」相对强度（2021-02=100）。相对强度走弱 = 板块跑输大盘。</div>
<div id="c_rel" class="chart tall"></div>
</div>

<div class="card">
<h2>五、前瞻性回测：PCLI 对中证畜牧的领先意义</h2>
<div class="desc">观察月 PCLI 状态/变化 → 未来 6 个月中证畜牧绝对收益与相对沪深300超额。窗口 2021-02 ~ 2026-09（受中证畜牧历史序列长度限制）。</div>
<div id="c_bt" class="chart"></div>
<table style="margin-top:10px">
<tr><th>分组</th><th class="c">样本</th><th class="c">前瞻6月绝对收益均值</th><th class="c">前瞻6月相对超额均值</th><th class="c">跑赢沪深300概率</th></tr>
<tr><td>OFF（&lt;55）</td><td class="c">""" + str(s6abs.get('OFF',{}).get('n','—')) + """</td><td class="c">""" + fmt(s6abs.get('OFF')) + """</td><td class="c">""" + fmt(s6rel.get('OFF')) + """</td><td class="c">""" + str(s6rel.get('OFF',{}).get('win_rate','—')) + """%</td></tr>
<tr><td>WATCH（55–70）</td><td class="c">""" + str(s6abs.get('WATCH',{}).get('n','—')) + """</td><td class="c">""" + fmt(s6abs.get('WATCH')) + """</td><td class="c">""" + fmt(s6rel.get('WATCH')) + """</td><td class="c">""" + str(s6rel.get('WATCH',{}).get('win_rate','—')) + """%</td></tr>
<tr><td>ON（&gt;70）</td><td class="c">""" + str(s6abs.get('ON',{}).get('n','—')) + """</td><td class="c">""" + fmt(s6abs.get('ON')) + """</td><td class="c">""" + fmt(s6rel.get('ON')) + """</td><td class="c">""" + str(s6rel.get('ON',{}).get('win_rate','—')) + """%</td></tr>
<tr style="border-top:2px solid var(--line)"><td><b>ΔPCLI&gt;0（边际走强）</b></td><td class="c">""" + str(du.get('n','—')) + """</td><td class="c">—</td><td class="c">""" + fmt(du) + """</td><td class="c">""" + str(du.get('win_rate','—')) + """%</td></tr>
<tr><td><b>ΔPCLI&lt;0（边际走弱）</b></td><td class="c">""" + str(dd.get('n','—')) + """</td><td class="c">—</td><td class="c">""" + fmt(dd) + """</td><td class="c">""" + str(dd.get('win_rate','—')) + """%</td></tr>
</table>
<div class="warn"><b>诚实结论</b>：① <b>绝对阈值（&gt;70 就买）无效</b>——ON 状态仅 3 个观察月且前瞻超额全为负，因为 2024 年中恰是「产业去化但股价钝化」的弱样本；② <b>边际变化（ΔPCLI）才有领先意义</b>——PCLI 走强的月份前瞻 6 月跑赢概率 40%，显著高于走弱的 11.1%，超额均值差约 9.6pct。这印证「PCLI 是方向过滤器、非精确择时器」「要交易二阶变化而非绝对水平」。样本量小（受中证畜牧序列长度限制），结论仅供参考。</div>
</div>

<div class="footer">数据源：同花顺 iFinD EDB（能繁母猪/猪价/利润）· Wind EDB（能繁母猪完整历史/季度出栏量）· 通达信（中证畜牧 930707 / 沪深300）· 模型 PCLI-Beta v3 · 2026-10-12</div>
</div>

<script>
const D = """ + data_js + """;
function ln(s,o){return Object.assign({type:'line',smooth:false,symbol:'circle',symbolSize:3,connectNulls:true},o,{data:s});}

(function(){
  const c=echarts.init(document.getElementById('c_main'));
  c.setOption({grid:{left:48,right:20,top:30,bottom:40},tooltip:{trigger:'axis'},legend:{top:0},
    xAxis:{type:'category',data:D.pcli_months,boundaryGap:false},
    yAxis:{type:'value',min:0,max:100,splitLine:{lineStyle:{color:'#eee'}}},
    series:[
      ln(D.pcli,{name:'PCLI-Beta',lineStyle:{color:'#2f6fed',width:2.5},itemStyle:{color:'#2f6fed'},areaStyle:{color:'rgba(47,111,237,0.10)'}}),
      {type:'line',data:[],markLine:{symbol:'none',label:{formatter:'ON 70',position:'end'},data:[{yAxis:70,lineStyle:{color:'#d33a2c',type:'dashed'}}]}},
      {type:'line',data:[],markLine:{symbol:'none',label:{formatter:'OFF 55',position:'end'},data:[{yAxis:55,lineStyle:{color:'#1a9c63',type:'dashed'}}]}}
    ]});
})();

(function(){
  const c=echarts.init(document.getElementById('c_csi'));
  c.setOption({grid:{left:48,right:60,top:30,bottom:40},tooltip:{trigger:'axis'},legend:{top:0},
    xAxis:{type:'category',data:D.csi_months,boundaryGap:false},
    yAxis:[{type:'value',min:0,max:100,position:'left',splitLine:{lineStyle:{color:'#eee'}},name:'PCLI'},
           {type:'value',position:'right',name:'指数点位',splitLine:{show:false}}],
    series:[
      ln(D.pcli.filter((v,i)=>D.pcli_months[i]>='2021-02'),{name:'PCLI-Beta(左)',lineStyle:{color:'#2f6fed',width:2.5},itemStyle:{color:'#2f6fed'}}),
      ln(D.csi,{name:'中证畜牧930707(右)',yAxisIndex:1,lineStyle:{color:'#d33a2c',width:2},itemStyle:{color:'#d33a2c'}})
    ]});
})();

(function(){
  const c=echarts.init(document.getElementById('c_rel'));
  c.setOption({grid:{left:48,right:60,top:30,bottom:40},tooltip:{trigger:'axis'},legend:{top:0},
    xAxis:{type:'category',data:D.csi_months,boundaryGap:false},
    yAxis:[{type:'value',min:0,max:100,position:'left',splitLine:{lineStyle:{color:'#eee'}},name:'PCLI'},
           {type:'value',position:'right',name:'相对强度',splitLine:{show:false}}],
    series:[
      ln(D.pcli.filter((v,i)=>D.pcli_months[i]>='2021-02'),{name:'PCLI-Beta(左)',lineStyle:{color:'#2f6fed',width:2.5},itemStyle:{color:'#2f6fed'}}),
      ln(D.rel,{name:'畜牧÷沪深300(右,2021-02=100)',yAxisIndex:1,lineStyle:{color:'#0d9488',width:2},itemStyle:{color:'#0d9488'}})
    ]});
})();

(function(){
  const c=echarts.init(document.getElementById('c_bt'));
  const groups=['OFF','WATCH','ON','ΔPCLI>0','ΔPCLI<0'];
  const rel=[D.summary.fwd6_rel.OFF.mean, D.summary.fwd6_rel.WATCH.mean, D.summary.fwd6_rel.ON.mean, D.summary.delta6_rel_up.mean, D.summary.delta6_rel_down.mean];
  const win=[D.summary.fwd6_rel.OFF.win_rate, D.summary.fwd6_rel.WATCH.win_rate, D.summary.fwd6_rel.ON.win_rate, D.summary.delta6_rel_up.win_rate, D.summary.delta6_rel_down.win_rate];
  c.setOption({grid:{left:48,right:50,top:40,bottom:40},tooltip:{trigger:'axis'},legend:{top:0},
    xAxis:{type:'category',data:groups},
    yAxis:[{type:'value',position:'left',name:'超额均值%',splitLine:{lineStyle:{color:'#eee'}}},
           {type:'value',position:'right',name:'跑赢概率%',max:100,splitLine:{show:false}}],
    series:[
      {type:'bar',name:'前瞻6月相对超额均值%',data:rel,barWidth:'40%',itemStyle:{color:'#2f6fed'}},
      {type:'line',name:'跑赢概率%(右)',data:win,yAxisIndex:1,lineStyle:{color:'#d33a2c',width:2},itemStyle:{color:'#d33a2c'},symbol:'circle',symbolSize:6}
    ]});
})();

window.addEventListener('resize',()=>{document.querySelectorAll('.chart').forEach(el=>{const c=echarts.getInstanceByDom(el);if(c)c.resize();});});
</script>
</body>
</html>
"""

with open('PCLI_五因子与回测报告.html','w',encoding='utf-8') as f:
    f.write(html)
print("报告已生成：PCLI_五因子与回测报告.html")
print(f"PCLI 数据点 {len(pcli)} 个月，最新 {latest['month']} = {latest['pcli']}（{status(latest['pcli'])}）")
