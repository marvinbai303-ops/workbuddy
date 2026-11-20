#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扶摇（hithink-finance）收盘快照取数与聚合 —— 独立旁路，不写主库。

定位：与现有 17:00 任务并行跑的一份「第二数据源」，用于交叉校验。
      它只写 data/store/hithink_agg.csv 与 hithink_snapshots/，
      绝不触碰 breadth_daily.csv / daily_agg.csv，避免污染正式序列。

口径：market.snapshot 一次请求返回全市场（约 5,584 条），字段为
      thscode / last_price / price_change_ratio_pct / turnover / volume。
      默认池 = 沪深A股含ST（.SH/.SZ），与 MCL 底库一致；--with-bj 可加北交所。

计费：扶摇当前免费、只做频率限流，本脚本一次运行 = 1 个 HTTP 请求。

用法：
    python3 fetch_hithink.py                # 取当日收盘快照
    python3 fetch_hithink.py --date 2026-11-19
    python3 fetch_hithink.py --allow-intraday   # 盘中试跑（数值非最终）
"""
import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import date, datetime

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import smd_paths as P

STORE = str(P.DATA / 'store')
SNAPDIR = os.path.join(STORE, 'hithink_snapshots')
AGG = os.path.join(STORE, 'hithink_agg.csv')
NOON_AGG = os.path.join(STORE, 'hithink_noon_agg.csv')
FIELDS = ['date', 'A', 'D', 'U', 'n', 'p', 'q', 'G', 'trin', 'amt_yuan', 'ts', 'pool']

BIN_CANDIDATES = [
    'hithink-finance',
    os.path.expanduser('~/.workbuddy/binaries/node/cli-connector-packages/bin/hithink-finance'),
]


def cli_path():
    for c in BIN_CANDIDATES:
        p = shutil.which(c) if os.sep not in c else (c if os.path.exists(c) else None)
        if p:
            return p
    sys.exit('找不到 hithink-finance 可执行文件')


def snapshot(with_bj=False):
    """一次请求拿全市场快照，返回 (items, timestamp)。"""
    tmp = os.path.join(tempfile.gettempdir(), f'hithink_snap_{os.getpid()}.json')
    cmd = [cli_path(), 'market', 'snapshot', '--limit', '6000',
           '--max-rows', '0', '--output', tmp, '--file-format', 'json', '--format', 'json']
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        sys.exit(f'扶摇取数失败（exit {r.returncode}）：{(r.stderr or r.stdout)[:400]}')
    d = json.load(open(tmp, encoding='utf-8'))
    os.unlink(tmp)
    if not d.get('ok'):
        sys.exit(f'扶摇返回异常：{json.dumps(d, ensure_ascii=False)[:400]}')
    data = d['data']
    items = data.get('item') or []
    ts = data.get('timestamp')
    suffix = ('.SH', '.SZ', '.BJ') if with_bj else ('.SH', '.SZ')
    keep = [x for x in items
            if x['thscode'].endswith(suffix)
            and x.get('price_change_ratio_pct') is not None
            and x.get('turnover') is not None]
    return keep, ts


def aggregate(items):
    A = D = 0
    Ep = En = 0.0
    for x in items:
        r, a = x['price_change_ratio_pct'], x['turnover']
        if r > 0:
            A += 1; Ep += a
        elif r < 0:
            D += 1; En += a
    if A == 0 or D == 0 or Ep <= 0 or En <= 0:
        sys.exit(f'聚合失败：A={A} D={D} E+={Ep} E-={En}，疑似数据不完整')
    p = 100.0 * A / (A + D)
    q = 100.0 * Ep / (Ep + En)
    return {
        'A': A, 'D': D, 'U': len(items) - A - D, 'n': len(items),
        'p': p, 'q': q, 'G': q - p, 'trin': (A / D) / (Ep / En),
        'amt_yuan': Ep + En,
    }


def ts_note_intraday(ts):
    """快照是否取自收盘前（用于拦截 promote）。"""
    if not ts:
        return False
    try:
        dt = datetime.fromtimestamp(int(ts) / 1000)
        return dt.hour * 60 + dt.minute < 15 * 60
    except Exception:
        return True


def ts_dt(ts):
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(int(ts) / 1000)
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', default=str(date.today()))
    ap.add_argument('--session', choices=('close', 'noon'), default='close',
                    help='close=收盘快照（写 hithink_agg + 正式库 eod）；'
                         'noon=11:30 午盘快照（写 hithink_noon_agg + 正式库 noon）')
    ap.add_argument('--with-bj', action='store_true', help='池子包含北交所')
    ap.add_argument('--allow-intraday', action='store_true', help='时点未到也允许写入（数值非最终）')
    ap.add_argument('--promote', action='store_true',
                    help='把聚合值写入正式库（breadth_daily + daily_agg），走 update.py 的校验')
    ap.add_argument('--force', action='store_true', help='同日已存在时覆盖（配合 --promote）')
    ap.add_argument('--etf', help='三只宽基 ETF 当日合计成交额（元），仅收盘场次随 promote 写入')
    ap.add_argument('--dry-run', action='store_true', help='只取数与核算，不落盘、不写正式库')
    args = ap.parse_args()

    is_noon = args.session == 'noon'
    label = '午盘' if is_noon else '收盘'
    now = datetime.now()
    mins = now.hour * 60 + now.minute
    if not args.allow_intraday:
        if is_noon and mins < 11 * 60 + 32:
            sys.exit(f'现在 {now:%H:%M} 未到 11:30 午盘收盘，快照不可用。确需试跑请加 --allow-intraday。')
        if not is_noon and mins < 15 * 60 + 5:
            sys.exit(f'现在 {now:%H:%M} 未收盘，快照不是最终值。确需试跑请加 --allow-intraday。')

    items, ts = snapshot(args.with_bj)
    agg = aggregate(items)
    pool = '沪深A股含ST' + ('+北交所' if args.with_bj else '')
    dt = ts_dt(ts)

    if dt and args.date and dt.date().isoformat() != args.date:
        sys.exit(f'快照时间 {dt:%Y-%m-%d %H:%M} 与 --date {args.date} 不一致')

    # 时点校验：午盘必须是 11:30–15:00 之间取的，收盘必须 15:00 之后
    if dt and not args.allow_intraday:
        m = dt.hour * 60 + dt.minute
        if is_noon and not (11 * 60 + 30 <= m < 15 * 60):
            sys.exit(f'拒绝写入午盘库：快照时间 {dt:%H:%M} 不在 11:30–15:00 区间')
        if not is_noon and m < 15 * 60:
            sys.exit('拒绝 promote：快照不是收盘后取的')

    agg_path = NOON_AGG if is_noon else AGG
    snap_file = f"noon_snap_{args.date}.csv" if is_noon else f"snap_{args.date}.csv"
    sp = os.path.join(SNAPDIR, snap_file)

    print(f"[{args.date}] 扶摇{label}快照 {agg['n']} 只（{pool}）"
          + (f" · 快照时间 {dt:%H:%M}" if dt else ''))
    print(f"  A/D/U {agg['A']}/{agg['D']}/{agg['U']}  "
          f"p {agg['p']:.4f}%  q {agg['q']:.4f}%  G {agg['G']:+.4f}pp  TRIN {agg['trin']:.4f}")
    print(f"  成交额 {agg['amt_yuan']/1e12:.4f} 万亿")

    if args.dry_run:
        print(f'  DRY-RUN：将写 {os.path.basename(agg_path)} 与 {snap_file}，未落盘')
        if args.promote:
            print('  DRY-RUN：跳过正式库写入')
        return

    os.makedirs(SNAPDIR, exist_ok=True)
    with open(sp, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['code', 'last_price', 'chg_pct', 'turnover_yuan', 'volume_shares'])
        for x in sorted(items, key=lambda y: y['thscode']):
            w.writerow([x['thscode'], x['last_price'], x['price_change_ratio_pct'],
                        f"{x['turnover']:.2f}", x['volume']])

    old = {}
    if os.path.exists(agg_path):
        with open(agg_path, encoding='utf-8-sig') as f:
            old = {r['date']: r for r in csv.DictReader(f)}
    old[args.date] = {
        'date': args.date, 'A': agg['A'], 'D': agg['D'], 'U': agg['U'], 'n': agg['n'],
        'p': f"{agg['p']:.6f}", 'q': f"{agg['q']:.6f}", 'G': f"{agg['G']:.6f}",
        'trin': f"{agg['trin']:.6f}", 'amt_yuan': f"{agg['amt_yuan']:.2f}",
        'ts': ts or '', 'pool': pool,
    }
    with open(agg_path, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for d in sorted(old):
            w.writerow(old[d])

    print(f"  逐股 → {sp}")
    print(f"  聚合 → {agg_path}")

    if args.promote:
        if is_noon:
            if args.etf:
                print('  ⚠ 午盘场次不写 ETF，--etf 已忽略')
            cmd = [sys.executable, os.path.join(BASE, 'update.py'), 'noon',
                   '--p', f"{agg['p']:.6f}", '--q', f"{agg['q']:.6f}", '--n', str(agg['n']),
                   '--a', str(agg['A']), '--d', str(agg['D']), '--u', str(agg['U']),
                   '--date', args.date, '--source', '扶摇 11:30 快照 · 含ST']
        else:
            cmd = [sys.executable, os.path.join(BASE, 'update.py'), 'eod',
                   '--p', f"{agg['p']:.6f}", '--q', f"{agg['q']:.6f}", '--n', str(agg['n']),
                   '--a', str(agg['A']), '--d', str(agg['D']), '--u', str(agg['U']),
                   '--date', args.date, '--source', '扶摇 收盘快照 · 含ST']
            if args.etf:
                cmd += ['--etf', str(args.etf)]
        if args.force:
            cmd.append('--force')
        print('  → 写入正式库：', ' '.join(cmd[-6:]))
        r = subprocess.run(cmd, text=True)
        if r.returncode != 0:
            sys.exit(f'promote 失败（exit {r.returncode}），正式库未更新')


if __name__ == '__main__':
    main()
