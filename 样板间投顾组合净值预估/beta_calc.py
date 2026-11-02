# -*- coding: utf-8 -*-
"""产业趋势组合 相对各指数 的分区间 Beta 计算
Beta = Cov(Rp, Rm) / Var(Rm)，即组合日收益率对指数日收益率的 OLS 斜率。
"""
import openpyxl
import numpy as np
import pandas as pd

F = '产业趋势贝塔研究.xlsx'
wb = openpyxl.load_workbook(F, data_only=True)
ws = wb['Sheet1']

dates, port, idx = [], [], {}
cols = {3: '创业板指', 4: '科创50', 5: '沪深300', 6: '中证500', 7: '中证1000', 8: '中证全指'}
for c in cols:
    idx[cols[c]] = []

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

# 日收益率
def ret(s):
    return s.pct_change()

rdf = df.copy()
for k in ['产业趋势'] + list(cols.values()):
    rdf[k] = ret(rdf[k])
rdf = rdf.dropna(subset=['产业趋势']).reset_index(drop=True)

def beta_of(rp, rm):
    """OLS 斜率 beta，并返回相关系数、R2、样本数、年化波动率"""
    m = np.isfinite(rp) & np.isfinite(rm)
    rp, rm = rp[m], rm[m]
    if len(rp) < 3:
        return None
    v = np.var(rm, ddof=1)
    if v == 0:
        return None
    beta = np.cov(rp, rm, ddof=1)[0, 1] / v
    corr = np.corrcoef(rp, rm)[0, 1]
    r2 = corr ** 2
    return beta, corr, r2, len(rp), np.std(rp, ddof=1) * np.sqrt(252), np.std(rm, ddof=1) * np.sqrt(252)

# 区间定义
periods = [
    ('全区间',                 '2024-09-24', '2026-10-23'),
    ('上行-924行情',            '2024-09-24', '2024-12-31'),
    ('上行-科技牛市主升浪',      '2025-05-01', '2025-11-30'),
    ('上行-科技牛市主升浪2',     '2026-04-01', '2026-06-30'),
    ('下行-2025年4月贸易战',    '2025-04-01', '2025-04-30'),
    ('下行-2026年3月美伊战争',  '2026-03-01', '2026-03-31'),
    ('下行-2026年7-10月科技股大回调', '2026-07-01', '2026-10-23'),
]

idx_names = list(cols.values())
print('=' * 110)
print('产业趋势组合 分区间 Beta 系数（Beta = Cov(Rp,Rm)/Var(Rm)，日收益率 OLS 斜率）')
print('=' * 110)
for name, s, e in periods:
    sub = rdf[(rdf['date'] >= pd.Timestamp(s)) & (rdf['date'] <= pd.Timestamp(e))]
    drange = f"{sub['date'].min().date()} ~ {sub['date'].max().date()}"
    print(f"\n### {name}  [{drange}]  N={len(sub)}")
    print(f"{'指数':<10}{'Beta':>9}{'相关系数':>10}{'R²':>8}{'组合年化波动':>13}{'指数年化波动':>13}")
    for k in idx_names:
        res = beta_of(sub['产业趋势'].values, sub[k].values)
        if res is None:
            print(f"{k:<10}  （样本不足）")
            continue
        b, corr, r2, n, volp, volm = res
        print(f"{k:<10}{b:>9.3f}{corr:>10.3f}{r2:>8.3f}{volp:>13.1%}{volm:>13.1%}")
print('=' * 110)
