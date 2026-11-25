#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""股指期货基差与年化升贴水（IF / IC / IM）

算法（与《期货年化基差_算法.md》一致）：
    基差(点)   = 期货主力收盘 − 指数收盘
    基差率     = 基差 ÷ 指数收盘
    年化基差率 = 基差率 × 365 ÷ 剩余自然日
    N日分位    = 年化基差率在过去 200 个交易日中的中位秩分位

主力判定：当日成交量最大的合约（逐日选，不做连续合约拼接，避免换月跳空污染年化）。
到期日：合约月的第三个星期五（股指期货交割日规则）。
数据：iFinD 期货 MCP `future_quotes` + 指数 MCP `index_data`，逐合约取日线；
      所有序列按 MCL 底库的交易日历过滤（供应商会在周末/节假日回填前值）。

用法：python3 futures_basis.py [--start 2025-09-01] [--end 2026-11-17] [--refresh]
输出：data/store/futures_basis.csv、data/store/index_close.csv
"""
import argparse
import calendar
import csv
import json
import os
import re
import sys
import time
from datetime import date, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent
import smd_paths as P
sys.path.insert(0, str(BASE / 'tools'))
from mcp_client import Client

STORE = P.DATA / 'store'
RAW = P.DATA / 'raw_futures'
PRODUCTS = {'IF': '000300.SH', 'IC': '000905.SH', 'IM': '000852.SH'}
INDEX_NAMES = {'000300.SH': '沪深300', '000905.SH': '中证500', '000852.SH': '中证1000'}
FIELDS = ['date', 'product', 'contract', 'days', 'fut', 'idx', 'basis', 'rate_pct',
          'ann_pct', 'pct_rank']


def trading_days():
    with open(STORE / 'breadth_daily.csv', encoding='utf-8-sig') as f:
        return sorted(r['date'] for r in csv.DictReader(f))


def parse_table(answer):
    """把 markdown 表格解析成 [(header...), rows...]；取第一张表"""
    lines = [l.strip() for l in answer.splitlines() if l.strip().startswith('|')]
    if not lines:
        return [], []
    def cells(l):
        return [c.strip() for c in l.strip('|').split('|')]
    head = cells(lines[0])
    rows = []
    for l in lines[1:]:
        c = cells(l)
        if len(c) < len(head):
            c += [''] * (len(head) - len(c))
        if set(''.join(c)) <= set('-: '):
            continue
        rows.append(c)
    return head, rows


def col(head, *names):
    for i, h in enumerate(head):
        for n in names:
            if n in h:
                return i
    return None


def third_friday(y, m):
    """合约月第三个星期五"""
    c = calendar.Calendar()
    fris = [d for d in c.itermonthdates(y, m) if d.weekday() == 4 and d.month == m]
    return fris[2]


def expiry(code):
    y = 2000 + int(code[2:4])
    m = int(code[4:6])
    return third_friday(y, m)


def fetch_query(client, tool, query, cache_key, refresh=False):
    RAW.mkdir(parents=True, exist_ok=True)
    p = RAW / f'{cache_key}.json'
    if p.exists() and not refresh:
        return json.loads(p.read_text(encoding='utf-8'))
    d = client.call(tool, {'query': query}, timeout=180)
    p.write_text(json.dumps(d, ensure_ascii=False), encoding='utf-8')
    return d


def fetch_parsed(client, tool, query, cache_key, refresh, parse, accept,
                 tries=3, label=''):
    """取数 → 解析 → 校验，通过后才写缓存。

    供应商会间歇性把「某合约区间收盘价」解析成只含证券代码/简称的实体表
    （2026-11-19 实测：IF 与 000852 各命中一次），此时 answer 里没有日期/收盘价列。
    旧逻辑会把这种空结果当成功：既写坏缓存，又让当日该品种无行。
    这里改为识别空解析并重试，且坏响应不落缓存。
    """
    RAW.mkdir(parents=True, exist_ok=True)
    p = RAW / f'{cache_key}.json'
    if p.exists() and not refresh:
        try:
            got = parse(json.loads(p.read_text(encoding='utf-8')))
            if accept(got):
                return got
        except Exception:
            pass                                   # 历史坏缓存：忽略并重取
    last = None
    for k in range(tries):
        try:
            d = client.call(tool, {'query': query}, timeout=180)
            got = parse(d)
            if accept(got):
                p.write_text(json.dumps(d, ensure_ascii=False), encoding='utf-8')
                return got
            last = '返回表缺少日期/收盘价列'
        except Exception as e:
            last = str(e)[:80]
            client.handshake()
        if k < tries - 1:
            time.sleep(1.2 * (k + 1))
    print(f'  {label} 重试 {tries} 次仍失败：{last}')
    return {}


def cn(d):
    y, m, dd = d.split('-')
    return f'{y}年{int(m)}月{int(dd)}日'


def series_from(d, need_vol=True):
    """解析一张 markdown 表；列顺序不固定（有的表把成交量放在收盘价前面），按表头定位"""
    head, rows = parse_table(d['data']['answer'])
    di, ci = col(head, '日期'), col(head, '收盘价')
    oi = col(head, '成交量') if need_vol else None
    if di is None or ci is None:
        return {}
    out = {}
    for r in rows:
        ds = re.sub(r'\D', '', r[di])[:8]
        if len(ds) != 8:
            continue
        if not r[ci].strip():
            continue                      # 已到期合约返回空行
        vol = r[oi].replace(',', '').strip() if oi is not None else '1'
        if need_vol and not vol:
            continue                      # 空成交量 = 供应商回填的非交易日
        try:
            v = float(r[ci])
        except Exception:
            continue
        out[f'{ds[:4]}-{ds[4:6]}-{ds[6:]}'] = (v, float(vol) if vol else 0.0)
    return out



def midrank(series, v):
    n = len(series)
    if n < 20:
        return None
    less = sum(1 for x in series if x < v)
    eq = sum(1 for x in series if x == v)
    return 100.0 * (less + 0.5 * eq) / n


def save_rows(rows, start, end, idx=None):
    """合并写盘并在合并后的整段上重算 200 日分位。

    只替换本次真正取到的 (date, product)；取数失败的品种沿用原值，
    避免 --refresh 局部失败把当日已有的行删掉（2026-11-19 实测过）。
    """
    path = STORE / 'futures_basis.csv'
    covered = {(r['date'], r['product']) for r in rows}
    kept, stale = [], []
    if path.exists():
        with open(path, encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                if not (start <= r['date'] <= end):
                    kept.append(r)
                elif (r['date'], r['product']) not in covered:
                    kept.append(r)
                    stale.append(r)
    merged = sorted(kept + rows, key=lambda r: (r['date'], r['product']))
    if stale:
        dts = sorted({r['date'] for r in stale})
        print(f'  ⚠ 以下日期未取到新值，沿用原记录：{", ".join(dts)}（{len(stale)} 行）')

    for prod in PRODUCTS:
        seg = [r for r in merged if r['product'] == prod]
        vals = [float(r['ann_pct']) if r['ann_pct'] else None for r in seg]
        for i, r in enumerate(seg):
            r['pct_rank'] = ''
            if not r['ann_pct']:
                continue
            win = [v for v in vals[max(0, i - 199):i + 1] if v is not None]
            p = midrank(win, float(r['ann_pct']))
            r['pct_rank'] = '' if p is None else f'{p:.2f}'

    STORE.mkdir(parents=True, exist_ok=True)
    tmp = str(path) + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(merged)
    os.replace(tmp, path)

    if idx:
        with open(STORE / 'index_close.csv', 'w', encoding='utf-8', newline='') as f:
            w = csv.writer(f)
            w.writerow(['date', 'code', 'name', 'close'])
            for code in sorted(idx):
                for d in sorted(idx[code]):
                    w.writerow([d, code, INDEX_NAMES[code], f'{idx[code][d]:.4f}'])

    print(f'\n写入 {path}：本次 {len(rows)} 行，合计 {len(merged)} 行')
    for prod in PRODUCTS:
        seg = [r for r in merged if r['product'] == prod and r['date'] <= end]
        if not seg:
            continue
        last = seg[-1]
        print(f"  {prod} {last['date']} 主力 {last['contract']} 剩 {last['days']} 日  "
              f"基差 {last['basis']} 点（{last['rate_pct']}%）  年化 {last['ann_pct'] or '—'}%  "
              f"分位 {last['pct_rank'] or '—'}")
    return merged


def month_codes(prod, d):
    """中金所股指期货只有四个合约：当月、下月、当季、下季。主力必在其中。"""
    def code(y, m):
        return f'{prod}{str(y)[2:]}{m:02d}'

    y, m = d.year, d.month
    out = [code(y, m)]
    y2, m2 = (y + 1, 1) if m == 12 else (y, m + 1)
    out.append(code(y2, m2))
    q = ((m - 1) // 3 + 1) * 3          # 下一个季月（3/6/9/12）
    for k in range(2):
        qq = q + 3 * k
        yy = y + (qq - 1) // 12
        mm = (qq - 1) % 12 + 1
        c = code(yy, mm)
        if c not in out:
            out.append(c)
    return out


def per_code(d, ds):
    """单日多合约响应 → {合约代码: (成交量, 收盘价)}"""
    head, rows = parse_table(d['data']['answer'])
    si, ci, oi = col(head, '证券代码'), col(head, '收盘价'), col(head, '成交量')
    di = col(head, '日期')
    if si is None or ci is None:
        return {}
    want = ds.replace('-', '')
    out = {}
    for r in rows:
        if di is not None and re.sub(r'\D', '', r[di])[:8] != want:
            continue
        if not r[ci].strip():
            continue
        try:
            close = float(r[ci])
            vol = float((r[oi] or '0').replace(',', '') or 0) if oi is not None else 1.0
        except Exception:
            continue
        code = r[si].split('.')[0].strip()
        out[code] = (vol, close)
    return out


def run_fast(ds, refresh=False):
    """日更模式：3 次期货 + 2 次指数，共 5 次调用（原逐合约模式约 60 次）。"""
    d0 = date.fromisoformat(ds)
    lo = (d0 - timedelta(days=7)).isoformat()
    fx = Client('hexin-ifind-ds-futures-mcp')
    ix = Client('hexin-ifind-ds-index-mcp')

    idx = {c: {} for c in PRODUCTS.values()}
    # 沪深300 已有日序列，直接读，省一次调用
    idp = STORE / 'index_daily.csv'
    if idp.exists():
        with open(idp, encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                if r['code'] == '000300.SH' and r['date'] == ds:
                    idx['000300.SH'][ds] = float(r['close'])
    for code in ('000905.SH', '000852.SH'):
        if code in idx and idx[code]:
            continue
        q = f'{INDEX_NAMES[code]}指数{code}，{cn(lo)}至{cn(ds)}每个交易日的收盘价'
        got = fetch_parsed(ix, 'index_data', q, f'fast_idx_{code}_{ds}', refresh,
                           lambda d: series_from(d, need_vol=False),
                           lambda g: ds in g, label=f'{code} {INDEX_NAMES[code]}')
        if ds in got:
            idx[code][ds] = got[ds][0]
        print(f'  {code} {INDEX_NAMES[code]}: {"OK" if ds in got else "缺"}')
    if not idx['000300.SH']:
        print('  警告：index_daily.csv 无 000300 当日收盘，请先跑 fetch_index.py')

    rows = []
    for prod, spot in PRODUCTS.items():
        codes = month_codes(prod, d0)
        q = '、'.join(f'{c}.CFE' for c in codes) + f'，{cn(lo)}至{cn(ds)}每个交易日的收盘价和成交量'
        got = fetch_parsed(fx, 'future_quotes', q, f'fast_{prod}_{ds}', refresh,
                           lambda d: per_code(d, ds), lambda g: bool(g), label=prod)
        cand = [(v, c, k, (expiry(k) - d0).days) for k, (v, c) in got.items() if v > 0]
        # 主力 = 成交量最大的合约；band 只剔除临到期（年化失真）与过远月份。
        # 2026-11-24 实测：25 日下限会在到期前一个月把仍在放量的当月合约踢掉
        # （IF2612 剩 24 日、成交 75,112 手 vs IF2703 20,958 手），三品种同时
        # 跳到季月，使年化基差序列断层。下限放宽到 5 日，让成交量决定换月。
        band = [x for x in cand if 5 <= x[3] <= 130]
        pick = sorted(band, reverse=True)[0] if band else (sorted(cand, reverse=True)[0] if cand else None)
        print(f'  {prod}: {len(got)} 个合约有量，选 {pick[2] if pick else "—"}')
        if not pick or spot not in idx or ds not in idx[spot]:
            continue
        vol, fut, code, _ = pick
        days = (expiry(code) - d0).days
        s = idx[spot][ds]
        basis = fut - s
        ann = '' if days < 10 else f'{100 * basis / s * 365 / days:.4f}'
        rows.append({'date': ds, 'product': prod, 'contract': code, 'days': days,
                     'fut': f'{fut:.2f}', 'idx': f'{s:.4f}', 'basis': f'{basis:.2f}',
                     'rate_pct': f'{100 * basis / s:.4f}', 'ann_pct': ann, 'pct_rank': ''})

    if not rows:
        sys.exit('fast 模式没有生成任何行')
    save_rows(rows, ds, ds, idx if all(idx[c] for c in idx) else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--start', default='2025-09-01')
    ap.add_argument('--end', default=str(date.today()))
    ap.add_argument('--date')
    ap.add_argument('--fast', action='store_true', help='日更：只取最近 4 个合约与 2 个指数，约 5 次调用')
    ap.add_argument('--refresh', action='store_true')
    args = ap.parse_args()
    if args.fast:
        ds = args.date or str(date.today())
        if ds not in trading_days():
            sys.exit(f'{ds} 不是交易日')
        run_fast(ds, args.refresh)
        return
    if args.date:
        args.start = args.end = args.date

    cal = [d for d in trading_days() if args.start <= d <= args.end]
    if not cal:
        sys.exit(f'区间内没有交易日：{args.start} ~ {args.end}')
    args.end = max(args.end, cal[-1])
    print(f'交易日 {len(cal)} 个：{cal[0]} → {cal[-1]}')

    fx = Client('hexin-ifind-ds-futures-mcp')
    ix = Client('hexin-ifind-ds-index-mcp')

    # 供应商单次最多返回约 100 行，按 60 个交易日切窗
    wins = [(cal[i], cal[min(i + 59, len(cal) - 1)]) for i in range(0, len(cal), 60)]
    print(f'  分 {len(wins)} 个窗口取数（单次上限约 100 行）')

    # ---------- 1. 指数收盘
    idx = {}
    for code in sorted(set(PRODUCTS.values())):
        acc = {}
        for a, b in wins:
            d = fetch_query(ix, 'index_data',
                            f'{INDEX_NAMES[code]}指数{code}，{cn(a)}至{cn(b)}每个交易日的收盘价',
                            f'idx_{code}_{a}', args.refresh)
            acc.update({k: v[0] for k, v in series_from(d, need_vol=False).items()})
        idx[code] = {k: v for k, v in acc.items() if k in set(cal)}
        print(f'  {code} {INDEX_NAMES[code]}: {len(idx[code])} 个交易日')

    # ---------- 2. 逐合约收盘与成交量
    futures = {}          # product -> date -> [(vol, close, code)]
    for prod in PRODUCTS:
        months = []
        y, m = 2025, 9
        while (y, m) <= (2027, 3):
            months.append(f'{prod}{str(y)[2:]}{m:02d}')
            m += 1
            if m == 13:
                y, m = y + 1, 1
        for code in months:
            s = {}
            for a, b in wins:
                try:
                    d = fetch_query(fx, 'future_quotes',
                                    f'{code}.CFE，{cn(a)}至{cn(b)}每个交易日的收盘价和成交量',
                                    f'{code}_{a}', args.refresh)
                except Exception as e:
                    print(f'    {code} {a} 跳过：{str(e)[:50]}')
                    continue
                s.update(series_from(d))
            if not s:
                continue
            for ds, (close, vol) in s.items():
                if ds in cal and vol > 0:
                    futures.setdefault(prod, {}).setdefault(ds, []).append((vol, close, code))
            time.sleep(0.1)
        n = len(futures.get(prod, {}))
        print(f'  {prod}: {len(months)} 个合约取到数据，覆盖 {n} 个交易日')

    # ---------- 3. 逐日选主力并计算
    rows = []
    for prod, spot in PRODUCTS.items():
        for ds in cal:
            cand = futures.get(prod, {}).get(ds)
            if not cand or ds not in idx[spot]:
                continue
            # 年化对分母极敏感：只在剩余 25~130 自然日的合约里选主力，
            # 避免到期前一周把 1% 的基差放大成 30%+ 的假信号。
            d0 = date.fromisoformat(ds)
            band = []
            for vol, close, code in cand:
                dd = (expiry(code) - d0).days
                if 25 <= dd <= 130:
                    band.append((vol, close, code, dd))
            if not band:
                vol, fut, code = max(cand)[:3]
            else:
                band.sort(reverse=True)
                vol, fut, code, _ = band[0]
            exp = expiry(code)
            days = (exp - d0).days
            if days <= 0:
                continue
            s = idx[spot][ds]
            basis = fut - s
            # 剩余自然日 < 10 时，年化把基差放大 3 倍以上（分母过小），
            # 这段样本不作年化、不进分位，图上留空。
            ann = '' if days < 10 else f'{100 * basis / s * 365 / days:.4f}'
            rows.append({'date': ds, 'product': prod, 'contract': code, 'days': days,
                         'fut': f'{fut:.2f}', 'idx': f'{s:.4f}', 'basis': f'{basis:.2f}',
                         'rate_pct': f'{100 * basis / s:.4f}',
                         'ann_pct': ann, 'pct_rank': ''})

    save_rows(rows, args.start, args.end, idx)


if __name__ == '__main__':
    main()
