# -*- coding: utf-8 -*-
"""简单贝塔（收益比口径）：区间贝塔 = 组合区间涨跌幅 / 指数区间涨跌幅。"""
import openpyxl
import pandas as pd

F = '产业趋势贝塔研究.xlsx'
wb = openpyxl.load_workbook(F, data_only=True)
ws = wb['Sheet1']
cols = {3: '创业板指', 4: '科创50', 5: '沪深300', 6: '中证500', 7: '中证1000', 8: '中证全指'}
dates, port, idx = [], [], {c: [] for c in cols.values()}
for r in range(3, ws.max_row + 1):
    d = ws.cell(row=r, column=1).value
    if d is None:
        continue
    dates.append(d); port.append(ws.cell(row=r, column=2).value)
    for c in cols:
        idx[cols[c]].append(ws.cell(row=r, column=c).value)
df = pd.DataFrame({'date': dates, '产业趋势': port})
for k in cols.values():
    df[k] = idx[k]
df['date'] = pd.to_datetime(df['date'])
df = df.sort_values('date').reset_index(drop=True)

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

def pct(v):
    return f'{v:+.2%}'

# sheet1: 涨跌幅明细
data = []
for name, s, e in periods:
    sub = df[(df['date'] >= pd.Timestamp(s)) & (df['date'] <= pd.Timestamp(e))]
    p0, p1 = sub['产业趋势'].iloc[0], sub['产业趋势'].iloc[-1]
    row = [name, str(sub['date'].iloc[0].date()), str(sub['date'].iloc[-1].date()), len(sub), p1 / p0 - 1]
    for k in idx_names:
        i0, i1 = sub[k].iloc[0], sub[k].iloc[-1]
        row.append(i1 / i0 - 1)
    data.append(row)

out = openpyxl.Workbook()
o = out.active
o.title = '区间涨跌幅'
o.append(['区间', '起始日', '结束日', '交易日数', '组合涨跌幅'] + idx_names)
for row in data:
    o.append([row[0], row[1], row[2], row[3]] + [pct(x) for x in row[4:]])

# sheet2: 简单贝塔 = 组合/指数
o2 = out.create_sheet('简单贝塔-组合除指数')
o2.append(['区间', '组合涨跌幅'] + idx_names)
for row in data:
    rp = row[4]
    o2.append([row[0], pct(rp)] + [pct(rp / x) if abs(x) > 1e-12 else 'N/A' for x in row[5:]])

# sheet3: 说明
o3 = out.create_sheet('说明')
notes = [
    '简单贝塔 = 组合区间涨跌幅 / 指数区间涨跌幅（收益比口径，非回归斜率）。',
    '涨跌幅 = 期末净值/期初净值 - 1，期初/期末取区间内首个/末个交易日净值。',
    '组合：产业趋势；指数：创业板指/科创50/沪深300/中证500/中证1000/中证全指。',
    '数据区间：2024-09-24 至 2026-10-23。',
    '主升浪2 按 2026-04~06（原文 202604-202406 疑似笔误）；7-10月大回调数据截至 10-23。',
    '注意：收益比口径对分母（指数涨跌幅）绝对值敏感——指数接近零涨跌时比值会失真（如贸易战期间科创50仅-1.17%），仅作相对强弱参考。',
]
for n in notes:
    o3.append([n])

out.save('产业趋势贝塔研究_贝塔结果.xlsx')
print('已覆盖写入 产业趋势贝塔研究_贝塔结果.xlsx')

# 打印简单贝塔表
print('\n简单贝塔 = 组合涨跌幅 / 指数涨跌幅：')
print(f'{"区间":<22}{"组合":>9}' + ''.join(f'{k:>10}' for k in idx_names))
for row in data:
    rp = row[4]
    print(f'{row[0]:<22}{pct(rp):>9}' + ''.join(f'{(rp/x if abs(x)>1e-12 else float("nan")):>10.2f}' for x in row[5:]))
