#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
聪明钱温度计 —— 数据装配与计算
输入：工作区已验收数据（douyin_research/ 下）
输出：out/dashboard_data.json（供渲染层使用，同时作为审计底稿）
所有分位、温度定义均在本文件内显式实现，不含隐藏参数。
"""
import csv, json, os, statistics as st
from datetime import date

BASE = os.path.dirname(os.path.abspath(__file__))
import smd_paths as P                      # 代码/数据/报告分处三棵目录
STORE = str(P.DATA / 'store')                     # 可增量更新的数据仓
SNAP = os.path.join(STORE, 'snapshots')

def rd(p):
    with open(p, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def fnum(x, default=None):
    try:
        if x is None or x == '':
            return default
        return float(x)
    except Exception:
        return default

WIN = 200   # 分位窗口（交易日），全页统一

def midrank_pct(series, v):
    """中位秩分位：100*(小于v的个数 + 0.5*等于v的个数)/N，取值0-100"""
    n = len(series)
    if n == 0 or v is None:
        return None
    less = sum(1 for x in series if x < v)
    eq = sum(1 for x in series if x == v)
    return 100.0 * (less + 0.5 * eq) / n

def r1(x, n=2):
    return None if x is None else round(x, n)

# ---------------------------------------------------------------- 1. MCL（从日更涨跌家数现算）
br_rows = rd(os.path.join(STORE, 'breadth_daily.csv'))
br_rows.sort(key=lambda r: r['date'])

def build_mcl(rows, warm=200):
    """X=A−D；EMA19(α=0.10)、EMA39(α=0.05)；首值初始化，第 200 次递推后标记预热完成。"""
    out, e19, e39 = [], None, None
    for i, r in enumerate(rows):
        A, D, U = int(r['A']), int(r['D']), int(r['U'])
        x = A - D
        e19 = x if e19 is None else 0.10 * x + 0.90 * e19
        e39 = x if e39 is None else 0.05 * x + 0.95 * e39
        out.append({
            'date': r['date'], 'A': A, 'D': D, 'U': U, 'net': x,
            'ema19': e19, 'ema39': e39, 'mcl': e19 - e39,
            'warmed': i >= warm,
            'p': 100.0 * A / (A + D),
        })
    return out

mcl = build_mcl(br_rows)

# ---------------------------------------------------------------- 2. 沪深300 VW-MACD（000300.SH，iFinD 指数日线，自算）
# 数据：fetch_index.py 抓取 2025-03-03 起 417 个交易日（多取约 40 根做 EMA 预热），
# 收盘与 Wind 逐日核对一致（≤0.0001 点）；成交量单位为股。
idx_rows = rd(os.path.join(STORE, 'index_daily.csv'))
csi = [(r['date'], float(r['close']), float(r['volume_shares']))
       for r in idx_rows if r['code'] == '000300.SH']
csi.sort()

def vw_macd(seq, short=12, long=26, mid=9):
    """VWMA_n = Σ(C×V)/ΣV；DIF=VWMA12−VWMA26；DEA=EMA9(DIF)；柱=2(DIF−DEA)。
    不足 long 根之前留空，DEA 自首个有效 DIF 起算（工程约定，与原上证版本一致）。"""
    out, dea = [], None
    for i, (d, c, v) in enumerate(seq):
        if i < long - 1:
            out.append({'date': d, 'close': c, 'dif': None, 'dea': None, 'hist': None})
            continue
        n12 = sum(seq[j][1] * seq[j][2] for j in range(i - short + 1, i + 1))
        d12 = sum(seq[j][2] for j in range(i - short + 1, i + 1))
        n26 = sum(seq[j][1] * seq[j][2] for j in range(i - long + 1, i + 1))
        d26 = sum(seq[j][2] for j in range(i - long + 1, i + 1))
        dif = n12 / d12 - n26 / d26
        dea = dif if dea is None else (2.0 / (mid + 1)) * dif + (1 - 2.0 / (mid + 1)) * dea
        out.append({'date': d, 'close': c, 'dif': dif, 'dea': dea, 'hist': 2 * (dif - dea)})
    return out

def to_weekly(seq):
    """按 ISO 周聚合：收盘取本周最后一个交易日，成交量按周求和。"""
    weeks = {}
    order = []
    for d, c, v in seq:
        y, m, dd = map(int, d.split('-'))
        iso = date(y, m, dd).isocalendar()
        k = f'{iso[0]}-W{iso[1]:02d}'
        if k not in weeks:
            weeks[k] = {'week': k, 'date': d, 'close': c, 'volume': v}
            order.append(k)
        else:
            weeks[k]['date'] = d
            weeks[k]['close'] = c
            weeks[k]['volume'] += v
    return [weeks[k] for k in order]

vw = vw_macd(csi)                                    # 日线
vw_valid = [r for r in vw if r['hist'] is not None]
# 周线：剔除最后一根未完成周（2026-11-16 为周一）
csi_w = [(w['date'], w['close'], w['volume']) for w in to_weekly(csi)[:-1]]
vww_all = vw_macd(csi_w)
vww = [r for r in vww_all if r['hist'] is not None]  # 仅保留有效周（26 周预热后）

# ---------------------------------------------------------------- 3. 三只ETF（从日更合计额现算 MA20）
etf_rows = rd(os.path.join(STORE, 'etf_daily.csv'))
etf_rows.sort(key=lambda r: r['date'])
etf = []
for i, r in enumerate(etf_rows):
    amt = float(r['amount_yuan'])
    ma = None
    if i >= 19:
        seg = etf_rows[i - 19:i + 1]
        ma = sum(float(x['amount_yuan']) for x in seg) / len(seg)
    etf.append({'date': r['date'], 'amt': amt, 'ma20': ma,
                'ratio': (amt / ma) if ma else None})
etf_valid = [r for r in etf if r['ratio'] is not None]

# ---------------------------------------------------------------- 4. 全市场日终 2026-11-16（逐股复算）
def load_universe(path, ret_key, turnover_key):
    rows = []
    for r in rd(path):
        ret = fnum(r[ret_key]); amt = fnum(r['amount_yuan']); vol = fnum(r['volume_shares'])
        to = fnum(r.get(turnover_key) or r.get('turnover_pct') or r.get('vendor_hourly_turnover_pct'))
        if ret is None or amt is None or vol is None:
            continue
        float_sh = (vol / (to / 100.0)) if (to and to > 0 and vol > 0) else None
        close = fnum(r.get('close_unadjusted') or r.get('close'))
        rows.append({'code': r['code'], 'name': r.get('name', ''),
                     'ret': ret, 'amt': amt, 'vol': vol, 'to': to,
                     'close': close,
                     # 午盘快照不含价格列，市值留空；市值分组只用 EOD
                     'mcap': (close * float_sh) if (close is not None and float_sh) else None})
    return rows

import glob

def latest_snapshot(kind):
    """取 snapshots/ 下最新的 eod_*.csv / noon_*.csv，返回 (date, path)"""
    files = sorted(glob.glob(os.path.join(SNAP, f'{kind}_*.csv')))
    if not files:
        raise SystemExit(f'缺少 {kind} 快照：{SNAP}')
    return os.path.basename(files[-1]).split('_')[1].replace('.csv', ''), files[-1]

EOD_DATE, EOD_PATH = latest_snapshot('eod')
NOON_DATE, NOON_PATH = latest_snapshot('noon')
eod = load_universe(EOD_PATH, 'return_pct', 'turnover_pct')
noon = load_universe(NOON_PATH, 'return_pct', 'vendor_hourly_turnover_pct')

def aggregate(rows):
    A = D = U = 0; Ep = En = 0.0; h5 = 0
    for r in rows:
        if r['ret'] > 0:
            A += 1; Ep += r['amt']
        elif r['ret'] < 0:
            D += 1; En += r['amt']
        else:
            U += 1
        if r['to'] and r['to'] > 5:
            h5 += 1
    p = 100.0 * A / (A + D)
    q = 100.0 * Ep / (Ep + En)
    return {
        'A': A, 'D': D, 'U': U, 'n': len(rows),
        'E_up': Ep, 'E_dn': En,
        'p': p, 'q': q, 'G': q - p,
        'trin_e': (A / D) / (Ep / En),
        'h5_count': h5, 'h5_pct': 100.0 * h5 / len(rows),
        'total_amt': Ep + En,
    }

agg_eod = aggregate(eod)
agg_noon = aggregate(noon)

# 午盘 MCL 预览：当日 11:30 的含ST家数，从上一收盘的 EMA 递推**一步**。
# 只做预览，绝不写入 breadth_daily —— 收盘时仍从同一个前日状态重算，不把午盘当成额外一日。
preview = None
nb_path = os.path.join(STORE, 'noon_breadth.csv')
if os.path.exists(nb_path):
    nb = sorted(rd(nb_path), key=lambda r: r['date'])
    if nb:
        r = nb[-1]
        gap = (date.fromisoformat(r['date']) - date.fromisoformat(mcl[-1]['date'])).days
        if r['date'] == NOON_DATE and 0 < gap <= 4:   # 基准必须是紧邻的上一个交易日，跨周末最多 4 天
            X = int(r['A']) - int(r['D'])
            e19 = 0.10 * X + 0.90 * mcl[-1]['ema19']
            e39 = 0.05 * X + 0.95 * mcl[-1]['ema39']
            preview = {
                'date': r['date'], 'A': int(r['A']), 'D': int(r['D']), 'U': int(r['U']),
                'n': int(r['A']) + int(r['D']) + int(r['U']), 'x': X,
                'ema19': e19, 'ema39': e39, 'mcl': e19 - e39,
                'base_date': mcl[-1]['date'], 'base_mcl': mcl[-1]['mcl'],
                'p': 100.0 * int(r['A']) / (int(r['A']) + int(r['D'])),
            }


# 市值分组（按推算流通市值五分位）
sized = [r for r in eod if r['mcap']]
sized.sort(key=lambda x: -x['mcap'])
q = len(sized) // 5
size_quint = []
names = ['Q1 最大', 'Q2', 'Q3', 'Q4', 'Q5 最小']
for i in range(5):
    seg = sized[i * q:(i + 1) * q] if i < 4 else sized[4 * q:]
    up = sum(1 for x in seg if x['ret'] > 0)
    dn = sum(1 for x in seg if x['ret'] < 0)
    a = sum(x['amt'] for x in seg if x['ret'] > 0)
    d = sum(x['amt'] for x in seg if x['ret'] < 0)
    size_quint.append({
        'label': names[i], 'n': len(seg),
        'mcap_hi': seg[0]['mcap'], 'mcap_lo': seg[-1]['mcap'],
        'up_pct': 100.0 * up / (up + dn),
        'q': 100.0 * a / (a + d) if (a + d) else None,
        'med_ret': st.median(x['ret'] for x in seg),
    })

# 成交额集中度
amt_sorted = sorted(eod, key=lambda x: -x['amt'])
tot_amt = sum(x['amt'] for x in eod)
cr = {k: 100.0 * sum(x['amt'] for x in amt_sorted[:k]) / tot_amt for k in (10, 50, 100)}

# 换手率分布（用于直方图）
buckets = [0, 0.5, 1, 2, 3, 5, 8, 12, 20, 1e9]
blabels = ['<0.5', '0.5-1', '1-2', '2-3', '3-5', '5-8', '8-12', '12-20', '>20']
hist = [0] * (len(buckets) - 1)
for r in eod:
    t = r['to']
    if t is None:
        continue
    for i in range(len(buckets) - 1):
        if buckets[i] <= t < buckets[i + 1]:
            hist[i] += 1
            break

# ---------------------------------------------------------------- 4b. 均线广度 P20/P60/P250
# 数据来自 ma_breadth.py：每天对每个周期取两次 iFinD 选股计数（分子=收盘>MA_n，分母=MA_n 有效）。
ma_rows = rd(os.path.join(STORE, 'ma_breadth.csv'))
MA = {20: [], 60: [], 250: []}
for r in ma_rows:
    n = int(r['period'])
    if n in MA:
        MA[n].append({'date': r['date'], 'pct': float(r['pct']),
                      'num': int(r['numerator']), 'den': int(r['denominator'])})
for n in MA:
    MA[n].sort(key=lambda r: r['date'])
ma_days = len({r['date'] for r in ma_rows})
ma_last = {n: (MA[n][-1] if MA[n] else None) for n in MA}
ma_pct_win = {n: midrank_pct([x['pct'] for x in MA[n][-WIN:]], MA[n][-1]['pct'])
              if len(MA[n]) >= 40 else None for n in MA}

def ma_chg(n, back):
    s = MA[n]
    if len(s) <= back:
        return None
    return s[-1]['pct'] - s[-1 - back]['pct']

# ---------------------------------------------------------------- 4c. 股指期货基差（IF/IC/IM）
fb_rows = rd(os.path.join(STORE, 'futures_basis.csv'))
FUT = {'IF': [], 'IC': [], 'IM': []}
for r in fb_rows:
    if r['product'] in FUT:
        FUT[r['product']].append({
            'date': r['date'], 'contract': r['contract'], 'days': int(r['days']),
            'fut': float(r['fut']), 'idx': float(r['idx']), 'basis': float(r['basis']),
            'rate': float(r['rate_pct']),
            'ann': (float(r['ann_pct']) if r['ann_pct'] else None),
            'pct': (float(r['pct_rank']) if r['pct_rank'] else None),
        })
for k in FUT:
    FUT[k].sort(key=lambda x: x['date'])
FUT_LAST = {k: (v[-1] if v else None) for k, v in FUT.items()}

def fut_chg(k, back):
    s = [x for x in FUT[k] if x['ann'] is not None]
    if len(s) <= back:
        return None
    return s[-1]['ann'] - s[-1 - back]['ann']

# ---------------------------------------------------------------- 4c2. 换手率分布（选股计数）
td_path = os.path.join(STORE, 'turnover_dist.csv')
TD = {}
for r in rd(td_path):
    TD.setdefault(r['date'], {})[r['bucket']] = int(r['count'])
TD_DATE = max(TD) if TD else None
TD_LABELS = ['<0.5', '0.5-1', '1-2', '2-3', '3-5', '5-8', '8-12', '12-20', '>20']

# ---------------------------------------------------------------- 4d. 换手率>5% 日序列
tr_rows = rd(os.path.join(STORE, 'turnover_daily.csv'))
TR = sorted([{'date': r['date'], 'n5': int(r['n_gt5']), 'nb': int(r['n_base']),
              'pct': float(r['pct'])} for r in tr_rows], key=lambda x: x['date'])
TR_LAST = TR[-1] if TR else None
TR_PCT = [x['pct'] for x in TR]

# ---------------------------------------------------------------- 4e. 两市合计成交额（沪深京）
amt_rows = rd(os.path.join(STORE, 'market_amount.csv'))
AMT = sorted([{'date': r['date'], 'amt': float(r['amount_yuan'])} for r in amt_rows],
             key=lambda x: x['date'])
AMT_LAST = AMT[-1] if AMT else None
AMT_VALS = [x['amt'] for x in AMT]

# ---------------------------------------------------------------- 5. 观测点（TRIN/额价差）
agg_rows = rd(os.path.join(STORE, 'daily_agg.csv'))
agg_rows.sort(key=lambda r: (r['date'], r['time']))
obs = []
for r in agg_rows[-3:]:
    obs.append({'date': r['date'], 'p': float(r['p']), 'q': float(r['q']),
                'trin': float(r['trin_e']), 'G': float(r['G']),
                'src': r['source'], 'kind': r['kind']})

blogger = [
    {'date': '2026-11-12', 'p': 15.81, 'q': 28.84, 'G': 13.03, 'trin': 0.46, 'trin_v': 0.50, 'mcl': 116.2},
    {'date': '2026-11-13', 'p': 13.88, 'q': 23.12, 'G': 9.24, 'trin': 0.54, 'trin_v': 0.49, 'mcl': -77.5},
    {'date': '2026-11-16', 'p': 20.75, 'q': 24.47, 'G': 3.73, 'trin': 0.81, 'trin_v': 0.50, 'mcl': -203.9},
]

# ---------------------------------------------------------------- 7. 温度计
mcl_win = [r['mcl'] for r in mcl[-WIN:]]
p_win = [r['p'] for r in mcl[-WIN:]]
pct_mcl = midrank_pct(mcl_win, mcl[-1]['mcl'])
pct_p = midrank_pct(p_win, mcl[-1]['p'])

# 当前口径：优先取 daily_agg 里最新的「收盘」记录（含ST，收盘后即终值）。
# 午盘快照虽然“日期更新”，但同一天 11:30 早于 15:00 收盘，不能用午盘盖收盘；
# 只有收盘记录缺失（或落后于快照日期）时才退回快照。
db_eod = None
for _r in agg_rows:
    if _r['kind'] == 'eod':
        db_eod = _r
if db_eod and db_eod['date'] >= max(EOD_DATE, NOON_DATE):
    CUR = dict(agg_eod)                      # 兜底字段（E_up/E_dn/h5 等）
    CUR.update({
        'n': int(db_eod['n']) if db_eod.get('n') else agg_eod['n'],
        'p': float(db_eod['p']), 'q': float(db_eod['q']),
        'G': float(db_eod['G']), 'trin_e': float(db_eod['trin_e']),
    })
    _b = next((r for r in rd(os.path.join(STORE, 'breadth_daily.csv'))
               if r['date'] == db_eod['date']), None)
    if _b:
        CUR.update({'A': int(_b['A']), 'D': int(_b['D']), 'U': int(_b['U'])})
    if TR_LAST and TR_LAST['date'] == db_eod['date']:
        CUR.update({'h5_count': TR_LAST['n5'], 'h5_pct': TR_LAST['pct']})
    CUR_DATE, CUR_KIND = db_eod['date'], 'eod'
elif NOON_DATE > EOD_DATE:
    CUR, CUR_DATE, CUR_KIND = agg_noon, NOON_DATE, 'noon'
else:
    CUR, CUR_DATE, CUR_KIND = agg_eod, EOD_DATE, 'eod'
CUR_LABEL = f'{CUR_DATE} 11:30' if CUR_KIND == 'noon' else f'{CUR_DATE} 收盘'

# 广度 v1（旧口径）= p 分位与 MCL 分位等权；v2 = 再加入 P20 分位（三者等权）
pct_p20 = ma_pct_win[20]
breadth_v1 = 0.5 * pct_p + 0.5 * pct_mcl
if pct_p20 is None:
    breadth_temp = breadth_v1
else:
    breadth_temp = (pct_p + pct_mcl + pct_p20) / 3.0
# 资金温度：把额价差按其理论上限归一 → [0,100]
g = CUR['G']; p_cur = CUR['p']
g_max = 100.0 * (1 - p_cur / 100.0) if g > 0 else 100.0 * (p_cur / 100.0)
money_temp = 50.0 + 50.0 * (g / g_max if g_max else 0)
total_temp = 0.5 * breadth_temp + 0.5 * money_temp
pct_p_cur = midrank_pct(p_win, p_cur)

def temp_label(t):
    if t < 20: return ('冰点', '极低参与面，成交额也不向上涨组集中')
    if t < 35: return ('偏冷', '参与面收缩，资金分布接近中性或轻度防守')
    if t < 50: return ('中性偏冷', '参与面弱，但成交分布仍有结构性支撑')
    if t < 65: return ('中性偏热', '参与面尚可，成交额开始向上涨组倾斜')
    if t < 80: return ('偏热', '参与面扩散且成交额跟随')
    return ('过热', '广度与成交同时极端，通常对应情绪高位')

label, label_desc = temp_label(total_temp)

FUT_SUM = {}
for _k, _v in FUT_LAST.items():
    if not _v:
        FUT_SUM[_k] = None
        continue
    _vals = [x['ann'] for x in FUT[_k] if x['ann'] is not None]
    FUT_SUM[_k] = {
        'date': _v['date'], 'contract': _v['contract'], 'days': _v['days'],
        'fut': _v['fut'], 'idx': _v['idx'], 'basis': _v['basis'], 'rate': _v['rate'],
        'ann': _v['ann'], 'pct': _v['pct'],
        'chg5': fut_chg(_k, 5), 'chg20': fut_chg(_k, 20),
        'min': min(_vals), 'max': max(_vals),
        'neg_share': 100.0 * sum(1 for x in _vals if x < 0) / len(_vals),
    }

payload = {
    'meta': {
        'generated': str(date.today()),
        'asof': mcl[-1]['date'],
        'eod_date': CUR_DATE if CUR_KIND == 'eod' else EOD_DATE,
        'noon_date': NOON_DATE,
        'noon_asof': f'{NOON_DATE} 11:30',
        'universe_mcl': ('沪深A股 · 含ST · '
                         f'{mcl[-1]["A"] + mcl[-1]["D"] + mcl[-1]["U"]:,}家（{mcl[-1]["date"]}）'),
        # 收盘口径已由 daily_agg（含ST）接管时，"宽度/量额"必须同步换池标签，
        # 否则会沿用上一条逐股快照的"剔ST/停牌"口径与旧日期（2026-11-19 实测到 11-18）。
        'universe_breadth': (
            f'沪深A股 · 含ST · {int(CUR.get("n") or agg_eod["n"]):,}家（{CUR_DATE}）'
            if CUR_KIND == 'eod' and CUR_DATE > EOD_DATE
            else f'沪深A股 · 剔ST/停牌/零成交 · {agg_eod["n"]:,}家（{EOD_DATE}）'),
        'index_name': '沪深300 000300.SH',
        'sources': '同花顺iFinD（指数/期货日线、选股计数）、同花顺扶摇（收盘快照）、万得Wind（交叉核对）',
    },
    'warmup_index': next((i for i, r in enumerate(mcl) if r['warmed']), None),
    'temp': {
        'total': total_temp, 'breadth': breadth_temp, 'money': money_temp,
        'pct_mcl': pct_mcl, 'pct_p': pct_p, 'pct_p20': pct_p20,
        'breadth_v1': breadth_v1, 'breadth_ver': 1 if pct_p20 is None else 2,
        'label': label, 'desc': label_desc,
        'window': WIN,
        'g_max': g_max,
        'pct_p_cur': pct_p_cur,
        'cur_kind': CUR_KIND, 'cur_date': CUR_DATE, 'cur_label': CUR_LABEL,
    },
    'cur': {**CUR, 'kind': CUR_KIND, 'date': CUR_DATE, 'label': CUR_LABEL},
    'fut': FUT_SUM,
    'market_amount': ({
        'date': AMT_LAST['date'], 'amt': AMT_LAST['amt'],
        'prev': AMT[-2]['amt'] if len(AMT) > 1 else None,
        'ma5': sum(AMT_VALS[-5:]) / len(AMT_VALS[-5:]) if len(AMT_VALS) >= 5 else None,
        'ma20': sum(AMT_VALS[-20:]) / len(AMT_VALS[-20:]) if len(AMT_VALS) >= 20 else None,
        'min': min(AMT_VALS), 'max': max(AMT_VALS), 'days': len(AMT),
    } if AMT_LAST else None),
    'turnover_daily': ({
        'date': TR_LAST['date'], 'n5': TR_LAST['n5'], 'nb': TR_LAST['nb'],
        'pct': TR_LAST['pct'], 'prev': TR[-2]['pct'] if len(TR) > 1 else None,
        'ma20': (sum(TR_PCT[-20:]) / len(TR_PCT[-20:])) if len(TR_PCT) >= 20 else None,
        'pct_rank': midrank_pct(TR_PCT[-WIN:], TR_LAST['pct']) if len(TR_PCT) >= 40 else None,
        'min': min(TR_PCT), 'max': max(TR_PCT), 'days': len(TR),
    } if TR_LAST else None),
    'ma': {
        'days': ma_days,
        'last_date': ma_last[20]['date'] if ma_last[20] else None,
        'periods': {str(n): ({
            'pct': ma_last[n]['pct'], 'num': ma_last[n]['num'], 'den': ma_last[n]['den'],
            'pct_rank': ma_pct_win[n], 'chg5': ma_chg(n, 5), 'chg20': ma_chg(n, 20),
            'min': min(x['pct'] for x in MA[n]), 'max': max(x['pct'] for x in MA[n]),
        } if ma_last[n] else None) for n in MA},
    },
    'preview': preview,
    'eod': agg_eod,
    'noon': agg_noon,
    'obs': obs, 'blogger': blogger,
    'size': {'quintiles': size_quint, 'cr': cr, 'n': len(sized)},
    'turnover': {'hist': hist, 'labels': blabels, 'h5': agg_eod['h5_count'], 'h5_pct': agg_eod['h5_pct']},
    'turnover_dist': ({'date': TD_DATE,
                       'labels': TD_LABELS,
                       'counts': [TD[TD_DATE].get(x, 0) for x in TD_LABELS],
                       'total': sum(TD[TD_DATE].values())} if TD_DATE else None),
    'series': {
        'mcl': [[r['date'], r1(r['mcl'], 1)] for r in mcl],
        'ema19': [[r['date'], r1(r['ema19'], 1)] for r in mcl],
        'ema39': [[r['date'], r1(r['ema39'], 1)] for r in mcl],
        'net': [[r['date'], r1(r['net'], 0)] for r in mcl],
        'p_series': [[r['date'], r1(r['p'], 1)] for r in mcl],
        'vw_close': [[r['date'], r1(r['close'], 1)] for r in vw],
        'vw_dif': [[r['date'], r1(r['dif'], 2)] for r in vw_valid],
        'vw_dea': [[r['date'], r1(r['dea'], 2)] for r in vw_valid],
        'vw_hist': [[r['date'], r1(r['hist'], 2)] for r in vw_valid],
        'vww_close': [[r['date'], r1(r['close'], 1)] for r in vww],
        'vww_dif': [[r['date'], r1(r['dif'], 2)] for r in vww if r['dif'] is not None],
        'vww_hist': [[r['date'], r1(r['hist'], 2)] for r in vww if r['hist'] is not None],
        'etf_amt': [[r['date'], r1(r['amt'] / 1e8, 1)] for r in etf],
        'etf_ma20': [[r['date'], r1(r['ma20'] / 1e8, 1)] for r in etf if r['ma20']],
        'etf_ratio': [[r['date'], r1(r['ratio'], 3)] for r in etf_valid],
        'ma20': [[x['date'], r1(x['pct'], 2)] for x in MA[20]],
        'ma60': [[x['date'], r1(x['pct'], 2)] for x in MA[60]],
        'ma250': [[x['date'], r1(x['pct'], 2)] for x in MA[250]],
        'fut_ann_IF': [[x['date'], r1(x['ann'], 2)] for x in FUT['IF'] if x['ann'] is not None],
        'fut_ann_IC': [[x['date'], r1(x['ann'], 2)] for x in FUT['IC'] if x['ann'] is not None],
        'fut_ann_IM': [[x['date'], r1(x['ann'], 2)] for x in FUT['IM'] if x['ann'] is not None],
        'turn_pct': [[x['date'], r1(x['pct'], 2)] for x in TR],
        'mkt_amt': [[x['date'], round(x['amt'] / 1e12, 4)] for x in AMT],
    },
    'stats': {
        'mcl_min': min(r['mcl'] for r in mcl), 'mcl_max': max(r['mcl'] for r in mcl),
        'mcl_last': mcl[-1]['mcl'], 'mcl_prev': mcl[-2]['mcl'],
        'vw_hist_last': vw_valid[-1]['hist'], 'vw_dif_last': vw_valid[-1]['dif'],
        'vw_dea_last': vw_valid[-1]['dea'],
        'vw_hist_pct': midrank_pct([r['hist'] for r in vw_valid[-WIN:]], vw_valid[-1]['hist']),
        'etf_ratio_last': etf_valid[-1]['ratio'],
        'etf_ratio_pct': midrank_pct([r['ratio'] for r in etf_valid], etf_valid[-1]['ratio']),
        'etf_above_share': 100.0 * sum(1 for r in etf_valid if r['ratio'] > 1) / len(etf_valid),
        'vw_week_last': vww[-1]['hist'], 'vw_week_dif': vww[-1]['dif'],
        'vw_hist_streak': next((i for i, r in enumerate(reversed(vw_valid)) if (r['hist'] > 0) != (vw_valid[-1]['hist'] > 0)), len(vw_valid)),
        'close_last': vw[-1]['close'],
        'close_max': max(r['close'] for r in vw),
        'close_max_date': max(vw, key=lambda r: r['close'])['date'],
        'drawdown': 100 * (vw[-1]['close'] / max(r['close'] for r in vw) - 1),
    },
}

os.makedirs(P.MID, exist_ok=True)
with open(os.path.join(P.MID, 'dashboard_data.json'), 'w', encoding='utf-8') as f:
    json.dump(payload, f, ensure_ascii=False, indent=1)

# 控制台摘要
print('=== 温度 ===')
print(f"综合 {total_temp:.1f} ({label}) | 广度 {breadth_temp:.1f} (pct_p={pct_p:.1f}, pct_mcl={pct_mcl:.1f}, pct_p20={pct_p20 if pct_p20 is None else round(pct_p20,1)}) | 资金 {money_temp:.1f}")
if ma_last[20]:
    print('  均线广度 ' + ' '.join(f"P{n} {ma_last[n]['pct']:.2f}%（{ma_last[n]['num']}/{ma_last[n]['den']}）" for n in (20, 60, 250)) + f'，样本 {ma_days} 日')
print(f"当前成交分布口径：{CUR_LABEL} | p {CUR['p']:.2f}% q {CUR['q']:.2f}% G {CUR['G']:+.2f}pp TRIN {CUR['trin_e']:.3f}")
if preview:
    print(f"午盘 MCL 预览：{preview['date']} 11:30  A−D={preview['x']}  "
          f"EMA19={preview['ema19']:.1f} EMA39={preview['ema39']:.1f}  MCL={preview['mcl']:.1f}"
          f"（基准 {preview['base_date']} 收盘 {preview['base_mcl']:.1f}，含ST {preview['n']} 家）")
print('=== 日终复算 ===')
for k in ('A', 'D', 'U', 'p', 'q', 'G', 'trin_e', 'h5_count', 'h5_pct'):
    print(f'  {k}: {agg_eod[k]:.4f}' if isinstance(agg_eod[k], float) else f'  {k}: {agg_eod[k]}')
print('=== 尺寸五分位 ===')
for s in size_quint:
    print(f"  {s['label']} n={s['n']} 上涨占比={s['up_pct']:.1f}% 中位涨跌={s['med_ret']:.2f}% 市值{s['mcap_lo']/1e8:.0f}-{s['mcap_hi']/1e8:.0f}亿")
print('=== 其他 ===')
print(f"  CR10={cr[10]:.1f}% CR50={cr[50]:.1f}% CR100={cr[100]:.1f}%")
print(f"  VW(沪深300) DIF {vw_valid[-1]['dif']:.1f} DEA {vw_valid[-1]['dea']:.1f} 柱 {vw_valid[-1]['hist']:.1f} pct {payload['stats']['vw_hist_pct']:.1f} | 周线柱 {vww[-1]['hist']:.1f}")
print(f"  ETF ratio {etf_valid[-1]['ratio']:.3f} pct {payload['stats']['etf_ratio_pct']:.1f}")
print(f"  沪深300 {vw[-1]['close']:.1f} 回撤 {payload['stats']['drawdown']:.1f}% (高点 {payload['stats']['close_max']:.1f} @ {payload['stats']['close_max_date']})")
