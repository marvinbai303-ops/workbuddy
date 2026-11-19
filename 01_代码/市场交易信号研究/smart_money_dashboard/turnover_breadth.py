#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""换手率 > 5% 的股票占比 —— iFinD 选股计数，逐日序列

定义：
    占比 = 100 × N(换手率 > 5%) / N(换手率 > 0)
分母只计入当日有成交的股票（换手率为 0 或停牌的不进分母）。
换手率为普通换手率（成交股数 ÷ 流通A股），与日终快照的 turnover_pct 同源。

为什么不从逐股快照算：逐股快照只有自动化上线之后的日期，历史补不回来；
选股计数每个交易日 2 次调用，可回补整段历史。

用法：
    python3 turnover_breadth.py --date 2026-11-17
    python3 turnover_breadth.py --start 2025-09-01 --end 2026-11-17
输出：data/store/turnover_daily.csv（date,n_gt5,n_base,pct,source）
"""
import argparse
import csv
import os
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
import smd_paths as P
sys.path.insert(0, str(BASE / 'tools'))
import ifind_mcp as M

STORE = P.DATA / 'store'
OUT = P.MID
POOL = '沪深A股，非ST，非*ST，非北交所'
FIELDS = ['date', 'n_gt5', 'n_base', 'pct', 'source']
BASE_MIN, BASE_MAX = 3500, 6200


def cn(d):
    y, m, dd = d.split('-')
    return f'{y}年{int(m)}月{int(dd)}日'


def rd(p):
    p = Path(p)
    if not p.exists():
        return []
    with p.open(encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def trading_days():
    return sorted(r['date'] for r in rd(STORE / 'breadth_daily.csv'))


def count(query, tries=3):
    for k in range(tries):
        try:
            return M.call('search_stocks', {'query': query}, timeout=180)['data']['selectedSecuritiesCount']
        except Exception:
            time.sleep(1.5 * (k + 1))
            M.handshake()
    return None


def fetch_day(d):
    n5 = count(f'{POOL}，{cn(d)}换手率大于5%。显示股票代码。')
    nb = count(f'{POOL}，{cn(d)}换手率大于0。显示股票代码。')
    if n5 is None or nb is None:
        return None, '取数失败'
    if not (BASE_MIN <= nb <= BASE_MAX):
        return None, f'分母 {nb} 超出 [{BASE_MIN},{BASE_MAX}]'
    if n5 <= 0:
        return None, '分子为 0，判定解析失败'
    if n5 > nb:
        return None, f'分子 {n5} > 分母 {nb}'
    return {'date': d, 'n_gt5': n5, 'n_base': nb, 'pct': f'{100.0 * n5 / nb:.6f}',
            'source': 'iFinD 选股计数'}, None


def save(rows):
    path = STORE / 'turnover_daily.csv'
    merged = {r['date']: r for r in rd(path)}
    for r in rows:
        merged[r['date']] = r
    tmp = str(path) + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for k in sorted(merged):
            w.writerow(merged[k])
    os.replace(tmp, path)
    return len(merged)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date')
    ap.add_argument('--start')
    ap.add_argument('--end')
    ap.add_argument('--force', action='store_true')
    args = ap.parse_args()

    cal = trading_days()
    if args.date:
        dates = [args.date]
    else:
        start = args.start or cal[0]
        end = args.end or cal[-1]
        dates = [d for d in cal if start <= d <= end]
    done = {r['date'] for r in rd(STORE / 'turnover_daily.csv')}
    todo = [d for d in dates if args.force or d not in done]
    print(f'目标 {len(dates)} 个交易日，待补 {len(todo)} 个')

    buf, fails, t0 = [], [], time.time()
    for i, d in enumerate(todo, 1):
        res, err = fetch_day(d)
        if res is None:
            fails.append(f'{d}\t{err}')
            print(f'  [{i}/{len(todo)}] {d} 跳过：{err}')
            continue
        buf.append(res)
        if i % 20 == 0 or i == len(todo):
            save(buf)
            print(f'  [{i}/{len(todo)}] {d} {float(res["pct"]):.2f}% '
                  f'（{res["n_gt5"]}/{res["n_base"]}）  用时 {(time.time()-t0)/60:.1f}min')
    if buf:
        save(buf)
    if fails:
        log = OUT / 'turnover_failed.txt'
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text('\n'.join(fails), encoding='utf-8')
        print(f'{len(fails)} 个交易日失败，见 {log}')
    total = len(rd(STORE / 'turnover_daily.csv'))
    print(f'turnover_daily.csv 共 {total} 行')


if __name__ == '__main__':
    main()
