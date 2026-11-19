#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""午盘 ST/*ST 补充快照 → data/inbox/noon_st_YYYY-MM-DD.csv

用途：MCL 的底库是**含 ST** 的沪深A股（5,217 家），而 noon_YYYY-MM-DD.csv 是剔 ST 池。
     要让午盘也能给出 MCL 预览，必须把 ST 那 ~190 只的 11:30 家数补上。

口径与 fetch_noon.py 完全一致（复用其 build_recs / collect / fetch_batch），
只是股票池换成 ST/*ST，输出另存一个文件，绝不与剔ST主池混写。

用法：python3 fetch_noon_st.py [YYYY-MM-DD]
"""
import csv, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE = Path(__file__).resolve().parent
import smd_paths as P
sys.path.insert(0, str(BASE))
import fetch_noon as F          # 复用其客户端、批次抓取与逐股核算

# ---- 额度护栏：逐股小时频接口单次运行约 500 次调用（iFinD 按次计费）
if __name__ == '__main__' and '--allow-heavy' not in sys.argv:
    sys.exit('[BUDGET] 本脚本走逐股小时频接口，单次约 500 次调用，已默认禁用。\n'
             '         确认要跑请追加 --allow-heavy；日常更新用 update.py + 日更序列脚本。')


def st_universe():
    q = '沪深A股，ST或*ST，非北交所。显示股票代码、股票简称。'
    d = F.M.call('search_stocks', {'query': q}, timeout=180)
    F.RAW.mkdir(parents=True, exist_ok=True)
    (F.RAW / 'universe_st.json').write_text(
        __import__('json').dumps({'query': q, 'data': d}, ensure_ascii=False), encoding='utf-8')
    total = d['data']['selectedSecuritiesCount']
    head, body = F.parse_table(d['data']['answer'])
    ci = head.index('股票代码')
    ni = head.index('股票简称') if '股票简称' in head else None
    rows = [{'code': r[ci], 'name': r[ni] if ni is not None else ''} for r in body]
    if len(rows) != total:
        rows = F._rows_from(d['data'], 'st')
    print(f'  ST 池声明 {total} 只，取到 {len(rows)} 只')
    return rows

def main():
    print(f'[1/3] ST 股票池（{F.DATE}）')
    uni = st_universe()
    codes = sorted({r['code'] for r in uni if r['code'].endswith(('.SH', '.SZ'))})
    names = {r['code']: r['name'] for r in uni}
    print(f'  ST 合计 {len(codes)} 只')

    print('[2/3] 逐股小时K')
    batches = [(f'noonst_{i//10:04d}', codes[i:i + 10]) for i in range(0, len(codes), 10)]
    results = {}
    with ThreadPoolExecutor(max_workers=F.CONC) as ex:
        for k, (name, d) in enumerate(ex.map(F.fetch_batch, batches), 1):
            results[name] = d
            if k % 10 == 0 or k == len(batches):
                print(f'  {k}/{len(batches)}')

    print('[3/3] 核算与写入')
    byc = F.collect(results, batches, codes)
    recs, excluded, warn = F.build_recs(byc, codes, names)
    recs.sort(key=lambda r: r['code'])
    out = P.DATA / 'inbox' / f'noon_st_{F.DATE}.csv'
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['date', 'code', 'name', 'close_unadjusted',
                                          'return_pct', 'amount_yuan',
                                          'volume_shares', 'turnover_pct'])
        w.writeheader()
        w.writerows(recs)
    A = sum(1 for r in recs if float(r['return_pct']) > 0)
    D = sum(1 for r in recs if float(r['return_pct']) < 0)
    print(f'  写入 {out}')
    print(f'  ST 样本 {len(recs)}（池 {len(codes)}，剔除 {len(excluded)}） A/D/U={A}/{D}/{len(recs)-A-D}')
    if excluded:
        print('  剔除样例:', excluded[:5])
    if warn:
        print(f'  涨跌链条差异 {len(warn)} 只：{warn[:5]}')

if __name__ == '__main__':
    main()
