# -*- coding: utf-8 -*-
"""产业趋势组合贝塔研究 —— 集成全部口径到一个 Excel。"""
import openpyxl
import numpy as np
import pandas as pd
from openpyxl.styles import Font, PatternFill, Alignment

F = '产业趋势贝塔研究.xlsx'
wb = openpyxl.load_workbook(F, data_only=True)
ws = wb['Sheet1']
cols = {3: '创业板指', 4: '科创50', 5: '沪深300', 6: '中证500', 7: '中证1000', 8: '中证全指'}
IDX = list(cols.values())
GROWTH = ['创业板指', '科创50']
WIDE = ['沪深300', '中证500', '中证1000', '中证全指']

rows = []
for r in range(3, ws.max_row + 1):
    d = ws.cell(row=r, column=1).value
    if d is None:
        continue
    rows.append([d, ws.cell(row=r, column=2).value] + [ws.cell(row=r, column=c).value for c in cols])
df = pd.DataFrame(rows, columns=['date', '组合'] + IDX)
df['date'] = pd.to_datetime(df['date'])
df = df.sort_values('date').reset_index(drop=True)

rdf = df.copy()
for k in ['组合'] + IDX:
    rdf[k] = rdf[k].pct_change()
rdf = rdf.dropna(subset=['组合']).reset_index(drop=True)

periods = [
    ('全区间', '2024-09-24', '2026-10-23'),
    ('上行-924行情', '2024-09-24', '2024-12-31'),
    ('上行-科技牛市主升浪', '2025-05-01', '2025-11-30'),
    ('上行-科技牛市主升浪2', '2026-04-01', '2026-06-30'),
    ('下行-2025年4月贸易战', '2025-04-01', '2025-04-30'),
    ('下行-2026年3月美伊战争', '2026-03-01', '2026-03-31'),
    ('下行-2026年7-10月科技股大回调', '2026-07-01', '2026-10-23'),
]
DOWN = ['下行-2025年4月贸易战', '下行-2026年3月美伊战争', '下行-2026年7-10月科技股大回调']

def sub_of(name):
    s, e = next((s, e) for n, s, e in periods if n == name)
    return df[(df['date'] >= pd.Timestamp(s)) & (df['date'] <= pd.Timestamp(e))]

def ret_range(sub, col):
    return sub[col].iloc[-1] / sub[col].iloc[0] - 1

def max_drawdown(sub, col):
    s = sub[col].values
    peak = s[0]; md = 0.0
    for v in s:
        if v > peak:
            peak = v
        dd = v / peak - 1
        if dd < md:
            md = dd
    return md

def reg_beta(sub, col):
    rp = sub['组合'].values
    rm = sub[col].values
    m = np.isfinite(rp) & np.isfinite(rm)
    rp, rm = rp[m], rm[m]
    if len(rp) < 3:
        return None
    v = np.var(rm, ddof=1)
    if v == 0:
        return None
    return np.cov(rp, rm, ddof=1)[0, 1] / v

# ---- 样式 ----
hdr_fill = PatternFill('solid', fgColor='D9E1F2')
hdr_font = Font(bold=True)
grow_fill = PatternFill('solid', fgColor='E2EFDA')
title_font = Font(bold=True, size=12)

def style_header(row, ws_):
    for c in row:
        c.fill = hdr_fill
        c.font = hdr_font
        c.alignment = Alignment(horizontal='center')

out = openpyxl.Workbook()

# ============ Sheet 1 区间涨跌幅 ============
o = out.active
o.title = '区间涨跌幅'
o.append(['区间', '起始日', '结束日', '交易日数', '组合涨跌幅'] + IDX)
for name, s, e in periods:
    sub = sub_of(name)
    r = [name, str(sub['date'].iloc[0].date()), str(sub['date'].iloc[-1].date()), len(sub),
         ret_range(sub, '组合')] + [ret_range(sub, k) for k in IDX]
    o.append(r)
style_header(o[1], o)
for row in o.iter_rows(min_row=2, max_row=o.max_row, min_col=5, max_col=11):
    for c in row:
        c.number_format = '+0.00%;-0.00%'
o.column_dimensions['A'].width = 28

# ============ Sheet 2 贝塔-涨跌幅比 ============
o = out.create_sheet('贝塔-涨跌幅比')
o.append(['区间', '组合涨跌幅'] + IDX)
for name, s, e in periods:
    sub = sub_of(name)
    rp = ret_range(sub, '组合')
    r = [name, rp] + [rp / ret_range(sub, k) for k in IDX]
    o.append(r)
style_header(o[1], o)
for row in o.iter_rows(min_row=2, max_row=o.max_row, min_col=2, max_col=2):
    for c in row:
        c.number_format = '+0.00%;-0.00%'
for row in o.iter_rows(min_row=2, max_row=o.max_row, min_col=3, max_col=8):
    for c in row:
        c.number_format = '0.00'
o.column_dimensions['A'].width = 28

# ============ Sheet 3 下跌-最大回撤 ============
o = out.create_sheet('下跌-最大回撤')
o.append(['区间', '组合最大回撤'] + IDX)
for name in DOWN:
    sub = sub_of(name)
    r = [name, max_drawdown(sub, '组合')] + [max_drawdown(sub, k) for k in IDX]
    o.append(r)
style_header(o[1], o)
for row in o.iter_rows(min_row=2, max_row=o.max_row, min_col=2, max_col=8):
    for c in row:
        c.number_format = '+0.00%;-0.00%'
o.column_dimensions['A'].width = 28

# ============ Sheet 4 下跌-回撤比 ============
o = out.create_sheet('下跌-回撤比')
o.append(['区间', '组合最大回撤'] + IDX)
for name in DOWN:
    sub = sub_of(name)
    mdp = max_drawdown(sub, '组合')
    r = [name, mdp] + [mdp / max_drawdown(sub, k) for k in IDX]
    o.append(r)
style_header(o[1], o)
for row in o.iter_rows(min_row=2, max_row=o.max_row, min_col=2, max_col=2):
    for c in row:
        c.number_format = '+0.00%;-0.00%'
for row in o.iter_rows(min_row=2, max_row=o.max_row, min_col=3, max_col=8):
    for c in row:
        c.number_format = '0.00'
o.column_dimensions['A'].width = 28

# ============ Sheet 5 贝塔-回归OLS ============
o = out.create_sheet('贝塔-回归OLS')
o.append(['区间', '交易日数'] + IDX)
for name, s, e in periods:
    sub = sub_of(name)
    rr = rdf[(rdf['date'] >= pd.Timestamp(s)) & (rdf['date'] <= pd.Timestamp(e))]
    r = [name, len(rr)] + [reg_beta(rr, k) for k in IDX]
    o.append(r)
style_header(o[1], o)
for row in o.iter_rows(min_row=2, max_row=o.max_row, min_col=3, max_col=8):
    for c in row:
        c.number_format = '0.000'
o.column_dimensions['A'].width = 28

# ============ Sheet 6 汇总-成长vs宽基 ============
o = out.create_sheet('汇总-成长vs宽基')
o.append(['口径', '成长指数(创业板指+科创50)', '宽基指数(沪深300/中证500/中证1000/中证全指)'])
o.append(['说明', '科创50+创业板指 平均贝塔', '沪深300、中证500、中证1000、中证全指 平均贝塔'])

def avg_beta(period_names, col_list, use_drawdown):
    vals = []
    for name in period_names:
        sub = sub_of(name)
        if use_drawdown:
            mdp = max_drawdown(sub, '组合')
            for k in col_list:
                vals.append(mdp / max_drawdown(sub, k))
        else:
            rp = ret_range(sub, '组合')
            for k in col_list:
                vals.append(rp / ret_range(sub, k))
    return np.mean(vals)

up_names = ['上行-924行情', '上行-科技牛市主升浪', '上行-科技牛市主升浪2']
summary = [
    ('全区间(涨跌幅比)', avg_beta(['全区间'], GROWTH, False), avg_beta(['全区间'], WIDE, False)),
    ('上行区间(涨跌幅比)', avg_beta(up_names, GROWTH, False), avg_beta(up_names, WIDE, False)),
    ('下跌区间(回撤比)', avg_beta(DOWN, GROWTH, True), avg_beta(DOWN, WIDE, True)),
]
for name, g, w in summary:
    o.append([name, g, w])
style_header(o[1], o)
for row in o.iter_rows(min_row=3, max_row=o.max_row, min_col=2, max_col=3):
    for c in row:
        c.number_format = '0.00'
o.column_dimensions['A'].width = 24
o.column_dimensions['B'].width = 30
o.column_dimensions['C'].width = 42

# ============ Sheet 7 说明 ============
o = out.create_sheet('说明')
notes = [
    '数据源：产业趋势贝塔研究.xlsx（组合净值 + 6 指数日度净值，2024-09-24 至 2026-10-23，共 502 个交易日）。',
    '区间涨跌幅 = 期末净值/期初净值 - 1（期初/期末取区间内首/末交易日）。',
    '贝塔-涨跌幅比 = 组合区间涨跌幅 / 指数区间涨跌幅（收益比口径，上行/全区间适用）。',
    '下跌-最大回撤 = 区间内净值自前高回落的最大幅度；下跌-回撤比 = 组合最大回撤 / 指数最大回撤（下跌区间适用，修正 V 型反弹导致的低估）。',
    '贝塔-回归OLS = 组合日收益率对指数日收益率的 OLS 斜率（未扣除无风险利率），作为标准贝塔参考。',
    '指数分类：成长指数 = 创业板指、科创50；宽基指数 = 沪深300、中证500、中证1000、中证全指。',
    '口径约定：全区间/上行用涨跌幅比，下跌用回撤比；宽基高贝塔主要反映组合超额收益(α)而非真实弹性。',
    '主升浪2 按 2026-04~06（原文 202604-202406 疑似笔误）；7-10月大回调数据截至 2026-10-23。',
]
for n in notes:
    o.append([n])
o.column_dimensions['A'].width = 100

out.save('产业趋势贝塔研究_贝塔结果.xlsx')
print('已集成全部口径 → 产业趋势贝塔研究_贝塔结果.xlsx')
print('sheets:', out.sheetnames)
for name, g, w in summary:
    print(f'  {name}: 成长 {g:.2f}, 宽基 {w:.2f}')
