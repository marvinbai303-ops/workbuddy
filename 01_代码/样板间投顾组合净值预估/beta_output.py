# -*- coding: utf-8 -*-
"""输出 Beta 结果到 xlsx + json，供可视化与交付使用。"""
import openpyxl
import numpy as np
import pandas as pd
import json

F = '产业趋势贝塔研究.xlsx'
wb = openpyxl.load_workbook(F, data_only=True)
ws = wb['Sheet1']
cols = {3: '创业板指', 4: '科创50', 5: '沪深300', 6: '中证500', 7: '中证1000', 8: '中证全指'}
dates, port, idx = [], [], {c: [] for c in cols.values()}
for r in range(3, ws.max_row + 1):
    d = ws.cell(row=r, column=1).value
    if d is None:
        continue
    dates.append(d)
    port.append(ws.cell(row=r, column=2).value)
    for c in cols:
        idx[cols[c]].append(ws.cell(row=r, column=c).value)

df = pd.DataFrame({'date': dates, '产业趋势': port})
for k in cols.values():
    df[k] = idx[k]
df['date'] = pd.to_datetime(df['date'])
df = df.sort_values('date').reset_index(drop=True)
rdf = df.copy()
for k in ['产业趋势'] + list(cols.values()):
    rdf[k] = rdf[k].pct_change()
rdf = rdf.dropna(subset=['产业趋势']).reset_index(drop=True)

def beta_of(rp, rm):
    m = np.isfinite(rp) & np.isfinite(rm)
    rp, rm = rp[m], rm[m]
    if len(rp) < 3:
        return None
    v = np.var(rm, ddof=1)
    if v == 0:
        return None
    beta = np.cov(rp, rm, ddof=1)[0, 1] / v
    corr = np.corrcoef(rp, rm)[0, 1]
    return beta, corr, corr ** 2, len(rp)

periods = [
    ('全区间', '2024-09-24', '2026-10-23'),
    ('上行-924行情', '2024-09-24', '2024-12-31'),
    ('上行-科技牛市主升浪', '2025-05-01', '2025-11-30'),
    ('上行-科技牛市主升浪2', '2026-04-01', '2026-06-30'),
    ('下行-2025年4月贸易战', '2025-04-01', '2025-04-30'),
    ('下行-2026年3月美伊战争', '2026-03-01', '2026-03-31'),
    ('下行-2026年7-10月科技股大回调', '2026-07-01', '2026-10-23'),
]
idx_names = list(cols.values())

# 组装结果
rows = []  # 每行: 区间名, 起止, N, {指数: beta}
json_out = {'periods': []}
for name, s, e in periods:
    sub = rdf[(rdf['date'] >= pd.Timestamp(s)) & (rdf['date'] <= pd.Timestamp(e))]
    rec = {'name': name, 'start': str(sub['date'].min().date()), 'end': str(sub['date'].max().date()),
           'n': int(len(sub)), 'beta': {}}
    for k in idx_names:
        res = beta_of(sub['产业趋势'].values, sub[k].values)
        rec['beta'][k] = None if res is None else round(float(res[0]), 3)
    json_out['periods'].append(rec)

with open('beta_result.json', 'w', encoding='utf-8') as f:
    json.dump(json_out, f, ensure_ascii=False, indent=2)

# 写 xlsx
out = openpyxl.Workbook()
o = out.active
o.title = '贝塔结果'
header = ['区间', '起始日', '结束日', '样本数'] + idx_names
o.append(header)
for p in json_out['periods']:
    o.append([p['name'], p['start'], p['end'], p['n']] + [p['beta'][k] for k in idx_names])

# 加一行"全区间相关性"备注 sheet
o2 = out.create_sheet('说明')
notes = [
    'Beta = Cov(Rp,Rm)/Var(Rm)，即组合日收益率对指数日收益率的 OLS 斜率（未扣除无风险利率）。',
    '组合：产业趋势（B 列净值）；指数：创业板指/科创50/沪深300/中证500/中证1000/中证全指。',
    '数据区间：2024-09-24 至 2026-10-23（共 502 个交易日，502-1=501 个日收益样本）。',
    '科技牛市主升浪2 原文为 202604-202406（疑似笔误），已按 2026-04 至 2026-06 处理。',
    '2026年7-10月科技股大回调 数据截至 2026-10-23。',
    '提示：Beta 同时受相关性(X)与相对波动(σp/σm)影响；判断"哪个指数最能解释组合"应看相关性/R²，而非仅看 Beta。',
]
for n in notes:
    o2.append([n])

out.save('产业趋势贝塔研究_贝塔结果.xlsx')
print('已写入 产业趋势贝塔研究_贝塔结果.xlsx')
print(json.dumps(json_out, ensure_ascii=False, indent=2))
