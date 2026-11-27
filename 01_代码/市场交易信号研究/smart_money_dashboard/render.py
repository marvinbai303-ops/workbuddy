#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""渲染「聪明钱温度计」单文件看板"""
import json, os, math
from datetime import date as ddate

BASE = os.path.dirname(os.path.abspath(__file__))
import smd_paths as P
D = json.load(open(os.path.join(P.MID, 'dashboard_data.json'), encoding='utf-8'))
T, EOD, NOON, S, META, SER = D['temp'], D['eod'], D['noon'], D['stats'], D['meta'], D['series']
CUR = D['cur']
PREV = D.get('preview')             # 午盘 MCL 预览（含ST口径，一步递推）
MA = D['ma']; MP = MA['periods']    # 均线广度 P20/P60/P250
P20, P60, P250 = MP['20'], MP['60'], MP['250']
_ps = [x[1] for x in SER['p_series']]
_p_mae = sum(abs(_ps[i] - _ps[i - 1]) for i in range(1, len(_ps))) / max(1, len(_ps) - 1)
_p_max = max(abs(_ps[i] - _ps[i - 1]) for i in range(1, len(_ps)))
AMT = D.get('market_amount')          # 两市合计成交额（沪深京口径）
TRJ = D.get('turnover_daily')
_tr_ma = f'{TRJ["ma20"]:.2f}%' if TRJ and TRJ['ma20'] is not None else '—'
_tr_rk = f'{TRJ["pct_rank"]:.0f}' if TRJ and TRJ['pct_rank'] is not None else '—'
_tr_cmp = ('单日在均值之上，短线情绪偏热' if TRJ and TRJ['ma20'] is not None and TRJ['pct'] > TRJ['ma20']
           else '单日在均值之下，短线情绪较前两周降温')

CUR_L = CUR['label']                # 例：2026-11-18 11:30
ASOF = META['asof']; ASOF_S = ASOF[5:]
CUR_S = CUR['date'][5:]
EOD_S = META['eod_date'][5:]        # 逐股快照日（结构章节用）
# 日终参照点：取 daily_agg 最新收盘（含ST），而不是逐股快照的 agg_eod。
# 两者的日期可以不同：结构章节只能用逐股快照，象限对比应该跟最新收盘。
EREF = D.get('eod_ref') or D['eod']
EREF_S = EREF['date'][5:]
# 午盘逐股快照的落盘位置随取数通道变化：扶摇写 hithink_snapshots/noon_snap_*.csv，
# 旧 iFinD 通道写 snapshots/noon_*.csv。底稿里按实际存在的文件给出路径。
_HX_NOON = os.path.join(P.DATA, 'store', 'hithink_snapshots', f'noon_snap_{META["noon_date"]}.csv')
NOON_SNAP_PATH = (f'data/store/hithink_snapshots/noon_snap_{META["noon_date"]}.csv'
                  if os.path.exists(_HX_NOON)
                  else f'data/store/snapshots/noon_{META["noon_date"]}.csv')
NOON_SNAP_NOTE = ('扶摇一次全市场快照（沪深A股含ST），落盘逐股明细'
                  if os.path.exists(_HX_NOON)
                  else '10:30/11:30 两根已完成小时K，剔除停牌')

# 午盘跑的时候成交分布比广度底库新一天：此时不能说“盘中读数先于收盘值”。
_TIME_NOTE = ('成交分布已到今日午盘，广度仍停在上一收盘——两者不是同一时点，不能合并成一个结论。'
              if CUR['date'] > ASOF
              else '盘中读数先于收盘值，不能当作同一时点的结论。')

def quadrant(p, g):
    if p >= 50 and g >= 0: return ('全面进攻', '普涨且成交额跟随，是最健康的状态')
    if p >= 50 and g < 0:  return ('反弹待确认', '价格普涨但成交额没跟上，需下一时点转正确认')
    if p < 50 and g >= 0:  return ('抱团', '少数股票上涨且成交额集中，赚钱效应窄')
    return ('冰点', '普跌且成交额也不向上涨组集中')

def f(x, n=1): return '—' if x is None else f'{x:,.{n}f}'

def num(x, n=0, sign=False):
    s = f'{x:+,.{n}f}' if sign else f'{x:,.{n}f}'
    return s.replace('-', '−')

CR = {k: v for k, v in D['size']['cr'].items()}

def temp_color(t):
    return '#1f6b52' if t < 20 else '#3c8f6e' if t < 35 else '#5c7f96' if t < 50 else '#c08b3e' if t < 65 else '#c85f2e' if t < 80 else '#b3372c'
TC = temp_color(T['total'])
P20TXT = '—' if T['pct_p20'] is None else f"{T['pct_p20']:.0f}"   # 均线广度尚未积累够窗口时为 —

# VW-MACD 柱体方向随数据走：正柱讲「衰减」，负柱讲「重新走弱」，不得写死
_VWH = S['vw_hist_last']
_VW_STREAK = S['vw_hist_streak']
_VW_WEEK_NEG = SER['vww_hist'][-1][1] < 0
_VW_NOTE = (f'日线柱连 {_VW_STREAK} 日为正、跌势动能衰减' if _VWH > 0
            else f'日线柱连 {_VW_STREAK} 日转负、动能重新走弱')
_VW_NOTE += f'；DIF/DEA 仍在零轴下，{"周线柱仍为负" if _VW_WEEK_NEG else "周线柱已转正"}。'
_VW_BULLET = (f'日线柱已连续 {_VW_STREAK} 日为正、读到 {num(_VWH,1,True)}（分位 {S["vw_hist_pct"]:.0f}），下跌动能在衰减。'
              if _VWH > 0 else
              f'日线柱已连续 {_VW_STREAK} 日落在零轴下方、读到 {num(_VWH,1,True)}（分位 {S["vw_hist_pct"]:.0f}），前一日的正柱未能延续，动能重新走弱。')
_VW_STATE = ('价格动能修复、广度仍弱＝反弹质量存疑' if _VWH > 0 and CUR['p'] < 50
             else '价格动能转负、广度仍弱＝两个模块同向走弱' if _VWH <= 0 and CUR['p'] < 50
             else '价格动能修复、广度也不弱＝两个模块同向改善' if _VWH > 0
             else '价格动能转负、广度尚可＝指数与个股背离，动能层先走弱')

# ---------------------------------------------------------------- 温度计
def arc(cx, cy, r, a0, a1):
    x0 = cx + r*math.cos(math.radians(180-a0)); y0 = cy - r*math.sin(math.radians(180-a0))
    x1 = cx + r*math.cos(math.radians(180-a1)); y1 = cy - r*math.sin(math.radians(180-a1))
    return f'M {x0:.2f} {y0:.2f} A {r} {r} 0 {1 if abs(a0-a1)>180 else 0} 0 {x1:.2f} {y1:.2f}'

parts = [f'<path d="{arc(150,152,116,v0*1.8,v1*1.8)}" stroke="{c}" stroke-width="16" fill="none"/>'
         for v0, v1, c in [(0,20,'#1f6b52'),(20,35,'#59a07d'),(35,50,'#5c7f96'),(50,65,'#c08b3e'),(65,80,'#c85f2e'),(80,100,'#b3372c')]]
for v in range(0, 101, 10):
    a = math.radians(180-v*1.8)
    parts.append(f'<line x1="{150+129*math.cos(a):.1f}" y1="{152-129*math.sin(a):.1f}" x2="{150+138*math.cos(a):.1f}" y2="{152-138*math.sin(a):.1f}" stroke="#c9c3b6"/>')
    if v % 20 == 0:
        parts.append(f'<text x="{150+144*math.cos(a):.1f}" y="{152-144*math.sin(a)+3.5:.1f}" text-anchor="middle" font-size="10" fill="#9a9384">{v}</text>')
na = math.radians(180-T['total']*1.8)
parts.append(f'<line x1="150" y1="152" x2="{150+92*math.cos(na):.1f}" y2="{152-92*math.sin(na):.1f}" stroke="#2b2a26" stroke-width="3.2" stroke-linecap="round"/>')
parts.append('<circle cx="150" cy="152" r="7.5" fill="#2b2a26"/><circle cx="150" cy="152" r="2.8" fill="#fffefb"/>')
GAUGE = f'<svg viewBox="-12 0 324 192" class="gauge">{"".join(parts)}</svg>'

def axbar(label, val, color, note):
    return f'''<div class="axbar"><div class="axbar-h"><span>{label}</span><b style="color:{color}">{val:.0f}<i>/100</i></b></div>
    <div class="axbar-t"><i style="width:{max(1.5,min(100,val)):.1f}%;background:{color}"></i></div>
    <div class="axbar-n">{note}</div></div>'''

HERO = f'''
<section class="hero">
  <div class="hero-l">{GAUGE}<div class="gauge-cap">综合温度</div></div>
  <div class="hero-r">
    <div class="hero-row"><span class="tag" style="background:{TC}14;color:{TC};border-color:{TC}55">{T['label']}</span>
      <span class="hero-date">日终 {META['asof']} · 午盘 {META['noon_date'][5:]}</span></div>
    <div class="dataline">
      <span>MCL 底库 <b>{META['asof']}</b></span>
      {('<span>MCL 预览 <b>' + PREV['date'] + ' 11:30</b></span>') if PREV else ''}
      <span>均线广度 <b>{MA['last_date']}</b></span>
      <span>成交分布 <b>{CUR_L}</b></span>
      <span>午盘快照 <b>{META['noon_date']} 11:30</b></span>
      {(f'<em>成交分布滞后：MCL 已到 {META["asof"]}，成交分布仍是 {CUR["date"]}</em>') if CUR['date'] < META['asof'] else '<em class="ok">成交分布已是最新快照</em>'}
    </div>
    <div class="mktline">两市合计成交额 <b>{AMT["amt"]/1e12:.2f} 万亿</b>
      <span>沪深京口径 · {AMT["date"][5:]} 收盘 · 较 20 日均额 {(lambda v: ('+' if v > 0 else '−') + f'{abs(v):.1f}')(100*(AMT["amt"]/AMT["ma20"]-1))}%</span></div>
    <div class="hero-big" style="color:{TC}">{T['total']:.0f}<span>分</span></div>
    <p class="hero-desc">{T['desc']}。由两个等权模块合成：<b>参与面</b>（广度）× <b>成交分布</b>（资金）。
    广度温度自本轮起改为三分项等权（涨家占比分位 / MCL 分位 / P20 分位）；两分项的旧口径为 <b>{T['breadth_v1']:.0f}</b>，可对照。</p>
    <div class="hero-axes">
      {axbar('广度温度', T['breadth'], '#5c7f96', f'涨家占比分位 {T["pct_p"]:.0f} · MCL 分位 {T["pct_mcl"]:.0f} · P20 分位 {P20TXT}，等权')}
      {axbar('资金温度', T['money'], '#b3372c', f'{CUR_L} 额价差 {CUR["G"]:+.2f}pp，占理论上限 {100*CUR["G"]/T["g_max"]:.0f}%')}
    </div>
    <div class="scale">
      <span><i style="background:#1f6b52"></i>0–20 冰点</span><span><i style="background:#59a07d"></i>20–35 偏冷</span>
      <span><i style="background:#5c7f96"></i>35–50 中性偏冷</span><span><i style="background:#c08b3e"></i>50–65 中性偏热</span>
      <span><i style="background:#c85f2e"></i>65–80 偏热</span><span><i style="background:#b3372c"></i>80–100 过热</span>
    </div>
  </div>
</section>'''

_p_now = D['series']['p_series'][-1][1]
_p_prev = D['series']['p_series'][-2][1]
_p_chg = _p_now - _p_prev
_h3 = ('广度单日反转' if _p_chg >= 20 else '广度回升' if _p_chg >= 5
       else '广度仍在收缩' if _p_now < 40 else '广度持稳')
_mcl_prev = D['series']['mcl'][-2][1]
if S['mcl_last'] >= 0:
    _mcl_note = 'MCL 为正，参与面动量尚可。'
elif S['mcl_last'] > _mcl_prev:
    _mcl_note = f'MCL 仍为负，但较前值 {num(_mcl_prev)} 回升 {S["mcl_last"] - _mcl_prev:+.0f}，恶化速度放缓，尚未修复。'
else:
    _mcl_note = 'MCL 从正转负后继续走低，参与面动量未修复。'

CONCL = f'''<section class="concl">
  <div class="concl-i"><span>01</span><p><b>温度 {T['total']:.0f}，落在“{T['label']}”。</b>两个模块的时点不同：广度取 {ASOF} 收盘（涨家占比分位 {T['pct_p']:.0f}、MCL 分位 {T['pct_mcl']:.0f}），成交分布取 <b>{CUR_L}</b>（{CUR['kind'] == 'noon' and '午盘' or '日终'}口径）。{_TIME_NOTE}</p></div>
  <div class="concl-i"><span>02</span><p><b>{CUR_L} 的成交分布：{quadrant(CUR['p'], CUR['G'])[0]}。</b>涨家占比 {CUR['p']:.1f}%、涨额占比 {CUR['q']:.1f}%、额价差 {CUR['G']:+.2f}pp、成交额 TRIN {CUR['trin_e']:.2f}。{quadrant(CUR['p'], CUR['G'])[1]}；判断标准是成交额份额有没有跟上家数份额。</p></div>
  <div class="concl-i"><span>03</span><p><b>{_h3}：{ASOF} 收盘涨家占比 {_p_now:.1f}%（前值 {_p_prev:.1f}%，{_p_chg:+.1f}pp）、MCL {num(S['mcl_last'])}{('（午盘预览 ' + num(PREV['mcl']) + '）') if PREV else ''}。</b>{_mcl_note}趋势层仍弱：{MA['last_date']} 站上 MA20 的只有 <b>{P20['pct']:.1f}%</b>、MA250 之上 <b>{P250['pct']:.1f}%</b>。单日极值不可外推——近 {len(D['series']['p_series'])} 日涨家占比单日平均变动 27pp，必须配 20 日均值读。</p></div>
</section>'''

def _fut_deep_note(limits=10.0):
    """按三品种各自的分位描述贴水深度，不预设三品种同向。"""
    ks = ['IF', 'IC', 'IM']
    deep = [k for k in ks if D['fut'][k]['pct'] <= limits]
    rest = [k for k in ks if k not in deep]
    if not deep:
        return f'三品种分位均未进入一年最深 {limits:.0f}%。'
    if not rest:
        return f'三品种均处一年最深 {limits:.0f}% 区间。'
    rest_txt = '、'.join('{:.0f}'.format(D['fut'][k]['pct']) for k in rest)
    return '{deep} 处一年最深 {lim:.0f}% 区间；{rest} 分位 {rt}，贴水相对偏浅。'.format(
        deep='/'.join(deep), lim=limits, rest='/'.join(rest), rt=rest_txt)

CARDS = [
 ('MCL 麦克连摆','100','公式与原始定义一致',
  (num(PREV['mcl']) if PREV else num(S["mcl_last"])), '午盘预览' if PREV else '分位',
  (num(S["mcl_last"]) if PREV else f'{T["pct_mcl"]:.0f}'), '#b3372c',
  (f'11:30 一步递推（基准 {PREV["base_date"]} 收盘 {num(PREV["base_mcl"])}）；收盘后以实际收盘重算。') if PREV
  else f'{ASOF} 收盘值。'),
 ('涨家占比 p','90','含ST · 同屏反算',f'{CUR["p"]:.1f}<i>%</i>','分位',f'{T["pct_p_cur"]:.0f}','#b3372c',f'{CUR_L}：{CUR["A"]:,} 家涨 / {CUR["D"]:,} 家跌。'),
 ('站上 MA20 比例','100','选股计数 · 逐日',f'{P20["pct"]:.1f}<i>%</i>','分位',P20TXT,'#31556e',f'{P20["num"]:,} / {P20["den"]:,} 只；同口径 P60 {P60["pct"]:.1f}%、P250 {P250["pct"]:.1f}%。'),
 ('成交额 TRIN','95','量版原式＋金额口径',f'{CUR["trin_e"]:.3f}','倍数',f'{1/CUR["trin_e"]:.2f}×','#1f6b52',f'上涨组平均成交额是下跌组的 {1/CUR["trin_e"]:.2f} 倍。'),
 ('额价差 G','90','终端输出确认',f'{CUR["G"]:+.2f}<i>pp</i>','占上限',f'{100*CUR["G"]/T["g_max"]:.0f}%','#c08b3e',f'q−p；占该 p 下理论上限的 {100*CUR["G"]/T["g_max"]:.0f}%。'),
 ('VW-MACD（沪深300）','100',f'参数 12/26/9 · {SER["vw_close"][-1][0][5:]} 收盘',num(S["vw_hist_last"],1,True),'柱体分位',f'{S["vw_hist_pct"]:.0f}','#c08b3e',_VW_NOTE),
 ('IF 年化基差','100',f'主力合约 · 200日分位 · {D["fut"]["IF"]["date"][5:]} 收盘',f'{D["fut"]["IF"]["ann"]:+.1f}<i>%</i>','分位',f'{D["fut"]["IF"]["pct"]:.0f}','#31556e',f'贴水 {abs(D["fut"]["IF"]["basis"]):.1f} 点；IC {D["fut"]["IC"]["ann"]:+.1f}%（分位 {D["fut"]["IC"]["pct"]:.0f}）、IM {D["fut"]["IM"]["ann"]:+.1f}%（分位 {D["fut"]["IM"]["pct"]:.0f}）。' + _fut_deep_note()),
 ('三只宽基 ETF / MA20','100','指定三只代码',f'{S["etf_ratio_last"]:.2f}','分位',f'{S["etf_ratio_pct"]:.0f}','#3c8f6e',(f'合计额 {D["series"]["etf_amt"][-1][1]:.0f} 亿，为 20 日均额的 {S["etf_ratio_last"]:.2f} 倍；' + ('宽基无增量，不能证明“国家队”。' if S["etf_ratio_last"] < 1 else '宽基放量，但仍推不出资金身份。'))),
 ('换手率&gt;5% 占比','75','定义可数学化',f'{TRJ["pct"]:.2f}<i>%</i>','分位',f'{TRJ["pct_rank"]:.0f}','#b3372c',f'{TRJ["date"][5:]} 收盘 {TRJ["n5"]:,}/{TRJ["nb"]:,}；20 日均值 {_tr_ma}。'),
]
card_html = ''.join(f'''<article class="card"><div class="card-h"><h3>{n}</h3></div>
<div class="card-src">{src}</div><div class="card-v" style="color:{col}">{val}</div>
<div class="card-sub"><span>{k}</span><b>{v}</b></div><p>{txt}</p></article>''' for n, sc, src, val, k, v, col, txt in CARDS)

# 参照系取“已收盘的最新交易日”：午盘快照是盘中值，不与收盘口径混比
_fdates = [ASOF, MA['last_date'], SER['vw_close'][-1][0],
           D['fut']['IF']['date'], SER['etf_amt'][-1][0], AMT['date'], TRJ['date'],
           (D['turnover_dist']['date'] if D.get('turnover_dist') else TRJ['date'])]
LATEST = max(_fdates)
_fgap = lambda d: (ddate.fromisoformat(LATEST) - ddate.fromisoformat(d)).days

def _frow(name, date, note, fixed_badge=None):
    gap = _fgap(date)
    if fixed_badge:
        badge = fixed_badge
    elif gap <= 0:
        badge = '<span class="badge ok sm">最新</span>'
    else:
        badge = f'<span class="badge warn sm">滞后 {gap} 天</span>'
    return (f'<tr><td>{name}</td><td class="b">{date}</td><td>{badge}</td>'
            f'<td class="mono">{note}</td></tr>')

fresh_table = ('<div class="table-wrap"><table class="tb"><thead><tr>'
               '<th style="width:30%">模块</th><th style="width:16%">数据时点</th>'
               '<th style="width:12%">状态</th><th>说明</th></tr></thead><tbody>'
               + _frow('MCL / 涨家占比（含ST）', ASOF, META.get('close_source') or '日终收盘快照')
               + _frow('均线广度 P20/60/250', MA['last_date'], '选股计数')
               + _frow('成交分布 TRIN / 额价差', CUR['date'],
                       ('午盘 11:30 快照，非收盘口径' if CUR['kind'] == 'noon' else '日终快照'),
                       ('<span class="badge ok sm">盘中</span>' if CUR['kind'] == 'noon'
                        and CUR['date'] > LATEST else None))
               + _frow('VW-MACD（沪深300）', SER['vw_close'][-1][0], '指数日线')
               + _frow('股指期货基差', D['fut']['IF']['date'], '主力合约日线')
               + _frow('三只 ETF 合计成交额', SER['etf_amt'][-1][0], '基金日行情')
               + _frow('两市合计成交额（沪深京）', AMT['date'], '板块 001005010 全部A股')
               + _frow('换手率&gt;5% 占比', TRJ['date'], '选股计数')
               + _frow('换手率分布（9 桶）', D['turnover_dist']['date'] if D.get('turnover_dist') else META['eod_date'],
                       '选股计数，9 次调用/日')
               + _frow('市值结构（五分位 / CR）', META['eod_date'], '需逐股明细，已退出日常流程，按需手动触发',
                       '<span class="badge warn sm">仅快照日</span>')
               + '</tbody></table></div>')

OVERVIEW = f'''<section class="sec" id="s0"><div class="sec-h"><span class="no">总览</span><div>
<h2>九项读数与一句话点评</h2></div></div>
<div class="cards">{card_html}</div>
<p class="cap">九个模块各自停在哪一天，见文末<a href="#fresh">数据时点</a>。</p></section>'''

def dot(p, g, label, color):
    x = min(97, max(3, p)); y = min(96, max(4, 100-(g+30)/60*100))
    return f'<div class="mx-dot" style="left:{x}%;top:{y}%;background:{color}"><span>{label}</span></div>'

MATRIX = f'''<section class="sec" id="s1"><div class="sec-h"><span class="no">矩阵</span><div>
<h2>把两个模块放在同一张图上</h2><p>横轴＝涨家占比（参与广度），纵轴＝额价差（成交额是否向上涨组倾斜）。两个模块回答不同问题，单看任何一个都会误判。</p></div></div>
<div class="mx-wrap"><div class="mx">
  <div class="mx-cell q1"><b>抱团</b><span>少数股票上涨且成交额集中。指数可能被权重撑住，但赚钱效应差。</span></div>
  <div class="mx-cell q2"><b>全面进攻</b><span>普涨且资金跟随，广度与成交同时改善，最健康的状态。</span></div>
  <div class="mx-cell q3"><b>冰点</b><span>普跌且成交额也不向上涨组集中，通常伴随缩量。</span></div>
  <div class="mx-cell q4"><b>反弹待确认</b><span>价格普涨但成交额没跟上，常见于超跌反弹第一波。</span></div>
  <div class="mx-axis-x"></div><div class="mx-axis-y"></div>
  {dot(CUR['p'],CUR['G'],CUR_S+' 当前','#2b2a26')}{dot(EREF['p'],EREF['G'],EREF_S+' 日终','#9c968a')}
</div><div class="mx-lg">
  <div><i style="background:#2b2a26"></i>{CUR_L}（当前）：p {CUR['p']:.1f}%，G {CUR['G']:+.1f}pp</div>
  <div><i style="background:#9c968a"></i>{EREF['date']} 收盘：p {EREF['p']:.1f}%，G {EREF['G']:+.1f}pp</div>
  <p>纵轴 −30 ~ +30pp，横轴 0 ~ 100%。灰线为 p=50%、G=0 的分界。午盘读数不进日终序列。{('结构（市值五分位 / CR / 涨跌分布）另需逐股明细，停在 ' + META['eod_date'] + ' 的逐股快照，与本图无关。') if META['eod_date'] < EREF['date'] else ''}</p>
</div></div></section>'''

# ---------------------------------------------------------------- 子项
def s_head(no, title, score, status, status_kind='ok'):
    return f'''<div class="sec-h"><span class="no">{no}</span><div><h2>{title}
    <span class="badge {status_kind}">{status}</span></h2></div></div>'''

def kpi(items):
    return '<div class="kpis">' + ''.join(f'<div class="kpi"><span>{k}</span><b style="color:{c}">{v}</b></div>' for k, v, c in items) + '</div>'

def formula(lines):
    return '<pre class="formula">' + '\n'.join(lines) + '</pre>'

S_MCL = f'''<section class="sec ind" id="s2">{s_head('01','MCL 麦克连摆','100',f"{len(D['series']['mcl'])}个交易日 · 含ST")}
{kpi([('午盘预览 · 11:30', (num(PREV['mcl']) if PREV else '—'), '#b3372c'), (f'收盘 · {ASOF_S}', num(S['mcl_last']), '#5f5b52'), ('近200日分位（收盘）', f'{T["pct_mcl"]:.0f}', '#5c7f96'), (f'{len(D["series"]["mcl"])}日极值', f'{num(S["mcl_min"])} / +{S["mcl_max"]:,.0f}', '#5f5b52')])}
<div class="legend"><i class="ln" style="background:#b3372c"></i>MCL = EMA19(A−D) − EMA39(A−D)<span class="lg-note">浅灰区＝EMA 初始化影响段，分位计算已跳过</span></div>
<div class="chart" id="c-mcl" style="height:320px"></div>
<div class="cols">
  <div><h4>公式与口径</h4>{formula(['X_t = A_t − D_t','EMA19 = 0.10·X_t + 0.90·EMA19(t−1)','EMA39 = 0.05·X_t + 0.95·EMA39(t−1)','MCL  = EMA19 − EMA39'])}
  <p>源码见 [41] 04:40 通达信编辑器，参数 N1=19、N2=39。数据为 iFinD「A股涨跌家数统计」报表，沪深A股含ST，2025-09-01 至 {ASOF} 共 {len(D['series']['mcl'])} 日；首值初始化，前 200 次递推为预热段。</p></div>
  <div><h4>怎么读</h4><ul>
    <li><b>MCL&gt;0</b>：19 日净上涨家数均线高于 39 日基线，参与面相对改善；<b>&lt;0</b> 则相反。</li>
    <li><b>从负值回升</b>：恶化速度减慢，不等于已经全面上涨。</li>
    <li><b>指数创新高而 MCL 不跟</b>：可疑的广度背离，需要看组成与后续延续。</li>
    <li><b>MCL&gt;0 ≠ 当天上涨家数更多</b>：11-09 的 A−D 为 −966，但 MCL 为 +74.8，短均线只是没那么负。</li>
  </ul></div>
  <div><h4>怎么用 · 边界</h4><ul>
    <li>只回答“广度动量往哪个方向走、有没有拐”，不单独当买卖信号。</li>
    <li>与涨家占比配对：<b>p 定水平，MCL 定方向</b>。两者同时走弱才是广度实质性恶化。</li>
    <li>含 ST 池与剔 ST 的 TRIN/额价差不是同一个股票池，<b>不能互相校验</b>，也别把两条序列拼起来。</li>
    <li>初始化与预热是工程约定，原始口径未说明；页面上的“37%”是历史分位，不是 MCL=37。</li>
  </ul></div>
</div></section>'''

S_P = f'''<section class="sec ind" id="s3">{s_head('02','涨家占比 p','90',f'{len(D["series"]["p_series"])}个交易日 · 含ST')}
{kpi([(f'{CUR_L} · 含ST',f'{CUR["p"]:.1f}%','#b3372c'),(f'{ASOF_S} 收盘 · 含ST 序列',f'{D["series"]["p_series"][-1][1]:.1f}%','#8d8779'),('当日分位',f'{T["pct_p_cur"]:.0f}','#5c7f96'),(f'{len(D["series"]["p_series"])}日区间',f'{min(x[1] for x in D["series"]["p_series"]):.1f}% – {max(x[1] for x in D["series"]["p_series"]):.1f}%','#5f5b52')])}
<div class="legend"><i class="ln" style="background:#b9c2c9"></i>单日涨家占比 p<i class="ln" style="background:#31556e"></i>20 日均值<span class="lg-note">单日 p 平均变动 27pp，趋势看 20 日均值</span></div>
<div class="chart" id="c-p" style="height:280px"></div>
<p class="cap">图中序列与当前读数同为<b>含ST池</b>（沪深A股，不含北交所）。2026-11-19 起成交分布也改用同一口径，MCL 与 p/q/TRIN 同池同源，不再维护剔ST的第二套数。</p>
<div class="cols">
  <div><h4>公式与口径</h4>{formula(['p = 100 × A / (A + D)','A＝上涨家数  D＝下跌家数','平盘 U 不进分母'])}
  <p>同源数值反算：4,381/(4,381+1,035)=80.8900%，与公开读数 80.89% 一致。⚠ 2026-11-19 之前 p 有两个池（MCL 含 ST、TRIN/额价差剔 ST）；现统一为含 ST 单池，本页所有读数同池同源，不再做跨池比较。</p></div>
  <div><h4>怎么读</h4><ul>
    <li><b>20% 以下</b>：普跌，参与面极窄；<b>80% 以上</b>：普涨。</li>
    <li>50% 附近为多空均衡，但 A 股极少停在均衡位。</li>
    <li>单日极值常在两日内反转：11-02 的 85.1% → 11-03 的 39.9% → 11-04 的 85.0%。</li>
    <li>近 {len(D['series']['p_series'])} 日单日平均变动 {_p_mae:.1f}pp、最大 {_p_max:.1f}pp，<b>任何单日 p 都必须配均值一起看</b>。</li>
  </ul></div>
  <div><h4>怎么用 · 边界</h4><ul>
    <li>流程第一步：先看 p 判断“参与上涨的股票多不多”，再解释 TRIN。</li>
    <li>用 5 日均值判断趋势，用单日值判断脉冲；两者含义不同。</li>
    <li>它不是指数涨跌幅，也不含平盘；指数被权重股拉动时，p 可以很低。</li>
    <li>原始股票池的剔除规则未公开，同日读数与本看板差 1–2pp（见口径对照）。</li>
  </ul></div>
</div></section>'''

# ---------------------------------------------------------------- 均线广度
def _chg(x):
    if x is None:
        return '—'
    return f'<span class="{"pos" if x > 0 else "neg"}">{x:+.2f}pp</span>'

def _ma_row(n, m):
    rk = '—' if m['pct_rank'] is None else f"{m['pct_rank']:.0f}"
    return (f'<tr><td class="b">MA{n}</td><td>{m["num"]:,}</td><td>{m["den"]:,}</td>'
            f'<td class="b">{m["pct"]:.2f}%</td><td>{_chg(m["chg5"])}</td>'
            f'<td>{_chg(m["chg20"])}</td><td>{rk}</td></tr>')

ma_rows = ''.join(_ma_row(n, MP[str(n)]) for n in (20, 60, 250))
_p20r = '—' if P20['pct_rank'] is None else f"{P20['pct_rank']:.0f}"
_gap = P20['pct'] - P250['pct']
_new = P20['den'] - P250['den']
_ma_desc = ('短期修复领先长期，但两者都在低位。' if _gap > 0
            else '短期已跌破长期趋势，属于新一轮破位。')

S_MA = f'''<section class="sec ind" id="s4">{s_head('03','站上均线比例 P20 / P60 / P250','100',f"{MA['days']}个交易日 · 逐日选股计数")}
{kpi([(f'P20 · {MA["last_date"][5:]}',f'{P20["pct"]:.2f}%','#31556e'),('P60',f'{P60["pct"]:.2f}%','#5c7f96'),('P250',f'{P250["pct"]:.2f}%','#8d8779'),('P20 分位',_p20r,'#c08b3e')])}
<div class="legend"><i class="ln" style="background:#31556e"></i>P20 站上 20 日线<i class="ln" style="background:#5c7f96"></i>P60<i class="ln" style="background:#c08b3e"></i>P250<span class="lg-note">虚线＝20% / 50% / 80% 参考位</span></div>
<div class="chart" id="c-ma" style="height:300px"></div>
<div class="table-wrap"><table class="tb"><thead><tr><th>周期</th><th>站上家数</th><th>有效分母</th><th>占比</th><th>5 日变化</th><th>20 日变化</th><th>分位</th></tr></thead>
<tbody>{ma_rows}</tbody></table></div>
<p class="cap">分母是“该周期有足够日K”的股票数：MA20 的 {P20["den"]:,} 只与 MA250 的 {P250["den"]:,} 只相差 <b>{_new:,}</b> 只，差的就是上市不足 250 个交易日的新股——它们不参与 MA250 的计算，也不该进它的分母，所以三条线的分母本来就不同。</p>
<div class="cols">
  <div><h4>公式与口径</h4>{formula(['Pₙ = 100 × N(C > MAₙ) / N(MAₙ 有效)','','MAₙ = 最近 n 个交易日收盘价的简单平均','分子：选股「收盘价 > n日简单移动平均线」','分母：选股「n日简单移动平均线 > 0」','       └ 均线为空即无值，不会 >0'])}
  <p>严格大于，等于不算。每个交易日、每个周期各两次选股计数，共 6 次调用，<b>不下载任何逐股价格</b>。日期必须写成「2026年11月17日」这种中文格式，写成「2026-11-17收盘时…」会被打回分时均线口径。</p></div>
  <div><h4>怎么读</h4><ul>
    <li><b>P250 最慢</b>：还有多少股票没跌破年线，反映长期趋势的存量。</li>
    <li><b>P20 最快</b>：最近一个月的位置；<b>P60</b> 居中。</li>
    <li>层间差 P20−P250 现在是 <b>{_gap:+.2f}pp</b>：{_ma_desc}</li>
    <li>同一天 p 是“今天多少股票在涨”，P20 是“多少股票还在月线上”；<b>p 高而 P20 低＝单日反弹没改趋势</b>。</li>
    <li>三条线同处低位且同向下行＝全面弱势；P20 先转向、P60/P250 未动＝修复初期。</li>
  </ul></div>
  <div><h4>怎么用 · 边界</h4><ul>
    <li>慢变量，按周/月看，<b>不当日内信号</b>。它进的是广度温度的第三个分项，不是交易触发线。</li>
    <li>读数是 iFinD 选股的条件计数，<b>供应商侧筛选结果，未逐股复算</b>；已用三只个股做双向抽查（见底稿）。</li>
    <li>不复权口径：除权日附近个别股票会翻转，对总占比的影响通常在 0.1pp 量级以内。</li>
    <li>分母随新股上市逐年增大，<b>跨月只能比比例，不能比家数</b>。</li>
    <li>历史仅 {MA["days"]} 个交易日（2025-09 起），分位窗口 {T["window"]} 日，早于窗口的读数不做外推。</li>
  </ul></div>
</div></section>'''

OBS_ROWS = ''.join(
    f'<tr><td>{o["date"]}</td><td>{"11:30 盘中" if o["kind"] == "noon" else "15:00 收盘"}</td>'
    f'<td>{o["p"]:.1f}%</td><td>{o["q"]:.1f}%</td>'
    f'<td class="{"pos" if o["G"]>0 else "neg"}">{o["G"]:+.2f}</td><td>{o["trin"]:.3f}</td></tr>'
    for o in D['obs'])

S_TRIN = f'''<section class="sec ind" id="s5">{s_head('04','成交分布：TRIN 与额价差','95',f'近一周 {len(D["obs"])} 个观测 · 盘中＋收盘','ok')}
{kpi([(f'TRIN_E · {CUR_S}',f'{CUR["trin_e"]:.3f}','#1f6b52'),('额价差',f'{CUR["G"]:+.2f}pp','#c08b3e'),('涨额占比 q',f'{CUR["q"]:.1f}%','#b3372c'),('涨家占比 p',f'{CUR["p"]:.1f}%','#5c7f96')])}
<div class="grid2">
  <div><div class="sub-h">涨家占比 p 与涨额占比 q（同一时点两把尺）</div>
    <div class="legend"><i class="ln" style="background:#31556e"></i>涨家占比 p<i class="ln" style="background:#b3372c"></i>涨额占比 q
    <span class="lg-note">x 轴：日期＋午/收</span></div>
    <div class="chart" id="c-obs" style="height:250px"></div></div>
  <div><div class="sub-h">p–G 象限：近一周观测点的位置（深色＝最新）</div><div class="chart" id="c-quad" style="height:250px"></div></div>
</div>
<div class="table-wrap"><table class="tb"><thead><tr><th>日期</th><th>时点</th><th>涨家占比 p</th><th>涨额占比 q</th><th>额价差 pp</th><th>TRIN_E</th></tr></thead>
<tbody>{OBS_ROWS}</tbody></table></div>
<p class="cap">近 5 个交易日的<b>盘中与收盘两组读数</b>，同日两行便于看日内到收盘的收敛方向。11-19 起为扶摇快照（含ST，与 MCL 同池、同源）；11-18 及以前为 iFinD/Wind（剔ST），属历史序列断点，跨这两段只比方向、不做数值对齐。</p>

<div class="explain">
  <div class="ex-h"><span>概念</span><h3>额价差到底在说什么</h3></div>
  <p class="ex-lead">一句话：<b>涨的那批股票，拿到的成交额份额，比它们的家数份额多几个百分点。</b></p>
  <p class="ex-note">资金温度这一条腿，独立信息只有这一条：涨额占比 q、额价差 G、TRIN_E 在给定 p 后互为函数，同源不重复计票。所以资金温度实质是<b>单指标映射</b>，不是多指标合成。</p>
  <div class="ex-grid">
    <div><h5>等价换算</h5><p>G&gt;0 ⇔ TRIN_E&lt;1 ⇔ <b>上涨组每只股票的平均成交额高于下跌组</b>。倍数＝1÷TRIN_E，{CUR_S} 是 <b>{1/CUR['trin_e']:.2f} 倍</b>。反过来，G={CUR['G']:+.2f}pp 就是“涨股均额多拿 {(1/CUR['trin_e']-1)*100:.0f}%”。</p></div>
    <div><h5>它不是什么</h5><p>不是涨跌幅之差，不是资金净流入，不是主动买卖差，也没有机构身份。它只是<b>同一时点两组股票的份额对比</b>。</p></div>
    <div><h5>量纲陷阱</h5><p>G 的可取范围随 p 变化：<b>[−100p, +100(1−p)]</b>。p=90% 时上限只有 +10pp，同样“+5pp”在 p=20% 与 p=90% 下含义完全不同。所以本看板看“占理论上限的比例”——{CUR_S} 的 {CUR['G']:+.2f}pp 占 <b>{100*CUR["G"]/T["g_max"]:.0f}%</b>。</p></div>
  </div>
</div>

<div class="cols">
  <div><h4>公式与口径</h4>{formula(['TRIN_E = (A/D) ÷ (E⁺/E⁻)','       = (E⁻/D) ÷ (E⁺/A)','         └ 跌组每只均额 ÷ 涨组每只均额','','额价差 G = 100 × (q − p)   [百分点]','q = E⁺ / (E⁺+E⁻)'])}
  <p>代码约定：金额为零的记录剔除；平盘保留但两组都不进入；A 或 D 为零、任一组成交额为零时 TRIN 留空，不制造无穷大。单位是<b>百分点</b>：+2.43pp＝242 个基点，不是 2.43 个基点。</p></div>
  <div><h4>怎么读</h4><ul>
    <li><b>TRIN&lt;1</b>：上涨组每只股票平均成交额更大；<b>&gt;1</b> 则相反。</li>
    <li>给定 p 时，TRIN、q、G <b>互为函数</b>，是同一个模块，不能重复计票。</li>
    <li>极端行情下 G 会机械归零：全涨或全跌时没有对照组，<b>0 不代表中性</b>。</li>
    <li>一只权重股就能改变整组均值，所以要配 p 与成交额集中度一起看。</li>
  </ul></div>
  <div><h4>怎么用 · 边界</h4><ul>
    <li>用途只有一个：判断<b>成交额有没有跟上参与面</b>。低 p + 正 G＝抱团；高 p + 负 G＝反弹待确认。</li>
    <li>它是按当天红绿盘把整只股票的量额分组，<b>不是主动买卖、不是机构净流入</b>，没有账户身份。</li>
    <li>0.7 / 0.6 / 0.5 / 0.9 等阈值是经验值，本轮<b>未验证其稳定性</b>，不设为通用买卖线。</li>
    <li>历史只有单日截面，尚未形成连续日序列；列为每日采集待补项。</li>
  </ul></div>
</div></section>'''

S_VW = f'''<section class="sec ind" id="s6">{s_head('05','VW-MACD（沪深300）','100',f'{len(SER["vw_hist"])}根有效日线 + {len(SER["vww_hist"])}根有效周线')}
{kpi([('日线柱',num(S['vw_hist_last'],1,True),'#c08b3e'),('日线 DIF / DEA',f'{num(S["vw_dif_last"],1)} / {num(S["vw_dea_last"],1)}','#b3372c'),('柱体分位',f'{S["vw_hist_pct"]:.0f}','#5c7f96'),('距年内高点',f'{num(S["drawdown"],1)}%','#5f5b52')])}
<div class="sub-h">日线：沪深300收盘点位与成交量加权 MACD（000300.SH）</div><div class="chart" id="c-vwpx" style="height:180px"></div>
<div class="chart" id="c-vwh" style="height:130px"></div>
<div class="sub-h">周线（{len(SER["vww_hist"])} 根有效周K，26 周预热后）</div><div class="chart" id="c-vww" style="height:150px"></div>
<div class="cols">
  <div><h4>公式与口径</h4>{formula(['VWMA_n = Σ(C×V) / ΣV   (最近 n 根K线)','DIF = VWMA12 − VWMA26','DEA = EMA9(DIF)','柱  = 2 × (DIF − DEA)'])}
  <p>原始公式 <code>VC1:=SUM(C*V,SHORT)/SUM(V,SHORT);</code>，参数 12/26/9。标的为<b>沪深300 000300.SH</b>：日线取自 iFinD 指数日线 2025-03-03 起共 417 根，多取的部分用于 EMA 预热；收盘与 Wind 逐日核对一致。26 根之前的 DIF 留空，DEA 自首个有效 DIF 起算。</p></div>
  <div><h4>怎么读</h4><ul>
    <li><b>零轴</b>定多空基调：DIF {num(S["vw_dif_last"],1)}、DEA {num(S["vw_dea_last"],1)} 同时在零轴下方，中期仍是弱势结构。</li>
    <li><b>柱体</b>定动能方向：{_VW_BULLET}</li>
    <li><b>级别要一致</b>：周线 DIF {num(S["vw_week_dif"],1)}、柱 {num(S["vw_week_last"],1)}；最近四根周柱为 {' / '.join(num(x[1],0) for x in SER['vww_hist'][-4:])}，{'仍未转正' if SER['vww_hist'][-1][1] < 0 else '已转正'}。<b>{'日线修复没有传导到周线。' if SER['vww_hist'][-1][1] < 0 else '周线与日线同向。'}</b></li>
    <li>价格新高而 DIF 不新高＝量价背离，这才是它相对普通 MACD 的信息量所在。</li>
  </ul></div>
  <div><h4>怎么用 · 边界</h4><ul>
    <li>与广度对照使用：<b>价格动能修复而广度仍弱</b>＝反弹质量存疑；<b>两者同向走弱</b>＝弱势延续。{ASOF} 的状态是：{_VW_STATE}。</li>
    <li>标的选择决定读数：沪深300 距 {S["close_max_date"]} 高点 {num(S["close_max"],0)} 回撤 {num(S["drawdown"],1)}%；换成中证全指会更深（中小盘权重更大）。跨标的不可直接比数值。</li>
    <li>它是价格技术指标，只用了指数自身的价与量，不含任何资金流信息。</li>
    <li>周线里 12/26/9 是“周”不是“日”；周线预热需 26 周，当前有效 {len(SER["vww_hist"])} 根。</li>
  </ul></div>
</div></section>'''

# ---------------------------------------------------------------- 期货基差
FUT = D['fut']
FIF, FIC, FIM = FUT['IF'], FUT['IC'], FUT['IM']
_fut_avg_pct = (FIF['pct'] + FIC['pct'] + FIM['pct']) / 3


def _fut_row(tag, m):
    return (f'<tr><td class="b">{tag}</td><td>{m["contract"]}</td><td>{m["days"]}</td>'
            f'<td>{m["fut"]:,.1f}</td><td>{m["idx"]:,.1f}</td>'
            f'<td class="{"neg" if m["basis"] < 0 else "pos"}">{m["basis"]:+.2f}</td>'
            f'<td class="{"neg" if m["rate"] < 0 else "pos"}">{m["rate"]:+.2f}%</td>'
            f'<td class="b {"neg" if m["ann"] < 0 else "pos"}">{m["ann"]:+.2f}%</td>'
            f'<td>{m["pct"]:.0f}</td><td>{m["chg5"]:+.1f}pp</td></tr>')


fut_rows = (_fut_row('IF · 沪深300', FIF) + _fut_row('IC · 中证500', FIC)
            + _fut_row('IM · 中证1000', FIM))

S_FUT = f'''<section class="sec ind" id="s7">{s_head('06','股指期货基差与年化升贴水','100',f'{len(SER["fut_ann_IF"])}个交易日 · IF / IC / IM')}
{kpi([('IF 年化', f'{FIF["ann"]:+.1f}%', '#31556e'), ('IC 年化', f'{FIC["ann"]:+.1f}%', '#5c7f96'),
      ('IM 年化', f'{FIM["ann"]:+.1f}%', '#c08b3e'), ('三品种平均分位', f'{_fut_avg_pct:.0f}', '#b3372c')])}
<div class="legend"><i class="ln" style="background:#31556e"></i>IF 沪深300<i class="ln" style="background:#5c7f96"></i>IC 中证500<i class="ln" style="background:#c08b3e"></i>IM 中证1000<span class="lg-note">负值＝期货贴水，零轴以上为升水</span></div>
<div class="chart" id="c-fut" style="height:300px"></div>
<div class="table-wrap"><table class="tb"><thead><tr><th>品种</th><th>主力合约</th><th>剩余自然日</th><th>期货</th><th>现货</th><th>基差(点)</th><th>基差率</th><th>年化</th><th>200日分位</th><th>5日变化</th></tr></thead>
<tbody>{fut_rows}</tbody></table></div>
<p class="cap">三品种全部为贴水，且贴水处在近一年的底部区间：IF 的分位 {FIF["pct"]:.0f}、IC {FIC["pct"]:.0f}、IM {FIM["pct"]:.0f}（0＝一年来最深）。IC/IM 的贴水历来比 IF 深，因为中性策略与雪球等产品的对冲盘集中在中小盘；<b>三个品种之间的相对高低比绝对水平更有信息量</b>。</p>
<div class="cols">
  <div><h4>公式与口径</h4>{formula(['基差(点)   = 期货主力收盘 − 指数收盘','基差率     = 基差 ÷ 指数收盘','年化基差率 = 基差率 × 365 ÷ 剩余自然日','分位       = 过去 200 个交易日的中位秩','主力       = 当日成交量最大、且剩余 5–130 日的合约'])}
  <p>年化用<b>自然日 365</b>，不是交易日 250；分母是“到期日 − 当日”的自然日差。期货取日线收盘，现货取同日指数收盘。剩余自然日不足 10 日的合约不做年化：分母太小时，同样的基差点数会被放大成几倍的假信号。</p></div>
  <div><h4>怎么读</h4><ul>
    <li><b>负值＝贴水</b>：期货比现货便宜。持有期货到期可少付这部分，本质是空头/对冲方愿意付的“保险费”。</li>
    <li><b>年化</b>把不同到期日拉平：同样是 −50 点，剩 30 天是 −14%/年，剩 90 天只有 −4.7%/年。</li>
    <li><b>分位</b>看相对位置：当前 IF 的分位是 {FIF["pct"]:.0f}（0＝一年来最深），说明贴水不只是绝对数字大，而是比过去一年都极端。</li>
    <li>贴水收敛（年化从 −17% 回到 −5%）＝空头平仓或套保盘撤退，常与反弹同步；贴水继续加深＝对冲需求还在加码。</li>
    <li>三个品种背离时看结构：IM 贴水明显浅于 IC＝资金对小微盘的悲观程度反而更低。</li>
  </ul></div>
  <div><h4>怎么用 · 边界</h4><ul>
    <li><b>不是方向指标</b>：深度贴水可以维持数月，单看它做多空会被埋。</li>
    <li>换月会带来台阶：主力在季月到期后跳到下一个季月，剩余天数从 25 天跳到 90 天左右，年化可能出现 5–10pp 的一次性跳变。</li>
    <li><b>未做分红调整</b>：5–7 月分红季，指数除息会让贴水自然加深，这段的年化不宜与冬季直接比。</li>
    <li>用的是收盘价，不含盘中；到期日按“合约月第三个星期五”计算，遇节假日顺延的年份可能与交易所公告差一天。</li>
    <li>本模块<b>不进综合温度</b>：它与额价差同属“资金/情绪”家族，同时计票会重复计算。</li>
    <li><b>分位方向</b>按“年化值越高（越接近平水/升水）分位越高”计算，0＝一年来贴水最深。公开表里分位方向未明示，若按“贴水越深分位越高”记，读数需取 100−当前分位。</li>
  </ul></div>
</div></section>'''

S_ETF = f'''<section class="sec ind" id="s8">{s_head('07','三只宽基 ETF 合计成交额','100',f'{len(SER["etf_amt"])}个有效交易日')}
{kpi([(f'{D["series"]["etf_amt"][-1][0][5:]} 合计',f'{D["series"]["etf_amt"][-1][1]:.1f} 亿','#31556e'),('20 日均额',f'{D["series"]["etf_ma20"][-1][1]:.1f} 亿','#5f5b52'),('当前/均额',f'{S["etf_ratio_last"]:.2f}','#3c8f6e'),('历史分位',f'{S["etf_ratio_pct"]:.0f}','#5c7f96')])}
<div class="legend"><i class="ln" style="background:#31556e"></i>三只 ETF 合计成交额（亿元）<i class="ln dashed" style="background:#c08b3e"></i>MA20</div>
<div class="chart" id="c-etf" style="height:250px"></div>
<div class="cols">
  <div><h4>公式与口径</h4>{formula(['TOTAL_t = [AMOUNT(510300) + AMOUNT(510050)','          + AMOUNT(588000)] / 1e8','MA20 = 最近20个交易日均值'])}
  <p>原始定义，单位亿元。只含沪深300、上证50、科创50 这三只，<b>不是所有宽基 ETF 的汇总</b>，也不含申赎数据。</p></div>
  <div><h4>怎么读</h4><ul>
    <li>高于 MA20：宽基层面活跃度提升；低于 MA20：缩量。</li>
    <li>当前 {S["etf_ratio_last"]:.2f}（分位 {S["etf_ratio_pct"]:.0f}），{'低于' if S['etf_ratio_last'] < 1 else '高于'} 20 日均额，{'与“无增量资金”的判断一致' if S['etf_ratio_last'] < 1 else '宽基层面有增量'}。</li>
    <li>历史上 {S["etf_above_share"]:.1f}% 的交易日高于 MA20，所以 {S["etf_ratio_last"]:.2f} {'属于偏低但不算极端' if S['etf_ratio_last'] < 1 else '属于偏高'}。</li>
  </ul></div>
  <div><h4>怎么用 · 边界</h4><ul>
    <li>用途是<b>观察活跃度</b>，以及反驳“宽基 ETF 放量＝国家队进场”——这条指标本身就是用来做证伪的。</li>
    <li>二级市场成交额既不含申购赎回，也不含投资者身份，<b>推不出任何机构行为</b>。</li>
    <li>午盘总额与全日均额不可直接比较，跨时点比较必须先统一口径。</li>
  </ul></div>
</div></section>'''


S_TURN = f'''<section class="sec ind" id="s9">{s_head('08','换手率 &gt; 5% 的股票占比','75',f'{TRJ["days"]}个交易日 · 逐日选股计数')}
{kpi([(f'{TRJ["date"][5:]} 收盘',f'{TRJ["pct"]:.2f}%','#b3372c'),('家数',f'{TRJ["n5"]:,} / {TRJ["nb"]:,}','#5f5b52'),('20 日均值',_tr_ma,'#5c7f96'),('历史分位',_tr_rk,'#c08b3e')])}
<div class="legend"><i class="ln" style="background:#b3372c"></i>换手率&gt;5% 占比<span class="lg-note">分母＝当日换手率大于 0 的沪深A股（剔ST、剔北交所）</span></div>
<div class="chart" id="c-turn-trend" style="height:260px"></div>
<div class="sub-h">{D['turnover_dist']['date'][5:] if D.get('turnover_dist') else EOD_S} 换手率分布（{D['turnover_dist']['total']:,} 只，选股计数）</div>
<div class="chart" id="c-turn" style="height:200px"></div>
<div class="cols">
  <div><h4>公式与口径</h4>{formula(['H5 = 100 × N(τ > 5%) / N(τ > 0)','τ = 成交股数 ÷ 流通A股股本'])}
  <p>原始表述：“所有换手率在 5% 以上的票子占整个市场的比例”。股本口径为<b>普通换手率（流通A股）</b>；分母只计当日有成交的股票，停牌与零成交不进分母，因此与该日“涨家占比”的 A+D 分母不同。序列由选股计数逐日取，每个交易日 2 次调用；在 {EOD_S} 与逐股复算完全一致（{EOD["h5_count"]:,}/{EOD["n"]:,}＝{EOD["h5_pct"]:.2f}%）。</p></div>
  <div><h4>怎么读</h4><ul>
    <li>高值是<b>交易活跃</b>，不必然看多；极端高换手常出现在题材发酵或派发阶段。</li>
    <li>当前 {TRJ["pct"]:.2f}% 的含义是：每 {100/TRJ["pct"]:.1f} 只股票就有 1 只当日换手超过 5%，博弈强度不低。</li>
    <li>20 日均值 {_tr_ma}、单日 {TRJ["pct"]:.2f}%，{_tr_cmp}。</li>
    <li>与广度收缩并存时，说明资金在做<b>结构性换手</b>，而非全面加仓。</li>
  </ul></div>
  <div><h4>怎么用 · 边界</h4><ul>
    <li>作为次级活跃度指标，<b>不进综合温度</b>。</li>
    <li>下方柱状图是 {D['turnover_dist']['date'][5:] if D.get('turnover_dist') else EOD_S} 的分桶家数，由选股计数逐桶取（9 次调用），与逐股快照在 {EOD_S} 的九桶完全一致（317/926/1579/810/718/384/158/95/40）。<b>它是单日截面，趋势看上面那条线。</b></li>
    <li>午盘口径是“截至 11:30 已换手超 5%”，与全日不可比，<b>不能把上午量乘 2 估全天</b>，也不能把阈值折半。</li>
    <li>换手率字段来自供应商，未逐股用当日流通A股复算，标记为待核。</li>
  </ul></div>
</div></section>'''

S_SKIP = f'''<section class="sec" id="s11"><div class="sec-h"><span class="no">未纳入</span><div><h2>三项没有进温度计，以及原因</h2>
<p>“能复现公式”“能逐点复现曲线”“能预测涨跌”是三件事。以下三项在当前数据条件下无法给出可信读数，故不纳入，也不做替代性近似。</p></div></div>
<div class="skip-grid">
  <div class="skip"><div class="skip-h"><b>综合评分</b><span class="badge bad">证据分 0</span></div>
    <p>原始体系展示过 0–100 的评分与各指标分位，但权重、窗口、样本构造均未公开。用等权或任何自拟权重去“还原”，得到的只是另一套模型。<span class="hl">本看板的温度是显式等权的两条腿合成，不是外部评分。</span></p></div>
  <div class="skip"><div class="skip-h"><b>PCR（期权）</b><span class="badge bad">底层缺失</span></div>
    <p>只确认了“ETF＋期货期权加权”的结构与 BB 20 2 的轨道参数，产品名单、成交量/持仓量/金额口径、权重均未公开。缺底层序列就无法计算，不做代理。</p></div>
  <div class="skip"><div class="skip-h"><b>市值/GDP</b><span class="badge warn">缺数据</span></div>
    <p>原始资料只给了 1.00 高估 / 0.70 低估 / 0.50 极度低估三条分位线，未给口径与更新频率；本工作区也没有对应的全市场总市值与 GDP 序列。</p></div>
</div></section>'''

# ---------------------------------------------------------------- 结构分解
SQ = D['size']['quintiles']
sq_rows = ''.join(f'''<div class="sq-row"><span class="sq-l">{q['label']}</span>
  <div class="sq-bar"><i style="width:{q['up_pct']:.1f}%"></i><em>{q['up_pct']:.1f}%</em></div>
  <span class="sq-m">{q['mcap_lo']/1e8:.0f}–{q['mcap_hi']/1e8:.0f}亿 · 中位 {q['med_ret']:+.2f}%</span></div>''' for q in SQ)

# 结构章节的成交额对照：官方两市合计取同一快照日，不用硬编码的外部数字（会随日期漂移）
_mkt_map = dict(D['series'].get('mkt_amt') or [])
_amt_snap = _mkt_map.get(META['eod_date'])
_amt_note = (f'同日沪深京两市合计 {_amt_snap * 1e4:,.0f} 亿元；差额来自池子口径（本节剔除 ST/停牌）与平盘个股。'
             if _amt_snap else '')

S_STRUCT = f'''<section class="sec" id="s10"><div class="sec-h"><span class="no">结构</span><div><h2>{META['eod_date']} 的钱去了哪里</h2>
<span class="badge warn">{META['eod_date']} 逐股快照</span>
<p>同一天拆开看：下跌是全面的，但不同市值组的跌幅与上涨比例差异明显。这一层解释了“指数跌幅小于个股中位跌幅”的背离。
  <b>本节需要逐股明细，停在最近一次取到快照的 {META['eod_date']}</b>；取不到的日子里它不更新，其余模块照常。涨跌家数、均线广度、换手率占比与分布、ETF、期货基差都不依赖逐股明细，已更新到 {EREF['date']} 收盘。</p></div></div>
<div class="grid2 wide">
  <div><div class="sub-h">按流通市值五等分：上涨家数占比</div>{sq_rows}
    <p class="cap">最大的一组上涨占比 {SQ[0]['up_pct']:.1f}%，最小的一组仅 {SQ[-1]['up_pct']:.1f}%；中位涨跌幅从 {SQ[0]['med_ret']:+.2f}% 递减到 {SQ[-1]['med_ret']:+.2f}%。市值由“不复权收盘价 × 当日成交股数/换手率”推算，仅用于分组，不作精确市值。</p></div>
  <div><div class="sub-h">成交额集中度</div>
    <div class="conc">
      <div><b>{CR['10']:.1f}%</b><span>前 10 只</span></div>
      <div><b>{CR['50']:.1f}%</b><span>前 50 只</span></div>
      <div><b>{CR['100']:.1f}%</b><span>前 100 只</span></div>
    </div>
    <p class="cap">前 10 只股票占全市场成交额 {CR['10']:.1f}%，前 100 只占 {CR['100']:.1f}%。集中度本身没有方向，需与 p、额价差一起读：<b>集中度高 + p 低 = 抱团</b>。</p>
    <div class="callout">本节股票池 {EOD['n']:,} 只合计成交额 {EOD['total_amt']/1e8:,.0f} 亿元。{_amt_note}</div>
  </div>
</div></section>'''

# ---------------------------------------------------------------- 口径对照
CMP = [
 ('MCL 公式','EMA19(A−D) − EMA39(A−D)，N1=19 / N2=39',f'同式，{len(D["series"]["mcl"])}日，含ST沪深A股','公式一致；初始化与股票池是本轮工程约定','ok'),
 ('MCL 判读','历史分位（公开读数 37%）＋绝对水平与“转负”标注','近200日自算分位＋绝对水平','分位窗口未公开→研究版，不能称“原分位”','warn'),
 ('TRIN 成交额版','(A/D)/(E⁺/E⁻)，公开定义＋终端输出','同式，沪深A股含ST，不含北交所','公式一致；2026-11-19 起与 MCL 同池','ok'),
 ('额价差','涨额占比 − 涨家占比，单位百分点','同式，单位 pp','完全一致','ok'),
 ('VW-MACD','SUM(C*V,n)/SUM(V,n)，12/26/9',f'同式，标的为沪深300 000300.SH（{len(SER["vw_hist"])}根有效日线＋{len(SER["vww_hist"])}根周线）','公式一致；标的按需求指定，换标的会改变读数','warn'),
 ('三只 ETF','510300+510050+588000，/1e8，MA20',f'同式，{len(SER["etf_amt"])}个有效交易日','一致','ok'),
 ('站上均线比例','P20 / P60 / P250',f'同式同周期，{MA["days"]}日逐日选股计数','公式与周期一致；口径差异：剔除ST/北交所（原始口径未公开），除权边界个别翻转','ok'),
 ('换手率&gt;5%','定义可数学化，股本口径未给','普通换手率＝成交股数/流通A股','口径补齐（你已确认）','ok'),
 ('综合评分','0–100，权重与样本未公开','不复制；改为显式等权温度','方法不同，不可与外部评分比数值','bad'),
]
cmp_rows = ''.join(f'<tr><td>{a}</td><td class="b">{b}</td><td>{c}</td><td>{d}</td><td><span class="badge {e} sm">{"一致" if e=="ok" else "差异" if e=="warn" else "不纳入"}</span></td></tr>' for a, b, c, d, e in CMP)

SAME = [
 ('2026-11-13','涨家占比','13.88%','14.42%（未剔ST）','池子更宽，多 0.54pp'),
 ('2026-11-13','涨额占比','23.12%','23.12%','完全一致'),
 ('2026-11-16','涨家占比','20.75%','22.08%（剔ST）/ 21.63%（含ST）','差 1.3pp，来自股票池'),
 ('2026-11-16','涨额占比','24.47%','24.51%','差 0.04pp'),
 ('2026-11-16','成交额 TRIN','0.81','0.873','家数口径差异传导'),
 ('2026-11-16','MCL','−203.9','−183.6','约 10%，同向'),
]
same_rows = ''.join(f'<tr><td>{a}</td><td>{b}</td><td class="b">{c}</td><td>{d}</td><td>{e}</td></tr>' for a, b, c, d, e in SAME)

S_CMP = f'''<section class="sec" id="s12"><div class="sec-h"><span class="no">对照</span><div><h2>与原始定义的差异</h2>
<p>本实现与公开原始定义的差别集中在<b>股票池、初始化、分位窗口</b>三处；纯公式本身基本没有改动。</p></div></div>
<div class="table-wrap"><table class="tb"><thead><tr><th style="width:16%">项目</th><th style="width:26%">原始定义</th><th style="width:26%">本看板实现</th><th>差异性质</th><th style="width:8%">判定</th></tr></thead><tbody>{cmp_rows}</tbody></table></div>
<div class="sub-h" style="margin-top:28px">同日读数交叉验证（同一日期，两种口径）</div>
<div class="table-wrap"><table class="tb"><thead><tr><th>日期</th><th>字段</th><th>外部读数</th><th>本看板读数</th><th>判读</th></tr></thead><tbody>{same_rows}</tbody></table></div>
<p class="cap">涨额占比两次几乎完全重合（23.12 / 24.51 对 24.47），说明<b>成交额分组口径基本一致</b>；差异集中在涨跌家数，指向股票池（是否含 ST/北交所）。这既是复现证据，也是“不能逐点复刻原图”的直接原因。</p></section>'''

WORKFLOW = f'''<section class="sec" id="s13"><div class="sec-h"><span class="no">流程</span><div><h2>每天六步，十分钟</h2>
<p>顺序不能颠倒：先确认数据可用，再分别看广度与成交，最后看延续性与结构。</p></div></div>
<ol class="steps">
  <li><b>核对数据</b><span>股票池家数、时间戳、缺失率、A+D+U 合计是否闭合。</span></li>
  <li><b>看广度水平</b><span>涨家占比 p：今天有多少股票在涨。用 20 日均值判断趋势，单日值只当脉冲；再用 P20/P60/P250 看趋势层站在哪。</span></li>
  <li><b>看广度动量</b><span>MCL：参与面相对 39 日基线是在改善还是恶化；与 p 背离时以动量为先。</span></li>
  <li><b>看成交分布</b><span>TRIN_E 与额价差（同一个模块，二选一）：成交额有没有跟上参与面。</span></li>
  <li><b>看结构与活跃度</b><span>规模分组、成交额集中度、ETF 活跃度、换手率，回答“钱去了哪里”。</span></li>
  <li><b>看延续与动能</b><span>同一读数连续 3 日以上才谈趋势；再对照 VW-MACD 的日线与周线是否同向。</span></li>
</ol>
<div class="cols two">
  <div><h4>推荐的记录句式</h4><p class="quote">“涨家占比 X%，涨额占比 Y%，额价差 Z 个百分点；MCL 从 A 变为 B；站上 MA20 / MA60 / MA250 分别为 P/Q/R%。成交分布与参与面的组合为〔抱团／进攻／冰点／待确认〕；VW-MACD 日线柱为〔正／负〕、周线柱为〔正／负〕。”</p></div>
  <div><h4>不要写的四句话</h4><ul class="no">
    <li>“聪明钱已进场” —— 没有账户身份字段。</li>
    <li>“TRIN 低于某值必然反转” —— 阈值未验证，且有反例。</li>
    <li>“柱体转正就是见底” —— 只说明下跌动能衰减，不等于上涨开始。</li>
    <li>“温度 X 分，所以明天涨” —— 温度描述状态，不预测收益率。</li>
  </ul></div>
</div></section>'''

STATUS = [
 ('MCL 底库（含ST）', 'data/store/breadth_daily.csv', f'{len(D["series"]["mcl"])} 行', 'iFinD 报表口径，日更追加；MCL 每次全量重算 EMA。2026-11-17 为 Wind 回补（A/D 已用 11-16 与 iFinD 对齐验证）', 'ok'),
 ('日终逐股快照', f'data/store/snapshots/eod_{META["eod_date"]}.csv', f'{EOD["n"]:,} 行', '逐股复算与供应商汇总一致', 'ok'),
 ('午盘逐股快照', NOON_SNAP_PATH, f'{NOON["n"]:,} 行', NOON_SNAP_NOTE, 'ok'),
 ('成交分布观测日志', 'data/store/daily_agg.csv', f'{len(D["obs"])} 条近期', '每次更新追加一行，含 p/q/TRIN/额价差', 'ok'),
 ('均线广度 P20/60/250', 'data/store/ma_breadth.csv', f'{MA["days"]} 日 × 3', '逐日两次选股计数（分子/分母）；与三只个股双向抽查一致；供应商筛选值，未逐股复算', 'ok'),
 ('沪深300日线', 'data/store/index_daily.csv', f'{len(SER["vw_close"])} 行', 'iFinD 指数日线（2025-03 起，多取 40 根做预热）；收盘与 Wind 逐日核对一致；VW-MACD 自算', 'ok'),
 ('股指期货基差', 'data/store/futures_basis.csv', f'{len(SER["fut_ann_IF"])} 日 × 3', '逐合约日线（成交量选主力，限 5–130 日）；11-02 一行与公开表对照：基差 −42.12、年化 −8.32% 完全吻合', 'ok'),
 ('两市合计成交额（沪深京）', 'data/store/market_amount.csv', f'{AMT["days"]} 行', 'iFinD 板块 001005010 全部A股；11-16 为 1.4942 万亿，与逐股快照汇总 1.4939 万亿相差 30 亿以内', 'ok'),
 ('三只 ETF 合计', 'data/store/etf_daily.csv', f'{len(SER["etf_amt"])} 行', '日更追加，MA20 每次现算', 'ok'),
 ('换手率&gt;5% 占比', 'data/store/turnover_daily.csv', f'{TRJ["days"]} 日', '选股计数（2 次/日）；11-16 与逐股复算一致 677/5,027', 'ok'),
 ('换手率分布（9 桶）', 'data/store/turnover_dist.csv', f'{(D["turnover_dist"]["total"] if D.get("turnover_dist") else 0):,} 只/日', '选股计数（9 次/日）；九桶与逐股快照完全一致', 'ok'),
 ('市值结构', '日终逐股快照的 turnover_pct / 收盘价', f'{EOD["n"]:,} 行', '需逐股明细，仅快照日可算', 'warn'),
]
st_rows = ''.join(f'<tr><td>{a}</td><td class="mono">{b}</td><td>{c}</td><td>{d}</td><td><span class="badge {e} sm">{"可用" if e=="ok" else "有限"}</span></td></tr>' for a, b, c, d, e in STATUS)

S_STATUS = f'''<section class="sec" id="s14"><div class="sec-h"><span class="no">底稿</span><div><h2>数据血缘与验收状态</h2>
<p>每一项都能回溯到工作区里的原始文件；标“有限”的表示只可用于量级与方向，不可用于阈值或回测。</p></div></div>
<div class="table-wrap"><table class="tb"><thead><tr><th style="width:17%">数据项</th><th style="width:34%">文件</th><th style="width:13%">规模</th><th>验收说明</th><th style="width:7%">状态</th></tr></thead><tbody>{st_rows}</tbody></table></div>
<div class="fresh-wrap" id="fresh"><div class="sub-h">各模块的数据时点</div>
<p class="cap" style="margin:0 0 8px">同一天里不同模块可能停在不同日期。这里把每块的数据时点摊开；标“滞后”的表示该模块落后于最近一个已收盘交易日。</p>
{fresh_table}</div>
<p class="cap"><b>自动更新</b>：交易日 17:00 一次（iFinD 按调用次数计费，单日预算 30 次）。广度与成交分布用 <b>{'1 次扶摇全市场快照（含ST家数与涨跌组成交额，不占 iFinD 额度）' if '扶摇' in (META.get('close_source') or '') else '1 次 Wind 查询（含ST家数与涨跌组成交额）'}</b>，均线广度 6 次、换手率占比 2 次、分布 9 桶 9 次、沪深300 日线 1 次、两市成交额 1 次、期货基差 5 次（<code>--fast</code>，只取当月/下月/当季）。逐股接口（小时频，单次 500+ 调用）已退出日常流程，只保留按需人工触发：<code>python3 fetch_eod.py --allow-heavy</code> 用于刷新市值结构与逐股明细（约 520 次调用）。所有写入由 <code>update.py</code> 校验后落盘并重建本页；校验不通过则整次拒绝，不会写入半截数据。手动重建：<code>python3 compute.py &amp;&amp; python3 render.py</code>；查看数据状态与当日调用数：<code>python3 update.py status</code>。温度计与所有分位为<b>本看板自算</b>：分位＝中位秩（小于当前值的个数＋0.5×相等个数）÷窗口长度；窗口 {T['window']} 个交易日。资金温度＝50 + 50 × 额价差 ÷ 给定 p 下的额价差理论上限。广度温度 v2＝涨家占比分位、MCL 分位、P20 分位三者等权（v1 为前两者等权，页内仍并列给出）。综合温度＝广度与资金等权。这些是本看板的显式约定，不是任何外部评分模型。</p></section>'''

FOOT = f'''<footer>
  <div class="ft-l"><b>聪明钱温度计</b><span>数据截止 {META['asof']}（日终）／{META['noon_date']} 11:30（午盘）</span></div>
  <div class="ft-r"><span>数据来源：{META['sources']}</span>
  <span>股票池：MCL {META['universe_mcl']}；宽度/量额 {META['universe_breadth']}</span>
  <span>{('<em>逐股快照截至 ' + META['eod_date'] + '（市值结构用），该类数据自 2026-11-17 起不可回补；换手率分布改用选股计数按日更新，其余日终序列已到 ' + META['asof'] + '。</em>')}</span>
  <span>本页为研究记录，不构成投资建议。指标描述状态，不预测收益率。</span></div>
</footer>'''

# ================================================================ CSS
CSS = r'''
*{box-sizing:border-box;margin:0;padding:0}
:root{--bg:#f7f5f0;--card:#fffefb;--line:#e6e1d5;--line2:#f0ece1;--ink:#22211d;--ink2:#5d584f;--ink3:#8e8879;
--red:#b3372c;--green:#1f6b52;--blue:#31556e;--amber:#c08b3e;--mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace}
html{-webkit-text-size-adjust:100%}
body{background:var(--bg);color:var(--ink);font:15px/1.78 "PingFang SC","Hiragino Sans GB","Microsoft YaHei",system-ui,-apple-system,sans-serif;
-webkit-font-smoothing:antialiased}
.wrap{max-width:1160px;margin:0 auto;padding:0 34px 96px}
.mast{display:flex;justify-content:space-between;align-items:center;padding:22px 0 18px;border-bottom:1px solid var(--line);
font:11.5px/1 var(--mono);letter-spacing:.1em;color:var(--ink3);text-transform:uppercase}
.mast b{color:var(--ink);font-weight:600}
.headline{padding:54px 0 30px;max-width:840px}
h1{font-size:46px;line-height:1.15;font-weight:600;letter-spacing:-.02em}
.headline p{margin-top:16px;color:var(--ink2);font-size:15.5px;max-width:720px}
.headline p.note{font-size:13px;color:var(--ink3);line-height:1.75;margin-top:10px;max-width:700px}
.headline p.note b{color:var(--ink2)}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin-top:20px}
.chips span{font:11.5px/1 var(--mono);letter-spacing:.04em;color:var(--ink2);border:1px solid var(--line);background:#fff;
padding:7px 10px;border-radius:2px}

.nav{display:flex;flex-wrap:wrap;gap:6px 20px;padding:11px 0;border-bottom:1px solid var(--line);position:sticky;top:0;
z-index:20;background:rgba(247,245,240,.96);backdrop-filter:blur(8px);font-size:11.5px;letter-spacing:.02em}
.nav a{color:var(--ink2);text-decoration:none;border-bottom:1px solid transparent;padding-bottom:1px}
.nav a:hover{color:var(--red);border-color:var(--red)}
.sec{scroll-margin-top:58px}
.hero{display:grid;grid-template-columns:330px 1fr;gap:34px;align-items:center;background:var(--card);
border:1px solid var(--line);border-radius:6px;padding:26px 34px 28px}
.gauge{width:100%;height:auto;display:block}
.gauge-cap{text-align:center;font:11px/1 var(--mono);letter-spacing:.14em;color:var(--ink3);margin-top:-6px}
.hero-row{display:flex;align-items:center;gap:12px}
.tag{font-size:12.5px;padding:5px 11px;border:1px solid;border-radius:20px;font-weight:600}
.hero-date{font:11.5px/1 var(--mono);color:var(--ink3);letter-spacing:.05em}
.hero-big{font:600 62px/1.05 var(--mono);letter-spacing:-.03em;margin:10px 0 2px}
.hero-big span{font-size:17px;font-weight:400;letter-spacing:0;margin-left:6px;color:var(--ink3)}
.dataline{display:flex;gap:12px;font:10.5px/1 var(--mono);color:var(--ink3);margin-top:9px;flex-wrap:wrap;align-items:center}
.dataline b{color:var(--ink2);font-weight:600}
.mktline{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap;margin-top:12px;font-size:12.5px;color:var(--ink2)}
.mktline b{font:600 17px/1.2 var(--mono);color:var(--ink);letter-spacing:-.01em}
.mktline span{color:var(--ink3);font-size:11.5px}
.dataline em{font-style:normal;color:#8a6320;background:#fdf7ea;border:1px solid #e6d5b3;padding:3px 6px;border-radius:2px}
.dataline em.ok{color:#2f5c4a;background:#f2f8f4;border-color:#bcd8cc}
.hero-desc{color:var(--ink2);font-size:13.5px;max-width:560px}
.hero-axes{display:grid;grid-template-columns:1fr 1fr;gap:22px;margin-top:22px}
.axbar-h{display:flex;justify-content:space-between;font-size:12.5px;color:var(--ink2)}
.axbar-h b{font:600 19px/1 var(--mono)}
.axbar-h i{font:400 10px/1 var(--mono);color:var(--ink3);font-style:normal}
.axbar-t{height:5px;background:#efeade;margin:8px 0 6px;border-radius:3px;overflow:hidden}
.axbar-t i{display:block;height:100%}
.axbar-n{font-size:11.5px;color:var(--ink3);line-height:1.5}
.scale{display:flex;flex-wrap:wrap;gap:6px 18px;margin-top:16px;padding-top:12px;border-top:1px dashed var(--line);
font:10.5px/1 var(--mono);color:var(--ink3);letter-spacing:.02em}
.scale span{display:flex;align-items:center;gap:5px}
.scale i{width:14px;height:4px;display:inline-block;border-radius:1px}

.concl{display:grid;grid-template-columns:repeat(3,1fr);gap:0;margin-top:26px;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
.concl-i{padding:24px 26px 24px 0;border-right:1px solid var(--line)}
.concl-i:last-child{border-right:0;padding-right:0}
.concl-i:nth-child(2),.concl-i:nth-child(3){padding-left:26px}
.concl-i span{font:11px/1 var(--mono);color:var(--ink3);letter-spacing:.1em}
.concl-i p{font-size:13.5px;color:var(--ink2);margin-top:9px;line-height:1.7}
.concl-i b{color:var(--ink)}

.sec{margin-top:66px}
.sec-h{display:flex;gap:16px;align-items:flex-start;border-top:1px solid var(--line);padding-top:24px;margin-bottom:26px}
.no{font:600 10.5px/1 var(--mono);letter-spacing:.12em;color:var(--ink3);border:1px solid var(--line);
padding:6px 8px;border-radius:2px;white-space:nowrap;margin-top:4px;background:#fff}
.sec-h h2{font-size:23px;font-weight:600;letter-spacing:-.01em;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.sec-h p{color:var(--ink2);font-size:13px;max-width:800px;margin-top:8px}
.sec-h b{color:var(--ink)}

.fresh-wrap{margin:18px 0 6px;scroll-margin-top:58px}
.fresh-wrap .tb td{padding:7px 10px}
.fresh-wrap .tb th{padding-bottom:6px}
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.card{background:var(--card);padding:18px 18px 16px;border:1px solid var(--line);border-radius:3px}
.card-h{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}
.card h3{font-size:13.5px;font-weight:600;line-height:1.4}
.score{font:600 10px/1 var(--mono);color:var(--ink3);border:1px solid var(--line);padding:4px 5px;border-radius:2px;background:#faf8f2;white-space:nowrap}
.score.lg{font-size:12px;padding:4px 7px;margin-left:4px;color:var(--ink2)}
.card-src{font-size:11px;color:var(--ink3);margin-top:3px}
.card-v{font:600 27px/1.2 var(--mono);margin:12px 0 8px;letter-spacing:-.02em}
.card-v i{font-style:normal;font-size:13px;color:var(--ink3);margin-left:2px}
.card-sub{display:flex;justify-content:space-between;font-size:11.5px;color:var(--ink3);
border-top:1px dashed var(--line);padding-top:7px}
.card-sub b{color:var(--ink2);font-weight:600}
.card p{font-size:12.5px;color:var(--ink2);line-height:1.62;margin-top:9px}

.badge{font:11px/1 var(--mono);padding:4px 7px;border-radius:2px;border:1px solid;letter-spacing:.02em;white-space:nowrap}
.badge.ok{color:#1f6b52;border-color:#bcd8cc;background:#f2f8f4}
.badge.warn{color:#8a6320;border-color:#e6d5b3;background:#fdf7ea}
.badge.bad{color:#9d3028;border-color:#e8c6c2;background:#fbf1f0}
.badge.sm{font-size:10px;padding:3px 5px}

.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:var(--line);border:1px solid var(--line);margin-bottom:20px}
.kpi{background:var(--card);padding:12px 14px}
.kpi span{display:block;font-size:11.5px;color:var(--ink3)}
.kpi b{font:600 20px/1.4 var(--mono);letter-spacing:-.01em}

.legend{display:flex;align-items:center;gap:7px;font-size:11.5px;color:var(--ink2);margin-bottom:2px;flex-wrap:wrap}
.legend i{display:inline-block;width:14px;height:2px;margin-left:12px;vertical-align:middle}
.legend i:first-child{margin-left:0}
.legend i.dashed{background-image:linear-gradient(90deg,currentColor 60%,transparent 0);}
.lg-note{margin-left:auto;color:var(--ink3);font-size:11px}

.chart{position:relative;width:100%;margin:6px 0 4px}
.chart svg{display:block;width:100%;overflow:visible}
.tip{position:absolute;pointer-events:none;background:#2b2a26;color:#fff;font:11px/1.55 var(--mono);
padding:7px 9px;border-radius:3px;opacity:0;transition:opacity .12s;white-space:nowrap;z-index:5;transform:translate(-50%,-118%)}
.tip b{font-weight:600}

.cols{display:grid;grid-template-columns:1fr 1fr 1fr;gap:30px;margin-top:30px}
.cols.two{grid-template-columns:1fr 1fr}
.cols h4{font:600 10.5px/1 var(--mono);letter-spacing:.14em;color:var(--ink3);text-transform:uppercase;margin-bottom:12px}
.cols p{font-size:12.8px;color:var(--ink2);line-height:1.72;margin-top:10px}
.cols code{font-family:var(--mono);font-size:11.5px;background:#f2efe7;padding:1px 4px;border-radius:2px}
.formula{font:12px/1.95 var(--mono);background:#f3f0e8;border-left:2px solid #c4bda9;padding:12px 14px;
white-space:pre-wrap;color:#3a3833;letter-spacing:-.01em;border-radius:0 3px 3px 0;overflow-x:auto}
ul{list-style:none}
li{position:relative;padding-left:13px;margin-bottom:8px;font-size:12.8px;color:var(--ink2);line-height:1.68}
li:before{content:"";position:absolute;left:0;top:.66em;width:4px;height:4px;background:#c4bda9;border-radius:50%}
li b,.cols p b{color:var(--ink)}
ul.no li:before{background:#d9a29c}

.sub-h{font-size:12.5px;font-weight:600;color:var(--ink2);margin:18px 0 6px;letter-spacing:.01em}
.sub-h:first-child{margin-top:0}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:26px}
.grid2.wide{gap:40px}

.table-wrap{overflow-x:auto;margin:8px 0 4px}
.tb{width:100%;border-collapse:collapse;font-size:12.5px}
.tb th{text-align:left;font-weight:600;color:var(--ink3);font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;
border-bottom:1px solid var(--ink);padding:0 10px 8px}
.tb td{padding:9px 10px;border-bottom:1px solid var(--line2);color:var(--ink2);vertical-align:top;line-height:1.6}
.tb td.b{color:var(--ink);font-weight:500}
.tb td.mono,.tb .mono{font-family:var(--mono);font-size:10.5px;color:var(--ink3);word-break:break-all}
.tb tr:hover td{background:#faf8f1}
.pos{color:var(--red)!important;font-weight:600}
.neg{color:var(--green)!important;font-weight:600}
.cap{font-size:11.5px;color:var(--ink3);line-height:1.7;margin-top:12px;max-width:900px}

.mx-wrap{display:grid;grid-template-columns:1fr 268px;gap:30px;align-items:start}
.mx{position:relative;height:400px;display:grid;grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;
border:1px solid var(--line);background:var(--card)}
.mx-cell{padding:18px 20px;border-right:1px dashed var(--line);border-bottom:1px dashed var(--line);position:relative}
.mx-cell:nth-child(2),.mx-cell:nth-child(4){border-right:0}
.mx-cell:nth-child(3),.mx-cell:nth-child(4){border-bottom:0}
.mx-cell b{font-size:14px;display:block;color:var(--ink)}
.mx-cell span{font-size:11.5px;color:var(--ink3);line-height:1.6;display:block;margin-top:6px;max-width:260px}
.q1 b:before,.q2 b:before,.q3 b:before,.q4 b:before{content:"";display:inline-block;width:6px;height:6px;margin-right:7px;vertical-align:1px;border-radius:50%}
.q1 b:before{background:#c08b3e}.q2 b:before{background:#b3372c}.q3 b:before{background:#1f6b52}.q4 b:before{background:#5c7f96}
.mx-axis-x{position:absolute;left:0;right:0;top:50%;height:0;border-top:1px solid #b9b3a7;opacity:.45;pointer-events:none}
.mx-axis-y{position:absolute;top:0;bottom:0;left:50%;width:0;border-left:1px solid #b9b3a7;opacity:.45;pointer-events:none}
.mx-dot{position:absolute;width:9px;height:9px;border-radius:50%;transform:translate(-50%,-50%);box-shadow:0 0 0 3px #fffefb;z-index:3}
.mx-dot span{position:absolute;left:13px;top:-8px;font:10.5px/1 var(--mono);color:var(--ink2);white-space:nowrap;
background:#fffefb;padding:2px 3px}
.mx-lg{font-size:12px;color:var(--ink2);padding-top:6px}
.mx-lg div{display:flex;align-items:center;gap:8px;margin-bottom:8px}
.mx-lg i{width:9px;height:9px;border-radius:50%;display:inline-block}
.mx-lg p{color:var(--ink3);font-size:11.5px;line-height:1.7;margin-top:10px;border-top:1px dashed var(--line);padding-top:12px}

.sq-row{display:grid;grid-template-columns:64px 1fr 190px;align-items:center;gap:12px;margin-bottom:9px}
.sq-l{font:11.5px/1 var(--mono);color:var(--ink3)}
.sq-bar{position:relative;height:22px;background:#f2efe7;border-radius:2px}
.sq-bar i{display:block;height:100%;background:linear-gradient(90deg,#c9564a,#b3372c);border-radius:2px}
.sq-bar em{position:absolute;right:8px;top:0;line-height:22px;font:600 11px/22px var(--mono);color:#5d584f;font-style:normal}
.sq-m{font-size:11px;color:var(--ink3);text-align:right}
.conc{display:grid;grid-template-columns:repeat(3,1fr);gap:1px;background:var(--line);border:1px solid var(--line);margin-bottom:6px}
.conc div{background:var(--card);padding:14px 12px;text-align:center}
.conc b{display:block;font:600 24px/1.2 var(--mono);color:var(--blue)}
.conc span{font-size:11px;color:var(--ink3)}
.callout{background:#f2f8f4;border-left:2px solid #9fc4b3;padding:12px 14px;font-size:12px;color:#2f5c4a;margin-top:16px;line-height:1.7}

.ex-note{font-size:12.5px;color:var(--ink2);line-height:1.7;margin:-8px 0 18px;padding:10px 12px;background:#f7f4ec;border-radius:2px}
.explain{background:var(--card);border:1px solid var(--line);border-left:3px solid #c08b3e;border-radius:0 3px 3px 0;padding:22px 24px;margin:26px 0 4px}
.ex-h{display:flex;align-items:center;gap:10px;margin-bottom:6px}
.ex-h span{font:10px/1 var(--mono);letter-spacing:.14em;color:#8a6320;border:1px solid #e6d5b3;background:#fdf7ea;padding:4px 6px;border-radius:2px}
.ex-h h3{font-size:15px;font-weight:600}
.ex-lead{font-size:14px;color:var(--ink);line-height:1.7;margin:10px 0 16px;padding-bottom:16px;border-bottom:1px dashed var(--line)}
.ex-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:24px}
.ex-grid h5{font:600 11px/1 var(--mono);letter-spacing:.1em;color:var(--ink3);text-transform:uppercase;margin-bottom:8px}
.ex-grid p{font-size:12.5px;color:var(--ink2);line-height:1.72}
.ex-grid b{color:var(--ink)}
.skip-grid{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--line);border:1px solid var(--line)}
.skip-grid .skip:last-child:nth-child(odd){grid-column:span 2}
.skip{background:var(--card);padding:22px}
.skip-h{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:10px}
.skip-h b{font-size:14px}
.skip p{font-size:12.5px;color:var(--ink2);line-height:1.72}
.hl{background:#fdf1ef;color:#8f2f27;padding:0 3px}

.steps{counter-reset:s;list-style:none;border-top:1px solid var(--line)}
.steps li{counter-increment:s;display:grid;grid-template-columns:54px 170px 1fr;gap:16px;padding:16px 0;
border-bottom:1px solid var(--line2);margin:0;padding-left:0}
.steps li:before{content:counter(s,decimal-leading-zero);position:static;width:auto;height:auto;background:none;border-radius:0;
font:600 12px/1.6 var(--mono);color:var(--ink3);top:auto;left:auto}
.steps b{font-size:13px;font-weight:600}
.steps span{font-size:12.8px;color:var(--ink2);line-height:1.7}
.quote{font-size:13px!important;line-height:1.8;border-left:2px solid #c9c3b6;padding-left:14px;color:#43413b}

footer{border-top:1px solid var(--ink);margin-top:76px;padding-top:22px;display:flex;justify-content:space-between;gap:40px;flex-wrap:wrap}
.ft-l b{font-size:15px}
.ft-l span{display:block;font-size:11.5px;color:var(--ink3);margin-top:5px}
.ft-r{font-size:11px;color:var(--ink3);line-height:1.9;text-align:right;max-width:640px}
.ft-r span{display:block}

@media(max-width:980px){
 .wrap{padding:0 20px 60px}
 h1{font-size:34px}
 .hero{grid-template-columns:1fr;gap:18px;padding:22px}
 .hero-big{font-size:48px}
 .cards{grid-template-columns:1fr 1fr}
 .concl{grid-template-columns:1fr}
 .concl-i{border-right:0;border-bottom:1px solid var(--line);padding:18px 0}
 .concl-i:nth-child(2),.concl-i:nth-child(3){padding-left:0}
 .cols,.grid2,.skip-grid,.mx-wrap{grid-template-columns:1fr}
 .kpis{grid-template-columns:1fr 1fr}
 .mx{height:440px}
}
'''

# ================================================================ JS
JS = r'''
const D = window.__DATA__;
const NS = "http://www.w3.org/2000/svg";
const E = (t, a) => { const e = document.createElementNS(NS, t); for (const k in a) e.setAttribute(k, a[k]); return e; };
const T = (x, y, s, a = {}) => { const e = E("text", Object.assign({ x: x, y: y }, a)); e.textContent = s; return e; };
const num = (v) => Math.abs(v) >= 1000 ? (v / 1000).toFixed(v % 1000 === 0 ? 1 : 1) + "k" : String(Math.round(v * 100) / 100);
function niceStep(range, ticks) {
  const raw = range / ticks, p = Math.pow(10, Math.floor(Math.log10(raw))), n = raw / p;
  const m = n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10;
  return m * p;
}
function tipFor(host) {
  let t = host.querySelector(".tip");
  if (!t) { t = document.createElement("div"); t.className = "tip"; host.appendChild(t); }
  return t;
}
const cache = [];
function drawAll() { cache.forEach(c => { c.host.style.height = c.cfg.h + "px"; c.fn(c.host, c.cfg); }); }

function lineChart(host, cfg) {
  host.innerHTML = "";
  const W = host.clientWidth || 760, H = cfg.h || 240;
  const M = { t: 14, r: cfg.mr || 56, b: 26, l: cfg.ml || 48 };
  const IW = W - M.l - M.r, IH = H - M.t - M.b;
  const x = cfg.x, n = x.length, xm = {};
  x.forEach((d, i) => xm[d] = i);
  const X = i => M.l + (n > 1 ? i / (n - 1) * IW : IW / 2);
  let vals = [];
  cfg.series.forEach(s => s.data.forEach(p => { if (p[1] != null) vals.push(p[1]); }));
  (cfg.refs || []).forEach(r => vals.push(r.y));
  let lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals);
  if (cfg.zero) { lo = Math.min(lo, 0); hi = Math.max(hi, 0); }
  if (hi === lo) hi = lo + 1;
  const pad = (hi - lo) * 0.10; lo -= pad; hi += pad;
  const Y = v => M.t + IH - (v - lo) / (hi - lo) * IH;
  const svg = E("svg", { viewBox: "0 0 " + W + " " + H, width: "100%", height: H });
  const st = niceStep(hi - lo, 4), dec = st < 1 ? (st < 0.1 ? 2 : 1) : 0;
  for (let v = Math.ceil(lo / st) * st; v <= hi; v += st) {
    svg.appendChild(E("line", { x1: M.l, x2: W - M.r, y1: Y(v), y2: Y(v), stroke: "#efeade", "stroke-width": 1 }));
    svg.appendChild(T(M.l - 9, Y(v) + 3.5, cfg.yfmt ? cfg.yfmt(v) : num(v), { "text-anchor": "end", "font-size": 10, fill: "#9a9384" }));
  }
  if (cfg.band) {
    const i0 = xm[cfg.band[0]], i1 = xm[cfg.band[1]];
    if (i0 != null && i1 != null) svg.appendChild(E("rect", { x: X(i0), y: M.t, width: Math.max(2, X(i1) - X(i0)), height: IH, fill: "#2b2a26", opacity: 0.045 }));
  }
  (cfg.refs || []).forEach(r => {
    svg.appendChild(E("line", { x1: M.l, x2: W - M.r, y1: Y(r.y), y2: Y(r.y), stroke: r.color || "#b9b3a7", "stroke-width": 1, "stroke-dasharray": r.dash || "3 4", opacity: 0.85 }));
    if (r.label) { const left = r.side === "left";
      svg.appendChild(T(left ? M.l + 8 : W - M.r - 8, Y(r.y) + 3.5, r.label,
        { "text-anchor": left ? "start" : "end", "font-size": 10, fill: r.lc || "#7b756a",
          stroke: "#fffefb", "stroke-width": 3.5, "paint-order": "stroke" })); }
  });
  cfg.series.forEach(s => {
    let d = "", open = false;
    s.data.forEach(p => {
      const i = xm[p[0]]; if (i == null || p[1] == null) { open = false; return; }
      d += (open ? "L" : "M") + X(i).toFixed(1) + " " + Y(p[1]).toFixed(1) + " "; open = true;
    });
    svg.appendChild(E("path", { d: d, fill: "none", stroke: s.color, "stroke-width": s.w || 1.6, "stroke-dasharray": s.dash || "", "stroke-linejoin": "round", "stroke-linecap": "round" }));
    if (s.dots) s.data.forEach(p => { const i = xm[p[0]]; if (i == null || p[1] == null) return;
      svg.appendChild(E("circle", { cx: X(i), cy: Y(p[1]), r: 2.6, fill: "#fffefb", stroke: s.color, "stroke-width": 1.4 })); });
  });
  const li = cfg.lastSeries != null ? cfg.lastSeries : 0;
  const lastS = cfg.series[li];
  const last = lastS.data.filter(p => p[1] != null).slice(-1)[0];
  if (last && !cfg.noLast) {
    const i = xm[last[0]];
    svg.appendChild(E("circle", { cx: X(i), cy: Y(last[1]), r: 3.4, fill: lastS.color }));
    const lab = cfg.lastLabel ? cfg.lastLabel(last[1]) : num(last[1]);
    svg.appendChild(T(X(i) + 7, Y(last[1]) + 3.5, lab,
      { "font-size": 10.5, "font-weight": 600, fill: lastS.color }));
  }
  const stepLbl = cfg.xlab || 6, every = Math.max(1, Math.round((n - 1) / (stepLbl - 1)));
  for (let i = 0; i < n; i += every) {
    svg.appendChild(T(X(i), H - 8, cfg.xfmt ? cfg.xfmt(x[i]) : x[i].slice(2), { "text-anchor": "middle", "font-size": 9.5, fill: "#9a9384" }));
  }
  host.appendChild(svg);
  const cross = E("line", { y1: M.t, y2: M.t + IH, stroke: "#2b2a26", "stroke-width": 1, opacity: 0, "stroke-dasharray": "2 3" });
  svg.appendChild(cross);
  const dots = cfg.series.map(s => { const c = E("circle", { r: 3, fill: "#fffefb", stroke: s.color, "stroke-width": 1.6, opacity: 0 }); svg.appendChild(c); return c; });
  const rect = E("rect", { x: M.l, y: M.t, width: IW, height: IH, fill: "transparent" });
  svg.appendChild(rect);
  const tip = tipFor(host);
  rect.addEventListener("mousemove", e => {
    const bb = svg.getBoundingClientRect();
    const px = (e.clientX - bb.left) / bb.width * W;
    let i = Math.round((px - M.l) / IW * (n - 1)); i = Math.max(0, Math.min(n - 1, i));
    cross.setAttribute("x1", X(i)); cross.setAttribute("x2", X(i)); cross.setAttribute("opacity", 0.45);
    let txt = "<b>" + x[i] + "</b>";
    cfg.series.forEach((s, k) => {
      const hit = s.data.find(p => p[0] === x[i]);
      if (hit && hit[1] != null) { dots[k].setAttribute("cx", X(i)); dots[k].setAttribute("cy", Y(hit[1])); dots[k].setAttribute("opacity", 1);
        txt += "<br>" + s.name + " " + (cfg.tipfmt ? cfg.tipfmt(hit[1]) : hit[1]); }
      else { dots[k].setAttribute("opacity", 0); }
    });
    tip.innerHTML = txt;
    tip.style.left = (X(i) / W * host.clientWidth) + "px";
    tip.style.top = (M.t + 6) + "px";
    tip.style.opacity = 1;
  });
  rect.addEventListener("mouseleave", () => { cross.setAttribute("opacity", 0); dots.forEach(d => d.setAttribute("opacity", 0)); tip.style.opacity = 0; });
}

function barChart(host, cfg) {
  host.innerHTML = "";
  const W = host.clientWidth || 760, H = cfg.h || 220;
  const M = { t: 22, r: 16, b: 28, l: cfg.ml || 48 };
  const IW = W - M.l - M.r, IH = H - M.t - M.b;
  const labels = cfg.labels, n = labels.length, k = cfg.series.length;
  let vals = [];
  cfg.series.forEach(s => s.data.forEach(v => vals.push(v)));
  if (cfg.threshold != null) vals.push(cfg.threshold);
  let lo = Math.min.apply(null, vals), hi = Math.max.apply(null, vals);
  if (cfg.zero !== false) { lo = Math.min(lo, 0); hi = Math.max(hi, 0); }
  const pad = (hi - lo) * 0.12 || 1; lo -= pad * (lo < 0 ? 1 : 0); hi += pad;
  const Y = v => M.t + IH - (v - lo) / (hi - lo) * IH;
  const svg = E("svg", { viewBox: "0 0 " + W + " " + H, width: "100%", height: H });
  const st = niceStep(hi - lo, 4), dec = st < 1 ? 1 : 0;
  for (let v = Math.ceil(lo / st) * st; v <= hi; v += st) {
    svg.appendChild(E("line", { x1: M.l, x2: W - M.r, y1: Y(v), y2: Y(v), stroke: "#efeade" }));
    svg.appendChild(T(M.l - 9, Y(v) + 3.5, v.toFixed(dec), { "text-anchor": "end", "font-size": 10, fill: "#9a9384" }));
  }
  if (lo < 0) svg.appendChild(E("line", { x1: M.l, x2: W - M.r, y1: Y(0), y2: Y(0), stroke: "#b9b3a7" }));
  const gw = IW / n, bw = Math.min(26, gw * 0.66 / k), gap = 3;
  cfg.series.forEach((s, j) => {
    s.data.forEach((v, i) => {
      if (v == null) return;
      const cx = M.l + gw * i + gw / 2;
      const x0 = cx - (k * bw + (k - 1) * gap) / 2 + j * (bw + gap);
      const y0 = Y(Math.max(v, 0)), y1 = Y(Math.min(v, 0));
      const fill = cfg.barColors ? cfg.barColors[i] : (cfg.signColor ? (v >= 0 ? cfg.posColor : cfg.negColor) : s.color);
      svg.appendChild(E("rect", { x: x0, y: y0, width: bw, height: Math.max(1, y1 - y0), fill: fill, opacity: 0.94, rx: 1 }));
      if (cfg.showVal) svg.appendChild(T(x0 + bw / 2, (v >= 0 ? y0 - 5 : y1 + 11), cfg.vfmt ? cfg.vfmt(v) : v, { "text-anchor": "middle", "font-size": 9.5, fill: s.color, "font-weight": 600 }));
    });
  });
  if (cfg.threshold != null) {
    svg.appendChild(E("line", { x1: M.l, x2: W - M.r, y1: Y(cfg.threshold), y2: Y(cfg.threshold), stroke: "#b3372c", "stroke-dasharray": "4 4" }));
    svg.appendChild(T(W - M.r, Y(cfg.threshold) - 6, cfg.thLabel || "", { "text-anchor": "end", "font-size": 10, fill: "#b3372c" }));
  }
  const every = Math.max(1, Math.round(n / (cfg.xlab || 9)));
  const idxs = []; for (let i = 0; i < n; i += every) idxs.push(i);
  if (idxs[idxs.length - 1] !== n - 1 && (n - 1 - idxs[idxs.length - 1]) >= every * 0.65) idxs.push(n - 1);
  idxs.forEach(i => svg.appendChild(T(M.l + gw * i + gw / 2, H - 9, cfg.xfmt ? cfg.xfmt(labels[i]) : labels[i],
    { "text-anchor": "middle", "font-size": 9.5, fill: "#9a9384" })));
  if (cfg.vline && cfg.vline.at != null) {
    const vx = M.l + gw * cfg.vline.at;
    svg.appendChild(E("line", { x1: vx, x2: vx, y1: M.t, y2: M.t + IH, stroke: cfg.vline.color || "#b3372c", "stroke-dasharray": "4 4" }));
    svg.appendChild(T(vx + 5, M.t + 12, cfg.vline.label || "", { "font-size": 9.5, fill: cfg.vline.color || "#b3372c" }));
  }
  (cfg.notes || []).forEach(nt => svg.appendChild(T(M.l + gw * nt.i + gw / 2, M.t - 6, nt.text, { "text-anchor": "middle", "font-size": 9.5, fill: nt.color || "#5d584f", "font-weight": 600 })));
  host.appendChild(svg);
}

function scatterChart(host, cfg) {
  host.innerHTML = "";
  const W = host.clientWidth || 520, H = cfg.h || 260;
  const M = { t: 16, r: 16, b: 34, l: 44 };
  const IW = W - M.l - M.r, IH = H - M.t - M.b;
  const xr = cfg.xr, yr = cfg.yr;
  const X = v => M.l + (v - xr[0]) / (xr[1] - xr[0]) * IW;
  const Y = v => M.t + IH - (v - yr[0]) / (yr[1] - yr[0]) * IH;
  const svg = E("svg", { viewBox: "0 0 " + W + " " + H, width: "100%", height: H });
  for (let v = 0; v <= 100; v += 25) svg.appendChild(E("line", { x1: X(v), x2: X(v), y1: M.t, y2: M.t + IH, stroke: "#f0ece1" }));
  for (let v = -30; v <= 30; v += 15) svg.appendChild(E("line", { x1: M.l, x2: W - M.r, y1: Y(v), y2: Y(v), stroke: "#f0ece1" }));
  svg.appendChild(E("line", { x1: X(50), x2: X(50), y1: M.t, y2: M.t + IH, stroke: "#b9b3a7", "stroke-dasharray": "3 3" }));
  svg.appendChild(E("line", { x1: M.l, x2: W - M.r, y1: Y(0), y2: Y(0), stroke: "#b9b3a7", "stroke-dasharray": "3 3" }));
  [0, 50, 100].forEach(v => svg.appendChild(T(X(v), H - 16, v + "%", { "text-anchor": "middle", "font-size": 9.5, fill: "#9a9384" })));
  [-30, 0, 30].forEach(v => svg.appendChild(T(M.l - 8, Y(v) + 3.5, (v > 0 ? "+" : "") + v, { "text-anchor": "end", "font-size": 9.5, fill: "#9a9384" })));
  svg.appendChild(T(M.l, H - 2, "涨家占比 p →", { "font-size": 9.5, fill: "#9a9384" }));
  svg.appendChild(T(W - M.r, M.t + 10, "额价差 pp", { "text-anchor": "end", "font-size": 9.5, fill: "#9a9384" }));
  cfg.points.forEach((p, i) => {
    if (p.hollow) { svg.appendChild(E("circle", { cx: X(p.x), cy: Y(p.y), r: 4.5, fill: "none", stroke: p.color, "stroke-width": 1.6 })); return; }
    svg.appendChild(E("circle", { cx: X(p.x), cy: Y(p.y), r: 5, fill: p.color, stroke: "#fffefb", "stroke-width": 1.8 }));
    const dx = p.dx != null ? p.dx : (p.x > 70 ? -10 : 10);
    const dy = p.dy != null ? p.dy : (i % 2 ? 14 : -8);
    if (p.label) svg.appendChild(T(X(p.x) + dx, Y(p.y) + dy, p.label,
      { "text-anchor": p.anchor || (dx > 0 ? "start" : "end"), "font-size": 9.5, fill: "#5d584f", stroke: "#fffefb", "stroke-width": 3, "paint-order": "stroke" }));
  });
  host.appendChild(svg);
}

function build() {
  const S = D.series;
  const mclX = S.mcl.map(p => p[0]);
  const pX = S.p_series.map(p => p[0]);
  const ma5 = S.p_series.map((p, i) => {
    if (i < 4) return [p[0], null];
    let s = 0; for (let j = i - 4; j <= i; j++) s += S.p_series[j][1];
    return [p[0], s / 5];
  });
  const vwX = S.vw_close.map(p => p[0]);
  const vhX = S.vw_hist.map(p => p[0]);
  const vwWeekX = S.vww_hist.map(p => p[0]);
  const etfX = S.etf_amt.map(p => p[0]);
  const maX = S.ma20.map(p => p[0]);
  const futX = S.fut_ann_IF.map(p => p[0]);

  cache.length = 0;
  const add = (id, fn, cfg) => { const host = document.getElementById(id); if (host) cache.push({ host: host, fn: fn, cfg: cfg }); };

  add("c-mcl", lineChart, {
    h: 320, x: mclX, zero: true, ml: 50, lastSeries: 0, lastLabel: v => (v > 0 ? "+" : "−") + Math.abs(v).toFixed(0),
    band: [mclX[0], mclX[mclX.length - 201]],
    series: [{ name: "MCL", color: "#b3372c", w: 1.9, data: S.mcl }]
  });
  const ma20 = S.p_series.map((p, i) => {
    if (i < 19) return [p[0], null];
    let s = 0; for (let j = i - 19; j <= i; j++) s += S.p_series[j][1];
    return [p[0], s / 20];
  });
  add("c-p", lineChart, {
    h: 280, x: pX, ml: 44, lastSeries: 1, lastLabel: v => v.toFixed(1) + "%", yfmt: v => v.toFixed(0),
    refs: [{ y: 80, label: "80% 普涨", color: "#d9b9b3", lc: "#a4564e" }, { y: 50, label: "50% 均衡", color: "#c9c3b6", lc: "#77716a", side: "left" }, { y: 20, label: "20% 普跌", color: "#b9cdc2", lc: "#3d7a63" }],
    series: [{ name: "单日 p", color: "#b9c2c9", w: 0.9, data: S.p_series },
             { name: "20日均值", color: "#31556e", w: 1.9, data: ma20 }]
  });

  const items = D.obs.map(o => ({
    lbl: o.date.slice(5) + (o.kind === "noon" ? "午" : "收"),
    p: o.p, q: o.q, G: o.G, kind: o.kind
  }));
  const obsLbl = items.map(x => x.lbl);
  const obsP = items.map(x => [x.lbl, x.p]);
  const obsQ = items.map(x => [x.lbl, x.q]);
  add("c-obs", lineChart, {
    h: 250, x: obsLbl, ml: 44, xlab: 6, xfmt: v => v,
    yfmt: v => v.toFixed(0), lastSeries: 0, lastLabel: v => v.toFixed(1) + "%",
    refs: [{ y: 50, label: "50% 均衡", color: "#c9c3b6", lc: "#77716a", side: "left" }],
    series: [{ name: "涨家占比 p", color: "#31556e", w: 1.8, data: obsP },
             { name: "涨额占比 q", color: "#b3372c", w: 1.8, data: obsQ }]
  });

  const qp = D.obs.map((o, i) => ({
    x: o.p, y: o.G,
    label: i === D.obs.length - 1 ? o.date.slice(5) + (o.kind === "noon" ? " 午" : " 收") : "",
    color: i === D.obs.length - 1 ? "#2b2a26" : (o.kind === "noon" ? "#8fa3b0" : "#9c968a")
  }));
  add("c-quad", scatterChart, { h: 250, xr: [0, 100], yr: [-30, 30], points: qp });

  add("c-vwpx", lineChart, { h: 180, x: vwX, ml: 50, noLast: false, lastLabel: v => v.toFixed(0),
    series: [{ name: "上证收盘", color: "#31556e", w: 1.5, data: S.vw_close }] });
  add("c-vwh", barChart, { h: 130, labels: vhX, ml: 46, xlab: 7, signColor: 1, posColor: "#b3372c", negColor: "#1f6b52",
    series: [{ name: "VW-MACD 柱", color: "#b3372c", data: S.vw_hist.map(p => p[1]) }] });
  add("c-vww", barChart, { h: 150, labels: vwWeekX, ml: 46, xlab: 6, signColor: 1, posColor: "#b3372c", negColor: "#1f6b52",
    xfmt: l => l.slice(2, 7), series: [{ name: "周线柱", color: "#5c7f96", data: S.vww_hist.map(p => p[1]) }] });

  add("c-ma", lineChart, {
    h: 300, x: maX, ml: 44, lastSeries: 0, lastLabel: v => v.toFixed(1) + "%", yfmt: v => v.toFixed(0),
    refs: [{ y: 80, label: "80% 普涨", color: "#d9b9b3", lc: "#a4564e" },
           { y: 50, label: "50% 均衡", color: "#c9c3b6", lc: "#77716a", side: "left" },
           { y: 20, label: "20% 普跌", color: "#b9cdc2", lc: "#3d7a63" }],
    series: [{ name: "P20", color: "#31556e", w: 1.8, data: S.ma20 },
             { name: "P60", color: "#5c7f96", w: 1.4, data: S.ma60 },
             { name: "P250", color: "#c08b3e", w: 1.4, data: S.ma250 }]
  });

  add("c-fut", lineChart, {
    h: 300, x: futX, ml: 52, lastSeries: 0, lastLabel: v => v.toFixed(1) + "%", yfmt: v => v.toFixed(0),
    refs: [{ y: 0, label: "0 = 平水", color: "#b9b3a7" }],
    series: [{ name: "IF 沪深300", color: "#31556e", w: 1.8, data: S.fut_ann_IF },
             { name: "IC 中证500", color: "#5c7f96", w: 1.3, data: S.fut_ann_IC },
             { name: "IM 中证1000", color: "#c08b3e", w: 1.3, data: S.fut_ann_IM }]
  });

  add("c-etf", lineChart, { h: 250, x: etfX, ml: 50, lastSeries: 0, lastLabel: v => v.toFixed(0) + "亿",
    series: [{ name: "合计成交额", color: "#31556e", w: 1.5, data: S.etf_amt },
             { name: "MA20", color: "#c08b3e", w: 1.2, dash: "4 3", data: S.etf_ma20 }] });

  const turnX = S.turn_pct.map(p => p[0]);
  add("c-turn-trend", lineChart, {
    h: 260, x: turnX, ml: 44, lastSeries: 0, lastLabel: v => v.toFixed(1) + "%", yfmt: v => v.toFixed(0),
    refs: [{ y: 10, label: "10%", color: "#c9c3b6" }],
    series: [{ name: "换手率>5% 占比", color: "#b3372c", w: 1.8, data: S.turn_pct }]
  });

  const td = D.turnover_dist;
  const tl = td ? td.labels : D.turnover.labels;
  const tv = td ? td.counts : D.turnover.hist;
  add("c-turn", barChart, { h: 230, labels: tl, ml: 46, showVal: false, xlab: 9,
    vline: { at: 5, label: "← 5% 分界", color: "#b3372c" },
    barColors: tl.map((l, i) => i < 5 ? "#9fb0bd" : "#b3372c"),
    series: [{ name: "家数", color: "#5c7f96", data: tv }] });

  drawAll();
}
window.addEventListener("DOMContentLoaded", build);
let rt; window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(drawAll, 160); });
'''

# ================================================================ 组装
JS = JS.replace('window.addEventListener("DOMContentLoaded", build);',
                'if (document.readyState === "loading") { window.addEventListener("DOMContentLoaded", build); } else { build(); }')

HEAD = f'''<div class="mast"><div><b>交易信号研究</b> &nbsp;/&nbsp; 聪明钱温度计</div>
<div>MCL {META['asof']}（含ST）· 成交分布 {CUR_L} · 午盘 {META['noon_date']} 11:30</div></div>
<nav class="nav"><a href="#s0">总览</a><a href="#s1">判读矩阵</a><a href="#s2">MCL</a><a href="#s3">广度</a><a href="#s4">均线广度</a><a href="#s5">成交分布</a><a href="#s6">价格动能</a><a href="#s7">期货基差</a><a href="#s8">ETF活跃度</a><a href="#s9">换手率</a><a href="#s10">结构</a><a href="#s12">口径对照</a><a href="#s14">底稿</a></nav>
<div class="headline">
  <h1>聪明钱温度计</h1>
  <p>把“参与面”和“成交分布”拆成两条腿分别量：广度有没有扩散，成交额有没有跟上。公式取自公开的原始定义，
  读数用工作区已验收的行情数据复算；两处不一致的地方在“对照”一节逐条列出。</p>
  <p class="note">所谓“聪明钱”，在这套指标里只能观测到<b>行为结果</b>——哪些股票在被买、成交额流向哪一组——观测不到账户身份。
  这不是机构资金流，也不是内幕信息，读数的边界由此决定。</p>
  <div class="chips"><span>沪深A股 {int(CUR['n']):,} 家（含ST）</span><span>{len(D['series']['mcl'])} 个交易日</span><span>9 项指标</span>
  <span>日终 + 午盘双时点</span></div>
</div>'''

BODY = HEAD + HERO + CONCL + OVERVIEW + MATRIX + S_MCL + S_P + S_MA + S_TRIN + S_VW + S_FUT + S_ETF + S_TURN \
    + S_STRUCT + S_SKIP + S_CMP + WORKFLOW + S_STATUS + FOOT

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>聪明钱温度计 · {max(META['asof'], CUR['date'])}</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
{BODY}
</div>
<script>window.__DATA__ = {json.dumps(D, ensure_ascii=False)};</script>
<script>{JS}</script>
</body>
</html>'''

out = os.path.join(P.REPORT, '聪明钱温度计.html')
with open(out, 'w', encoding='utf-8') as fp:
    fp.write(html)
print('written', out, len(html), 'chars')
