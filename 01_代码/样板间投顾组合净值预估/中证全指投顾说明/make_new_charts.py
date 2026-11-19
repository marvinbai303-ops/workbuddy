# -*- coding: utf-8 -*-
"""重新生成 p2 量价图（缩量绿 + 反弹红）与压力测试图"""
import pickle
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime

plt.rcParams['font.family'] = 'PingFang SC'
plt.rcParams['axes.unicode_minus'] = False

NAVY = '#061F32'
RED = '#C0392B'
GREEN = '#169A6C'
BLUE_FILL = '#A9C6E8'

BASE = '/Users/yangguang/Documents/Workbuddy/样板间投顾组合净值预估'
ASSETS = BASE + '/中证全指投顾说明/assets'

D = pickle.load(open(BASE + '/merged_kline.pkl', 'rb'))
sec = D['000985.SH']
tds = sorted(dt for dt in sec['dates'] if sec['data'][dt].get('close') is not None)
close = [sec['data'][dt]['close'] for dt in tds]
amt = [sec['data'][dt]['amount'] / 1e8 for dt in tds]
ma20 = [None] * len(tds)
for i in range(19, len(tds)):
    ma20[i] = sum(amt[i - 19:i + 1]) / 20
xs = [datetime.strptime(d, '%Y-%m-%d') for d in tds]
d_idx = {d: i for i, d in enumerate(tds)}

def ma_at(d):
    return ma20[d_idx[d]]

def fwd(d, n):
    i = d_idx[d]; j = min(i + n, len(tds) - 1)
    return tds[j], close[j]

# ============ P2 量价图（双轴） ============
EVENTS = [
    ("疫情恐慌底", "2020-03-23", 51.8, 60, 15.2),
    ("2022 市场底", "2022-04-26", 39.4, 60, 18.4),
    ("924 政策底", "2024-09-13", 42.0, 60, 31.6),
    ("贸易战冲击", "2025-04-07", 21.2, 120, 32.0),
    ("美伊战争", "2026-03-23", 38.9, 60, 15.7),
]

fig, ax1 = plt.subplots(figsize=(23, 11), dpi=100)
ax2 = ax1.twinx()

ax1.plot(xs, close, color=NAVY, lw=2.4, zorder=5)
ma_x = [x for x, v in zip(xs, ma20) if v is not None]
ma_y = [v for v in ma20 if v is not None]
ax2.fill_between(ma_x, 0, ma_y, color=BLUE_FILL, alpha=0.45, zorder=2)
ax2.plot(ma_x, ma_y, color=BLUE_FILL, lw=1.0, alpha=0.85, zorder=2)

# 反弹段（红）+ 缩量点（绿）
for name, bd, ctr, n, fwd_pct in EVENTS:
    i0 = d_idx[bd]; i1 = min(i0 + n, len(tds) - 1)
    ax1.plot(xs[i0:i1 + 1], close[i0:i1 + 1], color=RED, lw=5.0,
             solid_capstyle='round', zorder=6)
    ax1.scatter([xs[i0], xs[i1]], [close[i0], close[i1]], s=70, color=RED, zorder=7)
    ax2.scatter([datetime.strptime(bd, '%Y-%m-%d')], [ma_at(bd)], s=110,
                color=GREEN, zorder=8, marker='o')

# 红反弹标签（指向反弹段终点，标签置于线上方）
RED_POS = {
    "疫情恐慌底": (datetime(2020, 7, 5), 5150, 'center', -0.12),
    "2022 市场底": (datetime(2022, 8, 15), 5480, 'center', -0.14),
    "924 政策底": (datetime(2024, 12, 22), 5280, 'center', -0.10),
    "贸易战冲击": (datetime(2025, 10, 8), 6150, 'center', -0.14),
    "美伊战争": (datetime(2026, 7, 8), 6820, 'center', -0.12),
}
# 绿缩量标签（指向成交额均线底部点，标签置于曲线下方）
GREEN_POS = {
    "疫情恐慌底": (datetime(2020, 4, 30), 5200, 'center', -0.10),
    "2022 市场底": (datetime(2022, 6, 5), 4600, 'center', -0.10),
    "924 政策底": (datetime(2024, 9, 28), 2200, 'center', -0.10),
    "贸易战冲击": (datetime(2025, 5, 10), 9000, 'center', -0.10),
    "美伊战争": (datetime(2026, 4, 25), 19000, 'center', -0.10),
}

for name, bd, ctr, n, fwd_pct in EVENTS:
    end_d, end_c = fwd(bd, n)
    lx, ly, ha, rad = RED_POS[name]
    ax1.annotate(f"{n}日 +{fwd_pct}%",
                 xy=(datetime.strptime(end_d, '%Y-%m-%d'), end_c),
                 xytext=(lx, ly), ha=ha, va='center',
                 fontsize=17, color=RED, fontweight='bold',
                 arrowprops=dict(arrowstyle='-', color=RED, lw=1.1, alpha=0.8,
                                 connectionstyle=f"arc3,rad={rad}"), zorder=9)
    gx, gy, gha, grad = GREEN_POS[name]
    ax2.annotate(f"{name} 缩量 -{ctr}%",
                 xy=(datetime.strptime(bd, '%Y-%m-%d'), ma_at(bd)),
                 xytext=(gx, gy), ha=gha, va='center',
                 fontsize=16, color=GREEN, fontweight='bold',
                 arrowprops=dict(arrowstyle='-', color=GREEN, lw=1.1, alpha=0.85,
                                 connectionstyle=f"arc3,rad={grad}"), zorder=9)

ax1.set_xlim(datetime(2019, 12, 1), datetime(2026, 11, 15))
ax1.set_ylim(3000, 7000)
ax2.set_ylim(0, 45000)
ax1.set_ylabel('中证全指收盘点位', fontsize=15, color=NAVY)
ax2.set_ylabel('全A成交额（亿元）', fontsize=15, color='#5B7FA6')
ax1.tick_params(labelsize=13)
ax2.tick_params(labelsize=13)
ax2.tick_params(axis='y', colors='#5B7FA6')
ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
for sp in ('top',):
    ax1.spines[sp].set_visible(False)
    ax2.spines[sp].set_visible(False)
ax1.spines['left'].set_color('#CCCCCC')
ax1.spines['bottom'].set_color('#999999')
ax2.spines['right'].set_color('#CCCCCC')
ax1.grid(axis='y', color='#E8E8E8', lw=0.8, zorder=0)

ax1.set_title('中证全指全收益走势 vs 全A成交额20日平均值',
              fontsize=21, color='#111111', fontweight='bold', pad=16)
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
handles = [
    Line2D([0], [0], color=NAVY, lw=3, label='中证全指（左轴）'),
    Patch(facecolor=BLUE_FILL, alpha=0.6, label='全A成交额 20日均线（右轴）'),
    Line2D([0], [0], color=RED, lw=5, label='恐慌底后反弹段'),
    Line2D([0], [0], marker='o', color='w', markerfacecolor=GREEN, markersize=10,
           label='恐慌底成交额相较前期成交额高点缩量比例'),
]
ax1.legend(handles=handles, loc='lower center', fontsize=13.5, frameon=False,
           bbox_to_anchor=(0.5, -0.11), ncol=4)
plt.subplots_adjust(bottom=0.12)
plt.savefig(ASSETS + '/p1_chart.png', facecolor='white')
plt.close()
print("OK: p1_chart.png")

# ============ 压力测试图 ============
EV = [
    ("俄乌冲突（2022 年初）", -24.0, -34.0, -31.6, -33.8, -36.4, -26.7),
    ("流动性危机（2024.01）", -12.8, -26.7, -33.4, -16.5, -19.8, -14.5),
    ("贸易战（2025.04）", -11.4, -16.9, -19.6, -18.9, -15.2, -13.1),
    ("美伊战争（2026.03）", -10.3, -13.5, -14.7, -6.2, -15.6, -9.3),
]
LABELS = ["守正组合", "中证1000", "中证2000", "创业板指", "科创50", "偏股基金指数"]

fig, ax = plt.subplots(figsize=(23, 11), dpi=100)
n_ev = len(EV)
n_s = len(LABELS)
y = np.arange(n_ev)[::-1]
bar_h = 0.13
gap = 0.045
colors = [NAVY, '#B9C4CE', '#B9C4CE', '#B9C4CE', '#B9C4CE', '#5B7FA6']

for ei, row in enumerate(EV):
    vals = row[1:]
    center = y[ei]
    for si in range(n_s):
        by = center + (n_s / 2 - si - 0.5) * (bar_h + gap)
        ax.barh(by, vals[si], height=bar_h, color=colors[si], zorder=3)
        ax.text(vals[si] - 0.8, by, f"{vals[si]:.1f}%", va='center', ha='right',
                fontsize=12.5, color='#333333', zorder=4)

for ei, row in enumerate(EV):
    ax.text(0.6, y[ei], row[0], va='center', ha='left', fontsize=16.5,
            fontweight='bold', color=NAVY)

ax.set_xlim(-42, 2)
ax.set_ylim(-0.7, n_ev - 0.3)
ax.set_yticks([])
ax.set_xticks(range(-40, 1, 10))
ax.set_xticklabels([f"{v}%" for v in range(-40, 1, 10)], fontsize=13, color='#444444')
ax.set_xlabel('事件内最大回撤（%）', fontsize=15, color='#333333')
for sp in ('top', 'right', 'left'):
    ax.spines[sp].set_visible(False)
ax.spines['bottom'].set_color('#999999')
ax.axvline(0, color='#888888', lw=1.0, ls='--', zorder=1)

ax.set_title('四次黑天鹅：守正组合（深色）回撤持续小于小盘与科创指数',
             fontsize=21, color='#111111', fontweight='bold', pad=16)

from matplotlib.patches import Patch
handles = [
    Patch(facecolor=NAVY, label='守正组合'),
    Patch(facecolor='#B9C4CE', label='中证1000 / 中证2000 / 创业板指 / 科创50'),
    Patch(facecolor='#5B7FA6', label='偏股基金指数（930950）'),
]
ax.legend(handles=handles, loc='lower center', fontsize=13.5, frameon=False,
          bbox_to_anchor=(0.5, -0.11), ncol=3)
plt.subplots_adjust(bottom=0.12)
plt.savefig(ASSETS + '/stress_chart.png', facecolor='white')
plt.close()
print("OK: stress_chart.png")
