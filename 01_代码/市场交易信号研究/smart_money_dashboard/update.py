#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
聪明钱温度计 —— 增量更新入口（供定时任务调用）

用法：
  python3 update.py status
  python3 update.py eod  --snapshot <csv> [--date YYYY-MM-DD] [--a A --d D --u U] [--etf 元] [--force] [--dry-run]
  python3 update.py noon --snapshot <csv> [--date YYYY-MM-DD] [--force] [--dry-run]

约定：
  * --snapshot 必须是逐股明细（code, return_pct, amount_yuan 必需；turnover_pct 可选）
  * --a/--d/--u 是**含 ST 的沪深A股**涨跌家数（iFinD「A股涨跌家数统计」报表）。缺省则本次不写 MCL 底库。
  * 午盘不写 MCL 底库：午盘池剔 ST，与 MCL 的含 ST 池不同口径，混写会污染 291 日序列。
  * 所有写入都是「校验通过才落盘」；任何一项不通过就整次拒绝，不产生半截数据。
"""
import argparse, csv, glob, json, os, subprocess, sys
from datetime import date as _date

BASE = os.path.dirname(os.path.abspath(__file__))
import smd_paths as P
STORE = str(P.DATA / 'store')
SNAP = os.path.join(STORE, 'snapshots')

def rd(p):
    with open(p, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def wr(p, header, rows):
    with open(p, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)

def die(msg):
    print('REJECT: ' + msg)
    sys.exit(2)

# ---------------------------------------------------------------- 校验与计算
def load_snapshot(path, expect_date=None, min_rows=4500):
    if not os.path.exists(path):
        die(f'快照不存在：{path}')
    rows = rd(path)
    if len(rows) < min_rows:
        die(f'行数只有 {len(rows)}，低于 {min_rows} 的完整性下限（疑似截断）')
    need = {'code', 'return_pct', 'amount_yuan'}
    miss = need - set(rows[0].keys())
    if miss:
        die(f'缺少必需列：{sorted(miss)}')

    codes = [r['code'] for r in rows]
    if len(set(codes)) != len(codes):
        dup = len(codes) - len(set(codes))
        die(f'存在 {dup} 个重复代码')

    dates = {r.get('date', '').strip()[:10] for r in rows if r.get('date')}
    if len(dates) > 1:
        die(f'快照包含多个日期：{sorted(dates)[:5]}')
    if expect_date and dates and expect_date not in dates:
        die(f'快照日期 {sorted(dates)} 与指定日期 {expect_date} 不一致')

    bad_amt = sum(1 for r in rows if not r['amount_yuan'] or float(r['amount_yuan'] or 0) <= 0)
    if bad_amt > len(rows) * 0.02:
        die(f'{bad_amt} 行成交额为空或非正，超过 2% 容差')

    return rows, (sorted(dates)[0] if dates else expect_date)

def aggregate(rows):
    A = D = U = 0
    Ep = En = 0.0
    h5 = 0
    for r in rows:
        ret = float(r['return_pct'])
        amt = float(r['amount_yuan'] or 0)
        to = r.get('turnover_pct') or r.get('vendor_hourly_turnover_pct')
        if ret > 0:
            A += 1; Ep += amt
        elif ret < 0:
            D += 1; En += amt
        else:
            U += 1
        try:
            if to and float(to) > 5:
                h5 += 1
        except ValueError:
            pass
    if A + D < 1000:
        die(f'涨跌家数只有 {A + D}，样本异常')
    if Ep <= 0 or En <= 0:
        die('某一组成交额为 0，无法计算 TRIN')
    p = 100.0 * A / (A + D)
    q = 100.0 * Ep / (Ep + En)
    trin = (A / D) / (Ep / En)
    return {'A': A, 'D': D, 'U': U, 'n': len(rows), 'p': p, 'q': q,
            'G': q - p, 'trin': trin, 'Ep': Ep, 'En': En, 'h5': h5}

# ---------------------------------------------------------------- 写入
def append_breadth(d, A, D, U, source, force=False):
    path = os.path.join(STORE, 'breadth_daily.csv')
    rows = rd(path)
    exist = {r['date']: r for r in rows}
    if d in exist and not force:
        die(f'breadth_daily 已存在 {d}，如需覆盖请加 --force')
    if d in exist:
        rows = [r for r in rows if r['date'] != d]
    rows.append({'date': d, 'A': str(A), 'D': str(D), 'U': str(U), 'source': source})
    rows.sort(key=lambda r: r['date'])
    # 单调性检查：家数不应出现 0 或负数，且 A+D 不低于 3000
    for r in rows:
        if int(r['A']) + int(r['D']) < 3000:
            die(f"{r['date']} 的 A+D 只有 {int(r['A'])+int(r['D'])}，疑似错列")
    wr(path, ['date', 'A', 'D', 'U', 'source'],
       [[r['date'], r['A'], r['D'], r['U'], r['source']] for r in rows])
    return len(rows)

def append_agg(d, t, kind, agg, source, force=False):
    path = os.path.join(STORE, 'daily_agg.csv')
    rows = rd(path)
    key = (d, kind)
    exist = {(r['date'], r['kind']) for r in rows}
    if key in exist and not force:
        die(f'daily_agg 已存在 {d} {kind}，如需覆盖请加 --force')
    rows = [r for r in rows if (r['date'], r['kind']) != key]
    rows.append({'date': d, 'time': t, 'kind': kind,
                 'p': f'{agg["p"]:.6f}', 'q': f'{agg["q"]:.6f}',
                 'trin_e': f'{agg["trin"]:.6f}', 'G': f'{agg["G"]:.6f}',
                 'n': str(agg['n']), 'source': source})
    rows.sort(key=lambda r: (r['date'], r['time']))
    wr(path, ['date', 'time', 'kind', 'p', 'q', 'trin_e', 'G', 'n', 'source'],
       [[r['date'], r['time'], r['kind'], r['p'], r['q'], r['trin_e'], r['G'], r['n'], r['source']] for r in rows])
    return len(rows)

def append_noon_breadth(d, A, D_, U, n_st, source, force=False):
    path = os.path.join(STORE, 'noon_breadth.csv')
    rows = rd(path) if os.path.exists(path) else []
    if any(r['date'] == d for r in rows) and not force:
        die(f'noon_breadth 已存在 {d}，如需覆盖请加 --force')
    rows = [r for r in rows if r['date'] != d]
    rows.append({'date': d, 'A': str(A), 'D': str(D_), 'U': str(U),
                 'n_st': str(n_st), 'source': source})
    rows.sort(key=lambda r: r['date'])
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f); w.writerow(['date', 'A', 'D', 'U', 'n_st', 'source'])
        for r in rows:
            w.writerow([r['date'], r['A'], r['D'], r['U'], r['n_st'], r['source']])
    return len(rows)

def append_etf(d, amount_yuan, force=False):
    path = os.path.join(STORE, 'etf_daily.csv')
    rows = rd(path)
    if any(r['date'] == d for r in rows) and not force:
        die(f'etf_daily 已存在 {d}，如需覆盖请加 --force')
    rows = [r for r in rows if r['date'] != d]
    rows.append({'date': d, 'amount_yuan': str(int(amount_yuan))})
    rows.sort(key=lambda r: r['date'])
    wr(path, ['date', 'amount_yuan'], [[r['date'], r['amount_yuan']] for r in rows])
    return len(rows)

def copy_snapshot(src, kind, d):
    os.makedirs(SNAP, exist_ok=True)
    dst = os.path.join(SNAP, f'{kind}_{d}.csv')
    if os.path.abspath(src) == os.path.abspath(dst):
        return dst                      # 已在仓内，避免自拷贝把文件截断
    tmp = dst + '.tmp'
    with open(src, 'rb') as fi, open(tmp, 'wb') as fo:
        fo.write(fi.read())
    os.replace(tmp, dst)
    return dst

def preflight(d, kind, force):
    """写之前先查重，避免任何写入后才发现冲突"""
    b = rd(os.path.join(STORE, 'breadth_daily.csv'))
    if kind in ('eod', 'breadth') and any(r['date'] == d for r in b) and not force:
        die(f'breadth_daily 已存在 {d}，如需覆盖请加 --force')
    if kind == 'breadth':
        return
    a = rd(os.path.join(STORE, 'daily_agg.csv'))
    if any(r['date'] == d and r['kind'] == kind for r in a) and not force:
        die(f'daily_agg 已存在 {d} {kind}，如需覆盖请加 --force')

def rebuild():
    for cmd in (['python3', 'compute.py'], ['python3', 'render.py']):
        r = subprocess.run(cmd, cwd=BASE, capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stdout[-2000:]); print(r.stderr[-2000:])
            die(f'{" ".join(cmd)} 失败')
        print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else '')

# ---------------------------------------------------------------- 命令
def cmd_status(_):
    b = rd(os.path.join(STORE, 'breadth_daily.csv'))
    e = rd(os.path.join(STORE, 'etf_daily.csv'))
    a = rd(os.path.join(STORE, 'daily_agg.csv'))
    mp = os.path.join(STORE, 'ma_breadth.csv')
    m = rd(mp) if os.path.exists(mp) else []
    fb = os.path.join(STORE, 'futures_basis.csv')
    f = rd(fb) if os.path.exists(fb) else []
    tdp = os.path.join(STORE, 'turnover_daily.csv')
    td = rd(tdp) if os.path.exists(tdp) else []
    idp = os.path.join(STORE, 'index_daily.csv')
    ix = rd(idp) if os.path.exists(idp) else []
    snaps = sorted(os.path.basename(p) for p in glob.glob(os.path.join(SNAP, '*.csv')))
    # 今日 MCP 调用计数（按脚本）
    usage = {}
    up = os.path.join(STORE, 'mcp_usage.csv')
    if os.path.exists(up):
        today = str(_date.today())
        with open(up, encoding='utf-8') as fh:
            for r in csv.DictReader(fh):
                if r['date'] == today:
                    usage[r['script']] = usage.get(r['script'], 0) + 1
    print(json.dumps({
        'breadth_last': b[-1]['date'], 'breadth_rows': len(b),
        'etf_last': e[-1]['date'], 'etf_rows': len(e),
        'agg_last': a[-1]['date'] + ' ' + a[-1]['kind'], 'agg_rows': len(a),
        'ma_last': m[-1]['date'] if m else None,
        'ma_days': len({r['date'] for r in m}),
        'fut_last': f[-1]['date'] if f else None,
        'fut_days': len({r['date'] for r in f}),
        'index_last': ix[-1]['date'] if ix else None,
        'turn_last': td[-1]['date'] if td else None,
        'turn_days': len(td),
        'snapshots': snaps[-4:],
        'today': str(_date.today()),
        'mcp_calls_today': sum(usage.values()),
        'mcp_calls_by_script': usage,
    }, ensure_ascii=False, indent=1))

def grouped(args, d):
    """没有逐股快照时，用已聚合的 p/q/n 构造 agg（调用方自证来源与时间点）"""
    if not (args.p and args.q and args.n):
        die('既没有 --snapshot，也没有 --p/--q/--n')
    p, q, n = float(args.p), float(args.q), int(args.n)
    if not (0 < p < 100 and 0 < q < 100):
        die(f'p={p} q={q} 超出 (0,100)')
    if n < 3000:
        die(f'样本数 {n} 过小')
    G = q - p
    trin = (p / (100 - p)) / (q / (100 - q))
    return {'A': 0, 'D': 0, 'U': 0, 'n': n, 'p': p, 'q': q, 'G': G,
            'trin': trin, 'Ep': 0.0, 'En': 0.0, 'h5': 0}

def cmd_eod(args):
    """日终写入。两种输入：逐股快照（--snapshot）或预聚合（--p/--q/--n + --a/--d/--u）。"""
    rows = None
    if args.snapshot:
        rows, d = load_snapshot(args.snapshot, args.date)
        d = d or args.date or str(_date.today())
        agg = aggregate(rows)
    else:
        d = args.date or str(_date.today())
        agg = grouped(args, d)
    src = '逐股快照' if args.snapshot else '预聚合'
    print(f'[{d}] {src} n={agg["n"]} | p {agg["p"]:.3f}% q {agg["q"]:.3f}% '
          f'G {agg["G"]:+.3f}pp TRIN {agg["trin"]:.4f} | H5 {agg["h5"]}')

    # 含ST家数：优先由两个逐股快照合成；否则用 --a/--d/--u 直接传入
    nb = None
    if args.st_snapshot:
        if not rows:
            die('--st-snapshot 只能配合 --snapshot 使用；预聚合模式请直接用 --a/--d/--u 传含ST家数')
        st_rows, _ = load_snapshot(args.st_snapshot, args.date, min_rows=50)
        overlap = {r['code'] for r in rows} & {r['code'] for r in st_rows}
        if overlap:
            die(f'ST 快照与主池有 {len(overlap)} 个重复代码，口径矛盾')
        nb = aggregate(rows + st_rows)
        prev = rd(os.path.join(STORE, 'breadth_daily.csv'))[-1]
        prev_n = int(prev['A']) + int(prev['D']) + int(prev['U'])
        if abs(nb['n'] - prev_n) / prev_n > 0.01:
            die(f'含ST合计 {nb["n"]} 与上一交易日 {prev_n} 相差超过 1%，疑似池子不完整')
        print(f'  含ST口径：A/D/U {nb["A"]}/{nb["D"]}/{nb["U"]}（合计 {nb["n"]}，ST {len(st_rows)} 只）')

    A = int(args.a) if args.a else None
    Dn = int(args.d_) if args.d_ else None
    U = int(args.u) if args.u else None
    if A and Dn and U:
        if nb:
            die('同时提供了 --st-snapshot 与 --a/--d/--u，口径冲突')
        if A + Dn < 4000:
            die(f'含ST A+D={A + Dn} 过小，疑似错列')
        if U < 0:
            die('平盘家数不能为负')
        print(f'  含ST家数 {A}/{Dn}/{U}，将写入 MCL 底库')

    preflight(d, 'eod', args.force)
    if args.dry_run:
        print('DRY-RUN：校验通过，未写入'); return

    if args.snapshot:
        copy_snapshot(args.snapshot, 'eod', d)

    if nb:
        n = append_breadth(d, nb['A'], nb['D'], nb['U'],
                           'iFinD 逐股快照 · 含ST（主池+ST补充）', args.force)
        print(f'  breadth_daily 现有 {n} 行（MCL：含ST）')
    elif A and Dn and U:
        n = append_breadth(d, A, Dn, U, args.source or '预聚合 · 含ST', args.force)
        print(f'  breadth_daily 现有 {n} 行（MCL：含ST）')
    else:
        print('  未提供含ST家数：本次不写 MCL 底库（MCL 停留在上一交易日）')

    n = append_agg(d, 'close', 'eod', agg, args.source or 'iFinD/Wind · 含ST', args.force)
    print(f'  daily_agg 现有 {n} 行')
    if args.etf:
        v = float(args.etf)
        if not (1e9 < v < 5e11):
            die(f'ETF 合计成交额 {v} 元超出合理区间')
        n = append_etf(d, v, args.force)
        print(f'  etf_daily 现有 {n} 行')
    rebuild()

def cmd_noon(args):
    if args.snapshot:
        rows, d = load_snapshot(args.snapshot, args.date)
        d = d or args.date or str(_date.today())
        agg = aggregate(rows)
    else:
        d = args.date or str(_date.today())
        agg = grouped(args, d)
    src = '逐股快照' if args.snapshot else '预聚合'
    print(f'[{d} 11:30] {src} n={agg["n"]} | p {agg["p"]:.3f}% q {agg["q"]:.3f}% '
          f'G {agg["G"]:+.3f}pp TRIN {agg["trin"]:.4f}')
    print('  午盘不写 MCL 底库（剔ST池 ≠ 含ST池），只更新资金模块')
    preflight(d, 'noon', args.force)

    nb = None
    if args.st_snapshot:
        st_rows, _ = load_snapshot(args.st_snapshot, args.date, min_rows=50)
        base = {r['code'] for r in (rd(args.snapshot) if args.snapshot else [])}
        overlap = base & {r['code'] for r in st_rows}
        if overlap:
            die(f'ST 快照与主池有 {len(overlap)} 个重复代码，口径矛盾')
        allrows = (rd(args.snapshot) if args.snapshot else []) + st_rows
        nb = aggregate(allrows)
        prev = rd(os.path.join(STORE, 'breadth_daily.csv'))[-1]
        prev_n = int(prev['A']) + int(prev['D']) + int(prev['U'])
        if abs(nb['n'] - prev_n) / prev_n > 0.01:
            die(f'含ST合计 {nb["n"]} 与上一交易日 {prev_n} 相差超过 1%，疑似池子不完整')
        print(f'  含ST口径：A/D/U {nb["A"]}/{nb["D"]}/{nb["U"]}（合计 {nb["n"]}，ST {len(st_rows)} 只）')
    if args.dry_run:
        print('DRY-RUN：校验通过，未写入'); return
    copy_snapshot(args.snapshot, 'noon', d)
    n = append_agg(d, '11:30', 'noon', agg, args.source or 'iFinD · 午盘 · 剔ST', args.force)
    print(f'  daily_agg 现有 {n} 行')
    if nb:
        ns = append_noon_breadth(d, nb['A'], nb['D'], nb['U'], len(st_rows),
                                 'iFinD 11:30 · 含ST（主池+ST补充）', args.force)
        print(f'  noon_breadth 现有 {ns} 行（用于 MCL 午盘预览）')
    rebuild()

def cmd_snap(args):
    """只把逐股快照存进 store/snapshots，不动 agg/breadth。
    用途：17:00 写 agg 成功但快照文件缺失（或反过来）时的定点修复。"""
    d = args.date or str(_date.today())
    rows, _ = load_snapshot(args.snapshot, d)
    print(f'[{d}] 快照 {len(rows)} 行，校验通过')
    if args.dry_run:
        print('DRY-RUN：未写入'); return
    dst = copy_snapshot(args.snapshot, 'eod', d)
    print(f'  已存 {dst}')
    rebuild()

def cmd_rebuild(_):
    """只重建页面，不动数据。用于「数据已写入但渲染失败」的恢复。"""
    rebuild()

def cmd_breadth(args):
    d = args.date or str(_date.today())
    A, D, U = int(args.a), int(args.dd), int(args.u)
    if A + D < 3000:
        die(f'A+D={A+D} 过小')
    if A + D + U < 3000:
        die('合计过小')
    preflight(d, 'breadth', args.force)
    print(f'[{d}] 含ST家数 {A}/{D}/{U}，合计 {A+D+U}')
    if args.dry_run:
        print('DRY-RUN：校验通过，未写入'); return
    n = append_breadth(d, A, D, U, args.source or 'ifind_A_share_advance_decline_report', args.force)
    print(f'  breadth_daily 现有 {n} 行（仅更新 MCL，成交分布仍停在上一个快照日）')
    rebuild()

def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='cmd', required=True)

    s0 = sub.add_parser('status'); s0.set_defaults(func=cmd_status)

    s1 = sub.add_parser('eod')
    s1.add_argument('--snapshot')
    s1.add_argument('--p'); s1.add_argument('--q'); s1.add_argument('--n')
    s1.add_argument('--date')
    s1.add_argument('--a'); s1.add_argument('--d', dest='d_'); s1.add_argument('--u')
    s1.add_argument('--etf')
    s1.add_argument('--st-snapshot')
    s1.add_argument('--source')
    s1.add_argument('--force', action='store_true')
    s1.add_argument('--dry-run', action='store_true')
    s1.set_defaults(func=cmd_eod)

    s2 = sub.add_parser('noon')
    s2.add_argument('--snapshot')
    s2.add_argument('--p'); s2.add_argument('--q'); s2.add_argument('--n')
    s2.add_argument('--st-snapshot')
    s2.add_argument('--date')
    s2.add_argument('--source')
    s2.add_argument('--force', action='store_true')
    s2.add_argument('--dry-run', action='store_true')
    s2.set_defaults(func=cmd_noon)

    s3 = sub.add_parser('breadth')
    s3.add_argument('--a', required=True); s3.add_argument('--d', dest='dd', required=True)
    s3.add_argument('--u', required=True)
    s3.add_argument('--date'); s3.add_argument('--source')
    s3.add_argument('--force', action='store_true'); s3.add_argument('--dry-run', action='store_true')
    s3.set_defaults(func=cmd_breadth)

    s4 = sub.add_parser('rebuild'); s4.set_defaults(func=cmd_rebuild)

    s5 = sub.add_parser('snap')
    s5.add_argument('--snapshot', required=True)
    s5.add_argument('--date')
    s5.add_argument('--dry-run', action='store_true')
    s5.set_defaults(func=cmd_snap)

    args = p.parse_args()
    args.func(args)

if __name__ == '__main__':
    main()
