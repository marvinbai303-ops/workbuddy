#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""收盘同时点对照：扶摇快照 vs 主链路（Wind 聚合 + iFinD 逐股快照）。

主链路（17:00 任务）：
    data/store/daily_agg.csv         → 当日 eod 行的 p/q/G/TRIN（Wind 一次查询）
    data/store/snapshots/eod_*.csv   → 当日逐股明细（若 fetch_eod 跑过）
旁路（fetch_hithink.py）：
    data/store/hithink_agg.csv
    data/store/hithink_snapshots/snap_*.csv

判定：同池（取交集）后 |Δp| ≤ 0.3pp 且 |Δq| ≤ 0.3pp 记为 PASS；
      逐股方向一致率（剔除 |涨跌幅|<0.5% 的临界股）≥ 99% 记为一致。

用法：python3 compare_eod.py [--date 2026-11-19]
退出码：0 通过 / 1 需要复核 / 2 缺数据
"""
import argparse
import csv
import json
import os
import statistics as st
import sys
from datetime import date, datetime

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import smd_paths as P

STORE = str(P.DATA / 'store')
SNAP = os.path.join(STORE, 'snapshots')
HI_AGG = os.path.join(STORE, 'hithink_agg.csv')
HI_SNAP = os.path.join(STORE, 'hithink_snapshots')


def die2(msg):
    print(msg)
    sys.exit(2)


def rd(p):
    with open(p, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def fmt(v, n=2):
    return f'{v:+.{n}f}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', default=str(date.today()))
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args()
    d = args.date

    # ---------- 1. 主链路聚合值
    agg_path = os.path.join(STORE, 'daily_agg.csv')
    if not os.path.exists(agg_path):
        die2(f'[2] 缺 {agg_path}')
    rows = [r for r in rd(agg_path) if r['date'] == d and r['kind'] == 'eod']
    if not rows:
        die2(f'[2] daily_agg 里没有 {d} 的 eod 行——主任务可能还没写完')
    main = rows[-1]

    # ---------- 2. 扶摇聚合值
    if not os.path.exists(HI_AGG):
        die2(f'[2] 缺 {HI_AGG}，先跑 fetch_hithink.py')
    his = [r for r in rd(HI_AGG) if r['date'] == d]
    if not his:
        die2(f'[2] hithink_agg 里没有 {d}')
    hi = his[-1]

    # 扶摇那行必须是收盘后取的；盘中快照不能用于验收
    ts = hi.get('ts') or ''
    ts_note = None
    if ts:
        try:
            dt = datetime.fromtimestamp(int(ts) / 1000)
            if dt.date().isoformat() != d or dt.hour * 60 + dt.minute < 15 * 60:
                ts_note = f'扶摇快照时间 {dt:%Y-%m-%d %H:%M}，不是 {d} 收盘后'
        except Exception:
            ts_note = f'扶摇时间戳无法解析：{ts}'

    mp, mq = float(main['p']), float(main['q'])
    hp, hq = float(hi['p']), float(hi['q'])
    out = {
        'date': d,
        'main': {'n': int(main['n']), 'p': mp, 'q': mq,
                 'G': float(main['G']), 'trin': float(main['trin_e']), 'source': main['source']},
        'hithink': {'n': int(hi['n']), 'A': int(hi['A']), 'D': int(hi['D']), 'U': int(hi['U']),
                    'p': hp, 'q': hq, 'G': float(hi['G']), 'trin': float(hi['trin']),
                    'amt_yi': float(hi['amt_yuan']) / 1e8, 'pool': hi['pool']},
        'delta': {'p': hp - mp, 'q': hq - mq},
    }

    print(f'=== {d} 收盘对照 ===')
    print(f"主链路  {main['source']}  n={main['n']}  "
          f"p {mp:.4f}%  q {mq:.4f}%  G {float(main['G']):+.4f}pp  TRIN {float(main['trin_e']):.4f}")
    print(f"扶摇    {hi['pool']}  n={hi['n']}  A/D/U {hi['A']}/{hi['D']}/{hi['U']}  "
          f"p {hp:.4f}%  q {hq:.4f}%  G {float(hi['G']):+.4f}pp  TRIN {float(hi['trin']):.4f}")
    dn = int(hi['n']) - int(main['n'])
    print(f"差      Δp {fmt(hp-mp)}pp   Δq {fmt(hq-mq)}pp   池子差 {dn:+d} 只")
    if abs(dn) > 10:
        print(f"        注意：两边池子相差 {abs(dn)} 只（扶摇 {hi['pool']} vs 主链路），属近似对比")
    if ts_note:
        print(f"        ⚠ {ts_note}——该行不能用于验收")

    # ---------- 3. 逐股对照（两边都有快照才有意义）
    per = None
    # 逐股快照可能落在两处：store/snapshots（update.py 写入）或 data/inbox（fetch_eod 直接产出）
    cands = [os.path.join(SNAP, f'eod_{d}.csv'),
             os.path.join(str(P.DATA), 'inbox', f'eod_{d}.csv')]
    f_main = next((x for x in cands if os.path.exists(x)), cands[0])
    f_hi = os.path.join(HI_SNAP, f'snap_{d}.csv')
    if os.path.exists(f_main) and os.path.exists(f_hi):
        m = {r['code']: r for r in rd(f_main)}
        h = {r['code']: r for r in rd(f_hi)}
        common = sorted(set(m) & set(h))
        if common:
            def ok(k):
                a = float(m[k]['return_pct'])
                b = float(h[k]['chg_pct'])
                return (a > 0) == (b > 0) and (a < 0) == (b < 0)
            ag_all = sum(1 for k in common if ok(k))
            crit = [k for k in common if abs(float(m[k]['return_pct'])) >= 0.5]
            ag_crit = sum(1 for k in crit if ok(k)) if crit else 0
            xs = [float(m[k]['return_pct']) for k in common]
            ys = [float(h[k]['chg_pct']) for k in common]
            mx, my = st.mean(xs), st.mean(ys)
            cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
            sd = (sum((a - mx) ** 2 for a in xs) ** .5) * (sum((b - my) ** 2 for b in ys) ** .5)
            corr = cov / sd if sd else float('nan')
            pr = [float(h[k]['last_price']) / float(m[k]['close_unadjusted']) - 1
                  for k in common if float(m[k]['close_unadjusted']) > 0]
            ar = [float(h[k]['turnover_yuan']) / float(m[k]['amount_yuan']) - 1
                  for k in common if float(m[k]['amount_yuan']) > 0]
            per = {
                'common': len(common), 'agree_all': ag_all, 'agree_all_pct': 100 * ag_all / len(common),
                'agree_crit': ag_crit, 'agree_crit_pct': 100 * ag_crit / len(crit) if crit else None,
                'corr': corr,
                'price_med_pct': 100 * st.median(pr) if pr else None,
                'price_gt1pct': sum(1 for x in pr if abs(x) > 0.01),
                'amt_med_pct': 100 * st.median(ar) if ar else None,
                'amt_gt1pct': sum(1 for x in ar if abs(x) > 0.01),
            }
            print(f"\n逐股  交集 {len(common)}  方向一致 {ag_all} ({per['agree_all_pct']:.2f}%)  "
                  f"剔除|涨跌幅|<0.5%后 {ag_crit}/{len(crit)} ({per['agree_crit_pct']:.2f}%)")
            print(f"      涨跌幅相关 {corr:.4f}  价格比中位 {per['price_med_pct']:+.3f}% "
                  f"(>1% 偏离 {per['price_gt1pct']} 只)")
            print(f"      成交额比中位 {per['amt_med_pct']:+.2f}% (>1% 偏离 {per['amt_gt1pct']} 只)")

            # 同池聚合：两边都只用交集代码各算一遍，排除池子差异
            def agg_on(src, ret_key, amt_key):
                A = D = 0; Ep = En = 0.0
                for k in common:
                    r = float(src[k][ret_key]); a = float(src[k][amt_key])
                    if r > 0: A += 1; Ep += a
                    elif r < 0: D += 1; En += a
                pp = 100 * A / (A + D); qq = 100 * Ep / (Ep + En)
                return A, D, pp, qq, (Ep + En) / 1e8
            a1, d1, p1, q1, e1 = agg_on(m, 'return_pct', 'amount_yuan')
            a2, d2, p2, q2, e2 = agg_on(h, 'chg_pct', 'turnover_yuan')
            print(f"\n同池聚合（{len(common)} 只交集）")
            print(f"      iFinD  A/D {a1}/{d1}  p {p1:.4f}%  q {q1:.4f}%  额 {e1:.1f} 亿")
            print(f"      扶摇   A/D {a2}/{d2}  p {p2:.4f}%  q {q2:.4f}%  额 {e2:.1f} 亿")
            print(f"      Δp {fmt(p2-p1)}pp   Δq {fmt(q2-q1)}pp")
            per['same_pool'] = {'n': len(common), 'p_if': p1, 'q_if': q1, 'p_hi': p2, 'q_hi': q2}
        else:
            print('\n逐股  两边无可交集代码')
    else:
        print('\n逐股  跳过（缺 eod 逐股快照或扶摇快照）——只比聚合值')

    out['per_stock'] = per

    # ---------- 4. 判定
    verdict, why = 'PASS', []
    if ts_note:
        verdict = 'REVIEW'; why.append(ts_note)
    if abs(hp - mp) > 0.3:
        verdict = 'REVIEW'; why.append(f'|Δp|={abs(hp-mp):.2f}pp > 0.3')
    if abs(hq - mq) > 0.3:
        verdict = 'REVIEW'; why.append(f'|Δq|={abs(hq-mq):.2f}pp > 0.3')
    if per and per['agree_crit_pct'] is not None and per['agree_crit_pct'] < 99:
        verdict = 'REVIEW'; why.append(f"逐股一致率 {per['agree_crit_pct']:.2f}% < 99%")
    out['verdict'] = verdict
    out['reasons'] = why
    print(f"\n判定  {verdict}" + (f"（{'; '.join(why)}）" if why else '（聚合与逐股均在阈值内）'))

    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if verdict == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
