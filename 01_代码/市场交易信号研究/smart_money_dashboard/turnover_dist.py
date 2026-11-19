#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""换手率分布（9 个分桶）—— iFinD 选股计数，逐日可取，不依赖逐股快照

分桶与看板柱状图一致：
    (0,0.5] (0.5,1] (1,2] (2,3] (3,5] (5,8] (8,12] (12,20] >20  单位 %

为什么另开一条：逐股快照依赖小时频接口，只保留当日，漏跑就永久缺失；
选股计数可以按任意历史日期重取，用来兜底分布图。

用法：python3 turnover_dist.py --date 2026-11-17
      python3 turnover_dist.py --start 2025-09-01 --end 2026-11-17
输出：data/store/turnover_dist.csv（date,bucket,count）
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
FIELDS = ['date', 'bucket', 'count']
# (标签, 下界, 上界)；上界 None 表示无上限
BUCKETS = [
    ('<0.5', 0.0, 0.5),
    ('0.5-1', 0.5, 1.0),
    ('1-2', 1.0, 2.0),
    ('2-3', 2.0, 3.0),
    ('3-5', 3.0, 5.0),
    ('5-8', 5.0, 8.0),
    ('8-12', 8.0, 12.0),
    ('12-20', 12.0, 20.0),
    ('>20', 20.0, None),
]


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
            time.sleep(1.2 * (k + 1))
            M.handshake()
    return None


def fetch_day(d):
    out = []
    for tag, lo, hi in BUCKETS:
        if lo == 0.0:
            q = f'{POOL}，{cn(d)}换手率大于0且小于等于{hi}%。显示股票代码。'
        elif hi is None:
            q = f'{POOL}，{cn(d)}换手率大于{lo}%。显示股票代码。'
        else:
            q = f'{POOL}，{cn(d)}换手率大于{lo}%且小于等于{hi}%。显示股票代码。'
        n = count(q)
        if n is None:
            return None, f'{tag} 取数失败'
        out.append((tag, n))
    total = sum(n for _, n in out)
    if not (3500 <= total <= 6200):
        return None, f'合计 {total} 超出 [3500,6200]'
    return out, None


def save(rows):
    path = STORE / 'turnover_dist.csv'
    merged = {(r['date'], r['bucket']): r for r in rd(path)}
    for r in rows:
        merged[(r['date'], r['bucket'])] = r
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
    done = {r['date'] for r in rd(STORE / 'turnover_dist.csv')}
    todo = [d for d in dates if args.force or d not in done]
    print(f'目标 {len(dates)} 个交易日，待补 {len(todo)} 个，每日期 {len(BUCKETS)} 次调用')

    buf, fails, t0 = [], [], time.time()
    for i, d in enumerate(todo, 1):
        res, err = fetch_day(d)
        if res is None:
            fails.append(f'{d}\t{err}')
            print(f'  [{i}/{len(todo)}] {d} 跳过：{err}')
            continue
        for tag, n in res:
            buf.append({'date': d, 'bucket': tag, 'count': n})
        if i % 5 == 0 or i == len(todo):
            save(buf)
            print(f'  [{i}/{len(todo)}] {d} 合计 {sum(n for _, n in res)}，'
                  f'用时 {(time.time()-t0)/60:.1f}min')
    if buf:
        save(buf)
    if fails:
        log = OUT / 'turnover_dist_failed.txt'
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text('\n'.join(fails), encoding='utf-8')
        print(f'{len(fails)} 个交易日失败，见 {log}')
    print(f'turnover_dist.csv 共 {len(rd(STORE / "turnover_dist.csv"))} 行')


if __name__ == '__main__':
    main()
