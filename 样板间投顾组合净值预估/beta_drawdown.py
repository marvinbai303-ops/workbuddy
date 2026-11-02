# -*- coding: utf-8 -*-
"""下跌区间贝塔修正：区间涨跌幅比 vs 最大回撤比。
核心结论：下跌区间若含 V 型反弹，区间涨跌幅比会系统性低估贝塔，应以最大回撤比为准。
"""
import openpyxl
import pandas as pd

F = '产业趋势贝塔研究.xlsx'
wb = openpyxl.load_workbook(F, data_only=True)
ws = wb['Sheet1']
cols = {3: '创业板指', 4: '科创50', 5: '沪深300', 6: '中证500', 7: '中证1000', 8: '中证全指'}
rows = []
for r in range(3, ws.max_row + 1):
    d = ws.cell(row=r, column=1).value
    if d is None:
        continue
    rows.append([d, ws.cell(row=r, column=2).value] + [ws.cell(row=r, column=c).value for c in cols])
df = pd.DataFrame(rows, columns=['date', '组合'] + list(cols.values()))
df['date'] = pd.to_datetime(df['date'])

def max_drawdown(s):
    peak = s.iloc[0]; md = 0.0
    for v in s.values:
        if v > peak:
            peak = v
        dd = v / peak - 1
        if dd < md:
            md = dd
    return md

downs = [
    ('2025年4月贸易战', '2025-04-01', '2025-04-30'),
    ('2026年3月美伊战争', '2026-03-01', '2026-03-31'),
    ('2026年7-10月科技股大回调', '2026-07-01', '2026-10-23'),
]
idx_names = list(cols.values())

def pct(v):
    return f'{v:+.2%}'

# 组装修正结果
dd_rows = []
for name, s, e in downs:
    sub = df[(df['date'] >= pd.Timestamp(s)) & (df['date'] <= pd.Timestamp(e))]
    p0, p1 = sub['组合'].iloc[0], sub['组合'].iloc[-1]
    rp = p1 / p0 - 1
    mdp = max_drawdown(sub['组合'])
    row = {'name': name, 'rp': rp, 'mdp': mdp}
    for k in idx_names:
        i0, i1 = sub[k].iloc[0], sub[k].iloc[-1]
        rm = i1 / i0 - 1
        mdi = max_drawdown(sub[k])
        row[k + '_ret'] = rm
        row[k + '_dd'] = mdi
    dd_rows.append(row)

# 覆盖写入：在已有 3 个 sheet 基础上，追加“下跌区间贝塔修正”sheet
out = openpyxl.Workbook()
o = out.active
o.title = '下跌区间贝塔修正'
o.append(['区间', '组合最大回撤'] + [f'{k}_回撤' for k in idx_names])
for row in dd_rows:
    o.append([row['name'], pct(row['mdp'])] + [pct(row[k + '_dd']) for k in idx_names])

o2 = out.create_sheet('下跌区间-回撤比')
o2.append(['区间', '组合回撤'] + idx_names)
for row in dd_rows:
    o2.append([row['name'], pct(row['mdp'])] + [pct(row['mdp'] / row[k + '_dd']) for k in idx_names])

o3 = out.create_sheet('涨跌幅比对照')
o3.append(['区间', '组合区间涨跌幅'] + idx_names)
for row in dd_rows:
    o3.append([row['name'], pct(row['rp'])] + [pct(row['rp'] / row[k + '_ret']) for k in idx_names])

o4 = out.create_sheet('说明')
notes = [
    '口径修正说明：',
    '1) 区间涨跌幅比 = 组合区间涨跌幅 / 指数区间涨跌幅，对“月初到月底”的净值做差。',
    '2) 最大回撤比 = 组合区间内最大回撤 / 指数区间内最大回撤，捕捉区间内最深跌幅。',
    '3) 下跌区间若含 V 型反弹（如2025年4月贸易战），区间涨跌幅比会系统性低估贝塔，应以最大回撤比为准。',
    '4) 2025年4月贸易战：组合区间涨跌幅-3.24%但最大回撤-13.90%，创业板指回撤-14.13%，回撤比0.98≈1:1同跌，验证0.44确实偏低。',
    '5) 2026年7-10月大回调为单边下跌无V型反弹，涨跌幅比与回撤比接近（创业板指1.09/1.04），两口径基本一致。',
]
for n in notes:
    o4.append([n])

out.save('产业趋势贝塔研究_贝塔结果.xlsx')
print('已更新 产业趋势贝塔研究_贝塔结果.xlsx')

# 打印对照
print('\n=== 下跌区间：涨跌幅比 vs 回撤比 ===')
print(f'{"区间":<22}{"组合涨跌幅":>10}{"组合回撤":>10}')
for row in dd_rows:
    print(f'{row["name"]:<22}{pct(row["rp"]):>10}{pct(row["mdp"]):>10}')
print()
print('回撤比（修正后下跌贝塔）：')
print(f'{"区间":<22}' + ''.join(f'{k:>10}' for k in idx_names))
for row in dd_rows:
    print(f'{row["name"]:<22}' + ''.join(f'{row["mdp"]/row[k+"_dd"]:>10.2f}' for k in idx_names))
