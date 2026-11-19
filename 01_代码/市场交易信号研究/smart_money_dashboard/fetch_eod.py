#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""日终全市场快照：iFinD 逐股小时K（4 根）→ data/inbox/eod_YYYY-MM-DD.csv

口径与 fetch_noon.py 一致，只是把时间窗放到收盘：
  * 池：沪深A股，非 ST/*ST，非北交所
  * 取当日 10:30 / 11:30 / 14:00 / 15:00 四根已完成小时柱
  * 前收 = 首根柱收盘 − 首根柱涨跌（交易所参考昨收，含除权调整）
  * 涨跌幅 = 100 × (末根收盘 / 前收 − 1)
  * 成交额/量/换手率 = 四根柱求和（与全日值对账过：茅台 238 分钟合计＝日线）
  * 全天停牌、零成交、柱不齐（半日停牌）剔除，不记为平盘

用法：python3 fetch_eod.py [YYYY-MM-DD]
"""
import csv, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BASE = Path(__file__).resolve().parent
import smd_paths as P
sys.path.insert(0, str(BASE))
import fetch_noon as F

# ---- 额度护栏：逐股小时频接口单次运行约 500 次调用（iFinD 按次计费）
if __name__ == '__main__' and '--allow-heavy' not in sys.argv:
    sys.exit('[BUDGET] 本脚本走逐股小时频接口，单次约 500 次调用，已默认禁用。\n'
             '         确认要跑请追加 --allow-heavy；日常更新用 update.py + 日更序列脚本。')


EXPECT = ('10:30', '11:30', '14:00', '15:00')
CUTOFF = '15:00'

def main():
    print(f'[1/3] 股票池（{F.DATE} 日终）')
    uni = F.universe()
    codes = sorted({r['code'] for r in uni if r['code'].endswith(('.SH', '.SZ'))})
    names = {r['code']: r['name'] for r in uni}
    print(f'  沪深A股 非ST {len(codes)} 只')

    print('[2/3] 逐股小时K（4 根）')
    batches = [(f'eod_{i//10:04d}', codes[i:i + 10]) for i in range(0, len(codes), 10)]
    results = {}
    with ThreadPoolExecutor(max_workers=F.CONC) as ex:
        for k, (name, d) in enumerate(ex.map(F.fetch_batch, batches), 1):
            results[name] = d
            if k % 50 == 0 or k == len(batches):
                print(f'  {k}/{len(batches)}')

    print('[2b/3] ST 补充池（含ST口径需要）')
    import fetch_noon_st as ST
    st_uni = ST.st_universe()
    st_codes = sorted({r['code'] for r in st_uni if r['code'].endswith(('.SH', '.SZ'))})
    st_names = {r['code']: r['name'] for r in st_uni}
    st_batches = [(f'eodst_{i//10:04d}', st_codes[i:i + 10]) for i in range(0, len(st_codes), 10)]
    st_results = {}
    with ThreadPoolExecutor(max_workers=F.CONC) as ex:
        for k, (name, d) in enumerate(ex.map(F.fetch_batch, st_batches), 1):
            st_results[name] = d
    st_byc = F.collect(st_results, st_batches, st_codes, cutoff=CUTOFF)
    st_recs, st_exc, _ = F.build_recs(st_byc, st_codes, st_names, expect=EXPECT)
    st_out = P.DATA / 'inbox' / f'eod_st_{F.DATE}.csv'
    st_out.parent.mkdir(parents=True, exist_ok=True)
    with st_out.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['date', 'code', 'name', 'close_unadjusted',
                                          'return_pct', 'amount_yuan',
                                          'volume_shares', 'turnover_pct'])
        w.writeheader(); w.writerows(st_recs)
    print(f'  ST 样本 {len(st_recs)}（剔除 {len(st_exc)}）→ {st_out.name}')

    print('[3/3] 核算与写入')
    byc = F.collect(results, batches, codes, cutoff=CUTOFF)
    recs, excluded, warn = F.build_recs(byc, codes, names, expect=EXPECT)

    # 缺股补取：小时频偶发超时/限流，同一晚补两轮，避免因几十只股票拉低样本
    for attempt in (1, 2):
        have = {r['code'] for r in recs}
        missing = [c for c in codes if c not in have]
        if len(missing) < 5:
            break
        print(f'  补取第 {attempt} 轮：缺 {len(missing)} 只')
        rb = [(f'eodr{attempt}_{i//10:04d}', missing[i:i + 10]) for i in range(0, len(missing), 10)]
        rres = {}
        with ThreadPoolExecutor(max_workers=F.CONC) as ex:
            for name, d in ex.map(F.fetch_batch, rb):
                rres[name] = d
        rbyc = F.collect(rres, rb, missing, cutoff=CUTOFF)
        rrecs, rexc, rw = F.build_recs(rbyc, missing, names, expect=EXPECT)
        recs += rrecs
        excluded += rexc
        warn += rw
        print(f'    补到 {len(rrecs)} 只')

    seen, uniq = set(), []
    for r in recs:
        if r['code'] in seen:
            continue
        seen.add(r['code'])
        uniq.append(r)
    recs = sorted(uniq, key=lambda r: r['code'])
    out = P.DATA / 'inbox' / f'eod_{F.DATE}.csv'
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['date', 'code', 'name', 'close_unadjusted',
                                          'return_pct', 'amount_yuan',
                                          'volume_shares', 'turnover_pct'])
        w.writeheader()
        w.writerows(recs)

    A = sum(1 for r in recs if float(r['return_pct']) > 0)
    D = sum(1 for r in recs if float(r['return_pct']) < 0)
    Ep = sum(float(r['amount_yuan']) for r in recs if float(r['return_pct']) > 0)
    En = sum(float(r['amount_yuan']) for r in recs if float(r['return_pct']) < 0)
    print(f'  写入 {out}')
    print(f'  样本 {len(recs)}（池 {len(codes)}，剔除 {len(excluded)}） A/D/U={A}/{D}/{len(recs)-A-D}')
    if A + D:
        print(f'  p={100*A/(A+D):.4f}%  q={100*Ep/(Ep+En):.4f}%  '
              f'G={100*Ep/(Ep+En)-100*A/(A+D):+.4f}pp  TRIN={(A/D)/(Ep/En):.4f}')
    if excluded:
        print('  剔除样例:', excluded[:6])
    if warn:
        print(f'  涨跌链条差异 {len(warn)} 只：{warn[:5]}')

    # 硬校验：不过就非零退出，让定时任务的复检能立刻发现
    errs = []
    if len(recs) < 4500:
        errs.append(f'样本 {len(recs)} < 4500')
    if A + D < 4000:
        errs.append(f'A+D={A + D} 过小')
    if Ep <= 0 or En <= 0:
        errs.append('涨/跌组成交额为零')
    bad_amt = sum(1 for r in recs if float(r['amount_yuan']) <= 0)
    if bad_amt > len(recs) * 0.02:
        errs.append(f'成交额非正 {bad_amt} 只 > 2%')
    if errs:
        print('  [FAIL] ' + '；'.join(errs))
        sys.exit(2)
    print(f'  [OK] 校验通过：{len(recs)} 行，A+D={A + D}，A+D+U={len(recs)}')
    allr = recs + st_recs
    A2 = sum(1 for r in allr if float(r['return_pct']) > 0)
    D2 = sum(1 for r in allr if float(r['return_pct']) < 0)
    print(f'  含ST口径：A/D/U={A2}/{D2}/{len(allr)-A2-D2}  合计 {len(allr)}')
    if len(recs) < 4500:
        print('  !! 样本不足 4,500，禁止写入：请检查是否在收盘后运行、或接口是否截断')

if __name__ == '__main__':
    main()
