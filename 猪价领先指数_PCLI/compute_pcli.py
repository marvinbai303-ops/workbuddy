# -*- coding: utf-8 -*-
"""
PCLI-Beta 猪价领先指数 计算脚本 (v2)
数据来源：同花顺 iFinD 宏观行业经济数据库（EDB），通过 ifind-mcp 抓取，2026-10-11
模型：README.md「PCLI-Beta 工作版」
  PCLI-Beta = 0.45*母猪产能收缩 + 0.25*仔猪管线收缩 + 0.20*有效供给收缩 + 0.10*效率/体重反向修正

v2 关键修正（相对 v1）：
  1. 有效供给信号改用「生猪价格同比」（农业农村部口径稳定、市场出清），
     弃用屠宰量 TTM 同比——因其为“定点屠宰企业”口径、覆盖范围逐年扩大，
     3 年 TTM +46% 而官方出栏仅 +6%，存在严重口径虚增。
  2. 效率反向修正改用效率比(屠宰量TTM/能繁母猪)同比，但 k 调小至 2，缓解口径放大。
  3. 窗口提前至 2022-09（猪价 YoY 可算）。
标准化为研究假设参数，所有阈值/权重均未经过无前视回测校准。
"""
import json, csv
from datetime import datetime

# ============ 原始数据（月度，来自 iFinD EDB） ============
sow = {
"2021-02":4249,"2021-03":4318,"2021-04":4365,"2021-05":4400,"2021-06":4564,"2021-07":4541,
"2021-08":4500,"2021-09":4459,"2021-10":4348,"2021-11":4296,"2021-12":4329,
"2022-01":4290,"2022-02":4268,"2022-03":4185,"2022-04":4177,"2022-05":4192,"2022-06":4277,
"2022-07":4298,"2022-08":4324,"2022-09":4362,"2022-10":4379,"2022-11":4388,"2022-12":4390,
"2023-01":4367,"2023-02":4343,"2023-03":4305,"2023-04":4284,"2023-05":4258,"2023-06":4296,
"2023-07":4271,"2023-08":4241,"2023-09":4240,"2023-10":4210,"2023-11":4158,"2023-12":4142,
"2024-01":4067,"2024-02":4042,"2024-03":3992,"2024-04":3986,"2024-05":3996,"2024-06":4038,
"2024-07":4041,"2024-08":4036,"2024-09":4062,"2024-10":4073,"2024-11":4080,"2024-12":4078,
"2025-01":4062,"2025-02":4066,"2025-03":4039,"2025-04":4038,"2025-05":4042,"2025-06":4043,
"2025-07":4042,"2025-08":4038,"2025-09":4035,"2025-10":3990,"2025-12":3961,
"2026-03":3904,"2026-06":3780,
}
slaughter = {
"2021-09":2509.0,"2021-10":3023.45,"2021-11":2649.0,"2021-12":2896.0,
"2022-01":2847.42,"2022-02":1568.0,"2022-03":2590.0,"2022-04":2738.0,"2022-05":2530.0,"2022-06":2413.0,
"2022-07":2119.0,"2022-08":2167.0,"2022-09":2109.0,"2022-10":2097.0,"2022-11":2269.0,"2022-12":3090.0,
"2023-01":2897.0,"2023-02":2260.0,"2023-03":2669.0,"2023-04":2863.0,"2023-05":2807.0,"2023-06":2647.0,
"2023-07":2684.0,"2023-08":2645.0,"2023-09":2775.0,"2023-10":2867.0,"2023-11":3280.0,"2023-12":3978.0,
"2024-01":3725.0,"2024-02":2104.0,"2024-03":2545.0,"2024-04":2563.0,"2024-05":2666.0,"2024-06":2431.0,
"2024-07":2428.0,"2024-08":2442.0,"2024-09":2640.0,"2024-10":2876.0,"2024-11":3190.0,"2024-12":4162.0,
"2025-01":3816.0,"2025-02":2177.0,"2025-03":3063.0,"2025-04":3077.0,"2025-05":3216.0,"2025-06":3006.0,
"2025-07":3166.0,"2025-08":3350.0,"2025-09":3584.0,"2025-10":3834.0,"2025-11":3957.0,"2025-12":4891.0,
"2026-01":4404.0,"2026-02":3177.0,"2026-03":3514.0,"2026-04":3898.0,"2026-05":3912.0,"2026-06":3820.0,
"2026-07":3610.0,"2026-08":3755.0,
}
piglet_price = {
"2021-09":30.47,"2021-10":23.25,"2021-11":26.27,"2021-12":27.98,
"2022-01":26.55,"2022-02":25.41,"2022-03":24.32,"2022-04":25.77,"2022-05":31.55,"2022-06":35.80,
"2022-07":43.99,"2022-08":44.61,"2022-09":44.16,"2022-10":45.62,"2022-11":46.03,"2022-12":41.00,
"2023-01":34.86,"2023-02":34.06,"2023-03":37.72,"2023-04":36.89,"2023-05":36.55,"2023-06":34.97,
"2023-07":31.88,"2023-08":32.82,"2023-09":31.40,"2023-10":27.53,"2023-11":24.24,"2023-12":23.26,
"2024-01":23.22,"2024-02":28.23,"2024-03":32.11,"2024-04":36.73,"2024-05":38.27,"2024-06":43.58,
"2024-07":43.92,"2024-08":44.27,"2024-09":41.45,"2024-10":36.37,"2024-11":34.42,"2024-12":33.17,
"2025-01":33.97,"2025-02":36.21,"2025-03":37.24,"2025-04":39.07,"2025-05":39.14,"2025-06":37.25,
"2025-07":35.73,"2025-08":33.63,"2025-09":30.06,"2025-10":25.80,"2025-11":24.25,"2025-12":23.39,
"2026-01":23.93,"2026-02":27.57,"2026-03":26.49,"2026-04":23.50,"2026-05":23.35,"2026-06":22.54,
"2026-07":22.64,"2026-08":22.04,
}
hog_price = {
"2021-09":13.89,"2021-10":14.32,"2021-11":17.88,"2021-12":17.95,
"2022-01":15.88,"2022-02":14.16,"2022-03":13.34,"2022-04":14.06,"2022-05":15.92,"2022-06":17.15,
"2022-07":22.55,"2022-08":22.32,"2022-09":24.12,"2022-10":27.39,"2022-11":25.70,"2022-12":20.93,
"2023-01":16.83,"2023-02":14.90,"2023-03":15.54,"2023-04":14.61,"2023-05":14.47,"2023-06":14.30,
"2023-07":14.26,"2023-08":17.11,"2023-09":16.76,"2023-10":15.78,"2023-11":14.99,"2023-12":14.69,
"2024-01":14.63,"2024-02":14.97,"2024-03":14.85,"2024-04":15.38,"2024-05":15.78,"2024-06":18.36,
"2024-07":18.93,"2024-08":20.63,"2024-09":19.68,"2024-10":18.14,"2024-11":17.20,"2024-12":16.46,
"2025-01":16.41,"2025-02":15.77,"2025-03":15.20,"2025-04":15.06,"2025-05":14.92,"2025-06":14.57,
"2025-07":14.84,"2025-08":14.23,"2025-09":13.78,"2025-10":12.27,"2025-11":12.33,"2025-12":11.99,
"2026-01":13.10,"2026-02":12.54,"2026-03":10.59,"2026-04":9.58,"2026-05":9.80,"2026-06":9.71,
"2026-07":10.77,"2026-08":11.01,
}
profit = {
"2021-10":-481.85,"2021-11":82.37,"2021-12":39.71,
"2022-01":-248.64,"2022-02":-405.41,"2022-03":-524.00,"2022-04":-424.22,"2022-05":-200.50,"2022-06":-57.89,
"2022-07":574.26,"2022-08":517.50,"2022-09":734.08,"2022-10":1093.91,"2022-11":853.16,"2022-12":249.76,
"2023-01":-258.51,"2023-02":-337.01,"2023-03":-226.60,"2023-04":-336.47,"2023-05":-327.36,"2023-06":-314.50,
"2023-07":-336.50,"2023-08":22.73,"2023-09":-22.92,"2023-10":-139.13,"2023-11":-232.94,"2023-12":-238.50,
"2024-01":-245.26,"2024-02":-119.17,"2024-03":-145.83,"2024-04":-36.34,"2024-05":30.87,"2024-06":376.17,
"2024-07":404.58,"2024-08":636.58,"2024-09":484.84,"2024-10":313.75,"2024-11":207.96,"2024-12":151.77,
"2025-01":165.76,"2025-02":70.17,"2025-03":39.48,"2025-04":69.44,"2025-05":61.69,"2025-06":24.21,
"2025-07":101.66,"2025-08":35.98,"2025-09":-7.26,"2025-10":-169.60,"2025-11":-120.69,"2025-12":-148.33,
"2026-01":7.33,"2026-02":-92.72,"2026-03":-290.77,"2026-04":-378.51,"2026-05":-338.23,"2026-06":-345.97,
"2026-07":-209.02,"2026-08":-195.14,"2026-09":-198.47,
}

# ============ 工具 ============
def months_range(start, end):
    out = []
    y, m = map(int, start.split('-')); ey, em = map(int, end.split('-'))
    while (y, m) <= (ey, em):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13: m = 1; y += 1
    return out

def shift_month(m, k):
    y, mo = map(int, m.split('-'))
    idx = y * 12 + (mo - 1) + k
    return f"{idx//12:04d}-{idx%12+1:02d}"

def month_index(m):
    y, mo = map(int, m.split('-'))
    return y*12 + (mo-1)

def clip(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, x))

def fill_sow(sow):
    allm = sorted(sow.keys()); full = months_range(allm[0], allm[-1])
    filled = {}; status = {}
    for m in full:
        if m in sow: filled[m] = sow[m]; status[m] = 'official'
    keys = sorted(filled.keys())
    for m in full:
        if m in filled: continue
        prev_m = next((mm for mm in reversed(keys) if mm < m), None)
        next_m = next((mm for mm in keys if mm > m), None)
        if prev_m and next_m:
            d0 = month_index(m)-month_index(prev_m); d1 = month_index(next_m)-month_index(m)
            filled[m] = filled[prev_m] + (filled[next_m]-filled[prev_m])*d0/(d0+d1)
            status[m] = 'interp'
        elif prev_m:
            filled[m] = filled[prev_m]; status[m] = 'ffill'
        elif next_m:
            filled[m] = filled[next_m]; status[m] = 'bfill'
    return filled, status

# ============ 参数 ============
W = [0.45, 0.25, 0.20, 0.10]           # 权重
K_SOW, K_PIGLET, K_HOG, K_EFF = 6.0, 6.0, 2.0, 2.0   # 映射斜率

sow_f, sow_status = fill_sow(sow)

rows = []
months = sorted(set(hog_price.keys()) | set(sow_f.keys()))
for m in months:
    if m not in sow_f or m not in hog_price:
        continue
    row = {'month': m, 'sow_status': sow_status.get(m,'')}
    sow_v = sow_f[m]
    row['sow'] = round(sow_v, 2)
    row['slaughter'] = slaughter.get(m)
    row['hog_price'] = hog_price[m]
    row['piglet_price'] = piglet_price.get(m)
    row['profit'] = profit.get(m)

    # S1: 能繁母猪 YoY
    m12 = shift_month(m, -12)
    yoy_sow = (sow_v/sow_f[m12]-1)*100 if m12 in sow_f else None
    row['yoy_sow'] = round(yoy_sow,2) if yoy_sow is not None else None

    # S2: 能繁母猪 lag4 YoY（当期新生仔猪供给代理）
    ml4 = shift_month(m,-4); ml16 = shift_month(m,-16)
    yoy_sow_l4 = (sow_f[ml4]/sow_f[ml16]-1)*100 if (ml4 in sow_f and ml16 in sow_f) else None
    row['yoy_sow_lag4'] = round(yoy_sow_l4,2) if yoy_sow_l4 is not None else None

    # S3: 生猪价格 YoY（有效供给的市场出清代理）
    yoy_hog = (hog_price[m]/hog_price[m12]-1)*100 if m12 in hog_price else None
    row['yoy_hog'] = round(yoy_hog,2) if yoy_hog is not None else None

    # 屠宰量 TTM 及效率比（S4 用，参考用）
    m_prev12 = shift_month(m,-11); m_ttm12 = shift_month(m,-12)
    ttm = None; yoy_sl = None; eff = None; yoy_eff = None
    if all(mm in slaughter for mm in months_range(m_prev12, m)) and all(mm in slaughter for mm in months_range(shift_month(m_ttm12,-11), m_ttm12)):
        ttm = sum(slaughter[mm] for mm in months_range(m_prev12, m))
        ttm_prev = sum(slaughter[mm] for mm in months_range(shift_month(m_ttm12,-11), m_ttm12))
        yoy_sl = (ttm/ttm_prev-1)*100
        eff = ttm/sow_v
        if m12 in sow_f:
            yoy_eff = (eff/(ttm_prev/sow_f[m12])-1)*100
    row['slaughter_ttm'] = round(ttm,0) if ttm else None
    row['yoy_slaughter_ttm'] = round(yoy_sl,2) if yoy_sl is not None else None
    row['efficiency'] = round(eff,2) if eff else None
    row['yoy_efficiency'] = round(yoy_eff,2) if yoy_eff is not None else None

    # 模块信号
    s1 = clip(50 - K_SOW*yoy_sow) if yoy_sow is not None else None
    s2 = clip(50 - K_PIGLET*yoy_sow_l4) if yoy_sow_l4 is not None else None
    s3 = clip(50 + K_HOG*yoy_hog) if yoy_hog is not None else None
    s4 = clip(50 - K_EFF*yoy_eff) if yoy_eff is not None else None
    row['s1_sow'] = round(s1,2) if s1 is not None else None
    row['s2_piglet'] = round(s2,2) if s2 is not None else None
    row['s3_supply'] = round(s3,2) if s3 is not None else None
    row['s4_efficiency'] = round(s4,2) if s4 is not None else None

    # PCLI-Beta 加权（S4 缺失时前三项归一化）
    comps = [s1, s2, s3, s4]
    if s1 is not None and s2 is not None and s3 is not None:
        if s4 is not None:
            pcli = sum(w*c for w,c in zip(W, comps))
            row['pcli'] = round(pcli,2); row['pcli_full'] = True
        else:
            w3 = [W[0], W[1], W[2]]
            ws = [w/sum(w3) for w in w3]
            pcli = sum(w*c for w,c in zip(ws, comps[:3]))
            row['pcli'] = round(pcli,2); row['pcli_full'] = False
    else:
        row['pcli'] = None; row['pcli_full'] = None

    # Stress Index
    pr = row['profit']
    row['stress'] = round(clip(50 - pr*0.1),2) if pr is not None else None

    rows.append(row)

rows.sort(key=lambda r: r['month'])

# ============ 输出 CSV ============
cols = ['month','pcli','pcli_full','s1_sow','s2_piglet','s3_supply','s4_efficiency','stress',
        'sow','yoy_sow','yoy_sow_lag4','hog_price','yoy_hog','slaughter','slaughter_ttm',
        'yoy_slaughter_ttm','efficiency','yoy_efficiency','piglet_price','profit','sow_status']
with open('PCLI_result.csv','w',newline='',encoding='utf-8-sig') as f:
    w = csv.writer(f); w.writerow(cols)
    for r in rows: w.writerow([r.get(c,'') for c in cols])

# ============ 输出 JSON ============
out = {
  'rows': rows,
  'meta': {
    'model': 'PCLI-Beta 工作版 (v2)',
    'weights': {'母猪产能收缩':0.45,'仔猪管线收缩':0.25,'有效供给收缩':0.20,'效率/体重反向修正':0.10},
    'k_params': {'sow':6.0,'piglet':6.0,'hog':2.0,'efficiency':2.0},
    'signal_defs': {
      's1': '能繁母猪存栏同比↓ → 高分（远期产能收缩）',
      's2': '能繁母猪滞后4个月同比↓ → 高分（当期新生仔猪供给收缩）',
      's3': '生猪价格同比↑ → 高分（有效供给收缩的市场出清确认）',
      's4': '效率比(屠宰量TTM/能繁)同比↑ → 低分（效率抵消母猪去化，反向扣分）',
    },
    'thresholds': {'off':55,'watch_hi':70},
    'sources': {
      '能繁母猪存栏':'农业农村部，月度（2025年起季度化，缺口线性插值）',
      '屠宰量':'农业农村部，月度（定点企业口径，覆盖范围逐年扩大，仅作参考）',
      '仔猪价格':'农业农村部，月度',
      '生猪价格':'农业农村部，月度',
      '自繁自养利润':'博亚和讯，月度',
    },
    'fetched':'2026-10-11 via 同花顺iFinD EDB',
  }
}
with open('PCLI_result.json','w',encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

# ============ 控制台摘要 ============
valid = [r for r in rows if r['pcli'] is not None]
full = [r for r in rows if r.get('pcli_full')]
print(f"月度记录 {len(rows)} 条；PCLI 可算 {len(valid)} 个月（其中四模块完整 {len(full)} 个月）")
if valid:
    print(f"窗口：{valid[0]['month']} ~ {valid[-1]['month']}")
    latest = valid[-1]
    print(f"\n最新（{latest['month']}）：PCLI-Beta = {latest['pcli']}")
    print(f"  S1 母猪产能={latest['s1_sow']} (能繁YoY {latest['yoy_sow']}%)")
    print(f"  S2 仔猪管线={latest['s2_piglet']} (能繁lag4YoY {latest['yoy_sow_lag4']}%)")
    print(f"  S3 有效供给={latest['s3_supply']} (猪价YoY {latest['yoy_hog']}%)")
    print(f"  S4 效率修正={latest['s4_efficiency']} (效率比YoY {latest['yoy_efficiency']}%)")
    print(f"  Stress={latest['stress']} (自繁自养利润 {latest['profit']} 元/头)")
    def f(v): return '--' if v is None else f"{v:5.1f}"
    print("\n关键拐点 PCLI：")
    for ym in ['2022-10','2023-06','2024-04','2024-12','2025-06','2026-03','2026-06']:
        r = next((x for x in rows if x['month']==ym), None)
        if r and r['pcli'] is not None:
            print(f"  {ym}: PCLI={f(r['pcli'])}  S1={f(r['s1_sow'])} S2={f(r['s2_piglet'])} S3={f(r['s3_supply'])} S4={f(r['s4_efficiency'])}")
    print("\n最近12个月 PCLI：")
    for r in valid[-12:]:
        print(f"  {r['month']}: PCLI={f(r['pcli'])}  S1={f(r['s1_sow'])} S2={f(r['s2_piglet'])} S3={f(r['s3_supply'])} S4={f(r['s4_efficiency'])}  Stress={f(r['stress'])}")
