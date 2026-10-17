# -*- coding: utf-8 -*-
"""生成投顾两页 PPT 的 P1/P2 图表
P1: 中证全指 vs 全A成交额20日均线，4 事件 + 4 成交额回暖段（浅红线段+转暖幅度标注）
P2: 五轮行情哑铃图（最弱-全指-最强），持续时间改为「xxxx年x月 – xxxx年x月」
数据源: merged_kline.pkl (NeoData 行情接口, 不复权)
"""
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
WARM_RED = '#EE6B75'      # 浅红回暖段
GREEN = '#169A6C'
BLUE_FILL = '#A9C6E8'
GREY_LINE = '#9AA3AB'

BASE = '/Users/yangguang/Documents/Workbuddy/样板间投顾组合净值预估'
ASSETS = BASE + '/中证全指投顾说明/assets'

with open(BASE + '/merged_kline.pkl', 'rb') as f:
    D = pickle.load(f)

sec = D['000985.SH']
tds = sorted(dt for dt in sec['dates'] if sec['data'][dt].get('close') is not None)
close = [sec['data'][dt]['close'] for dt in tds]
amt = [sec['data'][dt]['amount'] / 1e8 for dt in tds]  # 亿元
ma20 = [None] * len(tds)
for i in range(19, len(tds)):
    ma20[i] = sum(amt[i - 19:i + 1]) / 20

xs = [datetime.strptime(d, '%Y-%m-%d') for d in tds]

# ---------------- P1 ----------------
fig, ax1 = plt.subplots(figsize=(23, 11), dpi=100)
ax2 = ax1.twinx()

# 全指 Navy 线
ax1.plot(xs, close, color=NAVY, lw=2.6, zorder=5)
# 成交额 20 日均线浅蓝面积
ma_x = [x for x, v in zip(xs, ma20) if v is not None]
ma_y = [v for v in ma20 if v is not None]
ax2.fill_between(ma_x, 0, ma_y, color=BLUE_FILL, alpha=0.55, zorder=2)
ax2.plot(ma_x, ma_y, color=BLUE_FILL, lw=1.0, alpha=0.9, zorder=2)

# 4 次大底事件
EVENTS = [
    ("疫情后复苏",  "2020-05-29", 23.5, (0, 15), (-0.02, 0.06)),
    ("2022 市场大底", "2022-04-27", 15.5, (0, 15), (-0.06, 0.30)),
    ("924 政策底",  "2024-09-24", 25.2, (0, 15), (-0.10, -0.22)),
    ("贸易战冲击",  "2025-04-07", 13.8, (0, 15), (-0.06, -0.30)),
]
x0, x1 = datetime(2019, 12, 1), datetime(2026, 11, 15)
span_days = (x1 - x0).days

def dx(offset_frac):
    from datetime import timedelta
    return x0 + timedelta(days=span_days * offset_frac)

# 手定标注位置 (x, y, ha, 引线rad) —— 避开Navy线与其他文字
EV_POS = {
    "疫情后复苏":  (datetime(2020, 3, 5), 3330, 'left', -0.15),
    "2022 市场大底": (datetime(2022, 1, 25), 5950, 'left', -0.18),
    "924 政策底":  (datetime(2024, 6, 10), 3320, 'center', -0.12),
    "贸易战冲击":  (datetime(2025, 4, 20), 3550, 'left', -0.18),
}
for name, dt, fwd, _, _ in EVENTS:
    e = datetime.strptime(dt, '%Y-%m-%d')
    i = tds.index(dt)
    y = close[i]
    ax1.scatter([e], [y], s=110, color=RED, zorder=8)
    lx, ly, ha, rad = EV_POS[name]
    ax1.annotate(f"{name}  60日 +{fwd}%",
                 xy=(e, y), xytext=(lx, ly), ha=ha, va='center',
                 fontsize=17, color=RED, fontweight='bold',
                 arrowprops=dict(arrowstyle='-', color=RED, lw=1.2,
                                 connectionstyle=f"arc3,rad={rad}"),
                 zorder=9)

# 4 段成交额回暖（浅红线段 + 转暖幅度标注）
WARM = [
    # (start, end, label, 文字x, 文字y(右轴), ha, 指向点(相对段), rad)
    ("2020-05-29", "2020-07-29", "边际转暖 +119%",
     datetime(2020, 8, 25), 13800, 'left', ('end', 900), -0.12),
    ("2022-04-26", "2022-07-07", "边际转暖 +28%",
     datetime(2022, 6, 20), 12300, 'center', ('mid', 900), -0.18),
    ("2024-09-18", "2024-11-14", "边际转暖 +281%",
     datetime(2024, 7, 5), 17200, 'center', ('mid', 800), 0.15),
    ("2025-06-06", "2025-07-31", "缩量企稳后转暖 +43%",
     datetime(2025, 8, 5), 9800, 'left', ('end', -900), 0.15),
]
date_idx = {d: i for i, d in enumerate(tds)}
for s, e, label, lx, ly, ha, (anchor, dy), rad in WARM:
    i0, i1 = date_idx[s], date_idx[e]
    ax2.plot(xs[i0:i1 + 1], ma20[i0:i1 + 1], color=WARM_RED, lw=4.0,
             solid_capstyle='round', zorder=6)
    # 段两端小圆点
    ax2.scatter([xs[i0], xs[i1]], [ma20[i0], ma20[i1]], s=42, color=WARM_RED, zorder=7)
    # 锚点：'start'段起点 / 'end'段终点 / 'mid'段中点
    ai = {'start': i0, 'end': i1, 'mid': (i0 + i1) // 2}[anchor]
    ax2.annotate(label, xy=(xs[ai], ma20[ai] + dy),
                 xytext=(lx, ly), ha=ha, va='center',
                 fontsize=16.5, color=WARM_RED, fontweight='bold',
                 arrowprops=dict(arrowstyle='-', color=WARM_RED, lw=1.1, alpha=0.85,
                                 connectionstyle=f"arc3,rad={rad}"),
                 zorder=9)

# 轴样式
ax1.set_xlim(x0, x1)
ax1.set_ylim(3000, 7000)
ax2.set_ylim(0, 42000)
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

# 图内标题 + 图例
ax1.set_title('成交额回暖 = 风险偏好回暖：中证全指随后均显著上行',
              fontsize=21, color='#111111', fontweight='bold', pad=16)
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
handles = [
    Line2D([0], [0], color=NAVY, lw=3, label='中证全指（左轴）'),
    Patch(facecolor=BLUE_FILL, alpha=0.6, label='全A成交额 20日均线（右轴）'),
    Line2D([0], [0], color=WARM_RED, lw=4, label='成交额回暖段（右轴）'),
]
ax1.legend(handles=handles, loc='upper left', fontsize=14, frameon=False,
           bbox_to_anchor=(0.005, 0.99))

plt.tight_layout()
plt.savefig(ASSETS + '/p1_chart.png', facecolor='white')
plt.close()

# ---------------- P2 ----------------
RALLIES = [
    ("疫后复苏",          "2020年3月 – 2020年7月", 36.8, ("医药", 55.5),  ("通信设备", 17.5)),
    ("2021新能源结构牛",   "2021年3月 – 2021年12月", 13.7, ("新能源", 80.8), ("恒生科技", -25.3)),
    ("疫后反弹",          "2022年4月 – 2022年6月", 23.8, ("新能源", 61.6), ("黄金", -1.5)),
    ("924行情",          "2024年9月 – 2024年11月", 38.9, ("半导体", 80.5), ("黄金", 5.3)),
    ("2025科技牛",        "2025年4月 – 2025年10月", 36.6, ("中证TMT", 68.0), ("医药", 19.8)),
]

fig, ax = plt.subplots(figsize=(23, 11.2), dpi=100)
ys = list(range(1, len(RALLIES) + 1))[::-1]  # 第1条在最上
XMIN, XMAX = -42, 96

for (name, dur, csi, best, worst), y in zip(RALLIES, ys):
    bx, by = y, y
    wv, bv = worst[1], best[1]
    # 哑铃连线
    ax.plot([wv, bv], [y, y], color=GREY_LINE, lw=3.0, zorder=2)
    # 最弱(绿) / 最强(红) / 全指(Navy大点)
    ax.scatter([wv], [y], s=210, color=GREEN, zorder=4)
    ax.scatter([bv], [y], s=210, color=RED, zorder=4)
    ax.scatter([csi], [y], s=430, color=NAVY, zorder=5)
    # 全指标注（点上方）
    ax.annotate(f"全指 +{csi}%", xy=(csi, y), xytext=(0, 17),
                textcoords='offset points', ha='center',
                fontsize=16.5, fontweight='bold', color=NAVY, zorder=6)
    # 最弱标注：默认下方居中；恒生科技(-25.3)太靠左会撞左侧标签，移到点右下方
    if wv < -20:
        w_off, w_ha = (14, -26), 'left'
    else:
        w_off, w_ha = (0, -30), 'center'
    ax.annotate(f"{worst[0]} {worst[1]:+.1f}%", xy=(wv, y), xytext=w_off,
                textcoords='offset points', ha=w_ha,
                fontsize=14.5, color=GREEN, zorder=6)
    # 最强标注（上方）
    ax.annotate(f"{best[0]} +{best[1]}", xy=(bv, y), xytext=(0, 17),
                textcoords='offset points', ha='center',
                fontsize=14.5, color=RED, zorder=6)
    # 左侧行情名 + 时间区间
    ax.annotate(name, xy=(XMIN + 1.5, y + 0.13), fontsize=16.5,
                fontweight='bold', color=NAVY, ha='left', va='center',
                annotation_clip=False)
    ax.annotate(dur, xy=(XMIN + 1.5, y - 0.20), fontsize=13.5,
                color='#666666', ha='left', va='center',
                annotation_clip=False)

# 0 轴虚线
ax.axvline(0, color='#888888', lw=1.0, ls='--', zorder=1)

ax.set_xlim(XMIN, XMAX)
ax.set_ylim(0.35, len(RALLIES) + 0.75)
ax.set_yticks([])
ax.set_xticks(range(-40, 100, 20))
ax.tick_params(axis='x', labelsize=14, colors='#444444')
ax.set_xlabel('区间涨跌幅（%）', fontsize=15, color='#333333')
for sp in ('top', 'right', 'left'):
    ax.spines[sp].set_visible(False)
ax.spines['bottom'].set_color('#999999')

ax.set_title('每轮上涨，中证全指均录得正收益，且避开最弱赛道的大坑',
             fontsize=21, color='#111111', fontweight='bold', pad=16, x=0.42)
handles = [
    Line2D([0], [0], marker='o', color='w', markerfacecolor=RED, markersize=12, label='当期最强行业'),
    Line2D([0], [0], marker='o', color='w', markerfacecolor=NAVY, markersize=14, label='中证全指'),
    Line2D([0], [0], marker='o', color='w', markerfacecolor=GREEN, markersize=12, label='当期最弱行业'),
]
ax.legend(handles=handles, loc='upper right', fontsize=14, frameon=False,
          bbox_to_anchor=(1.0, 1.02), ncol=3, columnspacing=1.6)

plt.tight_layout()
plt.savefig(ASSETS + '/p2_chart.png', facecolor='white')
plt.close()

print("OK: p1_chart.png, p2_chart.png generated")
