# -*- coding: utf-8 -*-
"""生成 PCLI-Beta 交互式 HTML 报告"""
import json

with open('PCLI_result.json', encoding='utf-8') as f:
    d = json.load(f)

rows = d['rows']
meta = d['meta']

def num(v, nd=1):
    return None if v is None else round(v, nd)

months = [r['month'] for r in rows]
pcli = [num(r.get('pcli')) for r in rows]
pcli_full = [r.get('pcli_full') for r in rows]
s1 = [num(r.get('s1_sow')) for r in rows]
s2 = [num(r.get('s2_piglet')) for r in rows]
s3 = [num(r.get('s3_supply')) for r in rows]
s4 = [num(r.get('s4_efficiency')) for r in rows]
stress = [num(r.get('stress')) for r in rows]
hog = [num(r.get('hog_price'), 2) for r in rows]
sow_v = [num(r.get('sow')) for r in rows]
slt = [num(r.get('slaughter_ttm')) for r in rows]
profit_v = [num(r.get('profit')) for r in rows]
piglet = [num(r.get('piglet_price'), 2) for r in rows]
yoy_sow = [num(r.get('yoy_sow')) for r in rows]
yoy_hog = [num(r.get('yoy_hog')) for r in rows]

data_js = json.dumps({
    'months': months, 'pcli': pcli, 'pcli_full': pcli_full,
    's1': s1, 's2': s2, 's3': s3, 's4': s4,
    'stress': stress, 'hog': hog, 'sow': sow_v, 'slt': slt,
    'profit': profit_v, 'piglet': piglet, 'yoy_sow': yoy_sow, 'yoy_hog': yoy_hog,
}, ensure_ascii=False)

# 最新值
latest = [r for r in rows if r.get('pcli') is not None][-1]
latest_full = [r for r in rows if r.get('pcli_full')][-1]

# 状态判断函数
def status(p):
    if p is None: return '—'
    if p < 55: return 'OFF'
    if p <= 70: return 'WATCH'
    return 'ON'

html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PCLI-Beta 猪价领先指数 · 走势报告</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>
  :root{
    --bg:#f6f7f9; --card:#ffffff; --ink:#1f2430; --sub:#6b7280;
    --line:#e5e7eb; --red:#d33a2c; --green:#1a9c63; --blue:#2f6fed;
    --amber:#e0912f; --purple:#7c5cd6; --teal:#0d9488;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;background:var(--bg);color:var(--ink);line-height:1.6;padding:24px}
  .wrap{max-width:1120px;margin:0 auto}
  h1{font-size:24px;font-weight:700;margin-bottom:4px}
  .sub{color:var(--sub);font-size:13px;margin-bottom:16px}
  .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:16px 0}
  .kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px}
  .kpi .lab{font-size:12px;color:var(--sub)}
  .kpi .val{font-size:26px;font-weight:700;margin-top:4px}
  .kpi .note{font-size:11px;color:var(--sub);margin-top:2px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px;margin-bottom:16px}
  .card h2{font-size:16px;font-weight:600;margin-bottom:4px}
  .card .desc{font-size:12px;color:var(--sub);margin-bottom:10px}
  .chart{width:100%;height:360px}
  .chart.tall{height:420px}
  table{width:100%;border-collapse:collapse;font-size:12px}
  th,td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
  th{background:#fafbfc;color:var(--sub);font-weight:600;position:sticky;top:0}
  th:first-child,td:first-child{text-align:left}
  .tbl-scroll{max-height:460px;overflow:auto}
  .badge{display:inline-block;padding:2px 8px;border-radius:6px;font-size:11px;font-weight:600}
  .off{background:#e8f5ee;color:var(--green)}
  .watch{background:#fdf3e3;color:var(--amber)}
  .on{background:#fdeaea;color:var(--red)}
  .method{font-size:13px;color:var(--ink)}
  .method li{margin:6px 0 6px 18px}
  .warn{background:#fff8e6;border:1px solid #f0d98c;border-radius:10px;padding:12px 14px;font-size:12.5px;color:#7a5b00;margin-top:8px}
  .footer{color:var(--sub);font-size:12px;text-align:center;margin-top:20px}
</style>
</head>
<body>
<div class="wrap">
  <h1>PCLI-Beta 猪价领先指数 · 走势报告</h1>
  <div class="sub">供给领先条件指数（产业层 Beta 过滤器）· 数据源：同花顺 iFinD EDB（农业农村部 / 博亚和讯）· 抓取日期 2026-10-11</div>

  <div class="kpis">
    <div class="kpi">
      <div class="lab">最新 PCLI-Beta（""" + latest['month'] + """）</div>
      <div class="val">""" + f"{latest['pcli']:.1f}" + """</div>
      <div class="note">状态：<span class="badge """ + ('watch' if 55<=latest['pcli']<=70 else ('on' if latest['pcli']>70 else 'off')) + """">""" + status(latest['pcli']) + """</span></div>
    </div>
    <div class="kpi">
      <div class="lab">母猪产能收缩信号（45%）</div>
      <div class="val">""" + f"{latest['s1_sow']:.0f}" + """</div>
      <div class="note">能繁母猪同比 """ + f"{latest['yoy_sow']:.1f}%" + """</div>
    </div>
    <div class="kpi">
      <div class="lab">仔猪管线收缩信号（25%）</div>
      <div class="val">""" + f"{latest['s2_piglet']:.0f}" + """</div>
      <div class="note">能繁母猪滞后4月同比 """ + f"{latest['yoy_sow_lag4']:.1f}%" + """</div>
    </div>
    <div class="kpi">
      <div class="lab">有效供给收缩信号（20%）</div>
      <div class="val">""" + f"{latest['s3_supply']:.0f}" + """</div>
      <div class="note">生猪价格同比 """ + f"{latest['yoy_hog']:.1f}%" + """</div>
    </div>
    <div class="kpi">
      <div class="lab">Stress Index（养殖压力，独立）</div>
      <div class="val">""" + f"{latest['stress']:.0f}" + """</div>
      <div class="note">自繁自养利润 """ + f"{latest['profit']:.0f}" + """ 元/头</div>
    </div>
  </div>

  <div class="card">
    <h2>PCLI-Beta 综合走势</h2>
    <div class="desc">0–100 分，&lt;55 OFF（回避）· 55–70 WATCH（朦胧区）· &gt;70 ON（产业 Beta 确认）。红色虚线为 70、绿色虚线为 55。</div>
    <div id="c_main" class="chart tall"></div>
  </div>

  <div class="card">
    <h2>四个模块信号分解</h2>
    <div class="desc">母猪产能收缩（45%）· 仔猪管线收缩（25%）· 有效供给收缩（20%）· 效率/体重反向修正（10%）。效率修正为扣分项。</div>
    <div id="c_decomp" class="chart tall"></div>
  </div>

  <div class="card">
    <h2>PCLI vs 生猪价格</h2>
    <div class="desc">左轴 PCLI-Beta，右轴生猪出场价（元/公斤）。有效供给信号用猪价同比（市场出清结果），因此猪价暴涨/暴跌会显著影响 PCLI。</div>
    <div id="c_price" class="chart tall"></div>
  </div>

  <div class="card">
    <h2>能繁母猪存栏 vs 屠宰量（TTM）</h2>
    <div class="desc">左轴能繁母猪存栏（万头，远期产能），右轴定点屠宰企业屠宰量 12 个月滚动合计（万头，仅作当期供给参考，口径逐年扩大）。</div>
    <div id="c_sow" class="chart"></div>
  </div>

  <div class="card">
    <h2>Stress Index 与自繁自养利润</h2>
    <div class="desc">养殖亏损压力单列，用于判断去产能的持续性，不直接等价于“供给已收缩”，故不进入 PCLI 主公式。</div>
    <div id="c_stress" class="chart"></div>
  </div>

  <div class="card">
    <h2>方法论与已知局限</h2>
    <ul class="method">
      <li><b>模型</b>：PCLI-Beta = 0.45×母猪产能收缩 + 0.25×仔猪管线收缩 + 0.20×有效供给收缩 + 0.10×效率/体重反向修正。</li>
      <li><b>信号映射</b>：各模块驱动变量经线性映射到 0–100（100 = 供给收缩最强）。斜率：母猪/仔猪 k=6，猪价 k=2，效率 k=2。均为研究假设参数。</li>
      <li><b>母猪产能</b>：能繁母猪存栏同比（农业农村部）。<b>仔猪管线</b>：能繁母猪滞后 4 个月同比（≈当期新生仔猪供给）。</li>
      <li><b>有效供给</b>：生猪价格同比（口径稳定、市场出清）。<b>效率修正</b>：屠宰量TTM/能繁母猪 的同比。</li>
      <li><b>Stress Index</b>：自繁自养利润（博亚和讯）映射，每亏 100 元/头 +10 分。</li>
    </ul>
    <div class="warn">
      <b>⚠️ 局限与口径提示</b>：① 屠宰量为“定点屠宰企业”口径，覆盖范围逐年扩大，其 TTM 同比（3 年 +46%）显著高于官方生猪出栏（+6%），故屠宰量仅作参考、不进入有效供给信号；② 能繁母猪 2025 年 11 月起由月度改为季度发布，缺口已线性插值（表中以 * 标注）；③ 全部权重、阈值、映射斜率未经无前视回测校准，本报告点位为研究性 Nowcast，不作投资依据。
    </div>
  </div>

  <div class="card">
    <h2>月度明细（可下载 PCLI_result.csv）</h2>
    <div class="tbl-scroll">
      <table>
        <thead><tr>
          <th>月份</th><th>PCLI</th><th>S1母猪</th><th>S2仔猪</th><th>S3供给</th><th>S4效率</th><th>Stress</th>
          <th>能繁(万头)</th><th>能繁YoY%</th><th>猪价(元/kg)</th><th>猪价YoY%</th><th>屠宰TTM(万头)</th><th>利润(元/头)</th>
        </tr></thead>
        <tbody id="tbody"></tbody>
      </table>
    </div>
  </div>

  <div class="footer">数据来源：同花顺 iFinD 宏观行业经济数据库（农业农村部 / 博亚和讯）· 模型：PCLI-Beta 工作版（README.md）· 生成于 2026-10-11</div>
</div>

<script>
const D = """ + data_js + """;

function line(series, opts={}) {
  return Object.assign({type:'line', smooth:false, symbol:'circle', symbolSize:4, connectNulls:true}, opts, {data:series});
}
function axis(name, pos, color, min, max) {
  return {name:name, type:'value', position:pos, min:min, max:max, axisLine:{lineStyle:{color:color}}, axisLabel:{color:color}, splitLine:{show:pos==='left'}};
}

// 主图
(function(){
  const c = echarts.init(document.getElementById('c_main'));
  const band55 = {type:'line', markArea:{silent:true, data:[
    [{yAxis:70,itemStyle:{color:'rgba(211,58,44,0.06)'}},{yAxis:100,itemStyle:{color:'rgba(211,58,44,0.06)'}}],
    [{yAxis:55,itemStyle:{color:'rgba(224,145,47,0.08)'}},{yAxis:70,itemStyle:{color:'rgba(224,145,47,0.08)'}}],
    [{yAxis:0,itemStyle:{color:'rgba(26,156,99,0.05)'}},{yAxis:55,itemStyle:{color:'rgba(26,156,99,0.05)'}}],
  ]}};
  c.setOption({
    grid:{left:50,right:24,top:30,bottom:40},
    tooltip:{trigger:'axis'},
    legend:{data:['PCLI-Beta'],top:0},
    xAxis:{type:'category',data:D.months,boundaryGap:false},
    yAxis:{type:'value',min:0,max:100,splitLine:{lineStyle:{color:'#eee'}}},
    series:[
      line(D.pcli,{name:'PCLI-Beta',lineStyle:{color:'#2f6fed',width:3},itemStyle:{color:'#2f6fed'},areaStyle:{color:'rgba(47,111,237,0.12)'}}),
      {type:'line',name:'ON线(70)',data:[],markLine:{symbol:'none',label:{formatter:'ON 70',position:'end'},data:[{yAxis:70,lineStyle:{color:'#d33a2c',type:'dashed'}}]}},
      {type:'line',name:'OFF线(55)',data:[],markLine:{symbol:'none',label:{formatter:'OFF 55',position:'end'},data:[{yAxis:55,lineStyle:{color:'#1a9c63',type:'dashed'}}]}},
    ]
  });
})();

// 分解图
(function(){
  const c = echarts.init(document.getElementById('c_decomp'));
  c.setOption({
    grid:{left:50,right:24,top:40,bottom:40},
    tooltip:{trigger:'axis'},
    legend:{top:0},
    xAxis:{type:'category',data:D.months,boundaryGap:false},
    yAxis:{type:'value',min:0,max:100,splitLine:{lineStyle:{color:'#eee'}}},
    series:[
      line(D.s1,{name:'S1 母猪产能(45%)',lineStyle:{color:'#d33a2c',width:2.2},itemStyle:{color:'#d33a2c'}}),
      line(D.s2,{name:'S2 仔猪管线(25%)',lineStyle:{color:'#e0912f',width:2.2},itemStyle:{color:'#e0912f'}}),
      line(D.s3,{name:'S3 有效供给(20%)',lineStyle:{color:'#2f6fed',width:2.2},itemStyle:{color:'#2f6fed'}}),
      line(D.s4,{name:'S4 效率修正(10%)',lineStyle:{color:'#7c5cd6',width:2,type:'dashed'},itemStyle:{color:'#7c5cd6'}}),
    ]
  });
})();

// 价格图
(function(){
  const c = echarts.init(document.getElementById('c_price'));
  c.setOption({
    grid:{left:50,right:56,top:40,bottom:40},
    tooltip:{trigger:'axis'},
    legend:{top:0},
    xAxis:{type:'category',data:D.months,boundaryGap:false},
    yAxis:[
      {type:'value',min:0,max:100,splitLine:{lineStyle:{color:'#eee'}},name:'PCLI'},
      {type:'value',min:0,position:'right',name:'元/公斤',splitLine:{show:false}}
    ],
    series:[
      line(D.pcli,{name:'PCLI-Beta(左)',lineStyle:{color:'#2f6fed',width:3},itemStyle:{color:'#2f6fed'},areaStyle:{color:'rgba(47,111,237,0.10)'}}),
      line(D.hog,{name:'生猪价格(右)',yAxisIndex:1,lineStyle:{color:'#d33a2c',width:2},itemStyle:{color:'#d33a2c'}}),
    ]
  });
})();

// 能繁+屠宰
(function(){
  const c = echarts.init(document.getElementById('c_sow'));
  c.setOption({
    grid:{left:56,right:60,top:40,bottom:40},
    tooltip:{trigger:'axis'},
    legend:{top:0},
    xAxis:{type:'category',data:D.months,boundaryGap:false},
    yAxis:[
      {type:'value',min:3600,max:4600,position:'left',name:'能繁(万头)',splitLine:{lineStyle:{color:'#eee'}}},
      {type:'value',min:25000,max:50000,position:'right',name:'屠宰TTM(万头)',splitLine:{show:false}}
    ],
    series:[
      line(D.sow,{name:'能繁母猪存栏(左)',lineStyle:{color:'#1a9c63',width:2.5},itemStyle:{color:'#1a9c63'}}),
      line(D.slt,{name:'屠宰量TTM(右)',yAxisIndex:1,lineStyle:{color:'#6b7280',width:2},itemStyle:{color:'#6b7280'}}),
    ]
  });
})();

// stress
(function(){
  const c = echarts.init(document.getElementById('c_stress'));
  c.setOption({
    grid:{left:50,right:56,top:40,bottom:40},
    tooltip:{trigger:'axis'},
    legend:{top:0},
    xAxis:{type:'category',data:D.months,boundaryGap:false},
    yAxis:[
      {type:'value',min:0,max:100,position:'left',name:'Stress',splitLine:{lineStyle:{color:'#eee'}}},
      {type:'value',position:'right',name:'元/头',splitLine:{show:false}}
    ],
    series:[
      line(D.stress,{name:'Stress Index(左)',lineStyle:{color:'#7c5cd6',width:2.5},itemStyle:{color:'#7c5cd6'},areaStyle:{color:'rgba(124,92,214,0.10)'}}),
      line(D.profit,{name:'自繁自养利润(右)',yAxisIndex:1,lineStyle:{color:'#e0912f',width:2},itemStyle:{color:'#e0912f'}}),
    ]
  });
})();

// 表格
(function(){
  const tbody = document.getElementById('tbody');
  const rev = D.months.map((_,i)=>i).reverse();
  let html = '';
  for(const i of rev){
    const m = D.months[i];
    const star = (m>='2025-11' && ['2025-11','2026-01','2026-02'].includes(m)) ? '*' : '';
    const st = D.pcli[i];
    let bd = '—';
    if(st!==null){ bd = st<55?'<span class="badge off">OFF</span>':(st<=70?'<span class="badge watch">WATCH</span>':'<span class="badge on">ON</span>'); }
    html += '<tr><td>'+m+star+'</td><td><b>'+(st===null?'—':st.toFixed(1))+'</b> '+bd+'</td>'
      +'<td>'+(D.s1[i]===null?'—':D.s1[i].toFixed(0))+'</td>'
      +'<td>'+(D.s2[i]===null?'—':D.s2[i].toFixed(0))+'</td>'
      +'<td>'+(D.s3[i]===null?'—':D.s3[i].toFixed(0))+'</td>'
      +'<td>'+(D.s4[i]===null?'—':D.s4[i].toFixed(0))+'</td>'
      +'<td>'+(D.stress[i]===null?'—':D.stress[i].toFixed(0))+'</td>'
      +'<td>'+(D.sow[i]===null?'—':D.sow[i].toFixed(0))+'</td>'
      +'<td>'+(D.yoy_sow[i]===null?'—':D.yoy_sow[i].toFixed(1)+'%')+'</td>'
      +'<td>'+(D.hog[i]===null?'—':D.hog[i].toFixed(2))+'</td>'
      +'<td>'+(D.yoy_hog[i]===null?'—':D.yoy_hog[i].toFixed(1)+'%')+'</td>'
      +'<td>'+(D.slt[i]===null?'—':D.slt[i].toFixed(0))+'</td>'
      +'<td>'+(D.profit[i]===null?'—':D.profit[i].toFixed(0))+'</td></tr>';
  }
  tbody.innerHTML = html;
})();

window.addEventListener('resize', ()=>{document.querySelectorAll('.chart').forEach(el=>{const c=echarts.getInstanceByDom(el); if(c)c.resize();});});
</script>
</body>
</html>
"""

with open('PCLI_走势报告.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("HTML 报告已生成：PCLI_走势报告.html")
print(f"数据点：{len(months)} 个月，最新 PCLI={latest['pcli']:.1f}（{status(latest['pcli'])}）")
