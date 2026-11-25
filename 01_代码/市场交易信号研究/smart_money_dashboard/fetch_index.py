#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抓取指数日线（收盘 + 成交量），供 VW-MACD 使用。

数据源：iFinD 指数 MCP `index_data`。供应商单次约 100 行且会在非交易日回填前值，
因此按 60 个交易日切窗、并用 MCL 底库的交易日历过滤。

用法：
    python3 fetch_index.py --code 000300.SH --start 2025-09-01 --end 2026-11-17
    python3 fetch_index.py --code 000300.SH --date 2026-11-18        # 日更追加
输出：data/store/index_daily.csv（date,code,close,volume_shares）
"""
import argparse
import csv
import json
import os
import re
import sys
from datetime import date, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent
import smd_paths as P
sys.path.insert(0, str(BASE / 'tools'))
from mcp_client import Client

STORE = P.DATA / 'store'
RAW = P.DATA / 'raw_index'
NAMES = {'000300.SH': '沪深300', '000905.SH': '中证500', '000852.SH': '中证1000',
         '000985.CSI': '中证全指'}


def cn(d):
    y, m, dd = d.split('-')
    return f'{y}年{int(m)}月{int(dd)}日'


def trading_days():
    with open(STORE / 'breadth_daily.csv', encoding='utf-8-sig') as f:
        return sorted(r['date'] for r in csv.DictReader(f))


def parse_table(answer):
    lines = [l.strip() for l in answer.splitlines() if l.strip().startswith('|')]
    if not lines:
        return [], []
    def cells(l):
        return [c.strip() for c in l.strip('|').split('|')]
    head = cells(lines[0])
    rows = []
    for l in lines[1:]:
        c = cells(l)
        if set(''.join(c)) <= set('-: '):
            continue
        rows.append(c + [''] * (len(head) - len(c)))
    return head, rows


UNIT = {'亿': 1e8, '万': 1e4}


def unit_mult(head_cell):
    """表头单位倍数：『成交量（单位：亿）』→ 1e8。

    2026-11-24 实测：供应商把单位从单元格（「203.9433亿」）挪进表头
    （「成交量（单位：亿）」），单元格只剩「197.3812」，只按单元格解析
    会把 197.38 亿股写成 197 股，VW-MACD 的成交量权重随之失效。
    """
    m = re.search(r'单位[:：]\s*(亿|万)?股?', head_cell or '')
    if not m:
        return None
    return UNIT.get(m.group(1), 1.0)


def num(txt, default_mult=1.0):
    """把『179.2629亿』『1234万』『3976.4629』统一成浮点数；无后缀时用表头倍数"""
    t = txt.replace(',', '').strip()
    if not t:
        return None
    m = re.match(r'^(-?[\d.]+)\s*(亿|万)?$', t)
    if not m:
        return None
    v = float(m.group(1))
    return v * (UNIT[m.group(2)] if m.group(2) else default_mult)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--code', default='000300.SH')
    ap.add_argument('--start')
    ap.add_argument('--end')
    ap.add_argument('--date')
    ap.add_argument('--refresh', action='store_true')
    args = ap.parse_args()

    cal = trading_days()
    if args.date:
        start = end = args.date
    else:
        start = args.start or cal[0]
        end = args.end or cal[-1]
    # 按自然日切窗（80 天 ≈ 55 个交易日，低于供应商 100 行上限）；
    # 这样也能抓 2025-09-01 之前的数据，给 VW-MACD 留预热。
    wins, a = [], date.fromisoformat(start)
    end_d = date.fromisoformat(end)
    while a <= end_d:
        b = min(a + timedelta(days=79), end_d)
        wins.append((str(a), str(b)))
        a = b + timedelta(days=1)
    days = [d for d in cal if start <= d <= end] or [start]
    cli = Client('hexin-ifind-ds-index-mcp')
    RAW.mkdir(parents=True, exist_ok=True)

    acc = {}
    for a, b in wins:
        p = RAW / f'{args.code}_{a}.json'
        if p.exists() and not args.refresh:
            d = json.loads(p.read_text(encoding='utf-8'))
        else:
            name = NAMES.get(args.code, args.code)
            q = f'{name}指数{args.code}，{cn(a)}至{cn(b)}每个交易日的收盘价、成交量'
            d = cli.call('index_data', {'query': q}, timeout=180)
            p.write_text(json.dumps(d, ensure_ascii=False), encoding='utf-8')
        head, rows = parse_table(d['data']['answer'])
        ic = next((i for i, h in enumerate(head) if '收盘价' in h), None)
        iv = next((i for i, h in enumerate(head) if '成交量' in h), None)
        id_ = next((i for i, h in enumerate(head) if '日期' in h), None)
        mv = unit_mult(head[iv]) or 1.0 if iv is not None else 1.0
        for r in rows:
            ds = re.sub(r'\D', '', r[id_])[:8]
            if len(ds) != 8:
                continue
            key = f'{ds[:4]}-{ds[4:6]}-{ds[6:]}'
            c, v = num(r[ic]), num(r[iv], mv)
            if c is None or v is None:
                continue        # 非交易日回填行：成交量空
            if not (1e8 <= v <= 1e11):
                print(f'  !! {key} 成交量 {v:.0f} 不在合理区间（1 亿–1000 亿股），已跳过')
                continue
            acc[key] = (c, v)

    path = STORE / 'index_daily.csv'
    merged = {}
    if path.exists():
        with open(path, encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                merged[(r['date'], r['code'])] = r
    for d, (c, v) in acc.items():
        if start <= d <= end:
            merged[(d, args.code)] = {'date': d, 'code': args.code,
                                      'close': f'{c:.4f}', 'volume_shares': f'{v:.0f}'}
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['date', 'code', 'close', 'volume_shares'])
        w.writeheader()
        for k in sorted(merged):
            w.writerow(merged[k])

    got = sorted(d for (d, c) in merged if c == args.code)
    print(f'{args.code}: 取到 {len([d for d in acc if start <= d <= end])} 个交易日，'
          f'库存 {len(got)} 日（{got[0]} → {got[-1]}）')


if __name__ == '__main__':
    main()
