#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""站上 MA20 / MA60 / MA250 的股票占比（P20/P60/P250）—— iFinD 选股计数，不拉全量价格

博主定义（[31] 图例、[42] P20/P60/P250 标签）：
    P_n = 100 × Σ 1(Cᵢ > MA_n(Cᵢ)) / N_n
分母 N_n 只计入“有 n 根日K”的股票（新股不足周期不进分母）。

取数方式（每个交易日每周期 2 次调用）：
    分子 = 选股「收盘价 > n日简单移动平均线」的 selectedSecuritiesCount
    分母 = 选股「n日简单移动平均线 > 0」的 selectedSecuritiesCount（均线为空即无值，不会 >0）

措辞陷阱（实测 2026-11-17）：
    写「20日均线」→ 被解析成「20日分时均线」（当日均价），count=3102（错）
    写「20日简单移动平均线」→ 真 MA20，count=916（对）
    日期必须写「2026年11月17日」，写「2026-11-17收盘时…」也会打回分时均线口径。

用法：
    python3 ma_breadth.py --date 2026-11-18                 # 单日
    python3 ma_breadth.py --start 2025-09-01 --end 2026-11-17  # 区间回补（可断点续跑）
输出：data/store/ma_breadth.csv（date,period,numerator,denominator,pct,source）
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
FIELDS = ['date', 'period', 'numerator', 'denominator', 'pct', 'source']
DEN_MIN, DEN_MAX = 3500, 6200          # 有效分母的合理区间，超出视为解析失败


def cn(d):
    y, m, dd = d.split('-')
    return f'{y}年{int(m)}月{int(dd)}日'


def rd(path):
    p = Path(path)
    if not p.exists():
        return []
    with p.open(encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def trading_days():
    """以 MCL 底库（含ST涨跌家数）的日期为交易日历"""
    rows = rd(STORE / 'breadth_daily.csv')
    return sorted(r['date'] for r in rows)


def _once(query):
    return M.call('search_stocks', {'query': query}, timeout=180)['data']['selectedSecuritiesCount']


def count(query, tries=3):
    """带重试的计数；失败返回 None（调用失败不写半截数据）"""
    last = None
    for k in range(tries):
        try:
            return _once(query)
        except Exception as e:                      # 会话过期 / 限流 / 超时
            last = e
            time.sleep(1.5 * (k + 1))
            M.handshake()
    print(f'    !! 计数失败：{last}')
    return None


def fetch_day(date, periods):
    """返回 [(period, numerator, denominator, pct), ...]，任一周期失败则整日丢弃"""
    out = []
    for n in periods:
        den = count(f'{POOL}，{cn(date)}，{n}日简单移动平均线大于0。显示股票代码。')
        num = count(f'{POOL}，{cn(date)}收盘价大于{n}日简单移动平均线。显示股票代码。')
        if num == 0:        # 计数为 0 基本只可能是解析失败，换措辞再问一次
            num = count(f'{POOL}，{cn(date)}收盘价高于{n}日简单移动平均线。显示股票代码。')
        if den is None or num is None:
            return None, f'MA{n} 取数失败'
        if not (DEN_MIN <= den <= DEN_MAX):
            return None, f'MA{n} 分母 {den} 超出 [{DEN_MIN},{DEN_MAX}]'
        if num <= 0:
            return None, f'MA{n} 分子为 0，判定解析失败'
        if num > den:
            return None, f'MA{n} 分子 {num} > 分母 {den}'
        out.append((n, num, den, 100.0 * num / den))
        time.sleep(0.12)
    return out, None


def save(rows):
    """整表重写，按 (date, period) 去重排序"""
    path = STORE / 'ma_breadth.csv'
    merged = {(r['date'], int(r['period'])): r for r in rd(path)}
    for r in rows:
        merged[(r['date'], int(r['period']))] = r
    path.parent.mkdir(parents=True, exist_ok=True)
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
    ap.add_argument('--periods', default='20,60,250')
    ap.add_argument('--force', action='store_true')
    args = ap.parse_args()

    periods = [int(x) for x in args.periods.split(',')]
    path = STORE / 'ma_breadth.csv'
    done = {(r['date'], int(r['period'])) for r in rd(path)}

    cal = trading_days()
    if args.date:
        dates = [args.date]
    else:
        start = args.start or (cal[0] if cal else None)
        end = args.end or (cal[-1] if cal else None)
        dates = [d for d in cal if start <= d <= end]
    if not dates:
        sys.exit('没有可取的交易日')

    todo = [d for d in dates
            if args.force or any((d, n) not in done for n in periods)]
    print(f'目标 {len(dates)} 个交易日，待补 {len(todo)} 个；周期 {periods}')

    buf, fails, t0 = [], [], time.time()
    for i, d in enumerate(todo, 1):
        res, err = fetch_day(d, periods)
        if res is None:
            fails.append(f'{d}\t{err}')
            print(f'  [{i}/{len(todo)}] {d} 跳过：{err}')
            continue
        for n, num, den, pct in res:
            buf.append({'date': d, 'period': n, 'numerator': num, 'denominator': den,
                        'pct': f'{pct:.6f}', 'source': 'iFinD 智能选股 count'})
        if i % 10 == 0 or i == len(todo):
            save(buf)
            elapsed = time.time() - t0
            eta = elapsed / i * (len(todo) - i)
            print(f'  [{i}/{len(todo)}] {d} ' +
                  ' '.join(f'P{n} {pct:.1f}' for n, _, _, pct in res) +
                  f'  | 已存 {len(buf)} 行，用时 {elapsed/60:.1f}min，预计剩余 {eta/60:.1f}min')
    if buf:
        save(buf)

    if fails:
        log = OUT / 'ma_breadth_failed.txt'
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open('w', encoding='utf-8') as f:
            f.write('\n'.join(fails))
        print(f'\n{len(fails)} 个交易日失败，明细见 {log}')
    total = len(rd(path))
    print(f'ma_breadth.csv 共 {total} 行（{total//len(periods)} 个交易日 × {len(periods)} 周期）')


if __name__ == '__main__':
    main()
