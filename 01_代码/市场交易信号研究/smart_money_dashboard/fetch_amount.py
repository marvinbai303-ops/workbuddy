#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""两市合计成交额（同花顺「全部A股」口径 = 沪 + 深 + 北证）

指标：iFinD 板块 001005010「内地股票->股票市场类->全部A股」，成交金额(合计)。
校验：11-16 供应商 1.4942 万亿，本看板逐股快照汇总 1.4939 万亿，差 30 亿以内。

为什么不用逐股快照求和：快照剔除了 ST/*ST 与停牌，且不含北交所；
这里的口径是沪深京全样本，和行情软件首页显示的一致。

用法：
    python3 fetch_amount.py --date 2026-11-17
    python3 fetch_amount.py --start 2025-09-01 --end 2026-11-17
输出：data/store/market_amount.csv（date,amount_yuan,source）
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
RAW = P.DATA / 'raw_amount'
FIELDS = ['date', 'amount_yuan', 'source']


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


def amount(txt):
    """『1.4675万亿』『99.9218亿』『1.2万』→ 元"""
    t = txt.replace(',', '').strip()
    if not t:
        return None
    m = re.match(r'^(-?[\d.]+)\s*(万亿|亿|万)?$', t)
    if not m:
        return None
    return float(m.group(1)) * {'万亿': 1e12, '亿': 1e8, '万': 1e4, None: 1}[m.group(2)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date')
    ap.add_argument('--start')
    ap.add_argument('--end')
    ap.add_argument('--refresh', action='store_true')
    args = ap.parse_args()

    cal = trading_days()
    if args.date:
        start = end = args.date
    else:
        start = args.start or cal[0]
        end = args.end or cal[-1]
    if not cal:
        sys.exit('breadth_daily 为空，无法确定交易日')

    wins, a = [], date.fromisoformat(start)
    end_d = date.fromisoformat(end)
    while a <= end_d:
        b = min(a + timedelta(days=79), end_d)
        wins.append((str(a), str(b)))
        a = b + timedelta(days=1)

    cli = Client('hexin-ifind-ds-index-mcp')
    RAW.mkdir(parents=True, exist_ok=True)
    acc = {}
    for a_, b_ in wins:
        p = RAW / f'all_{a_}.json'
        if p.exists() and not args.refresh:
            d = json.loads(p.read_text(encoding='utf-8'))
        else:
            q = f'全部A股板块，{cn(a_)}至{cn(b_)}每个交易日的成交金额'
            d = cli.call('sector_data', {'query': q}, timeout=180)
            p.write_text(json.dumps(d, ensure_ascii=False), encoding='utf-8')
        head, rows = parse_table(d['data']['answer'])
        ai = next((i for i, h in enumerate(head) if '成交金额' in h), None)
        if ai is None:
            print(f'  !! {a_}~{b_} 返回表缺少成交金额列，跳过')
            continue
        di = next((i for i, h in enumerate(head) if '日期' in h), None)
        for r in rows:
            # 单日窗口时接口只回一行、不带日期列（2026-11-19 实测），日期取窗口起点
            ds = re.sub(r'\D', '', r[di])[:8] if di is not None else re.sub(r'\D', '', a_)[:8]
            v = amount(r[ai])
            if len(ds) == 8 and v:
                acc[f'{ds[:4]}-{ds[4:6]}-{ds[6:]}'] = v

    path = STORE / 'market_amount.csv'
    merged = {r['date']: r for r in rd(path)}
    n = 0
    for d, v in acc.items():
        if start <= d <= end:
            merged[d] = {'date': d, 'amount_yuan': f'{v:.0f}',
                         'source': 'iFinD 板块 001005010 全部A股（沪深京）'}
            n += 1
    tmp = str(path) + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for k in sorted(merged):
            w.writerow(merged[k])
    os.replace(tmp, path)
    print(f'取到 {n} 个交易日，market_amount.csv 共 {len(merged)} 行；'
          f'最新 {merged[max(merged)]["date"]} {float(merged[max(merged)]["amount_yuan"])/1e12:.4f} 万亿')


if __name__ == '__main__':
    main()
