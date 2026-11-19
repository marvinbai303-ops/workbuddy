#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""日终快照体检：当天该到的文件到没到、数据全不全。

用途：17:00 主任务之后由 20:00 的兜底任务调用；不通过就重跑 fetch_eod + update。
退出码：0 全部就绪；1 缺快照或不合格（需补跑）；2 参数/环境问题。

用法：python3 verify_eod.py [--date YYYY-MM-DD]
"""
import argparse
import csv
import json
import os
import sys
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent
import smd_paths as P

STORE = P.DATA / 'store'
INBOX = P.DATA / 'inbox'


def rd(p):
    p = Path(p)
    if not p.exists():
        return []
    with p.open(encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def check_snapshot(path, min_rows=4500):
    rows = rd(path)
    if not rows:
        return False, {'error': 'missing'}
    dates = {r.get('date') for r in rows}
    codes = {r.get('code') for r in rows}
    bad_amt = sum(1 for r in rows if float(r.get('amount_yuan') or 0) <= 0)
    A = sum(1 for r in rows if float(r['return_pct']) > 0)
    D = sum(1 for r in rows if float(r['return_pct']) < 0)
    ok = (len(rows) >= min_rows and len(dates) == 1 and len(codes) == len(rows)
          and bad_amt <= len(rows) * 0.02 and A + D >= 4000)
    return ok, {'rows': len(rows), 'dates': sorted(dates), 'unique_codes': len(codes),
                'bad_amount': bad_amt, 'A': A, 'D': D, 'U': len(rows) - A - D}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date')
    args = ap.parse_args()

    cal = sorted(r['date'] for r in rd(STORE / 'breadth_daily.csv'))
    today = args.date or str(date.today())
    # 周末没有行情，退回最后一个交易日；工作日一律按“今天”检查，
    # 这样 17:00 若整场失败（breadth 都没写），复检不会误判成昨天已完成。
    if not args.date and date.today().weekday() >= 5:
        today = cal[-1] if cal else today
    if not today:
        print(json.dumps({'ok': False, 'error': 'breadth_daily 为空'}, ensure_ascii=False))
        sys.exit(2)

    rep = {'date': today}
    inbox = INBOX / f'eod_{today}.csv'
    snap = STORE / 'snapshots' / f'eod_{today}.csv'
    ok_i, rep['inbox'] = check_snapshot(inbox)
    ok_s, rep['snapshot'] = check_snapshot(snap)

    agg = [r for r in rd(STORE / 'daily_agg.csv') if r['date'] == today and r['kind'] == 'eod']
    etf = [r for r in rd(STORE / 'etf_daily.csv') if r['date'] == today]
    turn = [r for r in rd(STORE / 'turnover_daily.csv') if r['date'] == today]
    dist = [r for r in rd(STORE / 'turnover_dist.csv') if r['date'] == today]
    ma = [r for r in rd(STORE / 'ma_breadth.csv') if r['date'] == today]
    fut = [r for r in rd(STORE / 'futures_basis.csv') if r['date'] == today]

    rep['derived'] = {
        'daily_agg': len(agg), 'etf': len(etf), 'turnover': len(turn),
        'turnover_dist': len(dist), 'ma_breadth': len(ma), 'futures': len(fut),
    }
    # 逐股快照是唯一不可回补的一项；其余缺失只影响各自模块
    rep['ok'] = ok_i or ok_s
    rep['missing'] = [k for k, v in rep['derived'].items() if v == 0]
    if not ok_s:
        rep['missing'].insert(0, 'eod_snapshot')

    print(json.dumps(rep, ensure_ascii=False, indent=1))
    sys.exit(0 if rep['ok'] else 1)


if __name__ == '__main__':
    main()
